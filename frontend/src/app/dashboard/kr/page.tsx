'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { krAPI, KRMarketGate, KRSignalsResponse, DataStatus, fetchAPI } from '@/lib/api';
import { MAX_AUTO_RETRIES, shouldScheduleAutoRetry } from './retryHelpers';
import Modal from '@/app/components/Modal';

import Tooltip from '@/app/components/Tooltip';


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

function StrategyGuideModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="AI 전략 성과 지표 가이드" type="default" wide>
      <div className="space-y-8 max-h-[70vh] overflow-y-auto pr-2">

        {/* 1. Performance Metrics Guide */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <i className="fas fa-chart-bar text-amber-400"></i>
              성과 지표 해석
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                  <i className="fas fa-trophy"></i>
                </span>
                <h4 className="font-bold text-white text-sm">승률 (Win Rate)</h4>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">
                전체 매매 횟수 중 <span className="text-emerald-400">수익 실현</span>에 성공한 비율입니다.
                <br />
                <span className="text-gray-500 mt-1 block">계산식: (익절 횟수 / 전체 진입 횟수) × 100</span>
              </p>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-8 h-8 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center">
                  <i className="fas fa-percent"></i>
                </span>
                <h4 className="font-bold text-white text-sm">평균 수익률 (Avg)</h4>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed">
                모든 매매(익절+손절)의 손익률 평균입니다.
                <br />
                <span className="text-gray-500 mt-1 block">손절(-5%)이 포함되므로 낮게 보일 수 있습니다.</span>
              </p>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-8 h-8 rounded-lg bg-purple-500/20 text-purple-400 flex items-center justify-center">
                  <i className="fas fa-star"></i>
                </span>
                <h4 className="font-bold text-white text-sm">성능 등급</h4>
              </div>
              <ul className="text-xs text-gray-400 space-y-1">
                <li className="flex justify-between"><span className="text-emerald-400 font-bold">우수</span> <span>승률 60% 이상</span></li>
                <li className="flex justify-between"><span className="text-amber-400 font-bold">양호</span> <span>승률 40% ~ 59%</span></li>
                <li className="flex justify-between"><span className="text-rose-400 font-bold">미흡</span> <span>승률 40% 미만</span></li>
              </ul>
            </div>
          </div>
        </div>

        {/* 2. Strategy Criteria */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <i className="fas fa-chess-board text-indigo-400"></i>
              전략별 운영 기준
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* VCP Strategy */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30">VCP 전략</span>
                <span className="text-xs text-gray-500">변동성 축소 패턴 (Mark Minervini)</span>
              </div>
              <div className="bg-[#1c1c1e] rounded-xl border border-white/10 p-4 space-y-3">
                <div>
                  <h5 className="text-xs font-bold text-gray-300 mb-1">🎯 타겟 종목</h5>
                  <p className="text-[11px] text-gray-500">기관/외국인 수급이 유입되며 변동성이 줄어드는 주도주</p>
                </div>
                <div className="space-y-2">
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-emerald-500 mt-0.5"></i>
                    <span><strong>이평선 정배열</strong>: 주가 {'>'} 20일 {'>'} 60일 (상승 추세)</span>
                  </div>
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-emerald-500 mt-0.5"></i>
                    <span><strong>거래량 감소</strong>: 조정 구간에서 거래량 급감 (매물 소화)</span>
                  </div>
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-emerald-500 mt-0.5"></i>
                    <span><strong>돌파 시그널</strong>: 저항선 돌파 시 거래량 폭발</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Closing Bet Strategy */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 text-xs font-bold border border-amber-500/30">종가베팅 전략</span>
                <span className="text-xs text-gray-500">장 마감 전 동시호가 공략</span>
              </div>
              <div className="bg-[#1c1c1e] rounded-xl border border-white/10 p-4 space-y-3">
                <div>
                  <h5 className="text-xs font-bold text-gray-300 mb-1">🎯 타겟 종목</h5>
                  <p className="text-[11px] text-gray-500">당일 시장 주도주 중 장 막판까지 수급이 유지되는 종목</p>
                </div>
                <div className="space-y-2">
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-amber-500 mt-0.5"></i>
                    <span><strong>거래대금</strong>: 코스피 1000억↑ / 코스닥 500억↑</span>
                  </div>
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-amber-500 mt-0.5"></i>
                    <span><strong>수급 주체</strong>: 외국인/기관 양매수 or 강력한 순매수</span>
                  </div>
                  <div className="text-[11px] text-gray-400 flex gap-2">
                    <i className="fas fa-check text-amber-500 mt-0.5"></i>
                    <span><strong>고가 마감</strong>: 당일 고가 부근에서 밀리지 않고 마감</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-4 text-center">
          <p className="text-xs text-blue-300">
            <i className="fas fa-info-circle mr-2"></i>
            모든 성과 지표는 <strong>최근 30일(또는 설정된 기간)</strong>의 실제 시그널을 기반으로 자동 계산됩니다.
          </p>
        </div>
      </div>
    </Modal>
  );
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
  const [isStrategyGuideOpen, setIsStrategyGuideOpen] = useState(false);
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);
  const retryCountRef = useRef(0);
  const [autoRetryExhausted, setAutoRetryExhausted] = useState(false);

  const resetAutoRetry = useCallback(() => {
    retryCountRef.current = 0;
    setAutoRetryExhausted(prev => (prev ? false : prev));
  }, []);

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
    return () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
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


      // [Auto-Recovery] If initializing (Market Gate not ready) -> Rapid Polling (5s)
      if (useTodayMode) {
        // [Fixed] Don't retry just because signals are empty (valid state)
        const isInitializing =
          (gateResult.status === 'fulfilled' && (gateResult.value?.status === 'initializing' || gateResult.value?.message?.includes('대기')));

        if (isInitializing) {
          retryCountRef.current += 1;
          if (shouldScheduleAutoRetry(retryCountRef.current, MAX_AUTO_RETRIES, isInitializing)) {
            if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
            retryTimerRef.current = setTimeout(loadData, 5000);
          } else {
            console.error(`[Auto-Recovery] Retry limit (${MAX_AUTO_RETRIES}) exceeded after ~${MAX_AUTO_RETRIES * 5}s. Stopping auto-retry.`);
            setAutoRetryExhausted(true);
          }
        } else {
          // Gate data is ready — reset the retry counter
          resetAutoRetry();
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
    // Reset retry state so a user-initiated refresh starts fresh
    resetAutoRetry();
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
    // Reset retry state so a user-initiated refresh starts fresh
    resetAutoRetry();
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
    const s = signal?.toLowerCase();
    if (s === 'bullish') return 'bg-green-500/20 text-green-400 border-green-500/30';
    if (s === 'bearish') return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  };

  const renderTradeCount = (count: number) => {
    return count > 0 ? `${count} trades` : 'No trades';
  };

  const getGateStatusColor = (status: string, score?: number) => {
    const s = status?.toUpperCase();
    if (s === 'GREEN' || s === 'BULLISH' || s === 'STRONG BULL') return 'text-green-500';
    if (s === 'RED' || s === 'BEARISH' || s === 'DANGER') return 'text-red-500';
    if (s === 'YELLOW' || s === 'NEUTRAL' || s === 'SIDEWAYS') return 'text-yellow-500';

    // Fallback: Score based (Backend Logic: < 40 is Red, >= 40 is Yellow, >= 70 is Green)
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

  const getStrategyStatus = (rate: number) => {
    if (rate >= 60) return { label: '우수', className: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' };
    if (rate >= 40) return { label: '양호', className: 'bg-amber-500/10 text-amber-500 border-amber-500/20' };
    return { label: '미흡', className: 'bg-rose-500/10 text-rose-500 border-rose-500/20' };
  };

  const getStrategyTheme = (rate: number) => {
    if (rate >= 60) return {
      border: 'hover:border-emerald-500/30',
      glow: 'bg-emerald-500/10',
      text: 'group-hover:text-emerald-400',
      icon: 'text-emerald-500'
    };
    if (rate >= 40) return {
      border: 'hover:border-amber-500/30',
      glow: 'bg-amber-500/10',
      text: 'group-hover:text-amber-400',
      icon: 'text-amber-500'
    };
    return {
      border: 'hover:border-rose-500/30',
      glow: 'bg-rose-500/10',
      text: 'group-hover:text-rose-400',
      icon: 'text-rose-500'
    };
  };

  const getStrategyTooltip = (rate: number, avgReturn: number, count: number, strategyName: string) => {
    const isVCP = strategyName.includes("VCP");
    const criteriaText = isVCP
      ? "돌파 매매 진입 후 익절(+9%) 성공 비율"
      : "종가 매수 후 보유 시 익절(+9%) 성공 비율";

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-1">
          <span className="font-bold text-white text-sm">{strategyName} 성과 분석</span>
          <span className="text-[10px] text-gray-500">최근 30일 기준</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[10px] text-gray-400 mb-0.5">승률 (Win Rate)</div>
            <div className={`text-base font-black ${rate >= 50 ? 'text-rose-400' : 'text-blue-400'}`}>
              {rate}%
            </div>
          </div>
          <div>
            <div className="text-[10px] text-gray-400 mb-0.5">평균 수익률 (Avg)</div>
            <div className={`text-base font-black ${avgReturn > 0 ? 'text-rose-400' : 'text-blue-400'}`}>
              {avgReturn > 0 ? '+' : ''}{avgReturn}%
            </div>
          </div>
        </div>

        <div className="space-y-2 text-[11px] text-gray-300">
          <div className="flex gap-2">
            <span className="text-gray-500 min-w-[30px]">기준:</span>
            <span>익절 +9%, 손절 -5% 기준 백테스팅 결과입니다.</span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-500 min-w-[30px]">해석:</span>
            <span>
              {rate >= 60 ? "현재 시장 주도주 매매에 매우 유리한 구간입니다." :
                rate >= 40 ? "선별적인 접근으로 수익을 낼 수 있는 구간입니다." :
                  "시장 변동성이 크거나 추세가 약해 보수적 대응이 필요합니다."}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-500 min-w-[30px]">표본:</span>
            <span>총 {count}번의 매매 신호를 분석한 결과입니다.</span>
          </div>
        </div>
      </div>
    );
  };

  const getSignalCountTheme = (count: number) => {
    if (count >= 5) return {
      label: '강세',
      border: 'hover:border-emerald-500/30',
      glow: 'bg-emerald-500/10',
      text: 'group-hover:text-emerald-400',
      icon: 'text-emerald-500',
      badge: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
    };
    if (count >= 1) return {
      label: '관망',
      border: 'hover:border-amber-500/30',
      glow: 'bg-amber-500/10',
      text: 'group-hover:text-amber-400',
      icon: 'text-amber-500',
      badge: 'bg-amber-500/10 text-amber-500 border-amber-500/20'
    };
    return {
      label: '매도',
      border: 'hover:border-rose-500/30',
      glow: 'bg-rose-500/10',
      text: 'group-hover:text-rose-400',
      icon: 'text-rose-500',
      badge: 'bg-rose-500/10 text-rose-500 border-rose-500/20'
    };
  };

  const parseNumericValue = (raw: unknown): number | undefined => {
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
    if (typeof raw === 'string') {
      const normalized = raw.replace(/[,₩$%]/g, '').trim();
      if (!normalized) return undefined;
      const parsed = Number(normalized);
      return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
  };

  const normalizeCommodity = (raw: unknown): { value: number; change_pct: number } | undefined => {
    if (raw === null || raw === undefined) return undefined;

    const directNumber = parseNumericValue(raw);
    if (directNumber !== undefined) {
      return { value: directNumber, change_pct: 0 };
    }

    if (typeof raw === 'object' && raw !== null) {
      const item = raw as Record<string, unknown>;
      const valueRaw = item.value ?? item.price ?? item.close ?? item.current ?? item.last;
      const valueNum = parseNumericValue(valueRaw);
      if (valueNum === undefined) return undefined;

      const changeRaw = item.change_pct ?? item.changePct ?? item.change ?? 0;
      const changeNum = parseNumericValue(changeRaw);
      return {
        value: valueNum,
        change_pct: changeNum ?? 0,
      };
    }

    return undefined;
  };

  const resolveCommodity = (keys: string[]): { value: number; change_pct: number } | undefined => {
    const gateDataRecord: Record<string, unknown> =
      gateData && typeof gateData === 'object'
        ? (gateData as unknown as Record<string, unknown>)
        : {};
    const rawCommodities = gateDataRecord.commodities;
    const commodities: Record<string, unknown> =
      rawCommodities && typeof rawCommodities === 'object'
        ? (rawCommodities as Record<string, unknown>)
        : {};

    for (const key of keys) {
      const normalized = normalizeCommodity(commodities[key] ?? gateDataRecord[key]);
      if (normalized) return normalized;
    }

    return undefined;
  };

  const krxGold = resolveCommodity(['krx_gold', 'krxGold', 'KRX_GOLD']);
  const krxSilver = resolveCommodity(['krx_silver', 'krxSilver', 'KRX_SILVER']);

  return (
    <div className="space-y-8">
      {autoRetryExhausted && (
        <div role="alert" aria-live="assertive" className="flex items-center justify-between gap-4 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          <span>
            자동 갱신이 50초 동안 실패했습니다. 새로고침을 시도하거나 잠시 후 다시 확인해주세요.
          </span>
          <button
            onClick={() => {
              resetAutoRetry();
              loadData();
            }}
            className="shrink-0 rounded-lg border border-rose-500/40 bg-rose-500/20 px-3 py-1.5 text-xs font-bold text-rose-300 transition-colors hover:bg-rose-500/30"
          >
            다시 시도
          </button>
        </div>
      )}
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
              onClick={() => { resetAutoRetry(); setUseTodayMode(true); setTargetDate(''); }} // 실시간 복귀 시 날짜 초기화
              className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${useTodayMode
                ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
            >
              <i className="fas fa-clock mr-1.5"></i>
              실시간
            </button>
            <button
              onClick={() => { resetAutoRetry(); setUseTodayMode(false); if (!targetDate) setTargetDate(getLastBusinessDay()); }}
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
        <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 relative group">
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
              <Tooltip content={
                (gateData?.score && gateData.score >= 70) ? '상승장 (매수 우위)' :
                  (gateData?.score && gateData.score >= 40) ? '중립/혼조세 (방향성 탐색)' :
                    '하락장 (매도 우위)'
              } position="bottom">
                {loading ? 'Analyzing...' : (
                  (gateData?.score && gateData.score >= 70) ? 'Bullish' :
                    (gateData?.score && gateData.score >= 40) ? 'Neutral' :
                      'Bearish'
                )}
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
        {(() => {
          const signalCount = signalsData?.signals?.length ?? 0;
          const signalTheme = getSignalCountTheme(signalCount);
          return (
            <div className={`p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative group transition-all ${signalTheme.border}`}>
              <div className={`absolute top-0 right-0 w-20 h-20 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2 ${signalTheme.glow}`}></div>
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 mb-1">
                  <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">오늘의 시그널</div>
                  <Tooltip content="오늘 포착된 VCP 패턴 + 수급 유입 종목 수입니다." position="bottom" align="left">
                    <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
                  </Tooltip>
                </div>
              </div>
              <div className={`text-3xl font-black text-white transition-colors ${signalTheme.text}`}>
                {loading ? '--' : signalCount}
              </div>
              <div className="mt-2 text-xs text-gray-500">VCP + 외국인 순매수</div>
            </div>
          );
        })()}

        {/* 2. VCP Strategy Performance */}
        {(() => {
          const vcpRate = backtestData?.vcp?.win_rate ?? 0;
          const avgReturn = backtestData?.vcp?.avg_return ?? 0;
          const vcpTheme = getStrategyTheme(vcpRate);
          return (
            <div className={`p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative group transition-all ${vcpTheme.border}`}>
              <div className={`absolute top-0 right-0 w-20 h-20 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2 ${vcpTheme.glow}`}></div>
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 mb-1">
                  <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">VCP 전략</div>
                  <Tooltip content={getStrategyTooltip(vcpRate, avgReturn, backtestData?.vcp?.count ?? 0, "VCP 전략")} position="bottom" align="left">
                    <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
                  </Tooltip>
                  <button
                    onClick={() => setIsStrategyGuideOpen(true)}
                    className="ml-1 text-[8px] px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 text-gray-400 border border-white/10 transition-colors"
                  >
                    기준표
                  </button>
                </div>
                {(() => {
                  const status = getStrategyStatus(vcpRate);
                  return (
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${status.className}`}>
                      {status.label}
                    </span>
                  );
                })()}
              </div>
              <div className="flex items-baseline gap-2">
                <span className={`text-3xl font-black text-white transition-colors ${vcpTheme.text}`}>
                  {loading ? '--' : vcpRate}<span className="text-base text-gray-600">%</span>
                </span>
                <span className={`text-xs font-bold ${avgReturn > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                  Avg. {avgReturn > 0 ? '+' : ''}{avgReturn}%
                </span>
              </div>
              <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
                <span>{renderTradeCount(backtestData?.vcp?.count ?? 0)}</span>
                {backtestData?.vcp?.status === 'OK' && <i className={`fas fa-check-circle ${vcpTheme.icon}`}></i>}
              </div>
            </div>
          );
        })()}

        {/* 3. Closing Bet Performance */}
        {(() => {
          const cbRate = backtestData?.closing_bet?.win_rate ?? 0;
          const avgReturn = backtestData?.closing_bet?.avg_return ?? 0;
          const cbTheme = getStrategyTheme(cbRate);
          return (
            <div className={`p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative group transition-all ${cbTheme.border}`}>
              <div className={`absolute top-0 right-0 w-20 h-20 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2 ${cbTheme.glow}`}></div>
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 mb-1">
                  <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">종가베팅 전략</div>
                  <Tooltip content={getStrategyTooltip(cbRate, avgReturn, backtestData?.closing_bet?.count ?? 0, "종가베팅 전략")} position="bottom" align="left">
                    <i className="fas fa-question-circle text-gray-600 hover:text-gray-300 transition-colors cursor-help text-[10px]"></i>
                  </Tooltip>
                  <button
                    onClick={() => setIsStrategyGuideOpen(true)}
                    className="ml-1 text-[8px] px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/10 text-gray-400 border border-white/10 transition-colors"
                  >
                    기준표
                  </button>
                </div>
                {backtestData?.closing_bet?.status === 'Accumulating' ? (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 text-[10px] font-bold border border-amber-500/20 animate-pulse">
                    <i className="fas fa-hourglass-half mr-1"></i>축적 중
                  </span>
                ) : (
                  (() => {
                    const status = getStrategyStatus(cbRate);
                    return (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${status.className}`}>
                        {status.label}
                      </span>
                    );
                  })()
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
                    <span className={`text-3xl font-black text-white transition-colors ${cbTheme.text}`}>
                      {loading ? '--' : cbRate}<span className="text-base text-gray-600">%</span>
                    </span>
                    <span className={`text-xs font-bold ${(backtestData?.closing_bet?.avg_return ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
                      Avg. {(backtestData?.closing_bet?.avg_return ?? 0) > 0 ? '+' : ''}{backtestData?.closing_bet?.avg_return}%
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-gray-500 flex items-center justify-between">
                    <span>{renderTradeCount(backtestData?.closing_bet?.count ?? 0)}</span>
                    {backtestData?.closing_bet?.status === 'OK' && <i className={`fas fa-check-circle ${cbTheme.icon}`}></i>}
                  </div>
                </>
              )}
            </div>
          );
        })()}

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
                  {loading ? '--' : formatFinancialValue(krxGold?.value)}
                </span>
                {krxGold && (
                  <span className={`text-xs font-bold mb-0.5 ${(krxGold.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(krxGold.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(krxGold.change_pct ?? 0) >= 0 ? '+' : ''}{krxGold.change_pct?.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
            {/* KRX SILVER */}
            <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
              <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KRX SILVER</div>
              <div className="flex items-end gap-2">
                <span className="text-xl font-black text-white">
                  {loading ? '--' : formatFinancialValue(krxSilver?.value)}
                </span>
                {krxSilver && (
                  <span className={`text-xs font-bold mb-0.5 ${(krxSilver.change_pct ?? 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                    <i className={`fas fa-caret-${(krxSilver.change_pct ?? 0) >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                    {(krxSilver.change_pct ?? 0) >= 0 ? '+' : ''}{krxSilver.change_pct?.toFixed(1)}%
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
                    {(gateData.crypto.btc.change_pct ?? 0) >= 0 ? '+' : ''}{(gateData.crypto.btc.change_pct ?? 0).toFixed(1)}%
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
                    {(gateData.crypto.eth.change_pct ?? 0) >= 0 ? '+' : ''}{(gateData.crypto.eth.change_pct ?? 0).toFixed(1)}%
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
                    {(gateData.crypto.xrp.change_pct ?? 0) >= 0 ? '+' : ''}{(gateData.crypto.xrp.change_pct ?? 0).toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <StrategyGuideModal
        isOpen={isStrategyGuideOpen}
        onClose={() => setIsStrategyGuideOpen(false)}
      />
    </div>
  );
}
