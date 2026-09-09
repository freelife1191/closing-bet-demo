// Regression: [VCP-010] — 과거 날짜를 골라도 상세 차트가 오늘 기준 구간을 그리고,
// 차트 하단의 수축비율이 표와 다른 값을 보이던 문제
// 근거: docs/dev-cycle/TODO.md [VCP-010] (2026-09-02 FE-012 마감 qa-only)
//
// 차트 구간은 백엔드가 자르므로, 선택한 날짜를 API 로 넘기지 않으면 시그널이 발생한
// 캔들이 범위 밖으로 밀려난다. 수축비율은 표·AI 요약과 같은 백엔드 값을 써야 한다.
// 프론트가 따로 계산하던 값은 (10일 저점 / 30일 고점) 으로, 백엔드의 변동폭 비율과
// 애초에 다른 지표였다.

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    getSignals: vi.fn(async () => ({ signals: [SIGNAL, { ...SIGNAL, ticker: "000002", name: "베타테크" }], total_scanned: 2, source: 'test' })),
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
    getStockChart.mockReset();
    getStockChart.mockResolvedValue({ ticker: "034730", data: CHART_ROWS });
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

// A/B 응답 경합은 실제 페이지가 그리는 가격과 로딩 상태로 검증한다.
function deferredChart() {
  let resolve!: (value: { ticker: string; data: typeof CHART_ROWS }) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<{ ticker: string; data: typeof CHART_ROWS }>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function dismissDetail() {
  fireEvent.click(screen.getAllByRole('button', { name: '차트 닫기' })[0]);
}
async function openBeta() {
  fireEvent.click((await screen.findByRole('cell', { name: /베타테크/ })).closest('tr')!);
}
const betaRows = [{ date: '2026-05-05', open: 240, high: 250, low: 230, close: 245, volume: 100 }];

describe('[VCP-012] 오래된 상세 요청', () => {
  beforeEach(() => { getStockChart.mockReset(); });
  it('B가 완료된 다음 도착한 A 성공 응답이 B의 가격을 덮지 않는다', async () => {
    const a = deferredChart();
    getStockChart.mockReturnValueOnce(a.promise).mockResolvedValueOnce({ ticker: '000002', data: betaRows });
    render(<VCPPage />); await openDetailFromRow(); dismissDetail(); await openBeta();
    await screen.findByText('₩250');
    await act(async () => a.resolve({ ticker: '034730', data: CHART_ROWS }));
    expect(screen.getByText('₩250')).toBeTruthy();
    expect(screen.queryByText('₩130')).toBeNull();
  });
  it.each(['success', 'failure'])('A의 늦은 %s가 아직 진행 중인 B의 로딩을 해제하지 않는다', async (outcome) => {
    const a = deferredChart(); const b = deferredChart();
    getStockChart.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
    render(<VCPPage />); await openDetailFromRow(); dismissDetail(); await openBeta();
    await act(async () => { if (outcome === 'success') a.resolve({ ticker: '034730', data: CHART_ROWS }); else a.reject(new Error('old request')); });
    expect(screen.getByText('Loading chart data...')).toBeTruthy();
    await act(async () => b.resolve({ ticker: '000002', data: betaRows }));
    expect(screen.getByText('₩250')).toBeTruthy();
  });
  it('새 종목의 빈 응답이 이전 종목의 가격을 남기지 않는다', async () => {
    getStockChart.mockResolvedValueOnce({ ticker: '034730', data: CHART_ROWS }).mockResolvedValueOnce({ ticker: '000002', data: [] });
    render(<VCPPage />); await openDetailFromRow(); await screen.findByText('₩130'); dismissDetail(); await openBeta();
    await screen.findByText('No chart data available.');
    expect(screen.queryByText('₩130')).toBeNull();
  });
});

describe('[VCP-014] 기간 전환', () => {
  beforeEach(() => { getStockChart.mockReset(); getStockChart.mockResolvedValue({ ticker: '034730', data: CHART_ROWS }); });
  it('4개 기간 버튼으로 조회하며 선택한 과거 날짜를 유지한다', async () => {
    render(<VCPPage />); await selectHistoryDate(); await openDetailFromRow();
    for (const [label, period] of [['1개월','1m'],['3개월','3m'],['6개월','6m'],['1년','1y']]) {
      fireEvent.click(screen.getByRole('button', { name: label }));
      await waitFor(() => expect(getStockChart).toHaveBeenLastCalledWith('034730', period, '2026-05-05'));
      expect(screen.getByRole('button', { name: label }).getAttribute('aria-pressed')).toBe('true');
    }
  });
  it('같은 종목의 1년 응답 뒤에 도착한 1개월 응답을 버린다', async () => {
    const month = deferredChart();
    getStockChart.mockResolvedValueOnce({ ticker: '034730', data: CHART_ROWS }).mockReturnValueOnce(month.promise).mockResolvedValueOnce({ ticker: '034730', data: betaRows });
    render(<VCPPage />); await openDetailFromRow(); await screen.findByText('₩130');
    fireEvent.click(screen.getByRole('button', { name: '1개월' }));
    fireEvent.click(screen.getByRole('button', { name: '1년' }));
    await screen.findByText('₩250');
    await act(async () => month.resolve({ ticker: '034730', data: CHART_ROWS }));
    expect(screen.getByText('₩250')).toBeTruthy();
  });
});


describe('[VCP-012/014] 실패와 자료 공백의 화면 계약', () => {
  beforeEach(() => { getStockChart.mockReset(); });
  it('현재 요청의 실패는 빈 자료와 구분하고 재시도 성공 후 오류를 지운다', async () => {
    getStockChart.mockRejectedValueOnce(new Error('synthetic failure')).mockResolvedValueOnce({ticker:'034730',data:CHART_ROWS});
    render(<VCPPage />); await openDetailFromRow();
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByText('No chart data available.')).toBeNull();
    fireEvent.click(screen.getByRole('button', {name:'다시 시도'}));
    await screen.findByText('₩130');expect(screen.queryByRole('alert')).toBeNull();
  });
  it('B 완료 뒤 A가 실패해도 B에 오류 안내를 만들지 않는다', async () => {
    const a=deferredChart();getStockChart.mockReturnValueOnce(a.promise).mockResolvedValueOnce({ticker:'000002',data:betaRows});
    render(<VCPPage />); await openDetailFromRow();dismissDetail();await openBeta();await screen.findByText('₩250');
    await act(async()=>a.reject(new Error('late failure')));
    expect(screen.queryByRole('alert')).toBeNull();expect(screen.getByText('₩250')).toBeTruthy();
  });
  it('긴 날짜 간격의 양끝과 일수를 표시하고 짧은 구간으로 전환하면 안내를 제거한다', async () => {
    getStockChart.mockResolvedValueOnce({ticker:'034730',data:CHART_ROWS}).mockResolvedValueOnce({ticker:'034730',data:betaRows});
    render(<VCPPage />);await openDetailFromRow();
    expect(await screen.findByText('관측 자료의 날짜 간격 7일 초과: 1구간')).toBeTruthy();
    expect(screen.getByText('2026-04-20 → 2026-05-05: 15일')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'1개월'}));await screen.findByText('₩250');
    expect(screen.queryByText(/관측 자료의 날짜 간격 7일 초과/)).toBeNull();
  });
});
