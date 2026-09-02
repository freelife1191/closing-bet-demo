// Regression: [VCP-010] — 과거 날짜를 골라도 상세 차트가 오늘 기준 구간을 그리고,
// 차트 하단의 수축비율이 표와 다른 값을 보이던 문제
// 근거: docs/dev-cycle/TODO.md [VCP-010] (2026-09-02 FE-012 마감 qa-only)
//
// 차트 구간은 백엔드가 자르므로, 선택한 날짜를 API 로 넘기지 않으면 시그널이 발생한
// 캔들이 범위 밖으로 밀려난다. 수축비율은 표·AI 요약과 같은 백엔드 값을 써야 한다.
// 프론트가 따로 계산하던 값은 (10일 저점 / 30일 고점) 으로, 백엔드의 변동폭 비율과
// 애초에 다른 지표였다.

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VCPPage from './page';

const SIGNAL = {
  ticker: '034730',
  name: '알파테크',
  signal_date: '2026-05-05',
  score: 90,
  is_vcp: true,
  contraction_ratio: 0.41,
  entry_price: 475_500,
  current_price: 586_000,
};

// 백엔드가 자른 뒤의 응답을 흉내낸다. 30일 고점 130 / 10일 저점 88 이므로 프론트가
// 예전처럼 자체 계산하면 0.68 이 나오고, 백엔드 값 0.41 과 어긋난다.
const CHART_ROWS = [
  { date: '2026-04-20', open: 120, high: 130, low: 118, close: 125, volume: 1000 },
  { date: '2026-05-05', open: 100, high: 110, low: 88, close: 105, volume: 1200 },
];

const getStockChart = vi.hoisted(() => vi.fn(async () => ({ ticker: '034730', data: CHART_ROWS })));

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({ signals: [SIGNAL], total_scanned: 1, source: 'test' })),
    getSignalDates: vi.fn(async () => ['2026-05-05']),
    getAIAnalysis: vi.fn(async () => ({})),
    getMarketGate: vi.fn(async () => ({})),
    getVCPStatus: vi.fn(async () => ({ is_running: false })),
    getStockChart,
  },
  fetchAPI: vi.fn(async () => ({})),
}));

vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));

vi.mock('./StockChart', () => ({ default: () => null }));
vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ConfirmationModal', () => ({ default: () => null }));
vi.mock('@/app/components/Modal', () => ({ default: () => null }));
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

const findSignalRow = async () =>
  (await screen.findByRole('cell', { name: /알파테크/ })).closest('tr') as HTMLElement;

const openDetailFromRow = async () => {
  const row = await findSignalRow();
  fireEvent.click(row);
  return row;
};

const selectHistoryDate = async () => {
  fireEvent.click(screen.getByRole('button', { name: '과거' }));
  fireEvent.click(await screen.findByRole('button', { name: '2026-05-05' }));
};

describe('[VCP-010] VCP 상세 차트의 구간과 수축비율', () => {
  beforeEach(() => {
    getStockChart.mockClear();
  });

  it('과거 날짜를 고른 상태에서는 그 날짜를 차트 조회에 함께 넘긴다', async () => {
    render(<VCPPage />);
    await selectHistoryDate();
    await openDetailFromRow();

    await waitFor(() => {
      expect(getStockChart).toHaveBeenCalled();
    });
    expect(getStockChart).toHaveBeenLastCalledWith('034730', '3m', '2026-05-05');
  });

  it('최신 탭에서는 기준일을 넘기지 않는다', async () => {
    render(<VCPPage />);
    await openDetailFromRow();

    await waitFor(() => {
      expect(getStockChart).toHaveBeenCalled();
    });
    expect(getStockChart).toHaveBeenLastCalledWith('034730', '3m', undefined);
  });

  it('차트 하단의 수축비율이 표의 값과 같다', async () => {
    render(<VCPPage />);

    // 표에 찍힌 값을 먼저 읽어 둔다. 상세를 열면 같은 종목명이 헤더에도 나온다.
    const row = await findSignalRow();
    const inTable = within(row).getByText('0.41').textContent?.trim();

    fireEvent.click(row);

    const label = await screen.findByText('수축비율:');
    const inChart = (label.nextElementSibling as HTMLElement).textContent?.trim();

    expect(inChart).toBe(inTable);
    expect(inChart).toBe('0.41');
  });
});
