// Regression: [FE-040] — min-width 표 안의 빈 상태가 모바일 화면 밖으로 밀리는 문제

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CumulativeClientPage from '@/app/dashboard/kr/cumulative/CumulativeClientPage';
import PaperTradingModal from './PaperTradingModal';
import StockTradeHistoryModal from './StockTradeHistoryModal';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { email: 'qa@example.test' } }, status: 'authenticated' }),
}));
vi.mock('lightweight-charts', () => ({
  createChart: () => ({ remove: vi.fn(), timeScale: () => ({ fitContent: vi.fn() }) }),
  ColorType: { Solid: 'solid' },
  LineStyle: { Solid: 0 },
  AreaSeries: {},
  LineSeries: {},
}));
vi.mock('./BuyStockModal', () => ({ default: () => null }));
vi.mock('./SellStockModal', () => ({ default: () => null }));
vi.mock('./ConfirmationModal', () => ({ default: () => null }));
vi.mock('./PaperTradingAssetChart', () => ({ default: () => null }));
vi.mock('@/app/dashboard/kr/vcp/StockChart', () => ({ default: () => null }));
vi.mock('@/lib/api', () => ({
  isAuthenticationError: () => false,
  krAPI: { getStockChart: vi.fn(async () => ({ data: [] })) },
  paperTradingAPI: {
    getPortfolio: vi.fn(async () => ({
      holdings: [], cash: 100_000_000, total_asset_value: 100_000_000,
      total_stock_value: 0, total_profit: 0, total_profit_rate: 0, total_principal: 100_000_000,
    })),
    getTradeHistory: vi.fn(async () => ({ trades: [] })),
    getChartData: vi.fn(async () => ({ data: [] })),
    getAssetHistory: vi.fn(async () => ({ history: [] })),
    deposit: vi.fn(), reset: vi.fn(), buy: vi.fn(), sell: vi.fn(),
  },
}));

const expectOutsideHorizontalScroller = (element: HTMLElement) => {
  expect(element.closest('.overflow-x-auto')).toBeNull();
};

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({
      trades: [],
      kpi: {
        totalSignals: 0, wins: 0, losses: 0, open: 0, winRate: 0, avgRoi: 0,
        totalRoi: 0, avgDays: 0, priceDate: '2026-09-09', profitFactor: null, roiByGrade: {},
      },
      pagination: { page: 1, limit: 20, total: 0, totalPages: 0 },
    }),
  })));
});

describe('[FE-040] 카드 폭 기준 빈 상태', () => {
  it('누적성과 거래 내역 안내가 각 표의 가로 스크롤 밖에 있다', async () => {
    render(<CumulativeClientPage />);
    expectOutsideHorizontalScroller(await screen.findByText('해당 기간에 대한 거래 내역이 없습니다.'));
  });

  it('모의투자 보유·전체 거래 내역 안내가 각 표의 가로 스크롤 밖에 있다', async () => {
    render(<PaperTradingModal isOpen onClose={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '보유 종목' }));
    expectOutsideHorizontalScroller(await screen.findByText('보유 중인 종목이 없습니다.'));

    fireEvent.click(screen.getByRole('button', { name: '거래 내역' }));
    expectOutsideHorizontalScroller(await screen.findByText('거래 내역이 없습니다.'));
  });

  it('개별 종목 거래 내역 안내가 표의 가로 스크롤 밖에 있다', async () => {
    render(<StockTradeHistoryModal isOpen onClose={() => {}} stock={{ ticker: '005930', name: '삼성전자' }} />);
    await waitFor(() => expect(screen.getByText('해당 종목의 거래 내역이 없습니다.')).toBeTruthy());
    expectOutsideHorizontalScroller(screen.getByText('해당 종목의 거래 내역이 없습니다.'));
  });
});
