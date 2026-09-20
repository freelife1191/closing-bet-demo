import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Tooltip from './Tooltip';

const VIEWPORT_MARGIN = 8;

interface RectInit {
  left: number;
  top: number;
  width: number;
  height: number;
}

function rect({ left, top, width, height }: RectInit): DOMRect {
  return new DOMRect(left, top, width, height);
}

function setViewport(width: number, height: number) {
  Object.defineProperties(window, {
    innerWidth: { configurable: true, value: width },
    innerHeight: { configurable: true, value: height },
  });
}

function renderTooltip({
  size,
  position = 'top',
  align = 'center',
}: {
  size?: 'sm' | 'md' | 'lg';
  position?: 'top' | 'bottom';
  align?: 'left' | 'center' | 'right';
} = {}) {
  return render(
    <Tooltip content="설명" size={size} position={position} align={align}>
      <button type="button" data-testid="tooltip-trigger">
        도움말
      </button>
    </Tooltip>,
  );
}

function openWithHover() {
  fireEvent.mouseEnter(screen.getByTestId('tooltip-trigger'));
  return screen.getByRole('tooltip');
}

describe('Tooltip', () => {
  beforeEach(() => {
    setViewport(320, 240);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('size 프리셋', () => {
    function 열린툴팁상자(size?: 'sm' | 'md' | 'lg') {
      renderTooltip({ size });
      return openWithHover().className;
    }

    it('기본값은 작은 시각이다', () => {
      const cls = 열린툴팁상자();
      expect(cls).toContain('w-52');
      expect(cls).toContain('text-[10px]');
      expect(cls).toContain('text-center');
    });

    it('md 는 폭만 넓히고 나머지는 sm 과 같다', () => {
      const cls = 열린툴팁상자('md');
      expect(cls).toContain('w-64');
      expect(cls).toContain('text-[10px]');
      expect(cls).toContain('px-3');
    });

    it('lg 는 종전 공용 시각을 그대로 낸다', () => {
      const cls = 열린툴팁상자('lg');
      expect(cls).toContain('min-w-[260px]');
      expect(cls).toContain('text-xs');
      expect(cls).toContain('text-left');
      expect(cls).toContain('break-keep');
    });

    it('세 시각이 공유하는 것은 크기가 달라져도 남는다', () => {
      for (const size of ['sm', 'md', 'lg'] as const) {
        const { unmount } = renderTooltip({ size });
        const cls = openWithHover().className;
        expect(cls).toContain('bg-gray-900/95');
        expect(cls).toContain('z-[100]');
        unmount();
      }
    });
  });

  it('닫힌 동안은 팝업을 만들거나 위치를 재지 않고, 열릴 때만 실측한다', async () => {
    const measure = vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect');
    renderTooltip();

    expect(screen.queryByRole('tooltip')).toBeNull();
    expect(measure).not.toHaveBeenCalled();

    openWithHover();
    await waitFor(() => expect(measure.mock.calls.length).toBeGreaterThan(0));
  });

  it('위 공간이 부족하면 아래로 뒤집고 좌우를 viewport 안으로 제한한다', async () => {
    const triggerRect = rect({ left: 2, top: 2, width: 24, height: 20 });
    const popupRect = rect({ left: 0, top: 0, width: 220, height: 80 });

    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.getAttribute('role') === 'tooltip') return popupRect;
      if (this.getAttribute('data-testid') === 'tooltip-trigger') return triggerRect;
      return rect({ left: 0, top: 0, width: 0, height: 0 });
    });

    renderTooltip({ position: 'top', align: 'center' });
    const popup = openWithHover();

    await waitFor(() => {
      const left = Number.parseFloat(popup.style.left);
      const top = Number.parseFloat(popup.style.top);
      expect(popup.className).toContain('fixed');
      expect(left).toBeGreaterThanOrEqual(VIEWPORT_MARGIN);
      expect(left + popupRect.width).toBeLessThanOrEqual(window.innerWidth - VIEWPORT_MARGIN);
      expect(top).toBeGreaterThanOrEqual(triggerRect.bottom);
    });
  });

  it('스크롤과 resize 뒤 현재 trigger 위치로 다시 배치한다', async () => {
    let triggerRect = rect({ left: 120, top: 140, width: 40, height: 20 });
    const popupRect = rect({ left: 0, top: 0, width: 100, height: 40 });

    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.getAttribute('role') === 'tooltip') return popupRect;
      if (this.getAttribute('data-testid') === 'tooltip-trigger') return triggerRect;
      return rect({ left: 0, top: 0, width: 0, height: 0 });
    });

    renderTooltip();
    const popup = openWithHover();
    await waitFor(() => expect(popup.style.left).not.toBe(''));
    const initialLeft = popup.style.left;
    const initialTop = popup.style.top;

    triggerRect = rect({ left: 180, top: 110, width: 40, height: 20 });
    act(() => window.dispatchEvent(new Event('scroll')));
    await waitFor(() => {
      expect(popup.style.left).not.toBe(initialLeft);
      expect(popup.style.top).not.toBe(initialTop);
    });

    const afterScrollLeft = popup.style.left;
    setViewport(240, 200);
    triggerRect = rect({ left: 80, top: 90, width: 40, height: 20 });
    act(() => window.dispatchEvent(new Event('resize')));
    await waitFor(() => expect(popup.style.left).not.toBe(afterScrollLeft));
  });

  it('viewport보다 긴 설명은 화면 안의 스크롤 가능한 높이로 제한한다', async () => {
    setViewport(320, 360);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      if (this.getAttribute('role') === 'tooltip') {
        return rect({ left: 0, top: 0, width: 220, height: 900 });
      }
      if (this.getAttribute('data-testid') === 'tooltip-trigger') {
        return rect({ left: 140, top: 170, width: 24, height: 20 });
      }
      return rect({ left: 0, top: 0, width: 0, height: 0 });
    });

    renderTooltip();
    const popup = openWithHover();

    await waitFor(() => {
      expect(Number.parseFloat(popup.style.maxHeight)).toBeLessThanOrEqual(
        window.innerHeight - VIEWPORT_MARGIN * 2,
      );
      expect(popup.style.overflowY).toBe('auto');
    });
  });

  it('trigger를 떠난 뒤 200ms 걸려 팝업에 도착해도 읽는 동안 유지한다', () => {
    vi.useFakeTimers();
    renderTooltip();
    const trigger = screen.getByTestId('tooltip-trigger');
    const popup = openWithHover();

    fireEvent.mouseLeave(trigger);
    act(() => vi.advanceTimersByTime(200));
    fireEvent.mouseEnter(popup);
    act(() => vi.runAllTimers());
    expect(screen.getByRole('tooltip')).toBe(popup);

    fireEvent.mouseLeave(popup);
    act(() => vi.runAllTimers());
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('focus로 열고 설명을 trigger에 연결하며 Escape로 닫는다', () => {
    const { container } = render(
      <Tooltip content="키보드 설명">
        <button type="button" aria-describedby="기존-설명" data-testid="tooltip-trigger">
          도움말
        </button>
      </Tooltip>,
    );
    const trigger = screen.getByTestId('tooltip-trigger');

    fireEvent.focus(trigger);
    const popup = screen.getByRole('tooltip');
    expect(trigger.getAttribute('aria-describedby')?.split(' ')).toEqual([
      '기존-설명',
      popup.id,
    ]);
    expect(trigger.parentElement?.getAttribute('tabindex')).toBeNull();
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
    expect(trigger.getAttribute('aria-describedby')).toBe('기존-설명');
  });

  it.each([
    ['문자열', '도움말', 'span'],
    ['아이콘', <i key="plain-icon" data-testid="plain-icon" />, 'span'],
    ['일반 div', <div key="plain-div" data-testid="plain-div">도움말</div>, 'div'],
  ] as const)('%s 자식에는 wrapper가 한 번만 키보드 초점을 제공한다', (_label, child, as) => {
    const { container } = render(
      <Tooltip content="키보드 설명" as={as}>
        {child}
      </Tooltip>,
    );
    const wrapper = container.firstElementChild;
    if (!(wrapper instanceof HTMLElement)) {
      throw new Error('Tooltip wrapper를 찾지 못했습니다.');
    }

    expect(wrapper.getAttribute('tabindex')).toBe('0');
    fireEvent.focus(wrapper);
    const popup = screen.getByRole('tooltip');
    expect(wrapper.getAttribute('aria-describedby')).toBe(popup.id);
  });

  it('가장 가까운 활성 modal layer에 portal하고 비활성 modal에서는 닫힌다', async () => {
    const { rerender } = render(
      <div data-modal-layer data-modal-active="true" data-testid="modal-layer">
        <Tooltip content="모달 설명">
          <button type="button" data-testid="tooltip-trigger">
            도움말
          </button>
        </Tooltip>
      </div>,
    );
    const layer = screen.getByTestId('modal-layer');
    fireEvent.mouseEnter(screen.getByTestId('tooltip-trigger'));
    expect(layer.contains(screen.getByRole('tooltip'))).toBe(true);

    rerender(
      <div data-modal-layer data-modal-active="false" data-testid="modal-layer">
        <Tooltip content="모달 설명">
          <button type="button" data-testid="tooltip-trigger">
            도움말
          </button>
        </Tooltip>
      </div>,
    );
    await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull());
  });

  it('modal 밖에서는 body에 portal한다', () => {
    renderTooltip();
    const popup = openWithHover();
    expect(popup.parentElement).toBe(document.body);
  });

  it('언마운트하면 scroll과 resize 위치 측정도 정리한다', async () => {
    const measure = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockReturnValue(rect({ left: 40, top: 40, width: 40, height: 20 }));
    const { unmount } = renderTooltip();
    openWithHover();
    await waitFor(() => expect(measure.mock.calls.length).toBeGreaterThan(0));

    unmount();
    const callsAfterUnmount = measure.mock.calls.length;
    act(() => {
      window.dispatchEvent(new Event('scroll'));
      window.dispatchEvent(new Event('resize'));
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });

    expect(measure).toHaveBeenCalledTimes(callsAfterUnmount);
  });
});
