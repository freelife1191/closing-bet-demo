'use client';

import { useState } from 'react';
import { paperTradingAPI } from '@/lib/api';
import { CaptureAccountAction } from '@/lib/accountActionGuard';
import ConfirmationModal from './ConfirmationModal';

const MAX_DEPOSIT_PER_TX = 1_000_000_000_000; // 1조원

// 충전 팝오버의 가산 버튼이다. 금액만 다른 코드가 세 벌이었다.
const DEPOSIT_STEPS: ReadonlyArray<readonly [number, string]> = [
  [1_000_000, '+100만'],
  [10_000_000, '+1천만'],
  [100_000_000, '+1억'],
];

interface DepositPanelProps {
  cash: number;
  captureAccountAction: CaptureAccountAction;
  /** 충전이 끝났음을 모달 본체에 알린다. 본체가 포트폴리오를 다시 받는다. */
  onDeposited: () => void;
}

/** 모의투자 모달 머리의 예수금 표시와 충전 팝오버다. */
export function DepositPanel({ cash, captureAccountAction, onDeposited }: DepositPanelProps) {
  const [showDeposit, setShowDeposit] = useState(false);
  const [depositAmount, setDepositAmount] = useState('10000000'); // 기본 1000만원

  const handleDeposit = async () => {
    const isCurrent = captureAccountAction();
    const amt = parseInt(depositAmount.replace(/,/g, ''), 10);
    if (!amt || amt <= 0) return;
    if (amt > MAX_DEPOSIT_PER_TX) {
      alert('1회 최대 입금 한도(1조원)를 초과했습니다.');
      return;
    }
    try {
      await paperTradingAPI.deposit(amt);
      if (!isCurrent()) return;
      alert(`${amt.toLocaleString()}원이 충전되었습니다.`);
      setShowDeposit(false);
      onDeposited();
    } catch (e: any) {
      if (!isCurrent()) return;
      alert(e.message);
    }
  };

  return (
    <div className="text-right group relative">
      <div className="text-[10px] md:text-xs text-gray-500 flex items-center justify-end gap-1">
        예수금
        <button onClick={() => setShowDeposit(!showDeposit)} className="w-4 h-4 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500 hover:text-white flex items-center justify-center text-[10px] transition-colors">+</button>
      </div>
      <div className="text-sm md:text-base font-bold text-blue-400 whitespace-nowrap">{Math.floor(cash).toLocaleString()}원</div>

      {/* Deposit Popover */}
      {showDeposit && (
        <div className="absolute top-full right-0 mt-2 w-60 bg-[#2c2c2e] border border-white/10 rounded-lg shadow-xl p-3 z-50">
          <div className="flex justify-between items-center mb-2">
            <div className="text-xs text-white font-bold">예수금 충전</div>
            <button onClick={() => setShowDeposit(false)} className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-white/10 text-gray-400 hover:text-white transition-colors">
              <i className="fas fa-times text-xs"></i>
            </button>
          </div>
          <input
            type="text"
            className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-right text-sm text-white mb-2"
            value={depositAmount}
            onChange={e => {
              // 숫자와 콤마만 허용
              const val = e.target.value.replace(/[^0-9]/g, '');
              setDepositAmount(val ? parseInt(val, 10).toLocaleString() : '');
            }}
          />
          <div className="grid grid-cols-3 gap-1 mb-2">
            {DEPOSIT_STEPS.map(([step, label]) => (
              <button
                key={label}
                onClick={() => {
                  const current = parseInt(depositAmount.replace(/,/g, '') || '0', 10);
                  setDepositAmount((current + step).toLocaleString());
                }}
                className="px-1 py-1.5 bg-white/5 hover:bg-white/10 text-[10px] text-gray-300 hover:text-white rounded transition-colors"
              >
                {label}
              </button>
            ))}
          </div>
          <button onClick={handleDeposit} className="w-full py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded font-bold transition-colors">충전하기</button>
        </div>
      )}
    </div>
  );
}

interface ResetAccountButtonProps {
  captureAccountAction: CaptureAccountAction;
  /** 초기화가 끝났음을 모달 본체에 알린다. */
  onReset: () => void;
}

/** 계정 초기화 버튼과 그 확인 대화상자다. 되돌릴 수 없는 조작이라 확인을 한 번 받는다. */
export function ResetAccountButton({ captureAccountAction, onReset }: ResetAccountButtonProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleConfirm = async () => {
    const isCurrent = captureAccountAction();
    try {
      await paperTradingAPI.reset();
      if (!isCurrent()) return;
      setConfirmOpen(false);
      onReset();
    } catch (e) {
      if (!isCurrent()) return;
      alert('초기화 실패');
    }
  };

  return (
    <>
      <div className="mt-8 pt-6 border-t border-white/5 flex justify-end">
        <button
          onClick={() => setConfirmOpen(true)}
          className="px-4 py-2 rounded-lg text-sm text-gray-500 hover:text-rose-400 hover:bg-rose-500/5 transition-colors flex items-center gap-2"
        >
          <i className="fas fa-trash-alt"></i>
          계정 초기화
        </button>
      </div>
      <ConfirmationModal
        isOpen={confirmOpen}
        title="모의투자 초기화"
        message={`정말로 초기화하시겠습니까?\n모든 거래 내역과 자산이 삭제되며, 이 작업은 되돌릴 수 없습니다.`}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmOpen(false)}
        confirmText="초기화"
        cancelText="취소"
      />
    </>
  );
}
