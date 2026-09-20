import '@testing-library/jest-dom/vitest';

import { createRef, StrictMode, useState } from 'react';
import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import BuyStockModal from './BuyStockModal';
import SellStockModal from './SellStockModal';
import ConfirmationModal from './ConfirmationModal';
import Modal, { ModalShell } from './Modal';

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

afterEach(() => {
  vi.useRealTimers();
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

  it('확인 대화상자가 제목과 이어진 alertdialog 다', async () => {
    render(
      <ConfirmationModal
        isOpen
        title="모의투자 초기화"
        message="정말로 초기화하시겠습니까?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('alertdialog');
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(document.getElementById(labelId!)?.textContent).toContain('모의투자 초기화');
  });
});

describe('배경 클릭', () => {
  it('매도 모달을 닫는다', async () => {
    const onClose = vi.fn();
    render(<SellStockModal isOpen onClose={onClose} stock={sellTarget} onSell={vi.fn(async () => true)} />);

    // 셸은 body portal 로 이동하므로 렌더 컨테이너가 아니라 모달 host 에서 찾는다.
    const backdrop = document.querySelector('[data-modal-layer] .absolute.inset-0');
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop!);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('확인 대화상자를 취소로 닫고 실행은 부르지 않는다', () => {
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

    // 종전에는 배경 판이 없어 바깥을 눌러도 닫히지 않았다. 셸을 쓰면서 닫히게
    // 되었으므로, 그 경로가 실행 쪽으로 새지 않는다는 것을 고정한다.
    fireEvent.click(document.querySelector('[data-modal-layer] .absolute.inset-0')!);

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

    await waitFor(() => {
      expect(screen.getAllByRole('dialog')).toHaveLength(1);
      expect(screen.getAllByRole('alertdialog')).toHaveLength(1);
    });

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    expect(onOuterClose).not.toHaveBeenCalled();
  });

  it('위의 모달이 닫힌 뒤의 Escape 는 아래 모달에 닿는다', async () => {
    const onOuterClose = vi.fn();
    render(<NestedModals onOuterClose={onOuterClose} />);

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => expect(onOuterClose).toHaveBeenCalledTimes(1));
  });
});

describe('포털과 배경 격리', () => {
  it('body 직접 자식 host 하나만 활성화하고 배경을 inert 처리한다', async () => {
    const { container } = render(
      <ModalShell
        onClose={vi.fn()}
        labelledBy="portal-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="portal-title">포털 모달</h2>
        <button>확인</button>
      </ModalShell>,
    );

    const dialog = await screen.findByRole('dialog', { name: '포털 모달' });
    const layer = dialog.closest('[data-modal-layer]');
    expect(layer?.parentElement).toBe(document.body);
    expect(layer).toHaveAttribute('data-modal-active', 'true');
    expect(layer).toHaveClass('fixed', 'inset-0', 'overflow-visible');
    expect(layer?.className).not.toMatch(/\b(transform|filter)\b/);
    expect(container).toHaveAttribute('inert');
    expect(document.querySelectorAll('[data-modal-active="true"]')).toHaveLength(1);
  });

  it('중첩된 셸에서는 맨 위 host만 활성화하고 아래 셸을 inert 처리한다', async () => {
    function NestedLayers() {
      const [innerOpen, setInnerOpen] = useState(true);
      return (
        <>
          <ModalShell
            onClose={vi.fn()}
            labelledBy="outer-layer-title"
            overlayClassName="z-[100]"
            className="relative"
          >
            <h2 id="outer-layer-title">바깥 모달</h2>
            <button>바깥 동작</button>
          </ModalShell>
          {innerOpen && (
            <ModalShell
              onClose={() => setInnerOpen(false)}
              labelledBy="inner-layer-title"
              overlayClassName="z-[110]"
              className="relative"
            >
              <h2 id="inner-layer-title">안쪽 모달</h2>
              <button>안쪽 동작</button>
            </ModalShell>
          )}
        </>
      );
    }

    render(<NestedLayers />);

    const outerLayer = (await screen.findByRole('dialog', { name: '바깥 모달' })).closest('[data-modal-layer]');
    const innerLayer = screen.getByRole('dialog', { name: '안쪽 모달' }).closest('[data-modal-layer]');
    expect(outerLayer).toHaveAttribute('inert');
    expect(outerLayer).not.toHaveAttribute('data-modal-active');
    expect(innerLayer).toHaveAttribute('data-modal-active', 'true');
    expect(document.querySelectorAll('[data-modal-active="true"]')).toHaveLength(1);
  });

  it('실제 매수 모달보다 나중에 열린 확인 모달을 호출자 z-index와 무관하게 위에 둔다', async () => {
    render(
      <>
        <BuyStockModal
          isOpen
          onClose={vi.fn()}
          stock={buyTarget}
          onBuy={vi.fn(async () => true)}
        />
        <ConfirmationModal
          isOpen
          title="매수 확인"
          message="주문하시겠습니까?"
          onConfirm={vi.fn()}
          onCancel={vi.fn()}
        />
      </>,
    );

    const buyLayer = (await screen.findByRole('dialog', { name: '모의 투자 매수' }))
      .closest<HTMLElement>('[data-modal-layer]');
    const confirmation = screen.getByRole('alertdialog', { name: '매수 확인' });
    const confirmationLayer = confirmation.closest<HTMLElement>('[data-modal-layer]');
    expect(Number(confirmationLayer?.style.zIndex)).toBeGreaterThan(Number(buyLayer?.style.zIndex));
  });

  it('확인 모달 애니메이션을 transform 없는 host가 아니라 dialog 카드에 둔다', async () => {
    render(
      <ConfirmationModal
        isOpen
        title="레이어 확인"
        message="좌표계를 유지합니다."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('alertdialog', { name: '레이어 확인' });
    const layer = dialog.closest<HTMLElement>('[data-modal-layer]');
    expect(layer).not.toHaveClass('animate-fade-in');
    expect(layer).toHaveStyle({ transform: 'none' });
    expect(dialog).toHaveClass('animate-fade-in');
  });
});

describe('초점 수명주기', () => {
  it('initialFocusRef가 가리키는 요소로 진입 초점을 옮긴다', async () => {
    const initialFocusRef = createRef<HTMLButtonElement>();
    render(
      <ModalShell
        onClose={vi.fn()}
        labelledBy="initial-focus-title"
        initialFocusRef={initialFocusRef}
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="initial-focus-title">초점 지정</h2>
        <button>첫 버튼</button>
        <button ref={initialFocusRef}>지정 버튼</button>
      </ModalShell>,
    );

    await waitFor(() => expect(screen.getByRole('button', { name: '지정 버튼' })).toHaveFocus());
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement);
  });

  it('initialFocusRef가 없으면 첫 번째 조작 요소에 초점을 둔다', async () => {
    render(
      <ModalShell
        onClose={vi.fn()}
        labelledBy="default-focus-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="default-focus-title">기본 초점</h2>
        <div style={{ display: 'none' }}>
          <button>숨긴 버튼</button>
        </div>
        <button>첫 버튼</button>
        <button>마지막 버튼</button>
      </ModalShell>,
    );

    await waitFor(() => expect(screen.getByRole('button', { name: '첫 버튼' })).toHaveFocus());
  });

  it('Tab과 Shift+Tab이 활성 모달의 양 끝에서 순환한다', async () => {
    render(
      <ModalShell
        onClose={vi.fn()}
        labelledBy="focus-trap-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="focus-trap-title">초점 순환</h2>
        <button>첫 버튼</button>
        <button disabled>비활성 버튼</button>
        <button>마지막 버튼</button>
      </ModalShell>,
    );

    const first = screen.getByRole('button', { name: '첫 버튼' });
    const last = screen.getByRole('button', { name: '마지막 버튼' });
    await waitFor(() => expect(first).toHaveFocus());

    last.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(first).toHaveFocus();

    first.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(last).toHaveFocus();
  });

  it('onClose 함수가 바뀌어 재렌더되어도 사용자가 옮긴 초점을 초기화하지 않는다', async () => {
    const firstClose = vi.fn();
    const secondClose = vi.fn();
    const view = render(
      <ModalShell
        onClose={firstClose}
        labelledBy="rerender-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="rerender-title">재렌더 초점</h2>
        <button>첫 버튼</button>
        <button>사용자 선택</button>
      </ModalShell>,
    );
    const selected = screen.getByRole('button', { name: '사용자 선택' });
    await waitFor(() => expect(screen.getByRole('button', { name: '첫 버튼' })).toHaveFocus());
    selected.focus();

    view.rerender(
      <ModalShell
        onClose={secondClose}
        labelledBy="rerender-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="rerender-title">재렌더 초점</h2>
        <button>첫 버튼</button>
        <button>사용자 선택</button>
      </ModalShell>,
    );

    expect(selected).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(secondClose).toHaveBeenCalledTimes(1);
    expect(firstClose).not.toHaveBeenCalled();
  });

  it('닫힌 뒤 모달을 연 trigger로 초점을 돌려준다', async () => {
    function TriggerHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>모달 열기</button>
          {open && (
            <ModalShell
              onClose={() => setOpen(false)}
              labelledBy="return-focus-title"
              overlayClassName="z-[100]"
              className="relative"
            >
              <h2 id="return-focus-title">복귀 초점</h2>
              <button onClick={() => setOpen(false)}>닫기</button>
            </ModalShell>
          )}
        </>
      );
    }

    render(<TriggerHarness />);
    const trigger = screen.getByRole('button', { name: '모달 열기' });
    trigger.focus();
    fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByRole('button', { name: '닫기' })).toHaveFocus());

    fireEvent.click(screen.getByRole('button', { name: '닫기' }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('중첩 모달 trigger가 제거됐으면 남은 활성 모달 안으로 안전하게 복귀한다', async () => {
    function RemovedTriggerHarness() {
      const [innerOpen, setInnerOpen] = useState(false);
      const [showTrigger, setShowTrigger] = useState(true);
      return (
        <ModalShell
          onClose={vi.fn()}
          labelledBy="safe-fallback-outer-title"
          overlayClassName="z-[100]"
          className="relative"
        >
          <h2 id="safe-fallback-outer-title">바깥 모달</h2>
          {showTrigger && (
            <button onClick={() => setInnerOpen(true)}>안쪽 열기</button>
          )}
          <button>바깥 대체 초점</button>
          {innerOpen && (
            <ModalShell
              onClose={() => setInnerOpen(false)}
              labelledBy="safe-fallback-inner-title"
              overlayClassName="z-[110]"
              className="relative"
            >
              <h2 id="safe-fallback-inner-title">안쪽 모달</h2>
              <button onClick={() => setShowTrigger(false)}>trigger 제거</button>
              <button onClick={() => setInnerOpen(false)}>안쪽 닫기</button>
            </ModalShell>
          )}
        </ModalShell>
      );
    }

    render(<RemovedTriggerHarness />);
    fireEvent.click(await screen.findByRole('button', { name: '안쪽 열기' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'trigger 제거' })).toHaveFocus());
    fireEvent.click(screen.getByRole('button', { name: 'trigger 제거' }));
    fireEvent.click(screen.getByRole('button', { name: '안쪽 닫기' }));

    await waitFor(() => {
      const outerDialog = screen.getByRole('dialog', { name: '바깥 모달' });
      expect(outerDialog).toContainElement(document.activeElement as HTMLElement);
    });
  });

  it('닫힘 애니메이션이 끝나 실제로 언마운트될 때 trigger 초점을 복원한다', async () => {
    vi.useFakeTimers();

    function AnimatedHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>애니메이션 모달 열기</button>
          <Modal isOpen={open} onClose={() => setOpen(false)} title="애니메이션 모달">
            <button onClick={() => setOpen(false)}>애니메이션 닫기</button>
          </Modal>
        </>
      );
    }

    render(<AnimatedHarness />);
    const trigger = screen.getByRole('button', { name: '애니메이션 모달 열기' });
    trigger.focus();
    fireEvent.click(trigger);
    await act(async () => {});
    expect(screen.getByRole('dialog', { name: '애니메이션 모달' })).toContainElement(
      document.activeElement as HTMLElement,
    );

    fireEvent.click(screen.getByRole('button', { name: '애니메이션 닫기' }));
    expect(screen.getByRole('dialog', { name: '애니메이션 모달' })).toBeInTheDocument();
    expect(trigger).not.toHaveFocus();

    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByRole('dialog', { name: '애니메이션 모달' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe('중첩 모달 입력', () => {
  function NestedInteractionHarness({ onOuterClose }: { onOuterClose: () => void }) {
    const [innerOpen, setInnerOpen] = useState(false);
    return (
      <ModalShell
        onClose={onOuterClose}
        labelledBy="interaction-outer-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="interaction-outer-title">바깥 모달</h2>
        <button onClick={() => setInnerOpen(true)}>안쪽 열기</button>
        {innerOpen && (
          <ModalShell
            onClose={() => setInnerOpen(false)}
            labelledBy="interaction-inner-title"
            overlayClassName="z-[110]"
            className="relative"
          >
            <h2 id="interaction-inner-title">안쪽 모달</h2>
            <button>안쪽 확인</button>
          </ModalShell>
        )}
      </ModalShell>
    );
  }

  it('아래 모달 backdrop 클릭은 무시하고 맨 위 backdrop만 닫는다', async () => {
    const onOuterClose = vi.fn();
    render(<NestedInteractionHarness onOuterClose={onOuterClose} />);
    fireEvent.click(await screen.findByRole('button', { name: '안쪽 열기' }));

    const layers = Array.from(document.querySelectorAll<HTMLElement>('[data-modal-layer]'));
    expect(layers).toHaveLength(2);
    fireEvent.click(layers[0].querySelector('.absolute.inset-0')!);
    expect(onOuterClose).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog', { name: '안쪽 모달' })).toBeInTheDocument();

    fireEvent.click(layers[1].querySelector('.absolute.inset-0')!);
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '안쪽 모달' })).not.toBeInTheDocument());
    expect(onOuterClose).not.toHaveBeenCalled();
  });

  it('활성 모달 안에 열린 tooltip이 있으면 첫 Escape는 모달까지 닫지 않는다', async () => {
    const onClose = vi.fn();
    const view = render(
      <ModalShell
        onClose={onClose}
        labelledBy="tooltip-owner-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="tooltip-owner-title">도움말 모달</h2>
        <button>도움말</button>
        <div role="tooltip">열린 설명</div>
      </ModalShell>,
    );

    await screen.findByRole('tooltip');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();

    view.rerender(
      <ModalShell
        onClose={onClose}
        labelledBy="tooltip-owner-title"
        overlayClassName="z-[100]"
        className="relative"
      >
        <h2 id="tooltip-owner-title">도움말 모달</h2>
        <button>도움말</button>
      </ModalShell>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe('전역 상태 정리', () => {
  it('기존 body overflow와 배경 inert를 StrictMode 재마운트 뒤에도 보존하고 복원한다', async () => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'clip';
    const persistentBackground = document.createElement('main');
    persistentBackground.setAttribute('inert', '');
    const ordinaryBackground = document.createElement('aside');
    document.body.append(persistentBackground, ordinaryBackground);

    try {
      const onClose = vi.fn();
      const view = render(
        <StrictMode>
          <ModalShell
            onClose={onClose}
            labelledBy="strict-title"
            overlayClassName="z-[100]"
            className="relative"
          >
            <h2 id="strict-title">Strict 모달</h2>
            <button>확인</button>
          </ModalShell>
        </StrictMode>,
      );

      await screen.findByRole('dialog', { name: 'Strict 모달' });
      expect(document.body.style.overflow).toBe('hidden');
      expect(persistentBackground).toHaveAttribute('inert');
      expect(ordinaryBackground).toHaveAttribute('inert');
      expect(document.querySelectorAll('[data-modal-layer]')).toHaveLength(1);

      view.unmount();
      expect(document.body.style.overflow).toBe('clip');
      expect(persistentBackground).toHaveAttribute('inert');
      expect(ordinaryBackground).not.toHaveAttribute('inert');

      fireEvent.keyDown(document, { key: 'Escape' });
      expect(onClose).not.toHaveBeenCalled();
    } finally {
      persistentBackground.remove();
      ordinaryBackground.remove();
      document.body.style.overflow = previousOverflow;
    }
  });
});

describe('확인 대화상자 초점', () => {
  it('alertdialog 안의 취소 버튼에 초기 초점을 둔다', async () => {
    render(
      <ConfirmationModal
        isOpen
        title="모의투자 초기화"
        message="정말로 초기화하시겠습니까?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    expect(screen.getByRole('button', { name: '취소' })).toHaveFocus();
  });
});
