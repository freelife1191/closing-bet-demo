'use client';

import React from 'react';

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
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in">
      <div
        className="bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4 transform transition-all scale-100 animate-scale-in"
        role="dialog"
        aria-modal="true"
      >
        <div className="flex flex-col items-center text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center">
            <i className="fas fa-exclamation-triangle text-rose-500 text-xl"></i>
          </div>

          <h3 className="text-lg font-bold text-white">
            {title}
          </h3>

          <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
            {message}
          </p>

          <div className="flex gap-3 w-full pt-4">
            <button
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
      </div>
    </div>
  );
}
