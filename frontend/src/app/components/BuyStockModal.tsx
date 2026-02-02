'use client';

import { useState, useEffect } from 'react';
import Modal from './Modal';

interface BuyStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: {
    ticker: string;
    name: string;
    price: number;
  } | null;
  onBuy: (ticker: string, name: string, price: number, quantity: number) => Promise<boolean>;
}

export default function BuyStockModal({ isOpen, onClose, stock, onBuy }: BuyStockModalProps) {
  const [quantity, setQuantity] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setQuantity(10); // Default quantity
    }
  }, [isOpen]);

  if (!stock) return null;

  const totalCost = stock.price * quantity;

  const handleSubmit = async () => {
    if (quantity <= 0) return;
    setIsSubmitting(true);
    try {
      const success = await onBuy(stock.ticker, stock.name, stock.price, quantity);
      if (success) {
        onClose();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="모의 투자 매수"
      maxWidth="max-w-md"
      footer={
        <div className="flex justify-end gap-3 w-full">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-transparent text-gray-400 hover:text-white text-sm font-medium rounded-lg transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || quantity <= 0}
            className="px-6 py-2 bg-rose-500 hover:bg-rose-600 text-white text-sm font-bold rounded-lg transition-colors shadow-lg shadow-rose-900/20 disabled:opacity-50"
          >
            {isSubmitting ? <i className="fas fa-spinner fa-spin"></i> : '매수 주문'}
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="flex items-center justify-between p-4 bg-[#18181b] rounded-xl border border-white/5">
          <div>
            <div className="text-lg font-bold text-white">{stock.name}</div>
            <div className="text-sm text-gray-400">{stock.ticker}</div>
          </div>
          <div className="text-right">
            <div className="text-xl font-bold text-rose-400">{stock.price.toLocaleString()}원</div>
            <div className="text-xs text-gray-500">현재가/진입가</div>
          </div>
        </div>

        <div>
          <label className="block text-xs font-bold text-gray-500 mb-2">구매 수량 (주)</label>
          <input
            type="number"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 0))}
            className="w-full bg-[#18181b] border border-white/10 rounded-lg px-4 py-3 text-white text-lg font-bold focus:outline-none focus:border-rose-500 transition-colors text-right"
          />
        </div>

        <div className="p-4 bg-[#27272a] rounded-xl border border-white/5 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">주문 금액</span>
            <span className="text-white font-medium">{totalCost.toLocaleString()} 원</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">수수료 (0.015% 가정)</span>
            <span className="text-white font-medium">{Math.floor(totalCost * 0.00015).toLocaleString()} 원</span>
          </div>
          <div className="pt-2 border-t border-white/10 flex justify-between text-base font-bold text-rose-400">
            <span>총 결제 예상 금액</span>
            <span>{(totalCost + Math.floor(totalCost * 0.00015)).toLocaleString()} 원</span>
          </div>
        </div>
      </div>
    </Modal>
  );
}
