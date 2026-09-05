import { useState } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import BuyStockModal from './BuyStockModal';
import SellStockModal from './SellStockModal';
import ConfirmationModal from './ConfirmationModal';

// [FE-007] 회귀 검사. 모달 셸이 다섯 벌로 흩어져 있던 동안 갖춘 기능이 서로 달랐다.
// 매수와 매도 모달에는 Escape 키도 role="dialog" 도 없었고, 확인 대화상자에는
// role 은 있으나 Escape 가 없었다. 셸을 하나로 모은 뒤로는 세 가지가 어느 모달에서든
// 함께 따라온다. 그 사실을 여기서 고정한다.
//
// 근거: AUDIT-FE §2.2

vi.mock('@/lib/api', () => ({
  paperTradingAPI: {
    getPortfolio: vi.fn(async () => ({ cash: 1_000_000 })),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.alert = vi.fn();
  global.fetch = vi.fn(async () => ({ json: async () => ({ prices: {} }) })) as any;
});

const buyTarget = { ticker: '005930', name: '삼성전자', price: 10_000 };
const sellTarget = {
  ticker: '005930',
  name: '삼성전자',
  quantity: 10,
  avg_price: 60_000,
  current_price: 70_000,
};

describe('Escape 키', () => {
  it('매수 모달을 닫는다', async () => {
    const onClose = vi.fn();
    render(<BuyStockModal isOpen onClose={onClose} stock={buyTarget} onBuy={vi.fn(async () => true)} />);

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('매도 모달을 닫는다', async () => {
    const onClose = vi.fn();
    render(<SellStockModal isOpen onClose={onClose} stock={sellTarget} onSell={vi.fn(async () => true)} />);

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it('확인 대화상자를 취소로 닫는다', async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <ConfirmationModal
        isOpen
        title="모의투자 초기화"
        message="정말로 초기화하시겠습니까?"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1));
    // 되돌릴 수 없는 조작이므로 Escape 가 실행 쪽으로 새면 안 된다.
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('Escape 가 아닌 키에는 반응하지 않는다', async () => {
    const onClose = vi.fn();
    render(<SellStockModal isOpen onClose={onClose} stock={sellTarget} onSell={vi.fn(async () => true)} />);

    fireEvent.keyDown(document, { key: 'Enter' });
    fireEvent.keyDown(document, { key: 'a' });

    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('대화상자 역할', () => {
  it('매수 모달이 제목과 이어진 dialog 다', async () => {
    render(<BuyStockModal isOpen onClose={vi.fn()} stock={buyTarget} onBuy={vi.fn(async () => true)} />);

    const dialog = await screen.findByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    // aria-labelledby 가 가리키는 요소가 실제로 존재해야 낭독기가 제목을 읽는다.
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();
    expect(document.getElementById(labelId!)?.textContent).toContain('모의 투자 매수');
  });

  it('매도 모달이 제목과 이어진 dialog 다', async () => {
    render(<SellStockModal isOpen onClose={vi.fn()} stock={sellTarget} onSell={vi.fn(async () => true)} />);

    const dialog = await screen.findByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(document.getElementById(labelId!)?.textContent).toContain('모의 투자 매도');
  });

  it('확인 대화상자가 제목과 이어진 dialog 다', async () => {
    render(
      <ConfirmationModal
        isOpen
        title="모의투자 초기화"
        message="정말로 초기화하시겠습니까?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('dialog');
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(document.getElementById(labelId!)?.textContent).toContain('모의투자 초기화');
  });
});

describe('배경 클릭', () => {
  it('매도 모달을 닫는다', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <SellStockModal isOpen onClose={onClose} stock={sellTarget} onSell={vi.fn(async () => true)} />,
    );

    // 배경 판은 오버레이의 첫 자식이며 다이얼로그 카드보다 뒤에 깔린다.
    const backdrop = container.querySelector('.absolute.inset-0');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('확인 대화상자를 취소로 닫고 실행은 부르지 않는다', () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    const { container } = render(
      <ConfirmationModal
        isOpen
        title="모의투자 초기화"
        message="정말로 초기화하시겠습니까?"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    // 종전에는 배경 판이 없어 바깥을 눌러도 닫히지 않았다. 셸을 쓰면서 닫히게
    // 되었으므로, 그 경로가 실행 쪽으로 새지 않는다는 것을 고정한다.
    fireEvent.click(container.querySelector('.absolute.inset-0')!);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe('중첩 모달의 Escape', () => {
  // 셸이 저마다 document 에 keydown 리스너를 단다. 판정 없이 두면 모의투자 모달 위에
  // 매수 모달이 열린 상태에서 Escape 한 번에 둘 다 닫힌다. 브라우저 실측에서 실제로
  // 그렇게 동작하는 것을 확인해 맨 위의 셸만 반응하도록 고쳤고, 그것을 여기서 고정한다.
  function NestedModals({ onOuterClose }: { onOuterClose: () => void }) {
    const [innerOpen, setInnerOpen] = useState(true);
    return (
      <>
        <BuyStockModal isOpen onClose={onOuterClose} stock={buyTarget} onBuy={vi.fn(async () => true)} />
        <ConfirmationModal
          isOpen={innerOpen}
          title="모의투자 초기화"
          message="정말로 초기화하시겠습니까?"
          onConfirm={vi.fn()}
          onCancel={() => setInnerOpen(false)}
        />
      </>
    );
  }

  it('Escape 한 번은 위에 있는 모달만 닫는다', async () => {
    const onOuterClose = vi.fn();
    render(<NestedModals onOuterClose={onOuterClose} />);

    await waitFor(() => expect(screen.getAllByRole('dialog')).toHaveLength(2));

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(screen.getAllByRole('dialog')).toHaveLength(1));
    expect(onOuterClose).not.toHaveBeenCalled();
  });

  it('위의 모달이 닫힌 뒤의 Escape 는 아래 모달에 닿는다', async () => {
    const onOuterClose = vi.fn();
    render(<NestedModals onOuterClose={onOuterClose} />);

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.getAllByRole('dialog')).toHaveLength(1));

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(onOuterClose).toHaveBeenCalledTimes(1));
  });
});
