// Regression: ISSUE-005 — 결과 필터 칩이 현재 페이지와 전체 기간을 섞어 세던 문제
//             ISSUE-006 — outcome 을 'Win'/'Loss' 로 비교해 추세 분석이 항상 비어 있던 문제
// Found by /qa on 2026-09-01
// Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-01.md

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

// 현재 페이지에는 3승 2패만 담고, 전체 기간 KPI 는 71승 105패로 크게 벌려 둔다.
// 칩이 KPI 를 쓰면 3/2 대신 71/105 가 나오므로 두 기준이 갈리는지 바로 드러난다.
const PAGE_TRADES = [
  { id: 1, code: '005930', name: '삼성전자', date: '2026-05-05', grade: 'A', outcome: 'WIN', roi: 9, entry: 100, days: 1, market: 'KOSPI', maxHigh: 110, score: 12, themes: [], priceTrail: [] },
  { id: 2, code: '000660', name: 'SK하이닉스', date: '2026-05-05', grade: 'B', outcome: 'WIN', roi: 9, entry: 100, days: 1, market: 'KOSPI', maxHigh: 110, score: 11, themes: [], priceTrail: [] },
  { id: 3, code: '035720', name: '카카오', date: '2026-05-04', grade: 'B', outcome: 'LOSS', roi: -5, entry: 100, days: 1, market: 'KOSPI', maxHigh: 101, score: 10, themes: [], priceTrail: [] },
  { id: 4, code: '051910', name: 'LG화학', date: '2026-05-04', grade: 'A', outcome: 'WIN', roi: 9, entry: 100, days: 1, market: 'KOSPI', maxHigh: 110, score: 12, themes: [], priceTrail: [] },
  { id: 5, code: '207940', name: '삼성바이오', date: '2026-05-03', grade: 'B', outcome: 'LOSS', roi: -5, entry: 100, days: 1, market: 'KOSPI', maxHigh: 101, score: 9, themes: [], priceTrail: [] },
];

const KPI = {
  totalSignals: 176,
  wins: 71,
  losses: 105,
  open: 0,
  winRate: 40.3,
  avgRoi: 0.65,
  totalRoi: 114,
  avgDays: 2.1,
  profitFactor: 1.22,
  priceDate: '2026-05-22',
  roiByGrade: {},
};

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        trades: PAGE_TRADES,
        kpi: KPI,
        pagination: { page: 1, limit: 50, total: 176, totalPages: 4 },
      }),
    })),
  );
});

/** FilterButton 은 라벨과 (건수)를 별도 노드로 렌더하므로 버튼 전체 텍스트로 찾는다. */
function chipLabels(): string[] {
  return screen
    .getAllByRole('button')
    .map((button) => (button.textContent || '').replace(/\s+/g, ' ').trim())
    .filter((text) => /^(전체|성공|실패|보유) \(\d+\)$/.test(text));
}

describe('CumulativeClientPage', () => {
  it('결과 칩은 현재 페이지 기준으로 세어 전체 = 성공 + 실패 + 보유가 맞는다', async () => {
    render(<CumulativeClientPage />);

    await waitFor(() => {
      expect(chipLabels()).toContain('전체 (5)');
    });

    const labels = chipLabels();
    expect(labels).toContain('성공 (3)');
    expect(labels).toContain('실패 (2)');
    expect(labels).toContain('보유 (0)');
    // 전체 기간 KPI 값이 칩으로 새어 나오면 안 된다.
    expect(labels).not.toContain('성공 (71)');
    expect(labels).not.toContain('실패 (105)');
  });

  it('추세 분석이 대문자 outcome 을 인식해 실제 최근 승률을 계산한다', async () => {
    render(<CumulativeClientPage />);

    await waitFor(() => {
      expect(chipLabels()).toContain('전체 (5)');
    });

    // 5건 중 3승이므로 60%. 대소문자가 어긋나면 closedTrades 가 비어 '-' 가 된다.
    expect(screen.queryByText('60%')).not.toBeNull();
  });
});
