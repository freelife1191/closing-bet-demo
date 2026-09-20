import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SellStockModal from './SellStockModal';

// [FE-003] 회귀 검사. 화면이 안내하는 정산 금액은 백엔드가 실제로 입금하는 금액
// (가격 × 수량)과 같아야 한다. 수수료와 세금을 화면에서만 빼면 어긋난다.

const sessionState = vi.hoisted(() => ({
  data: { user: { email: 'seller@example.test' } } as { user: { email: string } } | null,
  status: 'authenticated',
}));

vi.mock('next-auth/react', () => ({
  useSession: () => sessionState,
}));

beforeEach(() => {
  vi.clearAllMocks();
  sessionState.data = { user: { email: 'seller@example.test' } };
  sessionState.status = 'authenticated';
  window.alert = vi.fn();
});

const holding = {
  ticker: '005930',
  name: '삼성전자',
  quantity: 10,
  avg_price: 60_000,
  current_price: 70_000,
};

function renderModal(onSell = vi.fn(async () => true)) {
  return render(
    <SellStockModal isOpen onClose={vi.fn()} stock={holding} onSell={onSell} />,
  );
}

describe('[INFRA-060] 로그인 경계', () => {
  it('익명 사용자는 매도 주문을 실행하지 않고 로그인 안내를 본다', () => {
    sessionState.data = null;
    sessionState.status = 'unauthenticated';
    const onSell = vi.fn(async () => true);

    renderModal(onSell);

    expect(screen.getByText('모의투자는 로그인 후 사용할 수 있습니다.')).not.toBeNull();
    expect(onSell).not.toHaveBeenCalled();
  });
});

describe('정산 금액', () => {
  it('가격 × 수량과 정확히 같다', async () => {
    renderModal();

    const input = screen.getByRole('textbox') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '5' } });
    });

    // 5주 × 7만 원 = 35만 원. 수수료 0.015% 와 세금 0.2% 를 빼면 349,248원이 된다.
    expect(document.body.textContent).toContain('350,000 원');
    expect(document.body.textContent).not.toContain('349,248');
  });

  it('보유 수량을 넘으면 주문 버튼을 잠근다', async () => {
    renderModal();

    const input = screen.getByRole('textbox') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { value: '11' } });
    });

    expect(document.body.textContent).toContain('보유 수량을 초과했습니다.');
    const submit = screen.getByText('매도 주문') as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
  });

  it('최대 버튼이 보유 수량을 채운다', async () => {
    renderModal();

    await act(async () => {
      fireEvent.click(screen.getByText('최대'));
    });

    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.value).toBe('10');
  });
});

describe('대화상자 닫기', () => {
  it('아이콘 닫기 버튼에 접근 가능한 이름을 제공한다', async () => {
    renderModal();

    expect(await screen.findByRole('button', { name: '닫기' })).not.toBeNull();
  });
});
