'use client';

import React, {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';

// [JONGGA-006] 종전에는 같은 컴포넌트가 세 벌 있었다. 이 파일과
// dashboard/kr/closing-bet/page.tsx 와 dashboard/data-status/page.tsx 가 저마다
// 정의했고 시각이 서로 달랐다. 셋을 여기로 모으면서 그 차이를 size 로 흡수했다.
//
// 크기만 바뀌는 것이 아니라 안쪽 여백과 글자 크기와 모서리와 정렬이 함께 움직인다.
// 짧은 힌트를 띄우는 작은 툴팁은 가운데 정렬이 읽기 좋고, 여러 줄 설명을 담는 큰
// 툴팁은 왼쪽 정렬에 낱말 단위 줄바꿈이 필요하기 때문이다. 그래서 개별 프롭으로
// 쪼개지 않고 프리셋 하나로 둔다.
const SIZE_CLASSES = {
  sm: 'w-52 max-w-[220px] px-3 py-2 text-[10px] rounded-lg text-center',
  md: 'w-64 max-w-[280px] px-3 py-2 text-[10px] rounded-lg text-center',
  lg: 'min-w-[260px] w-max max-w-[320px] px-4 py-3 text-xs rounded-xl text-left break-keep',
} as const;

const VIEWPORT_MARGIN = 8;
const TRIGGER_GAP = 8;
const CLOSE_DELAY_MS = 300;
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not(:disabled)',
  'input:not(:disabled):not([type="hidden"])',
  'select:not(:disabled)',
  'textarea:not(:disabled)',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',');

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  className?: string;
  position?: 'top' | 'bottom';
  align?: 'left' | 'center' | 'right';
  as?: 'span' | 'div';
  size?: keyof typeof SIZE_CLASSES;
}

interface TooltipLayout {
  left: number;
  top: number;
  arrowLeft: number;
  placement: 'top' | 'bottom';
  measured: boolean;
}

const INITIAL_LAYOUT: TooltipLayout = {
  left: 0,
  top: 0,
  arrowLeft: 0,
  placement: 'top',
  measured: false,
};

function joinDescriptionIds(existingId: string | undefined, tooltipId: string): string {
  return existingId ? `${existingId} ${tooltipId}` : tooltipId;
}

export default function Tooltip({
  children,
  content,
  className = '',
  position = 'top',
  align = 'center',
  as: Component = 'span',
  size = 'sm',
}: TooltipProps) {
  const tooltipId = useId();
  const wrapperRef = useRef<HTMLElement | null>(null);
  const triggerElementRef = useRef<HTMLElement | null>(null);
  const popupRef = useRef<HTMLDivElement | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const describedElementRef = useRef<{
    element: HTMLElement;
    originalDescription: string | null;
  } | null>(null);
  const triggerHoveredRef = useRef(false);
  const popupHoveredRef = useRef(false);
  const focusWithinRef = useRef(false);
  const [isOpen, setIsOpen] = useState(false);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const [hasFocusableDescendant, setHasFocusableDescendant] = useState(false);
  const [layout, setLayout] = useState<TooltipLayout>({
    ...INITIAL_LAYOUT,
    placement: position,
  });

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current !== null) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  const restoreDescribedElement = useCallback(() => {
    const described = describedElementRef.current;
    if (!described) return;

    if (described.originalDescription === null) {
      described.element.removeAttribute('aria-describedby');
    } else {
      described.element.setAttribute('aria-describedby', described.originalDescription);
    }
    describedElementRef.current = null;
  }, []);

  const describeFocusedElement = useCallback((element: HTMLElement) => {
    if (!element.matches(FOCUSABLE_SELECTOR)) return;
    restoreDescribedElement();

    const originalDescription = element.getAttribute('aria-describedby');
    element.setAttribute(
      'aria-describedby',
      joinDescriptionIds(originalDescription ?? undefined, tooltipId),
    );
    describedElementRef.current = { element, originalDescription };
  }, [restoreDescribedElement, tooltipId]);

  const closeTooltip = useCallback(() => {
    clearCloseTimer();
    restoreDescribedElement();
    triggerHoveredRef.current = false;
    popupHoveredRef.current = false;
    focusWithinRef.current = false;
    setIsOpen(false);
    setPortalTarget(null);
  }, [clearCloseTimer, restoreDescribedElement]);

  const scheduleClose = useCallback(() => {
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => {
      closeTimerRef.current = null;
      if (
        !triggerHoveredRef.current
        && !popupHoveredRef.current
        && !focusWithinRef.current
      ) {
        restoreDescribedElement();
        setIsOpen(false);
        setPortalTarget(null);
      }
    }, CLOSE_DELAY_MS);
  }, [clearCloseTimer, restoreDescribedElement]);

  const openForElement = useCallback((element: HTMLElement) => {
    const modalLayer = element.closest<HTMLElement>('[data-modal-layer]');
    if (modalLayer && modalLayer.dataset.modalActive !== 'true') {
      closeTooltip();
      return;
    }

    clearCloseTimer();
    triggerElementRef.current = element;
    setLayout({ ...INITIAL_LAYOUT, placement: position });
    setPortalTarget(modalLayer ?? document.body);
    setIsOpen(true);
  }, [clearCloseTimer, closeTooltip, position]);

  const resolveEventElement = useCallback((target: EventTarget | null): HTMLElement | null => {
    if (!(target instanceof HTMLElement)) return wrapperRef.current;
    return wrapperRef.current?.contains(target) ? target : null;
  }, []);

  const handleTriggerMouseEnter = useCallback((event: React.MouseEvent<HTMLElement>) => {
    const element = resolveEventElement(event.target);
    if (!element || !wrapperRef.current?.contains(element)) return;
    triggerHoveredRef.current = true;
    openForElement(element);
  }, [openForElement, resolveEventElement]);

  const handleTriggerMouseLeave = useCallback(() => {
    triggerHoveredRef.current = false;
    scheduleClose();
  }, [scheduleClose]);

  const handleFocusCapture = useCallback((event: React.FocusEvent<HTMLElement>) => {
    const element = resolveEventElement(event.target);
    if (!element || !wrapperRef.current?.contains(element)) return;
    focusWithinRef.current = true;
    if (hasFocusableDescendant) describeFocusedElement(element);
    openForElement(element);
  }, [describeFocusedElement, hasFocusableDescendant, openForElement, resolveEventElement]);

  const handleBlurCapture = useCallback((event: React.FocusEvent<HTMLElement>) => {
    if (
      event.relatedTarget instanceof Node
      && wrapperRef.current?.contains(event.relatedTarget)
    ) {
      return;
    }
    focusWithinRef.current = false;
    scheduleClose();
  }, [scheduleClose]);

  const updatePosition = useCallback(() => {
    const trigger = triggerElementRef.current ?? wrapperRef.current;
    const popup = popupRef.current;
    if (!trigger || !popup) return;

    const triggerRect = trigger.getBoundingClientRect();
    const popupRect = popup.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const maxWidth = Math.max(0, viewportWidth - VIEWPORT_MARGIN * 2);
    const maxHeight = Math.max(0, viewportHeight - VIEWPORT_MARGIN * 2);
    const popupWidth = Math.min(popupRect.width, maxWidth);
    const popupHeight = Math.min(popupRect.height, maxHeight);
    const topCandidate = triggerRect.top - TRIGGER_GAP - popupHeight;
    const bottomCandidate = triggerRect.bottom + TRIGGER_GAP;
    const fitsTop = topCandidate >= VIEWPORT_MARGIN;
    const fitsBottom = bottomCandidate + popupHeight <= viewportHeight - VIEWPORT_MARGIN;
    const spaceAbove = triggerRect.top - VIEWPORT_MARGIN;
    const spaceBelow = viewportHeight - VIEWPORT_MARGIN - triggerRect.bottom;
    let placement = position;

    if (position === 'top' && !fitsTop && (fitsBottom || spaceBelow > spaceAbove)) {
      placement = 'bottom';
    } else if (position === 'bottom' && !fitsBottom && (fitsTop || spaceAbove > spaceBelow)) {
      placement = 'top';
    }

    let desiredLeft = triggerRect.left;
    if (align === 'center') {
      desiredLeft = triggerRect.left + triggerRect.width / 2 - popupWidth / 2;
    } else if (align === 'right') {
      desiredLeft = triggerRect.right - popupWidth;
    }

    const maximumLeft = Math.max(VIEWPORT_MARGIN, viewportWidth - VIEWPORT_MARGIN - popupWidth);
    const left = Math.min(Math.max(desiredLeft, VIEWPORT_MARGIN), maximumLeft);
    const desiredTop = placement === 'top' ? topCandidate : bottomCandidate;
    const maximumTop = Math.max(VIEWPORT_MARGIN, viewportHeight - VIEWPORT_MARGIN - popupHeight);
    const top = Math.min(Math.max(desiredTop, VIEWPORT_MARGIN), maximumTop);
    const triggerCenter = triggerRect.left + triggerRect.width / 2;
    const arrowLeft = Math.min(
      Math.max(triggerCenter - left, VIEWPORT_MARGIN),
      Math.max(VIEWPORT_MARGIN, popupWidth - VIEWPORT_MARGIN),
    );

    setLayout({
      left,
      top,
      arrowLeft,
      placement,
      measured: true,
    });
  }, [align, position]);

  useLayoutEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    setHasFocusableDescendant(wrapper.querySelector(FOCUSABLE_SELECTOR) !== null);
  }, [children]);

  useLayoutEffect(() => {
    if (!isOpen || !portalTarget) return;

    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    const resizeObserver = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(updatePosition);
    const trigger = triggerElementRef.current ?? wrapperRef.current;
    if (trigger) resizeObserver?.observe(trigger);
    if (popupRef.current) resizeObserver?.observe(popupRef.current);

    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
      resizeObserver?.disconnect();
    };
  }, [isOpen, portalTarget, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;

    const modalLayer = triggerElementRef.current?.closest<HTMLElement>('[data-modal-layer]');
    if (!modalLayer) return;

    const closeIfInactive = () => {
      if (modalLayer.dataset.modalActive !== 'true') closeTooltip();
    };
    closeIfInactive();

    const observer = new MutationObserver(closeIfInactive);
    observer.observe(modalLayer, { attributes: true, attributeFilter: ['data-modal-active'] });
    return () => observer.disconnect();
  }, [closeTooltip, isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeTooltip();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [closeTooltip, isOpen]);

  useEffect(() => () => {
    clearCloseTimer();
    restoreDescribedElement();
  }, [clearCloseTimer, restoreDescribedElement]);

  const hasDisplayClass = className.includes('flex') || className.includes('block');
  const baseClasses = `relative group/tooltip ${hasDisplayClass ? '' : 'inline-flex items-center'}`;
  const arrowClass = layout.placement === 'bottom'
    ? 'bottom-full border-b-gray-900/95 -mb-1'
    : 'top-full border-t-gray-900/95 -mt-1';
  const viewportMaxHeight = typeof window === 'undefined'
    ? 0
    : Math.max(0, window.innerHeight - VIEWPORT_MARGIN * 2);
  const viewportMaxWidth = typeof window === 'undefined'
    ? 0
    : Math.max(0, window.innerWidth - VIEWPORT_MARGIN * 2);

  const popup = isOpen && portalTarget
    ? createPortal(
      <div
        ref={popupRef}
        id={tooltipId}
        role="tooltip"
        className={`${SIZE_CLASSES[size]} fixed bg-gray-900/95 text-gray-200 font-medium z-[100] border border-white/10 shadow-xl backdrop-blur-sm leading-relaxed whitespace-normal pointer-events-auto transition-opacity`}
        style={{
          left: layout.left,
          top: layout.top,
          maxHeight: viewportMaxHeight,
          maxWidth: viewportMaxWidth,
          overflowY: 'auto',
          visibility: layout.measured ? 'visible' : 'hidden',
        }}
        onMouseEnter={() => {
          popupHoveredRef.current = true;
          clearCloseTimer();
        }}
        onMouseLeave={() => {
          popupHoveredRef.current = false;
          scheduleClose();
        }}
        onFocusCapture={() => {
          focusWithinRef.current = true;
          clearCloseTimer();
        }}
        onBlurCapture={() => {
          focusWithinRef.current = false;
          scheduleClose();
        }}
      >
        {content}
        <div
          aria-hidden="true"
          className={`absolute border-4 border-transparent ${arrowClass}`}
          style={{ left: layout.arrowLeft, transform: 'translateX(-50%)' }}
        />
      </div>,
      portalTarget,
    )
    : null;

  return (
    <Component
      ref={(node: HTMLSpanElement | HTMLDivElement | null) => {
        wrapperRef.current = node;
      }}
      className={`${baseClasses} ${className}`.trim()}
      tabIndex={hasFocusableDescendant ? undefined : 0}
      aria-describedby={!hasFocusableDescendant && isOpen ? tooltipId : undefined}
      onMouseEnter={handleTriggerMouseEnter}
      onMouseLeave={handleTriggerMouseLeave}
      onFocusCapture={handleFocusCapture}
      onBlurCapture={handleBlurCapture}
    >
      {children}
      {popup}
    </Component>
  );
}
