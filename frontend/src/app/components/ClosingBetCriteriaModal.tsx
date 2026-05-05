'use client';

import React from 'react';
import Modal from './Modal';

interface ClosingBetCriteriaModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ClosingBetCriteriaModal({ isOpen, onClose }: ClosingBetCriteriaModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="종가베팅 점수 산정 기준표 (19점 만점)"
      maxWidth="max-w-2xl"
    >
      <div className="space-y-6">
        <div className="bg-indigo-500/10 border border-indigo-500/20 p-4 rounded-xl text-sm text-indigo-200">
          <p className="mb-2">
            <strong>종가베팅 점수란?</strong>
          </p>
          뉴스/거래대금/차트/수급/캔들/조정 6개 항목(기본 12점)과 가산점 7점을 합산한 <strong>19점 만점</strong>의 점수입니다.
          <br />
          <span className="text-amber-300">
            ※ VCP 시그널의 100점 만점 점수와는 다른 별개의 시스템입니다.
          </span>
        </div>

        <div className="space-y-4">
          {/* 기본 점수 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">기본 점수 (Max 12점)</h4>
              <span className="text-xs font-bold bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded">12점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                <li><span className="text-emerald-400 font-bold">뉴스 점수</span> (3점): 최근 3일 호재 강도 (LLM 평가) + 거래대금 폴백</li>
                <li><span className="text-emerald-400 font-bold">거래대금 점수</span> (3점): 1조(3) / 5천억(2) / 1천억(1)</li>
                <li><span className="text-emerald-400 font-bold">차트 점수</span> (2점): 신고가 1점 + 이평선 정배열 1점</li>
                <li><span className="text-emerald-400 font-bold">수급 점수</span> (2점): 외인+기관 5일 합 / 거래대금 비율</li>
                <li><span className="text-emerald-400 font-bold">캔들 점수</span> (1점): 장대양봉 + 윗꼬리 관리</li>
                <li><span className="text-emerald-400 font-bold">조정 점수</span> (1점): 볼린저밴드 수축 + 기간조정 후 돌파</li>
              </ul>
            </div>
          </div>

          {/* 가산점 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">가산점 (Max 7점)</h4>
              <span className="text-xs font-bold bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded">7점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                <li><span className="text-blue-400 font-bold">거래량 급증</span> (최대 5점): 평균 대비 6배 이상 5점 ~ 2배 이상 1점</li>
                <li><span className="text-blue-400 font-bold">장대양봉</span> (최대 1점): 차트 점수 1 이상 시 가산</li>
                <li><span className="text-blue-400 font-bold">상한가</span> (최대 1점): 당일 상한가 도달 시 가산</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="text-xs text-gray-500 text-center pt-2">
          * <strong>8점 이상</strong>이 강력 매수 신호이며, 등급 산정(S/A/B/C/D)은 점수 + 추가 조건(거래대금/등락률 등)을 종합하여 결정됩니다.
        </div>
      </div>
    </Modal>
  );
}
