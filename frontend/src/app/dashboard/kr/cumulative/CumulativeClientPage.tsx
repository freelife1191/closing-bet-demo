'use client';

import React, { useState } from 'react';
import Modal from '@/app/components/Modal';
import Tooltip from '@/app/components/Tooltip';

// Revised Interface matching API response
interface Trade {
  id: string;
  date: string;
  grade: string;
  name: string;
  code: string;
  market: string;
  entry: number;
  outcome: string;
  roi: number;
  maxHigh: number;
  priceTrail: number[];
  days: number;
  score: number;
  themes: string[];
}

interface GradeRoiData {
  count: number;
  avgRoi: number;
  totalRoi: number;
}

interface KPIData {
  totalSignals: number;
  winRate: number;
  wins: number;
  losses: number;
  open: number;
  avgRoi: number;
  totalRoi: number;
  roiByGrade: {
    S: GradeRoiData;
    A: GradeRoiData;
    B: GradeRoiData;
  };
  avgDays: number;
  priceDate: string;
  profitFactor: number;
}

// ----------------------------------------------------------------------
// 1. TOOLTIP CONTENT DEFINITIONS
// ----------------------------------------------------------------------
const TOOLTIP_CONTENT = {
  // --- Header Stats ---
  totalSignals: {
    title: "누적 추천수 (Total Signals)",
    desc: "AI 알고리즘이 발굴한 전체 매매 신호의 총 횟수입니다.",
    criteria: "전체 기간 동안 발생한 모든 매수 신호 포함",
    interpretation: "시장 상황에 따라 신호 발생 빈도가 달라질 수 있으며, 신호가 많다고 무조건 좋은 것은 아닙니다."
  },
  winRate: {
    title: "승률 (Win Rate)",
    desc: "전체 청산된 매매 중 익절 목표(+9%)에 도달한 비율입니다.",
    criteria: "익절 +9% 성공 / (익절 + 손절) * 100",
    interpretation: "승률 40% 이상이면 손익비 1.5:1 구조에서 꾸준한 우상향 수익이 가능합니다."
  },
  wins: {
    title: "성공 횟수 (Wins)",
    desc: "매수 후 목표 수익률(+9%)에 도달하여 이익 실현한 횟수입니다.",
    criteria: "고가가 진입가 대비 +9% 이상 도달 시 성공 처리",
    interpretation: "성공 횟수가 많을수록 계좌 수익금이 누적됩니다."
  },
  losses: {
    title: "실패 횟수 (Losses)",
    desc: "매수 후 손절 기준(-5%)을 이탈하여 손실 확정한 횟수입니다.",
    criteria: "저가가 진입가 대비 -5% 이하 하락 시 실패 처리",
    interpretation: "실패는 피할 수 없으며, 손실을 -5%로 제한하는 것이 핵심입니다."
  },
  open: {
    title: "보유중 (Open Positions)",
    desc: "현재 매수 후 아직 익절이나 손절 기준에 도달하지 않은 종목입니다.",
    criteria: "최대 15일 보유 기간 내 진행 중인 종목",
    interpretation: "보유 종목이 많을 때는 시장 리스크 관리에 유의해야 합니다."
  },
  avgRoi: {
    title: "평균 수익률 (Average ROI)",
    desc: "S/A/B 등급별 평균 수익률을 동시에 보여줍니다.",
    criteria: "각 등급별 (등급 총 수익률 합계) / (등급 매매 수)",
    interpretation: "S/A/B의 평균 수익률을 비교해 어떤 등급이 실제 수익에 기여하는지 확인할 수 있습니다."
  },
  totalRoi: {
    title: "누적 수익률 (Total ROI)",
    desc: "S/A/B 등급별 누적 수익률을 동시에 보여줍니다.",
    criteria: "각 등급의 개별 매매 수익률 단순 합산",
    interpretation: "S/A/B별 누적 수익률을 비교하면 전체 성과에서 등급별 기여도를 명확하게 볼 수 있습니다."
  },
  avgDays: {
    title: "평균 보유일 (Average Days)",
    desc: "매수 진입부터 청산(익절/손절)까지 걸린 평균 기간입니다.",
    criteria: "영업일(Trading Days) 기준",
    interpretation: "짧을수록 자금 회전율이 높아 복리 효과를 극대화할 수 있습니다. (목표: 3~5일)"
  },
  profitFactor: {
    title: "손익비 (Profit Factor)",
    desc: "총 이익금을 총 손실금으로 나눈 비율로, 전략의 효율성을 나타냅니다.",
    criteria: "(총 이익금 합계) / (총 손실금 합계의 절대값)",
    interpretation: "1.5 이상이면 훌륭한 전략이며, 2.0 이상이면 매우 강력한 수익 모델입니다."
  },

  // --- Grades ---
  gradeS: {
    title: "S등급 (Super) 성과",
    desc: "초대형 주도주(거래대금 1조↑, 점수 10점↑)에 대한 매매 성과입니다.",
    criteria: "가장 강력한 수급과 상승 모멘텀을 가진 종목군",
    interpretation: "시장 주도주로 승률이 가장 안정적이어야 하는 등급입니다."
  },
  gradeA: {
    title: "A등급 (Ace) 성과",
    desc: "대형 주도주(거래대금 5천억↑, 점수 8점↑)에 대한 매매 성과입니다.",
    criteria: "확실한 재료와 수급이 받쳐주는 종목군",
    interpretation: "가장 많은 매매 기회가 발생하며 수익의 허리를 담당합니다."
  },
  gradeB: {
    title: "B등급 (Basic) 성과",
    desc: "중형 수급주(거래대금 1천억↑, 점수 6점↑)에 대한 매매 성과입니다.",
    criteria: "테마의 2등주나 개별 호재주가 포함될 수 있음",
    interpretation: "변동성이 클 수 있어 선별적인 접근이 필요합니다."
  },
  // --- Distribution ---
  distribution: {
    title: "승패 분포 (Win/Loss Distribution)",
    desc: "전체 매매의 결과가 어떻게 분포되어 있는지 시각적으로 보여줍니다.",
    criteria: "성공(익절) / 보유(진행중) / 실패(손절)",
    interpretation: "녹색(성공) 영역이 붉은색(실패) 영역보다 넓어야 건전한 전략입니다."
  },

  // --- Table Headers ---
  table_date: {
    title: "추천일 (Date)",
    desc: "AI가 종가베팅 시그널을 발생시킨 날짜입니다.",
    criteria: "장 마감(15:20) 전후 데이터 분석 기준",
    interpretation: "해당 날짜의 종가 부근에서 매수 진입을 권장합니다."
  },
  table_grade: {
    title: "등급 (Grade)",
    desc: "AI가 분석한 종목의 상승 잠재력 등급입니다.",
    criteria: "S > A > B 순으로 강력함",
    interpretation: "등급이 높을수록 성공 확률과 기대 수익률이 높은 경향이 있습니다."
  },
  table_entry: {
    title: "진입가 (Entry Price)",
    desc: "추천일의 종가(Close Price)를 기준으로 한 매수 가격입니다.",
    criteria: "실제 체결가는 ±1~2호가 차이가 있을 수 있음",
    interpretation: "이 가격을 기준으로 +9% 익절, -5% 손절 라인이 설정됩니다."
  },
  table_result: {
    title: "결과 (Outcome)",
    desc: "매매가 현재 어떤 상태인지 나타냅니다.",
    criteria: "성공(WIN), 실패(LOSS), 보유(OPEN)",
    interpretation: "결과에 따라 수익률이 확정되거나 변동됩니다."
  },
  table_roi: {
    title: "수익률 (ROI)",
    desc: "진입가 대비 현재가(또는 청산가)의 등락률입니다.",
    criteria: "수수료 및 세금은 미포함된 수치",
    interpretation: "목표 +9% 달성 시 성공, -5% 이탈 시 실패로 기록됩니다."
  },
  table_maxHigh: {
    title: "최고가 (Max High)",
    desc: "보유 기간 동안 도달한 최고 수익률입니다.",
    criteria: "(기간내 최고가 - 진입가) / 진입가 * 100",
    interpretation: "최고가가 +9%를 넘었다면 성공으로 간주합니다."
  },
  table_priceTrail: {
    title: "가격 흐름 (Price Trail)",
    desc: "진입 이후 매일의 주가 변동폭을 바 그래프로 표현했습니다.",
    criteria: "전일 대비 등락률 시각화",
    interpretation: "빨강(하락), 초록(상승). 추세가 꺾이지 않고 유지되는지 확인하세요."
  },
  table_days: {
    title: "보유일 (Days)",
    desc: "매수 후 현재(또는 청산)까지 보유한 영업일 수입니다.",
    criteria: "주말/공휴일 제외",
    interpretation: "오래 보유할수록 기회비용이 발생하므로 빠른 승부가 유리합니다."
  },
  table_score: {
    title: "AI 점수 (Score)",
    desc: "기술적/수급적 요인을 종합 평가한 AI의 점수입니다.",
    criteria: "100점 만점 기준",
    interpretation: "점수가 높을수록 상승 모멘텀이 강하다고 판단합니다."
  },
  table_themes: {
    title: "테마 (Themes)",
    desc: "해당 종목이 속한 주요 테마나 섹터입니다.",
    criteria: "시장 주도 테마 포함 여부",
    interpretation: "주도 테마에 속한 종목이 더 강한 시세를 뿜어냅니다."
  }
};

// ----------------------------------------------------------------------
// 2. HELPER FUNCTION
// ----------------------------------------------------------------------
function renderTooltipContent(key: keyof typeof TOOLTIP_CONTENT) {
  const data = TOOLTIP_CONTENT[key];
  if (!data) return null;

  return (
    <div className="space-y-3 p-1">
      <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-1">
        <span className="font-bold text-white text-sm">{data.title}</span>
      </div>
      <div>
        <div className="text-[10px] text-gray-400 mb-0.5">설명</div>
        <div className="text-xs text-gray-200 leading-snug">{data.desc}</div>
      </div>
      <div className="grid grid-cols-1 gap-2 bg-white/5 p-2 rounded border border-white/5">
        <div>
          <div className="text-[10px] text-gray-500 font-bold mb-0.5">기준</div>
          <div className="text-[11px] text-emerald-400">{data.criteria}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 font-bold mb-0.5">해석</div>
          <div className="text-[11px] text-gray-300 leading-snug">{data.interpretation}</div>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// 3. COMPONENTS
// ----------------------------------------------------------------------

// ----------------------------------------------------------------------
// 5. DYNAMIC STAT TOOLTIP HELPER
// ----------------------------------------------------------------------
function renderStatTooltip(key: keyof typeof TOOLTIP_CONTENT, kpi: KPIData) {
  const baseContent = TOOLTIP_CONTENT[key];
  if (!baseContent) return null;

  let advice = "";
  let adviceColor = "text-gray-300";

  // Dynamic Logic based on Key
  switch (key) {
    case 'winRate':
      if (kpi.winRate >= 60) {
        advice = "승률이 매우 높습니다. 비중 확대를 고려해보세요.";
        adviceColor = "text-emerald-400 font-bold";
      } else if (kpi.winRate >= 40) {
        advice = "안정적인 승률입니다. 꾸준한 투자가 유효합니다.";
        adviceColor = "text-blue-400 font-bold";
      } else {
        advice = "승률 개선이 필요합니다. 진입 기준을 더 엄격하게 하세요.";
        adviceColor = "text-rose-400 font-bold";
      }
      break;

    case 'profitFactor':
      if (kpi.profitFactor >= 2.0) {
        advice = "탁월한 손익비입니다. 강력한 수익 모델입니다.";
        adviceColor = "text-emerald-400 font-bold";
      } else if (kpi.profitFactor >= 1.5) {
        advice = "우수한 손익비입니다. 안정적인 수익이 기대됩니다.";
        adviceColor = "text-blue-400 font-bold";
      } else if (kpi.profitFactor >= 1.2) {
        advice = "손익비가 양호하나, 손실 관리에 유의하세요.";
        adviceColor = "text-yellow-400";
      } else {
        advice = "손익비가 낮습니다. 전략의 우위가 약합니다.";
        adviceColor = "text-rose-400 font-bold";
      }
      break;

    case 'avgRoi':
      if (kpi.avgRoi > 0) {
        advice = "기대 수익이 긍정적(+)입니다.";
        adviceColor = "text-emerald-400 font-bold";
      } else {
        advice = "기대 수익이 부정적(-)입니다. 손절 원칙을 재점검하세요.";
        adviceColor = "text-rose-400 font-bold";
      }
      break;

    case 'avgDays':
      if (kpi.avgDays <= 3) {
        advice = "자금 회전이 빠릅니다. 복리 효과 극대화에 유리합니다.";
        adviceColor = "text-emerald-400 font-bold";
      } else if (kpi.avgDays > 5) {
        advice = "자금 회전이 다소 느립니다. 기회비용을 고려하세요.";
        adviceColor = "text-yellow-400";
      } else {
        advice = "적절한 보유 기간입니다.";
        adviceColor = "text-blue-400";
      }
      break;

    case 'open':
      if (kpi.open > 10) {
        advice = "보유 종목이 많습니다. 시장 하락 시 리스크가 커질 수 있습니다.";
        adviceColor = "text-rose-400 font-bold";
      } else if (kpi.open > 5) {
        advice = "적정 수준의 포트폴리오를 구성 중입니다.";
        adviceColor = "text-blue-400";
      } else {
        advice = "현금 비중이 높거나, 진입 기회를 기다리는 중입니다.";
        adviceColor = "text-gray-400";
      }
      break;

    // Default advice for others (optional)
    default:
      advice = baseContent.interpretation; // Fallback to static interpretation
      adviceColor = "text-gray-300";
      break;
  }

  // Override advice if it was just fallback
  const finalAdvice = advice === baseContent.interpretation ? baseContent.interpretation : advice;


  return (
    <div className="space-y-3 p-1 min-w-[260px]">
      <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-1">
        <span className="font-bold text-white text-sm">{baseContent.title}</span>
      </div>
      <div>
        <div className="text-[10px] text-gray-400 mb-0.5">설명</div>
        <div className="text-xs text-gray-200 leading-snug">{baseContent.desc}</div>
      </div>

      {/* Dynamic Advice Section */}
      <div className="bg-white/5 rounded-lg p-2 border border-white/10">
        <div className="text-[10px] text-gray-500 font-bold mb-0.5">전략 코멘트</div>
        <div className={`text-xs leading-snug ${adviceColor}`}>
          {finalAdvice}
        </div>
        {key !== 'profitFactor' && key !== 'avgDays' && key !== 'open' && (
          <div className="mt-2 pt-2 border-t border-white/5">
            <div className="text-[10px] text-gray-500 font-bold mb-0.5">기준</div>
            <div className="text-[11px] text-gray-400">{baseContent.criteria}</div>
          </div>
        )}
      </div>
    </div>
  );
}


function StatCard({ title, value, colorClass = 'text-white', subtext, kpi, tooltipKey, valueClassName = 'text-2xl' }: { title: string, value: React.ReactNode, colorClass?: string, subtext?: string, kpi?: KPIData, tooltipKey?: keyof typeof TOOLTIP_CONTENT, valueClassName?: string }) {
  const content = (
    <div className="bg-[#1c1c1e] p-4 rounded-xl border border-white/5 flex flex-col justify-between h-24 hover:border-white/20 transition-colors relative group cursor-help">
      <div className="flex justify-between items-start">
        <div className="text-[10px] text-gray-500 font-bold tracking-wider uppercase">{title}</div>
        {tooltipKey && <i className="fas fa-question-circle text-gray-700 text-[10px] group-hover:text-gray-500 transition-colors"></i>}
      </div>
      <div className={`${valueClassName} font-bold ${colorClass}`}>{value}</div>
      {subtext && <div className="text-xs text-gray-500">{subtext}</div>}
    </div>
  );

  if (tooltipKey && kpi) {
    return (
      <Tooltip content={renderStatTooltip(tooltipKey, kpi)} position="bottom" align="center" className="w-full h-full block" as="div">
        {content}
      </Tooltip>
    );
  } else if (tooltipKey) {
    // Fallback for static tooltip if no KPI provided (legacy support)
    return (
      <Tooltip content={renderTooltipContent(tooltipKey)} position="bottom" align="center" className="w-full h-full block" as="div">
        {content}
      </Tooltip>
    );
  }
  return content;
}

function CumulativeGuideModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="누적 성과 지표 가이드" type="default" wide>
      <div className="space-y-8 max-h-[70vh] overflow-y-auto pr-2">
        {/* 1. Key Metrics Guide */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <i className="fas fa-chart-line text-blue-400"></i>
              핵심 지표 해석
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="font-bold text-white text-sm mb-2 text-emerald-400">승률 (Win Rate)</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                전체 매매 중 익절(+9% 목표 도달)에 성공한 비율입니다.<br />
                <span className="text-gray-500 mt-1 block">계산식: (익절 횟수 / (익절 + 손절 횟수)) * 100</span>
              </p>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="font-bold text-white text-sm mb-2 text-cyan-400">손익비 (Profit Factor)</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                총 이익 / 총 손실 비율로, 1.5 이상이면 훌륭한 전략입니다.<br />
                <span className="text-gray-500 mt-1 block">계산식: (총 이익금 / 총 손실금) 절대값</span>
              </p>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="font-bold text-white text-sm mb-2 text-yellow-400">평균 보유일 (Avg Days)</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                매수 후 청산(익절/손절)까지 걸린 평균 기간입니다.<br />
                <span className="text-gray-500 mt-1 block">짧을수록 자금 회전율이 좋습니다.</span>
              </p>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h4 className="font-bold text-white text-sm mb-2 text-rose-400">누적 수익률 (Total ROI)</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                초기 자본금 대비 현재까지의 총 수익률(단리 합산)입니다.<br />
                <span className="text-gray-500 mt-1 block">실제 복리 수익률과는 차이가 있을 수 있습니다.</span>
              </p>
            </div>
          </div>
        </div>

        {/* 2. Strategy Criteria */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <i className="fas fa-clipboard-check text-purple-400"></i>
              매매 원칙 및 등급 기준
            </h3>
          </div>
          <div className="bg-white/5 rounded-xl p-5 border border-white/10 space-y-4">
            <div>
              <h4 className="font-bold text-white text-sm mb-1">매매 원칙 (Exit Strategy)</h4>
              <ul className="list-disc list-inside text-xs text-gray-400 space-y-1 ml-1">
                <li><span className="text-emerald-400 font-bold">익절 목표:</span> +9.0% 도달 시 전량 매도</li>
                <li><span className="text-rose-400 font-bold">손절 기준:</span> -5.0% 이탈 시 전량 매도</li>
                <li><span className="text-yellow-400 font-bold">최대 보유:</span> 15일 (기간 내 승부 안나면 매도 고려)</li>
              </ul>
            </div>
            <div className="border-t border-white/10 pt-4">
              <h4 className="font-bold text-white text-sm mb-1">등급 분류 (Ranking)</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                  <div className="p-2 border border-purple-500/30 bg-purple-500/10 rounded-lg">
                    <span className="text-purple-400 font-bold text-xs">[S등급]</span> <span className="text-gray-400 text-[10px]">거래대금 1조↑ + 점수 10점↑ (초대형 주도주)</span>
                  </div>
                  <div className="p-2 border border-rose-500/30 bg-rose-500/10 rounded-lg">
                    <span className="text-rose-400 font-bold text-xs">[A등급]</span> <span className="text-gray-400 text-[10px]">거래대금 5천억↑ + 점수 8점↑ (대형 주도주)</span>
                  </div>
                  <div className="p-2 border border-blue-500/30 bg-blue-500/10 rounded-lg">
                    <span className="text-blue-400 font-bold text-xs">[B등급]</span> <span className="text-gray-400 text-[10px]">거래대금 1천억↑ + 점수 6점↑ (준수한 수급주)</span>
                  </div>
                </div>
              </div>
            </div>
        </div>
      </div>
    </Modal>
  );
}


// ----------------------------------------------------------------------
// 4. DYNAMIC GRADE TOOLTIP HELPER
// ----------------------------------------------------------------------
function renderGradeTooltip(grade: string, stats: { count: number, winRate: number, avgRoi: number, wins: number, losses: number }) {
  const baseContent = TOOLTIP_CONTENT[`grade${grade}` as keyof typeof TOOLTIP_CONTENT];
  if (!baseContent) return null;

  // Dynamic Strategy Advice Logic
  let strategyAdvice = "";
  let adviceColor = "text-gray-300";

  if (stats.count === 0) {
    strategyAdvice = "아직 매매 데이터가 충분하지 않습니다.";
  } else if (stats.winRate >= 60) {
    strategyAdvice = "현재 승률이 매우 좋습니다! 적극적인 비중 확대가 유효한 구간입니다.";
    adviceColor = "text-emerald-400 font-bold";
  } else if (stats.winRate >= 40) {
    strategyAdvice = "안정적인 성과를 보이고 있습니다. 표준 비중으로 꾸준히 접근하세요.";
    adviceColor = "text-blue-400 font-bold";
  } else {
    strategyAdvice = "현재 성과가 저조합니다. 진입을 자제하거나 비중을 축소하고 관망하는 것이 좋습니다.";
    adviceColor = "text-rose-400 font-bold";
  }

  // ROI Warning
  if (stats.avgRoi < 0 && stats.count > 0) {
    strategyAdvice += " (평균 수익률이 마이너스입니다. 손절 원칙을 철저히 지키세요)";
    adviceColor = "text-rose-400 font-bold";
  }

  return (
    <div className="space-y-3 p-1 min-w-[280px]">
      <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-1">
        <span className="font-bold text-white text-sm">{baseContent.title}</span>
      </div>

      {/* 1. Grade Definition (Static) */}
      <div>
        <div className="text-[10px] text-gray-400 mb-0.5">등급 기준</div>
        <div className="text-xs text-gray-200 leading-snug">{baseContent.desc}</div>
        <div className="text-[10px] text-gray-500 mt-1">{baseContent.criteria}</div>
      </div>

      {/* 2. Current Status (Dynamic) */}
      <div className="bg-white/5 rounded-lg p-2 border border-white/10">
        <div className="text-[10px] text-gray-400 font-bold mb-1.5 border-b border-white/5 pb-1">현재 성과 분석</div>
        <div className="grid grid-cols-2 gap-y-1 gap-x-2 text-xs">
          <span className="text-gray-500">승률:</span>
          <span className={`font-mono font-bold ${stats.winRate >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>{stats.winRate}%</span>

          <span className="text-gray-500">평균 수익:</span>
          <span className={`font-mono font-bold ${stats.avgRoi > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {stats.avgRoi > 0 ? '+' : ''}{stats.avgRoi}%
          </span>

          <span className="text-gray-500">성공/실패:</span>
          <span className="font-mono text-white">{stats.wins}승 / {stats.losses}패</span>
        </div>
      </div>

      {/* 3. Strategic Advice (Dynamic) */}
      <div>
        <div className="text-[10px] text-gray-500 font-bold mb-0.5">전략 코멘트</div>
        <div className={`text-xs leading-snug ${adviceColor}`}>
          {strategyAdvice}
        </div>
      </div>
    </div>
  );
}


function GradeCard({ data }: { data: any }) {
  const content = (
    <div className={`p-5 rounded-2xl border ${data.border} ${data.bg} flex flex-col justify-between h-32 relative group cursor-help`}>
      <div className="flex justify-between items-start">
        <h3 className={`text-lg font-bold ${data.color} flex items-center gap-2`}>
          {data.grade} 등급
          <i className="fas fa-question-circle text-white/20 text-[10px] group-hover:text-white/50 transition-colors"></i>
        </h3>
        <span className="text-xs text-gray-400">{data.count}건</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center mt-2">
        <div>
          <div className="text-[10px] text-gray-500 mb-1">승률</div>
          <div className={`text-sm font-bold ${data.color}`}>{data.winRate}%</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 mb-1">평균 수익률</div>
          <div className={`text-sm font-bold ${data.avgRoi > 0 ? 'text-green-400' : 'text-rose-400'}`}>
            {data.avgRoi > 0 ? '+' : ''}{data.avgRoi}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 mb-1">성공/실패</div>
          <div className="text-sm font-bold text-white">{data.wins}/{data.losses}</div>
        </div>
      </div>
    </div>
  );

  return (
    <Tooltip content={renderGradeTooltip(data.grade, data)} position="top" align="center" className="w-full h-full block" as="div">
      {content}
    </Tooltip>
  );
}

// ----------------------------------------------------------------------
// 6. DISTRIBUTION TOOLTIP HELPER
// ----------------------------------------------------------------------
function renderDistributionTooltip(kpi: KPIData, trades: Trade[]) {
  const baseContent = TOOLTIP_CONTENT.distribution;
  if (!baseContent) return null;

  // Analysis Logic
  // 1. Filter closed trades (Win or Loss) and sort by date descending (assuming 'data' is already sorted or we sort here)
  // We assume 'trades' passed here are the current page's trades. For better accuracy, we might need global history, 
  // but using visible recent trades is a good proxy for "recent trend".
  const closedTrades = trades.filter(t => t.outcome === 'Win' || t.outcome === 'Loss');

  // Calculate Consecutive Losses
  let consecutiveLosses = 0;
  for (let i = 0; i < closedTrades.length; i++) {
    if (closedTrades[i].outcome === 'Loss') {
      consecutiveLosses++;
    } else {
      break;
    }
  }

  // Calculate Recent Win Rate (Last 10)
  const recentTrades = closedTrades.slice(0, 10);
  const recentWins = recentTrades.filter(t => t.outcome === 'Win').length;
  const recentWinRate = recentTrades.length > 0 ? (recentWins / recentTrades.length) * 100 : 0;

  // Determine Advice
  let advice = "승/패가 고르게 분포되어 있습니다.";
  let adviceColor = "text-gray-300";

  if (consecutiveLosses >= 3) {
    advice = `현재 ${consecutiveLosses}연패 중입니다. 잠시 매매를 멈추고 시장을 관망하세요.`;
    adviceColor = "text-rose-400 font-bold";
  } else if (recentTrades.length >= 5 && recentWinRate >= 80) {
    advice = "최근 흐름이 매우 좋습니다 (승률 80%↑). 추세를 이어가세요.";
    adviceColor = "text-emerald-400 font-bold";
  } else if (recentTrades.length >= 5 && recentWinRate <= 20) {
    advice = "최근 흐름이 좋지 않습니다. 보수적인 접근이 필요합니다.";
    adviceColor = "text-rose-400 font-bold";
  }


  return (
    <div className="space-y-3 p-1 min-w-[280px]">
      <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-1">
        <span className="font-bold text-white text-sm">{baseContent.title}</span>
      </div>
      <div>
        <div className="text-[10px] text-gray-400 mb-0.5">설명</div>
        <div className="text-xs text-gray-200 leading-snug">{baseContent.desc}</div>
      </div>

      {/* Outcome Definitions Section */}
      <div className="space-y-2 border-t border-white/10 pt-2 pb-2">
        <div className="text-[10px] text-gray-500 font-bold mb-1">항목별 상세 기준</div>
        <div className="grid grid-cols-1 gap-1.5 text-xs">
          <div className="flex justify-between items-start gap-2">
            <span className="text-emerald-400 font-bold w-12 shrink-0">목표달성</span>
            <span className="text-gray-300">진입가 대비 <span className="text-emerald-400">+9% 이상</span> 상승하여 이익 실현 (익절)</span>
          </div>
          <div className="flex justify-between items-start gap-2">
            <span className="text-gray-400 font-bold w-12 shrink-0">보유중</span>
            <span className="text-gray-300">아직 청산되지 않고 진행 중 (최대 <span className="text-gray-200">15일</span> 보유)</span>
          </div>
          <div className="flex justify-between items-start gap-2">
            <span className="text-rose-400 font-bold w-12 shrink-0">손절도달</span>
            <span className="text-gray-300">진입가 대비 <span className="text-rose-400">-5% 이하</span> 하락하여 손실 확정 (손절)</span>
          </div>
        </div>
      </div>

      {/* Dynamic Advice Section */}
      <div className="bg-white/5 rounded-lg p-2 border border-white/10">
        <div className="text-[10px] text-gray-500 font-bold mb-1 border-b border-white/5 pb-1">현재 추세 분석</div>
        <div className="grid grid-cols-2 gap-y-1 gap-x-2 text-xs mb-2">
          <span className="text-gray-500">최근 10건 승률:</span>
          <span className={`font-mono font-bold ${recentWinRate >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {recentTrades.length > 0 ? `${recentWinRate.toFixed(0)}%` : '-'}
          </span>
          <span className="text-gray-500">연속 손실:</span>
          <span className={`font-mono font-bold ${consecutiveLosses > 0 ? 'text-rose-400' : 'text-gray-400'}`}>
            {consecutiveLosses}회
          </span>
        </div>

        <div className="text-[10px] text-gray-500 font-bold mb-0.5">전략 코멘트</div>
        <div className={`text-xs leading-snug ${adviceColor}`}>
          {advice}
        </div>
      </div>
    </div>
  );
}

function DistributionBar({ kpi, trades }: { kpi: KPIData, trades: Trade[] }) {
  const total = kpi.wins + kpi.open + kpi.losses;
  const wPct = total > 0 ? (kpi.wins / total) * 100 : 0;
  const oPct = total > 0 ? (kpi.open / total) * 100 : 0;
  const lPct = total > 0 ? (kpi.losses / total) * 100 : 0;

  return (
    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5 mb-8">
      <div className="flex items-center gap-2 mb-4">
        <h3 className="text-gray-500 text-xs font-bold uppercase tracking-wider">승패 분포 (WIN/LOSS)</h3>
        <Tooltip content={renderDistributionTooltip(kpi, trades)} position="top" align="left">
          <i className="fas fa-question-circle text-gray-700 text-[10px] hover:text-gray-500 transition-colors cursor-help"></i>
        </Tooltip>
      </div>

      <div className="flex h-8 w-full rounded-lg overflow-hidden font-bold text-xs text-black">
        {wPct > 0 && <div style={{ width: `${wPct}%` }} className="bg-emerald-500 flex items-center justify-center">{kpi.wins} 성공</div>}
        {oPct > 0 && <div style={{ width: `${oPct}%` }} className="bg-gray-600 flex items-center justify-center text-white">{kpi.open} 보유</div>}
        {lPct > 0 && <div style={{ width: `${lPct}%` }} className="bg-rose-500 flex items-center justify-center text-white">{kpi.losses} 실패</div>}
      </div>
      <div className="flex gap-6 mt-3 text-[10px] text-gray-400 justify-start">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
          목표가 도달
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-gray-600"></div>
          보유중
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-rose-500"></div>
          손절가 도달
        </div>
      </div>
    </div>
  );
}

function FilterButton({ label, count, active, onClick }: { label: string, count?: number, active: boolean, onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all border ${active
        ? 'bg-blue-500/20 text-blue-400 border-blue-500/50'
        : 'bg-[#2c2c2e] text-gray-400 border-transparent hover:bg-[#3a3a3c]'
        }`}
    >
      {label} {count !== undefined && <span className="opacity-70">({count})</span>}
    </button>
  );
}

// DailyBarGraph Component
function DailyBarGraph({ data }: { data: number[] }) {
  if (!data || data.length < 2) return <span className="text-gray-600">-</span>;

  // Calculate daily percent changes
  const changes = data.slice(1).map((price, i) => {
    const prev = data[i];
    return ((price - prev) / prev) * 100;
  });

  return (
    <div className="flex items-end gap-1 h-5 select-none">
      {changes.map((change, i) => {
        const absChange = Math.abs(change);
        const heightPct = Math.min(Math.max((absChange / 2) * 100, 30), 100);

        let colorClass = 'bg-gray-600';
        if (change > 0) colorClass = 'bg-emerald-500';
        else if (change < 0) colorClass = 'bg-rose-500';
        else colorClass = 'bg-gray-700';

        return (
          <div
            key={i}
            className={`w-1.5 rounded-sm ${colorClass} opacity-90`}
            style={{ height: `${heightPct}%` }}
            title={`${change > 0 ? '+' : ''}${change.toFixed(2)}%`}
          />
        );
      })}
    </div>
  );
}

// [FIX] Adjusted Tooltip position to prevent clipping in table header
function TableHeader({
  label,
  tooltipKey,
  align = "left",
}: {
  label: string,
  tooltipKey?: keyof typeof TOOLTIP_CONTENT,
  align?: 'left' | 'center' | 'right'
}) {
  // Map text alignment to tooltip alignment for better positioning
  // Left text -> Left tooltip (expands right)
  // Right text -> Right tooltip (expands left)
  // Center text -> Center tooltip
  const tooltipAlign = align === 'right' ? 'right' : align === 'center' ? 'center' : 'left';

  return (
    <th className={`py-3 px-4 ${align === "center" ? "text-center" : align === "right" ? "text-right" : "text-left"} whitespace-nowrap`}>
      <div className={`flex items-center gap-1.5 ${align === "center" ? "justify-center" : align === "right" ? "justify-end" : "justify-start"}`}>
        {label}
        {tooltipKey && (
          <Tooltip content={renderTooltipContent(tooltipKey)} position="bottom" align={tooltipAlign}>
            <i className="fas fa-info-circle text-gray-600 text-[10px] hover:text-gray-400 cursor-help transition-colors"></i>
          </Tooltip>
        )}
      </div>
    </th>
  );
}

function TradeTable({ trades }: { trades: Trade[] }) {
  return (
    <div className="bg-[#1c1c1e] rounded-2xl border border-white/5 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[800px]">
          <thead className="bg-[#2c2c2e]/50 text-[10px] uppercase text-gray-500 font-medium">
            <tr>
              <th className="py-3 px-4 w-12 text-center">#</th>
              <TableHeader label="추천일" tooltipKey="table_date" />
              <TableHeader label="등급" tooltipKey="table_grade" />
              <TableHeader label="종목명" />
              <TableHeader label="진입가" tooltipKey="table_entry" align="right" />
              <TableHeader label="결과" tooltipKey="table_result" align="center" />
              <TableHeader label="수익률" tooltipKey="table_roi" align="right" />
              <TableHeader label="최고가" tooltipKey="table_maxHigh" align="center" />
              <TableHeader label="가격흐름" tooltipKey="table_priceTrail" align="center" />
              <TableHeader label="보유일" tooltipKey="table_days" align="center" />
              <TableHeader label="점수" tooltipKey="table_score" align="center" />
              <TableHeader label="테마" tooltipKey="table_themes" />
            </tr>
          </thead>
          <tbody className="text-xs divide-y divide-white/5">
            {trades.map((trade, idx) => (
              <tr key={`${trade.id}-${idx}`} className="hover:bg-white/5 transition-colors group">
                <td className="py-3 px-4 text-center text-gray-600">{trades.length - idx}</td>
                <td className="py-3 px-4 text-gray-400 font-mono tracking-tight">{trade.date}</td>
                <td className="py-3 px-4">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${trade.grade === 'S' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                    trade.grade === 'A' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
                      trade.grade === 'B' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                        'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                    }`}>
                    {trade.grade}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <div className="font-bold text-white">{trade.name}</div>
                  <div className="text-[10px]">
                    <span className="text-gray-500">{trade.code}</span>{' '}
                    <span className={`${trade.market === 'KOSPI' ? 'text-blue-400' :
                      trade.market === 'KOSDAQ' ? 'text-rose-400' :
                        'text-gray-500'
                      }`}>{trade.market}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-right text-gray-300 font-mono">{trade.entry.toLocaleString()}</td>
                <td className="py-3 px-4 text-center">
                  <span className={`inline-block whitespace-nowrap px-2 py-0.5 rounded text-[10px] font-bold ${trade.outcome === 'WIN' ? 'bg-emerald-500/20 text-emerald-400' :
                    trade.outcome === 'LOSS' ? 'bg-rose-500/20 text-rose-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                    {trade.outcome === 'WIN' ? '성공' : trade.outcome === 'LOSS' ? '실패' : '보유'}
                  </span>
                </td>
                <td className={`py-3 px-4 text-right font-bold font-mono ${trade.roi > 0 ? 'text-emerald-400' : trade.roi < 0 ? 'text-rose-400' : 'text-gray-400'
                  }`}>
                  {trade.roi > 0 ? '+' : ''}{trade.roi.toFixed(1)}%
                </td>
                {/* Max High Logic */}
                <td className={`py-3 px-4 text-center font-mono ${trade.maxHigh >= 9 ? 'text-emerald-400 font-bold' :
                  trade.maxHigh > 0 ? 'text-yellow-400' : 'text-gray-500'
                  }`}>
                  {trade.maxHigh > 0 ? trade.maxHigh + '%' : '-'}
                </td>
                {/* Daily Bar Graph */}
                <td className="py-3 px-4 text-center align-middle">
                  <div className="flex justify-center">
                    <DailyBarGraph data={trade.priceTrail} />
                  </div>
                </td>
                <td className="py-3 px-4 text-center text-gray-400">{trade.days}일</td>
                <td className="py-3 px-4 text-center text-blue-400 font-bold">{Math.floor(trade.score)}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1 flex-wrap">
                    {trade.themes.map(t => (
                      <span key={t} className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded text-[10px] border border-purple-500/20">{t}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={12} className="py-8 text-center text-gray-500">
                  해당 기간에 대한 거래 내역이 없습니다.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CumulativeClientPage() {
  const formatSignedPercent = (value: number) => `${value > 0 ? '+' : ''}${value}%`;
  const createEmptyRoiByGrade = () => ({
    S: { count: 0, avgRoi: 0, totalRoi: 0 },
    A: { count: 0, avgRoi: 0, totalRoi: 0 },
    B: { count: 0, avgRoi: 0, totalRoi: 0 }
  });

  const [outcomeFilter, setOutcomeFilter] = useState('All');
  const [gradeFilter, setGradeFilter] = useState('All');
  const [isGuideOpen, setIsGuideOpen] = useState(false);

  // State for Real Data
  const [kpi, setKpi] = useState<KPIData>({
    totalSignals: 0,
    winRate: 0,
    wins: 0,
    losses: 0,
    open: 0,
    avgRoi: 0,
    totalRoi: 0,
    roiByGrade: createEmptyRoiByGrade(),
    avgDays: 0,
    priceDate: '-',
    profitFactor: 0
  });
  const [trades, setTrades] = useState<Trade[]>([]);
  const [pagination, setPagination] = useState<any>(null); // Pagination Metadata
  const [loading, setLoading] = useState(true);

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50); // Default 50

  // Fetch Data
  React.useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // [FIX] Server-side Pagination
        const res = await fetch(`/api/kr/closing-bet/cumulative?page=${currentPage}&limit=${itemsPerPage}`);
        if (!res.ok) throw new Error('Failed to fetch data');
        const data = await res.json();
        const emptyRoiByGrade = createEmptyRoiByGrade();
        const apiRoiByGrade = data.kpi?.roiByGrade || {};
        setKpi({
          ...data.kpi,
          roiByGrade: {
            S: { ...emptyRoiByGrade.S, ...(apiRoiByGrade.S || {}) },
            A: { ...emptyRoiByGrade.A, ...(apiRoiByGrade.A || {}) },
            B: { ...emptyRoiByGrade.B, ...(apiRoiByGrade.B || {}) }
          }
        });
        setPagination(data.pagination);
        // D등급 제외 필터링 (Server should handle this ideally, but keeping frontend filter for safety/consistency)
        const filtered = (data.trades || []).filter((t: Trade) => t.grade !== 'D');
        setTrades(filtered);
      } catch (error) {
        console.error('Error fetching cumulative data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [currentPage, itemsPerPage]); // Re-fetch on page/limit change

  // Filter Logic
  const filteredTrades = trades.filter(t => {
    if (outcomeFilter !== 'All' && t.outcome !== outcomeFilter) return false;
    if (gradeFilter !== 'All' && t.grade !== gradeFilter) return false;
    return true;
  });

  // Derived Data for Grade Cards (Real-time calculation based on trades)
  const calculateGradeStats = (targetGrade: string) => {
    const gradeTrades = trades.filter(t => t.grade === targetGrade);
    const count = gradeTrades.length;
    if (count === 0) return { count: 0, winRate: 0, avgRoi: 0, wins: 0, losses: 0 };

    const wins = gradeTrades.filter(t => t.outcome === 'WIN').length;
    const losses = gradeTrades.filter(t => t.outcome === 'LOSS').length;
    const closed = wins + losses; // Open excluded from WR usually, or included? Keeping consistent with API
    const winRate = closed > 0 ? (wins / closed) * 100 : 0;
    const avgRoi = gradeTrades.reduce((acc, t) => acc + t.roi, 0) / count;

    return { count, winRate: parseFloat(winRate.toFixed(1)), avgRoi: parseFloat(avgRoi.toFixed(1)), wins, losses };
  };

  const sStats = calculateGradeStats('S');
  const aStats = calculateGradeStats('A');
  const bStats = calculateGradeStats('B');

  const gradeCards = [
    { grade: 'S', ...sStats, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20', tooltipKey: 'gradeS' as const },
    { grade: 'A', ...aStats, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20', tooltipKey: 'gradeA' as const },
    { grade: 'B', ...bStats, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20', tooltipKey: 'gradeB' as const },
  ];

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="text-gray-500 font-mono text-sm">데이터 불러오는 중...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-6 space-y-6 animate-in fade-in duration-500 font-sans text-gray-200">
      {/* Header */}
      <div className="flex flex-col gap-1 mb-2">
        {/* Breadcrumb-like label if needed, or just title */}
        <div className="inline-block px-3 py-1 rounded-full bg-[#1c1c1e] w-fit border border-white/10 text-xs text-purple-400 font-medium mb-2">
          성과 트래커
        </div>
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
              실전 종가베팅 <span className="text-blue-500">누적 성과</span>
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-400">
              <span>{kpi.priceDate} 기준 누적 성과</span>
              <div className="flex gap-2">
                <span className="whitespace-nowrap px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded text-[10px] font-bold">목표 (+9%)</span>
                <span className="whitespace-nowrap px-2 py-0.5 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded text-[10px] font-bold">손절 (-5%)</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsGuideOpen(true)}
              className="flex items-center gap-2 p-2 md:px-4 md:py-2 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 rounded-lg text-sm text-purple-400 transition-colors cursor-pointer whitespace-nowrap"
            >
              <i className="fas fa-book-open"></i>
              <span className="hidden sm:inline">성과 가이드</span>
            </button>
            <button
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 p-2 md:px-4 md:py-2 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 rounded-lg text-sm transition-colors cursor-pointer whitespace-nowrap"
            >
              <i className="fas fa-sync-alt"></i>
              <span className="hidden sm:inline">새로고침</span>
            </button>
          </div>
        </div>
      </div>

      <CumulativeGuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />


      {/* Metric Cards - Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <StatCard title="누적 추천수" value={kpi.totalSignals} tooltipKey="totalSignals" kpi={kpi} />
        <StatCard title="승률" value={`${kpi.winRate}%`} colorClass="text-yellow-400" tooltipKey="winRate" kpi={kpi} />
        <StatCard title="성공" value={kpi.wins} colorClass="text-emerald-400" tooltipKey="wins" kpi={kpi} />
        <StatCard title="실패" value={kpi.losses} colorClass="text-rose-400" tooltipKey="losses" kpi={kpi} />
        <StatCard title="보유중" value={kpi.open} colorClass="text-yellow-500" tooltipKey="open" kpi={kpi} />
        <StatCard
          title="평균 수익률 (S/A/B)"
          value={
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs md:text-sm font-semibold leading-tight">
              <span className="text-purple-300">S {formatSignedPercent(kpi.roiByGrade.S.avgRoi)}</span>
              <span className="text-rose-300">A {formatSignedPercent(kpi.roiByGrade.A.avgRoi)}</span>
              <span className="text-blue-300">B {formatSignedPercent(kpi.roiByGrade.B.avgRoi)}</span>
            </div>
          }
          valueClassName="text-sm leading-tight"
          colorClass="text-white"
          tooltipKey="avgRoi"
          kpi={kpi}
        />
      </div>


      {/* Metric Cards - Row 2 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="누적 수익률 (S/A/B)"
          value={
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs md:text-sm font-semibold leading-tight">
              <span className="text-purple-300">S {formatSignedPercent(kpi.roiByGrade.S.totalRoi)}</span>
              <span className="text-rose-300">A {formatSignedPercent(kpi.roiByGrade.A.totalRoi)}</span>
              <span className="text-blue-300">B {formatSignedPercent(kpi.roiByGrade.B.totalRoi)}</span>
            </div>
          }
          valueClassName="text-sm leading-tight"
          colorClass="text-white"
          tooltipKey="totalRoi"
          kpi={kpi}
        />
        <StatCard title="평균 보유일" value={kpi.avgDays} tooltipKey="avgDays" kpi={kpi} />
        <StatCard title="데이터 기준일" value={kpi.priceDate} />
        <StatCard title="손익비 (Profit Factor)" value={kpi.profitFactor} colorClass="text-cyan-400" tooltipKey="profitFactor" kpi={kpi} />
      </div>


      {/* Grade Performance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {gradeCards.map((data) => (
          <GradeCard key={data.grade} data={data} />
        ))}
      </div>

      {/* DistributionBar */}
      <DistributionBar kpi={kpi} trades={trades} />

      {/* Trade List Section */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-gray-500 text-sm font-medium">결과:</span>
              <div className="flex gap-1 bg-[#1c1c1e] p-1 rounded-lg border border-white/5">
                <FilterButton label="전체" count={trades.length} active={outcomeFilter === 'All'} onClick={() => setOutcomeFilter('All')} />
                <FilterButton label="성공" count={kpi.wins} active={outcomeFilter === 'WIN'} onClick={() => setOutcomeFilter('WIN')} />
                <FilterButton label="실패" count={kpi.losses} active={outcomeFilter === 'LOSS'} onClick={() => setOutcomeFilter('LOSS')} />
                <FilterButton label="보유" count={kpi.open} active={outcomeFilter === 'OPEN'} onClick={() => setOutcomeFilter('OPEN')} />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-gray-500 text-sm font-medium">등급:</span>
              <div className="flex gap-1 bg-[#1c1c1e] p-1 rounded-lg border border-white/5">
                <FilterButton label="전체" active={gradeFilter === 'All'} onClick={() => setGradeFilter('All')} />
                <FilterButton label="S" count={sStats.count} active={gradeFilter === 'S'} onClick={() => setGradeFilter('S')} />
                <FilterButton label="A" count={aStats.count} active={gradeFilter === 'A'} onClick={() => setGradeFilter('A')} />
                <FilterButton label="B" count={bStats.count} active={gradeFilter === 'B'} onClick={() => setGradeFilter('B')} />
              </div>
            </div>
          </div>

          {/* Pagination Size Selector */}
          <div className="flex items-center gap-2">
            <span className="text-gray-500 text-sm font-medium">페이지당:</span>
            <select
              value={itemsPerPage}
              onChange={(e) => {
                setItemsPerPage(Number(e.target.value));
                setCurrentPage(1); // Reset to first page
              }}
              className="bg-[#1c1c1e] text-white text-xs p-1.5 rounded border border-white/10 outline-none focus:border-indigo-500"
            >
              <option value={50}>50개</option>
              <option value={100}>100개</option>
              <option value={200}>200개</option>
              <option value={500}>500개</option>
            </select>
          </div>
        </div>

        <TradeTable trades={filteredTrades} />

        {/* Pagination Controls */}
        {pagination && pagination.totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-4">
            <button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 bg-[#1c1c1e] border border-white/10 rounded disabled:opacity-50 hover:bg-white/5 transition-colors"
            >
              Prev
            </button>
            <span className="text-sm text-gray-400">
              Page <span className="text-white font-bold">{currentPage}</span> of {pagination.totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(prev => Math.min(pagination.totalPages, prev + 1))}
              disabled={currentPage === pagination.totalPages}
              className="px-3 py-1 bg-[#1c1c1e] border border-white/10 rounded disabled:opacity-50 hover:bg-white/5 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>

    </div>
  );
}
