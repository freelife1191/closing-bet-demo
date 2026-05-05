import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import PaperTradingModal from './PaperTradingModal';

// Mock lightweight-charts to avoid canvas/DOM issues in jsdom
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addCandlestickSeries: () => ({ setData: vi.fn() }),
    addLineSeries: () => ({ setData: vi.fn() }),
    addSeries: () => ({ setData: vi.fn(), priceToCoordinate: vi.fn(() => 0) }),
    timeScale: () => ({ fitContent: vi.fn() }),
    subscribeCrosshairMove: vi.fn(),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  }),
  ColorType: { Solid: 'solid' },
  LineStyle: { Solid: 0 },
  AreaSeries: {},
  LineSeries: {},
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

beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
});

// ---------------------------------------------------------------------------
// 1. ESC closes modal when open
// ---------------------------------------------------------------------------
describe('ESC key behavior', () => {
  it('calls onClose when Escape is pressed while modal is open', async () => {
    renderOpen();

    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });
    });

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT call onClose when Escape is pressed while modal is closed', async () => {
    renderOpen({ isOpen: false });

    await act(async () => {
      fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });
    });

    expect(mockOnClose).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 3. ARIA attributes
// ---------------------------------------------------------------------------
describe('ARIA attributes', () => {
  it('has role="dialog", aria-modal="true", and aria-labelledby on the modal container', async () => {
    renderOpen();

    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');

    const labelId = dialog?.getAttribute('aria-labelledby');
    expect(labelId).toBe('paper-trading-modal-title');

    // The element referenced by aria-labelledby must exist
    const titleEl = document.getElementById('paper-trading-modal-title');
    expect(titleEl).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 4-6. Deposit limit validation
// ---------------------------------------------------------------------------
describe('handleDeposit limit validation', () => {
  async function openDepositPopover() {
    // Wait for portfolio to load so the deposit button is visible
    await waitFor(() => {
      expect(screen.queryByText('예수금')).not.toBeNull();
    });

    // Click the "+" button next to 예수금 to show the deposit popover
    const plusBtn = document.querySelector('button.w-4.h-4') as HTMLButtonElement;
    expect(plusBtn).not.toBeNull();
    await act(async () => {
      fireEvent.click(plusBtn);
    });
  }

  async function setAmountAndDeposit(rawValue: string) {
    const input = screen.getByRole('textbox') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: rawValue } });
    });

    const depositBtn = screen.getByText('충전하기');
    await act(async () => {
      fireEvent.click(depositBtn);
    });
  }

  it('rejects amount > 1조원 — does not call API and shows alert', async () => {
    renderOpen();
    await openDepositPopover();

    // 1조 + 1 = 1_000_000_000_001
    await setAmountAndDeposit('1000000000001');

    expect(paperTradingAPI.deposit).not.toHaveBeenCalled();
    expect(window.alert).toHaveBeenCalledWith('1회 최대 입금 한도(1조원)를 초과했습니다.');
  });

  it('allows deposit of exactly 1조원 — calls API', async () => {
    renderOpen();
    await openDepositPopover();

    // exactly 1조 = 1_000_000_000_000
    await setAmountAndDeposit('1000000000000');

    await waitFor(() => {
      expect(paperTradingAPI.deposit).toHaveBeenCalledWith(1_000_000_000_000);
    });
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('충전되었습니다'),
    );
  });

  it('calls API with correct value for a normal deposit amount', async () => {
    renderOpen();
    await openDepositPopover();

    await setAmountAndDeposit('10000000');

    await waitFor(() => {
      expect(paperTradingAPI.deposit).toHaveBeenCalledWith(10_000_000);
    });
    expect(window.alert).toHaveBeenCalledWith(
      expect.stringContaining('충전되었습니다'),
    );
  });
});
