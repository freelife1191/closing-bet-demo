'use client';

import React, { useState } from 'react';

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

interface KPIData {
  totalSignals: number;
  winRate: number;
  wins: number;
  losses: number;
  open: number;
  avgRoi: number;
  totalRoi: number;
  avgDays: number;
  priceDate: string;
  profitFactor: number;
}

function StatCard({ title, value, colorClass = 'text-white', subtext }: { title: string, value: string | number, colorClass?: string, subtext?: string }) {
  return (
    <div className="bg-[#1c1c1e] p-4 rounded-xl border border-white/5 flex flex-col justify-between h-24">
      <div className="text-[10px] text-gray-500 font-bold tracking-wider uppercase">{title}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>{value}</div>
      {subtext && <div className="text-xs text-gray-500">{subtext}</div>}
    </div>
  );
}

function GradeCard({ data }: { data: any }) {
  return (
    <div className={`p-5 rounded-2xl border ${data.border} ${data.bg} flex flex-col justify-between h-32`}>
      <div className="flex justify-between items-start">
        <h3 className={`text-lg font-bold ${data.color}`}>{data.grade} 등급</h3>
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
}

function DistributionBar({ kpi }: { kpi: KPIData }) {
  const total = kpi.wins + kpi.open + kpi.losses;
  const wPct = total > 0 ? (kpi.wins / total) * 100 : 0;
  const oPct = total > 0 ? (kpi.open / total) * 100 : 0;
  const lPct = total > 0 ? (kpi.losses / total) * 100 : 0;

  return (
    <div className="bg-[#1c1c1e] p-6 rounded-2xl border border-white/5 mb-8">
      <h3 className="text-gray-500 text-xs font-bold uppercase tracking-wider mb-4">승패 분포 (WIN/LOSS)</h3>
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

function TradeTable({ trades }: { trades: Trade[] }) {
  return (
    <div className="bg-[#1c1c1e] rounded-2xl border border-white/5 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[800px]">
          <thead className="bg-[#2c2c2e]/50 text-[10px] uppercase text-gray-500 font-medium">
            <tr>
              <th className="py-3 px-4 w-12 text-center">#</th>
              <th className="py-3 px-4">추천일</th>
              <th className="py-3 px-4">등급</th>
              <th className="py-3 px-4">종목명</th>
              <th className="py-3 px-4 text-right">진입가</th>
              <th className="py-3 px-4 text-center">결과</th>
              <th className="py-3 px-4 text-right">수익률</th>
              <th className="py-3 px-4 text-center whitespace-nowrap">최고가</th>
              <th className="py-3 px-4 text-center whitespace-nowrap">가격흐름</th>
              <th className="py-3 px-4 text-center whitespace-nowrap">보유일</th>
              <th className="py-3 px-4 text-center whitespace-nowrap">점수</th>
              <th className="py-3 px-4">테마</th>
            </tr>
          </thead>
          <tbody className="text-xs divide-y divide-white/5">
            {trades.map((trade, idx) => (
              <tr key={trade.id} className="hover:bg-white/5 transition-colors group">
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
  const [outcomeFilter, setOutcomeFilter] = useState('All');
  const [gradeFilter, setGradeFilter] = useState('All');

  // State for Real Data
  const [kpi, setKpi] = useState<KPIData>({
    totalSignals: 0,
    winRate: 0,
    wins: 0,
    losses: 0,
    open: 0,
    avgRoi: 0,
    totalRoi: 0,
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
        setKpi(data.kpi);
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
  const cStats = calculateGradeStats('C');

  const gradeCards = [
    { grade: 'S', ...sStats, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
    { grade: 'A', ...aStats, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' },
    { grade: 'B', ...bStats, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
    { grade: 'C', ...cStats, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
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
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 p-2 md:px-4 md:py-2 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 rounded-lg text-sm transition-colors cursor-pointer whitespace-nowrap"
          >
            <i className="fas fa-sync-alt"></i>
            <span className="hidden sm:inline">새로고침</span>
          </button>
        </div>
      </div>

      {/* Metric Cards - Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <StatCard title="누적 추천수" value={kpi.totalSignals} />
        <StatCard title="승률" value={`${kpi.winRate}%`} colorClass="text-yellow-400" />
        <StatCard title="성공" value={kpi.wins} colorClass="text-emerald-400" />
        <StatCard title="실패" value={kpi.losses} colorClass="text-rose-400" />
        <StatCard title="보유중" value={kpi.open} colorClass="text-yellow-500" />
        <StatCard title="평균 수익률" value={`${kpi.avgRoi > 0 ? '+' : ''}${kpi.avgRoi}%`} colorClass={kpi.avgRoi >= 0 ? "text-emerald-400" : "text-rose-400"} />
      </div>

      {/* Metric Cards - Row 2 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="누적 수익률" value={`${kpi.totalRoi > 0 ? '+' : ''}${kpi.totalRoi}%`} colorClass={kpi.totalRoi >= 0 ? "text-emerald-400" : "text-rose-400"} />
        <StatCard title="평균 보유일" value={kpi.avgDays} />
        <StatCard title="데이터 기준일" value={kpi.priceDate} />
        <StatCard title="손익비 (Profit Factor)" value={kpi.profitFactor} colorClass="text-cyan-400" />
      </div>

      {/* Grade Performance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {gradeCards.map((data) => (
          <GradeCard key={data.grade} data={data} />
        ))}
      </div>

      {/* Distribution Bar */}
      <DistributionBar kpi={kpi} />

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
                <FilterButton label="C" count={cStats.count} active={gradeFilter === 'C'} onClick={() => setGradeFilter('C')} />
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
