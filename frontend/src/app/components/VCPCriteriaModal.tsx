'use client';

import React from 'react';
import Modal from './Modal';

interface VCPCriteriaModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function VCPCriteriaModal({ isOpen, onClose }: VCPCriteriaModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="VCP 점수 산정 기준표 (100점 만점)"
      maxWidth="max-w-2xl"
    >
      <div className="space-y-6">
        <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-xl text-sm text-blue-200">
          <p className="mb-2">
            <strong>💡 VCP (Volatility Contraction Pattern) 점수란?</strong>
          </p>
          주가의 변동성이 줄어들며 에너지가 응축되는 과정을 정량화한 지표입니다.
          <br />
          종가베팅과 VCP 시그널 모두 <strong>동일한 로직</strong>으로 계산됩니다.
        </div>

        <div className="space-y-4">
          {/* 1. 변동성 축소 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">1. 변동성 축소 (Range Contraction)</h4>
              <span className="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded">40점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>최근 5일간의 고가-저가 폭이 20일 평균 대비 얼마나 줄어들었는지 평가합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-emerald-400 font-bold">40점</span> : 비율 &lt; 0.5 (매우 좋음)</li>
                <li><span className="text-blue-400 font-bold">30점</span> : 비율 &lt; 0.6 (좋음)</li>
                <li><span className="text-yellow-400 font-bold">15점</span> : 비율 &lt; 0.7 (보통)</li>
              </ul>
            </div>
          </div>

          {/* 2. 거래량 급감 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">2. 거래량 급감 (Volume Dry-up)</h4>
              <span className="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded">30점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>최근 5일 거래량이 20일 평균 대비 얼마나 줄어들었는지(매물 소화) 평가합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-emerald-400 font-bold">30점</span> : 비율 &lt; 0.5 (매우 좋음)</li>
                <li><span className="text-blue-400 font-bold">20점</span> : 비율 &lt; 0.7 (좋음)</li>
                <li><span className="text-yellow-400 font-bold">10점</span> : 비율 &lt; 0.9 (보통)</li>
              </ul>
            </div>
          </div>

          {/* 3. 이평선 정배열 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">3. 이동평균선 정배열 (Trend)</h4>
              <span className="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded">30점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>현재 주가와 이동평균선(5일, 20일)의 위치 관계를 평가합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-emerald-400 font-bold">30점</span> : 주가 &gt; 5일선 &gt; 20일선 (완벽한 정배열)</li>
                <li><span className="text-blue-400 font-bold">15점</span> : 주가 &gt; 20일선 (상승 추세 유지)</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="text-xs text-gray-500 text-center pt-2">
          * 점수가 높을수록 에너지가 잘 응축되었음을 의미하며, <strong>50점 이상</strong>일 때 의미 있는 패턴으로 간주합니다.
        </div>
      </div>
    </Modal>
  );
}
