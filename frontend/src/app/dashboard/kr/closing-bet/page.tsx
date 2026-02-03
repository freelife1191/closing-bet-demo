'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Modal from '@/app/components/Modal';

// Tooltip 컴포넌트 - 아이콘 hover 시에만 표시
function Tooltip({ children, content, className = "", position = "top", align = "center", wide = false, width }: {
  children: React.ReactNode,
  content: React.ReactNode,
  className?: string,
  position?: 'top' | 'bottom',
  align?: 'left' | 'center' | 'right',
  wide?: boolean,
  width?: string
}) {
  const positionClass = position === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';
  const arrowClass = position === 'bottom' ? 'bottom-full border-b-gray-900/95 -mb-1' : 'top-full border-t-gray-900/95 -mt-1';
  const widthClass = width || (wide ? 'w-64 max-w-[280px]' : 'w-52 max-w-[220px]');

  let alignClass = 'left-1/2 -translate-x-1/2';
  let arrowAlignClass = 'left-1/2 -translate-x-1/2';

  if (align === 'left') {
    alignClass = 'left-0';
    arrowAlignClass = 'left-4';
  } else if (align === 'right') {
    alignClass = 'right-0';
    arrowAlignClass = 'right-4';
  }

  return (
    <span className={`relative group/tooltip inline-flex items-center ${className}`}>
      {children}
      <div className={`absolute ${alignClass} ${positionClass} ${widthClass} px-3 py-2 bg-gray-900/95 text-gray-200 text-[10px] font-medium rounded-lg opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-[100] border border-white/10 shadow-xl backdrop-blur-sm text-center leading-relaxed whitespace-normal`}>
        {content}
        <div className={`absolute ${arrowAlignClass} border-4 border-transparent ${arrowClass}`}></div>
      </div>
    </span>
  );
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
  };
  ai_evaluation?: {
    action: 'BUY' | 'HOLD' | 'SELL';
    confidence: number;
    model?: string;
  };
  themes?: string[]; // 관련 테마 태그 (예: 원전, SMR, 전력인프라)
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

// TradingView Simple Chart Widget
function TradingViewChart({ symbol }: { symbol: string }) {
  useEffect(() => {
    // TradingView 위젯 스크립트 로드
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      if (typeof (window as unknown as { TradingView: unknown }).TradingView !== 'undefined') {
        new (window as unknown as { TradingView: { widget: new (config: unknown) => unknown } }).TradingView.widget({
          'autosize': true,
          'symbol': `KRX:${symbol}`,
          'interval': 'D',
          'timezone': 'Asia/Seoul',
          'theme': 'dark',
          'style': '1',
          'locale': 'kr',
          'toolbar_bg': '#1c1c1e',
          'enable_publishing': false,
          'allow_symbol_change': false,
          'container_id': 'tradingview_chart',
          'hide_side_toolbar': false,
          'studies': ['RSI@tv-basicstudies', 'MASimple@tv-basicstudies'],
        });
      }
    };
    document.head.appendChild(script);

    return () => {
      const container = document.getElementById('tradingview_chart');
      if (container) container.innerHTML = '';
    };
  }, [symbol]);

  return (
    <div className="flex flex-col h-full bg-[#131722]">
      <div id="tradingview_chart" className="flex-1 min-h-[400px]" />
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
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 transition-opacity animate-in fade-in duration-200" onClick={onClose}>
      <div
        className="bg-[#1c1c1e] w-full max-w-4xl h-[80vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden relative animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-white/5 bg-[#1c1c1e]">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-white">{name}</h3>
            <span className="text-sm font-mono text-gray-400">{symbol}</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <i className="fas fa-times text-xl"></i>
          </button>
        </div>

        <div className="flex-1 relative">
          <TradingViewChart symbol={symbol} />
        </div>
      </div>
    </div>
  );
}

// Price Range Progress Bar Component
function PriceRangeBar({ low, high, current, label }: { low: number; high: number; current: number; label: string }) {
  const range = high - low;
  const position = range > 0 ? ((current - low) / range) * 100 : 50;
  const positionClamped = Math.max(0, Math.min(100, position));

  return (
    <div className="mb-5">
      <div className="flex justify-between items-end mb-2">
        <span className="text-xs text-gray-400 font-medium">{label}</span>
        <div className="text-right">
          <span className="text-[10px] text-gray-500 mr-2">현재</span>
          <span className="text-sm font-bold text-white">₩{current.toLocaleString()}</span>
        </div>
      </div>

      <div className="relative h-2.5 bg-[#131722] rounded-full ring-1 ring-white/10">
        {/* Background Range Gradient (Low -> High indication) */}
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500/20 via-gray-500/10 to-rose-500/20" />

        {/* Active Range Fill (Optional: Low to Current) */}
        <div
          className="absolute top-0 left-0 h-full rounded-l-full bg-white/5"
          style={{ width: `${positionClamped}%` }}
        />

        {/* Indicator Knob */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full border-2 border-indigo-500 shadow-lg z-10 transition-all duration-500 group cursor-help"
          style={{ left: `${positionClamped}%`, transform: 'translate(-50%, -50%)' }}
        >
          <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-indigo-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            {positionClamped.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="flex justify-between text-[10px] text-gray-500 mt-1.5 font-mono">
        <span className="text-blue-400">L: ₩{low.toLocaleString()}</span>
        <span className="text-rose-400">H: ₩{high.toLocaleString()}</span>
      </div>
    </div>
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
  const [detail, setDetail] = useState<StockDetailInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

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

  const formatBigNumber = (num: number | undefined | null) => {
    if (num === undefined || num === null || num === 0) return '-';

    const abs = Math.abs(num);
    const sign = num < 0 ? '-' : '';

    if (abs >= 10000000000000000) return `${sign}${(abs / 10000000000000000).toFixed(1)}경`;
    if (abs >= 1000000000000) return `${sign}${(abs / 1000000000000).toFixed(1)}조`;
    if (abs >= 100000000) return `${sign}${(abs / 100000000).toFixed(0)}억`;
    if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(0)}만`;

    return num.toLocaleString();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="bg-[#1c1c1e] w-full max-w-3xl max-h-[85vh] rounded-2xl border border-white/10 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-bold text-white">{name}</h3>
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
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
          >
            <i className="fas fa-times text-xl"></i>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(85vh-70px)]">
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
                  <i className="fas fa-chart-bar text-indigo-400"></i> 시세 정보
                  <Tooltip content="오늘의 가격 움직임(1일 범위)과 최근 52주간 최저/최고가를 비교하여 현재 가격 위치를 보여줍니다.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                <PriceRangeBar
                  low={detail.priceInfo.low || detail.priceInfo.prevClose * 0.97}
                  high={detail.priceInfo.high || detail.priceInfo.prevClose * 1.03}
                  current={detail.priceInfo.current || detail.priceInfo.prevClose}
                  label="1일 범위"
                />
                <PriceRangeBar
                  low={detail.yearRange.low_52w}
                  high={detail.yearRange.high_52w}
                  current={detail.priceInfo.current}
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
                    <span className="text-gray-500">거래대금 (Val)</span>
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
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      시가총액
                      <Tooltip content="발행주식수 × 현재가. 기업의 시장가치를 나타냅니다.">
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
                  <i className="fas fa-users text-purple-400"></i> 투자자 동향 (5일 합계)
                  <Tooltip content="최근 5영업일 동안 각 투자자 유형의 순매수/순매도 금액입니다. 외국인/기관 순매수는 호재로 해석됩니다.">
                    <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[10px] cursor-help"></i>
                  </Tooltip>
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      외국인
                      <Tooltip content="외국인 투자자의 순매수 금액. 양수면 매수우위.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className={`text-sm font-bold ${detail.investorTrend.foreign >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                      {detail.investorTrend.foreign >= 0 ? '+' : ''}{formatBigNumber(detail.investorTrend.foreign)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      기관
                      <Tooltip content="기관 투자자(연기금, 자산운용사 등)의 순매수 금액.">
                        <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                      </Tooltip>
                    </div>
                    <div className={`text-sm font-bold ${detail.investorTrend.institution >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                      {detail.investorTrend.institution >= 0 ? '+' : ''}{formatBigNumber(detail.investorTrend.institution)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                      개인
                      <Tooltip content="개인 투자자의 순매수 금액. 보통 외국인/기관과 반대.">
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
                  <div className="grid grid-cols-3 gap-4">
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
      </div>
    </div>
  );
}

export default function JonggaV2Page() {
  const [data, setData] = useState<ScreenerResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('latest');

  const [chartModal, setChartModal] = useState<{ isOpen: boolean, symbol: string, name: string }>({
    isOpen: false, symbol: '', name: ''
  });
  const [detailModal, setDetailModal] = useState<{ isOpen: boolean, code: string, name: string }>({
    isOpen: false, code: '', name: ''
  });
  const [gradeGuideOpen, setGradeGuideOpen] = useState(false);

  // Tips Collapse State

  // Tips Collapse State
  const [isTipsOpen, setIsTipsOpen] = useState(false);

  // Filters
  const [filterTradingValue, setFilterTradingValue] = useState(0);
  const [filterRise, setFilterRise] = useState(0);
  const [filterVol, setFilterVol] = useState(0);
  const [filterGrade, setFilterGrade] = useState<string>('ALL');
  const [filterScore, setFilterScore] = useState(0);

  const getFilteredSignals = () => {
    if (!data?.signals) return [];
    return data.signals.filter(s => {
      // 1. Trading Value Filter
      if (filterTradingValue > 0 && s.trading_value < filterTradingValue) return false;

      // 2. Rise % Filter
      const rise = s.score_details?.rise_pct ?? s.change_pct;
      if (filterRise > 0 && rise < filterRise) return false;

      // 3. Volume Ratio Filter
      const vol = s.volume_ratio ?? s.score_details?.volume_ratio ?? 0;
      if (filterVol > 0 && vol < filterVol) return false;

      // 4. Grade Filter
      if (filterGrade !== 'ALL') {
        const gradeWeight: Record<string, number> = { 'S': 4, 'A': 3, 'B': 2, 'C': 1, 'D': 0 };
        const sGrade = typeof s.grade === 'string' ? s.grade : (s.grade as any).value;
        const sWeight = gradeWeight[sGrade] ?? -1;
        const fWeight = gradeWeight[filterGrade] ?? -1;

        if (sWeight < fWeight) return false;
      }

      // 5. Total Score Filter
      if (filterScore > 0 && s.score.total < filterScore) return false;

      return true;
    });
  };

  const filteredSignals = getFilteredSignals();
  const matchCount = filteredSignals.length;

  useEffect(() => {
    fetch('/api/kr/jongga-v2/dates')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setDates(data);
        }
      })
      .catch((err) => console.error('Failed to fetch dates:', err));
  }, []);

  useEffect(() => {
    setLoading(true);
    let url = '/api/kr/jongga-v2/latest';
    if (selectedDate !== 'latest') {
      url = `/api/kr/jongga-v2/history/${selectedDate}`;
    }

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        setData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch data:', err);
        setLoading(false);
        setData(null);
      });
  }, [selectedDate]);

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
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/20 bg-indigo-500/5 text-xs text-indigo-400 font-medium mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping"></span>
            AI 기반 전략
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
            종가 <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">베팅</span>
          </h2>
          <p className="text-gray-400 text-lg">
            Gemini 3.0 분석 + 기관 수급 추세
          </p>
        </div>

        {/* TRENDING THEMES Box */}
        <TrendingThemesBox themes={getTrendingThemes(filteredSignals)} />
      </div>

      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/5">
        <div className="flex gap-6">
          <StatBox label="CANDIDATES" value={data?.filtered_count || 0} tooltip="시장에서 1차 필터링된 후보 종목 수입니다." />
          <StatBox label="FILTERED" value={data?.total_candidates || 0} highlight tooltip="AI 조건에 의해 최종 선별된 종목 수입니다." />
          <DataStatusBox updatedAt={data?.updated_at} />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex gap-2 items-end">
            {/* Trading Value Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                거래대금
                <Tooltip content="하루 동안 거래된 총 금액입니다. 거래대금이 클수록 유동성이 좋고 기관의 관심을 받는 종목입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
                value={filterTradingValue}
                onChange={(e) => setFilterTradingValue(Number(e.target.value))}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterTradingValue > 0 ? 'border-indigo-500 text-indigo-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value={0}>전체</option>
                <option value={50000000000}>500억 이상</option>
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

            {/* Volume Ratio Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                거래량
                <Tooltip content="20일 평균 대비 오늘 거래량 배수입니다. 2배 이상이면 관심 증가, 5배 이상이면 급등 가능성입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
                value={filterVol}
                onChange={(e) => setFilterVol(Number(e.target.value))}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterVol > 0 ? 'border-amber-500 text-amber-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value={0}>전체</option>
                <option value={1.5}>1.5배 이상</option>
                <option value={2}>2배 이상 (Standard)</option>
                <option value={3}>3배 이상</option>
                <option value={5}>5배 이상 (Surge)</option>
                <option value={10}>10배 이상 (Explosion)</option>
              </select>
            </div>

            {/* Grade Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                등급
                <Tooltip content="AI가 평가한 종합 등급입니다. S(최고), A(우수), B(양호), D(주의) 순서입니다.">
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
                value={filterGrade}
                onChange={(e) => setFilterGrade(e.target.value)}
                className={`bg-[#1c1c1e] border text-xs rounded-xl px-3 py-2 outline-none transition-colors ${filterGrade !== 'ALL' ? 'border-purple-500 text-purple-400' : 'border-white/10 text-gray-400'}`}
              >
                <option value="ALL">전체</option>
                <option value="S">S급 이상</option>
                <option value="A">A급 이상</option>
                <option value="B">B급 이상</option>
                <option value="D">D급 이상</option>
              </select>
            </div>

            {/* Score Filter */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1 text-[9px] text-gray-500">
                총점
                <Tooltip content="6개 항목(뉴스, 거래량, 차트, 수급, 타이밍, 캔들)의 총 점수입니다. 최대 12점, 8점 이상이면 강력 추천입니다.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <select
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

          <div className="h-6 w-px bg-white/10 mx-2"></div>

          <Tooltip content="이전 리포트 기록을 조회할 수 있습니다. Latest Report는 가장 최신 데이터를 보여줍니다." position="bottom" align="right" wide>
            <select
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-[#1c1c1e] border border-white/10 text-gray-300 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-500/50 outline-none transition-all hover:border-white/20"
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
            <button
              onClick={() => setSelectedDate(selectedDate)}
              className="p-2 bg-[#1c1c1e] border border-white/10 rounded-xl hover:bg-white/5 text-gray-400 hover:text-white transition-all"
            >
              <i className="fas fa-sync-alt"></i>
            </button>
          </Tooltip>
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
              <h3 className={`text-sm font-bold ${isTipsOpen ? 'text-white' : 'text-gray-400 group-hover:text-gray-200'}`}>
                Trading Tips & Strategy
              </h3>
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
              <h4 className="text-sm font-bold text-indigo-300 mb-2 flex items-center gap-2">
                <i className="fas fa-compass"></i> Market Adaptation Strategy
              </h4>
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
                    <li><span className="text-rose-400">Profit</span>: 익일 시초 30분 내 +3% 발생 시 50% 분할 익절</li>
                    <li><span className="text-gray-400">Stop</span>: 전일 종가 또는 5일선 이탈 시 나머지 전량 매도</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Closing Bet Buy Daily Patterns */}
            <div className="bg-[#1c1c1e] border border-white/5 rounded-2xl p-5">
              <h4 className="text-sm font-bold text-gray-200 mb-4 flex items-center gap-2">
                <span className="w-1 h-4 bg-emerald-500 rounded-full"></span>
                종가베팅 매수 일봉 패턴
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h5 className="text-xs font-bold text-emerald-400 mb-2">1) 신고가 조정 후 반등</h5>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 신고가 돌파 → 10~40일 20일선 지지 조정 → 매물 소화 → 거래량 터진 양봉(윗꼬리 짧음)</p>
                    <p>• <strong>타이밍</strong>: 전고점 근처 깔끔한 양봉 종가</p>
                  </div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h5 className="text-xs font-bold text-emerald-400 mb-2">2) 장대양봉 후 5일선 지지</h5>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 장대양봉 → 다음날 음봉에도 5일선 위 버팀 → 관찰 → 5일선 지지 양봉</p>
                    <p>• <strong>특징</strong>: 재료 좋은 종목, 장대양봉 다음날 대량 음봉 OK</p>
                  </div>
                </div>
                <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                  <h5 className="text-xs font-bold text-emerald-400 mb-2">3) 엔벨로프 돌파 후 7일선 지지</h5>
                  <div className="text-[10px] text-gray-400 space-y-1">
                    <p>• <strong>패턴</strong>: 엔벨로프 20/40선 돌파 → 연속 시세 → 7일선(or 15일선) 지지</p>
                    <p>• <strong>의미</strong>: 단발성 아닌 연속성 재료 확정</p>
                  </div>
                </div>
              </div>

              <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-3">
                <h5 className="text-xs font-bold text-indigo-300 mb-2 flex items-center gap-1">
                  <i className="fas fa-check-circle"></i> 공통 조건
                </h5>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-[10px] text-gray-300">
                  <div className="flex items-center gap-1.5"><span className="text-indigo-500">•</span> <span>거래대금 500억↑ (대형주 1000억↑) + 거래량 3~5배↑</span></div>
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
            <h3 className="text-xl font-bold text-gray-300">No Signals Found</h3>
            <p className="text-gray-500 mt-2 max-w-md">
              Try adjusting filters or wait for market conditions to improve.
            </p>
          </div>
        ) : (
          filteredSignals.map((signal, idx) => (
            <SignalCard
              key={signal.stock_code}
              signal={signal}
              index={idx}
              onOpenChart={() => setChartModal({ isOpen: true, symbol: signal.stock_code, name: signal.stock_name })}
              onOpenDetail={() => setDetailModal({ isOpen: true, code: signal.stock_code, name: signal.stock_name })}
            />
          ))
        )}
      </div>

      <div className="text-center text-xs text-gray-600 pt-8">
        Engine: v2.0.1 (Gemini 3.0 Flash) • Updated: {data?.updated_at || '-'}
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
    </div>
  );
}

function DataStatusBox({ updatedAt }: { updatedAt?: string }) {
  const [updating, setUpdating] = useState(false);
  const [analyzingGemini, setAnalyzingGemini] = useState(false);
  const [currentUpdatedAt, setCurrentUpdatedAt] = useState(updatedAt);

  // updatedAt props가 변경되면 내부 상태도 업데이트 (초기화용)
  useEffect(() => {
    setCurrentUpdatedAt(updatedAt);
  }, [updatedAt]);

  const pollStatus = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        // 변경: 상태 전용 엔드포인트 폴링
        const res = await fetch('/api/kr/jongga-v2/status');
        const data = await res.json();

        if (data) {
          // 실행 중이면 계속 폴링
          if (data.is_running) {
            if (!updating) setUpdating(true); // 강제 상태 동기화
          } else {
            // 실행 끝남 (is_running: false)
            // 만약 내가 '업데이트 중'이라고 알고 있었다면 -> 완료 처리
            if (updating) {
              clearInterval(interval);
              setUpdating(false);
              // 데이터 리프레시 (리로드 대신 fetch)
              window.location.reload();
            }
          }
        }
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 2000); // 2초마다 체크 (반응성 향상)

    // 5분 후에는 폴링 중단 (안전장치)
    setTimeout(() => {
      clearInterval(interval);
      if (updating) setUpdating(false);
    }, 300000);
  }, [updating]);

  if (!updatedAt && !updating && !analyzingGemini) return <StatBox label="Data Status" value={0} customValue="LOADING..." />;

  const updateDate = updatedAt ? new Date(updatedAt) : new Date();
  const today = new Date();
  const isToday = updatedAt ? (
    updateDate.getDate() === today.getDate() &&
    updateDate.getMonth() === today.getMonth() &&
    updateDate.getFullYear() === today.getFullYear()
  ) : false;

  const timeStr = updateDate.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

  const handleUpdate = async () => {
    if (updating) return;

    setUpdating(true);
    try {
      const res = await fetch('/api/kr/jongga-v2/run', { method: 'POST' });
      if (res.ok) {
        console.log('Engine started in background');
        // 폴링 시작
        pollStatus();
      } else {
        // 이미 실행 중인 경우
        if (res.status === 409) {
          console.log('Engine is already running.');
          pollStatus(); // 실행 중이면 바로 폴링 시작
        } else {
          console.error('엔진 실행 실패. 서버 로그를 확인하세요.');
          setUpdating(false);
        }
      }
    } catch (error) {
      console.error('업데이트 요청 중 오류 발생', error);
      setUpdating(false);
    }
  };

  const handleGeminiReanalyze = async () => {
    if (analyzingGemini) return;

    setAnalyzingGemini(true);
    try {
      console.log('Gemini Analysis Request Triggered...');
      const res = await fetch('/api/kr/jongga-v2/reanalyze-gemini', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok) {
        console.log(data.message || 'Gemini 분석 완료!');
        window.location.reload();
      } else {
        console.error(data.error || 'Gemini 분석 실패');
      }
    } catch (error) {
      console.error('Gemini 분석 요청 중 오류 발생', error);
    } finally {
      setAnalyzingGemini(false);
    }
  };

  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1 flex items-center gap-2">
        Data Status
        <Tooltip content="스크리너 엔진을 실행하여 모든 종목에 대해 전체 업데이트(뉴스, 수급, 점수 등)를 수행합니다." position="bottom" align="right" wide>
          <button
            onClick={handleUpdate}
            disabled={updating || analyzingGemini}
            className={`p-1 rounded bg-white/5 hover:bg-white/10 transition-all ${updating ? 'animate-spin text-indigo-400' : 'text-gray-500 hover:text-white'}`}
          >
            <i className="fas fa-sync-alt text-[10px]"></i>
          </button>
        </Tooltip>
        <Tooltip content="기존 데이터를 기반으로 Gemini AI를 재호출하여 분석 결과만 업데이트합니다." position="bottom" align="right" wide>
          <button
            onClick={handleGeminiReanalyze}
            disabled={updating || analyzingGemini}
            className={`p-1 rounded bg-white/5 hover:bg-white/10 transition-all ${analyzingGemini ? 'animate-pulse text-purple-400' : 'text-gray-500 hover:text-purple-400'}`}
          >
            <i className="fas fa-brain text-[10px]"></i>
          </button>
        </Tooltip>
      </span>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${(isToday && !updating && !analyzingGemini) ? 'bg-emerald-500 animate-pulse' : 'bg-gray-500'}`}></span>
        <span className={`text-xl font-mono font-bold ${(isToday && !updating && !analyzingGemini) ? 'text-emerald-400' : 'text-gray-400'}`}>
          {updating ? 'RUNNING...' : analyzingGemini ? 'ANALYZING...' : (isToday ? 'UPDATED' : 'OLD DATA')}
        </span>
      </div>
      <span className="text-[10px] text-gray-600 font-mono mt-0.5">{updating || analyzingGemini ? 'Please wait...' : timeStr}</span>
    </div>
  )
}

function StatBox({ label, value, highlight = false, customValue, tooltip }: { label: string, value: number, highlight?: boolean, customValue?: string, tooltip?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1 flex items-center gap-1">
        {label}
        {tooltip && (
          <Tooltip content={tooltip}>
            <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
          </Tooltip>
        )}
      </span>
      <span className={`text-2xl font-mono font-bold ${highlight ? 'text-indigo-400' : 'text-white'}`}>
        {customValue || value}
      </span>
    </div>
  )
}

function SignalCard({ signal, index, onOpenChart, onOpenDetail }: { signal: Signal, index: number, onOpenChart: () => void, onOpenDetail: () => void }) {
  const gradeStyles: Record<string, { bg: string, text: string, border: string }> = {
    S: { bg: 'bg-indigo-500/20', text: 'text-indigo-400', border: 'border-indigo-500/30' },
    A: { bg: 'bg-rose-500/20', text: 'text-rose-400', border: 'border-rose-500/30' },
    B: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
    C: { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/30' },
    D: { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/30' },
  };

  const style = gradeStyles[signal.grade] || gradeStyles.D;

  // AI Evaluation Fallback Logic
  const aiEval = signal.ai_evaluation || {
    action: ['S', 'A'].includes(signal.grade) ? 'BUY' : 'HOLD',
    confidence: signal.score.total * 8 + (signal.grade === 'S' ? 10 : 0), // Simple derivation
    model: 'Gemini 3.0 (Est.)'
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#1c1c1e] overflow-hidden transition-all hover:border-white/20">
      {/* Main Content - 3 Column Layout */}
      <div className="flex flex-col lg:flex-row">

        {/* Column 1: Stock Info + Chart */}
        <div className="p-5 lg:w-[25%] border-b lg:border-b-0 lg:border-r border-white/10 flex flex-col">
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
          <h3 className="text-xl font-bold text-white mb-1 truncate">{signal.stock_name}</h3>
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
          <div className="grid grid-cols-2 gap-2 mb-4 bg-white/5 rounded-xl p-3">
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                상승률
                <Tooltip content="전일 종가 대비 현재가의 상승/하락률입니다. 양수(+)면 상승, 음수(-)면 하락입니다.">
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
                {(signal.volume_ratio ?? signal.score_details?.volume_ratio ?? 1).toFixed(1)}x
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                현재가
                <Tooltip content="현재 주식의 거래 가격입니다. 실시간으로 업데이트되지 않을 수 있습니다.">
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
                <Tooltip content="최근 5일간 외국인 순매수 합계입니다. 양수는 순매수, 음수는 순매도를 의미합니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className={`text-sm font-bold ${(signal.score_details?.foreign_net_buy || 0) > 0 ? 'text-rose-400' :
                (signal.score_details?.foreign_net_buy || 0) < 0 ? 'text-blue-400' : 'text-gray-400'
                }`}>
                {(signal.score_details?.foreign_net_buy)
                  ? Math.abs(signal.score_details.foreign_net_buy) >= 100000000
                    ? `${(signal.score_details.foreign_net_buy / 100000000).toFixed(0)}억`
                    : `${(signal.score_details.foreign_net_buy / 10000).toFixed(0)}만`
                  : '-'
                }
              </div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-gray-500 mb-1 flex items-center justify-center gap-1">
                기관 (5일)
                <Tooltip content="최근 5일간 기관 순매수 합계입니다. 양수는 순매수, 음수는 순매도를 의미합니다.">
                  <i className="fas fa-info-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </div>
              <div className={`text-sm font-bold ${(signal.score_details?.inst_net_buy || 0) > 0 ? 'text-rose-400' :
                (signal.score_details?.inst_net_buy || 0) < 0 ? 'text-blue-400' : 'text-gray-400'
                }`}>
                {(signal.score_details?.inst_net_buy)
                  ? Math.abs(signal.score_details.inst_net_buy) >= 100000000
                    ? `${(signal.score_details.inst_net_buy / 100000000).toFixed(0)}억`
                    : `${(signal.score_details.inst_net_buy / 10000).toFixed(0)}만`
                  : '-'
                }
              </div>
            </div>
          </div>

          {/* AI Analysis Result (Action / Confidence) - NEW */}
          {aiEval && (
            <div className="flex items-center justify-between bg-white/5 rounded-lg p-2 mb-3">
              <Tooltip content="Gemini AI의 매매 추천입니다. BUY(매수), HOLD(관망), SELL(매도) 중 하나입니다." position="bottom" align="left" wide>
                <div className={`px-2 py-0.5 rounded text-[10px] font-bold border cursor-help ${aiEval.action === 'BUY' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                  aiEval.action === 'SELL' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
                    'bg-gray-500/20 text-gray-400 border-gray-500/30'
                  }`}>
                  {aiEval.action}
                </div>
              </Tooltip>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 flex items-center gap-1">
                  확신도
                  <Tooltip content="AI가 평가한 추천 신뢰도입니다. 높을수록 강력한 시그널입니다.">
                    <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                  </Tooltip>
                </span>
                <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${aiEval.confidence >= 80 ? 'bg-purple-500' : aiEval.confidence >= 60 ? 'bg-indigo-500' : 'bg-gray-500'}`}
                    style={{ width: `${Math.min(aiEval.confidence, 100)}%` }}
                  ></div>
                </div>
                <span className="text-[10px] font-mono text-white">{Math.min(aiEval.confidence, 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          {/* Chart Area */}
          {/* Chart Area */}
          <div className="relative h-24 bg-[#131722] rounded-xl overflow-hidden mb-2 cursor-pointer group/chart" onClick={onOpenChart}>
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
        <div className="p-5 lg:w-[45%] border-b lg:border-b-0 lg:border-r border-white/10 flex flex-col justify-between">
          <div>
            <h4 className="text-xs font-bold text-gray-400 mb-3 flex items-center gap-2">
              <i className="fas fa-microscope text-indigo-400"></i> AI 분석 리포트
              {(aiEval.model || signal.score.llm_reason) && (
                <span className="text-[10px] font-normal text-indigo-300 bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                  {aiEval.model ? aiEval.model.replace(/[-_]/g, ' ') : 'Gemini 2.0 Flash'}
                </span>
              )}
            </h4>
            <p className="text-sm text-gray-300 leading-relaxed line-clamp-4">
              {signal.score.llm_reason || "AI 분석 대기 중입니다..."}
            </p>
          </div>

          <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-2 gap-4">
            <div>
              <h5 className="text-[10px] text-gray-500 mb-2 font-bold flex items-center gap-1">
                전략 포인트
                <Tooltip content="AI가 분석한 최적의 매매 가격대입니다. 시장 상황에 따라 유동적으로 대응하세요.">
                  <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
                </Tooltip>
              </h5>
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
                    : <span className="text-emerald-400 font-mono">₩{(signal.buy_price || signal.entry_price || 0).toLocaleString()}</span>
                  </span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-amber-500 mt-0.5">●</span>
                  <span>
                    <Tooltip content={
                      <div className="text-[10px] leading-snug text-left w-48">
                        <span className="text-amber-400 font-bold block mb-1 text-center">🟠 매도 전략</span>
                        <ul className="list-disc pl-4 space-y-0.5 text-gray-300">
                          <li><strong>+2.5%</strong>: 시초가 1/3 분할 매도</li>
                          <li><strong>+5% (수급↑)</strong>: 5분 내 전량 매도</li>
                          <li><strong>15:50</strong>: 매수 잔량↑ → 홀딩/시간외</li>
                          <li><strong>15:59</strong>: 매도 잔량↑ → 리스크 관리</li>
                        </ul>
                      </div>
                    }>
                      <span className="cursor-help border-b border-dashed border-gray-600 hover:border-amber-500 hover:text-amber-400 transition-colors">목표가</span>
                    </Tooltip>
                    : <span className="text-amber-400 font-mono">₩{signal.target_price?.toLocaleString()}</span>
                  </span>
                </li>
                <li className="flex items-start gap-1.5">
                  <span className="text-rose-500 mt-0.5">●</span>
                  <span>
                    <Tooltip content={
                      <div className="text-[10px] leading-snug text-left w-48">
                        <span className="text-rose-400 font-bold block mb-1 text-center">🔴 손절 전략</span>
                        <ul className="list-disc pl-4 space-y-0.5 text-gray-300">
                          <li><strong>-1% ~ -3%</strong> (2~3만원):<br />무조건 손절</li>
                          <li><strong>큰 금액 투자시</strong> (10만원↑):<br />-0.5% ~ -1% 즉시 손절</li>
                        </ul>
                      </div>
                    }>
                      <span className="cursor-help border-b border-dashed border-gray-600 hover:border-rose-500 hover:text-rose-400 transition-colors">손절가</span>
                    </Tooltip>
                    : <span className="text-rose-400 font-mono">₩{signal.stop_price?.toLocaleString()}</span>
                  </span>
                </li>
              </ul>
            </div>
            <div>
              <h5 className="text-[10px] text-gray-500 mb-2 font-bold">체크리스트</h5>
              <div className="space-y-1">
                <div className={`text-[10px] px-2 py-1 rounded w-fit ${signal.checklist.has_news ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-500'}`}>
                  {signal.checklist.has_news ? '뉴스/호재 있음' : '특별한 호재 없음'}
                </div>
                <div className={`text-[10px] px-2 py-1 rounded w-fit ${signal.checklist.supply_positive ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-500'}`}>
                  {signal.checklist.supply_positive ? '수급 양호 (외인/기관)' : '수급 보통'}
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
        <div className="p-5 lg:w-[30%] flex flex-col justify-between bg-black/20">
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
                  strokeDashoffset={`${2 * Math.PI * 40 * (1 - signal.score.total / 12)}`}
                  className="transition-all duration-1000 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-bold text-white">{signal.score.total}</span>
                <span className="text-[10px] text-gray-500">/ 12점</span>
              </div>
            </div>
            <div className="text-xs text-gray-400 mt-2 font-medium flex items-center justify-center gap-1">
              TOTAL SCORE
              <Tooltip content="6개 항목(News, Volume, Chart, Supply, Timing, Candle)의 합계 점수입니다. 최대 12점이며, 8점 이상이면 강력한 매수 신호입니다." position="bottom">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 text-[8px] cursor-help"></i>
              </Tooltip>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-center text-[10px] text-gray-500 mb-4 px-2">
            <div className="bg-white/5 rounded py-1 hover:bg-white/10 transition-colors">
              <Tooltip content="차트 패턴: 신고가/돌파 여부 및 추세 분석 (최대 2점)">
                <div className="cursor-help">차트</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.chart}/2</div>
            </div>
            <div className="bg-white/5 rounded py-1 hover:bg-white/10 transition-colors">
              <Tooltip content="수급 점수: 외국인/기관 순매수 강도 (최대 2점)">
                <div className="cursor-help">수급</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.supply}/2</div>
            </div>
            <div className="bg-white/5 rounded py-1 hover:bg-white/10 transition-colors">
              <Tooltip content="관련 뉴스 점수: 최근 3일간 관련 뉴스 품질 및 수량 평가 (최대 3점)">
                <div className="cursor-help">뉴스</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.news}/3</div>
            </div>
            <div className="bg-white/5 rounded py-1 hover:bg-white/10 transition-colors">
              <Tooltip content="거래대금 점수: 1조(3점), 5000억(2점), 1000억(1점) (최대 3점)">
                <div className="cursor-help">거래량</div>
              </Tooltip>
              <div className="text-white font-bold">{signal.score.volume}/3</div>
            </div>
          </div>

          <div className="mt-auto space-y-2">
            <button
              onClick={onOpenDetail}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold rounded-xl transition-all shadow-lg shadow-indigo-500/20 active:scale-95 flex items-center justify-center gap-2"
            >
              <i className="fas fa-search-plus"></i> 상세 분석 보기
            </button>
            <div className="grid grid-cols-2 gap-2">
              <a
                href={`https://m.stock.naver.com/domestic/stock/${signal.stock_code}/main`}
                target="_blank"
                rel="noopener noreferrer"
                className="py-2.5 bg-[#03c75a] hover:bg-[#02b351] text-white text-sm font-bold rounded-xl transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2"
              >
                <span className="font-serif font-black">N</span> 네이버
              </a>
              <a
                href={`https://tossinvest.com/stocks/${signal.stock_code}`}
                target="_blank"
                rel="noopener noreferrer"
                className="py-2.5 bg-[#3182f6] hover:bg-[#1b64da] text-white text-sm font-bold rounded-xl transition-all shadow-lg active:scale-95 flex items-center justify-center gap-2"
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

function GradeGuideModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
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
            <span className="text-xs text-slate-500">※ 거래대금 300억 미만 자동 제외</span>
          </div>

          <div className="overflow-hidden rounded-xl border border-white/10">
            <table className="w-full text-xs text-left">
              <thead className="bg-white/5 text-slate-400 font-medium">
                <tr>
                  <th className="px-4 py-3 w-16 text-center">등급</th>
                  <th className="px-4 py-3">거래대금 & 등락률</th>
                  <th className="px-4 py-3">점수 (Total Score)</th>
                  <th className="px-4 py-3">추가 조건 (거래량/수급)</th>
                  <th className="px-4 py-3">비고</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-300">
                <tr className="bg-indigo-500/5 hover:bg-indigo-500/10 transition-colors">
                  <td className="px-4 py-3 font-bold text-indigo-400 text-center text-sm">S 급</td>
                  <td className="px-4 py-3">
                    <span className="block text-indigo-300 font-bold mb-1">1조 원 이상</span>
                    <span className="text-rose-400 font-bold">+10% 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white">10점 이상</td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>거래량 5배↑</div>
                    <div className="text-emerald-400">외인+기관 양매수</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">초대형 수급 폭발</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-rose-400 text-center text-sm">A 급</td>
                  <td className="px-4 py-3">
                    <span className="block text-rose-300 font-bold mb-1">5,000억 이상</span>
                    <span className="text-rose-400 font-bold">+5% 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white">8점 이상</td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>거래량 3배↑</div>
                    <div>외인 or 기관</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">대형 우량주</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-blue-400 text-center text-sm">B 급</td>
                  <td className="px-4 py-3">
                    <span className="block text-blue-300 font-bold mb-1">1,000억 이상</span>
                    <span className="text-rose-400 font-bold">+4% 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white">6점 이상</td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>거래량 2배↑</div>
                    <div>외인 or 기관</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">중형 주도주</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-emerald-400 text-center text-sm">C 급</td>
                  <td className="px-4 py-3">
                    <span className="block text-emerald-300 font-bold mb-1">500억 이상</span>
                    <span className="text-rose-400 font-bold">+5% 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white">8점 이상</td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>거래량 3배↑</div>
                    <div className="text-emerald-400">외인+기관 양매수</div>
                  </td>
                  <td className="px-4 py-3 text-slate-400">강소 주도주</td>
                </tr>
                <tr className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 font-bold text-gray-400 text-center text-sm">D 급</td>
                  <td className="px-4 py-3">
                    <span className="block text-slate-400 font-bold mb-1">500억 이상</span>
                    <span className="text-rose-400 font-bold">+4% 이상</span>
                  </td>
                  <td className="px-4 py-3 font-bold text-white">6점 이상</td>
                  <td className="px-4 py-3 text-slate-400">
                    <div>거래량 2배↑</div>
                    <div className="text-slate-500">수급 무관</div>
                  </td>
                  <td className="px-4 py-3 text-slate-500">관망 / 조건부</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 3. 핵심 평가 요소 */}
        <div className="space-y-3">
          <h3 className="text-base font-bold text-white flex items-center gap-2 border-b border-indigo-500/30 pb-2">
            <span className="px-2 py-0.5 bg-indigo-500/20 text-indigo-400 rounded text-xs">3</span>
            핵심 평가 요소 (Score 12점 만점)
          </h3>
          <p className="text-xs text-gray-400">
            위 점수 조건에 사용되는 항목별 배점입니다.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>📰 뉴스</span>
                <span className="text-indigo-400">3점</span>
              </div>
              <div className="text-xs text-gray-400">호재성 기사 유무 및 AI 강도 평가</div>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>💰 거래대금</span>
                <span className="text-indigo-400">3점</span>
              </div>
              <div className="text-xs text-gray-400">시장 주도력 평가 (유동성)</div>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>📈 차트</span>
                <span className="text-indigo-400">2점</span>
              </div>
              <div className="text-xs text-gray-400">신고가, 이평선 정배열 등 </div>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>🤝 수급</span>
                <span className="text-indigo-400">2점</span>
              </div>
              <div className="text-xs text-gray-400">외인/기관 순매수 지속성</div>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>🕯 캔들</span>
                <span className="text-indigo-400">1점</span>
              </div>
              <div className="text-xs text-gray-400">장대양봉 및 윗꼬리 관리 여부</div>
            </div>
            <div className="bg-white/5 rounded-xl p-3 border border-white/5 flex flex-col gap-1">
              <div className="flex justify-between items-center text-sm font-bold text-white">
                <span>⏳ 기간조정</span>
                <span className="text-indigo-400">1점</span>
              </div>
              <div className="text-xs text-gray-400">볼린저밴드 수축 등 변동성 축소 후 발산</div>
            </div>
          </div>
        </div>

      </div>
    </Modal>
  );
}


function ScoreBar({ label, score, max, color, tooltip }: { label: string, score: number, max: number, color: string, tooltip?: string }) {
  const widthPct = Math.min((score / max) * 100, 100);
  return (
    <div className="flex items-center gap-3 group relative">
      <div className="w-14 text-xs font-medium text-gray-400 cursor-help" title={tooltip || label}>{label}</div>
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${widthPct}%` }}
        ></div>
      </div>
      <div className="w-8 text-xs font-mono text-gray-400 text-right">{score}<span className="text-gray-600">/{max}</span></div>
      {tooltip && (
        <div className="absolute left-0 bottom-full mb-2 w-52 px-3 py-2 bg-gray-900 text-gray-200 text-[10px] rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 border border-white/10 shadow-2xl whitespace-normal">
          {tooltip}
          <div className="absolute top-full left-4 -mt-1 border-4 border-transparent border-t-gray-900"></div>
        </div>
      )}
    </div>
  );
}
