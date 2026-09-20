'use client';

import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

export interface ModalShellProps {
  onClose: () => void;
  labelledBy: string;
  children: React.ReactNode;
  /** 다이얼로그 카드에 붙일 클래스. 폭과 여백과 배경이 모달마다 다르다. */
  className: string;
  /** 포털 host에 덧붙일 클래스. z-index와 바깥 여백이 모달마다 다르다. */
  overlayClassName: string;
  /** 배경 판에 붙일 클래스. 어둡기가 모달마다 다르다. */
  backdropClassName?: string;
  role?: 'dialog' | 'alertdialog';
  initialFocusRef?: React.RefObject<HTMLElement | null>;
}

interface ModalShellEntry {
  layer: HTMLElement;
  dialog: HTMLElement;
  onCloseRef: React.RefObject<() => void>;
  initialFocusRef?: React.RefObject<HTMLElement | null>;
  previousFocus: HTMLElement | null;
}

interface BodyOverflowSnapshot {
  value: string;
  priority: string;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'object',
  'embed',
  '[contenteditable]:not([contenteditable="false"])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

const modalShellStack: ModalShellEntry[] = [];
const inertSnapshots = new Map<HTMLElement, boolean>();
let bodyOverflowSnapshot: BodyOverflowSnapshot | null = null;
let bodyObserver: MutationObserver | null = null;

function isAvailableForFocus(element: HTMLElement): boolean {
  if (!element.isConnected || element.closest('[hidden], [inert]')) return false;
  let current: HTMLElement | null = element;
  while (current) {
    const style = window.getComputedStyle(current);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    current = current.parentElement;
  }
  return true;
}

function focusElement(element: HTMLElement): void {
  element.focus({ preventScroll: true });
}

function focusableElements(dialog: HTMLElement): HTMLElement[] {
  return Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(isAvailableForFocus);
}

function focusEntry(entry: ModalShellEntry, useInitialFocus = true): void {
  const requested = useInitialFocus ? entry.initialFocusRef?.current : null;
  if (requested && entry.dialog.contains(requested) && isAvailableForFocus(requested)) {
    focusElement(requested);
    return;
  }

  const first = focusableElements(entry.dialog)[0];
  focusElement(first ?? entry.dialog);
}

function rememberAndSetInert(element: HTMLElement): void {
  if (!inertSnapshots.has(element)) {
    inertSnapshots.set(element, element.hasAttribute('inert'));
  }
  element.setAttribute('inert', '');
}

function restoreManagedInert(element: HTMLElement): void {
  const hadInert = inertSnapshots.get(element);
  if (hadInert === undefined) return;
  if (!hadInert) element.removeAttribute('inert');
  inertSnapshots.delete(element);
}

function restoreAllManagedInert(): void {
  inertSnapshots.forEach((hadInert, element) => {
    if (element.isConnected && !hadInert) element.removeAttribute('inert');
  });
  inertSnapshots.clear();
}

function syncModalEnvironment(): void {
  const top = modalShellStack[modalShellStack.length - 1];

  modalShellStack.forEach((entry, index) => {
    entry.layer.style.zIndex = String(1_000 + index);
  });

  document.querySelectorAll<HTMLElement>('[data-modal-layer]').forEach((layer) => {
    if (layer === top?.layer) {
      layer.setAttribute('data-modal-active', 'true');
      restoreManagedInert(layer);
    } else {
      layer.removeAttribute('data-modal-active');
      if (top) rememberAndSetInert(layer);
    }
  });

  if (!top) {
    restoreAllManagedInert();
    return;
  }

  Array.from(document.body.children).forEach((child) => {
    if (!(child instanceof HTMLElement) || child === top.layer) return;
    rememberAndSetInert(child);
  });

  inertSnapshots.forEach((_hadInert, element) => {
    if (!element.isConnected) inertSnapshots.delete(element);
  });
}

function handleDocumentKeyDown(event: KeyboardEvent): void {
  const top = modalShellStack[modalShellStack.length - 1];
  if (!top) return;

  if (event.key === 'Escape') {
    if (top.layer.querySelector('[role="tooltip"]')) return;
    event.preventDefault();
    event.stopPropagation();
    top.onCloseRef.current();
    return;
  }

  if (event.key !== 'Tab') return;
  const focusable = focusableElements(top.dialog);
  if (focusable.length === 0) {
    event.preventDefault();
    focusElement(top.dialog);
    return;
  }

  const active = document.activeElement;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && (active === first || !top.dialog.contains(active))) {
    event.preventDefault();
    focusElement(last);
  } else if (!event.shiftKey && (active === last || !top.dialog.contains(active))) {
    event.preventDefault();
    focusElement(first);
  }
}

function lockBody(): void {
  if (bodyOverflowSnapshot) return;
  bodyOverflowSnapshot = {
    value: document.body.style.getPropertyValue('overflow'),
    priority: document.body.style.getPropertyPriority('overflow'),
  };
  document.body.style.setProperty('overflow', 'hidden');
  document.addEventListener('keydown', handleDocumentKeyDown);
  bodyObserver = new MutationObserver(() => syncModalEnvironment());
  bodyObserver.observe(document.body, { childList: true });
}

function unlockBody(): void {
  document.removeEventListener('keydown', handleDocumentKeyDown);
  bodyObserver?.disconnect();
  bodyObserver = null;
  if (bodyOverflowSnapshot) {
    if (bodyOverflowSnapshot.value) {
      document.body.style.setProperty(
        'overflow',
        bodyOverflowSnapshot.value,
        bodyOverflowSnapshot.priority,
      );
    } else {
      document.body.style.removeProperty('overflow');
    }
    bodyOverflowSnapshot = null;
  }
}

function registerModal(entry: ModalShellEntry): () => void {
  if (modalShellStack.length === 0) lockBody();
  modalShellStack.push(entry);
  syncModalEnvironment();
  focusEntry(entry);

  return () => {
    const index = modalShellStack.indexOf(entry);
    if (index === -1) return;
    const wasTop = index === modalShellStack.length - 1;
    modalShellStack.splice(index, 1);
    syncModalEnvironment();

    if (modalShellStack.length === 0) unlockBody();
    if (!wasTop) return;

    if (entry.previousFocus && isAvailableForFocus(entry.previousFocus)) {
      focusElement(entry.previousFocus);
      return;
    }

    const nextTop = modalShellStack[modalShellStack.length - 1];
    if (nextTop) {
      focusEntry(nextTop, false);
    } else {
      focusElement(document.body);
    }
  };
}

/**
 * 공용 모달 셸이다. 카드가 아니라 전체 화면 host를 body의 직접 자식으로 portal한다.
 * 열려 있는 맨 위 셸만 입력과 초점을 받고, 마지막 셸이 실제로 언마운트될 때 배경과
 * body 스크롤 및 이전 초점을 원래 상태로 돌린다.
 */
export function ModalShell({
  onClose,
  labelledBy,
  children,
  className,
  overlayClassName,
  backdropClassName = 'bg-black/80 backdrop-blur-sm',
  role = 'dialog',
  initialFocusRef,
}: ModalShellProps) {
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);
  const layerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);

  useLayoutEffect(() => {
    const layer = layerRef.current;
    const dialog = dialogRef.current;
    if (!portalTarget || !layer || !dialog) return;

    return registerModal({
      layer,
      dialog,
      onCloseRef,
      initialFocusRef,
      previousFocus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
    });
  }, [portalTarget]);

  if (!portalTarget) return null;

  return createPortal(
    <div
      ref={layerRef}
      data-modal-layer=""
      className={`fixed inset-0 overflow-visible flex items-center justify-center ${overlayClassName}`}
      style={{ transform: 'none', filter: 'none' }}
    >
      <div
        aria-hidden="true"
        className={`absolute inset-0 ${backdropClassName}`}
        onClick={() => {
          if (modalShellStack[modalShellStack.length - 1]?.layer === layerRef.current) {
            onCloseRef.current();
          }
        }}
      />
      <div
        ref={dialogRef}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={className}
      >
        {children}
      </div>
    </div>,
    portalTarget,
  );
}

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  type?: 'default' | 'danger' | 'success';
  wide?: boolean;
}

export default function Modal({ isOpen, onClose, title, children, footer, type = 'default', wide = false, maxWidth }: ModalProps & { maxWidth?: string }) {
  const [show, setShow] = useState(isOpen);
  const titleId = useId();

  useEffect(() => {
    if (isOpen) {
      setShow(true);
    } else {
      const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const timer = window.setTimeout(() => setShow(false), reduceMotion ? 0 : 200);
      return () => window.clearTimeout(timer);
    }
  }, [isOpen]);

  if (!show && !isOpen) return null;

  return (
    <ModalShell
      onClose={onClose}
      labelledBy={titleId}
      overlayClassName={`z-[100] transition-opacity duration-200 motion-reduce:transition-none ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      backdropClassName="bg-black/60 backdrop-blur-sm"
      className={`relative bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl w-full ${maxWidth ? maxWidth : (wide ? 'max-w-4xl' : 'max-w-md')} overflow-hidden flex flex-col max-h-[90vh] transform transition-all duration-200 motion-reduce:transition-none ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}`}
    >
      <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
        <h3 id={titleId} className="text-lg font-bold text-white flex items-center gap-2">
          {type === 'success' && <i className="fas fa-check-circle text-emerald-500"></i>}
          {type === 'danger' && <i className="fas fa-exclamation-circle text-red-500"></i>}
          {title}
        </h3>
        <button onClick={onClose} aria-label="닫기" className="text-gray-400 hover:text-white transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10">
          <i className="fas fa-times"></i>
        </button>
      </div>

      <div className="p-6 text-gray-300 leading-relaxed text-sm overflow-y-auto">
        {children}
      </div>

      {footer && (
        <div className="px-6 py-4 bg-[#151517] border-t border-white/5 flex justify-end gap-3">
          {footer}
        </div>
      )}
    </ModalShell>
  );
}
