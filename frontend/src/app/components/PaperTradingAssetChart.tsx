'use client';

import { useEffect, useRef, useState } from 'react';
import { paperTradingAPI, PaperTradingAssetHistory } from '@/lib/api';
// Dynamic import usage below
import type { IChartApi, Time } from 'lightweight-charts';
import { formatSmartPercent } from './paperTradingFormat';

const TIME_RANGE_DAYS: Record<'1M' | '3M' | '6M' | '1Y' | 'ALL', number> = {
  '1M': 30,
  '3M': 90,
  '6M': 180,
  '1Y': 365,
  ALL: 3650,
};

const buildFallbackAssetHistory = (
  totalAsset: number,
  cash: number,
  stockValue: number,
): PaperTradingAssetHistory[] => {
  const safeTotal = Number.isFinite(totalAsset) && totalAsset > 0 ? totalAsset : 100000000;
  const safeCash = Number.isFinite(cash) && cash >= 0 ? cash : safeTotal;
  const safeStock = Number.isFinite(stockValue) && stockValue >= 0 ? stockValue : Math.max(0, safeTotal - safeCash);
  const now = new Date();
  return Array.from({ length: 5 }, (_, idx) => {
    const dayOffset = 4 - idx;
    const dt = new Date(now);
    dt.setDate(now.getDate() - dayOffset);
    return {
      date: dt.toISOString().split('T')[0],
      total_asset: safeTotal,
      cash: safeCash,
      stock_value: safeStock,
    };
  });
};

const normalizeAssetHistory = (rawHistory: unknown): PaperTradingAssetHistory[] => {
  if (!Array.isArray(rawHistory)) return [];

  const normalizedRows = rawHistory
    .map((entry) => {
      const row = (entry ?? {}) as Record<string, unknown>;
      const rawDate = String(row.date ?? '').trim();
      const parsedDate = rawDate ? new Date(rawDate) : null;
      const date = parsedDate && !Number.isNaN(parsedDate.getTime())
        ? parsedDate.toISOString().split('T')[0]
        : '';
      const totalAsset = Number(row.total_asset);
      const cash = Number(row.cash);
      const stockValue = Number(row.stock_value);
      return {
        date,
        total_asset: Number.isFinite(totalAsset) ? totalAsset : NaN,
        cash: Number.isFinite(cash) ? cash : NaN,
        stock_value: Number.isFinite(stockValue) ? stockValue : NaN,
      };
    })
    .filter((row) => row.date && Number.isFinite(row.total_asset))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  const dedupedByDate = new Map<string, PaperTradingAssetHistory>();
  normalizedRows.forEach((row) => {
    dedupedByDate.set(row.date, row);
  });
  return Array.from(dedupedByDate.values());
};

interface PaperTradingAssetChartProps {
  /** 매수·매도·입금·초기화 뒤에 값이 오르면 자산 히스토리를 다시 받는다. */
  refreshKey: number;
  /** 히스토리를 받지 못했을 때 그릴 대체 자료의 기준값이다. */
  fallbackTotalAsset: number;
  fallbackCash: number;
  /** 수익률 축의 기준이 되는 원금이다. */
  principalBase: number;
}

/**
 * 모의투자 모달의 「수익 차트」 탭이다. 종전에는 이 300여 줄이 모달 본체에
 * 섞여 있어서 차트 초기화 하나를 고치려 해도 파일 전체를 훑어야 했다.
 *
 * 탭에 들어갔을 때만 마운트되므로 자산 히스토리 조회도 그때 시작한다.
 * 종전에는 모달을 열기만 해도 조회가 일어났고, 기간을 바꾸면 포트폴리오까지
 * 함께 다시 받았다.
 */
export default function PaperTradingAssetChart({
  refreshKey,
  fallbackTotalAsset,
  fallbackCash,
  principalBase,
}: PaperTradingAssetChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [chartData, setChartData] = useState<PaperTradingAssetHistory[]>([]);
  // 마운트 직후의 첫 렌더에서 「자산 데이터 수집 중」 안내가 스치지 않도록 참으로 연다.
  // 조회는 effect 안에서 시작하므로 그 사이의 한 프레임이 비어 있다.
  const [chartLoading, setChartLoading] = useState(true);
  const [chartError, setChartError] = useState<string | null>(null);
  const [maToggle, setMaToggle] = useState<{ [key: number]: boolean }>({ 10: true });
  const [timeRange, setTimeRange] = useState<'1M' | '3M' | '6M' | '1Y' | 'ALL'>('1Y');

  // 폴백 값은 조회가 실패했거나 결과가 비었을 때만 읽는다. 의존성 배열에 두면
  // 포트폴리오가 갱신될 때마다 히스토리를 다시 받게 되므로 ref 로 최신값만 건넨다.
  const fallbackRef = useRef({ fallbackTotalAsset, fallbackCash });
  fallbackRef.current = { fallbackTotalAsset, fallbackCash };

  useEffect(() => {
    let isCancelled = false;

    const fallbackRows = () => {
      const { fallbackTotalAsset: total, fallbackCash: cash } = fallbackRef.current;
      return buildFallbackAssetHistory(total, cash, total - cash);
    };

    const fetchChartHistory = async (days: number) => {
      setChartLoading(true);
      setChartError(null);
      try {
        const res = await paperTradingAPI.getAssetHistory(days);
        if (isCancelled) return;
        const normalized = normalizeAssetHistory((res as { history?: unknown })?.history);
        if (normalized.length > 0) {
          setChartData(normalized);
        } else {
          setChartData(fallbackRows());
        }
      } catch (e) {
        if (isCancelled) return;
        console.error("Failed to fetch asset history", e);
        setChartError('차트 데이터를 불러오지 못해 로컬 기준 데이터로 표시합니다.');
        setChartData(fallbackRows());
      } finally {
        if (!isCancelled) {
          setChartLoading(false);
        }
      }
    };

    fetchChartHistory(TIME_RANGE_DAYS[timeRange]);

    return () => {
      isCancelled = true;
    };
  }, [refreshKey, timeRange]);

  // 차트 렌더링 (Dynamic Import 적용 + 데이터 포맷팅 강화)
  useEffect(() => {
    let chartInstance: any = null;
    let resizeObserver: ResizeObserver | null = null;

    const initChart = async () => {
      // 컴포넌트 마운트 및 데이터 유효성 확인
      if (chartContainerRef.current) {

        try {
          // Dynamic Import: 클라이언트 사이드에서만 라이브러리 로드
          const { createChart, ColorType, LineStyle } = await import('lightweight-charts');

          // 기존 차트 제거 (cleanup)
          if (chartRef.current) {
            try {
              chartRef.current.remove();
            } catch (e) { /* ignore cleanup error */ }
            chartRef.current = null;
          }

          // 차트 생성
          const chart = createChart(chartContainerRef.current, {
            layout: {
              background: { type: ColorType.Solid, color: '#1c1c1e' },
              textColor: '#d1d5db',
            },
            grid: {
              vertLines: { color: '#333' },
              horzLines: { color: '#333' },
            },
            width: chartContainerRef.current.clientWidth > 0 ? chartContainerRef.current.clientWidth : 600, // 기본값 설정
            height: 220,
            timeScale: {
              timeVisible: true,
              borderColor: '#444',
              tickMarkFormatter: (time: string | number | { year: number, month: number, day: number }) => {
                let date: Date;
                if (typeof time === 'number') {
                  date = new Date(time * 1000);
                } else if (typeof time === 'string') {
                  date = new Date(time);
                } else if (typeof time === 'object' && 'year' in time) {
                  date = new Date(time.year, time.month - 1, time.day);
                } else {
                  return '';
                }
                if (isNaN(date.getTime())) return '';
                return `${date.getMonth() + 1}/${date.getDate()}`;
              },
            },
            rightPriceScale: {
              borderColor: '#444',
            }
          });

          // Add Unit Label Overlay
          const unitLabel = document.createElement('div');
          unitLabel.className = 'absolute top-2 right-2 text-xs text-gray-500 z-10 pointer-events-none';
          unitLabel.innerText = '(단위: 원)';
          chartContainerRef.current.style.position = 'relative';
          chartContainerRef.current.appendChild(unitLabel);



          chartInstance = chart;
          chartRef.current = chart;

          // ResizeObserver 설정
          resizeObserver = new ResizeObserver(entries => {
            if (entries.length === 0 || !entries[0].contentRect) return;
            const { width } = entries[0].contentRect;
            if (chartInstance && width > 0) {
              chartInstance.applyOptions({ width });
            }
          });
          resizeObserver.observe(chartContainerRef.current);

          // 메인 자산 라인 -> Area Chart
          // 메인 자산 라인 -> Area Chart (v5 호환)

          const { AreaSeries, LineSeries } = await import('lightweight-charts');

          const mainSeries = chart.addSeries(AreaSeries, {
            lineColor: '#fb7185', // rose-400
            topColor: 'rgba(251, 113, 133, 0.4)',
            bottomColor: 'rgba(251, 113, 133, 0.0)',
            lineWidth: 2,
          });

          // 데이터 포맷팅 (lightweight-charts v5 입력 제한 대응)
          const rawFormattedData = chartData
            .map(d => {
              const dateStr = typeof d.date === 'string' ? d.date.split('T')[0] : d.date;
              const value = Number(d.total_asset);
              return {
                time: dateStr,
                value
              };
            })
            .filter(d => typeof d.time === 'string' && d.time.length > 0 && Number.isFinite(d.value))
            .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

          if (rawFormattedData.length === 0) {
            // 데이터가 아예 없으면 3일 전부터 오늘까지의 가상 데이터 생성 (사용자 요청)
            const today = new Date();
            const threeDaysAgo = new Date(today);
            threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);

            rawFormattedData.push({ time: threeDaysAgo.toISOString().split('T')[0], value: 100000000 });
            rawFormattedData.push({ time: today.toISOString().split('T')[0], value: 100000000 });
          } else if (rawFormattedData.length === 1) {
            // 데이터가 1개뿐이면 3일 전 데이터를 시작점으로 추가
            const firstDate = new Date(rawFormattedData[0].time);
            const prevDate = new Date(firstDate);
            prevDate.setDate(prevDate.getDate() - 3);
            rawFormattedData.unshift({
              time: prevDate.toISOString().split('T')[0],
              value: 100000000 // 기본 초기 자산
            });
          }

          // lightweight-charts v5는 약 ±9e13 범위를 넘는 값을 허용하지 않으므로 동적 축소
          const MAX_CHART_ABS_VALUE = 90_000_000_000_000;
          const maxAbsValue = rawFormattedData.reduce((max, item) => Math.max(max, Math.abs(item.value)), 0);
          const scaleDivisor = maxAbsValue > MAX_CHART_ABS_VALUE
            ? Math.ceil(maxAbsValue / MAX_CHART_ABS_VALUE)
            : 1;

          const formattedData = rawFormattedData.map((item) => ({
            time: item.time,
            value: item.value / scaleDivisor,
          }));

          mainSeries.setData(formattedData);

          // 기간 필터(1M/3M/6M/1Y/ALL)에 맞춰 X축 표시 범위를 강제로 설정한다.
          // 데이터가 적어도 사용자가 선택한 기간만큼 X축이 펼쳐지도록 한다.
          try {
            const rangeDays = TIME_RANGE_DAYS[timeRange] ?? 365;
            const lastDateStr = formattedData[formattedData.length - 1]?.time as string | undefined;
            const endDate = lastDateStr ? new Date(lastDateStr) : new Date();
            if (!Number.isNaN(endDate.getTime())) {
              const startDate = new Date(endDate);
              startDate.setDate(startDate.getDate() - rangeDays);
              const fmt = (d: Date) => d.toISOString().split('T')[0];
              chart.timeScale().setVisibleRange({
                from: fmt(startDate) as Time,
                to: fmt(endDate) as Time,
              });
            }
          } catch (rangeErr) {
            // visible range 설정 실패는 차트 자체 동작에는 영향 없으므로 silent fallback
            console.debug('Failed to set chart visible range', rangeErr);
          }

          // 이평선 추가
          const maColors: Record<number, string> = {
            3: '#4ade80', 5: '#f87171', 10: '#60a5fa', 20: '#facc15',
            40: '#a78bfa', 60: '#fb923c', 100: '#e879f9', 120: '#94a3b8'
          };

          Object.entries(maToggle).forEach(([periodStr, isVisible]) => {
            const period = parseInt(periodStr);
            if (!isVisible) return;

            const maData = [];
            for (let i = 0; i < rawFormattedData.length; i++) {
              if (i < period - 1) continue;
              let sum = 0;
              for (let j = 0; j < period; j++) {
                sum += Number(rawFormattedData[i - j].value) || 0;
              }
              maData.push({
                time: rawFormattedData[i].time,
                value: (sum / period) / scaleDivisor
              });
            }
            maData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

            if (maData.length > 0) {
              const maSeries = chart.addSeries(LineSeries, {
                color: maColors[period] || '#fff',
                lineWidth: 1,
                lineStyle: LineStyle.Solid,
                title: `${period}일선`
              });
              maSeries.setData(maData);
            }
          });

          // Y-Axis Formatting (Korean currency units or commas)
          chart.applyOptions({
            localization: {
              priceFormatter: (p: number) => Math.round(p * scaleDivisor).toLocaleString(),
            },
          });

          // Floating Tooltip Logic
          // 툴팁 엘리먼트 생성 (DOM 조작 대신 React state로 관리하면 좋지만, Crosshair 성능상 ref로 직접 조작)
          const toolTipWidth = 200;
          const toolTipHeight = 100;

          const toolTip = document.createElement('div');
          toolTip.className = 'absolute bg-[#2a2a2e] border border-white/10 rounded-lg p-3 shadow-xl text-sm z-50 pointer-events-none hidden';
          toolTip.style.width = '220px';
          // 차트 컨테이너에 추가 (relative여야 함)
          chartContainerRef.current.style.position = 'relative';
          chartContainerRef.current.appendChild(toolTip);

          const updateTooltip = (param: any) => {
            if (
              param.point === undefined ||
              !param.time ||
              param.point.x < 0 ||
              param.point.x > chartContainerRef.current!.clientWidth ||
              param.point.y < 0 ||
              param.point.y > chartContainerRef.current!.clientHeight
            ) {
              toolTip.style.display = 'none';
              return;
            }

            // 메인 시리즈 데이터 가져오기
            const data = param.seriesData.get(mainSeries);
            if (!data) {
              toolTip.style.display = 'none';
              return;
            }

            toolTip.style.display = 'block';

            const totalAsset = Number(data.value) * scaleDivisor;
            const profit = totalAsset - principalBase;
            const profitRate = principalBase > 0 ? (profit / principalBase) * 100 : 0;
            const isPlus = profit >= 0;
            const colorClass = isPlus ? 'text-rose-400' : 'text-blue-400';
            const sign = isPlus ? '+' : '';

            const dateStr = param.time as string; // String type because we setup time as string

            toolTip.innerHTML = `
              <div class="font-bold text-gray-300 mb-2 border-b border-white/10 pb-1">${dateStr}</div>
              <div class="flex justify-between items-center mb-1">
                <span class="text-gray-500 text-xs">총 자산</span>
                <span class="font-bold text-white">${Math.floor(totalAsset).toLocaleString()}원</span>
              </div>
              <div class="flex justify-between items-center mb-1">
                <span class="text-gray-500 text-xs">평가 손익</span>
                <span class="font-bold ${colorClass}">${sign}${Math.floor(profit).toLocaleString()}원</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-500 text-xs">수익률</span>
                <span class="font-bold ${colorClass}">${sign}${formatSmartPercent(profitRate, 2)}%</span>
              </div>
            `;

            // 위치 조정
            const coordinate = mainSeries.priceToCoordinate(totalAsset);
            let shiftedX = param.point.x + 15;
            let shiftedY = param.point.y + 15;

            // 화면 밖으로 나가지 않게 조정
            if (shiftedX + toolTipWidth > chartContainerRef.current!.clientWidth) {
              shiftedX = param.point.x - toolTipWidth - 15;
            }
            if (shiftedY + toolTipHeight > chartContainerRef.current!.clientHeight) {
              shiftedY = param.point.y - toolTipHeight - 15;
            }

            toolTip.style.left = shiftedX + 'px';
            toolTip.style.top = shiftedY + 'px';
          };

          chart.subscribeCrosshairMove(updateTooltip);

          // 데이터가 있으면 마지막 데이터로 초기 툴팁 표시 또는 고정 표시 (선택)
          // 여기서는 hover 시에만 나오도록 함

        } catch (err) {
          console.error("Failed to load/render chart:", err);
          setChartError('차트 렌더링 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
        }
      }
    };

    // requestAnimationFrame으로 실행 시점 보장
    requestAnimationFrame(() => initChart());

    return () => {
      if (resizeObserver) resizeObserver.disconnect();
      if (chartInstance) {
        try {
          chartInstance.remove();
        } catch (e) { /* ignore */ }
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = '';
        }
        chartInstance = null;
        chartRef.current = null;
      }
    };
  }, [chartData, maToggle, principalBase, timeRange]);

  return (
    <div className="h-full flex flex-col space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
      {/* Controls */}
      <div className="bg-[#252529] p-3 rounded-xl border border-white/5 flex flex-col md:flex-row flex-wrap gap-2 items-start md:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 font-bold px-2">기간</span>
          {(['1M', '3M', '6M', '1Y', 'ALL'] as const).map(range => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-2 py-1 text-xs rounded transition-colors ${timeRange === range
                ? 'bg-rose-500 text-white font-bold'
                : 'bg-black/20 text-gray-400 hover:bg-black/40 hover:text-white'
                }`}
            >
              {range === '1M' && '1개월'}
              {range === '3M' && '3개월'}
              {range === '6M' && '6개월'}
              {range === '1Y' && '1년'}
              {range === 'ALL' && '전체'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap max-w-full">
          <span className="text-xs text-gray-500 font-bold px-2 whitespace-nowrap">이동평균선</span>
          {[3, 5, 10, 20, 60, 120].map(d => {
            const isAvailable = chartData.length >= d;
            return (
              <label
                key={d}
                className={`flex items-center gap-1.5 px-2 py-1 bg-black/20 rounded transition-colors flex-shrink-0 ${isAvailable ? 'cursor-pointer hover:bg-black/40' : 'opacity-50 cursor-not-allowed'
                  }`}
              >
                <input
                  type="checkbox"
                  checked={!!maToggle[d]}
                  onChange={e => {
                    if (isAvailable) {
                      setMaToggle(p => ({ ...p, [d]: e.target.checked }));
                    }
                  }}
                  disabled={!isAvailable}
                  className="rounded border-gray-600 bg-gray-700 text-rose-500 focus:ring-offset-0 focus:ring-0 w-3 h-3 disabled:opacity-50"
                />
                <span className="text-xs text-gray-300 whitespace-nowrap">{d}일</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* Chart Container */}
      <div className="bg-[#252529] rounded-xl border border-white/5 p-4 relative" style={{ minHeight: '250px' }}>
        <div ref={chartContainerRef} className="w-full" style={{ height: '220px' }} />
        {chartLoading && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400 bg-black/50 z-10 backdrop-blur-sm rounded-xl">
            <div className="text-center">
              <i className="fas fa-spinner fa-spin text-lg mb-2"></i>
              <p className="text-sm font-bold">수익 차트 로딩 중</p>
            </div>
          </div>
        )}
        {!chartLoading && chartError && (
          <div className="absolute top-3 left-3 right-3 z-20 text-xs md:text-sm text-amber-300 bg-amber-900/30 border border-amber-500/30 rounded-lg px-3 py-2">
            {chartError}
          </div>
        )}
        {!chartLoading && !chartError && chartData.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-500 bg-black/50 z-10 backdrop-blur-sm rounded-xl">
            <div className="text-center">
              <p className="mb-2 font-bold text-gray-400">자산 데이터 수집 중</p>
              <p className="text-xs opacity-70">첫 거래 후 데이터가 기록되기까지 잠시 기다려주세요</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
