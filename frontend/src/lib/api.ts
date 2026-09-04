// API utility functions

const API_BASE = '';  // Empty = use Next.js proxy

interface FetchOptions extends RequestInit {
  timeout?: number;
}

export async function fetchAPI<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options.timeout ?? 10000; // 기본 10초, 옵션으로 변경 가능
  const id = setTimeout(() => controller.abort(), timeoutMs);

  try {
    // 옵션 병합 (signal 우선순위 고려)
    const fetchOptions: RequestInit = {
      ...options,
      signal: controller.signal
    };

    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);
    clearTimeout(id);

    if (!response.ok) {
      // 백엔드는 실패 사유를 `message` 나 `error` 중 한 자리에 적어 보낸다. 그 문구를
      // Error.message 로 올려야 호출부가 `e.message` 를 그대로 화면에 띄울 수 있다.
      // 여기서 올리지 않으면 사유를 꺼내는 코드를 호출부마다 따로 두게 된다.
      let data: any;
      try {
        data = await response.json();
      } catch (e) { /* 본문이 JSON 이 아니면 상태 코드만 가지고 간다 */ }

      const error: any = new Error(
        data?.message || data?.error || `API Error: ${response.status}`
      );
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return response.json();
  } catch (e: any) {
    if (e.name === 'AbortError') {
      throw new Error('Request timed out');
    }
    throw e;
  } finally {
    // fetch 자체가 거부하면(백엔드 다운, DNS 실패) 위의 clearTimeout 에 닿지 못한다.
    // 그대로 두면 타이머가 만료 시각까지 남는다. 폴링이 도는 화면에서는 계속 쌓인다.
    clearTimeout(id);
  }
}

// KR Market API Types
export interface KRSignal {
  ticker: string;
  name: string;
  market: 'KOSPI' | 'KOSDAQ';
  signal_date: string;
  entry_price: number;
  current_price: number;
  /** 진입가 기준 목표가. 진입가가 없으면 백엔드가 비워 둔다. */
  target_price?: number | null;
  /** 진입가 기준 손절가. 진입가가 없으면 백엔드가 비워 둔다. */
  stop_price?: number | null;
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
  generated_at?: string;
  error?: string;
  source?: string;
  /** 오늘 기준 시그널이 없을 때 백엔드가 내려주는 안내 문구 */
  stale_warning?: string;
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
    gold?: { value: number; change_pct: number };
    silver?: { value: number; change_pct: number };
    krx_gold?: { value: number; change_pct: number };
    krx_silver?: { value: number; change_pct: number };
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

export interface VCPStatus {
  running: boolean;
  status?: string;
  message: string;
  progress: number;
  task_type?: 'screener' | 'reanalysis_failed_ai' | null;
  cancel_requested?: boolean;
  last_run?: string | null;
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
  // end 를 주면 그 날짜까지의 구간을 돌려준다. 과거 시그널을 열었을 때 시그널이 발생한
  // 캔들이 차트 범위 밖으로 밀려나지 않게 하려는 것이다.
  getStockChart: (ticker: string, period?: string, end?: string) => fetchAPI<KRChartResponse>(`/api/kr/stock-chart/${ticker}?period=${period || '3m'}${end ? `&end=${end}` : ''}`),
  getHistoryDates: () => fetchAPI<{ dates: string[] }>('/api/kr/ai-history-dates'),
  getHistory: (date: string) => fetchAPI<KRAIAnalysis>(`/api/kr/ai-history/${date}`),

  // VCP 스크리너 실행 (VCP Signals + AI)
  runVCPScreener: (target_date?: string, max_stocks = 50) =>
    fetchAPI<any>('/api/kr/signals/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_date, max_stocks }),
      // 이 엔드포인트의 409 만 사유를 영어("Already running")로 답한다. 화면이 예외의
      // message 를 그대로 띄우므로 여기서 한국어로 바꾼다.
    }).catch((e: any) => {
      if (e?.status === 409) throw new Error('이미 분석이 진행 중입니다.');
      throw e;
    }),

  // VCP 실패 AI 재분석 (옵션: provider 강제 재분석).
  // background 를 거짓으로 보내면 백엔드가 요청 스레드에서 LLM 을 돌려 분 단위로 걸린다.
  // 그런 호출자가 없으므로 참으로 고정한다. 인자로 열어 두면 10초에 끊기는 길이 생긴다.
  reanalyzeVCPFailedAI: (target_date?: string, force_provider?: 'gemini' | 'second') =>
    fetchAPI<any>('/api/kr/signals/reanalyze-failed-ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_date, background: true, force_provider }),
    }),

  stopVCPFailedAIReanalysis: () =>
    fetchAPI<any>('/api/kr/signals/reanalyze-failed-ai/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  getVCPStatus: () =>
    fetchAPI<VCPStatus>(`/api/kr/signals/status?_t=${Date.now()}`, {
      cache: 'no-store',
      timeout: 30000,
    }),

  // Market Gate 개별 업데이트.
  // 수급 수집과 Market Gate 분석을 백엔드가 동기로 돌리므로 기본 10초로는 모자란다.
  // gunicorn 이 워커를 120초에 끊으니(`--timeout 120`) 그보다 오래 기다릴 이유도 없다.
  updateMarketGate: (target_date?: string) =>
    fetchAPI<any>('/api/kr/market-gate/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_date }),
      timeout: 120000,
    }),
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

  // 주문은 fetchAPI 를 거쳐야 타임아웃과 4xx 응답이 예외로 올라온다. 다만 백엔드는
  // 잔고 부족 같은 거절을 HTTP 200 + {status:'error'} 로 돌려주므로, 호출부에서
  // 응답 본문의 status 를 한 번 더 확인해야 실패가 드러난다.
  buy: (data: BuyRequest): Promise<TradeResponse> =>
    fetchAPI<TradeResponse>('/api/portfolio/buy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  sell: (data: SellRequest): Promise<TradeResponse> =>
    fetchAPI<TradeResponse>('/api/portfolio/sell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  reset: () => fetchAPI<any>('/api/portfolio/reset', { method: 'POST' }),

  deposit: (amount: number) =>
    fetchAPI<any>('/api/portfolio/deposit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ amount }),
    }),

  getTradeHistory: (limit = 50, ticker?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (ticker) params.set('ticker', ticker);
    return fetchAPI<any>(`/api/portfolio/history?${params.toString()}`);
  },

  // days = 기간 필터(최근 N일). 백엔드에서 기간에 맞는 자산 히스토리를 잘라서 반환한다.
  getAssetHistory: (days = 365) =>
    fetchAPI<any>(`/api/portfolio/history/asset?days=${days}`),
};
