import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import BuyStockModal from './BuyStockModal';

// [FE-003] 회귀 검사. 화면이 안내하는 결제 금액과 매수 가능 수량은 백엔드가 실제로
// 차감하는 금액(가격 × 수량)과 같아야 한다. 수수료를 화면에서만 얹으면 어긋난다.

const sessionState = vi.hoisted(() => ({
  data: { user: { email: 'buyer@example.test' } } as { user: { email: string } } | null,
  status: 'authenticated',
}));

vi.mock('next-auth/react', () => ({
  useSession: () => sessionState,
}));

const apiMocks = vi.hoisted(() => ({
  getPortfolio: vi.fn(async () => ({ cash: 1_000_000 })),
}));

vi.mock('@/lib/api', () => ({
  isAuthenticationError: (error: unknown) =>
    typeof error === 'object' && error !== null && (error as { status?: unknown }).status === 401,
  paperTradingAPI: {
    getPortfolio: apiMocks.getPortfolio,
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  sessionState.data = { user: { email: 'buyer@example.test' } };
  sessionState.status = 'authenticated';
  window.alert = vi.fn();
  // 마운트 시 실시간 가격을 조회한다. 빈 응답을 주면 stock 이 들고 온 가격으로 떨어진다.
  global.fetch = vi.fn(async () => ({ json: async () => ({ prices: {} }) })) as any;
});

function renderModal(stock: any, onBuy = vi.fn(async () => true)) {
  return render(
    <BuyStockModal isOpen onClose={vi.fn()} stock={stock} onBuy={onBuy} />,
  );
}

const stockAt10000 = { ticker: '005930', name: '삼성전자', price: 10_000 };

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

describe('[INFRA-060] 로그인 경계', () => {
  it('익명 사용자는 잔고 요청과 주문 없이 로그인 안내만 본다', () => {
    sessionState.data = null;
    sessionState.status = 'unauthenticated';
    const onBuy = vi.fn(async () => true);

    renderModal(stockAt10000, onBuy);

    expect(screen.getByText('모의투자는 로그인 후 사용할 수 있습니다.')).not.toBeNull();
    expect(apiMocks.getPortfolio).not.toHaveBeenCalled();
    expect(onBuy).not.toHaveBeenCalled();
  });

  it('인증된 세션의 잔고 조회가 401이면 기존 주문 UI 대신 로그인 안내를 표시한다', async () => {
    apiMocks.getPortfolio.mockRejectedValueOnce(Object.assign(
      new Error('모의투자는 로그인 후 사용할 수 있습니다.'),
      { status: 401 },
    ));

    renderModal(stockAt10000);

    expect(await screen.findByText('모의투자는 로그인 후 사용할 수 있습니다.')).not.toBeNull();
    expect(screen.queryByText('구매 수량 (주)')).toBeNull();
  });

  it('계정 전환 뒤 이전 매수 응답이 새 모달을 닫지 않는다', async () => {
    const pendingBuy = deferred<boolean>();
    const onClose = vi.fn();
    const view = render(<BuyStockModal isOpen onClose={onClose} stock={stockAt10000} onBuy={() => pendingBuy.promise} />);

    await waitFor(() => expect(document.body.textContent).toContain('가능: 100주'));
    await act(async () => {
      fireEvent.change(screen.getByRole('textbox'), { target: { value: '1' } });
      fireEvent.click(screen.getByText('매수 주문'));
    });

    sessionState.data = { user: { email: 'buyer-b@example.test' } };
    view.rerender(<BuyStockModal isOpen onClose={onClose} stock={stockAt10000} onBuy={() => pendingBuy.promise} />);

    await act(async () => {
      pendingBuy.resolve(true);
      await pendingBuy.promise;
    });

    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('매수 가능 수량', () => {
  it('예수금을 가격으로 나눈 몫을 그대로 보여 준다', async () => {
    renderModal(stockAt10000);

    // 100만 원 ÷ 1만 원 = 100주. 수수료 계수 1.00015 가 남아 있으면 99주가 된다.
    await waitFor(() => {
      expect(document.body.textContent).toContain('가능: 100주');
    });
  });

  it('가격을 못 받아 온 상태에서도 무한대 대신 0주로 표시한다', async () => {
    renderModal({ ticker: '000000', name: '가격없음', price: 0 });

    await waitFor(() => {
      expect(document.body.textContent).toContain('가능: 0주');
    });
    expect(document.body.textContent).not.toContain('∞');
  });

  it('최대 버튼이 예수금 전액에 해당하는 수량을 채운다', async () => {
    renderModal(stockAt10000);
    await waitFor(() => {
      expect(document.body.textContent).toContain('가능: 100주');
    });

    await act(async () => {
      fireEvent.click(screen.getByText('최대'));
    });

    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.value).toBe('100');
  });
});

describe('결제 금액', () => {
  it('가격 × 수량과 정확히 같다', async () => {
    renderModal(stockAt10000);
    await waitFor(() => {
      expect(document.body.textContent).toContain('가능: 100주');
    });

    const input = screen.getByRole('textbox') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '10' } });
    });

    // 10주 × 1만 원 = 10만 원. 수수료 0.015% 가 붙어 있으면 100,015원이 된다.
    expect(document.body.textContent).toContain('100,000 원');
    expect(document.body.textContent).not.toContain('100,015');
  });

  it('예수금을 넘는 주문에서 부족 금액을 수수료 없이 계산한다', async () => {
    renderModal(stockAt10000);
    await waitFor(() => {
      expect(document.body.textContent).toContain('가능: 100주');
    });

    const input = screen.getByRole('textbox') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '150' } });
    });

    // 150주 × 1만 원 = 150만 원, 예수금 100만 원이므로 부족분은 50만 원이다.
    expect(document.body.textContent).toContain('부족: 500,000원');
  });
});

describe('대화상자 닫기', () => {
  it('아이콘 닫기 버튼에 접근 가능한 이름을 제공한다', async () => {
    renderModal(stockAt10000);

    expect(await screen.findByRole('button', { name: '닫기' })).not.toBeNull();
  });
});
