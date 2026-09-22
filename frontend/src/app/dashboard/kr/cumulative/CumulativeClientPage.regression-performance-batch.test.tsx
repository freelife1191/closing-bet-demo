// Regression: [FLOW-013] 누적성과 화면은 전체 KPI와 현재 페이지 행을 섞지 않는다.
//
// 서버는 전체 기간 KPI를 내려주고 표는 페이지별 행만 내려준다. 등급 카드와 핵심
// 수익률, 최근 10건 지표가 표 행에서 다시 계산되면 페이지 전환에 따라 값이 바뀐다.
// D 등급도 다른 등급과 같은 계약으로 화면에 남아야 한다.

import { StrictMode } from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from './CumulativeClientPage';

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

type Outcome = 'WIN' | 'LOSS' | 'OPEN';
type Grade = 'S' | 'A' | 'B' | 'D';

function makeTrade(index: number, grade: Grade, outcome: Outcome, name: string) {
  return {
    id: `trade-${index}`,
    date: `2026-09-${String(18 - index).padStart(2, '0')}`,
    grade,
    name,
    code: `000${index}`,
    market: 'KOSPI',
    entry: 100_000,
    outcome,
    roi: outcome === 'WIN' ? 5 : outcome === 'LOSS' ? -3 : 0,
    maxHigh: 5,
    priceTrail: [],
    days: 2,
    score: 10,
    themes: [],
  };
}

const ROI_BY_GRADE = {
  S: { count: 6, avgRoi: 3, totalRoi: 18, wins: 5, losses: 1, winRate: 83.3 },
  A: { count: 6, avgRoi: 2, totalRoi: 12, wins: 4, losses: 2, winRate: 66.7 },
  B: { count: 6, avgRoi: 1, totalRoi: 6, wins: 3, losses: 3, winRate: 50 },
  D: { count: 6, avgRoi: 2.17, totalRoi: 13, wins: 2, losses: 4, winRate: 33.3 },
};

interface CumulativeKpiFixture {
  totalSignals: number;
  wins: number;
  losses: number;
  open: number;
  winRate: number;
  avgRoi: number;
  totalRoi: number;
  avgDays: number;
  priceDate: string;
  profitFactor: number | null;
  roiByGrade: typeof ROI_BY_GRADE;
  recentWinRate: number | null;
  recentClosedCount: number;
  consecutiveLosses: number;
}

const KPI: CumulativeKpiFixture = {
  totalSignals: 24,
  wins: 14,
  losses: 7,
  open: 3,
  winRate: 66.7,
  // 등급별 합계(49)와 별개로, 메인 값은 서버가 계산한 전체 KPI다.
  avgRoi: 2.04,
  totalRoi: 49,
  avgDays: 2.5,
  priceDate: '2026-09-18',
  profitFactor: 2.38,
  roiByGrade: ROI_BY_GRADE,
  recentWinRate: 30,
  recentClosedCount: 10,
  consecutiveLosses: 7,
};

const PAGE_ONE_TRADES = [
  makeTrade(1, 'S', 'WIN', '첫 번째 페이지 S'),
  makeTrade(2, 'A', 'WIN', '첫 번째 페이지 A'),
  makeTrade(3, 'B', 'WIN', '첫 번째 페이지 B'),
  makeTrade(4, 'D', 'LOSS', '첫 번째 페이지 D-1'),
  makeTrade(5, 'D', 'LOSS', '첫 번째 페이지 D-2'),
  makeTrade(6, 'S', 'WIN', '첫 번째 페이지 S-2'),
  makeTrade(7, 'A', 'WIN', '첫 번째 페이지 A-2'),
  makeTrade(8, 'B', 'LOSS', '첫 번째 페이지 B-2'),
  makeTrade(9, 'S', 'WIN', '첫 번째 페이지 S-3'),
  makeTrade(10, 'A', 'LOSS', '첫 번째 페이지 A-3'),
];

const PAGE_TWO_TRADES = [
  makeTrade(11, 'S', 'LOSS', '두 번째 페이지 S'),
  makeTrade(12, 'A', 'LOSS', '두 번째 페이지 A'),
  makeTrade(13, 'B', 'LOSS', '두 번째 페이지 B'),
  makeTrade(14, 'D', 'LOSS', '두 번째 페이지 D-1'),
  makeTrade(15, 'D', 'LOSS', '두 번째 페이지 D-2'),
  makeTrade(16, 'S', 'LOSS', '두 번째 페이지 S-2'),
  makeTrade(17, 'A', 'LOSS', '두 번째 페이지 A-2'),
  makeTrade(18, 'B', 'LOSS', '두 번째 페이지 B-2'),
  makeTrade(19, 'S', 'LOSS', '두 번째 페이지 S-3'),
  makeTrade(20, 'A', 'LOSS', '두 번째 페이지 A-3'),
];

function responseFor(trades: ReturnType<typeof makeTrade>[], kpi: CumulativeKpiFixture = KPI) {
  return {
    trades,
    kpi,
    pagination: { total: 24, page: trades === PAGE_ONE_TRADES ? 1 : 2, limit: 10, totalPages: 3 },
  };
}

type CumulativeResponse = ReturnType<typeof responseFor>;

interface MockResponse {
  ok: boolean;
  json: () => Promise<CumulativeResponse>;
}

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function createDeferred<T>(): Deferred<T> {
  let resolvePromise: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return {
    promise,
    resolve: (value) => resolvePromise?.(value),
  };
}

function mockResponse(payload: CumulativeResponse): MockResponse {
  return { ok: true, json: async () => payload };
}

function kpiCard(title: string): HTMLElement {
  const titleElement = screen
    .getAllByText(title)
    .find((element) => element.classList.contains('uppercase'));

  if (!titleElement?.parentElement?.parentElement) {
    throw new Error(`${title} KPI 카드를 찾지 못했습니다.`);
  }

  return titleElement.parentElement.parentElement;
}

function gradeCard(grade: Grade): HTMLElement {
  const titleElement = screen.getByText(`${grade} 등급`);

  if (!titleElement.parentElement?.parentElement) {
    throw new Error(`${grade} 등급 카드를 찾지 못했습니다.`);
  }

  return titleElement.parentElement.parentElement;
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

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('[FLOW-013] 누적성과 KPI 표시', () => {
  it('D 등급을 포함하고 메인 평균·누적 수익률은 서버 KPI를 그대로 사용한다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, json: async () => responseFor(PAGE_ONE_TRADES) })),
    );

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByText('2026-09-18')).toBeTruthy());

    // 전체 기간 D 등급은 카드의 6건이며, 현재 페이지의 D 두 행과 혼동하면 안 된다.
    expect(within(gradeCard('D')).getByText('6건')).toBeTruthy();

    // 기존 S+A+B 재계산 값(평균 2.0%, 누적 36%)이 아니라 서버의 전체 KPI를 표시한다.
    expect(within(kpiCard('평균 수익률')).getByText('+2.04%')).toBeTruthy();
    expect(within(kpiCard('누적 수익률')).getByText('+49%')).toBeTruthy();
  });

  it('페이지가 달라져도 최근 성과는 서버 KPI를 유지한다', async () => {
    const fetchMock = vi.fn(async (input: string) => ({
      ok: true,
      json: async () => responseFor(input.includes('page=2') ? PAGE_TWO_TRADES : PAGE_ONE_TRADES),
    }));
    vi.stubGlobal('fetch', fetchMock);

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByText('첫 번째 페이지 S')).toBeTruthy());
    const tooltip = openDistributionTooltip();
    expect(within(tooltip).getByText('30%')).toBeTruthy();
    expect(within(tooltip).getByText('7회')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(screen.getByText('두 번째 페이지 S')).toBeTruthy());
    expect(fetchMock).toHaveBeenLastCalledWith('/api/kr/closing-bet/cumulative?page=2&limit=50');
    expect(within(tooltip).getByText('30%')).toBeTruthy();
    expect(within(tooltip).getByText('7회')).toBeTruthy();
  });

  it('최근 승률은 실제 청산 표본 수를 라벨에 표시한다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => responseFor(PAGE_ONE_TRADES, {
          ...KPI,
          recentWinRate: 50,
          recentClosedCount: 2,
          consecutiveLosses: 0,
        }),
      })),
    );

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByText('승패 분포 (WIN/LOSS)')).toBeTruthy());
    const tooltip = within(openDistributionTooltip());
    expect(tooltip.getByText('최근 청산 2건 승률 (추천일순)')).toBeTruthy();
    expect(tooltip.getByText('최근 청산 2건 승률 (추천일순)').nextElementSibling?.textContent).toBe('50%');
  });

  it('StrictMode 초기 요청의 늦은 응답이 최신 페이지 표와 KPI를 덮지 않는다', async () => {
    const requests: Deferred<MockResponse>[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        const request = createDeferred<MockResponse>();
        requests.push(request);
        return request.promise;
      }),
    );

    render(
      <StrictMode>
        <CumulativeClientPage />
      </StrictMode>,
    );
    await waitFor(() => expect(requests).toHaveLength(2));
    await act(async () => {
      requests[1].resolve(mockResponse(responseFor(PAGE_ONE_TRADES)));
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.getByText('첫 번째 페이지 S')).toBeTruthy());
    const tooltip = openDistributionTooltip();

    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(requests).toHaveLength(3));
    await act(async () => {
      requests[2].resolve(mockResponse(responseFor(PAGE_TWO_TRADES)));
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.getByText('두 번째 페이지 S')).toBeTruthy());
    expect(within(tooltip).getByText('30%')).toBeTruthy();

    await act(async () => {
      requests[0].resolve(mockResponse(responseFor(PAGE_ONE_TRADES, {
        ...KPI,
        recentWinRate: 10,
        consecutiveLosses: 10,
      })));
      await Promise.resolve();
    });

    expect(screen.getByText('두 번째 페이지 S')).toBeTruthy();
    expect(screen.queryByText('첫 번째 페이지 S')).toBeNull();
    expect(within(tooltip).getByText('30%')).toBeTruthy();
    expect(within(tooltip).queryByText('10%')).toBeNull();
  });

  it('최근 청산이 없으면 집계 전으로 표시한다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => responseFor([], {
          ...KPI,
          recentWinRate: null,
          recentClosedCount: 0,
          consecutiveLosses: 0,
        }),
      })),
    );

    render(<CumulativeClientPage />);

    await waitFor(() => expect(screen.getByText('승패 분포 (WIN/LOSS)')).toBeTruthy());
    const tooltip = within(openDistributionTooltip());
    expect(tooltip.getByText('집계 전')).toBeTruthy();
    expect(tooltip.getByText('최근 청산 0건 승률 (추천일순)')).toBeTruthy();
    expect(tooltip.getByText('종료된 거래가 없어 추세를 집계하지 않았습니다.')).toBeTruthy();
    expect(tooltip.getByText('집계 전').className).toContain('text-gray-400');
  });
});
