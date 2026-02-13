// API utility functions

const API_BASE = '';  // Empty = use Next.js proxy

interface FetchOptions extends RequestInit {
  timeout?: number;
}

/**
 * AbortController를 사용하여 타임아웃 기능이 있는 fetch 래퍼
 */
function createTimeoutFetch(timeoutMs: number = 10000): {
  controller: AbortController;
  cleanup: () => void;
} {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const cleanup = () => clearTimeout(timeoutId);

  return { controller, cleanup };
}

/**
 * API 호출을 위한 공통 fetch 함수 (GET)
 * - 타임아웃 처리 포함
 * - 에러 핸들링 표준화
 */
export async function fetchAPI<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { controller, cleanup } = createTimeoutFetch(options.timeout ?? 10000);

  try {
    const fetchOptions: RequestInit = {
      ...options,
      signal: controller.signal
    };

    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (!response.ok) {
      const error: any = new Error(`API Error: ${response.status}`);
      error.status = response.status;
      try {
        error.data = await response.json();
      } catch { /* ignore */ }
      throw error;
    }
    return response.json();
  } catch (e: any) {
    if (e.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw e;
  } finally {
    cleanup();
  }
}

/**
 * POST 요청을 위한 공통 fetch 함수
 * - 타임아웃 처리 포함
 * - JSON 직렬화 자동 처리
 * - 에러 핸들링 표준화
 */
export async function fetchPostAPI<T>(
  endpoint: string,
  data: any,
  options: { timeout?: number; headers?: Record<string, string> } = {}
): Promise<T> {
  const { timeout = 30000, headers = {} } = options; // POST는 기본 30초
  const { controller, cleanup } = createTimeoutFetch(timeout);

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
      signal: controller.signal,
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const error: any = new Error(`API Error: ${response.status}`);
      error.status = response.status;
      try {
        error.data = await response.json();
      } catch { /* ignore */ }
      throw error;
    }
    return response.json();
  } catch (e: any) {
    if (e.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw e;
  } finally {
    cleanup();
  }
}

// KR Market API Types
export interface KRSignal {
  ticker: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ';
  signal_date: string;
  entry_price: number;
  target_price?: number;
  stop_price?: number;
  current_price: number;
  return_pct: number;
  foreign_5d: number;
  inst_5d: number;
  score: number;
  contraction_ratio: number;
  gpt_recommendation?: AIRecommendation;
  perplexity_recommendation?: AIRecommendation;
  gemini_recommendation?: AIRecommendation;
  news?: NewsItem[];
}

export interface KRSignalsResponse {
  signals: KRSignal[];
  total_scanned?: number;
  error?: string;
  source?: string;
}

export interface KRMarketGate {
  score: number;
  label: string;
  status: string; // GREEN, YELLOW, RED, GRAY
  kospi_close: number;
  kospi_change_pct: number;
  kosdaq_close: number;
  kosdaq_change_pct: number;
  commodities?: {
    krx_gold: { value: number; change_pct: number };
    krx_silver: { value: number; change_pct: number };
    us_gold?: { value: number; change_pct: number };
    us_silver?: { value: number; change_pct: number };
  };
  indices?: {
    sp500: { value: number; change_pct: number };
    nasdaq: { value: number; change_pct: number };
  };
  crypto?: {
    btc: { value: number; change_pct: number };
    eth: { value: number; change_pct: number };
    xrp: { value: number; change_pct: number };
  };
  sectors: KRSector[];
  message?: string;
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

export interface NewsItem {
  title: string;
  url: string;
  source?: string;
  summary?: string;
}

export interface KRAIAnalysis {
  signals: Array<{
    ticker: string;
    gpt_recommendation?: AIRecommendation;
    perplexity_recommendation?: AIRecommendation;
    gemini_recommendation?: AIRecommendation;
    news?: NewsItem[];
  }>;
  market_indices?: {
    kospi?: { value: number; change_pct: number };
    kosdaq?: { value: number; change_pct: number };
  };
  generated_at?: string;
}


export interface DataStatus {
  last_update: string | null;
  collected_stocks: number;
  signals_count: number;
  market_status: string;
  files: Record<string, { exists: boolean; updated_at?: string; size?: number }>;
}

// Chart Types
export interface KRChartData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KRChartResponse {
  ticker: string;
  data: KRChartData[];
  message?: string;
}

// KR Market API functions
export const krAPI = {
  getSignals: (date?: string) => fetchAPI<KRSignalsResponse>(`/api/kr/signals?_t=${Date.now()}${date ? `&date=${date}` : ''}`),
  getSignalDates: () => fetchAPI<string[]>('/api/kr/signals/dates'),
  getMarketGate: (date?: string) => fetchAPI<KRMarketGate>(`/api/kr/market-gate?_t=${Date.now()}${date ? `&date=${date}` : ''}`),
  getAIAnalysis: (date?: string) => fetchAPI<KRAIAnalysis>(`/api/kr/ai-analysis?_t=${Date.now()}${date ? `&date=${date}` : ''}`),
  getDataStatus: () => fetchAPI<{ status: string; data: DataStatus }>('/api/kr/status'),
  getStockChart: (ticker: string, period?: string) => fetchAPI<KRChartResponse>(`/api/kr/stock-chart/${ticker}${period ? `?period=${period}` : ''}`),
  getHistoryDates: () => fetchAPI<{ dates: string[] }>('/api/kr/ai-history-dates'),
  getHistory: (date: string) => fetchAPI<KRAIAnalysis>(`/api/kr/ai-history/${date}`),

  // 스크리너 실행 (Closing Bet)
  runScreener: (capital = 50_000_000, markets = ['KOSPI', 'KOSDAQ'], target_date?: string) =>
    fetchPostAPI<any>('/api/kr/jongga-v2/run', { capital, markets, target_date }, { timeout: 60000 }),

  // VCP 스크리너 실행 (VCP Signals + AI)
  runVCPScreener: async (target_date?: string, max_stocks = 50) => {
    try {
      return await fetchPostAPI<any>('/api/kr/signals/run', { target_date, max_stocks }, { timeout: 60000 });
    } catch (e: any) {
      // Preserve 409 status error message
      if (e.message.includes('409') || e.status === 409) {
        throw new Error('이미 분석이 진행 중입니다.');
      }
      throw e;
    }
  },

  getVCPStatus: () => fetchAPI<{ running: boolean; status: string; message: string; progress: number }>('/api/kr/signals/status'),

  // Market Gate 개별 업데이트
  updateMarketGate: (target_date?: string) =>
    fetchPostAPI<any>('/api/kr/market-gate/update', { target_date }, { timeout: 30000 }),
};

// Closing Bet API
export interface ExpertAdvice {
  trading_tip: string;
  selling_strategy: string;
  market_context: string;
}

export interface ScoreDetails {
  base: number;
  bonus: number;
  total: number;
  details: {
    volume_ratio?: number;
    rise_pct?: number;
    [key: string]: any;
  };
  foreign_net_buy?: number;
  inst_net_buy?: number;
}

export interface CandleData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ClosingBetCandidate {
  stock_code: string;
  stock_name: string;
  market: string;
  grade: 'S' | 'A' | 'B' | 'C';
  current_price: number;
  entry_price: number;
  stop_price: number;
  target_price: number;
  trading_value: number;
  change_pct: number;
  total_score: number;
  score_details?: ScoreDetails;
  advice?: ExpertAdvice;
  mini_chart?: CandleData[];

  // Legacy support
  score: {
    total: number;
    llm_reason: string;
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
  getCandidates: (limit = 25, date?: string) =>
    fetchAPI<ClosingBetResponse>(`/api/kr/closing-bet/candidates?limit=${limit}${date ? `&date=${date}` : ''}`),
  getTiming: () => fetchAPI<ClosingBetTiming>('/api/kr/closing-bet/timing'),
  getBacktestStats: () => fetchAPI<any>('/api/kr/closing-bet/backtest-stats'),
};

// 모의투자 API Types
export interface PaperTradingHolding {
  ticker: string;
  name: string;
  avg_price: number;
  quantity: number;
  total_cost: number;
  current_price?: number;
  market_value?: number;
  profit_loss?: number;
  profit_rate?: number;
  return_pct?: number;
  is_stale?: boolean;
}

export interface PaperTradingPortfolio {
  holdings: PaperTradingHolding[];
  cash: number;
  total_asset_value: number;
  total_stock_value?: number;
  total_profit?: number;
  total_profit_rate?: number;
  total_principal?: number;
}

export interface PaperTradingAssetHistory {
  date: string;
  total_asset: number;
  cash: number;
  stock_value: number;
}

export interface TradeLogEntry {
  id: number;
  action: 'BUY' | 'SELL';
  ticker: string;
  name: string;
  price: number;
  quantity: number;
  timestamp: string;
}

export interface BuyRequest {
  ticker: string;
  name: string;
  price: number;
  quantity: number;
}

export interface SellRequest {
  ticker: string;
  price: number;
  quantity: number;
}

export interface TradeResponse {
  status: 'success' | 'error';
  message: string;
}

// 모의투자 API
export const paperTradingAPI = {
  getPortfolio: () => fetchAPI<PaperTradingPortfolio>('/api/portfolio'),

  buy: (data: BuyRequest) => fetchPostAPI<TradeResponse>('/api/portfolio/buy', data),

  sell: (data: SellRequest) => fetchPostAPI<TradeResponse>('/api/portfolio/sell', data),

  reset: () => fetchPostAPI<any>('/api/portfolio/reset', {}),

  deposit: (amount: number) => fetchPostAPI<any>('/api/portfolio/deposit', { amount }),

  getTradeHistory: (limit = 50) => fetchAPI<any>(`/api/portfolio/history?limit=${limit}`),

  getAssetHistory: (limit = 30) => fetchAPI<any>(`/api/portfolio/history/asset?limit=${limit}`)
};
