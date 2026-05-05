'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { paperTradingAPI, krAPI, KRChartData } from '@/lib/api';

const StockChart = dynamic(() => import('@/app/dashboard/kr/vcp/StockChart'), { ssr: false });

type ChartPeriod = '1M' | '3M' | '6M' | '1Y';
const CHART_PERIODS: ChartPeriod[] = ['1M', '3M', '6M', '1Y'];

interface TradeRow {
  id: number;
  action: 'BUY' | 'SELL';
  ticker: string;
  name: string;
  price: number;
  quantity: number;
  timestamp: string;
  profit?: number | null;
  profit_rate?: number | null;
}

interface StockTradeHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  stock: {
    ticker: string;
    name: string;
  } | null;
}

const formatPercent = (value: number, digits = 2) => {
  if (!Number.isFinite(value)) return (0).toFixed(digits);
  return value.toFixed(digits);
};

export default function StockTradeHistoryModal({
  isOpen,
  onClose,
  stock,
}: StockTradeHistoryModalProps) {
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('3M');
  const [chartData, setChartData] = useState<KRChartData[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !stock) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    paperTradingAPI
      .getTradeHistory(500, stock.ticker)
      .then((data: { trades?: TradeRow[] }) => {
        if (cancelled) return;
        setTrades(Array.isArray(data?.trades) ? data.trades : []);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        console.error('Failed to fetch stock trade history', e);
        setError('거래 내역을 불러오지 못했습니다.');
        setTrades([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, stock]);

  useEffect(() => {
    if (!isOpen || !stock) return;
    let cancelled = false;
    setChartLoading(true);
    setChartError(null);
    krAPI
      .getStockChart(stock.ticker, chartPeriod.toLowerCase())
      .then((res) => {
        if (cancelled) return;
        setChartData(Array.isArray(res?.data) ? res.data : []);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        console.error('Failed to fetch stock chart', e);
        setChartError('차트 데이터를 불러오지 못했습니다.');
        setChartData([]);
      })
      .finally(() => {
        if (!cancelled) setChartLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, stock, chartPeriod]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const summary = useMemo(() => {
    let buyQty = 0;
    let buyAmount = 0;
    let sellQty = 0;
    let sellAmount = 0;
    let realizedProfit = 0;
    trades.forEach((t) => {
      const total = (t.price || 0) * (t.quantity || 0);
      if (t.action === 'BUY') {
        buyQty += t.quantity || 0;
        buyAmount += total;
      } else if (t.action === 'SELL') {
        sellQty += t.quantity || 0;
        sellAmount += total;
        realizedProfit += Number(t.profit || 0);
      }
    });
    const avgBuyPrice = buyQty > 0 ? buyAmount / buyQty : 0;
    const avgSellPrice = sellQty > 0 ? sellAmount / sellQty : 0;
    return {
      buyQty,
      buyAmount,
      sellQty,
      sellAmount,
      realizedProfit,
      avgBuyPrice,
      avgSellPrice,
      remainingQty: buyQty - sellQty,
    };
  }, [trades]);

  if (!isOpen || !stock) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative bg-[#1c1c1e] w-full max-w-4xl max-h-[85vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="stock-trade-history-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 md:p-5 border-b border-white/10 bg-[#252529] flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500 to-orange-500 flex items-center justify-center shadow-lg shadow-rose-500/20 flex-shrink-0">
              <i className="fas fa-receipt text-white text-lg"></i>
            </div>
            <div className="min-w-0">
              <h2
                id="stock-trade-history-title"
                className="text-lg md:text-xl font-bold text-white truncate"
              >
                {stock.name} 거래 내역
              </h2>
              <div className="text-xs text-slate-400 font-medium">{stock.ticker}</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors flex-shrink-0"
            aria-label="닫기"
          >
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-[#18181b] space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <i className="fas fa-spinner fa-spin text-2xl text-rose-500"></i>
            </div>
          ) : error ? (
            <div className="text-center text-red-400 py-12">{error}</div>
          ) : (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-[#252529] rounded-xl border border-white/5 p-3">
                  <div className="text-[10px] text-gray-500 mb-1">누적 매수</div>
                  <div className="text-sm font-bold text-rose-400">
                    {summary.buyQty.toLocaleString()}주
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">
                    {Math.floor(summary.buyAmount).toLocaleString()}원
                  </div>
                </div>
                <div className="bg-[#252529] rounded-xl border border-white/5 p-3">
                  <div className="text-[10px] text-gray-500 mb-1">누적 매도</div>
                  <div className="text-sm font-bold text-blue-400">
                    {summary.sellQty.toLocaleString()}주
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">
                    {Math.floor(summary.sellAmount).toLocaleString()}원
                  </div>
                </div>
                <div className="bg-[#252529] rounded-xl border border-white/5 p-3">
                  <div className="text-[10px] text-gray-500 mb-1">평균 매수단가</div>
                  <div className="text-sm font-bold text-white">
                    {Math.round(summary.avgBuyPrice).toLocaleString()}원
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">
                    잔여 {summary.remainingQty.toLocaleString()}주
                  </div>
                </div>
                <div className="bg-[#252529] rounded-xl border border-white/5 p-3">
                  <div className="text-[10px] text-gray-500 mb-1">실현손익</div>
                  <div
                    className={`text-sm font-bold ${
                      summary.realizedProfit >= 0 ? 'text-rose-400' : 'text-blue-400'
                    }`}
                  >
                    {summary.realizedProfit > 0 ? '+' : ''}
                    {Math.round(summary.realizedProfit).toLocaleString()}원
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">
                    매도 {summary.sellQty.toLocaleString()}주 기준
                  </div>
                </div>
              </div>

              {/* Price & Volume chart */}
              <div className="bg-[#252529] rounded-xl border border-white/5 p-3 md:p-4">
                <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                  <div className="text-xs text-gray-400 font-bold flex items-center gap-2">
                    <i className="fas fa-chart-bar text-rose-400"></i>
                    가격·거래량 추세
                  </div>
                  <div className="flex items-center gap-1">
                    {CHART_PERIODS.map((p) => (
                      <button
                        key={p}
                        onClick={() => setChartPeriod(p)}
                        className={`px-2 py-1 text-[11px] rounded transition-colors ${
                          chartPeriod === p
                            ? 'bg-rose-500 text-white font-bold'
                            : 'bg-black/20 text-gray-400 hover:bg-black/40 hover:text-white'
                        }`}
                      >
                        {p === '1M' && '1개월'}
                        {p === '3M' && '3개월'}
                        {p === '6M' && '6개월'}
                        {p === '1Y' && '1년'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="relative w-full" style={{ height: '280px' }}>
                  {chartLoading ? (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-400">
                      <i className="fas fa-spinner fa-spin text-lg"></i>
                    </div>
                  ) : chartError ? (
                    <div className="absolute inset-0 flex items-center justify-center text-amber-400 text-xs">
                      {chartError}
                    </div>
                  ) : chartData.length === 0 ? (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-xs">
                      차트 데이터가 없습니다.
                    </div>
                  ) : (
                    <StockChart data={chartData} ticker={stock.ticker} name={stock.name} />
                  )}
                </div>
              </div>

              {/* Trade list */}
              <div className="bg-[#252529] rounded-xl border border-white/5 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse min-w-[640px]">
                    <thead>
                      <tr className="bg-white/5 text-xs text-gray-500 uppercase tracking-wider">
                        <th className="px-4 py-3 font-semibold whitespace-nowrap">일시</th>
                        <th className="px-4 py-3 font-semibold text-center whitespace-nowrap">
                          유형
                        </th>
                        <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                          단가
                        </th>
                        <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                          수량
                        </th>
                        <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                          총액
                        </th>
                        <th className="px-4 py-3 font-semibold text-right whitespace-nowrap">
                          실현손익
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {trades.map((t) => {
                        const total = (t.price || 0) * (t.quantity || 0);
                        const profit = Number(t.profit || 0);
                        const profitRate = Number(t.profit_rate || 0);
                        return (
                          <tr key={t.id} className="hover:bg-white/5 transition-colors">
                            <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-400">
                              {new Date(t.timestamp).toLocaleString('ko-KR')}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-center">
                              <span
                                className={`px-2 py-1 rounded text-[10px] font-bold ${
                                  t.action === 'BUY'
                                    ? 'bg-rose-500/10 text-rose-400'
                                    : 'bg-blue-500/10 text-blue-400'
                                }`}
                              >
                                {t.action === 'BUY' ? '매수' : '매도'}
                              </span>
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-300">
                              {Math.round(t.price || 0).toLocaleString()}원
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-right text-sm text-gray-300">
                              {(t.quantity || 0).toLocaleString()}주
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-right text-sm font-bold text-white">
                              {Math.floor(total).toLocaleString()}원
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap text-right">
                              {t.action === 'SELL' && t.profit !== undefined && t.profit !== null ? (
                                <div>
                                  <div
                                    className={`text-sm font-bold ${
                                      profit >= 0 ? 'text-rose-400' : 'text-blue-400'
                                    }`}
                                  >
                                    {profit > 0 ? '+' : ''}
                                    {Math.round(profit).toLocaleString()}원
                                  </div>
                                  <div
                                    className={`text-xs ${
                                      profitRate >= 0 ? 'text-rose-500/70' : 'text-blue-500/70'
                                    }`}
                                  >
                                    {profitRate > 0 ? '+' : ''}
                                    {formatPercent(profitRate, 2)}%
                                  </div>
                                </div>
                              ) : (
                                <span className="text-gray-600">-</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                      {trades.length === 0 && (
                        <tr>
                          <td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                            해당 종목의 거래 내역이 없습니다.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
