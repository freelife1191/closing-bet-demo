'use client';

import React, { useEffect, useId, useRef, useState } from 'react';

interface ModalShellProps {
  onClose: () => void;
  labelledBy: string;
  children: React.ReactNode;
  /** 다이얼로그 카드에 붙일 클래스. 폭과 여백과 배경이 모달마다 다르다. */
  className: string;
  /** 오버레이에 덧붙일 클래스. z-index 와 바깥 여백이 모달마다 다르다. */
  overlayClassName: string;
  /** 배경 판에 붙일 클래스. 어둡기가 모달마다 다르다. */
  backdropClassName?: string;
}

/** 열려 있는 셸을 마운트 순서대로 담는다. Escape 를 맨 위의 셸에만 넘기는 데 쓴다. */
const modalShellStack: object[] = [];

/**
 * 모달 여섯 벌이 함께 쓰는 셸이다. 오버레이와 배경 클릭으로 닫기, Escape 키,
 * 그리고 화면 낭독기가 대화상자로 인식하는 데 필요한 세 속성을 이 자리에서
 * 한 번만 보장한다. 종전에는 같은 코드가 다섯 벌 있었고 갖춘 기능이 서로 달라서,
 * 매수와 매도 모달에서는 Escape 키가 듣지 않았다.
 *
 * 마운트 여부는 호출자가 정한다. 아래의 `Modal` 처럼 닫히는 애니메이션이 끝날
 * 때까지 남아 있어야 하는 모달과, 곧바로 사라지는 모달이 섞여 있기 때문이다.
 */
export function ModalShell({
  onClose,
  labelledBy,
  children,
  className,
  overlayClassName,
  backdropClassName = 'bg-black/80 backdrop-blur-sm',
}: ModalShellProps) {
  const idRef = useRef({});

  // 마운트 순서를 쌓아 둔다. 등록만 하는 훅을 따로 두는 이유는 아래 훅의 의존성이
  // `onClose` 이기 때문이다. 호출자가 인라인 화살표 함수를 넘기면 렌더마다 새 함수가
  // 되어 그 훅이 다시 돌아가는데, 그때마다 스택에서 빠졌다 맨 뒤로 다시 들어가면
  // 쌓인 순서가 실제 마운트 순서와 어긋난다.
  useEffect(() => {
    const id = idRef.current;
    modalShellStack.push(id);
    return () => {
      const at = modalShellStack.indexOf(id);
      if (at !== -1) modalShellStack.splice(at, 1);
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // 맨 위의 셸만 반응한다. 리스너가 셸마다 document 에 붙으므로 이 판정이 없으면
      // 모의투자 모달 위에 매수 모달이 열린 상태에서 Escape 한 번에 둘 다 닫힌다.
      if (e.key !== 'Escape') return;
      if (modalShellStack[modalShellStack.length - 1] !== idRef.current) return;
      onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className={`fixed inset-0 flex items-center justify-center ${overlayClassName}`}>
      <div className={`absolute inset-0 ${backdropClassName}`} onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-labelledby={labelledBy} className={className}>
        {children}
      </div>
    </div>
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
      const timer = setTimeout(() => setShow(false), 200); // Wait for animation
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  if (!show && !isOpen) return null;

  return (
    <ModalShell
      onClose={onClose}
      labelledBy={titleId}
      overlayClassName={`z-[100] transition-opacity duration-200 ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      backdropClassName="bg-black/60 backdrop-blur-sm"
      className={`relative bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl w-full ${maxWidth ? maxWidth : (wide ? 'max-w-4xl' : 'max-w-md')} overflow-hidden flex flex-col max-h-[90vh] transform transition-all duration-200 ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}`}
    >
      {/* Header */}
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

      {/* Body */}
      <div className="p-6 text-gray-300 leading-relaxed text-sm overflow-y-auto">
        {children}
      </div>

      {/* Footer */}
      {footer && (
        <div className="px-6 py-4 bg-[#151517] border-t border-white/5 flex justify-end gap-3">
          {footer}
        </div>
      )}
    </ModalShell>
  );
}
