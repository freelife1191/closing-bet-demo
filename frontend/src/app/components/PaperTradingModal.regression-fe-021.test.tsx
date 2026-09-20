import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, beforeAll, afterEach } from 'vitest';
import PaperTradingModal from './PaperTradingModal';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { email: 'modal@example.test' } }, status: 'authenticated' }),
}));

// Mock child modals to keep tests simple
vi.mock('./BuyStockModal', () => ({ default: () => null }));
vi.mock('./SellStockModal', () => ({ default: () => null }));
vi.mock('./ConfirmationModal', () => ({ default: () => null }));

const mockPortfolio = {
  holdings: [],
  cash: 100_000_000,
  total_asset_value: 100_000_000,
  total_stock_value: 0,
  total_profit: 0,
  total_profit_rate: 0,
  total_principal: 100_000_000,
};

vi.mock('@/lib/api', () => ({
  isAuthenticationError: () => false,
  paperTradingAPI: {
    getPortfolio: vi.fn(async () => mockPortfolio),
    getChartData: vi.fn(async () => ({ data: [] })),
    getAssetHistory: vi.fn(async () => ({ history: [] })),
    getTradeHistory: vi.fn(async () => ({ trades: [] })),
    deposit: vi.fn(async () => ({})),
    reset: vi.fn(async () => ({})),
    buy: vi.fn(async () => ({ status: 'success', message: 'ok' })),
    sell: vi.fn(async () => ({ status: 'success', message: 'ok' })),
  },
}));

// Import after mock so we get the mock reference
import { paperTradingAPI } from '@/lib/api';

const mockOnClose = vi.fn();

function renderOpen(props?: Partial<{ isOpen: boolean; onClose: () => void }>) {
  return render(
    <PaperTradingModal
      isOpen={props?.isOpen ?? true}
      onClose={props?.onClose ?? mockOnClose}
    />,
  );
}

beforeAll(async () => {
  vi.stubGlobal('ResizeObserver', class {
    observe() {} unobserve() {} disconnect() {}
  });
});
beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
  // jsdom has no drawing surface. Keep the actual chart and its request effects;
  // substitute only Canvas 2D methods (pixel rendering is covered in browser QA).
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(function (this: HTMLCanvasElement) {
    return new Proxy({}, {
      get: (_target, key) => {
        if (key === 'canvas') return this;
        if (key === 'measureText') return (text: string) => ({ width: text.length * 7 });
        if (key === 'createLinearGradient') return () => ({ addColorStop: () => {} });
        return () => {};
      },
    }) as CanvasRenderingContext2D;
  });
});

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('[FE-021] real chart period request boundary', () => {
  it('changes asset history days without fetching portfolio again', async () => {
    renderOpen();
    await screen.findByText('예수금');
    fireEvent.click(screen.getByText('수익 차트'));
    await waitFor(() => expect(paperTradingAPI.getAssetHistory).toHaveBeenCalledWith(365));
    await act(async () => { await vi.dynamicImportSettled(); });
    const calls = vi.mocked(paperTradingAPI.getPortfolio).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '3개월' }));
    await waitFor(() => expect(paperTradingAPI.getAssetHistory).toHaveBeenLastCalledWith(90));
    await act(async () => { await vi.dynamicImportSettled(); });
    expect(paperTradingAPI.getPortfolio).toHaveBeenCalledTimes(calls);
    fireEvent.click(screen.getByRole('button', { name: '1개월' }));
    await waitFor(() => expect(paperTradingAPI.getAssetHistory).toHaveBeenLastCalledWith(30));
    await act(async () => { await vi.dynamicImportSettled(); });
    expect(paperTradingAPI.getPortfolio).toHaveBeenCalledTimes(calls);
  });
});
