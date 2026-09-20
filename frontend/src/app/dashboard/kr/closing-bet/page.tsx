'use client';

import React, { useState, useEffect, useCallback, useId, useLayoutEffect, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { fetchAPI, isAuthenticationError, paperTradingAPI } from '@/lib/api';
import { useAccountActionGuard } from '@/lib/accountActionGuard';
import { parseAIConfidence } from '@/lib/aiConfidence';
import Modal, { ModalShell } from '@/app/components/Modal';
import BuyStockModal from '@/app/components/BuyStockModal';
import ClosingBetCriteriaModal from '@/app/components/ClosingBetCriteriaModal';
import GradeGuideModal from '@/app/components/GradeGuideModal';
import Tooltip from '@/app/components/Tooltip';
import { useAdmin } from '@/hooks/useAdmin';
import { CHART_PERIODS, formatBigNumber, stockChartUrl } from './displayHelpers';
import { PriceRangeBar, StatBox } from './displayPrimitives';
import ConfirmationModal from '@/app/components/ConfirmationModal';

// 이 화면에서 되돌릴 수 없는 지출을 일으키는 조작은 셋이다. 앞의 둘은 DATA STATUS 의
// 아이콘 버튼이고, 셋째는 카드마다 있는 「이 종목만 재분석」이다. 셋 모두 아이콘만 두지
// 않고 이름을 붙이며, 실행 전에 확인 모달을 한 번 거친다. 버튼 이름과 모달 제목이 같은
// 문구를 쓰도록 여기에 모은다.
const COSTLY_ACTIONS = {
  update: {
    name: '스크리너 전체 업데이트',
    body: '스크리너 엔진을 실행해 모든 종목의 뉴스와 수급과 점수를 다시 계산합니다.',
  },
  gemini: {
    name: 'GEMINI AI 재분석',
    body: '기존 데이터를 기반으로 Gemini AI 를 재호출합니다. 미분석 항목과 실패 항목만 다시 분석합니다.',
  },
} as const;

type CostlyAction = keyof typeof COSTLY_ACTIONS;

const COSTLY_WARNING = '외부 API 를 호출하므로 실제 요금이 발생하며, 실행한 뒤에는 되돌릴 수 없습니다.';

const costlyMessage = (body: string) => `${body}\n\n${COSTLY_WARNING}`;


// 응답은 이 판정을 최상위와 score 두 자리에 담는다. 지난 자료는 score 안에만 넣고
// 최상위를 null 로 두므로 두 자리 모두 null 을 허용해야 한다.
interface AiEvaluation {
  action: 'BUY' | 'HOLD' | 'SELL';
  // [JONGGA-008] 백엔드는 확신도가 없는 상태를 0 이 아니라 null 로 보낸다.
  confidence?: number | null;
  model?: string;
  reason?: string;
}

interface ScoreDetail {
  news: number;
  volume: number;
  chart: number;
  candle: number;
  consolidation: number;
  timing: number;
  supply: number;
  llm_reason: string;
  total: number;
  ai_evaluation?: AiEvaluation | null;
}

interface BonusBreakdown {
  volume?: number;
  candle?: number;
  limit_up?: number;
}

interface ChecklistDetail {
  has_news: boolean;
  news_sources: string[];
  is_new_high: boolean;
  is_breakout: boolean;
  supply_positive: boolean;
  volume_surge: boolean;
}

interface NewsItem {
  title: string;
  source: string;
  published_at: string;
  url: string;
}

interface Signal {
  stock_code: string;
  stock_name: string;
  market: string;
  sector: string;
  grade: string;
  score: ScoreDetail;
  checklist: ChecklistDetail;
  current_price: number;
  entry_price: number;
  stop_price: number;
  target_price: number;
  change_pct: number;
  trading_value: number;
  volume_ratio?: number;
  buy_price?: number;
  target_price_1?: number;
  target_price_2?: number;
  news_items?: NewsItem[];
  advice?: ExpertAdvice;
  mini_chart?: CandleData[];
  score_details?: {
    rise_pct?: number;
    volume_ratio?: number;
    foreign_net_buy?: number;
    inst_net_buy?: number;
    base_score?: number;
    bonus_score?: number;
    bonus_breakdown?: BonusBreakdown;
    is_new_high?: boolean;
    is_limit_up?: boolean;
    candle?: number;
    consolidation?: number;
  };
  ai_evaluation?: AiEvaluation | null;
  themes?: string[]; // 관련 테마 태그 (예: 원전, SMR, 전력인프라)
  signal_date?: string; // 신호가 나온 거래일. 매수가가 어느 날 종가인지 밝히는 데 쓴다
}

interface ExpertAdvice {
  trading_tip: string;
  selling_strategy: string;
  market_context: string;
  buy_strategy?: string;
}

interface CandleData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ScreenerResult {
  date: string;
  total_candidates: number;
  filtered_count: number;
  signals: Signal[];
  updated_at: string;
  status?: string;
  is_stale?: boolean;
  stale_warning?: string;
  latest_available_date?: string;
  message?: string;
}

interface StockDetailInfo {
  code: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ' | 'UNKNOWN';
  priceInfo: {
    current: number;
    prevClose: number;
    open: number;
    high: number;
    low: number;
    change: number;
    change_pct: number;
    volume: number;
    trading_value: number;
  };
  yearRange: {
    high_52w: number;
    low_52w: number;
  };
  indicators: {
    marketCap: number;
    per: number;
    pbr: number;
    eps: number;
    bps: number;
    dividendYield: number;
    roe?: number;
    psr?: number;
  };
  investorTrend: {
    foreign: number;
    institution: number;
    individual: number;
  };
  investorTrend5Day?: {
    foreign: number;
    institution: number;
  };
  financials: {
    revenue: number;
    operatingProfit: number;
    netIncome: number;
  };
  safety: {
    debtRatio: number;
    currentRatio: number;
  };
}

function StockChart({ symbol, name }: { symbol: string, name: string }) {
  const [period, setPeriod] = useState<(typeof CHART_PERIODS)[number]>(CHART_PERIODS[0]);
  const [failed, setFailed] = useState(false);

  return (
    <div className="flex flex-col h-full bg-[#131722]">
      <div className="flex items-center gap-2 px-4 pt-4">
        {CHART_PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => { setPeriod(p); setFailed(false); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
              period.key === p.key
                ? 'bg-indigo-500 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            {p.label}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-gray-500">네이버 금융 제공</span>
      </div>

      <div className="flex items-center justify-center p-4">
        {failed ? (
          <div className="text-center px-6">
            <i className="fas fa-chart-line text-4xl text-gray-600 mb-3"></i>
            <p className="text-gray-200 font-bold">{name} ({symbol}) 차트를 불러오지 못했습니다</p>
            <p className="text-sm text-gray-500 mt-2">
              다른 종목의 차트를 대신 보여주지 않습니다. 아래 네이버 금융이나 토스 증권에서 확인하세요.
            </p>
          </div>
        ) : (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={stockChartUrl(symbol, period.key)}
            alt={`${name} ${symbol} ${period.label} 차트`}
            onError={() => setFailed(true)}
            width={700}
            height={289}
            className="max-w-full h-auto object-contain"
          />
        )}
      </div>

      <div className="flex gap-3 p-4 bg-[#1c1c1e] border-t border-white/5">
        <a
          href={`https://m.stock.naver.com/domestic/stock/${symbol}/chart`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 px-4 py-3 bg-[#03c75a] hover:bg-[#00b24e] text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
        >
          <i className="fas fa-chart-line"></i>
          네이버 금융
        </a>
        <a
          href={`https://tossinvest.com/stocks/${symbol}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 px-4 py-3 bg-[#3182f6] hover:bg-[#1b64da] text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
        >
          <i className="fas fa-mobile-alt"></i>
          토스 증권
        </a>
      </div>
    </div>
  );
}

function ChartModal({ symbol, name, onClose }: { symbol: string, name: string, onClose: () => void }) {
  const titleId = useId();

  return (
    <ModalShell
      onClose={onClose}
      labelledBy={titleId}
      overlayClassName="z-[100] p-4"
      className="bg-[#1c1c1e] w-full max-w-4xl max-h-[85vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden relative animate-fade-in motion-reduce:animate-none"
    >
        <div className="flex items-center justify-between p-4 border-b border-white/5 bg-[#1c1c1e]">
          <div className="flex items-center gap-3">
            <h3 id={titleId} className="text-xl font-bold text-white">{name}</h3>
            <span className="text-sm font-mono text-gray-400">{symbol}</span>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <i className="fas fa-times text-xl"></i>
          </button>
        </div>

        <div className="flex-1 relative overflow-y-auto">
          <StockChart symbol={symbol} name={name} />
        </div>
    </ModalShell>
  );
}

// 트렌딩 테마 집계 함수
function getTrendingThemes(signals: Signal[]): { theme: string; count: number }[] {
  const themeCount: Record<string, number> = {};

  signals.forEach(signal => {
    signal.themes?.forEach(theme => {
      themeCount[theme] = (themeCount[theme] || 0) + 1;
    });
  });

  return Object.entries(themeCount)
    .map(([theme, count]) => ({ theme, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 15);
}

// Trending Themes Box Component - Word Cloud Style
function TrendingThemesBox({ themes }: { themes: { theme: string; count: number }[] }) {
  // 색상 팔레트 (이미지 참고: 보라, 노란, 초록, 파랑, 청록 등)
  const colors = [
    'text-purple-400',    // 1위 - 보라색
    'text-yellow-400',    // 2위 - 노란색
    'text-emerald-400',   // 3위 - 초록색
    'text-cyan-400',      // 4위 - 청록색
    'text-amber-400',     // 5위 - 주황색
    'text-blue-400',      // 6위 - 파란색
    'text-pink-400',      // 7위 - 분홍색
    'text-lime-400',      // 8위 - 라임색
    'text-indigo-400',    // 9위 - 인디고
    'text-teal-400',      // 10위 - 틸
    'text-orange-400',    // 11위 - 오렌지
    'text-violet-400',    // 12위 - 바이올렛
    'text-green-400',     // 13위 - 그린
    'text-rose-400',      // 14위 - 로즈
    'text-sky-400',       // 15위 - 스카이
  ];

  // 빈도수에 따른 글자 크기 계산 (워드 클라우드 스타일)
  const getThemeStyle = (index: number, count: number, maxCount: number) => {
    // 첫 번째 테마는 가장 크게 (2.5rem), 나머지는 빈도에 따라 조절
    if (index === 0) {
      return {
        fontSize: '2.5rem',
        fontWeight: 800,
        color: colors[0],
      };
    }

    // 빈도수 비율에 따라 크기 계산 (0.875rem ~ 1.5rem)
    const ratio = maxCount > 0 ? count / maxCount : 0;
    const minSize = 0.875;  // 14px
    const maxSize = 1.5;    // 24px
    const fontSize = minSize + (maxSize - minSize) * ratio;

    return {
      fontSize: `${fontSize}rem`,
      fontWeight: ratio > 0.7 ? 700 : ratio > 0.4 ? 600 : 500,
      color: colors[index % colors.length],
    };
  };

  const maxCount = themes[0]?.count || 1;

  return (
    <div className="bg-[#1c1c1e] rounded-2xl border border-white/10 p-5 min-w-[320px] max-w-[600px]">
      {/* Header */}
      <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase tracking-wider mb-4">
        <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
        TRENDING THEMES
      </div>

      {themes.length > 0 ? (
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 leading-relaxed">
          {themes.map((t, i) => {
            const style = getThemeStyle(i, t.count, maxCount);
            return (
              <span
                key={i}
                className={`${style.color} transition-all duration-300 hover:opacity-80 cursor-default whitespace-nowrap`}
                style={{
                  fontSize: style.fontSize,
                  fontWeight: style.fontWeight,
                }}
                title={`${t.theme}: ${t.count}개 종목`}
              >
                {t.theme}
              </span>
            );
          })}
        </div>
      ) : (
        <div className="text-gray-500 text-sm py-4">
          데이터 갱신 후 표시됩니다
        </div>
      )}
    </div>
  );
}

// Stock Detail Modal Component
function StockDetailModal({ code, name, onClose }: { code: string; name: string; onClose: () => void }) {
  const titleId = useId();
  const [detail, setDetail] = useState<StockDetailInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // TossCollector 응답을 StockDetailInfo 형식으로 변환
  const mapTossDataToDetail = (data: Record<string, unknown>): StockDetailInfo => {
    // 이미 백엔드에서 가공된 데이터인 경우 (kr_market.py 응답) 그대로 반환
    if (data.priceInfo) {
      return data as unknown as StockDetailInfo;
    }

    const price = (data.price || {}) as Record<string, number>;
    const indicators = (data.indicators || {}) as Record<string, number>;
    const investorTrend = (data.investor_trend || {}) as Record<string, number>;
    const investorTrend5Day = (data.investorTrend5Day || {}) as Record<string, number>;
    const financials = (data.financials || {}) as Record<string, number>;
    const stability = (data.stability || {}) as Record<string, number>;

    return {
      code: data.code as string || '',
      name: data.name as string || '',
      market: (data.market as 'KOSPI' | 'KOSDAQ' | 'UNKNOWN') || 'UNKNOWN',
      priceInfo: {
        current: price.current || 0,
        prevClose: price.prev_close || 0,
        open: price.open || 0,
        high: price.high || 0,
        low: price.low || 0,
        change: (price.current || 0) - (price.prev_close || 0),
        change_pct: price.prev_close ? (((price.current || 0) - price.prev_close) / price.prev_close * 100) : 0,
        volume: price.volume || 0,
        trading_value: price.trading_value || 0,
      },
      yearRange: {
        high_52w: price.high_52w || 0,
        low_52w: price.low_52w || 0,
      },
      indicators: {
        marketCap: price.market_cap || 0,
        per: indicators.per || 0,
        pbr: indicators.pbr || 0,
        eps: indicators.eps || 0,
        bps: indicators.bps || 0,
        dividendYield: indicators.dividend_yield || 0,
        roe: indicators.roe || 0,
        psr: indicators.psr || 0,
      },
      investorTrend: {
        foreign: investorTrend.foreign || 0,
        institution: investorTrend.institution || 0,
        individual: investorTrend.individual || 0,
      },
      investorTrend5Day: {
        foreign: investorTrend5Day.foreign || 0,
        institution: investorTrend5Day.institution || 0,
      },
      financials: {
        revenue: financials.revenue || 0,
        operatingProfit: financials.operating_profit || 0,
        netIncome: financials.net_income || 0,
      },
      safety: {
        debtRatio: stability.debt_ratio || 0,
        currentRatio: stability.current_ratio || 0,
      },
    };
  };

  useEffect(() => {
    fetch(`/api/kr/stock-detail/${code}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.error) {
          setError(data.error);
        } else {
          // API 응답을 StockDetailInfo 형식으로 변환
          const mappedDetail = mapTossDataToDetail(data);
          setDetail(mappedDetail);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [code]);

  // 외국인·기관 5일 순매수는 카드가 쓰는 KRX 확정 집계(investorTrend5Day)를 그대로 쓴다.
  // 응답에 그 키가 없으면 실시간 시세 제공처가 낸 5일 집계로 물러선다.
  // 같은 집계이되 같은 값은 아니다. 상세 API 는 날짜를 받지 않아 늘 오늘 기준으로
  // 돌려주므로, 지난 날짜의 리포트를 보고 있으면 카드의 신호일 기준값과 어긋난다.
  const foreign5Day = detail?.investorTrend5Day?.foreign ?? detail?.investorTrend?.foreign ?? 0;
  const institution5Day = detail?.investorTrend5Day?.institution ?? detail?.investorTrend?.institution ?? 0;

  return (
    <ModalShell
      onClose={onClose}
      labelledBy={titleId}
      overlayClassName="z-[100] p-2 md:p-4"
      className="bg-[#1c1c1e] w-[95%] md:w-full max-w-3xl max-h-[85vh] rounded-2xl border border-white/10 shadow-2xl overflow-hidden animate-fade-in motion-reduce:animate-none"
    >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <h3 id={titleId} className="text-xl font-bold text-white">{name}</h3>
            <span className="text-sm font-mono text-gray-400">{code}</span>
            {detail?.market && (
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${detail.market === 'KOSDAQ'
                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  : 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  }`}
              >
                {detail.market}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <i className="fas fa-times text-xl"></i>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 md:p-6 overflow-y-auto max-h-[calc(85vh-70px)]">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
            </div>
          ) : error ? (
            <div className="text-center text-rose-400 py-8">{error}</div>
          ) : detail ? (
            <div className="space-y-6">
              {/* Price Range Section */}
              <div className="bg-white/5 rounded-xl p-4">
                <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <i className="fas fa-chart-bar text-indigo-400"></i> 시세 정보 (실시간)
                  <Tooltip content="당일의 가격 움직임(1일 범위)과 최근 52주간 최저·최고가를 견주어 지금의 가격 위치를 보여줍니다. 카드에 적힌 값은 신호가 나온 거래일에 확정된 것이라 이 값과 다릅니다.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                {/* 두 호출 모두 폴백 없이 원값을 넘긴다. 1일 범위에는 값이 없을 때
                    전일종가에 0.97 과 1.03 을 곱해 범위를 지어내는 폴백이 있었으나,
                    그렇게 만든 숫자가 「L: ₩36,133」처럼 실제 저가인 것처럼 적혔다.
                    값이 없으면 없다고 적는 쪽이 낫다. 판정은 PriceRangeBar 가 한다. */}
                <PriceRangeBar
                  low={detail.priceInfo?.low}
                  high={detail.priceInfo?.high}
                  current={detail.priceInfo?.current}
                  label="1일 범위"
                />
                <PriceRangeBar
                  low={detail.yearRange?.low_52w}
                  high={detail.yearRange?.high_52w}
                  current={detail.priceInfo?.current}
                  label="52주 범위"
                />

                {/* Price Detail Grid */}
                <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 bg-[#1c1c1e] p-3 rounded-lg border border-white/5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">시가 (Open)</span>
                    <span className={`font-mono ${detail.priceInfo.open >= detail.priceInfo.prevClose ? 'text-rose-400' : 'text-blue-400'}`}>
                      {detail.priceInfo.open?.toLocaleString() || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">전일종가 (Prev)</span>
                    <span className="font-mono text-gray-300">
                      {detail.priceInfo.prevClose?.toLocaleString() || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">고가 (High)</span>
                    <span className="font-mono text-rose-400">
                      {detail.priceInfo.high?.toLocaleString() || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">저가 (Low)</span>
                    <span className="font-mono text-blue-400">
                      {detail.priceInfo.low?.toLocaleString() || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">거래량 (Vol)</span>
                    <span className="font-mono text-white">
                      {detail.priceInfo.volume?.toLocaleString() || '-'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500 flex items-center gap-1">
                      거래대금 (Val)
                      <Tooltip content="장이 시작한 뒤 지금까지 쌓인 거래대금이라 장이 끝날 때까지 계속 늘어납니다. 카드의 「거래대금」은 신호가 나온 거래일에 확정된 하루치이므로 두 값은 다릅니다. 등급 판정은 카드의 확정값을 씁니다.">
                        <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </span>
                    <span className="font-mono text-emerald-400">
                      {formatBigNumber(detail.priceInfo.trading_value)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Investment Indicators */}
              <div className="bg-white/5 rounded-xl p-4">
                <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <i className="fas fa-coins text-amber-400"></i> 투자 지표
                  <Tooltip content="기업의 가치평가, 수익성, 배당 정보입니다. 동일 업종 평균과 비교해서 판단하세요.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      시가총액
                      <Tooltip content="발행주식수 × 주가. 기업의 시장가치를 나타냅니다.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-white">{formatBigNumber(detail.indicators.marketCap)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      PER
                      <Tooltip content="주가수익비율. 주가 ÷ 주당순이익. 낮을수록 저평가, 업종 평균과 비교 필요.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-cyan-400">{detail.indicators.per?.toFixed(2) || '-'}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      PBR
                      <Tooltip content="주가순자산비율. 주가 ÷ 주당순자산. 1 미만이면 장부가치보다 저렴.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-cyan-400">{detail.indicators.pbr?.toFixed(2) || '-'}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      EPS
                      <Tooltip content="주당순이익. 순이익 ÷ 발행주식수. 높을수록 수익성 좋음.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-white">{detail.indicators.eps?.toLocaleString() || '-'}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      BPS
                      <Tooltip content="주당순자산. 순자산 ÷ 발행주식수. 청산가치의 기준.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-white">{detail.indicators.bps?.toLocaleString() || '-'}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      배당수익률
                      <Tooltip content="주당배당금 ÷ 주가 × 100. 배당으로 얻는 수익률.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-emerald-400">{detail.indicators.dividendYield?.toFixed(2) || '-'}%</div>
                  </div>
                </div>
              </div>

              {/* Investor Trend */}
              <div className="bg-white/5 rounded-xl p-4">
                <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <i className="fas fa-users text-purple-400"></i> 투자자 동향 (오늘 기준 5영업일)
                  <Tooltip content="오늘을 기준으로 최근 5영업일 동안 각 투자자 유형이 순매수하거나 순매도한 금액입니다. 선택한 날짜와 무관하게 늘 오늘 기준으로 집계하므로, 지난 날짜를 골랐다면 카드에 적힌 5일 순매수와 다릅니다. 외국인과 기관의 순매수는 호재로 해석됩니다. 개인은 집계처가 달라 세 값의 합이 맞지 않을 수 있습니다.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      외국인
                      <Tooltip content="외국인 투자자가 오늘 기준 최근 5영업일 동안 순매수한 금액입니다. 양수면 매수우위입니다. 카드의 「외인 (5일)」은 신호가 나온 거래일 기준이므로, 지난 날짜를 골랐다면 두 값이 다릅니다.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className={`text-sm font-bold ${foreign5Day >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                      {foreign5Day >= 0 ? '+' : ''}{formatBigNumber(foreign5Day)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      기관
                      <Tooltip content="기관 투자자(연기금, 자산운용사 등)가 오늘 기준 최근 5영업일 동안 순매수한 금액입니다. 카드의 「기관 (5일)」은 신호가 나온 거래일 기준이므로, 지난 날짜를 골랐다면 두 값이 다릅니다.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className={`text-sm font-bold ${institution5Day >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                      {institution5Day >= 0 ? '+' : ''}{formatBigNumber(institution5Day)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      개인
                      <Tooltip content="개인 투자자가 최근 5영업일 동안 순매수한 금액입니다. 보통 외국인·기관과 방향이 반대입니다. 이 값만 실시간 시세 제공처가 집계하므로 위의 외국인·기관과 기준일이 달라질 수 있습니다.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className={`text-sm font-bold ${detail.investorTrend.individual >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                      {detail.investorTrend.individual >= 0 ? '+' : ''}{formatBigNumber(detail.investorTrend.individual)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Financials */}
              {detail.financials && (
                <div className="bg-white/5 rounded-xl p-4">
                  <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <i className="fas fa-file-invoice-dollar text-emerald-400"></i> 재무 정보
                    <Tooltip content="최근 연간 실적 기준 매출, 영업이익, 순이익입니다. 성장 추세를 확인하세요.">
                      <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                    </Tooltip>
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                        매출액
                        <Tooltip content="상품/서비스 판매로 발생한 총 수익.">
                          <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                        </Tooltip>
                      </div>
                      <div className="text-sm font-bold text-white">{formatBigNumber(detail.financials.revenue)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                        영업이익
                        <Tooltip content="매출에서 영업비용을 뺀 금액. 본업 수익성 지표.">
                          <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                        </Tooltip>
                      </div>
                      <div className="text-sm font-bold text-white">{formatBigNumber(detail.financials.operatingProfit)}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                        순이익
                        <Tooltip content="모든 비용과 세금을 제외한 최종 이익.">
                          <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                        </Tooltip>
                      </div>
                      <div className="text-sm font-bold text-white">{formatBigNumber(detail.financials.netIncome)}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Safety Indicators */}
              <div className="bg-white/5 rounded-xl p-4">
                <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <i className="fas fa-shield-alt text-blue-400"></i> 안정성 지표
                  <Tooltip content="기업의 재무 건전성을 나타내는 지표입니다. 부채비율은 낮을수록, 유동비율은 높을수록 안정적입니다.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      부채비율
                      <Tooltip content="부채 ÷ 자본 × 100. 100% 미만이면 양호, 200% 이상은 주의.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-white">{detail.safety.debtRatio ? `${detail.safety.debtRatio.toFixed(1)}%` : '-'}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      유동비율
                      <Tooltip content="유동자산 ÷ 유동부채 × 100. 100% 이상이면 단기 지급능력 양호.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className="text-sm font-bold text-white">{detail.safety.currentRatio ? `${detail.safety.currentRatio.toFixed(1)}%` : '-'}</div>
                  </div>
                </div>
              </div>

              {/* External Links */}
              {/* External Links removed per user request */}
            </div>
          ) : null}
        </div>
    </ModalShell>
  );
}

export default function JonggaV2Page() {
  const bulkBuyReasonId = useId();
  const { isAdmin } = useAdmin();
  const { data: session, status } = useSession();
  const paperTradingAccountKey = status === 'authenticated' ? session?.user?.email ?? null : null;
  const isPaperTradingAuthenticated = Boolean(paperTradingAccountKey);
  const capturePaperTradingAction = useAccountActionGuard(paperTradingAccountKey);
  const [analyzingGemini, setAnalyzingGemini] = useState(false);
  const [retryingTicker, setRetryingTicker] = useState<string | null>(null);
  const [retryConfirmCode, setRetryConfirmCode] = useState<string | null>(null);
  const [data, setData] = useState<ScreenerResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('latest');
  const [refreshKey, setRefreshKey] = useState(0);
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [chartModal, setChartModal] = useState<{ isOpen: boolean, symbol: string, name: string }>({
    isOpen: false, symbol: '', name: ''
  });
  const [detailModal, setDetailModal] = useState<{ isOpen: boolean, code: string, name: string }>({
    isOpen: false, code: '', name: ''
  });
  const [gradeGuideOpen, setGradeGuideOpen] = useState(false);

  // Buy Modal State
  const [isBuyModalOpen, setIsBuyModalOpen] = useState(false);
  const [buyingStock, setBuyingStock] = useState<{ ticker: string; name: string; price: number } | null>(null);
  const [isBulkBuyingClosingBet, setIsBulkBuyingClosingBet] = useState(false);
  const [isClosingBetCriteriaModalOpen, setIsClosingBetCriteriaModalOpen] = useState(false);

  // Alert Modal State
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'success' | 'danger';
    title: string;
    content: string;
  }>({ isOpen: false, type: 'default', title: '', content: '' });

  const showPaperTradingLoginRequired = () => {
    setAlertModal({
      isOpen: true,
      type: 'default',
      title: '로그인 필요',
      content: '모의투자는 로그인 후 사용할 수 있습니다.',
    });
  };

  useLayoutEffect(() => {
    setIsBuyModalOpen(false);
    setBuyingStock(null);
    setIsBulkBuyingClosingBet(false);
    setAlertModal((current) => current.title.includes('매수') || current.title === '로그인 필요'
      ? { ...current, isOpen: false }
      : current);
  }, [paperTradingAccountKey]);

  // Tips Collapse State

  // Tips Collapse State
  const [isTipsOpen, setIsTipsOpen] = useState(false);

  // Filters
  const [filterTradingValue, setFilterTradingValue] = useState(0);
  const [filterRise, setFilterRise] = useState(0);
  const [filterGrade, setFilterGrade] = useState<string>('ALL');
  const [filterScore, setFilterScore] = useState(0);

  const formatFilterTradingValue = (value: number) => {
    if (value >= 1_000_000_000_000) return `${Math.floor(value / 1_000_000_000_000)}조 이상`;
    if (value >= 100_000_000) return `${Math.floor(value / 100_000_000)}억 이상`;
    return `${value.toLocaleString()}원 이상`;
  };

  const resetSignalFilters = () => {
    setFilterTradingValue(0);
    setFilterRise(0);
    setFilterGrade('ALL');
    setFilterScore(0);
  };

  const getFilteredSignals = () => {
    if (!data?.signals) return [];
    return data.signals.filter(s => {
      // 1. Trading Value Filter
      if (filterTradingValue > 0 && s.trading_value < filterTradingValue) return false;

      // 2. Rise % Filter
      const rise = s.score_details?.rise_pct ?? s.change_pct;
      if (filterRise > 0 && rise < filterRise) return false;

      // 3. Grade Filter
      if (filterGrade !== 'ALL') {
        const gradeWeight: Record<string, number> = { 'S': 3, 'A': 2, 'B': 1 };
        const sGrade = String(s.grade || '').trim().toUpperCase();
        const fGrade = String(filterGrade || '').trim().toUpperCase();
        const sWeight = gradeWeight[sGrade] ?? -1;
        const fWeight = gradeWeight[fGrade] ?? -1;

        if (sWeight < fWeight) return false;
      }

      // 4. Total Score Filter
      if (filterScore > 0 && s.score.total < filterScore) return false;

      return true;
    });
  };

  const filteredSignals = getFilteredSignals();
  const matchCount = filteredSignals.length;
  const totalSignalCount = data?.signals?.length ?? 0;
  const activeFilterLabels = [
    filterTradingValue > 0 ? `거래대금 ${formatFilterTradingValue(filterTradingValue)}` : null,
    filterRise > 0 ? `상승률 ${filterRise}% 이상` : null,
    filterGrade !== 'ALL' ? `${filterGrade}급 이상` : null,
    filterScore > 0 ? `총점 ${filterScore}점 이상` : null,
  ].filter((label): label is string => Boolean(label));
  const hasActiveFilters = activeFilterLabels.length > 0;
  const candidatesCount = data?.total_candidates ?? 0;
  const filteredCount = data?.filtered_count ?? data?.signals?.length ?? 0;

  // 이 조작은 DATA STATUS 의 「GEMINI AI 재분석」과 같은 엔드포인트를 부르므로 같은
  // 비용이 든다. 카드마다 있어서 오히려 실수로 누르기 쉬우므로 같은 확인 절차를 거친다.
  const requestRetryAnalysis = (stockCode: string) => {
    if (!isAdmin) {
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '권한 없음',
        content: '관리자만 실행할 수 있습니다.'
      });
      return;
    }

    if (analyzingGemini) return;

    setRetryConfirmCode(stockCode);
  };

  const handleRetryAnalysis = async (stockCode: string) => {
    setRetryConfirmCode(null);
    setAnalyzingGemini(true);
    setRetryingTicker(stockCode);
    try {
      await fetchAPI('/api/kr/jongga-v2/reanalyze-gemini', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_tickers: [stockCode] }),
        timeout: 120000 // 120s timeout for LLM
      });
      setRefreshKey(prev => prev + 1);
    } catch (error: any) {
      console.error('개별 분석 실패', error);
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '분석 실패',
        content: '재분석 실패: ' + (error.message || 'Unknown error')
      });
    } finally {
      setAnalyzingGemini(false);
      setRetryingTicker(null);
    }
  };

  const isLatestReportToday = (() => {
    if (!data?.updated_at) return false;
    try {
      const todayKst = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date());
      const updatedKst = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date(data.updated_at));
      return todayKst === updatedKst;
    } catch {
      return selectedDate === 'latest';
    }
  })();

  // 날짜 조건은 일괄 매수와 카드별 매수가 함께 쓴다. 한쪽만 막으면 개별 주문을 종목 수만큼
  // 반복해 일괄 매수가 막으려던 결과에 그대로 도달한다.
  const buyDisabledReason = (() => {
    if (selectedDate !== 'latest') return 'Latest Report(최신 리포트)에서만 매수를 실행할 수 있습니다.';
    if (!isLatestReportToday) return '현재 최신 리포트가 오늘 데이터가 아닙니다.';
    return '';
  })();

  const bulkBuyClosingBetDisabledReason = (() => {
    if (isBulkBuyingClosingBet) return '종가베팅 일괄 매수를 진행 중입니다.';
    if (loading) return '종가베팅 데이터를 불러오는 중입니다.';
    if (buyDisabledReason) return buyDisabledReason;
    if (!data?.signals?.length) return '오늘 종가베팅 매수 대상 종목이 없습니다.';
    return '';
  })();

  const isBulkBuyClosingBetDisabled = Boolean(bulkBuyClosingBetDisabledReason);

  const bulkBuyClosingBetTooltip = bulkBuyClosingBetDisabledReason || '오늘 종가베팅 종목 전체를 10주씩 매수합니다.';

  const handleBulkBuyClosingBet = async () => {
    if (!isPaperTradingAuthenticated) {
      showPaperTradingLoginRequired();
      return;
    }
    if (isBulkBuyingClosingBet) return;
    const isCurrent = capturePaperTradingAction();
    if (buyDisabledReason) {
      setAlertModal({
        isOpen: true,
        type: 'default',
        title: '오늘 데이터만 가능',
        content: buyDisabledReason
      });
      return;
    }

    const sourceSignals = (data?.signals || []).filter((signal) => String(signal.grade || '').toUpperCase() !== 'D');
    if (sourceSignals.length === 0) {
      setAlertModal({
        isOpen: true,
        type: 'default',
        title: '매수 대상 없음',
        content: '오늘 종가베팅 매수 대상 종목이 없습니다.'
      });
      return;
    }

    const uniqueTargets = new Map<string, { ticker: string; name: string; price: number }>();
    sourceSignals.forEach((signal) => {
      const ticker = signal.stock_code;
      if (!ticker || uniqueTargets.has(ticker)) return;
      const price = signal.current_price || signal.buy_price || signal.entry_price || 0;
      uniqueTargets.set(ticker, {
        ticker,
        name: signal.stock_name,
        price
      });
    });

    setIsBulkBuyingClosingBet(true);
    let successCount = 0;
    let failCount = 0;
    let skippedCount = 0;
    const failedItems: string[] = [];

    try {
      const buyOrders: Array<{ ticker: string; name: string; price: number; quantity: number }> = [];
      for (const target of uniqueTargets.values()) {
        if (!Number.isFinite(target.price) || target.price <= 0) {
          skippedCount += 1;
          failedItems.push(`${target.name}(가격 정보 없음)`);
          continue;
        }
        buyOrders.push({
          ticker: target.ticker,
          name: target.name,
          price: target.price,
          quantity: 10
        });
      }

      if (buyOrders.length > 0) {
        try {
          const result = await paperTradingAPI.bulkBuy(buyOrders);
          if (!isCurrent()) return;
          const resultRows = Array.isArray(result?.results) ? result.results : [];

          if (resultRows.length > 0) {
            resultRows.forEach((row) => {
              const rowName = row?.name || row?.ticker || '종목';
              if (row?.status === 'success') {
                successCount += 1;
              } else {
                failCount += 1;
                failedItems.push(`${rowName}(${row?.message || '매수 실패'})`);
              }
            });
          } else if (result?.status === 'success') {
            successCount += buyOrders.length;
          } else {
            failCount += buyOrders.length;
            failedItems.push(`일괄 매수(${result?.message || '매수 실패'})`);
          }
          } catch (error: unknown) {
            if (!isCurrent()) return;
            console.error('[Closing Bet Bulk Buy] bulk buy failed:', error);
            if (isAuthenticationError(error)) {
              showPaperTradingLoginRequired();
              return;
            }
            failCount += buyOrders.length;
            failedItems.push('일괄 매수(요청 오류)');
        }
      }

      const summary: string[] = [`성공 ${successCount}건`];
      if (failCount > 0) summary.push(`실패 ${failCount}건`);
      if (skippedCount > 0) summary.push(`스킵 ${skippedCount}건`);
      const failedPreview = failedItems.slice(0, 3).join(', ');
      const failedSuffix = failedItems.length > 3 ? ' 외' : '';
      const resultType: 'default' | 'success' | 'danger' =
        failCount > 0 ? (successCount > 0 ? 'default' : 'danger') : (successCount > 0 ? 'success' : 'default');

      setAlertModal({
        isOpen: true,
        type: resultType,
        title: '종가베팅 일괄 매수 결과',
        content: `오늘 종가베팅 종목 10주씩 매수 완료\n${summary.join(' / ')}${failedPreview ? `\n실패/스킵: ${failedPreview}${failedSuffix}` : ''}`
      });
    } finally {
      if (isCurrent()) setIsBulkBuyingClosingBet(false);
    }
  };

  useEffect(() => {
    fetchAPI('/api/kr/jongga-v2/dates')
      .then((data: any) => {
        if (Array.isArray(data)) {
          setDates(data);
        }
      })
      .catch((err) => console.error('Failed to fetch dates:', err));
  }, []);

  useEffect(() => {
    // Safety Force Timeout
    const safetyTimer = setTimeout(() => {
      setLoading(prev => {
        if (prev) {
          console.error("Force safety timeout triggered for Closing Bet data load");
          return false;
        }
        return prev;
      });
    }, 15000); // 15s absolute max wait

    setLoading(true);
    let url = '/api/kr/jongga-v2/latest';
    if (selectedDate !== 'latest') {
      url = `/api/kr/jongga-v2/history/${selectedDate}`;
    }

    fetchAPI(url)
      .then((data: any) => {
        // [Auto-Recovery] If initializing, retry in 5s
        if (selectedDate === 'latest' && (data?.status === 'initializing' || data?.message?.includes('분석 중'))) {
          if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
          retryTimerRef.current = setTimeout(() => {
            setRefreshKey(prev => prev + 1);
          }, 5000);
          // Do NOT set loading to false, keep spinning
          return;
        }

        setData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch data:', err);

        // [Fix] 404 Not Found (데이터 없음)인 경우 무한 재시도 방지
        if (err.status === 404 || err.message?.includes('404')) {
          console.warn('Data not found (404). Stopping retry.');
          setLoading(false);
          setData(null); // Explicitly set null to trigger "No Data" UI
          return;
        }

        // [Auto-Recovery] Retry on other errors (e.g. timeout, 500)
        if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
        retryTimerRef.current = setTimeout(() => {
          setRefreshKey(prev => prev + 1);
        }, 5000);
        // Keep loading true so user sees spinner, not empty state
        // setLoading(false); 
      })
      .finally(() => {
        clearTimeout(safetyTimer);
      });

    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      clearTimeout(safetyTimer);
    };
  }, [selectedDate, refreshKey]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center text-gray-500">
        <div className="relative w-16 h-16">
          <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-500/30 rounded-full animate-ping"></div>
          <div className="absolute top-0 left-0 w-full h-full border-4 border-t-blue-500 rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Header with Trending Themes */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 text-xs text-gray-400 font-medium mb-2">
            <i className="fas fa-robot text-indigo-400"></i>
            스마트 머니 봇
          </div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/20 bg-indigo-500/5 text-xs text-indigo-400 font-medium mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping"></span>
            AI 기반 전략
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
            종가 <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">베팅</span>
          </h1>
          <p className="text-gray-400 text-lg">
            Gemini 분석 + 기관 수급 추세
          </p>
        </div>

        {/* TRENDING THEMES Box */}
        <TrendingThemesBox themes={getTrendingThemes(filteredSignals)} />
      </div>

      <div className="flex flex-col gap-6 pb-6 border-b border-white/5">
        <div className="flex gap-6">
          <StatBox label="CANDIDATES" value={candidatesCount} tooltip="시장에서 1차 필터링된 후보 종목 수입니다." />
          <StatBox label="FILTERED" value={filteredCount} highlight tooltip="AI 조건에 의해 최종 선별된 종목 수입니다." />
          <DataStatusBox
            updatedAt={data?.updated_at || null}
            loading={loading}
            analyzingGemini={analyzingGemini}
            setAnalyzingGemini={setAnalyzingGemini}
            onRefresh={() => setRefreshKey(prev => prev + 1)}
          />
        </div>

        {selectedDate === 'latest' && (data?.is_stale || data?.status === 'stale' || data?.stale_warning) && (
          <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            <div className="flex items-start gap-3">
              <i className="fas fa-triangle-exclamation mt-0.5 text-amber-300"></i>
              <div>
                <div className="font-semibold">오늘 종가베팅 데이터가 아직 없습니다.</div>
                <div className="mt-1 text-amber-100/80">
                  {data?.stale_warning || data?.message || `최신 저장 데이터는 ${data?.latest_available_date || data?.date}입니다.`}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 w-full">
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {/* [MOVED] VCP 기준표 버튼 removed from here */}

            {/* Trading Value Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                거래대금
                <Tooltip content="하루 동안 거래된 총 금액입니다. 거래대금이 클수록 유동성이 좋고 기관의 관심을 받는 종목입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
                aria-label="거래대금"
                value={filterTradingValue}
                onChange={(e) => setFilterTradingValue(Number(e.target.value))}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterTradingValue > 0 ? 'border-indigo-500 text-indigo-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value={0}>전체</option>
                <option value={100000000000}>1000억 이상</option>
                <option value={500000000000}>5000억 이상</option>
                <option value={1000000000000}>1조 이상</option>
              </select>
            </div>

            {/* Rise % Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                상승률
                <Tooltip content="전일 종가 대비 상승률입니다. 5% 이상이면 강세, 10% 이상이면 급등 신호입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
                aria-label="상승률"
                value={filterRise}
                onChange={(e) => setFilterRise(Number(e.target.value))}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterRise > 0 ? 'border-rose-500 text-rose-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value={0}>전체</option>
                <option value={2}>2% 이상</option>
                <option value={3}>3% 이상</option>
                <option value={5}>5% 이상 (Standard)</option>
                <option value={7}>7% 이상</option>
                <option value={10}>10% 이상 (Strong)</option>
                <option value={15}>15% 이상 (Very Strong)</option>
                <option value={20}>20% 이상 (Super)</option>
                <option value={25}>25% 이상 (Limit)</option>
              </select>
            </div>

            {/* Grade Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                등급
                <Tooltip content="AI가 평가한 종합 등급입니다. S(최고), A(우수), B(양호) 순서입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
                <button
                  onClick={() => setGradeGuideOpen(true)}
                  className="ml-1 text-[8px] px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors"
                >
                  기준표
                </button>
              </div>
              <select
                aria-label="등급"
                value={filterGrade}
                onChange={(e) => setFilterGrade(e.target.value)}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterGrade !== 'ALL' ? 'border-purple-500 text-purple-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value="ALL">전체</option>
                <option value="S">S급 이상</option>
                <option value="A">A급 이상</option>
                <option value="B">B급 이상</option>
              </select>
            </div>

            {/* Score Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                총점
                <Tooltip content="기본 6개 항목 12점과 가산점 7점을 더한 총점입니다. 최대 19점, 8점 이상이면 강한 신호입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
                aria-label="총점"
                value={filterScore}
                onChange={(e) => setFilterScore(Number(e.target.value))}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterScore > 0 ? 'border-emerald-500 text-emerald-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value={0}>전체</option>
                <option value={4}>4점 이상</option>
                <option value={8}>8점 이상</option>
                <option value={10}>10점 이상</option>
              </select>
            </div>
          </div>

          {hasActiveFilters && (
            <div className="w-full md:w-auto flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-gray-400">
              <span className="font-medium text-gray-300">
                표시 {matchCount} / 전체 {totalSignalCount}
              </span>
              {activeFilterLabels.map((label) => (
                <span key={label} className="rounded-full border border-indigo-500/25 bg-indigo-500/10 px-2 py-0.5 text-indigo-200">
                  {label}
                </span>
              ))}
              <button
                type="button"
                onClick={resetSignalFilters}
                className="ml-auto rounded-full border border-white/10 px-2 py-0.5 text-gray-300 hover:border-white/20 hover:bg-white/10 hover:text-white transition-colors"
              >
                필터 초기화
              </button>
            </div>
          )}

          <div className="flex items-center gap-3 md:ml-auto">
            <div className="hidden md:block h-6 w-px bg-white/10 mx-2"></div>

            <div className="flex flex-col items-end gap-1">
              <Tooltip content={bulkBuyClosingBetTooltip} position="top" align="right" size="md">
                <button
                  onClick={handleBulkBuyClosingBet}
                  disabled={isBulkBuyClosingBetDisabled}
                  aria-describedby={isBulkBuyClosingBetDisabled ? bulkBuyReasonId : undefined}
                  className="px-3 py-1.5 bg-amber-500/15 hover:bg-amber-500/30 text-amber-300 hover:text-amber-200 rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 border border-amber-400/30 disabled:opacity-40 disabled:cursor-not-allowed"
                  title={bulkBuyClosingBetTooltip}
                >
                  <i className={`fas ${isBulkBuyingClosingBet ? 'fa-circle-notch fa-spin' : 'fa-cart-shopping'}`}></i>
                  <span>{isBulkBuyingClosingBet ? '일괄 매수 중...' : '종가베팅 전체 10주 매수'}</span>
                </button>
              </Tooltip>
              {isBulkBuyClosingBetDisabled && (
                <p id={bulkBuyReasonId} className="max-w-64 text-right text-[10px] leading-relaxed text-amber-300">
                  {bulkBuyClosingBetDisabledReason}
                </p>
              )}
            </div>

            {/* 종가베팅 점수표 버튼 */}
            <button
              onClick={() => setIsClosingBetCriteriaModalOpen(true)}
              className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 border border-white/10"
            >
              <i className="fas fa-table"></i> 종가베팅 점수표
            </button>

            <Tooltip content="이전 리포트 기록을 조회할 수 있습니다. Latest Report는 가장 최신 데이터를 보여줍니다." position="bottom" align="right" size="md">
              <select
                aria-label="리포트 날짜"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="bg-[#1c1c1e] border border-white/10 text-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all hover:border-white/20 w-full md:w-auto"
              >
                <option value="latest">Latest Report</option>
                {dates.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </Tooltip>
            <Tooltip content="현재 선택된 날짜의 데이터를 다시 불러옵니다." position="bottom" align="right">
              {/* 종전에는 setSelectedDate(selectedDate) 였다. 같은 값이므로 React 가 상태
                  갱신을 건너뛰어 조회 이펙트가 다시 돌지 않았고 버튼이 죽어 있었다. 이름을
                  붙이면서 하지 않는 일을 약속하게 되므로 여기서 함께 고친다. */}
              <button
                onClick={() => setRefreshKey(prev => prev + 1)}
                aria-label="선택한 날짜의 리포트 다시 불러오기"
                className="p-2 bg-[#1c1c1e] border border-white/10 rounded-xl hover:bg-white/5 text-gray-400 hover:text-white transition-all"
              >
                <i className="fas fa-sync-alt"></i>
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Collapsible Tips Section */}
      <div className="mb-8">
        <button
          onClick={() => setIsTipsOpen(!isTipsOpen)}
          className="w-full flex items-center justify-between p-4 bg-[#1c1c1e] hover:bg-white/5 border border-white/5 rounded-2xl transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${isTipsOpen ? 'bg-indigo-500/20 text-indigo-400' : 'bg-white/5 text-gray-400 group-hover:text-yellow-400'}`}>
              <i className="fas fa-lightbulb"></i>
            </div>
            <div className="text-left">
              <h2 className={`text-sm font-bold ${isTipsOpen ? 'text-white' : 'text-gray-400 group-hover:text-gray-200'}`}>
                Trading Tips & Strategy
              </h2>
              {!isTipsOpen && (
                <p className="text-[10px] text-gray-500 mt-0.5">
                  시장 대응 전략 및 종가베팅 매수 패턴 가이드 보기
                </p>
              )}
            </div>
          </div>
          <i className={`fas fa-chevron-down text-gray-500 transition-transform duration-300 ${isTipsOpen ? 'rotate-180' : ''}`}></i>
        </button>

        {isTipsOpen && (
          <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
            {/* Market Adaptation Tips */}
            <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl p-4">
              <h3 className="text-sm font-bold text-indigo-300 mb-2 flex items-center gap-2">
                <i className="fas fa-compass"></i> Market Adaptation Strategy
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-400">
                <div>
                  <strong className="text-white block mb-1">Target Selection</strong>
                  <ul className="list-disc list-inside space-y-1">
                    <li><span className="text-indigo-400">KOSPI</span>: 시총 대형주 + 거래대금 1000억 이상 (추세 지속)</li>
                    <li><span className="text-rose-400">KOSDAQ</span>: 알짜 중소형주 (200~500억) 변동성 활용</li>
                    <li><span className="text-amber-400">Bull Market</span>: 코스피 5000 등 대상승장엔 S등급 주도주만 집중</li>
                  </ul>
                </div>
                <div>
                  <strong className="text-white block mb-1">Execution Timing</strong>
                  <ul className="list-disc list-inside space-y-1">
                    <li><span className="text-emerald-400">Entry</span>: 15:10 ~ 15:30 (종가 부근), 눌림목 지지 확인 필수</li>
                    <li><span className="text-rose-400">Profit</span>: 시그널 목표가 도달 여부로 판정 (누락 시 진입가 대비 기본 +5%)</li>
                    <li><span className="text-gray-400">Stop</span>: 시그널 손절가 도달 여부로 판정 (누락 시 진입가 대비 기본 -3%)</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Closing Bet Buy Daily Patterns */}
            <div className="bg-[#1c1c1e] border border-white/5 rounded-2xl p-5">
              <h3 className="text-sm font-bold text-gray-200 mb-4 flex items-center gap-2">
                <span className="w-1 h-4 bg-emerald-500 rounded-full"></span>
                종가베팅 매수 일봉 패턴
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h4 className="text-xs font-bold text-emerald-400 mb-2">1) 신고가 조정 후 반등</h4>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 신고가 돌파 → 10~40일 20일선 지지 조정 → 매물 소화 → 거래량 터진 양봉(윗꼬리 짧음)</p>
                    <p>• <strong>타이밍</strong>: 전고점 근처 깔끔한 양봉 종가</p>
                  </div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h4 className="text-xs font-bold text-emerald-400 mb-2">2) 장대양봉 후 5일선 지지</h4>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 장대양봉 → 다음날 음봉에도 5일선 위 버팀 → 관찰 → 5일선 지지 양봉</p>
                    <p>• <strong>특징</strong>: 재료 좋은 종목, 장대양봉 다음날 대량 음봉 OK</p>
                  </div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h4 className="text-xs font-bold text-emerald-400 mb-2">3) 엔벨로프 돌파 후 7일선 지지</h4>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 엔벨로프 20/40선 돌파 → 연속 시세 → 7일선(or 15일선) 지지</p>
                    <p>• <strong>의미</strong>: 단발성 아닌 연속성 재료 확정</p>
                  </div>
                </div>
              </div>

              <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3">
                <h4 className="text-xs font-bold text-indigo-300 mb-2 flex items-center gap-1">
                  <i className="fas fa-check-circle"></i> 공통 조건
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-gray-300">
                  <div className="flex items-center gap-1.5"><span className="text-indigo-500">•</span> <span>거래대금 1,000억↑ + 외인/기관 양매수</span></div>
                  <div className="flex items-center gap-1.5"><span className="text-indigo-500">•</span> <span>고점비율 90%↑ 종가 (상한가 제외)</span></div>
                  <div className="flex items-center gap-1.5"><span className="text-indigo-500">•</span> <span>외인/기관 양매수 (수급 확인 필수)</span></div>
                  <div className="flex items-center gap-1.5"><span className="text-indigo-500">•</span> <span>(20일선 OR 5일선 OR 7일선 지지) 패턴 부합</span></div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6">
        {!data || filteredSignals.length === 0 ? (
          <div className="bg-[#1c1c1e] rounded-2xl p-16 text-center border border-white/5 flex flex-col items-center">
            <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4">
              <span className="text-3xl opacity-30">💤</span>
            </div>
            <h2 className="text-xl font-bold text-gray-300">No Signals Found</h2>
            <p className="text-gray-500 mt-2 max-w-md">
              Try adjusting filters or wait for market conditions to improve.
            </p>
          </div>
        ) : (
          filteredSignals
            .filter(s => s.grade !== 'D') // D등급 원천 필터링 (안전장치)
            .map((signal, idx) => (
              <SignalCard
                key={`${signal.stock_code}-${idx}`}
                signal={signal}
                index={idx}
                onOpenChart={() => setChartModal({ isOpen: true, symbol: signal.stock_code, name: signal.stock_name })}
                onOpenDetail={() => setDetailModal({ isOpen: true, code: signal.stock_code, name: signal.stock_name })}
                onBuy={() => {
                  setBuyingStock({ ticker: signal.stock_code, name: signal.stock_name, price: signal.current_price || signal.entry_price || 0 });
                  setIsBuyModalOpen(true);
                }}
                onRetry={requestRetryAnalysis}
                isRetrying={retryingTicker === signal.stock_code}
                isAdmin={isAdmin}
                buyDisabledReason={buyDisabledReason}
              />
            ))
        )}
      </div>

      <div className="text-center text-xs text-gray-600 pt-8">
        Engine: v2.0.1 (Gemini Flash) • Updated: {data?.updated_at || '-'}
      </div>

      {chartModal.isOpen && (
        <ChartModal
          symbol={chartModal.symbol}
          name={chartModal.name}
          onClose={() => setChartModal({ ...chartModal, isOpen: false })}
        />
      )}
      {detailModal.isOpen && (
        <StockDetailModal
          code={detailModal.code}
          name={detailModal.name}
          onClose={() => setDetailModal({ ...detailModal, isOpen: false })}
        />
      )}

      <GradeGuideModal
        isOpen={gradeGuideOpen}
        onClose={() => setGradeGuideOpen(false)}
      />

      <BuyStockModal
        isOpen={isBuyModalOpen}
        onClose={() => setIsBuyModalOpen(false)}
        stock={buyingStock}
        onBuy={async (ticker, name, price, quantity) => {
          const isCurrent = capturePaperTradingAction();
          try {
            const data = await paperTradingAPI.buy({ ticker, name, price, quantity });
            if (!isCurrent()) return false;
            if (data.status === 'success') {
              setAlertModal({
                isOpen: true,
                type: 'success',
                title: '매수 완료',
                content: `${name} ${quantity}주 매수 완료!`
              });
              return true;
            } else {
              setAlertModal({
                isOpen: true,
                type: 'danger',
                title: '매수 실패',
                content: `매수 실패: ${data.message}`
              });
              return false;
            }
          } catch (e: unknown) {
            if (!isCurrent()) return false;
            console.error('Buy error:', e);
            setAlertModal({
              isOpen: true,
              type: 'danger',
              title: isAuthenticationError(e) ? '로그인 필요' : '오류',
              content: isAuthenticationError(e) ? '모의투자는 로그인 후 사용할 수 있습니다.' : '매수 중 오류가 발생했습니다.'
            });
            return false;
          }
        }}
      />

      {/* 카드별 재분석의 확인 모달. DATA STATUS 의 두 조작과 같은 비용이 든다 */}
      <ConfirmationModal
        isOpen={retryConfirmCode !== null}
        title="이 종목만 재분석"
        message={costlyMessage(`${retryConfirmCode ?? ''} 한 종목을 Gemini AI 로 다시 분석합니다.`)}
        confirmText="실행"
        onCancel={() => setRetryConfirmCode(null)}
        onConfirm={() => retryConfirmCode && handleRetryAnalysis(retryConfirmCode)}
      />

      {/* Alert Modal */}
      <Modal
        isOpen={alertModal.isOpen}
        onClose={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
        title={alertModal.title}
        type={alertModal.type}
        footer={
          <button
            onClick={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
            className={`px-4 py-2 rounded-lg text-sm font-bold text-white transition-colors ${alertModal.type === 'danger' ? 'bg-red-500 hover:bg-red-600' :
              alertModal.type === 'success' ? 'bg-emerald-500 hover:bg-emerald-600' :
                'bg-blue-500 hover:bg-blue-600'
              }`}
          >
            확인
          </button>
        }
      >
        <p>{alertModal.content}</p>
      </Modal>

      {/* 종가베팅 점수표 Modal */}
      <ClosingBetCriteriaModal
        isOpen={isClosingBetCriteriaModalOpen}
        onClose={() => setIsClosingBetCriteriaModalOpen(false)}
      />
    </div>
  );
}

function DataStatusBox({ updatedAt, loading, analyzingGemini, setAnalyzingGemini, onRefresh }: {
  updatedAt: string | null,
  loading: boolean,
  analyzingGemini: boolean,
  setAnalyzingGemini: (v: boolean) => void,
  onRefresh: () => void,
}) {
  const [updating, setUpdating] = useState(false);
  const [runningMessage, setRunningMessage] = useState('');
  const [currentUpdatedAt, setCurrentUpdatedAt] = useState(updatedAt);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingGenerationRef = useRef(0);
  const pollingRequestActiveRef = useRef(false);
  const isMountedRef = useRef(false);

  // ADMIN 권한 체크
  const { isAdmin } = useAdmin();
  const [permissionModal, setPermissionModal] = useState(false);
  const [confirmAction, setConfirmAction] = useState<CostlyAction | null>(null);
  const [alertModal, setAlertModal] = useState<{
    isOpen: boolean;
    type: 'default' | 'success' | 'danger';
    title: string;
    content: string;
  }>({ isOpen: false, type: 'default', title: '', content: '' });

  // updatedAt props가 변경되면 내부 상태도 업데이트 (초기화용)
  useEffect(() => {
    setCurrentUpdatedAt(updatedAt);
  }, [updatedAt]);

  const stopPolling = useCallback(() => {
    pollingGenerationRef.current += 1;
    pollingRequestActiveRef.current = false;
    if (pollingIntervalRef.current !== null) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (pollingTimeoutRef.current !== null) {
      clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  const pollStatus = useCallback(() => {
    if (!isMountedRef.current) return;

    stopPolling();
    const generation = pollingGenerationRef.current;
    const isCurrentPolling = () => (
      isMountedRef.current && pollingGenerationRef.current === generation
    );
    const checkStatus = async () => {
      if (!isCurrentPolling() || pollingRequestActiveRef.current) return;
      pollingRequestActiveRef.current = true;
      try {
        // 변경: 상태 전용 엔드포인트 폴링
        const res: any = await fetchAPI('/api/kr/jongga-v2/status');
        const data = res; // fetchAPI returns JSON directly
        if (!isCurrentPolling()) return;
        const isRunning = Boolean(data?.isRunning ?? data?.is_running);

        if (data) {
          // 실행 중이면 계속 폴링
          if (isRunning) {
            setUpdating(true);
            if (data.message) {
              setRunningMessage(String(data.message));
            } else {
              setRunningMessage('종가베팅 스케쥴링 진행 중인 상태');
            }
          } else {
            // 완료는 runUpdate 렌더 당시의 updating 값이 아니라 현재 polling 세대가 판정한다.
            stopPolling();
            setUpdating(false);
            setRunningMessage('');
            onRefresh();
          }
        }
      } catch (error) {
        if (isCurrentPolling()) console.error('Polling error:', error);
      } finally {
        if (isCurrentPolling()) pollingRequestActiveRef.current = false;
      }
    };

    pollingIntervalRef.current = setInterval(() => {
      void checkStatus();
    }, 2000); // 2초마다 체크 (반응성 향상)

    // 5분 후에는 폴링 중단 (안전장치)
    pollingTimeoutRef.current = setTimeout(() => {
      if (!isCurrentPolling()) return;
      stopPolling();
      setUpdating(false);
      setRunningMessage('');
    }, 350000);
  }, [onRefresh, stopPolling]);

  // 조회가 끝났는데도 updatedAt이 없으면 데이터가 없는 것이므로 LOADING에 머물지 않는다.
  if (!updatedAt && !updating && !analyzingGemini) {
    return <StatBox label="Data Status" value={0} customValue={loading ? 'LOADING...' : 'NO DATA'} />;
  }

  const updateDate = updatedAt ? new Date(updatedAt) : new Date();
  const today = new Date();
  const isToday = updatedAt ? (
    updateDate.getDate() === today.getDate() &&
    updateDate.getMonth() === today.getMonth() &&
    updateDate.getFullYear() === today.getFullYear()
  ) : false;

  const timeStr = updateDate.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

  // ... (existing code)

  // 버튼은 곧바로 실행하지 않고 확인 모달만 연다. 권한과 중복 실행 검사는 두 조작이
  // 같으므로 이 자리에 모은다.
  const requestCostlyAction = (action: CostlyAction) => {
    if (!isAdmin) {
      setPermissionModal(true);
      return;
    }
    if (updating || analyzingGemini) return;
    setConfirmAction(action);
  };

  const runUpdate = async () => {
    setRunningMessage('');
    setUpdating(true);
    try {
      // fetchAPI를 사용하여 타임아웃 적용 (엔진 실행은 오래 걸릴 수 있으므로 타임아웃 넉넉히 주거나, 비동기 확인만 하므로 기본값 사용)
      const res = await fetchAPI('/api/kr/jongga-v2/run', { method: 'POST' });
      // fetchAPI throws on error, so we catch it below. 
      // Note: fetchAPI returns the parsed JSON if successful.
      // However, the original code checks res.ok or res.status which fetchAPI masks by throwing on error.
      // We need to adjust usage or assumption. 
      // fetchAPI signature: async function fetchAPI<T = any>(url: string, options: RequestInit = {}): Promise<T>
      // It returns data directly and throws error with status attached if possible.

      pollStatus();

    } catch (error: any) {
      if (error.status === 409) {
        pollStatus();
      } else {
        console.error('업데이트 요청 중 오류 발생', error);
        setUpdating(false);
        setRunningMessage('');
      }
    }
  };

  const runGeminiReanalyze = async () => {
    setAnalyzingGemini(true);
    try {
      await fetchAPI('/api/kr/jongga-v2/reanalyze-gemini', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        timeout: 240000 // 4분 (Global은 오래 걸림)
      });
      onRefresh();
    } catch (error: any) {
      console.error('Gemini 분석 요청 중 오류 발생', error);
      setAlertModal({
        isOpen: true,
        type: 'danger',
        title: '분석 실패',
        content: error.message || '분석 중 오류가 발생했습니다.'
      });
      // alert(error.message || '분석 실패');
    } finally {
      setAnalyzingGemini(false);
    }
  };

  const runCostlyAction = (action: CostlyAction) => {
    setConfirmAction(null);
    if (action === 'update') runUpdate();
    else runGeminiReanalyze();
  };

  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1 flex items-center gap-2">
        Data Status
        <Tooltip content="스크리너 엔진을 실행하여 모든 종목에 대해 전체 업데이트(뉴스, 수급, 점수 등)를 수행합니다." position="bottom" align="right" size="md">
          <button
            onClick={() => requestCostlyAction('update')}
            disabled={updating || analyzingGemini}
            aria-label={COSTLY_ACTIONS.update.name}
            className={`p-1 rounded bg-white/5 hover:bg-white/10 transition-all ${updating ? 'animate-spin text-indigo-400' : 'text-gray-500 hover:text-white'}`}
          >
            <i className="fas fa-sync-alt text-[10px]"></i>
          </button>
        </Tooltip>
        <Tooltip content="기존 데이터를 기반으로 Gemini AI를 재호출합니다. 전체 실행 시 미분석/실패 항목만 재분석됩니다." position="bottom" align="right" size="md">
          <button
            onClick={() => requestCostlyAction('gemini')}
            disabled={updating || analyzingGemini}
            aria-label={COSTLY_ACTIONS.gemini.name}
            className={`p-1 rounded bg-white/5 hover:bg-white/10 transition-all ${analyzingGemini ? 'text-purple-400' : 'text-gray-500 hover:text-purple-400'}`}
          >
            <i className={`fas fa-brain text-[10px] ${analyzingGemini ? 'animate-spin' : ''}`}></i>
          </button>
        </Tooltip>
      </span>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${(isToday && !updating && !analyzingGemini) ? 'bg-emerald-500 animate-pulse' : 'bg-gray-500'}`}></span>
        <span className={`text-xl font-mono font-bold ${(isToday && !updating && !analyzingGemini) ? 'text-emerald-400' : 'text-gray-400'}`}>
          {updating ? 'RUNNING...' : analyzingGemini ? 'ANALYZING...' : (isToday ? 'UPDATED' : 'OLD DATA')}
        </span>
      </div>

      <span className="text-[10px] text-gray-600 font-mono mt-0.5">
        {analyzingGemini ? 'Please wait...' : (updating ? (runningMessage || 'Please wait...') : timeStr)}
      </span>

      {/* 비용을 일으키는 조작의 확인 모달 */}
      <ConfirmationModal
        isOpen={confirmAction !== null}
        title={confirmAction ? COSTLY_ACTIONS[confirmAction].name : ''}
        message={confirmAction ? costlyMessage(COSTLY_ACTIONS[confirmAction].body) : ''}
        confirmText="실행"
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => confirmAction && runCostlyAction(confirmAction)}
      />

      {/* Permission Denied Modal */}
      <Modal
        isOpen={permissionModal}
        onClose={() => setPermissionModal(false)}
        title="권한 없음"
        type="danger"
        footer={
          <button
            onClick={() => setPermissionModal(false)}
            className="px-4 py-2 rounded-lg text-sm font-bold text-white bg-red-500 hover:bg-red-600 transition-colors"
          >
            확인
          </button>
        }
      >
        <p>관리자만 실행할 수 있습니다.</p>
        <p className="text-sm text-gray-400 mt-2">관리자 계정으로 로그인해 주세요.</p>
      </Modal>

      {/* Alert Modal */}
      <Modal
        isOpen={alertModal.isOpen}
        onClose={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
        title={alertModal.title}
        type={alertModal.type}
        footer={
          <button
            onClick={() => setAlertModal(prev => ({ ...prev, isOpen: false }))}
            className={`px-4 py-2 rounded-lg text-sm font-bold text-white transition-colors ${alertModal.type === 'danger' ? 'bg-red-500 hover:bg-red-600' :
              alertModal.type === 'success' ? 'bg-emerald-500 hover:bg-emerald-600' :
                'bg-blue-500 hover:bg-blue-600'
              }`}
          >
            확인
          </button>
        }
      >
        <p>{alertModal.content}</p>
      </Modal>
    </div >
  )
}

function SignalCard({ signal, index, onOpenChart, onOpenDetail, onBuy, onRetry, isRetrying, isAdmin, buyDisabledReason }: {
  signal: Signal,
  index: number,
  onOpenChart: () => void,
  onOpenDetail: () => void,
  onBuy: () => void,
  onRetry: (code: string) => void,
  isRetrying: boolean,
  isAdmin: boolean,
  buyDisabledReason: string
}) {
  const buyReasonId = useId();
  const buyTooltip = buyDisabledReason || '모의 계좌로 매수 주문을 실행합니다.';
  const gradeStyles: Record<string, { bg: string, text: string, border: string }> = {
    S: { bg: 'bg-indigo-500/20', text: 'text-indigo-400', border: 'border-indigo-500/30' },
    A: { bg: 'bg-rose-500/20', text: 'text-rose-400', border: 'border-rose-500/30' },
    B: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
    D: { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/30' },
  };

  // Helper function to format model names (handles legacy names and formatting)
  const formatAiModelName = (modelName: string): string => {
    // Alias Mapping (Legacy or Configuration nicknames)
    const lowerName = modelName.toLowerCase();
    if (lowerName === 'gemini-flash-latest' || lowerName === 'gemini flash latest') {
      return 'Gemini Flash (Latest)';
    }

    // Default formatting (snake_case or kebab-case to Title Case)
    return modelName
      .replace(/[-_]/g, ' ')
      .replace(/\bgemini\b/gi, 'Gemini')
      .replace(/\bgpt\b/gi, 'GPT');
  };

  const style = gradeStyles[signal.grade] || gradeStyles.D;

  // [JONGGA-016] 판정은 응답의 두 자리에 담긴다. 지난 자료는 score 안에만 넣고 최상위를
  // null 로 두므로, 최상위만 읽으면 판정과 확신도가 함께 사라진다. 그 빈자리를 llm_reason
  // 텍스트로 추정하던 폴백은 걷어냈다. 부정 맥락의 「상승」과 「매수」까지 BUY 로 읽어
  // 아홉 건 가운데 일곱 건을 틀렸다. 경위는 page.regression-jongga-016.test.tsx 에 있다.
  const aiEval = signal.ai_evaluation ?? signal.score.ai_evaluation;

  // [JONGGA-004] 여기서 등급으로 확신도를 지어내지 않는다. AI 결과가 없는 상태는
  // aiEval 이 없는 것으로 두고, 렌더 쪽에서 대기 상태로 표시한다.
  const confidencePct = parseAIConfidence(aiEval?.confidence);

  // [JONGGA-015] 목표가와 손절가는 매수가에서 파생되고, 같은 카드에 놓인 「종가」와는
  // 무관하다. 두 값이 나란히 보이므로 어느 쪽이 기준인지 화면에 적어 둔다.
  const entryPrice = Number.isFinite(signal.entry_price) && signal.entry_price > 0
    ? signal.entry_price : signal.buy_price || 0;
  const basePrice = Math.round(entryPrice);
  const pctFromBase = (price?: number) => {
    if (!(basePrice > 0) || !price) return null;
    // 옆에 찍히는 금액이 반올림된 값이므로 비율도 같은 값에서 뽑는다.
    const pct = ((Math.round(price) - basePrice) / basePrice) * 100;
    return (
      <span className="text-gray-500 text-[10px] ml-1 whitespace-nowrap">
        (매수가 {pct >= 0 ? '+' : ''}{pct.toFixed(1)}%)
      </span>
    );
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#1c1c1e] overflow-hidden transition-all hover:border-white/20">
      {/* Main Content - 3 Column Layout */}
      <div className="flex flex-col xl:flex-row">

        {/* Column 1: Stock Info + Chart */}
        <div className="p-5 xl:w-[25%] border-b xl:border-b-0 xl:border-r border-white/10 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${style.bg} ${style.text} border ${style.border}`}>
                {signal.grade} GRADE
              </span>
              <span className="text-xs text-gray-500">#{index + 1}</span>
            </div>
          </div>

          {/* Stock Name */}
          <h2 className="text-xl font-bold text-white mb-1 truncate">{signal.stock_name}</h2>
          <div className="text-sm font-mono text-gray-400 mb-2">{signal.stock_code}</div>

          {/* Theme Tags */}
          {signal.themes && signal.themes.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {signal.themes.slice(0, 3).map((theme, i) => (
                <span key={i} className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] rounded-full border border-indigo-500/20">
                  {theme}
                </span>
              ))}
            </div>
          )}

          {/* Key Metrics - NEW! */}
          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-2 gap-2 mb-4 bg-white/5 rounded-xl p-3">
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                상승률
                <Tooltip content="신호가 나온 거래일의 상승률입니다. 그날의 전일 종가 대비 종가를 비교한 값이며, 실시간 등락률이 아닙니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className={`text-sm font-bold ${signal.change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                {signal.change_pct >= 0 ? '+' : ''}{signal.change_pct?.toFixed(1) || 0}%
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                거래량 배수
                <Tooltip content="최근 20일 평균 거래량 대비 오늘 거래량의 배수입니다. 2x 이상이면 평소보다 2배 이상 거래되고 있습니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className="text-sm font-bold text-amber-400">
                {(signal.volume_ratio ?? signal.score_details?.volume_ratio ?? 1).toFixed(0)}x
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                종가
                <Tooltip content="가장 최근 거래일의 종가입니다. 장중에는 갱신되지 않으므로 실시간 시세와 다를 수 있습니다. 실시간 시세는 「상세 분석 보기」에서 확인하세요.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className="text-sm font-bold text-white">
                ₩{signal.current_price?.toLocaleString() || '-'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                거래대금
                <Tooltip content="오늘 하루 동안 거래된 총 금액입니다. 대금이 클수록 유동성이 좋고 큰 손들의 관심을 받고 있습니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className="text-sm font-bold text-emerald-400">
                {(() => {
                  const value = signal.trading_value || 0;
                  // 1조 이상: X.X조
                  if (value >= 1_000_000_000_000) {
                    return `${(value / 1_000_000_000_000).toFixed(1)}조`;
                  }
                  // 1억 이상: XXXX억 (정수 표기)
                  if (value >= 100_000_000) {
                    return `${Math.round(value / 100_000_000).toLocaleString()}억`;
                  }
                  // 1만 이상: XXXX만
                  if (value >= 10_000) {
                    return `${Math.round(value / 10_000).toLocaleString()}만`;
                  }
                  return value.toLocaleString();
                })()}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                외인 (5일)
                <Tooltip content="신호가 나온 거래일까지 5일간 외국인이 순매수한 금액입니다. 양수는 순매수, 음수는 순매도를 의미합니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className={`text-sm font-bold ${(signal.score_details?.foreign_net_buy || 0) > 0 ? 'text-rose-400' :
                (signal.score_details?.foreign_net_buy || 0) < 0 ? 'text-blue-400' : 'text-gray-400'
                }`}>
                {formatBigNumber(signal.score_details?.foreign_net_buy)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                기관 (5일)
                <Tooltip content="신호가 나온 거래일까지 5일간 기관이 순매수한 금액입니다. 양수는 순매수, 음수는 순매도를 의미합니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className={`text-sm font-bold ${(signal.score_details?.inst_net_buy || 0) > 0 ? 'text-rose-400' :
                (signal.score_details?.inst_net_buy || 0) < 0 ? 'text-blue-400' : 'text-gray-400'
                }`}>
                {formatBigNumber(signal.score_details?.inst_net_buy)}
              </div>
            </div>
          </div>

          {/* AI Analysis Result (Action / Confidence) */}
          <div className="flex items-center justify-between bg-white/5 rounded-lg p-2 mb-3">
            <Tooltip
              content={aiEval
                ? 'Gemini AI가 분석한 결과에서 읽은 매매 추천입니다. BUY(매수), HOLD(관망), SELL(매도) 중 하나입니다.'
                : '이 종목은 아직 AI 분석을 받지 않았습니다. 매매 추천과 확신도는 AI 분석이 끝난 뒤에 표시됩니다.'}
              position="bottom" align="left" size="md"
            >
              <div className={`px-2 py-0.5 rounded text-[10px] font-bold border cursor-help ${aiEval?.action === 'BUY' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                aiEval?.action === 'SELL' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
                  'bg-gray-500/20 text-gray-400 border-gray-500/30'
                }`}>
                {aiEval?.action ?? 'AI 분석 대기'}
              </div>
            </Tooltip>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 flex items-center gap-1">
                확신도
                <Tooltip content="Gemini AI가 산출한 추천 신뢰도입니다. 높을수록 강력한 시그널이며, 값이 없으면 미산출로 표시합니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </span>
              {confidencePct !== null ? (
                <>
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${confidencePct >= 80 ? 'bg-purple-500' : confidencePct >= 60 ? 'bg-indigo-500' : 'bg-gray-500'}`}
                      style={{ width: `${confidencePct}%` }}
                    ></div>
                  </div>
                  <span className="text-[10px] font-mono text-white">{confidencePct.toFixed(0)}%</span>
                </>
              ) : (
                <span className="text-[10px] font-mono text-gray-500">미산출</span>
              )}
            </div>
          </div>

          {/* Chart Area */}
          {/* Chart Area */}
          <div data-testid="mini-chart" className="relative h-24 bg-[#131722] rounded-xl overflow-hidden mb-2 cursor-pointer group/chart" onClick={onOpenChart}>
            {/* Gradient Overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/10 to-transparent" />

            {/* SVG 심플 라인 차트 */}
            <svg viewBox="0 0 100 40" className="w-full h-16 relative z-10">
              <defs>
                <linearGradient id={`gradient-${signal.stock_code}`} x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor={signal.change_pct >= 0 ? "#10b981" : "#ef4444"} stopOpacity="0.5" />
                  <stop offset="100%" stopColor={signal.change_pct >= 0 ? "#10b981" : "#ef4444"} stopOpacity="1" />
                </linearGradient>
              </defs>
              {/* 상승 패턴 라인 */}
              <polyline
                fill="none"
                stroke={`url(#gradient-${signal.stock_code})`}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={signal.change_pct >= 0
                  ? "5,35 15,30 25,28 35,25 45,22 55,18 65,15 75,12 85,8 95,5"
                  : "5,5 15,8 25,12 35,15 45,18 55,22 65,25 75,28 85,30 95,35"
                }
              />
              {/* 마지막 점 강조 */}
              <circle
                cx={signal.change_pct >= 0 ? "95" : "95"}
                cy={signal.change_pct >= 0 ? "5" : "35"}
                r="3"
                fill={signal.change_pct >= 0 ? "#10b981" : "#ef4444"}
              />
            </svg>

            {/* 상승률 오버레이 */}
            <div className={`absolute bottom-2 right-2 text-lg font-bold ${signal.change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {signal.change_pct >= 0 ? '↑' : '↓'} {Math.abs(signal.change_pct)?.toFixed(1)}%
            </div>

            <div className="absolute top-2 right-2 z-20 opacity-0 group-hover/chart:opacity-100 transition-opacity">
              <span className="px-2 py-1 bg-gray-800/80 rounded text-[10px] text-white backdrop-blur">
                <i className="fas fa-expand-arrows-alt mr-1"></i> 크게 보기
              </span>
            </div>
          </div>

        </div>

        {/* Column 2: Analysis Details */}
        <div className="p-5 xl:w-[45%] border-b xl:border-b-0 xl:border-r border-white/10 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold text-gray-400 mb-3 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <i className="fas fa-microscope text-indigo-400"></i> AI 분석 리포트
                {aiEval?.model && (
                  <span className="text-[10px] font-normal text-indigo-300 bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                    {formatAiModelName(aiEval.model)}
                  </span>
                )}
              </span>
              {/* Retry Button - Only for Admin */}
              {isAdmin && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRetry(signal.stock_code);
                  }}
                  disabled={isRetrying}
                  className={`transition-colors p-1 ${isRetrying ? 'text-indigo-400' : 'text-gray-600 hover:text-indigo-400'}`}
                  aria-label={`${signal.stock_name} 이 종목만 재분석`}
                  title="이 종목만 재분석 (Admin)"
                >
                  <i className={`fas fa-redo-alt text-[10px] ${isRetrying ? 'animate-spin' : ''}`}></i>
                </button>
              )}
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {signal.score.llm_reason || "AI 분석 대기 중입니다..."}
            </p>
            {signal.score.llm_reason && (
              <p className="mt-2 text-xs text-gray-500 leading-relaxed">
                AI 원문에는 다른 가격이 포함될 수 있습니다. 이 화면의 시스템 계산 기준은 아래 목표가·손절가입니다.
              </p>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <h4 className="text-[10px] text-gray-500 mb-2 font-bold flex items-center gap-1">
                시스템 계산 기준
                <Tooltip content="시그널에 저장된 목표가·손절가를 우선 사용합니다. 가격이 없으면 진입가 대비 기본 +5%/-3%로 계산합니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </h4>
              <ul className="text-xs text-gray-400 space-y-1">
                <li className="flex items-start gap-1.5">
                  <span className="text-emerald-500 mt-0.5">●</span>
                  <span>
                    <Tooltip content={
                      <div className="text-[10px] leading-snug text-left">
                        <span className="text-emerald-400 font-bold block mb-1 text-center">🟢 매수 전략</span>
                        <ul className="list-disc pl-4 space-y-0.5 text-gray-300">
                          <li><strong>15:10 ~ 15:29</strong></li>
                          <li>분할 3회 매수</li>
                        </ul>
                      </div>
                    }>
                      <span className="cursor-help border-b border-dashed border-gray-600 hover:border-emerald-500 hover:text-emerald-400 transition-colors">매수가</span>
                    </Tooltip>
                    : <span className="text-emerald-400 font-mono">₩{basePrice.toLocaleString()}</span>
                    {signal.signal_date && (
                      <span className="text-gray-500 text-[10px] ml-1 whitespace-nowrap">({signal.signal_date} 종가)</span>
                    )}
                  </span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-amber-500 mt-0.5">●</span>
                  <span>
                    <Tooltip content="저장된 목표가를 기준으로 익절 여부를 계산합니다. 목표가가 없으면 진입가 대비 기본 +5%를 사용합니다.">
                      <span className="cursor-help border-b border-dashed border-gray-600 hover:border-amber-500 hover:text-amber-400 transition-colors">목표가</span>
                    </Tooltip>
                    : <span className="text-amber-400 font-mono">₩{Math.round(signal.target_price || 0).toLocaleString()}</span>
                    {pctFromBase(signal.target_price)}
                  </span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-rose-500 mt-0.5">●</span>
                  <span>
                    <Tooltip content="저장된 손절가를 기준으로 손절 여부를 계산합니다. 손절가가 없으면 진입가 대비 기본 -3%를 사용합니다. 같은 일봉에서 양쪽에 도달하면 손절을 우선합니다.">
                      <span className="cursor-help border-b border-dashed border-gray-600 hover:border-rose-500 hover:text-rose-400 transition-colors">손절가</span>
                    </Tooltip>
                    : <span className="text-rose-400 font-mono">₩{Math.round(signal.stop_price || 0).toLocaleString()}</span>
                    {pctFromBase(signal.stop_price)}
                  </span>
                </li>
              </ul>
            </div>
            <div>
              <h4 className="text-[10px] text-gray-500 mb-2 font-bold">체크리스트</h4>
              <div className="space-y-1">
                <div className={`text-[10px] px-2 py-1 rounded w-fit ${signal.checklist?.has_news ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-500'}`}>
                  {signal.checklist?.has_news ? '뉴스/호재 있음' : '특별한 호재 없음'}
                </div>
                <div className={`text-[10px] px-2 py-1 rounded w-fit ${signal.checklist?.supply_positive ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-500'}`}>
                  {signal.checklist?.supply_positive ? '수급 양호 (외인/기관)' : '수급 보통'}
                </div>
              </div>
            </div>
          </div>

          {/* References */}
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                REFERENCES
                <Tooltip content="AI 분석에 활용된 최신 뉴스 기사 목록입니다. 클릭하면 원문으로 이동합니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </span>
            </div>
            <div className="space-y-1.5">
              {signal.news_items && signal.news_items.length > 0 ? (
                signal.news_items.slice(0, 3).map((news, i) => (
                  <a
                    key={i}
                    href={news.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-xs text-gray-400 hover:text-indigo-400 transition-colors line-clamp-1"
                  >
                    <i className="fas fa-newspaper mr-1.5 text-[10px] text-gray-600"></i>
                    [{news.source}] {news.title}
                  </a>
                ))
              ) : (
                <p className="text-xs text-gray-600">관련 뉴스 없음</p>
              )}
            </div>
          </div>
        </div>

        {/* Column 3: Score & Actions */}
        <div className="p-5 xl:w-[30%] flex flex-col justify-between bg-black/20">
          <div className="text-center mb-4">
            <div className="inline-block relative">
              <svg className="w-24 h-24 transform -rotate-90">
                <circle cx="48" cy="48" r="40" stroke="#374151" strokeWidth="8" fill="transparent" />
                <circle
                  cx="48"
                  cy="48"
                  r="40"
                  stroke={signal.score.total >= 10 ? '#8b5cf6' : signal.score.total >= 8 ? '#10b981' : '#f59e0b'}
                  strokeWidth="8"
                  fill="transparent"
                  strokeDasharray={`${2 * Math.PI * 40}`}
                  strokeDashoffset={`${2 * Math.PI * 40 * (1 - signal.score.total / 19)}`}
                  className="transition-all duration-1000 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold text-white">{signal.score.total}</span>
                <span className="text-[10px] text-gray-500">/ 19점</span>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-2 font-medium flex items-center justify-center gap-1">
              TOTAL SCORE
              <Tooltip content={
                <div className="text-left space-y-2">
                  <p><strong>합계 점수: {signal.score.total}점</strong> (최대 19점)</p>
                  <p className="text-[9px] text-gray-400">● 기본 점수 (Max 12): 뉴스(3), 거래량(3), 차트(2), 수급(2), 캔들(1), 기간조정(1)</p>
                  <p className="text-[9px] text-gray-400">● 가산점 (Max 7): 거래량 급증(최대 5), 장대양봉(최대 1), 상한가(최대 1)</p>
                  <p className="text-indigo-400 font-bold mt-1">※ 8점 이상 강력 매수 신호</p>
                </div>
              } position="bottom" size="md">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
              </Tooltip>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-2 gap-2 text-center text-[10px] text-gray-500 mb-4 px-2">
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.chart >= 2 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="차트 패턴: 신고가/돌파 여부 및 추세 분석 (최대 2점)">
                <div className="cursor-help">차트</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.chart}/2</div>
            </div>
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.supply >= 2 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="수급 점수: 외국인/기관 순매수 강도 (최대 2점)">
                <div className="cursor-help">수급</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.supply}/2</div>
            </div>
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.news >= 3 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="관련 뉴스 점수: 최근 3일간 관련 뉴스 품질/수량 및 AI 평가 (최대 3점)">
                <div className="cursor-help">뉴스</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.news}/3</div>
            </div>
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.volume >= 3 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="거래대금 점수: 1조(3점), 5000억(2점), 1000억(1점) (최대 3점)">
                <div className="cursor-help">거래량</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.volume}/3</div>
            </div>
            {/* 추가된 항목들 */}
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.candle >= 1 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="캔들 형태: 장대양봉 및 윗꼬리 관리 여부 (최대 1점)">
                <div className="cursor-help">캔들</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.candle}/1</div>
            </div>
            <div className={`bg-white/5 rounded py-1 hover:bg-white/10 transition-colors border ${signal.score.timing >= 1 ? 'border-indigo-500/30' : 'border-transparent'}`}>
              <Tooltip content="변동성 수축: 볼린저밴드 수축 및 기간조정 여부 (최대 1점)">
                <div className="cursor-help">조정</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.timing}/1</div>
            </div>
                <div className={`col-span-2 bg-indigo-500/10 rounded py-1 hover:bg-indigo-500/20 transition-colors border ${(signal.score_details?.bonus_score || 0) > 0 ? 'border-indigo-500/50' : 'border-transparent'}`}>
                  <Tooltip
                    content={
                      <div className="text-left space-y-1">
                    <p>가산점: 거래량 급증/장대양봉/상한가 (최대 7점)</p>
                    <p className="text-emerald-300">● 거래량 급증: +{signal.score_details?.bonus_breakdown?.volume || 0}/5</p>
                    <p className="text-emerald-300">● 장대양봉: +{signal.score_details?.bonus_breakdown?.candle || 0}/1</p>
                    <p className="text-emerald-300">● 상한가: +{signal.score_details?.bonus_breakdown?.limit_up || 0}/1</p>
                  </div>
                }>
                  <div className="cursor-help text-indigo-300 font-bold">보너스 (가산점)</div>
                </Tooltip>
                <div className="text-indigo-400 font-bold">+{signal.score_details?.bonus_score || 0}/7</div>
                {signal.score_details?.bonus_breakdown && (
                  <div className="text-[9px] text-gray-500 mt-1">거래량/{signal.score_details.bonus_breakdown.volume || 0} | 장대양봉/{signal.score_details.bonus_breakdown.candle || 0}/1 | 상한가/{signal.score_details.bonus_breakdown.limit_up || 0}/1</div>
                )}
              </div>
            </div>

          <div className="mt-auto grid grid-cols-1 md:grid-cols-2 xl:grid-cols-1 gap-2.5">
            {/* Primary Actions: Stacked for better mobile/narrow visibility */}
            <button
              onClick={onOpenDetail}
              className="w-full py-3 bg-indigo-600/90 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-indigo-500/10 active:scale-[0.98] flex items-center justify-center gap-2 group/btn"
            >
              <i className="fas fa-search-plus transition-transform group-hover/btn:scale-110"></i>
              상세 분석 보기
            </button>
            <div className="space-y-1">
              <button
                onClick={onBuy}
                disabled={Boolean(buyDisabledReason)}
                aria-label={`${signal.stock_name} 모의 매수`}
                aria-describedby={buyDisabledReason ? buyReasonId : undefined}
                title={buyTooltip}
                className="w-full py-3 bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-amber-500/20 active:scale-[0.98] flex items-center justify-center gap-2 group/buy disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:from-amber-600 disabled:hover:to-orange-600 disabled:active:scale-100"
              >
                <i className="fas fa-shopping-cart transition-transform group-hover/buy:scale-110"></i>
                모의 매수
              </button>
              {buyDisabledReason && (
                <p id={buyReasonId} className="text-xs leading-relaxed text-amber-200">
                  {buyDisabledReason}
                </p>
              )}
            </div>

            {/* Secondary Actions: 2-Column Grid for Links */}
            <div className="grid grid-cols-2 gap-2 md:col-span-2 xl:col-span-1">
              <a
                href={`https://m.stock.naver.com/domestic/stock/${signal.stock_code}/main`}
                target="_blank"
                rel="noopener noreferrer"
                className="py-2.5 bg-[#03c75a] hover:bg-[#02b351] text-white text-xs font-bold rounded-xl transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2 whitespace-nowrap"
              >
                <span className="font-serif font-black">N</span> 네이버
              </a>
              <a
                href={`https://tossinvest.com/stocks/${signal.stock_code}`}
                target="_blank"
                rel="noopener noreferrer"
                className="py-2.5 bg-[#3182f6] hover:bg-[#1b64da] text-white text-xs font-bold rounded-xl transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2 whitespace-nowrap"
              >
                <i className="fas fa-mobile-alt"></i> 토스
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
