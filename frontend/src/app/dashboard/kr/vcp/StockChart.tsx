'use client';

import { createChart, ColorType, IChartApi, Time, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { useEffect, useRef } from 'react';

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

export default function StockChart({ data, ticker, name, vcpRange }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

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

    // Candlestick Series (v5 API)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',    // Red for up
      downColor: '#3b82f6',  // Blue for down
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

    // VCP 범위 표시 (Price Lines)
    if (vcpRange?.enabled && vcpRange.firstHalf > 0 && vcpRange.secondHalf > 0) {
      // 전반부 범위 (상단 라인 - 빨간색 점선)
      candlestickSeries.createPriceLine({
        price: vcpRange.firstHalf,
        color: '#ef4444',
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: '전반부',
      });

      // 후반부 범위 (하단 라인 - 파란색 점선)
      candlestickSeries.createPriceLine({
        price: vcpRange.secondHalf,
        color: '#3b82f6',
        lineWidth: 2,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: '후반부',
      });
    }

    // Volume Series (Overlay) (v5 API)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume_scale', // Custom scale ID
    });

    // Configure the volume scale to be an overlay at the bottom
    chart.priceScale('volume_scale').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const volumeData = data.map((d: any) => ({
      time: d.date as Time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(239, 68, 68, 0.5)' : 'rgba(59, 130, 246, 0.5)',
    }));
    volumeSeries.setData(volumeData);



    // Moving Average Series (SMA 20)
    const smaData = calculateSMA(data, 20);
    const smaSeries = chart.addSeries(LineSeries, {
      color: '#fbbf24', // Amber-400
      lineWidth: 2,
      crosshairMarkerVisible: false,
    });
    smaSeries.setData(smaData);

    chart.timeScale().fitContent();

    chartRef.current = chart;

    chart.timeScale().fitContent();

    chartRef.current = chart;

    // Resize Observer for efficient resizing
    const resizeObserver = new ResizeObserver(entries => {
      if (entries.length === 0 || !entries[0].contentRect) return;
      const { width, height } = entries[0].contentRect;
      chart.applyOptions({ width, height });
    });

    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [data, vcpRange]);

  return (
    <div className="w-full h-full relative group">
      <div ref={chartContainerRef} className="w-full h-full" />
      <div className="absolute top-2 left-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        <span className="text-[10px] text-amber-400 font-bold bg-black/50 px-2 py-1 rounded border border-amber-400/30">SMA 20</span>
        {vcpRange?.enabled && (
          <span className="text-[10px] text-rose-400 font-bold bg-black/50 px-2 py-1 rounded border border-rose-400/30 ml-1">VCP Range</span>
        )}
      </div>
    </div>
  );
}

function calculateSMA(data: any[], period: number) {
  const smaData = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      continue;
    }
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    smaData.push({ time: data[i].date, value: sum / period });
  }
  return smaData;
}
