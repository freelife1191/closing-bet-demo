import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PaperTradingModal from './PaperTradingModal';

const sessionState = vi.hoisted(() => ({
  data: { user: { email: 'alice@example.test' } } as { user: { email: string } } | null,
  status: 'authenticated',
}));

const apiMocks = vi.hoisted(() => ({
  getPortfolio: vi.fn(),
}));

vi.mock('next-auth/react', () => ({
  useSession: () => sessionState,
}));

vi.mock('@/lib/api', () => ({
  isAuthenticationError: (error: unknown) =>
    typeof error === 'object' && error !== null && (error as { status?: unknown }).status === 401,
  paperTradingAPI: {
    getPortfolio: apiMocks.getPortfolio,
    getTradeHistory: vi.fn(),
    getAssetHistory: vi.fn(),
    deposit: vi.fn(),
    reset: vi.fn(),
    buy: vi.fn(),
    sell: vi.fn(),
  },
}));

vi.mock('./BuyStockModal', () => ({ default: () => null }));
vi.mock('./SellStockModal', () => ({ default: () => null }));
vi.mock('./StockTradeHistoryModal', () => ({ default: () => null }));
vi.mock('./PaperTradingAssetChart', () => ({ default: () => null }));
vi.mock('./ConfirmationModal', () => ({ default: () => null }));

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function portfolio(cash: number) {
  return {
    holdings: [],
    cash,
    total_asset_value: cash,
    total_stock_value: 0,
    total_profit: 0,
    total_profit_rate: 0,
    total_principal: 100_000_000,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionState.data = { user: { email: 'alice@example.test' } };
  sessionState.status = 'authenticated';
});

describe('[INFRA-060] PaperTradingModal 계정 경계', () => {
  it('새 계정 응답 전에는 이전 계정 포트폴리오를 표시하지 않는다', async () => {
    const alice = deferred<ReturnType<typeof portfolio>>();
    const bob = deferred<ReturnType<typeof portfolio>>();
    apiMocks.getPortfolio.mockReturnValueOnce(alice.promise).mockReturnValueOnce(bob.promise);

    const view = render(<PaperTradingModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(apiMocks.getPortfolio).toHaveBeenCalledTimes(1));

    await act(async () => {
      alice.resolve(portfolio(111_000_000));
      await alice.promise;
    });
    expect((await screen.findAllByText('111,000,000원')).length).toBeGreaterThan(0);

    sessionState.data = { user: { email: 'bob@example.test' } };
    view.rerender(<PaperTradingModal isOpen onClose={vi.fn()} />);
    await waitFor(() => expect(apiMocks.getPortfolio).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('111,000,000원')).toBeNull();

    await act(async () => {
      bob.resolve(portfolio(222_000_000));
      await bob.promise;
    });
    expect((await screen.findAllByText('222,000,000원')).length).toBeGreaterThan(0);
  });

  it('익명 상태에서는 기존 자료를 요청하지 않고 로그인 안내를 표시한다', () => {
    sessionState.data = null;
    sessionState.status = 'unauthenticated';

    render(<PaperTradingModal isOpen onClose={vi.fn()} />);

    expect(screen.getByText('모의투자는 로그인 후 사용할 수 있습니다.')).not.toBeNull();
    expect(apiMocks.getPortfolio).not.toHaveBeenCalled();
  });

  it('서버가 401을 돌려주면 기존 포트폴리오 대신 로그인 안내를 표시한다', async () => {
    apiMocks.getPortfolio.mockRejectedValueOnce(Object.assign(
      new Error('모의투자는 로그인 후 사용할 수 있습니다.'),
      { status: 401 },
    ));

    render(<PaperTradingModal isOpen onClose={vi.fn()} />);

    expect(await screen.findByText('모의투자는 로그인 후 사용할 수 있습니다.')).not.toBeNull();
  });
});
