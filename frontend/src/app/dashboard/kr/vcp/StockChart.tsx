'use client';

import { createChart, ColorType, IChartApi, Time, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';

import { calculateSMA } from './chartUtils';

interface ChartProps {
  data: {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }[];
  ticker: string;
  name: string;
  vcpRange?: {
    enabled: boolean;
    firstHalf: number;  // 전반부 범위 (고점)
    secondHalf: number; // 후반부 범위 (저점)
  };
}

const MA_PERIODS = [3, 5, 10, 20, 60, 120];
const MA_COLORS: Record<number, string> = {
  3: '#f472b6',  // 3일선: 분홍
  5: '#22d3ee',  // 5일선: 하늘
  10: '#a78bfa', // 10일선: 보라
  20: '#fbbf24', // 20일선: 노랑 (생명선)
  60: '#4ade80', // 60일선: 초록 (수급선)
  120: '#f87171' // 120일선: 빨강 (경기선)
};

export default function StockChart({ data, ticker, name, vcpRange }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const smaSeriesRefs = useRef<Record<number, any>>({});

  const [visibleSMAs, setVisibleSMAs] = useState<number[]>([20]); // 기본 20일선 활성화

  // 1. 차트 초기화 및 시리즈 생성
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1c1c1e' },
        textColor: '#d1d5db',
      },
      grid: {
        vertLines: { color: '#333' },
        horzLines: { color: '#333' },
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Candlestick Series
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#3b82f6',
      borderVisible: false,
      wickUpColor: '#ef4444',
      wickDownColor: '#3b82f6',
    });

    const candleData = data.map((d: any) => ({
      time: d.date as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candlestickSeries.setData(candleData);

    // VCP 범위
    if (vcpRange?.enabled && vcpRange.firstHalf > 0 && vcpRange.secondHalf > 0) {
      candlestickSeries.createPriceLine({
        price: vcpRange.firstHalf,
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: '전반부',
      });
      candlestickSeries.createPriceLine({
        price: vcpRange.secondHalf,
        color: '#3b82f6',
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: '후반부',
      });
    }

    // Volume Series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume_scale',
    });
    chart.priceScale('volume_scale').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const volumeData = data.map((d: any) => ({
      time: d.date as Time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(239, 68, 68, 0.5)' : 'rgba(59, 130, 246, 0.5)',
    }));
    volumeSeries.setData(volumeData);

    // 이동평균선(SMA) 한 번에 모두 계산 후 생성
    MA_PERIODS.forEach(period => {
      const smaData = calculateSMA(data, period);
      const smaSeries = chart.addSeries(LineSeries, {
        color: MA_COLORS[period],
        lineWidth: period === 20 ? 2 : 1, // Lightweight charts only accept integers
        crosshairMarkerVisible: false,
        visible: visibleSMAs.includes(period), // 초기 상태 적용
      });
      smaSeries.setData(smaData);
      smaSeriesRefs.current[period] = smaSeries;
    });

    chart.timeScale().fitContent();
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(entries => {
      if (entries.length === 0 || !entries[0].contentRect) return;
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, vcpRange]); // visibleSMAs 제외하여 차트가 불필요하게 통째로 재생성되는 것 방지

  // 2. 이동평균선 표시/숨김 토글 (차트 객체 자체의 visible 옵션만 변경)
  useEffect(() => {
    MA_PERIODS.forEach(period => {
      const series = smaSeriesRefs.current[period];
      if (series) {
        series.applyOptions({
          visible: visibleSMAs.includes(period)
        });
      }
    });
  }, [visibleSMAs]);

  const toggleSMA = (period: number) => {
    setVisibleSMAs(prev =>
      prev.includes(period) ? prev.filter(p => p !== period) : [...prev, period]
    );
  };

  return (
    <div className="w-full h-full relative group">
      <div ref={chartContainerRef} className="w-full h-full pb-8" />

      {/* VCP Range Tooltip (상단) */}
      <div className="absolute top-2 left-2 z-10 flex gap-2">
        {vcpRange?.enabled && (
          <div className="relative group/tooltip">
            <span className="text-[10px] text-rose-400 font-bold bg-black/60 px-2 py-1 rounded border border-rose-400/30 cursor-help flex items-center gap-1">
              VCP 표시 <i className="fas fa-info-circle"></i>
            </span>
            <div className="absolute top-full left-0 mt-2 w-64 bg-[#2c2c2e] text-xs text-gray-200 p-3 rounded shadow-xl border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-50 pointer-events-none">
              <div className="font-bold text-rose-400 mb-1">VCP Range (변동성 수축)</div>
              고점(전반부)과 저점(후반부) 사이의 주가 변동 폭이 갈수록 줄어들며, 에너지가 응집되는 돌파 직전의 핵심 구간을 점선으로 나타냅니다.
            </div>
          </div>
        )}
      </div>

      {/* SMA Toggles Tooltip (하단) */}
      <div className="absolute bottom-1 left-0 right-0 z-10 flex justify-center mt-2 px-2 overflow-x-auto custom-scrollbar pb-1">
        <div className="flex bg-black/80 rounded border border-white/10 p-1 gap-1 items-center backdrop-blur-sm shadow-lg">
          <div className="relative group/tooltip">
            <span className="text-[10px] text-gray-400 font-bold px-2 py-1 cursor-help flex items-center gap-1">
              이동평균선 토글 <i className="fas fa-info-circle"></i>
            </span>
            <div className="absolute bottom-full left-0 mb-2 w-64 bg-[#2c2c2e] text-xs text-gray-200 p-3 rounded shadow-xl border border-white/10 opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all z-50 pointer-events-none">
              <div className="font-bold mb-1">이동평균선 (Moving Average)</div>
              특정 기간 동안의 평균 주가를 연결한 선입니다. 추세와 지지/저항을 파악할 때 유용합니다.<br /><br />
              • 3, 5일선: 단기 급등선<br />
              • 10, 20일선: 생명선/단기 추세선<br />
              • 60일선: 수급선/중기 추세선<br />
              • 120일선: 경기선/장기 추세선<br /><br />
              *초기 구간은 보유 데이터 범위 기준 평균으로 표시됩니다.
            </div>
          </div>

          <div className="w-[1px] h-3 bg-white/20 mx-1"></div>

          {MA_PERIODS.map(period => {
            const isActive = visibleSMAs.includes(period);
            return (
              <button
                key={period}
                onClick={() => toggleSMA(period)}
                className={`text-[10px] sm:text-xs px-2 py-0.5 rounded font-bold transition-all ${isActive
                  ? 'bg-white/10 shadow-sm'
                  : 'bg-transparent text-gray-500 hover:bg-white/5 opacity-60'
                  }`}
                style={{ color: isActive ? MA_COLORS[period] : undefined }}
              >
                {period}일선
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
