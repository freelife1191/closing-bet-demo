'use client';

import { useEffect, useState, useRef } from 'react';
import { krAPI, KRMarketGate, KRSignalsResponse, DataStatus, fetchAPI } from '@/lib/api';

function Tooltip({ children, content, className = "", position = "top", align = "center" }: { children: React.ReactNode, content: string, className?: string, position?: 'top' | 'bottom', align?: 'left' | 'center' | 'right' }) {
  const positionClass = position === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2';
  const arrowClass = position === 'bottom' ? 'bottom-full border-b-gray-900/95 -mb-1' : 'top-full border-t-gray-900/95 -mt-1';

  // Alignment classes
  let alignClass = 'left-1/2 -translate-x-1/2'; // Default center
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
      <div className={`absolute ${alignClass} ${positionClass} w-56 px-3 py-2 bg-gray-900/95 text-gray-200 text-[11px] font-medium rounded-lg opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-50 border border-white/10 shadow-xl backdrop-blur-sm text-center leading-relaxed`}>
        {content}
        <div className={`absolute ${arrowAlignClass} border-4 border-transparent ${arrowClass}`}></div>
      </div>
    </span>
  );
}

interface BacktestStats {
  status: string;
  count: number;
  win_rate: number;
  avg_return: number;
  profit_factor?: number;
  message?: string;
}

interface BacktestSummary {
  vcp: BacktestStats;
  closing_bet: BacktestStats & {
    candidates?: any[]; // For filtering
  };
}

export default function KRMarketOverview() {
  const [gateData, setGateData] = useState<KRMarketGate | null>(null);
  const [signalsData, setSignalsData] = useState<KRSignalsResponse | null>(null);
  const [backtestData, setBacktestData] = useState<BacktestSummary | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  // 날짜 선택 상태
  const [topSectors, setTopSectors] = useState<any[]>([]); // New state for top sectors
  const [useTodayMode, setUseTodayMode] = useState(true);
  const [targetDate, setTargetDate] = useState('');
  const [mgLoading, setMgLoading] = useState(false);
  const [updateInterval, setUpdateInterval] = useState(30); // Default 30min
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 설정값 로드
  useEffect(() => {
    fetch('/api/kr/config/interval')
      .then(res => res.json())
      .then(data => {
        if (data.interval) setUpdateInterval(data.interval);
      })
      .catch(err => console.error('Failed to load interval config:', err));
  }, []);

  const handleIntervalChange = async (minutes: number) => {
    try {
      setUpdateInterval(minutes); // UI 즉시 반영 (낙관적 업데이트)
      const res = await fetch('/api/kr/config/interval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval: minutes })
      });
      if (!res.ok) throw new Error('Failed to update interval');
      console.log(`Update interval changed to ${minutes} min`);
    } catch (error) {
      console.error('Error changing interval:', error);
      // 실패 시 롤백 로직이 필요할 수 있음
    }
  };


  useEffect(() => {
    // 0 or custom interval handling
    const intervalMs = (updateInterval > 0 ? updateInterval : 30) * 60 * 1000;

    // Initial load happens in the other useEffect(loadData), here we just set the interval
    const intervalId = setInterval(() => {
      // Only refresh if looking at today's data ("Realtime" mode)
      if (useTodayMode) {
        console.log(`[Auto-Refresh] Fetching data... (Interval: ${updateInterval}m)`);
        loadData();
      }
    }, intervalMs);

    return () => clearInterval(intervalId);
  }, [updateInterval, useTodayMode]); // Re-run when interval or mode changes

  // 최근 영업일 계산
  const getLastBusinessDay = () => {
    const d = new Date();
    const day = d.getDay();
    if (day === 0) d.setDate(d.getDate() - 2);
    else if (day === 6) d.setDate(d.getDate() - 1);
    // 09시 이전이면 전일 기준 (서버 데이터 기준에 맞춤)
    if (d.getHours() < 9) d.setDate(d.getDate() - 1);

    // 주말 처리 후 다시 주말일 경우 (토/일 -> 금 확인) 재귀보다는 단순 처리
    if (d.getDay() === 0) d.setDate(d.getDate() - 2);
    else if (d.getDay() === 6) d.setDate(d.getDate() - 1);

    return d.toISOString().split('T')[0];
  };

  useEffect(() => {
    loadData();
  }, [useTodayMode, targetDate]); // 의존성 추가 (날짜 변경 시 자동 로드)

  const loadData = async () => {
    // Safety: Force loading to false after 15s
    const safetyTimer = setTimeout(() => {
      setLoading(prev => {
        if (prev) {
          console.warn('[Safety] Force stopping loading spinner');
          return false;
        }
        return prev;
      });
    }, 15000);

    // Clear pending retry since we are loading now
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    setLoading(true);
    try {
      // 날짜 파라미터 결정
      const dateParam = useTodayMode ? undefined : (targetDate || getLastBusinessDay());

      // 모든 데이터 로드를 병렬로 처리하되, 하나가 실패해도 나머지는 표시되도록 allSettled 사용
      const [gateResult, signalsResult, statusResult, btResult] = await Promise.allSettled([
        krAPI.getMarketGate(dateParam),
        krAPI.getSignals(dateParam),
        krAPI.getDataStatus(),
        fetchAPI<BacktestSummary>('/api/kr/backtest-summary') // Updated to fetchAPI for consistency
      ]);

      // Market Gate 데이터 처리
      if (gateResult.status === 'fulfilled') {
        setGateData(gateResult.value);
      } else {
        console.error('Failed to load Market Gate:', gateResult.reason);
      }

      // Signals 데이터 처리
      if (signalsResult.status === 'fulfilled') {
        setSignalsData(signalsResult.value);
      } else {
        console.error('Failed to load Signals:', signalsResult.reason);
      }

      // Status 데이터 처리
      if (statusResult.status === 'fulfilled') {
        if (statusResult.value && statusResult.value.data) {
          setDataStatus(statusResult.value.data);
        }
      } else {
        console.error('Failed to load Data Status:', statusResult.reason);
      }

      // Backtest 데이터 처리
      if (btResult.status === 'fulfilled') {
        setBacktestData(btResult.value);
      } else {
        console.error('Failed to load Backtest Summary:', btResult.reason);
      }


      // [Auto-Recovery] If initializing or empty in Realtime Mode -> Rapid Polling (5s)
      if (useTodayMode) {
        const isInitializing =
          (gateResult.status === 'fulfilled' && (gateResult.value?.status === 'initializing' || gateResult.value?.message?.includes('대기'))) ||
          (signalsResult.status === 'fulfilled' && (!signalsResult.value?.signals || signalsResult.value.signals.length === 0));

        if (isInitializing) {
          console.log('[Auto-Recovery] Data not ready. Retrying in 5s...');
          if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
          retryTimerRef.current = setTimeout(loadData, 5000);
        }
      }

      setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
    } catch (error) {
      console.error('Critical Error in loadData:', error);
    } finally {
      clearTimeout(safetyTimer);
      setLoading(false);
    }
  };

  const refreshMarketGate = async () => {
    if (mgLoading) return;
    setMgLoading(true);
    try {
      const dateParam = useTodayMode ? undefined : (targetDate || getLastBusinessDay());
      await krAPI.updateMarketGate(dateParam);
      // 업데이트 후 데이터 다시 로드
      const gate = await krAPI.getMarketGate(dateParam);
      setGateData(gate);
    } catch (e) {
      console.error('Market Gate update failed', e);
    } finally {
      setMgLoading(false);
    }
  };

  const refreshData = async () => {
    setLoading(true);
    try {
      const dateParam = useTodayMode ? undefined : (targetDate || getLastBusinessDay());
      const refreshRes = await fetch('/api/kr/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_date: dateParam })
      });
      if (!refreshRes.ok) {
        console.error('Refresh API failed');
      }
      await loadData();
    } catch (error) {
      console.error('Failed to refresh data:', error);
      setLoading(false);
    }
  };

  const getGateColor = (score: number) => {
    if (score >= 70) return 'text-green-500';
    if (score >= 40) return 'text-yellow-500';
    return 'text-red-500';
  };

  const getSectorColor = (signal: string) => {
    if (signal === 'bullish') return 'bg-green-500/20 text-green-400 border-green-500/30';
    if (signal === 'bearish') return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  };

  const renderTradeCount = (count: number) => {
    return count > 0 ? `${count} trades` : 'No trades';
  };

  const getGateStatusColor = (status: string, score?: number) => {
    const s = status?.toUpperCase();
    if (s === 'GREEN' || s === 'BULLISH') return 'text-green-500';
    if (s === 'RED' || s === 'BEARISH') return 'text-red-500';
    if (s === 'YELLOW' || s === 'NEUTRAL' || s === 'SIDEWAYS' || s === 'UNKNOWN') return 'text-yellow-500';

    // Fallback: Score based
    if (score !== undefined) {
      if (score >= 70) return 'text-green-500';
      if (score >= 40) return 'text-yellow-500';
      return 'text-red-500';
    }

    return 'text-gray-500';
  };

  /**
   * Helper: Format number with smart decimals
   * - Indices/Crypto/Commodities: No decimals (user request), unless value < 10 (e.g. XRP)
   */
  const formatFinancialValue = (val: number | undefined) => {
    if (val === undefined || val === null) return '--';
    // If value is small (< 10), keep 2 decimals (e.g. XRP $1.26)
    // Otherwise, integer only (e.g. KOSPI 2500, BTC 60000)
    const maxDecimals = val < 10 ? 2 : 0;
    return val.toLocaleString(undefined, { maximumFractionDigits: maxDecimals });
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-rose-500/20 bg-rose-500/5 text-xs text-rose-400 font-medium mb-4">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
            KR 마켓 알파
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
            스마트머니 <span className="text-transparent bg-clip-text bg-gradient-to-r from-rose-400 to-amber-400">추적</span>
          </h2>
          <p className="text-gray-400 text-lg">VCP 패턴 & 기관/외국인 수급 추적</p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-3 bg-[#1c1c1e] p-1 rounded-lg border border-white/10">
            <button
              onClick={() => { setUseTodayMode(true); setTargetDate(''); }} // 실시간 복귀 시 날짜 초기화
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${useTodayMode
                ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
            >
              <i className="fas fa-clock mr-1.5"></i>
              실시간
            </button>
            <button
              onClick={() => { setUseTodayMode(false); if (!targetDate) setTargetDate(getLastBusinessDay()); }}
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${!useTodayMode
                ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/20'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
            >
              <i className="far fa-calendar-alt mr-1.5"></i>
              날짜 지정
            </button>
          </div>

          <div className="flex flex-col items-end gap-1 px-1">
            <div className="text-[10px] text-gray-500 font-medium flex items-center gap-1.5 relative group">
              <span className="w-1 h-1 rounded-full bg-blue-500/50"></span>
              매크로 지표:
              {/* 커스텀 값인 경우 number input 표시 */}
              {![1, 5, 10, 15, 30, 60].includes(updateInterval) ? (
                <div className="flex items-center gap-1 ml-0.5">
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    value={updateInterval}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      if (val >= 1 && val <= 1440) {
                        handleIntervalChange(val);
                      }
                    }}
                    className="w-12 bg-[#1c1c1e] border border-gray-700 rounded text-[10px] px-1.5 py-0.5 text-center text-blue-400 focus:outline-none focus:border-blue-500 [appearance:textfield] [&::-webkit-outer-spin-button]:opacity-100 [&::-webkit-inner-spin-button]:opacity-100"
                  />
                  <span className="text-[10px] text-gray-500">분</span>
                  <button
                    onClick={() => handleIntervalChange(5)}
                    className="text-[9px] text-gray-600 hover:text-gray-400 ml-1"
                    title="기본값(5분)으로 초기화"
                  >
                    <i className="fas fa-times"></i>
                  </button>
                </div>
              ) : (
                <select
                  value={updateInterval}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === 'custom') {
                      // 직접입력 선택시 기본값 2로 시작
                      handleIntervalChange(2);
                    } else {
                      handleIntervalChange(Number(val));
                    }
                  }}
                  className="bg-transparent border-none text-[10px] font-bold text-gray-400 hover:text-blue-400 focus:ring-0 cursor-pointer appearance-none text-right pr-0 ml-0.5 transition-colors outline-none"
                  style={{ WebkitAppearance: 'none', MozAppearance: 'none' }}
                >
                  <option value={1} className="bg-[#1c1c1e] text-gray-300">1분</option>
                  <option value={5} className="bg-[#1c1c1e] text-gray-300">5분</option>
                  <option value={10} className="bg-[#1c1c1e] text-gray-300">10분</option>
                  <option value={15} className="bg-[#1c1c1e] text-gray-300">15분</option>
                  <option value={30} className="bg-[#1c1c1e] text-gray-300">30분</option>
                  <option value={60} className="bg-[#1c1c1e] text-gray-300">60분</option>
                  <option value="custom" className="bg-[#1c1c1e] text-gray-300">직접입력...</option>
                </select>
              )}
              <span className="text-gray-500 ml-1">마다 자동 갱신</span>
              {/* Custom Arrow for Dropdown */}
              {[1, 5, 10, 15, 30, 60].includes(updateInterval) && (
                <i className="fas fa-chevron-down text-[8px] text-gray-600 ml-1 group-hover:text-blue-500 transition-colors pointer-events-none absolute right-full mr-1 opacity-0 group-hover:opacity-100"></i>
              )}
            </div>
            <div className="text-[10px] text-gray-500 font-medium flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-gray-600"></span>
              시그널 분석: 매일 15:40 (KST)
            </div>
            {lastUpdated && (
              <div className="text-[10px] text-emerald-500/70 font-bold flex items-center gap-1.5 mt-0.5">
                <span className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse"></span>
                마지막 업데이트: {lastUpdated}
              </div>
            )}
          </div>

          {!useTodayMode && (
            <div className="flex items-center gap-2 animate-in fade-in slide-in-from-top-1 mt-1">
              <input
                type="date"
                value={targetDate}
                max={new Date().toISOString().split('T')[0]} // 미래 날짜 방지
                onChange={(e) => setTargetDate(e.target.value)}
                className="bg-[#1c1c1e] border border-white/20 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
              />
            </div>
          )}
        </div>
      </div>

      {/* Market Gate Section */}
      <section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Gate Score Card */}
        <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity text-rose-500">
            <i className="fas fa-chart-line text-4xl"></i>
          </div>
          <h3 className="text-sm font-bold text-gray-400 mb-4 flex items-center gap-2 relative z-10">
            KR Market Gate
            <Tooltip content="시장 강도(Score)와 수급 상태를 종합 분석한 마켓 타이밍 지표입니다." position="bottom" align="left">
              <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
            </Tooltip>
            <button
              onClick={refreshMarketGate}
              disabled={mgLoading}
              className={`ml-1 p-1.5 rounded-full bg-white/5 hover:bg-white/10 text-[10px] text-gray-400 hover:text-white transition-all ${mgLoading ? 'animate-spin opacity-50' : ''}`}
              title="Refresh Market Gate Only"
            >
              <i className="fas fa-sync-alt"></i>
            </button>
            <div className="hidden lg:block ml-auto w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></div>
          </h3>
          <div className="flex flex-col items-center justify-center py-2">
            <div className="relative w-32 h-32 flex items-center justify-center">
              <svg className="w-full h-full -rotate-90">
                <circle cx="64" cy="64" r="58" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-white/5" />
                <circle
                  cx="64" cy="64" r="58"
                  stroke="currentColor"
                  strokeWidth="8"
                  fill="transparent"
                  strokeDasharray="364.4"
                  strokeDashoffset={364.4 - (364.4 * (gateData?.score ?? 0) / 100)}
                  className={`${getGateStatusColor(gateData?.status ?? 'GRAY', gateData?.score)} transition-all duration-1000 ease-out`}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-3xl font-black ${getGateStatusColor(gateData?.status ?? 'GRAY', gateData?.score)}`}>
                  {loading ? '--' : gateData?.score ?? '--'}
                </span>
                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Score</span>
              </div>
            </div>
            <div className={`mt-4 px-4 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold ${getGateStatusColor(gateData?.status ?? 'GRAY', gateData?.score)}`}>
              <Tooltip content={gateData?.label === 'Bullish' ? '상승장 (매수 우위)' : gateData?.label === 'Bearish' ? '하락장 (매도 우위)' : '중립/혼조세 (방향성 탐색)'} position="bottom">
                {loading ? 'Analyzing...' : (gateData?.label === 'Unknown' || gateData?.label === 'UnKnown' ? 'Neutral' : gateData?.label ?? 'Neutral')}
              </Tooltip>
            </div>
          </div>
        </div>

        {/* Sector Grid */}
        <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-400 flex items-center gap-2">
              KOSPI 200 Sector Index
              <Tooltip content="KOSPI 200 주요 섹터별 등락 현황입니다." position="bottom">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
              </Tooltip>
            </h3>
            <div className="flex items-center gap-4 text-[10px] font-bold text-gray-500 uppercase tracking-tighter">
              <Tooltip content="상승세: 20/60일 이평 상회 및 수급 유입" position="bottom">
                <span className="flex items-center gap-1 cursor-help"><span className="w-2 h-2 rounded-full bg-green-500"></span> Bullish</span>
              </Tooltip>
              <Tooltip content="혼조세: 방향성 탐색 중" position="bottom">
                <span className="flex items-center gap-1 cursor-help"><span className="w-2 h-2 rounded-full bg-yellow-500"></span> Neutral</span>
              </Tooltip>
              <Tooltip content="하락세: 주요 이평 하회 및 수급 이탈" position="bottom">
                <span className="flex items-center gap-1 cursor-help"><span className="w-2 h-2 rounded-full bg-red-500"></span> Bearish</span>
              </Tooltip>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-16 rounded-xl bg-white/5 animate-pulse border border-white/5"></div>
              ))
            ) : (
              gateData?.sectors?.map((sector) => (
                <div
                  key={sector.name}
                  className={`p-3 rounded-xl border ${getSectorColor(sector.signal)} transition-all hover:scale-105`}
                >
                  <div className="text-xs font-bold truncate">{sector.name}</div>
                  <div className={`text-lg font-black ${sector.change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    {sector.change_pct >= 0 ? '+' : ''}{sector.change_pct.toFixed(2)}%
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* KPI Cards (Performance Overview) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Today's Signals */}
        <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
          <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
          <div className="flex items-center gap-2 mb-1">
            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Today&apos;s Signals</div>
            <Tooltip content="오늘 포착된 VCP 패턴 + 수급 유입 종목 수입니다." position="bottom" align="left">
              <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
            </Tooltip>
          </div>
          <div className="text-3xl font-black text-white group-hover:text-rose-400 transition-colors">
            {loading ? '--' : signalsData?.signals?.length ?? 0}
          </div>
          <div className="mt-2 text-xs text-gray-500">VCP + 외국인 순매수</div>
        </div>

        {/* 2. VCP Strategy Performance */}
        <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-amber-500/30 transition-all">
          <div className="absolute top-0 right-0 w-20 h-20 bg-amber-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-2 mb-1">
              <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">VCP Strategy</div>
              <Tooltip content="VCP 전략(변동성 축소 패턴)의 과거 성과(승률) 분석 결과입니다." position="bottom" align="left">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
              </Tooltip>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 text-[10px] font-bold border border-amber-500/20">Win Rate</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-black text-white group-hover:text-amber-400 transition-colors">
              {loading ? '--' : backtestData?.vcp?.win_rate ?? 0}<span className="text-base text-gray-600">%</span>
            </span>
            <span className={`text-xs font-bold ${(backtestData?.vcp?.avg_return ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
              Avg. {(backtestData?.vcp?.avg_return ?? 0) > 0 ? '+' : ''}{backtestData?.vcp?.avg_return}%
            </span>
          </div>
          <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
            <span>{renderTradeCount(backtestData?.vcp?.count ?? 0)}</span>
            {backtestData?.vcp?.status === 'OK' && <i className="fas fa-check-circle text-emerald-500"></i>}
          </div>
        </div>

        {/* 3. Closing Bet Performance */}
        <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-emerald-500/30 transition-all">
          <div className="absolute top-0 right-0 w-20 h-20 bg-emerald-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-2 mb-1">
              <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">종가베팅</div>
              <Tooltip content="종가베팅 전략(장 마감 전 진입)의 성과 분석 결과입니다." position="bottom" align="left">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
              </Tooltip>
            </div>
            {backtestData?.closing_bet?.status === 'Accumulating' ? (
              <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 text-[10px] font-bold border border-amber-500/20 animate-pulse">
                <i className="fas fa-hourglass-half mr-1"></i>축적 중
              </span>
            ) : (
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 text-[10px] font-bold border border-emerald-500/20">Win Rate</span>
            )}
          </div>
          {backtestData?.closing_bet?.status === 'Accumulating' ? (
            <div className="py-4">
              <div className="text-2xl font-black text-amber-400 mb-1">
                <i className="fas fa-database mr-2"></i>데이터 축적 중
              </div>
              <div className="text-xs text-gray-500">
                {backtestData?.closing_bet?.message || '최소 2일 데이터 필요'}
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-black text-white group-hover:text-emerald-400 transition-colors">
                  {loading ? '--' : backtestData?.closing_bet?.win_rate ?? 0}<span className="text-base text-gray-600">%</span>
                </span>
                <span className={`text-xs font-bold ${(backtestData?.closing_bet?.avg_return ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                  Avg. {(backtestData?.closing_bet?.avg_return ?? 0) > 0 ? '+' : ''}{backtestData?.closing_bet?.avg_return}%
                </span>
              </div>
              <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
                <span>{renderTradeCount(backtestData?.closing_bet?.count ?? 0)}</span>
                {backtestData?.closing_bet?.status === 'OK' && <i className="fas fa-check-circle text-emerald-500"></i>}
              </div>
            </>
          )}
        </div>

        {/* 4. Update Button */}
        <button
          onClick={refreshData}
          disabled={loading}
          className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 flex flex-col justify-center items-center gap-2 cursor-pointer hover:bg-white/5 transition-all group disabled:opacity-50"
        >
          <div className={`w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-white group-hover:rotate-180 transition-transform duration-500 ${loading ? 'animate-spin' : ''}`}>
            <i className="fas fa-sync-alt"></i>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-white">Refresh Data</div>
            <div className="text-[10px] text-gray-500">Last: {lastUpdated || '-'}</div>
          </div>
        </button>
      </div>

      <section className="space-y-6">
        {/* 1. Global Indices */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span className="w-1 h-5 bg-rose-500 rounded-full"></span>
              Market Indices
              <Tooltip content="주요 국내외 증시 지수 현황입니다.">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-xs"></i>
              </Tooltip>
            </h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* KOSPI */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KOSPI</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.kospi_close)}
                </span>
                {gateData && (
                  <span className={`text-xs font-bold mb-0.5 ${gateData.kospi_change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${gateData.kospi_change_pct >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {gateData.kospi_change_pct >= 0 ? '+' : ''}{gateData.kospi_change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* KOSDAQ */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KOSDAQ</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.kosdaq_close)}
                </span>
                {gateData && (
                  <span className={`text-xs font-bold mb-0.5 ${gateData.kosdaq_change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${gateData.kosdaq_change_pct >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {gateData.kosdaq_change_pct >= 0 ? '+' : ''}{gateData.kosdaq_change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* S&P 500 */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">S&P 500</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.indices?.sp500?.value)}
                </span>
                {gateData?.indices?.sp500 && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.indices.sp500.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.indices.sp500.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.indices.sp500.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.indices.sp500.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* NASDAQ */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">NASDAQ</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.indices?.nasdaq?.value)}
                </span>
                {gateData?.indices?.nasdaq && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.indices.nasdaq.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.indices.nasdaq.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.indices.nasdaq.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.indices.nasdaq.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 2. Commodities */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-400 flex items-center gap-2">
              <span className="w-1 h-5 bg-amber-500 rounded-full"></span>
              Commodities
              <Tooltip content="금, 은 등 주요 원자재 가격 동향입니다.">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-xs"></i>
              </Tooltip>
            </h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* KRX GOLD */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KRX GOLD</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.commodities?.gold?.value)}
                </span>
                {gateData?.commodities?.gold && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.commodities.gold.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.commodities.gold.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.commodities.gold.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.commodities.gold.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* KRX SILVER */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KRX SILVER</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.commodities?.silver?.value)}
                </span>
                {gateData?.commodities?.silver && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.commodities.silver.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.commodities.silver.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.commodities.silver.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.commodities.silver.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* US GOLD (F) */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">US GOLD (F)</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  ${loading ? '--' : formatFinancialValue(gateData?.commodities?.us_gold?.value)}
                </span>
                {gateData?.commodities?.us_gold && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.commodities.us_gold?.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.commodities.us_gold?.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.commodities.us_gold?.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.commodities.us_gold?.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* US SILVER (F) */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">US SILVER (F)</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  ${loading ? '--' : formatFinancialValue(gateData?.commodities?.us_silver?.value)}
                </span>
                {gateData?.commodities?.us_silver && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.commodities.us_silver?.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.commodities.us_silver?.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.commodities.us_silver?.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.commodities.us_silver?.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Crypto */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-bold text-gray-400 flex items-center gap-2">
              <span className="w-1 h-5 bg-indigo-500 rounded-full"></span>
              Crypto Assets
              <Tooltip content="주요 암호화폐 실시간 시세입니다.">
                <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-xs"></i>
              </Tooltip>
            </h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {/* BITCOIN */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">BITCOIN</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.crypto?.btc?.value)}
                </span>
                {gateData?.crypto?.btc && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.crypto.btc.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.crypto.btc.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.crypto.btc.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.crypto.btc.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* ETHEREUM */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">ETHEREUM</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.crypto?.eth?.value)}
                </span>
                {gateData?.crypto?.eth && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.crypto.eth.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.crypto.eth.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.crypto.eth.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.crypto.eth.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* XRP */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">XRP</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(gateData?.crypto?.xrp?.value)}
                </span>
                {gateData?.crypto?.xrp && (
                  <span className={`text-xs font-bold mb-0.5 ${(gateData.crypto.xrp.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(gateData.crypto.xrp.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(gateData.crypto.xrp.change_pct ?? 0) >= 0 ? '+' : ''}{gateData.crypto.xrp.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
