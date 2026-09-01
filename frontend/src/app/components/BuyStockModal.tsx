'use client';

import { useState, useEffect } from 'react';
import { paperTradingAPI } from '@/lib/api';

interface BuyStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: {
    ticker: string;
    name: string;
    price: number;
    current_price?: number;
    entry_price?: number;
  } | null;
  onBuy: (ticker: string, name: string, price: number, quantity: number) => Promise<boolean>;
}

export default function BuyStockModal({ isOpen, onClose, stock, onBuy }: BuyStockModalProps) {
  const [mode, setMode] = useState<'quantity' | 'amount'>('quantity');
  const [quantity, setQuantity] = useState<string>('0');
  const [amount, setAmount] = useState<string>('0');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [fetchedPrice, setFetchedPrice] = useState<number | null>(null);
  const [loadingPrice, setLoadingPrice] = useState(false);

  // 포트폴리오(예수금) 조회 및 실시간 가격 조회
  useEffect(() => {
    if (isOpen && stock) {
      paperTradingAPI.getPortfolio().then(setPortfolio).catch(console.error);
      setQuantity('0');
      setAmount('0');

      // 실시간 가격 조회
      setLoadingPrice(true);
      fetch('/api/kr/realtime-prices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: [stock.ticker] })
      })
        .then(res => res.json())
        .then(data => {
          if (data.prices && data.prices[stock.ticker]) {
            setFetchedPrice(data.prices[stock.ticker]);
          } else if (data[stock.ticker]) {
            // Fallback for any legacy format (though backend is updated)
            setFetchedPrice(data[stock.ticker]);
          }
        })
        .catch(console.error)
        .finally(() => setLoadingPrice(false));
    } else {
      setFetchedPrice(null);
    }
  }, [isOpen, stock]);

  if (!stock) return null;

  const price = fetchedPrice || stock.current_price || stock.entry_price || stock.price || 0;
  const numericQty = parseInt(quantity.replace(/,/g, ''), 10) || 0;
  const numericAmount = parseInt(amount.replace(/,/g, ''), 10) || 0;

  // 계산
  const estimatedQty = mode === 'quantity' ? numericQty : (price > 0 ? Math.floor(numericAmount / price) : 0);
  // 실제 체결 금액 (주 단위 절삭 반영). 백엔드는 가격 × 수량만 차감하므로
  // 수수료를 화면에서만 얹으면 안내 금액이 실제 정산액과 어긋난다.
  const finalCost = estimatedQty * price;

  const cash = portfolio ? portfolio.cash : 0;
  // 가격을 못 받아 온 상태에서 나누면 Infinity 가 되어 `가능: ∞주` 로 표시된다.
  const maxBuyableQty = price > 0 ? Math.floor(cash / price) : 0;
  const isInsufficient = finalCost > cash;

  const handleSubmit = async () => {
    if (isSubmitting || estimatedQty <= 0) return;
    if (isInsufficient) return;

    setIsSubmitting(true);
    try {
      const success = await onBuy(stock.ticker, stock.name, price, estimatedQty);
      if (success) onClose();
    } catch (e) {
      console.error('[BuyStockModal] Error:', e);
      alert('매수 실패: ' + e);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 최대 매수 버튼
  const handleMax = () => {
    if (mode === 'quantity') {
      setQuantity(maxBuyableQty.toString());
    } else {
      setAmount(cash.toString());
    }
  };

  const handleAdjust = (delta: number) => {
    if (mode === 'quantity') {
      const currentQty = parseInt(quantity.replace(/[^0-9]/g, ''), 10) || 0;
      const newVal = Math.max(0, Math.min(maxBuyableQty, currentQty + delta));
      setQuantity(newVal.toString());
    } else {
      // 금액 모드에서는 1주 가격만큼 증감한다. 가격을 못 받아 온 동안에는 1만 원 단위로 움직인다.
      const currentAmount = parseInt(amount.replace(/[^0-9]/g, ''), 10) || 0;
      const step = price > 0 ? price : 10000;
      const newVal = Math.max(0, Math.min(cash, currentAmount + (delta * step)));
      setAmount(newVal.toString());
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#1c1c1e] w-full max-w-md rounded-2xl border border-white/10 shadow-2xl p-6 animate-in fade-in zoom-in-95 duration-200">

        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">모의 투자 매수</h2>
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
          <div className="flex flex-col">
            <span className="text-gray-400 text-sm flex items-center gap-2">
              현재가 (매수가)
              {loadingPrice && <i className="fas fa-circle-notch fa-spin text-xs text-blue-500"></i>}
            </span>
            {fetchedPrice ? (
              <span className="text-[10px] text-green-400 font-bold flex items-center gap-1 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                실시간 시세 적용
              </span>
            ) : (
              <span className="text-[10px] text-yellow-500 font-bold mt-0.5">
                ⚠ 진입가/기본가 적용
              </span>
            )}
          </div>
          <span className={`text-2xl font-bold ${loadingPrice ? 'opacity-50' : 'text-rose-400'} transition-opacity`}>
            {price.toLocaleString()}원
          </span>
        </div>

        {/* Mode Tabs */}
        <div className="flex p-1 bg-black/40 rounded-lg mb-4 border border-white/5">
          <button
            onClick={() => { setMode('quantity'); setQuantity('0'); setAmount('0'); }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${mode === 'quantity' ? 'bg-[#3f3f46] text-white shadow-sm' : 'text-gray-400 hover:text-white'
              }`}
          >
            수량 매수
          </button>
          <button
            onClick={() => { setMode('amount'); setAmount('0'); setQuantity('0'); }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${mode === 'amount' ? 'bg-[#3f3f46] text-white shadow-sm' : 'text-gray-400 hover:text-white'
              }`}
          >
            금액 매수
          </button>
        </div>

        {/* Input */}
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-500 mb-2">
            {mode === 'quantity' ? '구매 수량 (주)' : '구매 금액 (원)'}
            <span className="float-right text-gray-600 font-normal">
              가능: {portfolio ? maxBuyableQty.toLocaleString() : '-'}주
            </span>
          </label>

          <div className="relative">
            <input
              type="text"
              className={`w-full bg-[#18181b] border border-white/10 rounded-xl pl-12 pr-16 py-3 text-right text-lg font-bold text-white focus:outline-none focus:border-blue-500 transition-colors ${isInsufficient ? 'border-red-500/50 focus:border-red-500' : ''}`}
              value={mode === 'quantity' ? quantity : parseInt(amount).toLocaleString()}
              placeholder="0"
              onChange={(e) => {
                const val = e.target.value.replace(/[^0-9]/g, '');
                if (mode === 'quantity') setQuantity(val || '0');
                else setAmount(val || '0');
              }}
            />
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 text-sm font-medium">
              {mode === 'quantity' ? 'QTY' : 'KRW'}
            </span>
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
            <button onClick={() => handleAdjust(10)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400 text-xs">{mode === 'quantity' ? '+10주' : '+10단위'}</button>
            <button onClick={() => handleAdjust(100)} className="px-3 py-1 bg-white/5 rounded hover:bg-white/10 text-gray-400 text-xs">{mode === 'quantity' ? '+100주' : '+100단위'}</button>
          </div>
          {isInsufficient && (
            <div className="text-red-400 text-xs mt-2 flex items-center gap-1 animate-pulse">
              <i className="fas fa-exclamation-circle"></i>
              예수금이 부족합니다 (부족: {(finalCost - cash).toLocaleString()}원)
            </div>
          )}
        </div>

        {/* Summary */}
        <div className="bg-[#18181b] rounded-xl p-4 border border-white/5 space-y-2 mb-6 text-sm shadow-inner">
          <div className="flex justify-between">
            <span className="text-gray-400">주문 수량</span>
            <span className="text-white font-medium">{estimatedQty.toLocaleString()} 주</span>
          </div>
          <div className="border-t border-white/10 pt-3 flex justify-between items-center mt-2">
            <span className="text-rose-400 font-bold">결제 금액</span>
            <span className="text-rose-400 font-bold text-lg">{finalCost.toLocaleString()} 원</span>
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
            disabled={isSubmitting || estimatedQty <= 0 || isInsufficient}
            className={`flex-1 py-3.5 rounded-xl font-bold text-white transition-all flex items-center justify-center gap-2 ${isSubmitting || estimatedQty <= 0 || isInsufficient
              ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
              : 'bg-gradient-to-r from-rose-500 to-pink-600 hover:from-rose-400 hover:to-pink-500 shadow-lg shadow-rose-900/20 scale-[1.02] active:scale-100'
              }`}
          >
            {isSubmitting ? <i className="fas fa-spinner fa-spin"></i> : '매수 주문'}
          </button>
        </div>
      </div>
    </div>
  );
}
