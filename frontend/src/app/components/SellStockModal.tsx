'use client';

import { useState, useEffect } from 'react';
import { paperTradingAPI } from '@/lib/api';

interface SellStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: {
    ticker: string;
    name: string;
    quantity: number; // 보유 수량 (필수)
    current_price?: number;
    avg_price: number;
  } | null;
  onSell: (ticker: string, name: string, price: number, quantity: number) => Promise<boolean>;
}

export default function SellStockModal({ isOpen, onClose, stock, onSell }: SellStockModalProps) {
  const [mode, setMode] = useState<'quantity'>('quantity'); // 매도는 수량 매도만 기본 지원 (금액 매도는 복잡)
  const [quantity, setQuantity] = useState<string>('0');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setQuantity('0');
    }
  }, [isOpen]);

  if (!stock) return null;

  const price = stock.current_price || stock.avg_price || 0;
  const numericQty = parseInt(quantity.replace(/[^0-9]/g, ''), 10) || 0;
  const maxQty = stock.quantity;

  const estimatedTotal = numericQty * price;
  const commission = Math.floor(estimatedTotal * 0.00015); // 0.015%
  const tax = Math.floor(estimatedTotal * 0.002); // 0.2% (국내주식 매도세 가정)
  const finalReceive = estimatedTotal - commission - tax;

  const isInvalid = numericQty <= 0 || numericQty > maxQty;

  const handleSubmit = async () => {
    console.log('[SellStockModal] Submit Clicked. Qty:', numericQty, 'Max:', maxQty, 'Invalid:', isInvalid);
    if (isSubmitting || isInvalid) return;

    setIsSubmitting(true);
    try {
      console.log('[SellStockModal] Calling onSell...');
      const success = await onSell(stock.ticker, stock.name, price, numericQty);
      console.log('[SellStockModal] onSell result:', success);
      if (success) onClose();
    } catch (e: any) {
      console.error('[SellStockModal] Error:', e);
      alert('매도 실패: ' + e.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMax = () => {
    setQuantity(maxQty.toString());
  };

  const handleAdjust = (delta: number) => {
    const newVal = Math.max(0, Math.min(maxQty, numericQty + delta));
    setQuantity(newVal.toString());
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#1c1c1e] w-full max-w-md rounded-2xl border border-white/10 shadow-2xl p-6 animate-in fade-in zoom-in-95 duration-200">

        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">모의 투자 매도</h2>
            <div className="text-sm text-gray-400">
              <span className="text-white font-semibold mr-2">{stock.name}</span>
              <span>{stock.ticker}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <i className="fas fa-times text-xl"></i>
          </button>
        </div>

        {/* Price Info */}
        <div className="flex justify-between items-center bg-white/5 rounded-xl p-4 mb-6 border border-white/5">
          <span className="text-gray-400 text-sm">현재가 (매도가)</span>
          <span className="text-2xl font-bold text-blue-400">
            {price.toLocaleString()}원
          </span>
        </div>

        {/* Input */}
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-500 mb-2">
            매도 수량 (주)
            <span className="float-right text-gray-600 font-normal">
              보유: {maxQty.toLocaleString()}주
            </span>
          </label>

          <div className="relative">
            <input
              type="text"
              className={`w-full bg-[#18181b] border border-white/10 rounded-xl pl-12 pr-16 py-3 text-right text-lg font-bold text-white focus:outline-none focus:border-blue-500 transition-colors ${numericQty > maxQty ? 'border-red-500/50 focus:border-red-500' : ''}`}
              value={quantity}
              placeholder="0"
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, '');
                setQuantity(val || '0');
              }}
            />
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm font-medium">QTY</span>

            {/* 증감 버튼 (Overlay) */}
            <div className="absolute left-1/2 -translate-x-1/2 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 hover:opacity-100 transition-opacity">
              {/* UI 복잡도를 줄이기 위해 여기 넣지 않고 아래 별도 버튼 제공이 나을 수도 있음 */}
            </div>

            <button
              onClick={handleMax}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 px-2 py-1 rounded transition-colors font-medium"
            >
              최대
            </button>
          </div>

          {/* 증감 컨트롤 */}
          <div className="flex justify-center gap-2 mt-2">
            <button onClick={() => handleAdjust(-1)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400"><i className="fas fa-minus"></i></button>
            <button onClick={() => handleAdjust(1)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400"><i className="fas fa-plus"></i></button>
            <button onClick={() => handleAdjust(10)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400 text-xs">+10</button>
            <button onClick={() => handleAdjust(100)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400 text-xs">+100</button>
          </div>

          {numericQty > maxQty && (
            <div className="text-red-400 text-xs mt-2 flex items-center gap-1 animate-pulse">
              <i className="fas fa-exclamation-circle"></i>
              보유 수량을 초과했습니다.
            </div>
          )}
        </div>

        {/* Summary */}
        <div className="bg-[#18181b] rounded-xl p-4 border border-white/5 space-y-2 mb-6 text-sm shadow-inner">
          <div className="flex justify-between">
            <span className="text-gray-400">매도 금액</span>
            <span className="text-white font-medium">{estimatedTotal.toLocaleString()} 원</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">예상 수수료 + 세금</span>
            <span className="text-gray-500">{(commission + tax).toLocaleString()} 원</span>
          </div>
          <div className="border-t border-white/10 pt-3 flex justify-between items-center mt-2">
            <span className="text-blue-400 font-bold">정산 예상 금액</span>
            <span className="text-blue-400 font-bold text-lg">{finalReceive.toLocaleString()} 원</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3.5 bg-white/5 hover:bg-white/10 text-gray-300 rounded-xl font-bold transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || isInvalid}
            className={`flex-1 py-3.5 rounded-xl font-bold text-white transition-all flex items-center justify-center gap-2 ${isSubmitting || isInvalid
              ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
              : 'bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-400 hover:to-indigo-500 shadow-lg shadow-blue-900/20 scale-[1.02] active:scale-100'
              }`}
          >
            {isSubmitting ? <i className="fas fa-spinner fa-spin"></i> : '매도 주문'}
          </button>
        </div>
      </div>
    </div>
  );
}
