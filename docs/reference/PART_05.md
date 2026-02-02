# PART 5 (Core Logic)

### frontend/src/app/dashboard/kr/page.tsx (kr_market_package/frontend/src/app/dashboard/kr/page.tsx)
```tsx
'use client';

import { useEffect, useState } from 'react';
import { krAPI, KRMarketGate, KRSignalsResponse } from '@/lib/api';

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
    closing_bet: BacktestStats;
}

export default function KRMarketOverview() {
    const [gateData, setGateData] = useState<KRMarketGate | null>(null);
    const [signalsData, setSignalsData] = useState<KRSignalsResponse | null>(null);
    const [backtestData, setBacktestData] = useState<BacktestSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<string>('');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            // Load core data
            const [gate, signals] = await Promise.all([
                krAPI.getMarketGate(),
                krAPI.getSignals(),
            ]);
            setGateData(gate);
            setSignalsData(signals);

            // Load Backtest Summary
            const btRes = await fetch('/api/kr/backtest-summary');
            if (btRes.ok) {
                setBacktestData(await btRes.json());
            }

            setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
        } catch (error) {
            console.error('Failed to load KR Market data:', error);
        } finally {
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

    return (
        <div className="space-y-8">
            {/* Header */}
            <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-rose-500/20 bg-rose-500/5 text-xs text-rose-400 font-medium mb-4">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
                    KR Market Alpha
                </div>
                <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
                    Smart Money <span className="text-transparent bg-clip-text bg-gradient-to-r from-rose-400 to-amber-400">Footprints</span>
                </h2>
                <p className="text-gray-400 text-lg">VCP 패턴 & 기관/외국인 수급 추적</p>
            </div>

            {/* Market Gate Section */}
            <section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                {/* Gate Score Card */}
                <div className="lg:col-span-1 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity text-rose-500">
                        <i className="fas fa-chart-line text-4xl"></i>
                    </div>
                    <h3 className="text-sm font-bold text-gray-400 mb-4 flex items-center gap-2">
                        KR Market Gate
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
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
                                    className={`${getGateColor(gateData?.score ?? 0)} transition-all duration-1000 ease-out`}
                                />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className={`text-3xl font-black ${getGateColor(gateData?.score ?? 0)}`}>
                                    {loading ? '--' : gateData?.score ?? '--'}
                                </span>
                                <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Score</span>
                            </div>
                        </div>
                        <div className="mt-4 px-4 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-bold text-gray-400">
                            {loading ? 'Analyzing...' : gateData?.label ?? 'N/A'}
                        </div>
                    </div>
                </div>

                {/* Sector Grid */}
                <div className="lg:col-span-3 p-6 rounded-2xl bg-[#1c1c1e] border border-white/10">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-bold text-gray-400">KOSPI 200 Sector Index</h3>
                        <div className="flex items-center gap-4 text-[10px] font-bold text-gray-500 uppercase tracking-tighter">
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500"></span> Bullish</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500"></span> Neutral</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"></span> Bearish</span>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
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
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* 1. Today's Signals */}
                <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-rose-500/30 transition-all">
                    <div className="absolute top-0 right-0 w-20 h-20 bg-rose-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
                    <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Today&apos;s Signals</div>
                    <div className="text-3xl font-black text-white group-hover:text-rose-400 transition-colors">
                        {loading ? '--' : signalsData?.signals?.length ?? 0}
                    </div>
                    <div className="mt-2 text-xs text-gray-500">VCP + 외국인 순매수</div>
                </div>

                {/* 2. VCP Strategy Performance */}
                <div className="p-5 rounded-2xl bg-[#1c1c1e] border border-white/10 relative overflow-hidden group hover:border-amber-500/30 transition-all">
                    <div className="absolute top-0 right-0 w-20 h-20 bg-amber-500/10 rounded-full blur-[25px] -translate-y-1/2 translate-x-1/2"></div>
                    <div className="flex justify-between items-start">
                        <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">VCP Strategy</div>
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
                        <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Closing Bet</div>
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
                    onClick={loadData}
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

            {/* Market Indices (Existing) */}
            <section>
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                        <span className="w-1 h-5 bg-rose-500 rounded-full"></span>
                        Market Indices
                    </h3>
                    <span className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">KOSPI / KOSDAQ</span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
                        <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KOSPI</div>
                        <div className="flex items-end gap-2">
                            <span className="text-xl font-black text-white">
                                {loading ? '--' : gateData?.kospi_close?.toLocaleString() ?? '--'}
                            </span>
                            {gateData && (
                                <span className={`text-xs font-bold mb-0.5 ${gateData.kospi_change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                                    <i className={`fas fa-caret-${gateData.kospi_change_pct >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                                    {gateData.kospi_change_pct >= 0 ? '+' : ''}{gateData.kospi_change_pct?.toFixed(2)}%
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="p-4 rounded-2xl bg-[#1c1c1e] border border-white/10">
                        <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1">KOSDAQ</div>
                        <div className="flex items-end gap-2">
                            <span className="text-xl font-black text-white">
                                {loading ? '--' : gateData?.kosdaq_close?.toLocaleString() ?? '--'}
                            </span>
                            {gateData && (
                                <span className={`text-xs font-bold mb-0.5 ${gateData.kosdaq_change_pct >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                                    <i className={`fas fa-caret-${gateData.kosdaq_change_pct >= 0 ? 'up' : 'down'} mr-0.5`}></i>
                                    {gateData.kosdaq_change_pct >= 0 ? '+' : ''}{gateData.kosdaq_change_pct?.toFixed(2)}%
                                </span>
                            )}
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
```

### frontend/src/app/dashboard/kr/closing-bet/page.tsx (kr_market_package/frontend/src/app/dashboard/kr/closing-bet/page.tsx)
```tsx
'use client';

import React, { useState, useEffect } from 'react';

// Interfaces (Based on backend models)
interface ScoreDetail {
    news: number;
    volume: number;
    chart: number;
    candle: number;
    consolidation: number;
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
    grade: string; // 'S', 'A', 'B', 'C'
    score: ScoreDetail;
    checklist: ChecklistDetail;
    current_price: number;
    entry_price: number;
    stop_price: number;
    target_price: number;
    change_pct: number;
    trading_value: number;
    news_items?: NewsItem[];
}

interface ScreenerResult {
    date: string;
    total_candidates: number;
    filtered_count: number;
    signals: Signal[];
    updated_at: string;
}

// 3. Naver Chart Image Component (Bypass iframe restriction)
function NaverChartWidget({ symbol }: { symbol: string }) {
    // stable timestamp for the lifecycle of the component
    const [timestamp] = useState(() => Date.now());

    return (
        <div className="flex flex-col items-center justify-center p-8 bg-white h-full relative">
            <div className="w-full flex-1 flex items-center justify-center overflow-hidden">
                <img
                    src={`https://ssl.pstatic.net/imgfinance/chart/item/candle/day/${symbol}.png?sidcode=${timestamp}`}
                    alt="Chart"
                    className="max-w-full max-h-full object-contain"
                />
            </div>
            <a
                href={`https://m.stock.naver.com/domestic/stock/${symbol}/chart`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 px-6 py-3 bg-[#03c75a] hover:bg-[#00b24e] text-white font-bold rounded-xl transition-all shadow-lg hover:shadow-xl flex items-center gap-2"
            >
                <span>View Interactive Chart (Naver)</span>
                <i className="fas fa-external-link-alt"></i>
            </a>
            <p className="mt-4 text-xs text-gray-400">
                * Static chart image provided by Naver Finance. Click the button for real-time interactive analysis.
            </p>
        </div>
    );
}

// 4. Chart Modal Component
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
                {/* Header */}
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

                {/* Content - White background for Chart Image */}
                <div className="flex-1 bg-white relative">
                    <NaverChartWidget symbol={symbol} />
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

    // 차트 모달 상태
    const [chartModal, setChartModal] = useState<{ isOpen: boolean, symbol: string, name: string }>({
        isOpen: false, symbol: '', name: ''
    });

    // 1. Load Available Dates
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

    // 2. Load Data (Latest or Specific Date)
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
            {/* 1. Header Section (VCP Style) */}
            <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/20 bg-indigo-500/5 text-xs text-indigo-400 font-medium mb-4">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-ping"></span>
                    AI Powered Strategy
                </div>
                <h2 className="text-4xl md:text-5xl font-bold tracking-tighter text-white leading-tight mb-2">
                    Closing <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Bet V2</span>
                </h2>
                <p className="text-gray-400 text-lg">
                    Gemini 3.0 Analysis + Institutional Supply Trend
                </p>
            </div>

            {/* 2. Controls & Stats */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/5">
                <div className="flex gap-6">
                    <StatBox label="Candidates" value={data?.total_candidates || 0} />
                    <StatBox label="Signals" value={data?.filtered_count || 0} highlight />
                    <DataStatusBox updatedAt={data?.updated_at} />
                </div>

                <div className="flex items-center gap-3">
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
                    <button
                        onClick={() => setSelectedDate(selectedDate)}
                        className="p-2 bg-[#1c1c1e] border border-white/10 rounded-xl hover:bg-white/5 text-gray-400 hover:text-white transition-all"
                        title="Refresh"
                    >
                        <i className="fas fa-sync-alt"></i> ↻
                    </button>
                </div>
            </div>

            {/* 3. Signal Grid */}
            <div className="grid grid-cols-1 gap-6">
                {!data || data.signals.length === 0 ? (
                    <div className="bg-[#1c1c1e] rounded-2xl p-16 text-center border border-white/5 flex flex-col items-center">
                        <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4">
                            <span className="text-3xl opacity-30">💤</span>
                        </div>
                        <h3 className="text-xl font-bold text-gray-300">No Signals Found</h3>
                        <p className="text-gray-500 mt-2 max-w-md">
                            Today&apos;s market conditions did not meet the strict AI & Supply criteria.
                        </p>
                    </div>
                ) : (
                    data.signals.map((signal, idx) => (
                        <SignalCard
                            key={signal.stock_code}
                            signal={signal}
                            index={idx}
                            onOpenChart={() => setChartModal({ isOpen: true, symbol: signal.stock_code, name: signal.stock_name })}
                        />
                    ))
                )}
            </div>

            <div className="text-center text-xs text-gray-600 pt-8">
                Engine: v2.0.1 (Gemini 3.0 Flash) • Updated: {data?.updated_at || '-'}
            </div>

            {/* Chart Modal */}
            {chartModal.isOpen && (
                <ChartModal
                    symbol={chartModal.symbol}
                    name={chartModal.name}
                    onClose={() => setChartModal({ ...chartModal, isOpen: false })}
                />
            )}
        </div>
    );
}

function DataStatusBox({ updatedAt }: { updatedAt?: string }) {
    const [updating, setUpdating] = useState(false);

    if (!updatedAt && !updating) return <StatBox label="Data Status" value={0} customValue="LOADING..." />;

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
        if (!confirm('종가베팅 v2 분석 엔진을 전체 실행하시겠습니까? (수분 소요될 수 있음)')) return;

        setUpdating(true);
        try {
            const res = await fetch('/api/kr/jongga-v2/run', { method: 'POST' });
            if (res.ok) {
                alert('전체 분석이 완료되었습니다!');
                window.location.reload();
            } else {
                alert('엔진 실행 실패. 서버 로그를 확인하세요.');
            }
        } catch (error) {
            console.error(error);
            alert('업데이트 요청 중 오류 발생');
        } finally {
            setUpdating(false);
        }
    }

    return (
        <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1 flex items-center gap-2">
                Data Status
                <button
                    onClick={handleUpdate}
                    disabled={updating}
                    className={`p-1 rounded bg-white/5 hover:bg-white/10 transition-all ${updating ? 'animate-spin text-indigo-400' : 'text-gray-500 hover:text-white'}`}
                    title="Run Engine V2 (Full Update)"
                >
                    <i className="fas fa-sync-alt text-[10px]"></i>
                </button>
            </span>
            <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${(isToday && !updating) ? 'bg-emerald-500 animate-pulse' : 'bg-gray-500'}`}></span>
                <span className={`text-xl font-mono font-bold ${(isToday && !updating) ? 'text-emerald-400' : 'text-gray-400'}`}>
                    {updating ? 'RUNNING...' : (isToday ? 'UPDATED' : 'OLD DATA')}
                </span>
            </div>
            <span className="text-[10px] text-gray-600 font-mono mt-0.5">{updating ? 'Please wait...' : timeStr}</span>
        </div>
    )
}

function StatBox({ label, value, highlight = false, customValue }: { label: string, value: number, highlight?: boolean, customValue?: string }) {
    return (
        <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-1">{label}</span>
            <span className={`text-2xl font-mono font-bold ${highlight ? 'text-indigo-400' : 'text-white'}`}>
                {customValue || value}
            </span>
        </div>
    )
}

function SignalCard({ signal, index, onOpenChart }: { signal: Signal, index: number, onOpenChart: () => void }) {
    // 등급별 스타일
    const gradeStyles: Record<string, { bg: string, text: string, border: string, glow: string }> = {
        S: { bg: 'bg-indigo-500/10', text: 'text-indigo-400', border: 'border-indigo-500/30', glow: 'shadow-indigo-500/20' },
        A: { bg: 'bg-rose-500/10', text: 'text-rose-400', border: 'border-rose-500/30', glow: 'shadow-rose-500/20' },
        B: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30', glow: 'shadow-blue-500/30' },
        C: { bg: 'bg-gray-500/10', text: 'text-gray-400', border: 'border-gray-500/30', glow: 'shadow-gray-500/20' },
    };

    const style = gradeStyles[signal.grade] || gradeStyles.B;

    // 날짜 포맷팅 헬퍼 (2025-01-15T12:00 -> 01.15)
    const formatDate = (isoString: string) => {
        if (!isoString) return '';
        const d = new Date(isoString);
        return `${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getDate().toString().padStart(2, '0')}`;
    };

    return (
        <div
            className={`relative rounded-2xl border ${style.border} bg-[#1c1c1e] overflow-hidden transition-all duration-300 hover:scale-[1.01] hover:border-opacity-50 group`}
            style={{ animationDelay: `${index * 0.1}s`, animationFillMode: 'both' }}
        >
            {/* Background Glow */}
            <div className={`absolute top-0 right-0 w-64 h-64 ${style.bg} rounded-full blur-[60px] -translate-y-1/2 translate-x-1/2 opacity-20 group-hover:opacity-30 transition-opacity`}></div>

            <div className="flex flex-col lg:flex-row relative z-10">

                {/* Left: Info & Grade */}
                <div className="p-6 lg:w-1/3 border-b lg:border-b-0 lg:border-r border-white/5 flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${style.border} ${style.bg} ${style.text}`}>
                                {signal.grade} GRADE
                            </span>
                            <span className="text-xs text-gray-500 font-mono">#{index + 1}</span>
                        </div>

                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-2xl font-bold text-white leading-none mb-1">
                                    {signal.stock_name}
                                </h3>
                                <div className="text-sm text-gray-400 font-mono">{signal.stock_code}</div>
                            </div>
                            <div className={`text-4xl font-black ${style.text} opacity-20`}>{signal.grade}</div>
                        </div>

                        <div className="mt-6 flex flex-wrap gap-2">
                            {/* Tags */}
                            {signal.checklist.is_new_high && (
                                <span className="px-2 py-1 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[10px] font-bold">NEW HIGH</span>
                            )}
                            {signal.checklist.supply_positive && (
                                <span className="px-2 py-1 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px] font-bold">INST BUY</span>
                            )}
                            {signal.checklist.has_news && (
                                <span className="px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold">NEWS</span>
                            )}
                        </div>
                    </div>

                    <div className="mt-8">

                        <button
                            onClick={onOpenChart}
                            className="mt-6 flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm text-gray-300 transition-all hover:text-white w-fit group-hover:border-indigo-500/30"
                        >
                            <i className="fas fa-chart-line text-indigo-400"></i>
                            <span>View Chart</span>
                        </button>
                    </div>
                </div>

                {/* Middle: AI Analysis + News References */}
                <div className="p-6 lg:w-5/12 border-b lg:border-b-0 lg:border-r border-white/5 flex flex-col">
                    <div className="mb-3 flex items-center gap-2">
                        <span className="w-1.5 h-1.5 bg-gradient-to-r from-blue-400 to-indigo-400 rounded-full"></span>
                        <span className="text-xs font-bold text-gray-300">Gemini 3.0 Analysis</span>
                    </div>
                    {/* Analysis Text */}
                    <div className="bg-black/20 rounded-xl p-5 text-sm text-gray-300 leading-relaxed border border-white/5 mb-4">
                        {signal.score.llm_reason ? (
                            `"${signal.score.llm_reason}"`
                        ) : (
                            <span className="text-gray-600 italic">No analysis available.</span>
                        )}
                    </div>

                    {/* News References */}
                    {signal.news_items && signal.news_items.length > 0 && (
                        <div className="mt-auto">
                            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-bold mb-2 flex items-center gap-1">
                                <i className="fas fa-quote-left"></i> References
                            </div>
                            <div className="space-y-1.5">
                                {signal.news_items.slice(0, 3).map((news, i) => (
                                    <a
                                        key={i}
                                        href={news.url || '#'}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="block text-xs text-gray-400 hover:text-indigo-400 hover:bg-white/5 p-1.5 rounded transition-colors truncate"
                                    >
                                        <span className="text-gray-500 font-mono mr-2">[{news.source || 'News'}]</span>
                                        <span className="mr-2">{news.title}</span>
                                        <span className="text-gray-600 text-[10px] ml-auto">({formatDate(news.published_at)})</span>
                                    </a>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Right: Score Breakdown */}
                <div className="p-6 lg:w-1/4 bg-white/[0.02] flex flex-col justify-center">
                    <div className="text-center mb-6">
                        <div className="inline-flex items-baseline gap-1">
                            <span className="text-4xl font-mono font-bold text-white">{signal.score.total}</span>
                            <span className="text-sm text-gray-500">/ 10</span>
                        </div>
                        <div className="text-[10px] text-gray-500 mt-1 uppercase tracking-wider">Total Score</div>
                    </div>

                    <div className="space-y-2.5">
                        <ScoreBar label="News" score={signal.score.news} max={3} />
                        <ScoreBar label="Supply" score={signal.score.supply} max={2} />
                        <ScoreBar label="Chart" score={signal.score.chart} max={2} />
                        <ScoreBar label="Volume" score={signal.score.volume} max={2} />
                        <ScoreBar label="Candle" score={signal.score.candle} max={1} />
                    </div>
                </div>

            </div>
        </div>
    );
}

function ScoreBar({ label, score, max }: { label: string, score: number, max: number }) {
    const pct = (score / max) * 100;
    return (
        <div className="flex items-center gap-3 text-xs">
            <span className="w-12 text-gray-400 text-right">{label}</span>
            <div className="flex-1 h-1.5 bg-gray-700/50 rounded-full overflow-hidden border border-white/5">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${pct >= 100 ? 'bg-gradient-to-r from-emerald-500 to-green-400' : pct >= 50 ? 'bg-gradient-to-r from-yellow-500 to-orange-400' : 'bg-gray-600'}`}
                    style={{ width: `${pct}%` }}
                ></div>
            </div>
            <span className="w-8 text-right font-mono text-gray-300 transform scale-90">
                <span className="text-white font-bold">{score}</span>
                <span className="text-gray-600">/{max}</span>
            </span>
        </div>
    )
}
```

### frontend/src/lib/api.ts (kr_market_package/frontend/src/lib/api.ts)
```typescript
// API utility functions

const API_BASE = '';  // Empty = use Next.js proxy

export async function fetchAPI<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`);
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
}

// KR Market API Types
export interface KRSignal {
    ticker: string;
    name: string;
    market: 'KOSPI' | 'KOSDAQ';
    signal_date: string;
    entry_price: number;
    current_price: number;
    return_pct: number;
    foreign_5d: number;
    inst_5d: number;
    score: number;
    contraction_ratio: number;
}

export interface KRSignalsResponse {
    signals: KRSignal[];
    error?: string;
}

export interface KRMarketGate {
    score: number;
    label: string;
    kospi_close: number;
    kospi_change_pct: number;
    kosdaq_close: number;
    kosdaq_change_pct: number;
    sectors: KRSector[];
}

export interface KRSector {
    name: string;
    change_pct: number;
    signal: 'bullish' | 'neutral' | 'bearish';
}

export interface AIRecommendation {
    action: 'BUY' | 'SELL' | 'HOLD';
    confidence: number;
    reason: string;
}

export interface KRAIAnalysis {
    signals: Array<{
        ticker: string;
        gpt_recommendation?: AIRecommendation;
        gemini_recommendation?: AIRecommendation;
    }>;
    market_indices?: {
        kospi?: { value: number; change_pct: number };
        kosdaq?: { value: number; change_pct: number };
    };
}

// KR Market API functions
export const krAPI = {
    getSignals: () => fetchAPI<KRSignalsResponse>('/api/kr/signals'),
    getMarketGate: () => fetchAPI<KRMarketGate>('/api/kr/market-gate'),
    getAIAnalysis: () => fetchAPI<KRAIAnalysis>('/api/kr/ai-analysis'),
    getStockChart: (ticker: string, period = '6mo') =>
        fetchAPI<{ candles: any[] }>(`/api/kr/stock-chart/${ticker}?period=${period}`),
    getHistoryDates: () => fetchAPI<{ dates: string[] }>('/api/kr/ai-history-dates'),
    getHistory: (date: string) => fetchAPI<KRAIAnalysis>(`/api/kr/ai-history/${date}`),
};

// Closing Bet API
export interface ClosingBetCandidate {
    rank: number;
    ticker: string;
    name: string;
    market: string;
    grade: 'S' | 'A' | 'B' | 'C' | 'D';
    price: number;
    change_pct: number;
    total_score: number;
    scores: {
        volume: number;
        institutional: number;
        news: number;
        chart: number;
        candle: number;
        consolidation: number;
    };
}

export interface ClosingBetResponse {
    candidates: ClosingBetCandidate[];
}

export interface ClosingBetTiming {
    phase: string;
    time_remaining: string;
    urgency_score: number;
    is_entry_allowed: boolean;
    recommended_action: string;
}

export const closingBetAPI = {
    getCandidates: (limit = 25) =>
        fetchAPI<ClosingBetResponse>(`/api/kr/closing-bet/candidates?limit=${limit}`),
    getTiming: () => fetchAPI<ClosingBetTiming>('/api/kr/closing-bet/timing'),
    getBacktestStats: () => fetchAPI<any>('/api/kr/closing-bet/backtest-stats'),
};
```

