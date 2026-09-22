// Regression: ISSUE-005 — 결과 필터 칩이 현재 페이지와 전체 기간을 섞어 세던 문제
//             최근 지표는 현재 페이지 행이 아니라 서버 KPI를 읽는다.
// Found by /qa on 2026-09-01
// Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-01.md

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

// 현재 페이지에는 3승 2패만 담고, 전체 기간 KPI 는 71승 105패로 크게 벌려 둔다.
// [FLOW-017] 부터 칩은 서버가 전체 목록에서 센 counts(5승 3패 1보유)를 읽는다.
// 세 값이 모두 달라서 칩이 어느 기준을 읽는지 바로 드러난다.
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
  recentWinRate: 60,
  recentClosedCount: 5,
  consecutiveLosses: 0,
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
        counts: { total: 9, outcome: { WIN: 5, LOSS: 3, OPEN: 1 }, grade: { S: 0, A: 4, B: 5, D: 0 } },
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

function openDistributionTooltip(): HTMLElement {
  const heading = screen.getByText('승패 분포 (WIN/LOSS)');
  const trigger = heading.parentElement?.querySelector('i.fa-question-circle');
  if (!(trigger instanceof HTMLElement)) {
    throw new Error('승패 분포 툴팁 trigger를 찾지 못했습니다.');
  }
  fireEvent.mouseEnter(trigger);
  return screen.getByRole('tooltip');
}

describe('CumulativeClientPage', () => {
  it('결과 칩은 서버 counts 로 세어 전체 = 성공 + 실패 + 보유가 맞는다', async () => {
    render(<CumulativeClientPage />);

    await waitFor(() => {
      expect(chipLabels()).toContain('전체 (9)');
    });

    const labels = chipLabels();
    expect(labels).toContain('성공 (5)');
    expect(labels).toContain('실패 (3)');
    expect(labels).toContain('보유 (1)');
    // KPI 값이나 현재 페이지 행으로 센 값이 칩으로 새어 나오면 안 된다.
    expect(labels).not.toContain('성공 (71)');
    expect(labels).not.toContain('성공 (3)');
  });

  it('서버가 제공한 최근 승률을 표시한다', async () => {
    render(<CumulativeClientPage />);

    await waitFor(() => {
      expect(chipLabels()).toContain('전체 (9)');
    });

    // 5건 중 3승인 60%를 서버 KPI로 공급한다. WIN/LOSS 대문자 집계 계약은
    // 백엔드 성과 묶음 회귀에서 검증하며, 이 화면은 현재 표 행으로 재계산하지 않는다.
    expect(within(openDistributionTooltip()).getByText('60%')).toBeTruthy();
  });
});

it('누적성과 안내는 저장 가격 우선과 기본 +5/-3을 설명한다', async () => {
  render(<CumulativeClientPage />);
  await waitFor(() => expect(chipLabels()).toContain('전체 (9)'));
  fireEvent.click(screen.getByRole('button', { name: '성과 가이드' }));
  expect(within(screen.getByRole('dialog')).getByText(/저장된 목표가·손절가를 우선/)).toBeTruthy();
});
