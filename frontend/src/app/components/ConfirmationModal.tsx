'use client';

import { useId, useRef } from 'react';
import { ModalShell } from './Modal';

interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmText?: string;
  cancelText?: string;
}

export default function ConfirmationModal({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = '확인',
  cancelText = '취소'
}: ConfirmationModalProps) {
  const titleId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  if (!isOpen) return null;

  return (
    <ModalShell
      onClose={onCancel}
      labelledBy={titleId}
      role="alertdialog"
      initialFocusRef={cancelButtonRef}
      overlayClassName="z-[100]"
      backdropClassName="bg-black/50 backdrop-blur-sm"
      className="relative bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4 animate-fade-in motion-reduce:animate-none"
    >
      <div className="flex flex-col items-center text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center">
          <i className="fas fa-exclamation-triangle text-rose-500 text-xl"></i>
        </div>

        <h3 id={titleId} className="text-lg font-bold text-white">
          {title}
        </h3>

        <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
          {message}
        </p>

        <div className="flex gap-3 w-full pt-4">
          <button
            ref={cancelButtonRef}
            onClick={onCancel}
            className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 text-sm font-medium transition-colors"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className="flex-1 px-4 py-2.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-white text-sm font-medium transition-colors shadow-lg shadow-rose-500/20"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
