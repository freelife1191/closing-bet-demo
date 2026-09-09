'use client';

import { Activity, useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { isAuthenticationError, paperTradingAPI, PaperTradingPortfolio, PaperTradingHolding } from '@/lib/api';
import { useAccountActionGuard } from '@/lib/accountActionGuard';
import { ModalShell } from './Modal';
import { formatSmartPercent } from './paperTradingFormat';
import PaperTradingAssetChart from './PaperTradingAssetChart';
import { DepositPanel, ResetAccountButton } from './PaperTradingAccountActions';
import BuyStockModal from './BuyStockModal';
import SellStockModal from './SellStockModal';
import StockTradeHistoryModal from './StockTradeHistoryModal';

interface PaperTradingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type PaperTradingTabId = 'overview' | 'holdings' | 'history' | 'chart';

interface PaperTradingHistoryEntry {
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

interface SelectedStock {
  ticker: string;
  name: string;
  price: number;
  avg_price: number;
  current_price?: number;
  quantity: number;
}

// fetchAPI 가 4xx 응답의 본문을 error.data 에 담아 준다. 그쪽을 먼저 읽어야
// 사용자에게 `API Error: 400` 대신 서버가 적어 보낸 사유를 보여 줄 수 있다.
const tradeErrorMessage = (error: unknown): string => {
  if (typeof error !== 'object' || error === null) return '알 수 없는 오류';
  const apiError = error as { status?: unknown; data?: { message?: unknown }; message?: unknown };
  if (apiError.status === 401) return '모의투자는 로그인 후 사용할 수 있습니다.';
  if (typeof apiError.data?.message === 'string') return apiError.data.message;
  return typeof apiError.message === 'string' ? apiError.message : '알 수 없는 오류';
};

export default function PaperTradingModal({ isOpen, onClose }: PaperTradingModalProps) {
  const { data: session, status } = useSession();
  const accountEmail = status === 'authenticated' ? session?.user?.email ?? null : null;
  return (
    <PaperTradingModalAccount
      key={accountEmail ?? 'unauthenticated'}
      isOpen={isOpen}
      onClose={onClose}
      isAuthenticated={Boolean(accountEmail)}
    />
  );
}

interface PaperTradingModalAccountProps extends PaperTradingModalProps {
  isAuthenticated: boolean;
}

function PaperTradingModalAccount({
  isOpen,
  onClose,
  isAuthenticated,
}: PaperTradingModalAccountProps) {
  const captureAccountAction = useAccountActionGuard(null);
  const [activeTab, setActiveTab] = useState<PaperTradingTabId>('overview');
  const [portfolio, setPortfolio] = useState<PaperTradingPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // 거래 내역 state
  const [tradeHistory, setTradeHistory] = useState<PaperTradingHistoryEntry[]>([]);


  // Modals state
  const [buyModalOpen, setBuyModalOpen] = useState(false);
  const [sellModalOpen, setSellModalOpen] = useState(false);
  const [selectedStock, setSelectedStock] = useState<SelectedStock | null>(null); // 매수/매도용 선택된 종목
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyStock, setHistoryStock] = useState<{ ticker: string; name: string } | null>(null);
  const tabs: { id: PaperTradingTabId; label: string; icon: string }[] = [
    { id: 'overview', label: '자산 개요', icon: 'fa-wallet' },
    { id: 'holdings', label: '보유 종목', icon: 'fa-list' },
    { id: 'chart', label: '수익 차트', icon: 'fa-chart-area' },
    { id: 'history', label: '거래 내역', icon: 'fa-history' },
  ];

  const fetchPortfolio = async (isCancelled: () => boolean) => {
    // 스피너는 첫 조회에만 띄운다. 갱신 때마다 띄우면 콘텐츠 영역이 통째로 갈리면서
    // 그 안의 Activity 경계까지 언마운트되어, 차트 탭에서 입금했을 때 기간과
    // 이동평균선 선택이 사라진다.
    if (!portfolio) setLoading(true);
    try {
      const data = await paperTradingAPI.getPortfolio();
      if (!isCancelled()) setPortfolio(data);
    } catch (e) {
      if (!isCancelled()) {
        const denied = isAuthenticationError(e);
        setAccessDenied(denied);
        if (!denied) console.error("Failed to fetch portfolio", e);
      }
    } finally {
      if (!isCancelled()) setLoading(false);
    }
  };

  const fetchHistory = async (isCancelled: () => boolean) => {
    try {
      const data = await paperTradingAPI.getTradeHistory(50);
      if (!isCancelled() && data.trades) {
        setTradeHistory(data.trades);
      }
    } catch (e) {
      if (!isCancelled()) {
        const denied = isAuthenticationError(e);
        setAccessDenied(denied);
        if (!denied) console.error("Failed to fetch trade history", e);
      }
    }
  };


  useEffect(() => {
    let cancelled = false;
    setAccessDenied(false);

    if (!isOpen || !isAuthenticated) {
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    void fetchPortfolio(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [isOpen, isAuthenticated, refreshKey]);

  // 탭 변경 시 데이터 로드
  useEffect(() => {
    let cancelled = false;
    if (isOpen && isAuthenticated && activeTab === 'history') {
      void fetchHistory(() => cancelled);
    }
    return () => {
      cancelled = true;
    };
  }, [isOpen, isAuthenticated, activeTab, refreshKey]);


  // Handlers for Buy/Sell
  const openBuyModal = (stock: PaperTradingHolding) => {
    setSelectedStock({
      ticker: stock.ticker,
      name: stock.name,
      price: stock.current_price || stock.avg_price,
      avg_price: stock.avg_price,
      quantity: stock.quantity,
      current_price: stock.current_price // BuyStockModal expects this
    });
    setBuyModalOpen(true);
  };

  const openHistoryModal = (stock: PaperTradingHolding) => {
    setHistoryStock({ ticker: stock.ticker, name: stock.name });
    setHistoryModalOpen(true);
  };

  const openSellModal = (stock: PaperTradingHolding) => {
    setSelectedStock({
      ticker: stock.ticker,
      name: stock.name,
      price: stock.current_price || stock.avg_price,
      avg_price: stock.avg_price,
      current_price: stock.current_price,
      quantity: stock.quantity
    });
    setSellModalOpen(true);
  };

  const handleBuySubmit = async (ticker: string, name: string, price: number, quantity: number) => {
    const isCurrent = captureAccountAction();
    try {
      // 잔고 부족 같은 거절은 예외가 아니라 HTTP 200 + {status:'error'} 로 온다.
      const result = await paperTradingAPI.buy({ ticker, name, price, quantity });
      if (!isCurrent()) return false;
      if (result?.status === 'error') {
        alert(`매수 실패: ${result.message}`);
        return false;
      }
      alert(`${name} ${quantity}주 매수 완료`);
      setRefreshKey(p => p + 1);
      return true;
    } catch (e: any) {
      if (!isCurrent()) return false;
      alert(`매수 실패: ${tradeErrorMessage(e)}`);
      return false;
    }
  };

  const handleSellSubmit = async (ticker: string, name: string, price: number, quantity: number) => {
    const isCurrent = captureAccountAction();
    try {
      const result = await paperTradingAPI.sell({ ticker, price, quantity });
      if (!isCurrent()) return false;
      if (result?.status === 'error') {
        alert(`매도 실패: ${result.message}`);
        return false;
      }
      alert(`${name} ${quantity}주 매도 완료`);
      setRefreshKey(p => p + 1);
      return true;
    } catch (e: any) {
      if (!isCurrent()) return false;
      alert(`매도 실패: ${tradeErrorMessage(e)}`);
      return false;
    }
  };


  if (!isOpen) return null;

  return (
    <>
      <ModalShell
        onClose={onClose}
        labelledBy="paper-trading-modal-title"
        overlayClassName="z-[110] p-4"
        className="relative bg-[#1c1c1e] w-full max-w-6xl max-h-[90vh] rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200"
      >

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between p-4 md:p-5 border-b border-white/10 bg-[#252529] gap-4 md:gap-0 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 md:w-12 md:h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 flex-shrink-0">
              <i className="fas fa-chart-line text-white text-lg md:text-xl"></i>
            </div>
            <div>
              <h2 id="paper-trading-modal-title" className="text-lg md:text-xl font-bold text-white whitespace-nowrap">모의투자 포트폴리오</h2>
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
                  <DepositPanel
                    cash={portfolio.cash}
                    captureAccountAction={captureAccountAction}
                    onDeposited={() => setRefreshKey(p => p + 1)}
                  />
              </div>
            )}
            <button onClick={onClose} className="hidden md:flex w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 items-center justify-center text-gray-400 hover:text-white transition-colors">
              <i className="fas fa-times"></i>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-white/10 bg-[#1c1c1e] overflow-x-auto no-scrollbar flex-shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
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
        <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-[#18181b] relative">
          {!isAuthenticated || accessDenied ? (
            <div className="flex h-full items-center justify-center text-center text-gray-300">
              모의투자는 로그인 후 사용할 수 있습니다.
            </div>
          ) : loading ? (
            <div className="flex h-full items-center justify-center">
              <i className="fas fa-spinner fa-spin text-3xl text-rose-500"></i>
            </div>
          ) : !portfolio ? (
            <div className="text-center text-gray-500 mt-20">데이터를 불러올 수 없습니다.</div>
          ) : (
            <>
              {/* Overview Tab */}
              {activeTab === 'overview' && (() => {
                // 백엔드는 이제 사전 반올림 없는 float를 내려주므로 그대로 사용하고,
                // 누락/비유한 값일 때만 total_profit/total_principal 로컬 계산으로 폴백한다.
                const principal = Number(portfolio.total_principal ?? 0);
                const profitAbs = Number(portfolio.total_profit ?? 0);
                const fallbackRate = principal > 0 ? (profitAbs / principal) * 100 : 0;
                const backendRate = portfolio.total_profit_rate;
                const displayRate = typeof backendRate === 'number' && Number.isFinite(backendRate)
                  ? backendRate
                  : fallbackRate;

                const totalAssetValue = Number(portfolio.total_asset_value || 0);
                const stockValue = Number(portfolio.total_stock_value || 0);
                const cashValue = Number(portfolio.cash || 0);
                const stockPct = totalAssetValue > 0 ? (stockValue / totalAssetValue) * 100 : 0;
                const cashPct = totalAssetValue > 0 ? (cashValue / totalAssetValue) * 100 : 0;
                // 막대 시각화는 0.5% 미만이라도 보이도록 최소 폭을 보장한다(값이 0인 경우는 제외).
                const stockBarWidth = stockValue > 0 ? Math.max(stockPct, 0.8) : 0;
                const cashBarWidth = cashValue > 0 ? Math.max(cashPct, 0.8) : 0;

                return (
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
                            * 총 수익률 = (총 평가 자산 - 총 원금) / 총 원금<br />
                            * 총 원금 = 초기 자본금(1억) + 총 입금액<br />
                            (보유 현금 비중이 높으면 개별 종목 수익률보다 낮을 수 있습니다.)
                          </div>
                        </div>
                      </div>
                      <div className={`text-3xl md:text-4xl font-bold mb-2 tracking-tight ${profitAbs >= 0 ? 'text-rose-400' : 'text-blue-400'}`}>
                        {profitAbs > 0 ? '+' : ''}{profitAbs.toLocaleString()}원
                      </div>
                      <div className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${displayRate >= 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-blue-500/10 text-blue-400'}`}>
                        <i className={`fas fa-caret-${displayRate >= 0 ? 'up' : 'down'}`}></i>
                        {displayRate > 0 ? '+' : ''}{formatSmartPercent(displayRate, 2)}%
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
                            <span className="text-white font-bold">{formatSmartPercent(stockPct, 1)}%</span>
                          </div>
                          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                            <div className="h-full bg-rose-500" style={{ width: `${Math.min(stockBarWidth, 100)}%` }}></div>
                          </div>
                          <div className="text-[10px] text-gray-500 mt-1 text-right">{Math.floor(stockValue).toLocaleString()}원</div>
                        </div>
                        <div className="flex-1">
                          <div className="flex justify-between text-xs mb-1 whitespace-nowrap gap-2">
                            <span className="text-gray-300">현금</span>
                            <span className="text-white font-bold">{formatSmartPercent(cashPct, 1)}%</span>
                          </div>
                          <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500" style={{ width: `${Math.min(cashBarWidth, 100)}%` }}></div>
                          </div>
                          <div className="text-[10px] text-gray-500 mt-1 text-right">{Math.floor(cashValue).toLocaleString()}원</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                );
              })()}

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
                          {portfolio.holdings.map((stock) => {
                            // current_price가 0/undefined일 때만 평단가 fallback (단, 0은 비정상이므로 평단가로 대체).
                            const currentPrice = stock.current_price && stock.current_price > 0
                              ? stock.current_price
                              : stock.avg_price;
                            // market_value가 백엔드에서 내려오면 그대로 쓰고, 없으면 즉석 계산.
                            const marketValue = typeof stock.market_value === 'number'
                              ? stock.market_value
                              : Math.floor(currentPrice * stock.quantity);
                            // 손익은 가능한 한 백엔드 값을 사용하되, 누락 시 평단가/현재가/수량으로 직접 계산.
                            const profitLoss = typeof stock.profit_loss === 'number'
                              ? stock.profit_loss
                              : Math.round((currentPrice - stock.avg_price) * stock.quantity);
                            const profitRate = typeof stock.profit_rate === 'number'
                              ? stock.profit_rate
                              : (stock.avg_price > 0 ? ((currentPrice - stock.avg_price) / stock.avg_price) * 100 : 0);
                            const isPlus = profitRate >= 0;

                            return (
                            <tr
                              key={stock.ticker}
                              className="hover:bg-white/5 transition-colors group cursor-pointer"
                              onClick={() => openHistoryModal(stock)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  openHistoryModal(stock);
                                }
                              }}
                              title="클릭하여 거래 내역 보기"
                            >
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center gap-3">
                                  <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-xs font-bold text-gray-400 group-hover:text-white group-hover:bg-white/10 transition-colors">
                                    {stock.ticker.slice(0, 2)}
                                  </div>
                                  <div>
                                    <div className="text-sm font-bold text-white flex items-center gap-2">
                                      {stock.name}
                                      <i className="fas fa-receipt text-[10px] text-gray-600 group-hover:text-rose-400 transition-colors"></i>
                                    </div>
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
                                <div className="flex items-center justify-end gap-1">
                                  {currentPrice.toLocaleString()}원
                                  {stock.is_stale && (
                                    <div className="group/stale relative">
                                      <i className="fas fa-exclamation-triangle text-amber-500 text-[10px] cursor-help"></i>
                                      <div className="absolute right-0 bottom-full mb-1 w-32 bg-gray-800 text-[10px] text-gray-300 p-1.5 rounded border border-white/10 shadow-lg hidden group-hover/stale:block z-50 text-center">
                                        현재가 지연됨<br />(매수평단가 표시 중)
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-bold text-white">
                                {marketValue.toLocaleString()}원
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right">
                                <div className={`text-sm font-bold ${isPlus ? 'text-rose-400' : 'text-blue-400'}`}>
                                  {profitRate > 0 ? '+' : ''}{formatSmartPercent(profitRate, 2)}%
                                </div>
                                <div className={`text-xs ${isPlus ? 'text-rose-500/70' : 'text-blue-500/70'}`}>
                                  {profitLoss > 0 ? '+' : ''}{profitLoss.toLocaleString()}원
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-center">
                                <div className="flex items-center justify-center gap-2">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openBuyModal(stock);
                                    }}
                                    className="px-3 py-1.5 rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white text-xs font-bold transition-colors"
                                  >
                                    매수
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openSellModal(stock);
                                    }}
                                    className="px-3 py-1.5 rounded bg-rose-500/10 text-rose-400 hover:bg-rose-500 hover:text-white text-xs font-bold transition-colors"
                                  >
                                    매도
                                  </button>
                                </div>
                              </td>
                            </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {portfolio.holdings.length === 0 && (
                      <div className="px-6 py-12 text-center text-gray-500">
                        보유 중인 종목이 없습니다.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Chart Tab. Activity 로 감싸면 탭을 벗어나도 컴포넌트가 살아남아
                  기간과 이동평균선 선택이 유지된다. 숨은 동안에는 effect 가 정리되므로
                  차트 인스턴스를 붙들고 있지도 않는다. */}
              <Activity mode={activeTab === 'chart' ? 'visible' : 'hidden'}>
                <PaperTradingAssetChart
                  refreshKey={refreshKey}
                  fallbackTotalAsset={Number(portfolio.total_asset_value ?? 100000000)}
                  fallbackCash={Number(portfolio.cash ?? portfolio.total_asset_value ?? 100000000)}
                  principalBase={Number(portfolio.total_principal ?? 100000000)}
                />
              </Activity>

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
                      </tbody>
                    </table></div>
                    {tradeHistory.length === 0 && (
                      <div className="px-6 py-12 text-center text-gray-500">
                        거래 내역이 없습니다.
                      </div>
                    )}
                  </div>
                </div>
              )}

              <ResetAccountButton
                captureAccountAction={captureAccountAction}
                onReset={() => { setRefreshKey(p => p + 1); setActiveTab('overview'); }}
              />
            </>
          )}
        </div>
      </ModalShell>

      {/* Modals */}
      <BuyStockModal
        isOpen={isAuthenticated && !accessDenied && buyModalOpen}
        onClose={() => setBuyModalOpen(false)}
        stock={selectedStock}
        onBuy={handleBuySubmit}
      />
      <SellStockModal
        isOpen={isAuthenticated && !accessDenied && sellModalOpen}
        onClose={() => setSellModalOpen(false)}
        stock={selectedStock}
        onSell={handleSellSubmit}
      />
      <StockTradeHistoryModal
        isOpen={isAuthenticated && !accessDenied && historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
        stock={historyStock}
      />
    </>
  );
}
