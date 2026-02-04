'use client';

import { useState, useEffect, useRef } from 'react';
import { paperTradingAPI, PaperTradingPortfolio, PaperTradingAssetHistory, PaperTradingHolding } from '@/lib/api';
// Dynamic import usage below
import type { IChartApi } from 'lightweight-charts';
import BuyStockModal from './BuyStockModal';
import SellStockModal from './SellStockModal';
import ConfirmationModal from './ConfirmationModal';

interface PaperTradingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PaperTradingModal({ isOpen, onClose }: PaperTradingModalProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'holdings' | 'history' | 'chart'>('overview');
  const [portfolio, setPortfolio] = useState<PaperTradingPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  // 충전 관련 state
  const [showDeposit, setShowDeposit] = useState(false);
  const [depositAmount, setDepositAmount] = useState('10000000'); // 기본 1000만원

  // 거래 내역 state
  const [tradeHistory, setTradeHistory] = useState<any[]>([]);

  // 차트 관련 state
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [chartData, setChartData] = useState<PaperTradingAssetHistory[]>([]);
  const [maToggle, setMaToggle] = useState<{ [key: number]: boolean }>({ 10: true });
  const [timeRange, setTimeRange] = useState<'1M' | '3M' | '6M' | '1Y' | 'ALL'>('1Y');

  // Modals state
  const [buyModalOpen, setBuyModalOpen] = useState(false);
  const [sellModalOpen, setSellModalOpen] = useState(false);
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [selectedStock, setSelectedStock] = useState<any>(null); // 매수/매도용 선택된 종목

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const data = await paperTradingAPI.getPortfolio();
      setPortfolio(data);
    } catch (e) {
      console.error("Failed to fetch portfolio", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const data = await paperTradingAPI.getTradeHistory(50);
      if (data.trades) {
        setTradeHistory(data.trades);
      }
    } catch (e) {
      console.error("Failed to fetch trade history", e);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchPortfolio();

      // Calculate days based on timeRange
      let days = 365;
      if (timeRange === '1M') days = 30;
      else if (timeRange === '3M') days = 90;
      else if (timeRange === '6M') days = 180;
      else if (timeRange === '1Y') days = 365;
      else if (timeRange === 'ALL') days = 3650;

      // 차트 데이터 로드
      paperTradingAPI.getAssetHistory(days).then(res => {
        if (res.history) setChartData(res.history);
      }).catch(console.error);
    }
  }, [isOpen, refreshKey, timeRange]);

  // 탭 변경 시 데이터 로드
  useEffect(() => {
    if (isOpen && activeTab === 'history') {
      fetchHistory();
    }
  }, [isOpen, activeTab, refreshKey]);

  // 차트 렌더링 (Dynamic Import 적용 + 데이터 포맷팅 강화)
  useEffect(() => {
    let chartInstance: any = null;
    let resizeObserver: ResizeObserver | null = null;

    const initChart = async () => {
      // 컴포넌트 마운트 및 데이터 유효성 확인
      if (activeTab === 'chart' && chartContainerRef.current) {

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

          // 데이터 포맷팅
          const formattedData = chartData
            .map(d => {
              const dateStr = typeof d.date === 'string' ? d.date.split('T')[0] : d.date;
              return {
                time: dateStr,
                value: d.total_asset
              };
            })
            .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

          if (formattedData.length === 0) {
            // 데이터가 아예 없으면 3일 전부터 오늘까지의 가상 데이터 생성 (사용자 요청)
            const today = new Date();
            const threeDaysAgo = new Date(today);
            threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);

            formattedData.push({ time: threeDaysAgo.toISOString().split('T')[0], value: 100000000 });
            formattedData.push({ time: today.toISOString().split('T')[0], value: 100000000 });
          } else if (formattedData.length === 1) {
            // 데이터가 1개뿐이면 3일 전 데이터를 시작점으로 추가
            const firstDate = new Date(formattedData[0].time);
            const prevDate = new Date(firstDate);
            prevDate.setDate(prevDate.getDate() - 3);
            formattedData.unshift({
              time: prevDate.toISOString().split('T')[0],
              value: 100000000 // 기본 초기 자산
            });
          }


          mainSeries.setData(formattedData);

          // 이평선 추가
          const maColors: Record<number, string> = {
            3: '#4ade80', 5: '#f87171', 10: '#60a5fa', 20: '#facc15',
            40: '#a78bfa', 60: '#fb923c', 100: '#e879f9', 120: '#94a3b8'
          };

          Object.entries(maToggle).forEach(([periodStr, isVisible]) => {
            const period = parseInt(periodStr);
            if (!isVisible) return;

            const maData = [];
            for (let i = 0; i < chartData.length; i++) {
              if (i < period - 1) continue;
              let sum = 0;
              for (let j = 0; j < period; j++) {
                sum += chartData[i - j].total_asset;
              }
              const dateStr = typeof chartData[i].date === 'string' ? chartData[i].date.split('T')[0] : chartData[i].date;
              maData.push({
                time: dateStr,
                value: sum / period
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
              priceFormatter: (p: number) => Math.round(p).toLocaleString(),
            },
          });

          // Floating Tooltip Logic
          // 툴팁 엘리먼트 생성 (DOM 조작 대신 React state로 관리하면 좋지만, Crosshair 성능상 ref로 직접 조작)
          const toolTipWidth = 200;
          const toolTipHeight = 100;
          const toolTipMargin = 15;

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

            const totalAsset = data.value;
            const profit = totalAsset - 100000000;
            const profitRate = (profit / 100000000) * 100;
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
                <span class="font-bold ${colorClass}">${sign}${profitRate.toFixed(2)}%</span>
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
        // 툴팁 제거 로직은 chart.remove()시 DOM은 알아서 정리되나? 
        // chartContainerRef.current 내부를 비우는게 확실함.
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = '';
        }
        chartInstance = null;
        chartRef.current = null;
      }
    };
  }, [activeTab, chartData, maToggle]);


  const handleDeposit = async () => {
    const amt = parseInt(depositAmount.replace(/,/g, ''), 10);
    if (!amt || amt <= 0) return;
    try {
      await paperTradingAPI.deposit(amt);
      alert(`${amt.toLocaleString()}원이 충전되었습니다.`);
      setShowDeposit(false);
      setRefreshKey(p => p + 1);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleResetConfirm = async () => {
    try {
      await paperTradingAPI.reset();
      setRefreshKey(p => p + 1);
      setActiveTab('overview');
      setResetModalOpen(false);
    } catch (e) {
      alert('초기화 실패');
    }
  };

  // Handlers for Buy/Sell
  const openBuyModal = (stock: PaperTradingHolding) => {
    setSelectedStock({
      ticker: stock.ticker,
      name: stock.name,
      price: stock.current_price || stock.avg_price,
      current_price: stock.current_price // BuyStockModal expects this
    });
    setBuyModalOpen(true);
  };

  const openSellModal = (stock: PaperTradingHolding) => {
    setSelectedStock({
      ticker: stock.ticker,
      name: stock.name,
      avg_price: stock.avg_price,
      current_price: stock.current_price,
      quantity: stock.quantity
    });
    setSellModalOpen(true);
  };

  const handleBuySubmit = async (ticker: string, name: string, price: number, quantity: number) => {
    try {
      await paperTradingAPI.buy({ ticker, name, price, quantity });
      alert(`${name} ${quantity}주 매수 완료`);
      setRefreshKey(p => p + 1);
      return true;
    } catch (e: any) {
      alert(`매수 실패: ${e.message}`);
      return false;
    }
  };

  const handleSellSubmit = async (ticker: string, name: string, price: number, quantity: number) => {
    try {
      await paperTradingAPI.sell({ ticker, price, quantity });
      alert(`${name} ${quantity}주 매도 완료`);
      setRefreshKey(p => p + 1);
      return true;
    } catch (e: any) {
      alert(`매도 실패: ${e.message}`);
      return false;
    }
  };


  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
        <div className="relative bg-[#1c1c1e] w-full max-w-6xl max-h-[90vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">

          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between p-4 md:p-5 border-b border-white/10 bg-[#252529] gap-4 md:gap-0">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 flex-shrink-0">
                <i className="fas fa-chart-line text-white text-lg md:text-xl"></i>
              </div>
              <div>
                <h2 className="text-lg md:text-xl font-bold text-white whitespace-nowrap">모의투자 포트폴리오</h2>
                <div className="text-xs text-slate-400 font-medium">Paper Trading Account</div>
              </div>
              <button onClick={onClose} className="ml-auto md:hidden w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-gray-400 hover:text-white">
                <i className="fas fa-times"></i>
              </button>
            </div>

            <div className="flex flex-col md:flex-row md:items-center gap-3 w-full md:w-auto">
              {portfolio && (
                <div className="flex flex-row items-center justify-between md:justify-start gap-4 px-4 py-3 md:py-2 bg-black/20 rounded-xl border border-white/5 md:mr-4 w-full md:w-auto">
                  <div className="text-right">
                    <div className="text-[10px] md:text-xs text-gray-500">총 평가 자산</div>
                    <div className="text-sm md:text-base font-bold text-white whitespace-nowrap">{Math.floor(portfolio.total_asset_value).toLocaleString()}원</div>
                  </div>
                  <div className="h-8 w-px bg-white/10"></div>
                  <div className="text-right group relative">
                    <div className="text-[10px] md:text-xs text-gray-500 flex items-center justify-end gap-1">
                      예수금
                      <button onClick={() => setShowDeposit(!showDeposit)} className="w-4 h-4 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500 hover:text-white flex items-center justify-center text-[10px] transition-colors">+</button>
                    </div>
                    <div className="text-sm md:text-base font-bold text-blue-400 whitespace-nowrap">{Math.floor(portfolio.cash).toLocaleString()}원</div>

                    {/* Deposit Popover */}
                    {showDeposit && (
                      <div className="absolute top-full right-0 mt-2 w-60 bg-[#2c2c2e] border border-white/10 rounded-lg shadow-xl p-3 z-50">
                        <div className="text-xs text-white mb-2 font-bold">예수금 충전</div>
                        <input
                          type="text"
                          className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-right text-sm text-white mb-2"
                          value={depositAmount}
                          onChange={e => setDepositAmount(e.target.value)}
                        />
                        <button onClick={handleDeposit} className="w-full py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-xs rounded font-bold">충전하기</button>
                      </div>
                    )}
                  </div>
                </div>
              )}
              <button onClick={onClose} className="hidden md:flex w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 items-center justify-center text-gray-400 hover:text-white transition-colors">
                <i className="fas fa-times"></i>
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/10 bg-[#1c1c1e] overflow-x-auto no-scrollbar">
            {[
              { id: 'overview', label: '자산 개요', icon: 'fa-wallet' },
              { id: 'holdings', label: '보유 종목', icon: 'fa-list' },
              { id: 'chart', label: '수익 차트', icon: 'fa-chart-area' },
              { id: 'history', label: '거래 내역', icon: 'fa-history' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-none flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors relative whitespace-nowrap focus:outline-none focus:ring-0 ${activeTab === tab.id ? 'text-white' : 'text-gray-500 hover:text-gray-300'
                  }`}
              >
                <i className={`fas ${tab.icon}`}></i>
                {tab.label}
                {activeTab === tab.id && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-rose-500 shadow-[0_-2px_8px_rgba(244,63,94,0.5)]"></div>
                )}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-[#18181b]">
            {loading ? (
              <div className="flex h-full items-center justify-center">
                <i className="fas fa-spinner fa-spin text-3xl text-rose-500"></i>
              </div>
            ) : !portfolio ? (
              <div className="text-center text-gray-500 mt-20">데이터를 불러올 수 없습니다.</div>
            ) : (
              <>
                {/* Overview Tab */}
                {activeTab === 'overview' && (
                  <div className="max-w-4xl mx-auto space-y-4 md:space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="bg-[#252529] p-5 md:p-6 rounded-2xl border border-white/5 relative overflow-hidden group hover:border-white/10 transition-colors">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                          <i className="fas fa-coins text-8xl text-rose-500 transform rotate-12"></i>
                        </div>
                        <div className="flex items-center gap-2 mb-1">
                          <div className="text-gray-400 text-sm font-medium">총 평가 손익</div>
                          <div className="group/info relative">
                            <i className="fas fa-question-circle text-gray-600 hover:text-gray-400 cursor-help text-xs"></i>
                            <div className="absolute left-0 bottom-full mb-2 w-64 bg-gray-800 text-xs text-gray-300 p-2 rounded border border-white/10 shadow-lg hidden group-hover/info:block z-50">
                              * 총 수익률 = (총 평가 자산 - 초기 자본금) / 초기 자본금<br />
                              * 초기 자본금: 1억 원<br />
                              (보유 현금 비중이 높으면 개별 종목 수익률보다 낮을 수 있습니다.)
                            </div>
                          </div>
                        </div>
                        <div className={`text-3xl md:text-4xl font-bold mb-2 tracking-tight ${(portfolio.total_profit || 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                          {(portfolio.total_profit || 0) > 0 ? '+' : ''}{(portfolio.total_profit || 0).toLocaleString()}원
                        </div>
                        <div className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${(portfolio.total_profit_rate || 0) >= 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-blue-500/10 text-blue-400'}`}>
                          <i className={`fas fa-caret-${(portfolio.total_profit_rate || 0) >= 0 ? 'up' : 'down'}`}></i>
                          {(portfolio.total_profit_rate || 0)}%
                        </div>
                      </div>

                      <div className="bg-[#252529] p-5 md:p-6 rounded-2xl border border-white/5 relative overflow-hidden group hover:border-white/10 transition-colors">
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                          <i className="fas fa-chart-pie text-8xl text-blue-500 transform -rotate-12"></i>
                        </div>
                        <div className="text-gray-400 text-sm font-medium mb-1">자산 구성</div>
                        <div className="flex items-center gap-4 mt-4">
                          <div className="flex-1">
                            <div className="flex justify-between text-xs mb-1 whitespace-nowrap gap-2">
                              <span className="text-gray-300">주식</span>
                              <span className="text-white font-bold">{((portfolio?.total_stock_value || 0) / portfolio.total_asset_value * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                              <div className="h-full bg-rose-500" style={{ width: `${((portfolio?.total_stock_value || 0) / portfolio.total_asset_value * 100)}%` }}></div>
                            </div>
                          </div>
                          <div className="flex-1">
                            <div className="flex justify-between text-xs mb-1 whitespace-nowrap gap-2">
                              <span className="text-gray-300">현금</span>
                              <span className="text-white font-bold">{(portfolio.cash / portfolio.total_asset_value * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                              <div className="h-full bg-blue-500" style={{ width: `${(portfolio.cash / portfolio.total_asset_value * 100)}%` }}></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Holdings Tab */}
                {activeTab === 'holdings' && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <div className="bg-[#252529] rounded-xl border border-white/5 overflow-hidden">
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse min-w-[800px]">
                          <thead>
                            <tr className="bg-white/5 text-xs text-gray-500 uppercase tracking-wider">
                              <th className="px-6 py-4 whitespace-nowrap font-semibold whitespace-nowrap">종목명</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">보유수량</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">평균단가</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">현재가</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">평가금액</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">손익(률)</th>
                              <th className="px-6 py-4 whitespace-nowrap font-semibold text-center whitespace-nowrap">주문</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {portfolio.holdings.map((stock) => (
                              <tr key={stock.ticker} className="hover:bg-white/5 transition-colors group">
                                <td className="px-6 py-4 whitespace-nowrap">
                                  <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-xs font-bold text-gray-400 group-hover:text-white group-hover:bg-white/10 transition-colors">
                                      {stock.ticker.slice(0, 2)}
                                    </div>
                                    <div>
                                      <div className="text-sm font-bold text-white">{stock.name}</div>
                                      <div className="text-xs text-gray-500">{stock.ticker}</div>
                                    </div>
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-300">
                                  {stock.quantity.toLocaleString()}주
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-300">
                                  {Math.round(stock.avg_price).toLocaleString()}원
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium text-white">
                                  {(stock.current_price || stock.avg_price).toLocaleString()}원
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-bold text-white">
                                  {(stock.market_value || Math.floor((stock.current_price || stock.avg_price) * stock.quantity)).toLocaleString()}원
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right">
                                  <div className={`text-sm font-bold ${(stock.profit_rate || 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                                    {(stock.profit_rate || 0) > 0 ? '+' : ''}{(stock.profit_rate || 0).toFixed(2)}%
                                  </div>
                                  <div className={`text-xs ${(stock.profit_loss || 0) >= 0 ? 'text-rose-500/70' : 'text-blue-500/70'}`}>
                                    {(stock.profit_loss || 0).toLocaleString()}원
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-center">
                                  <div className="flex items-center justify-center gap-2">
                                    <button
                                      onClick={() => openBuyModal(stock)}
                                      className="px-3 py-1.5 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white text-xs font-bold transition-colors"
                                    >
                                      매수
                                    </button>
                                    <button
                                      onClick={() => openSellModal(stock)}
                                      className="px-3 py-1.5 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500 hover:text-white text-xs font-bold transition-colors"
                                    >
                                      매도
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                            {portfolio.holdings.length === 0 && (
                              <tr>
                                <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                  보유 중인 종목이 없습니다.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* Chart Tab */}
                {activeTab === 'chart' && (
                  <div className="h-full flex flex-col space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    {/* Controls */}
                    <div className="bg-[#252529] p-3 rounded-xl border border-white/5 flex flex-wrap gap-2 items-center justify-between">
                      <div className="flex items-center gap-2">
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

                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 font-bold px-2">이동평균선</span>
                        {[3, 5, 10, 20, 60, 120].map(d => (
                          <label key={d} className="flex items-center gap-1.5 px-2 py-1 bg-black/20 rounded cursor-pointer hover:bg-black/40 transition-colors">
                            <input
                              type="checkbox"
                              checked={!!maToggle[d]}
                              onChange={e => setMaToggle(p => ({ ...p, [d]: e.target.checked }))}
                              className="rounded border-gray-600 bg-gray-700 text-rose-500 focus:ring-offset-0 focus:ring-0 w-3 h-3"
                            />
                            <span className="text-xs text-gray-300">{d}일</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    {/* Chart Container */}
                    <div className="bg-[#252529] rounded-xl border border-white/5 p-4 relative" style={{ minHeight: '250px' }}>
                      <div ref={chartContainerRef} className="w-full" style={{ height: '220px' }} />
                      {chartData.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center text-gray-500 bg-black/50 z-10 backdrop-blur-sm rounded-xl">
                          <div>
                            <p className="mb-2">표시할 데이터가 충분하지 않습니다</p>
                            <p className="text-xs opacity-70">거래를 시작하면 자산 변동 그래프가 그려집니다</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* History Tab (New) */}
                {activeTab === 'history' && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
                    <div className="bg-[#252529] rounded-xl border border-white/5 overflow-hidden">
                      <div className="overflow-x-auto"><table className="w-full text-left border-collapse min-w-[700px]">
                        <thead>
                          <tr className="bg-white/5 text-xs text-gray-500 uppercase tracking-wider">
                            <th className="px-6 py-4 whitespace-nowrap font-semibold whitespace-nowrap">일시</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold whitespace-nowrap">종목명</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold text-center whitespace-nowrap">유형</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">체결가</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">수량</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">총액</th>
                            <th className="px-6 py-4 whitespace-nowrap font-semibold text-right whitespace-nowrap">실현손익</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          {tradeHistory.map((trade) => (
                            <tr key={trade.id} className="hover:bg-white/5 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-400">
                                {new Date(trade.timestamp).toLocaleString('ko-KR')}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm font-bold text-white">{trade.name}</div>
                                <div className="text-xs text-gray-500">{trade.ticker}</div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <span className={`px-2 py-1 rounded text-[10px] font-bold ${trade.action === 'BUY' ? 'bg-rose-500/10 text-rose-400' : 'bg-blue-500/10 text-blue-400'}`}>
                                  {trade.action === 'BUY' ? '매수' : '매도'}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-300">
                                {trade.price.toLocaleString()}원
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-300">
                                {trade.quantity.toLocaleString()}주
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-bold text-white">
                                {Math.floor(trade.price * trade.quantity).toLocaleString()}원
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right">
                                {trade.action === 'SELL' && trade.profit !== undefined ? (
                                  <div>
                                    <div className={`text-sm font-bold ${(trade.profit || 0) >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                                      {(trade.profit || 0) > 0 ? '+' : ''}{(trade.profit || 0).toLocaleString()}원
                                    </div>
                                    <div className={`text-xs ${(trade.profit_rate || 0) >= 0 ? 'text-rose-500/70' : 'text-blue-500/70'}`}>
                                      {(trade.profit_rate || 0).toFixed(2)}%
                                    </div>
                                  </div>
                                ) : (
                                  <span className="text-gray-600">-</span>
                                )}
                              </td>
                            </tr>
                          ))}
                          {tradeHistory.length === 0 && (
                            <tr>
                              <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                거래 내역이 없습니다.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table></div>
                    </div>
                  </div>
                )}

                {/* Reset Button */}
                <div className="mt-8 pt-6 border-t border-white/5 flex justify-end">
                  <button
                    onClick={() => setResetModalOpen(true)}
                    className="px-4 py-2 rounded-lg text-sm text-gray-500 hover:text-rose-400 hover:bg-rose-500/5 transition-colors flex items-center gap-2"
                  >
                    <i className="fas fa-trash-alt"></i>
                    계정 초기화
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      <BuyStockModal
        isOpen={buyModalOpen}
        onClose={() => setBuyModalOpen(false)}
        stock={selectedStock}
        onBuy={handleBuySubmit}
      />
      <SellStockModal
        isOpen={sellModalOpen}
        onClose={() => setSellModalOpen(false)}
        stock={selectedStock}
        onSell={handleSellSubmit}
      />
      <ConfirmationModal
        isOpen={resetModalOpen}
        title="모의투자 초기화"
        message={`정말로 초기화하시겠습니까?\n모든 거래 내역과 자산이 삭제되며, 이 작업은 되돌릴 수 없습니다.`}
        onConfirm={handleResetConfirm}
        onCancel={() => setResetModalOpen(false)}
        confirmText="초기화"
        cancelText="취소"
      />
    </>
  );
}
