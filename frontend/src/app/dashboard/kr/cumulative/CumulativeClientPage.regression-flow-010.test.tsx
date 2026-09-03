// Regression: [FLOW-010] 등급 카드가 전체 기간이 아니라 현재 페이지만 집계하던 문제
//
// 등급 카드가 표에 그려진 50행으로 다시 계산되어, 페이지를 넘기면 같은 등급의 건수와
// 승률과 평균 수익률이 통째로 바뀌었다. S 등급은 1페이지에서 -3%, 2페이지에서 +4.3%
// 로 부호까지 뒤집혔고, 그 부호에 근거한 전략 조언 문구까지 함께 달라졌다.
//
// 표에 그려지는 trades 와 전체 기간을 담은 kpi.roiByGrade 를 일부러 어긋나게 두어
// 화면이 어느 쪽을 읽는지 갈라낸다.

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

// 전체 기간의 S 등급은 16건이고 평균 수익률이 양수다.
const ROI_BY_GRADE = {
  S: { count: 16, avgRoi: 0.25, totalRoi: 4.0, wins: 6, losses: 10, winRate: 37.5 },
  A: { count: 26, avgRoi: 1.57, totalRoi: 40.8, wins: 8, losses: 18, winRate: 30.8 },
  B: { count: 131, avgRoi: 0.21, totalRoi: 27.0, wins: 46, losses: 85, winRate: 35.1 },
};

// 이 페이지에 그려지는 S 등급은 2건뿐이고 둘 다 손실이다. 화면이 이쪽을 읽으면
// 건수 2 와 승률 0% 와 평균 수익률 -3% 가 나온다.
const PAGE_TRADES = [
  {
    id: 'a', date: '2026-09-01', grade: 'S', name: '삼성전자', code: '005930',
    market: 'KOSPI', entry: 70000, outcome: 'LOSS', roi: -3, maxHigh: 0,
    priceTrail: [], days: 2, score: 12, themes: [],
  },
  {
    id: 'b', date: '2026-09-01', grade: 'S', name: 'SK하이닉스', code: '000660',
    market: 'KOSPI', entry: 200000, outcome: 'LOSS', roi: -3, maxHigh: 0,
    priceTrail: [], days: 2, score: 12, themes: [],
  },
];

function mockCumulativeResponse() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        trades: PAGE_TRADES,
        kpi: {
          totalSignals: 173,
          wins: 60,
          losses: 113,
          open: 0,
          winRate: 34.7,
          avgRoi: 0.4,
          totalRoi: 71.8,
          avgDays: 3.1,
          priceDate: '2026-09-02',
          profitFactor: 1.09,
          roiByGrade: ROI_BY_GRADE,
        },
        pagination: { total: 173, page: 1, limit: 50, totalPages: 4 },
      }),
    })),
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-010] 등급 카드의 집계 원천', () => {
  it('현재 페이지가 아니라 전체 기간을 집계해 보여준다', async () => {
    mockCumulativeResponse();

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.queryByText('2026-09-02')).not.toBeNull());

    // 건수: 전체 기간 값이어야 한다. 현재 페이지의 S 등급 2건이 새어 나오면 안 된다.
    expect(screen.getAllByText('16건').length).toBeGreaterThan(0);
    expect(screen.getAllByText('26건').length).toBeGreaterThan(0);
    expect(screen.getAllByText('131건').length).toBeGreaterThan(0);
    expect(screen.queryByText('2건')).toBeNull();

    // 승률: 세 등급 모두 전체 기간 값이어야 한다. 현재 페이지로 다시 계산하면
    // S 는 0% 가 되고 A 와 B 는 카드에 셀 거래가 하나도 없다.
    expect(screen.getAllByText('37.5%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('30.8%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('35.1%').length).toBeGreaterThan(0);

    // 평균 수익률: 부호가 뒤집히지 않아야 한다. 표기는 소수 첫째 자리이므로 0.25 는
    // +0.3% 로 그려진다. 현재 페이지로 다시 계산하면 -3% 가 나오는데, 표의 수익률 칸은
    // -3.0% 이므로 소수점 없는 이 표기는 등급 카드에서만 나올 수 있다.
    expect(screen.getAllByText('+0.3%').length).toBeGreaterThan(0);
    expect(screen.queryByText('-3%')).toBeNull();
  });
});
