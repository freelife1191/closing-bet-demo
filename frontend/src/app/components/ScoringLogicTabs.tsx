'use client';

import { useState, type ReactNode } from 'react';

interface ScoringLogicTabsProps {
  vcp: ReactNode;
  supply: ReactNode;
  closing: ReactNode;
}

/**
 * 랜딩 페이지의 「Scoring Logic Detail」 탭이다. 종전에는 이 탭 상태 하나 때문에
 * 페이지 713줄 전체에 `'use client'` 가 붙어 클라이언트 번들로 실려 나갔다.
 *
 * 세 패널을 프롭으로 받는 이유가 여기에 있다. 프롭이나 children 으로 넘어온 서버
 * 컴포넌트는 클라이언트의 모듈 그래프에 들어가지 않고 서버에서 그린 결과만 전달되므로
 * (`node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`),
 * 정적 마크업 340여 줄이 번들 밖에 남는다. 이 파일 안에서 직접 import 하면 그 효과가
 * 사라진다.
 */
export default function ScoringLogicTabs({ vcp, supply, closing }: ScoringLogicTabsProps) {
  const [activeTab, setActiveTab] = useState<'vcp' | 'supply' | 'closing'>('closing');

  return (
    <>
      <div className="inline-flex p-1 rounded-xl bg-[#1c1c1e] border border-white/10 mb-12">
        <button
          onClick={() => setActiveTab('vcp')}
          className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'vcp' ? 'bg-[#2c2c2e] text-white shadow-lg' : 'text-gray-500 hover:text-gray-300'}`}
        >
          VCP 분석
        </button>
        <button
          onClick={() => setActiveTab('supply')}
          className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'supply' ? 'bg-[#2c2c2e] text-white shadow-lg' : 'text-gray-500 hover:text-gray-300'}`}
        >
          수급 점수
        </button>
        <button
          onClick={() => setActiveTab('closing')}
          className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'closing' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25' : 'text-gray-500 hover:text-gray-300'}`}
        >
          종가베팅
        </button>
      </div>

      <div className="bg-[#13151A] rounded-3xl border border-white/5 p-8 md:p-12 text-left relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-[80px] pointer-events-none"></div>

        {activeTab === 'closing' && closing}
        {activeTab === 'vcp' && vcp}
        {activeTab === 'supply' && supply}
      </div>
    </>
  );
}
