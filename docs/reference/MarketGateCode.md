

## config.py (kr_market_package/config.py)
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Configuration
국장 분석 시스템 설정 - 외인/기관 수급 기반
"""
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Tuple
from enum import Enum


class MarketRegime(Enum):
    """시장 상태"""
    KR_BULLISH = "강세장"      # KOSPI > 20MA > 60MA, 외인 순매수
    KR_NEUTRAL = "중립"        # 혼조세
    KR_BEARISH = "약세장"      # KOSPI < 20MA, 외인 순매도

class SignalType(Enum):
    """진입 시그널 유형"""
    FOREIGNER_BUY = "외인매수"     # 외국인 5일 연속 순매수
    INST_SCOOP = "기관매집"        # 기관 10일 순매수 + 거래량 급증
    DOUBLE_BUY = "쌍끌이"          # 외인 + 기관 동시 매수


@dataclass
class TrendThresholds:
    """수급 트렌드 판단 기준"""
    # 외국인 (Foreign)
    foreign_strong_buy: int = 5_000_000     # 강매수 (5백만주)
    foreign_buy: int = 2_000_000            # 매수 (2백만주)
    foreign_neutral: int = -1_000_000       # 중립
    foreign_sell: int = -2_000_000          # 매도
    foreign_strong_sell: int = -5_000_000   # 강매도
    
    # 기관 (Institutional)
    inst_strong_buy: int = 3_000_000        # 강매수 (3백만주)
    inst_buy: int = 1_000_000               # 매수 (1백만주)
    inst_neutral: int = -500_000            # 중립
    inst_sell: int = -1_000_000             # 매도
    inst_strong_sell: int = -3_000_000      # 강매도
    
    # 비율 기준
    high_ratio_foreign: float = 12.0        # 외국인 고비율
    high_ratio_inst: float = 8.0            # 기관 고비율


@dataclass 
class MarketGateConfig:
    """Market Gate 설정 - 시장 진입 조건"""
    # 환율 기준 (USD/KRW)
    usd_krw_safe: float = 1350.0            # 안전 (초록)
    usd_krw_warning: float = 1400.0         # 주의 (노랑)
    usd_krw_danger: float = 1450.0          # 위험 (빨강)
    
    # KOSPI 기준
    kospi_ma_short: int = 20                # 단기 이평
    kospi_ma_long: int = 60                 # 장기 이평
    
    # 외인 수급 기준
    foreign_net_buy_threshold: int = 500_000_000_000  # 5000억원 순매수


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    # === 진입 조건 ===
    entry_trigger: Literal["FOREIGNER_BUY", "INST_SCOOP", "DOUBLE_BUY"] = "DOUBLE_BUY"
    
    # 최소 점수/등급
    min_score: int = 60                     # 최소 수급 점수 (0-100)
    min_consecutive_days: int = 3           # 최소 연속 매수일
    
    # === 청산 조건 ===
    stop_loss_pct: float = 5.0              # 손절 (%)
    take_profit_pct: float = 15.0           # 익절 (%)
    trailing_stop_pct: float = 5.0          # 트레일링 스탑 (고점 대비 %)
    max_hold_days: int = 15                 # 최대 보유 기간 (일)
    
    # RSI 기반 청산
    rsi_exit_threshold: int = 70            # RSI 70 도달 시 절반 익절
    
    # 외인 청산 조건
    exit_on_foreign_sell: bool = True       # 외인 순매도 전환 시 청산
    foreign_sell_days: int = 2              # N일 연속 순매도 시
    
    # === Market Regime ===
    allowed_regimes: List[str] = field(default_factory=lambda: ["KR_BULLISH", "KR_NEUTRAL"])
    use_usd_krw_gate: bool = True           # 환율 게이트 사용
    
    # === 자금 관리 ===
    initial_capital: float = 100_000_000    # 초기 자본 (1억원)
    position_size_pct: float = 10.0         # 포지션 크기 (자본의 %)
    max_positions: int = 10                 # 최대 동시 보유 종목
    
    # === 수수료/슬리피지 ===
    commission_pct: float = 0.015           # 거래 수수료 (0.015%)
    slippage_pct: float = 0.1               # 슬리피지 (0.1%)
    tax_pct: float = 0.23                   # 세금 (매도 시 0.23%)
    
    def get_total_cost_pct(self) -> float:
        """총 거래 비용 (왕복)"""
        return (self.commission_pct * 2) + self.slippage_pct + self.tax_pct
    
    def should_trade_in_regime(self, regime: str) -> bool:
        """해당 시장 상태에서 거래 가능 여부"""
        return regime in self.allowed_regimes
    
    @classmethod
    def conservative(cls) -> "BacktestConfig":
        """보수적 설정 - 안정적 수익 추구"""
        return cls(
            entry_trigger="DOUBLE_BUY",
            min_score=70,
            min_consecutive_days=5,
            stop_loss_pct=3.0,
            take_profit_pct=10.0,
            trailing_stop_pct=4.0,
            max_hold_days=10,
            exit_on_foreign_sell=True,
            foreign_sell_days=1,
            position_size_pct=5.0,
            max_positions=5
        )
    
    @classmethod
    def aggressive(cls) -> "BacktestConfig":
        """공격적 설정 - 고수익 추구"""
        return cls(
            entry_trigger="FOREIGNER_BUY",
            min_score=50,
            min_consecutive_days=3,
            stop_loss_pct=7.0,
            take_profit_pct=25.0,
            trailing_stop_pct=6.0,
            max_hold_days=20,
            exit_on_foreign_sell=False,
            position_size_pct=15.0,
            max_positions=15
        )


@dataclass
class ScreenerConfig:
    """스크리너 설정"""
    # 데이터 소스
    data_source: Literal["naver", "krx", "both"] = "naver"
    
    # 분석 기간
    lookback_days: int = 60                 # 분석 기간 (일)
    
    # 점수 가중치
    weight_foreign: float = 0.40            # 외국인 수급 (40%)
    weight_inst: float = 0.30               # 기관 수급 (30%)
    weight_technical: float = 0.20          # 기술적 분석 (20%)
    weight_fundamental: float = 0.10        # 펀더멘털 (10%)
    
    # Top N
    top_n: int = 20                         # 상위 N개 종목 선정
    
    # 필터
    min_market_cap: int = 100_000_000_000   # 최소 시총 (1000억)
    min_avg_volume: int = 100_000           # 최소 평균 거래량
    exclude_admin: bool = True              # 관리종목 제외
    exclude_etf: bool = True                # ETF 제외


# === 상수 정의 ===
KOSPI_TICKER = "^KS11"
KOSDAQ_TICKER = "^KQ11"
USD_KRW_TICKER = "KRW=X"

# 섹터 분류 (GICS 기준)
SECTORS = {
    "반도체": ["005930", "000660", "042700"],    # 삼성전자, SK하이닉스, 한미반도체
    "2차전지": ["373220", "006400", "003670"],   # LG엔솔, 삼성SDI, 포스코퓨처엠
    "자동차": ["005380", "000270", "012330"],    # 현대차, 기아, 현대모비스
    "헬스케어": ["207940", "068270", "000100"],  # 삼성바이오, 셀트리온, 유한양행
    "IT": ["035420", "035720", "018260"],        # NAVER, 카카오, 삼성SDS
    "은행": ["105560", "055550", "086790"],      # KB금융, 신한지주, 하나금융지주
    "철강": ["005490", "004020", "010130"],      # POSCO홀딩스, 현대제철, 고려아연
    "증권": ["006800", "016360", "005940"],      # 미래에셋증권, 삼성증권, NH투자증권
    "조선": ["329180", "009540", "010140"],      # HD현대중공업, HD한국조선해양, 삼성중공업 (추가)
    "에너지": ["096770", "010950", "034020"],    # SK이노베이션, S-Oil, 두산에너빌리티 (추가)
}
```


### models.py (kr_market_package/models.py)
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - Data Models
국장 분석 시스템 데이터 모델
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class StockInfo:
    """종목 기본 정보"""
    ticker: str
    name: str
    market: str                         # KOSPI / KOSDAQ
    sector: Optional[str] = None
    market_cap: Optional[int] = None    # 시가총액
    is_etf: bool = False
    is_admin: bool = False              # 관리종목


@dataclass
class InstitutionalFlow:
    """기관/외국인 수급 데이터"""
    ticker: str
    date: str
    
    # 외국인 순매매
    foreign_net_buy: int = 0            # 주수
    foreign_net_buy_amount: int = 0     # 금액 (원)
    foreign_holding_pct: float = 0.0    # 보유 비율 (%)
    
    # 기관 순매매  
    inst_net_buy: int = 0
    inst_net_buy_amount: int = 0
    
    # 개인 순매매
    retail_net_buy: int = 0
    retail_net_buy_amount: int = 0
    
    # 거래량
    volume: int = 0
    close_price: float = 0.0


@dataclass
class TrendAnalysis:
    """수급 트렌드 분석 결과"""
    ticker: str
    analysis_date: str
    
    # 기간별 외국인 순매매
    foreign_net_60d: int = 0
    foreign_net_20d: int = 0
    foreign_net_10d: int = 0
    foreign_net_5d: int = 0
    
    # 기간별 기관 순매매
    inst_net_60d: int = 0
    inst_net_20d: int = 0
    inst_net_10d: int = 0
    inst_net_5d: int = 0
    
    # 거래량 대비 비율
    foreign_ratio_20d: float = 0.0
    inst_ratio_20d: float = 0.0
    
    # 연속 매수일
    foreign_consecutive_buy_days: int = 0
    inst_consecutive_buy_days: int = 0
    
    # 트렌드 판단
    foreign_trend: str = "neutral"      # strong_buying, buying, neutral, selling, strong_selling
    inst_trend: str = "neutral"
    
    # 종합 점수 (0-100)
    supply_demand_score: float = 50.0
    supply_demand_stage: str = "중립"   # 강한매집, 매집, 약매집, 중립, 약분산, 분산, 강한분산
    
    # 매집 신호
    is_double_buy: bool = False         # 쌍끌이
    accumulation_intensity: str = "보통"
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Signal:
    """매수/매도 시그널"""
    ticker: str
    name: str
    signal_type: str                    # FOREIGNER_BUY, INST_SCOOP, DOUBLE_BUY
    signal_time: int                    # Unix timestamp
    
    # 시그널 강도
    score: int                          # 0-100
    grade: str                          # A, B, C, D
    
    # 가격 정보
    price: float
    pivot_high: Optional[float] = None  # 돌파 기준점
    
    # 수급 정보
    foreign_net_5d: int = 0
    inst_net_5d: int = 0
    consecutive_days: int = 0
    
    # 시장 상태
    market_regime: str = "KR_NEUTRAL"
    usd_krw: float = 0.0
    
    # 기술적 지표
    rsi: Optional[float] = None
    ma_alignment: Optional[str] = None  # 정배열, 역배열, 혼조
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Trade:
    """개별 거래 기록"""
    ticker: str
    name: str
    
    # 진입
    entry_time: int                     # Unix timestamp
    entry_price: float
    entry_type: str                     # FOREIGNER_BUY, INST_SCOOP, DOUBLE_BUY
    entry_score: int
    
    # 청산 (진행 중이면 None)
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None   # STOP_LOSS, TAKE_PROFIT, TRAILING_STOP, TIME_EXIT, FOREIGN_SELL, RSI_EXIT
    
    # 포지션 정보
    quantity: int = 0
    position_value: float = 0.0
    stop_loss: float = 0.0
    take_profit: Optional[float] = None
    
    # 수급 정보 (진입 시점)
    foreign_net_5d: int = 0
    inst_net_5d: int = 0
    
    # 시장 상태
    market_regime: str = "KR_NEUTRAL"
    
    @property
    def is_closed(self) -> bool:
        return self.exit_price is not None
    
    @property
    def return_pct(self) -> float:
        if not self.is_closed:
            return 0.0
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100
    
    @property
    def pnl(self) -> float:
        """손익 금액"""
        if not self.is_closed:
            return 0.0
        return (self.exit_price - self.entry_price) * self.quantity
    
    @property
    def r_multiple(self) -> float:
        """리스크 대비 수익 (R-Multiple)"""
        if not self.is_closed or self.stop_loss == 0:
            return 0.0
        risk = self.entry_price - self.stop_loss
        if risk <= 0:
            return 0.0
        reward = self.exit_price - self.entry_price
        return reward / risk
    
    @property
    def is_winner(self) -> bool:
        return self.return_pct > 0
    
    @property
    def holding_days(self) -> int:
        if not self.is_closed:
            return 0
        return (self.exit_time - self.entry_time) // 86400
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['is_closed'] = self.is_closed
        d['return_pct'] = self.return_pct
        d['pnl'] = self.pnl
        d['r_multiple'] = self.r_multiple
        d['is_winner'] = self.is_winner
        d['holding_days'] = self.holding_days
        return d


@dataclass
class BacktestResult:
    """백테스트 결과"""
    # 설정
    config_name: str
    start_date: str
    end_date: str
    
    # 거래 통계
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    
    # 수익률
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    avg_winner_pct: float = 0.0
    avg_loser_pct: float = 0.0
    
    # R-Multiple
    avg_r_multiple: float = 0.0
    total_r: float = 0.0
    
    # 리스크 지표
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    
    # 벤치마크 비교
    kospi_return_pct: float = 0.0
    kosdaq_return_pct: float = 0.0
    alpha: float = 0.0                  # KOSPI 대비 초과수익
    
    # 자금
    initial_capital: float = 0.0
    final_capital: float = 0.0
    
    # 기간 통계
    avg_holding_days: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # 시그널별 통계
    signal_stats: Dict = field(default_factory=dict)
    
    # 상세 데이터
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)  # [(timestamp, equity), ...]
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['trades'] = [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.trades]
        return d


@dataclass
class MarketStatus:
    """현재 시장 상태"""
    timestamp: int
    
    # 지수
    kospi: float = 0.0
    kospi_change_pct: float = 0.0
    kosdaq: float = 0.0
    kosdaq_change_pct: float = 0.0
    
    # 환율
    usd_krw: float = 0.0
    usd_krw_change_pct: float = 0.0
    
    # 외인/기관 당일 순매매 (전체)
    foreign_net_total: int = 0          # 금액 (억원)
    inst_net_total: int = 0
    retail_net_total: int = 0
    
    # 시장 상태
    regime: str = "KR_NEUTRAL"
    regime_score: float = 50.0          # 0-100 (100이면 매우 강세)
    
    # 게이트 상태
    is_gate_open: bool = True
    gate_reason: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
```

---

## frontend/src/app/dashboard/kr/page.tsx (kr_market_package/frontend/src/app/dashboard/kr/page.tsx)
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