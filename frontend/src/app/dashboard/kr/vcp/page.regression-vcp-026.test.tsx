// Regression: [VCP-026] — 최신 탭이 최신 저장분으로 대체 표시 중일 때 상세 차트가 오늘 기준
// 구간을 그려 시그널 캔들이 범위 밖으로 밀리던 문제(심층 리뷰 MINOR 1).
// 백엔드가 구간을 자르므로 대체 시그널의 날짜를 차트 조회의 기준일로 넘겨야 한다.
// 최신 탭에 경고가 없으면 종전대로 기준일을 넘기지 않는다(010 회귀가 덮는다).

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

const getStockChart = vi.hoisted(() => vi.fn(async () => ({ ticker: '034730', data: [] })));

vi.mock('@/lib/api', () => ({
  krAPI: {
    getSignals: vi.fn(async () => ({
      signals: [SIGNAL],
      total_scanned: 1,
      source: 'signals_log.csv',
      stale_warning: '오늘(2026-09-22) 기준 VCP 시그널이 없어 최신 저장분(2026-05-05)을 표시합니다.',
    })),
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
vi.mock('@/app/components/Modal', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/app/components/Modal')>();
  return { ...actual, default: () => null };
});
vi.mock('@/app/components/VCPCriteriaModal', () => ({ default: () => null }));
vi.mock('@/app/components/ThinkingProcess', () => ({ default: () => null }));
vi.mock('react-markdown', () => ({ default: () => null }));
vi.mock('remark-gfm', () => ({ default: () => null }));

describe('[VCP-026] 대체 표시 중의 상세 차트 구간', () => {
  it('최신 탭이 최신 저장분을 보일 때는 그 시그널 날짜를 차트 기준일로 넘긴다', async () => {
    render(<VCPPage />);
    const row = (await screen.findByRole('cell', { name: /알파테크/ })).closest('tr') as HTMLElement;

    fireEvent.click(row);

    await waitFor(() => {
      expect(getStockChart).toHaveBeenCalled();
    });
    expect(getStockChart).toHaveBeenLastCalledWith('034730', '3m', '2026-05-05');
  });
});
