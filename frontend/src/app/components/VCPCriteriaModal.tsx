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
            <strong>VCP (Volatility Contraction Pattern) 점수란?</strong>
          </p>
          주가의 변동성이 줄어들며 에너지가 응축되는 과정을 정량화한 지표(<strong>100점 만점</strong>)입니다.
          <br />
          <span className="text-amber-300">
            ※ 종가베팅 점수(19점 만점)와는 별개의 시스템입니다. 종가베팅 점수표는 종가베팅 페이지에서 확인하세요.
          </span>
        </div>

        <div className="space-y-4">
          {/* 1. 변동성 축소 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">1. 변동성 축소 (Range Contraction)</h4>
              <span className="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded">40점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>최근 5일간의 고가-저가 폭이 직전 15일 평균 대비 얼마나 줄어들었는지 평가합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-emerald-400 font-bold">40점</span> : 비율 ≤ 0.5 (매우 강한 수축)</li>
                <li><span className="text-blue-400 font-bold">30점</span> : 비율 ≤ 0.7 (건전한 수축)</li>
                <li><span className="text-yellow-400 font-bold">15점</span> : 비율 ≤ 0.9 (약한 수축)</li>
              </ul>
              <p className="text-[11px] text-gray-500 mt-2">
                ※ <span className="text-amber-300">VCP 인정 조건</span>: 비율 ≤ 0.7 <span className="text-gray-600">AND</span> 총점 ≥ 50점 <span className="text-gray-600">AND</span> 현재가 ≥ 최근 고가의 85%
              </p>
            </div>
          </div>

          {/* 2. 거래량 급감 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">2. 거래량 급감 (Volume Dry-up)</h4>
              <span className="text-xs font-bold bg-rose-500/20 text-rose-400 px-2 py-0.5 rounded">30점</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>최근 5일 평균 거래량이 직전 15일 평균 대비 얼마나 줄어들었는지(매물 소화) 평가합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-emerald-400 font-bold">30점</span> : 비율 ≤ 0.5 (강한 드라이업)</li>
                <li><span className="text-blue-400 font-bold">20점</span> : 비율 ≤ 0.7 (수축)</li>
                <li><span className="text-yellow-400 font-bold">10점</span> : 비율 ≤ 0.9 (소폭 감소)</li>
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

          {/* AI 분석 보강 */}
          <div className="border border-white/10 rounded-xl overflow-hidden">
            <div className="bg-white/5 px-4 py-2 border-b border-white/10 flex justify-between items-center">
              <h4 className="font-bold text-white">+ Multi-AI 추천 (Gemini 우선 · GPT/Perplexity 보조)</h4>
              <span className="text-xs font-bold bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">보조 검증</span>
            </div>
            <div className="p-4 space-y-2 text-sm text-gray-400">
              <p>VCP 1차 통과 종목에 대해 <span className="text-indigo-400">Gemini</span>가 1차 추론을 수행하고, 환경 설정(<code className="text-gray-400">VCP_AI_PROVIDERS</code>)에 따라 <span className="text-sky-400">GPT</span> 또는 <span className="text-green-400">Perplexity</span>가 보조 검증해 매매 추천(BUY/HOLD/SELL)과 신뢰도를 산출합니다.</p>
              <ul className="list-disc list-inside space-y-1 mt-2 text-gray-300">
                <li><span className="text-indigo-400 font-bold">Gemini (Vertex AI)</span>: 1차 추론 (심층 추론·긴 컨텍스트, 기본 활성)</li>
                <li><span className="text-sky-400 font-bold">GPT</span>: 빠른 보조 검증 (Z.ai fallback 지원, 기본 활성)</li>
                <li><span className="text-green-400 font-bold">Perplexity</span>: 실시간 웹 검색 기반 검증 (옵션, env 설정 시 활성)</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="text-xs text-gray-500 text-center pt-2">
          * 점수가 높을수록 에너지가 잘 응축되었음을 의미하며, <strong>50점 이상 + 수축비율 ≤ 0.7</strong>을 모두 만족할 때 의미 있는 VCP 패턴으로 간주합니다.
        </div>
      </div>
    </Modal>
  );
}
