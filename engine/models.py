from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, date

class Grade(Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class SignalStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

@dataclass
class StockData:
    code: str
    name: str
    market: str
    sector: Optional[str] = None
    close: float = 0
    change_pct: float = 0
    trading_value: float = 0
    volume: int = 0
    marcap: int = 0
    high_52w: float = 0
    low_52w: float = 0

@dataclass
class ChartData:
    opens: List[float] = field(default_factory=list)
    highs: List[float] = field(default_factory=list)
    lows: List[float] = field(default_factory=list)
    closes: List[float] = field(default_factory=list)
    volumes: List[int] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)

@dataclass
class SupplyData:
    foreign_buy_5d: int = 0
    inst_buy_5d: int = 0
    retail_buy_5d: int = 0
    # Additional fields if needed by other components, but scorer only uses these

@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published_at: Optional[datetime] = None
    weight: float = 1.0
    summary: str = ""

@dataclass
class ScoreDetail:
    total: float = 0
    news: int = 0
    volume: int = 0
    chart: int = 0
    candle: int = 0
    timing: int = 0
    supply: int = 0
    llm_reason: str = ""
    ai_evaluation: Optional[Dict] = None

@dataclass
class ChecklistDetail:
    has_news: bool = False
    is_new_high: bool = False
    is_breakout: bool = False
    ma_aligned: bool = False
    supply_positive: bool = False
    news_sources: List[str] = field(default_factory=list)

@dataclass
class Signal:
    stock_code: str
    stock_name: str
    market: str
    sector: str
    signal_date: date
    signal_time: datetime
    grade: Grade
    score: ScoreDetail
    checklist: ChecklistDetail
    news_items: List[Dict] 
    current_price: float
    change_pct: float
    entry_price: float
    stop_price: float
    target_price: float
    r_value: float
    position_size: int
    quantity: int
    r_multiplier: float
    trading_value: float
    volume_ratio: float
    status: SignalStatus
    created_at: datetime
    score_details: Dict
    themes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.grade, Enum):
            d['grade'] = self.grade.value
        if isinstance(self.status, Enum):
            d['status'] = self.status.value
            
        # Serialize Date/Time objects
        for key, value in d.items():
            if isinstance(value, (date, datetime)):
                d[key] = value.isoformat()
                
        # Handle nested lists/dicts if necessary (e.g. news_items)
        if 'news_items' in d and isinstance(d['news_items'], list):
            new_news = []
            for item in d['news_items']:
                if isinstance(item, dict):
                    new_item = item.copy()
                    if 'published_at' in new_item and isinstance(new_item['published_at'], (date, datetime)):
                        new_item['published_at'] = new_item['published_at'].isoformat()
                    new_news.append(new_item)
            d['news_items'] = new_news
            
        return d

@dataclass
class ScreenerResult:
    date: date
    total_candidates: int
    filtered_count: int
    scanned_count: int  # 전체 스캔 종목 수
    signals: List[Signal]
    by_grade: Dict[str, int]
    by_market: Dict[str, int]
    processing_time_ms: float
    market_status: Dict[str, Any]
    market_summary: str
    trending_themes: List[str]

