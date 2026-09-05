'use client';

import Modal from './Modal';

// [JONGGA-006] 종가베팅 등급 기준표. 종가베팅 고유 로직을 담지 않은 정적 마크업이라
// 페이지 본체에서 떼어냈다. 성격이 같은 ClosingBetCriteriaModal 이 이미 이 자리에 있다.
//
// 근거: AUDIT-JONGGA §4.1
export default function GradeGuideModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  // 모달이 닫혀있으면 렌더링하지 않음 (Modal 컴포넌트 내부에서 처리하지만, content 생성을 막기 위해)
  // 단, 애니메이션을 위해 Modal 컴포넌트에 위임

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="종가베팅 등급 산정 기준" type="default" wide>
      <div className="space-y-8 max-h-[70vh] overflow-y-auto pr-2">

        {/* Unified Grade Logic */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-indigo-500/30 pb-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <i className="fas fa-list-ol text-indigo-400"></i>
              통합 등급 산정 기준
            </h3>
            <span className="text-xs text-slate-500">※ 외인+기관 동반 매수 필수</span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full text-xs text-left min-w-[600px] border-collapse">
              <thead className="bg-white/5 text-slate-400 font-medium">
                <tr>
                  <th className="px-4 py-3 w-16 text-center whitespace-nowrap">등급</th>
                  <th className="px-4 py-3 whitespace-nowrap">거래대금 기준</th>
                  <th className="px-4 py-3 whitespace-nowrap">점수 (Total / 19)</th>
                  <th className="px-4 py-3 whitespace-nowrap">추가 조건</th>
                  <th className="px-4 py-3 whitespace-nowrap">비고</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                <tr className="bg-indigo-500/5 hover:bg-indigo-500/10 transition-colors">
                  <td className="px-4 py-3 font-bold text-indigo-400 text-center text-sm whitespace-nowrap">S 급</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="text-indigo-300 font-bold">1조 원 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white whitespace-nowrap">10점 이상</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                    <div className="text-emerald-400">외인+기관 양매수</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">초대형 수급 폭발</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-rose-400 text-center text-sm whitespace-nowrap">A 급</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="text-rose-300 font-bold">5,000억 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white whitespace-nowrap">8점 이상</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                    <div className="text-emerald-400">외인+기관 양매수</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">대형 우량주</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-blue-400 text-center text-sm whitespace-nowrap">B 급</td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <span className="text-blue-300 font-bold">1,000억 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white whitespace-nowrap">6점 이상</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                    <div className="text-emerald-400">외인+기관 양매수</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">중형 주도주</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-base font-bold text-white flex items-center gap-2 border-b border-indigo-500/30 pb-2">
            <span className="px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded text-xs">2</span>
            핵심 평가 요소 (Score 19점 만점)
          </h3>
          <p className="text-xs text-gray-400">
            기본 점수(12점)와 가산점(7점)으로 구성됩니다.
          </p>

          <div className="space-y-4">
            {/* 기본 점수 섹션 */}
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="text-xs font-bold text-indigo-400 mb-3 flex items-center gap-2">
                <i className="fas fa-check-circle"></i> 기본 배점 항목 (Max 12점)
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>📰 뉴스/재료</span>
                    <span className="text-indigo-400 font-mono">3점</span>
                  </div>
                  <div className="text-[10px] text-gray-500 space-y-1">
                    <div>LLM 뉴스 점수: 0~3점(최대 3점)</div>
                    <div>신규 뉴스 부재 시 거래대금 보정 적용</div>
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>💰 거래대금</span>
                    <span className="text-indigo-400 font-mono">3점</span>
                  </div>
                  <div className="text-[10px] text-gray-500 space-y-1">
                    <div>1조원 이상: 3점</div>
                    <div>5,000억 이상: 2점</div>
                    <div>1,000억 이상: 1점</div>
                  </div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>📈 차트</span>
                    <span className="text-indigo-400 font-mono">2점</span>
                  </div>
                  <div className="text-[10px] text-gray-500 space-y-1">
                    <div>52주 신고가 돌파: +1점</div>
                    <div>MA20&gt;MA60 &amp; 종가&gt;MA20: +1점</div>
                  </div>
                </div>
                  <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                    <div className="flex justify-between items-center text-xs font-bold text-white">
                      <span>🤝 수급</span>
                      <span className="text-indigo-400 font-mono">2점</span>
                    </div>
                    <div className="text-[10px] text-gray-500">외인+기관 5일 순매수 합계 (거래대금 대비 5%/10%)</div>
                  </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>🕯 캔들</span>
                    <span className="text-indigo-400 font-mono">1점</span>
                  </div>
                  <div className="text-[10px] text-gray-500">장대양봉 및 꼬리 관리</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>⏳ 기간조정</span>
                    <span className="text-indigo-400 font-mono">1점</span>
                  </div>
                  <div className="text-[10px] text-gray-500">변동성 및 이격 수축</div>
                </div>
              </div>
            </div>

            {/* 가산점 섹션 */}
                <div className="bg-indigo-500/5 rounded-xl p-4 border border-indigo-500/20">
                  <h4 className="text-xs font-bold text-emerald-400 mb-3 flex items-center gap-2">
                    <i className="fas fa-plus-circle"></i> 가산점 항목 (Max 7점)
                  </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>📊 거래량 급증</span>
                    <span className="text-emerald-400 font-mono">+5점</span>
                  </div>
                  <div className="text-[10px] text-gray-500">2배(1점), 3배(2점), 4배(3점), 5배(4점), 6배 이상(5점)</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>📈 장대양봉</span>
                    <span className="text-emerald-400 font-mono">+1점</span>
                  </div>
                  <div className="text-[10px] text-gray-500">상승폭이 큰 장대양봉 마감</div>
                </div>
                <div className="bg-slate-800/50 rounded-lg p-2.5 border border-white/5 flex flex-col gap-1">
                  <div className="flex justify-between items-center text-xs font-bold text-white">
                    <span>🧯 상한가</span>
                    <span className="text-emerald-400 font-mono">+1점</span>
                  </div>
                  <div className="text-[10px] text-gray-500">상한가(거래일 등락률) 돌파 시</div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </Modal >
  );
}
