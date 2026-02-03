'use client';

import React, { useEffect, useState } from 'react';

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
    <div className={`fixed inset-0 z-[100] flex items-center justify-center transition-opacity duration-200 ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal Content */}
      <div className={`relative bg-[#1c1c1e] border border-white/10 rounded-2xl shadow-2xl w-full ${maxWidth ? maxWidth : (wide ? 'max-w-4xl' : 'max-w-md')} overflow-hidden flex flex-col max-h-[90vh] transform transition-all duration-200 ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'}`}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-white/5">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            {type === 'success' && <i className="fas fa-check-circle text-emerald-500"></i>}
            {type === 'danger' && <i className="fas fa-exclamation-circle text-red-500"></i>}
            {title}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10">
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
      </div>
    </div>
  );
}
