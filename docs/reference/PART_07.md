# PART 7 (Core Logic)

> [!WARNING]
> **Reference Only**: This document contains reference code and backups.
> The actual source of truth is located in the `app/` and `engine/` directories.
> Do not modify this file directly for production changes.

### blueprint/BLUEPRINT_01_OVERVIEW.md (kr_market_package/blueprint/BLUEPRINT_01_OVERVIEW.md)
```markdown
# KR Market AI Stock Analysis System - Blueprint Part 1: Overview

> **Version**: 1.0  
> **Last Updated**: 2026-01-03  
> **Author**: AI-Generated Blueprint  

---

## 1. Project Overview

### 1.1 What This System Does

This is a **Korean stock market analysis system** that combines:

1. **VCP (Volatility Contraction Pattern) Screening** - Mark Minervini's technical pattern detection
2. **Institutional Flow Analysis** - Foreign and institutional investor tracking
3. **Dual-AI Analysis** - GPT-5.2 and Gemini 3.0 cross-validation
4. **Real-time News Grounding** - Gemini's Google Search for latest news
5. **Automated Price Updates** - Background scheduler for live prices

### 1.2 Key Features

| Feature                 | Description                                                     |
| :---------------------- | :-------------------------------------------------------------- |
| **VCP Scanner**         | Detects volatility contraction patterns for breakout candidates |
| **Smart Money Tracker** | Tracks 5-day foreign/institutional net buying                   |
| **AI Recommendations**  | GPT + Gemini provide BUY/HOLD/SELL signals                      |
| **News Integration**    | Real-time news with AI-generated summaries                      |
| **Backtesting**         | Historical performance validation                               |
| **Live Dashboard**      | Web-based real-time monitoring                                  |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                    (Web Browser - dashboard.html)                   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FLASK SERVER                                │
│                        (flask_app.py)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ KR Market   │  │ US Market   │  │ Dividend    │                 │
│  │ APIs        │  │ APIs        │  │ APIs        │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   AI ANALYSIS       │ │   DATA SOURCES      │ │   BACKGROUND JOBS   │
│   (kr_ai_analyzer)  │ │   (pykrx, yfinance) │ │   (scheduler)       │
│                     │ │                     │ │                     │
│  - Gemini 3.0       │ │  - KRX (Korea)      │ │  - Price Updates    │
│  - GPT-5.2          │ │  - Yahoo Finance    │ │  - Signal Tracking  │
│  - News Grounding   │ │  - News APIs        │ │  - Daily Scans      │
└─────────────────────┘ └─────────────────────┘ └─────────────────────┘
```

### 2.2 Data Flow

```
1. User requests AI Analysis
           │
           ▼
2. Flask loads signals from signals_log.csv
           │
           ▼
3. For each signal (Top 10):
   ├── Fetch fundamentals (pykrx)
   ├── Fetch current price (pykrx)
   ├── Call Gemini (with Google Search grounding)
   │   └── Returns: recommendation + news summaries
   ├── Call GPT (with Gemini's news)
   │   └── Returns: recommendation
   └── Combine results
           │
           ▼
4. Save to kr_ai_analysis.json
           │
           ▼
5. Return JSON to frontend
```

---

## 3. File Structure

```
국내주식/
├── flask_app.py                 # Main Flask server (3,522 lines)
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (API keys)
│
├── templates/
│   ├── dashboard.html           # Main dashboard (5,923 lines)
│   └── index.html               # Landing page (723 lines)
│
├── kr_market/                   # Korean market module
│   ├── __init__.py              # Package init
│   ├── config.py                # Configuration classes (183 lines)
│   ├── kr_ai_analyzer.py        # AI analysis logic (397 lines)
│   ├── signal_tracker.py        # VCP signal tracking (358 lines)
│   ├── screener.py              # Stock screener (563 lines)
│   ├── scheduler.py             # Background jobs (384 lines)
│   ├── market_gate.py           # Market condition checker (300 lines)
│   ├── models.py                # Data models (286 lines)
│   │
│   ├── data/
│   │   ├── kr_ai_analysis.json  # AI analysis results (cached)
│   │   └── history/             # Historical analysis files
│   │
│   ├── scripts/
│   │   └── create_complete_daily_prices.py  # Daily price data generator
│   │
│   ├── daily_prices.csv                     # 📌 2년치 일봉 데이터 (120MB+)
│   ├── all_institutional_trend_data.csv     # 📌 수급 데이터 (기관/외인 순매매)
│   ├── signals_log.csv                      # Active VCP signals
│   ├── korean_stocks_list.csv               # Korean stock ticker database
│   └── backtest_results.csv                 # Backtest output
│
└── us_market/                   # US market module (separate)
    └── ...
```

---

## 4. Dependencies

### 4.1 requirements.txt

```txt
# Web Framework
flask
gunicorn

# Data & Finance
yfinance
pandas
numpy
pykrx

# AI/LLM
google-generativeai
openai

# Utilities
requests
tqdm
python-dotenv
beautifulsoup46
lxml_html_clean

# Visualization
plotly
```

### 4.2 System Requirements

- **Python**: 3.11+
- **OS**: macOS / Linux / Windows
- **RAM**: 4GB+ recommended
- **Storage**: 1GB for data files

---

## 5. Environment Variables

### 5.1 .env File Template

```bash
# === AI API Keys ===
GOOGLE_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# === Optional: News APIs ===
# NAVER_CLIENT_ID=your_naver_client_id       # Deprecated
# NAVER_CLIENT_SECRET=your_naver_secret      # Deprecated

# === Server Config ===
FLASK_DEBUG=true
FLASK_PORT=5501
```

### 5.2 Getting API Keys

| Service              | URL                                  | Purpose        |
| :------------------- | :----------------------------------- | :------------- |
| **Google AI Studio** | https://aistudio.google.com/apikey   | Gemini 3.0 API |
| **OpenAI**           | https://platform.openai.com/api-keys | GPT-5.2 API    |

---

## 6. Data Schemas

### 6.1 signals_log.csv (VCP Signals)

```csv
ticker,name,signal_date,entry_price,status,score,contraction_ratio,foreign_5d,inst_5d
005930,삼성전자,2025-12-29,72000,OPEN,82.5,0.45,1500000,800000
000270,기아,2025-12-29,119800,OPEN,75.0,0.52,420000,350000
```

| Column              | Type   | Description                              |
| :------------------ | :----- | :--------------------------------------- |
| `ticker`            | string | 6-digit stock code (zero-padded)         |
| `name`              | string | Company name                             |
| `signal_date`       | date   | VCP signal detection date                |
| `entry_price`       | float  | Recommended entry price                  |
| `status`            | enum   | OPEN / CLOSED                            |
| `score`             | float  | VCP score (0-100)                        |
| `contraction_ratio` | float  | Volatility contraction (0-1)             |
| `foreign_5d`        | int    | Foreign net buy (5-day cumulative)       |
| `inst_5d`           | int    | Institutional net buy (5-day cumulative) |

### 6.2 kr_ai_analysis.json (AI Results)

```json
{
  "market_indices": {
    "kospi": { "value": 4281.47, "change_pct": 1.6 },
    "kosdaq": { "value": 940.43, "change_pct": 1.62 }
  },
  "signals": [
    {
      "ticker": "123410",
      "name": "코리아에프티",
      "score": 82.5,
      "contraction_ratio": 0.41,
      "foreign_5d": 1036584,
      "inst_5d": 223456,
      "entry_price": 8240,
      "current_price": 8180,
      "return_pct": -0.73,
      "fundamentals": {
        "per": "6.49",
        "pbr": "1.05",
        "roe": "16.18%",
        "eps": "1,269원",
        "bps": "7,705원",
        "div_yield": "1.85%",
        "marcap": "2,255억원"
      },
      "news": [
        {
          "title": "코리아에프티, HEV 열풍 타고 '1조 클럽' 진입 초읽기",
          "summary": "하이브리드용 캐니스터 ASP가 내연기관 대비 2배 이상...",
          "url": "https://example.com/news/1"
        }
      ],
      "gpt_recommendation": {
        "action": "BUY",
        "confidence": 84,
        "reason": "VCP 점수와 외국인 순매수세, 실적 호조..."
      },
      "gemini_recommendation": {
        "action": "BUY",
        "confidence": 92,
        "reason": "HEV 시장 성장 수혜 및 저평가..."
      }
    }
  ],
  "generated_at": "2026-01-02T13:52:31.311951",
  "signal_date": "2025-12-29"
}
```

---

## 7. Quick Start Guide

### 7.1 Installation

```bash
# 1. Clone or create project directory
mkdir 국내주식
cd 국내주식

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install flask gunicorn yfinance pandas numpy pykrx
pip install google-generativeai openai
pip install requests tqdm python-dotenv beautifulsoup4 plotly

# 4. Create .env file
cat > .env << 'EOF'
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
FLASK_DEBUG=true
FLASK_PORT=5501
EOF

# 5. Create directory structure
mkdir -p kr_market/data templates
```

### 7.2 Running the Server

```bash
# Development mode
python flask_app.py

# Production mode (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5501 flask_app:app
```

### 7.3 Accessing the Dashboard

Open browser: `http://localhost:5501/app`

---

## 8. API Endpoints Overview

### 8.1 KR Market APIs

| Method | Endpoint                           | Description                     |
| :----- | :--------------------------------- | :------------------------------ |
| GET    | `/api/kr/signals`                  | Get active VCP signals          |
| GET    | `/api/kr/ai-analysis`              | Get AI recommendations (cached) |
| GET    | `/api/kr/ai-analysis?refresh=true` | Force new AI analysis           |
| GET    | `/api/kr/vcp-scan`                 | Run VCP scanner                 |
| GET    | `/api/kr/backtest`                 | Get backtest results            |

### 8.2 Response Format

All APIs return JSON with consistent structure:

```json
{
  "status": "success",
  "data": { ... },
  "generated_at": "2026-01-03T10:00:00"
}
```

---

## 9. Configuration Reference

### 9.1 VCP Scoring Weights

```python
# From config.py
weight_foreign: float = 0.40    # Foreign flow (40%)
weight_inst: float = 0.30       # Institutional flow (30%)
weight_technical: float = 0.20  # Technical analysis (20%)
weight_fundamental: float = 0.10 # Fundamentals (10%)
```

### 9.2 Backtest Parameters

```python
@dataclass
class BacktestConfig:
    stop_loss_pct: float = 5.0       # Stop loss at -5%
    take_profit_pct: float = 15.0    # Take profit at +15%
    trailing_stop_pct: float = 5.0   # Trailing stop
    max_hold_days: int = 15          # Maximum holding period
    position_size_pct: float = 10.0  # 10% of capital per position
    max_positions: int = 10          # Maximum 10 concurrent positions
```

### 9.3 Signal Thresholds

```python
# Strong buy signals
foreign_strong_buy: int = 5_000_000  # 5M shares foreign net buy
inst_strong_buy: int = 3_000_000     # 3M shares institutional net buy

# VCP pattern requirements
min_score: int = 60                  # Minimum VCP score
max_contraction_ratio: float = 0.8   # Maximum volatility contraction
```

---

## 10. Troubleshooting

### 10.1 Common Issues

| Issue                           | Cause                               | Solution                                              |
| :------------------------------ | :---------------------------------- | :---------------------------------------------------- |
| `ModuleNotFoundError: pykrx`    | Missing dependency                  | `pip install pykrx`                                   |
| API returns empty data          | No signals in CSV                   | Run VCP scanner first                                 |
| Gemini timeout                  | Rate limiting                       | Wait 1 minute, retry                                  |
| Port 5501 in use                | Another process                     | Kill process or change port                           |
| `❌ 가격 데이터 파일이 없습니다` | daily_prices.csv 누락               | `python scripts/create_complete_daily_prices.py` 실행 |
| `❌ 수급 데이터 파일이 없습니다` | institutional data 누락             | `python all_institutional_trend_data.py` 실행         |
| `signal_tracker` 데이터 못 찾음 | 🔧 **경로 버그 (2026-01-03 수정됨)** | `os.path.dirname()` 제거 - data_dir 직접 사용         |

### 10.2 데이터 파일 생성 순서 (중요!)

시스템을 처음 실행할 때 아래 순서로 데이터를 생성해야 합니다:

```bash
cd kr_market

# 1. 주식 목록 생성 (pykrx 사용)
python scripts/create_kr_stock_list.py

# 2. 일별 가격 데이터 생성 (약 5분 소요)
python scripts/create_complete_daily_prices.py

# 3. 수급 데이터 수집 (약 5분 소요)
python all_institutional_trend_data.py

# 4. VCP 시그널 스캔
python signal_tracker.py

# 5. AI 분석 (Flask 서버에서 /api/kr/ai-analysis?refresh=true)
```

### 10.3 Log Locations

```
Console output:
  ⏰ KR Price Scheduler started (5min interval, 10s stagger)
  🔄 Updated price for 코리아에프티 (123410): 8180 (Wait 10s...)
  ✅ Using cached AI analysis for 2025-12-29
```

---

## Next Steps

Continue to **[BLUEPRINT_02_BACKEND_FLASK_CORE.md](./BLUEPRINT_02_BACKEND_FLASK_CORE.md)** for Flask server implementation details.
```

### README.md (kr_market_package/README.md)
```markdown
# KR Market Package - 기술 문서

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                         │
│                     (http://localhost:3500)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ VCP 시그널 │ │ 종가베팅  │ │ Market   │ │   Data Status    │   │
│  │  /vcp    │ │/closing  │ │  Gate    │ │   /data-status   │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
└───────┼────────────┼────────────┼────────────────┼─────────────┘
        │            │            │                │
        ▼            ▼            ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Flask API Backend                            │
│                    (http://localhost:5501)                       │
│                                                                  │
│  /api/kr/signals     /api/kr/jongga-v2    /api/kr/market-gate   │
│  /api/kr/ai-analysis /api/kr/backtest     /api/system/data-status│
└───────┬─────────────────────────┬────────────────────────────────┘
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────────────────────────────┐
│   Data Sources   │    │              AI Analysis                  │
│                  │    │                                          │
│  1. pykrx (KRX)  │    │  ┌─────────────┐ ┌─────────────────────┐ │
│  2. FinanceData  │    │  │   Gemini    │ │      OpenAI GPT     │ │
│     Reader       │    │  │   (필수)    │ │     (선택사항)      │ │
│  3. yfinance     │    │  └─────────────┘ └─────────────────────┘ │
│  4. 네이버 금융  │    └──────────────────────────────────────────┘
└──────────────────┘    

---

## 📊 분석 엔진 상세

### 1. VCP (Volatility Contraction Pattern) 분석

**파일**: `screener.py` → `SmartMoneyScreener.detect_vcp_pattern()`

```
VCP 감지 로직:
├── ATR(변동성) 점진적 감소 확인
├── 고가-저가 범위 축소 비율 계산
├── 현재가가 최근 고점 근처인지 확인
└── contraction_threshold: 0.7 (70% 이하 축소 시 VCP 인정)
```

**VCP 점수 (0-20점)**:
- 수축 비율 깊을수록 높은 점수
- 시간 조정 기간 적절할수록 가산점

---

### 2. 수급 분석 (Smart Money Tracking)

**파일**: `screener.py` → `SmartMoneyScreener._calculate_score()`

**분석 가중치 (총 100점)**:
| 항목               | 가중치 | 설명               |
| ------------------ | ------ | ------------------ |
| 외국인 순매매량    | 25점   | 5일/20일/60일 누적 |
| 외국인 연속 매수일 | 15점   | 연속 순매수 일수   |
| 기관 순매매량      | 20점   | 5일/20일/60일 누적 |
| 기관 연속 매수일   | 10점   | 연속 순매수 일수   |
| 거래량 대비 비율   | 20점   | 수급 강도          |
| VCP 패턴           | 10점   | 변동성 수축 패턴   |

**데이터 소스 우선순위**:
1. **pykrx** - KRX 공식 데이터
2. **FinanceDataReader** - 네이버 금융 크롤링
3. **yfinance** - Yahoo Finance API

---

### 3. 종가베팅 점수 시스템 (12점 만점)

**파일**: `engine/scorer.py` → `Scorer.calculate()`

| 항목          | 최대점수 | 분석 내용                        |
| ------------- | -------- | -------------------------------- |
| **뉴스/재료** | 3점      | LLM 기반 호재 분석 (키워드 폴백) |
| **거래대금**  | 3점      | 1조→3점, 5천억→2점, 1천억→1점    |
| **차트패턴**  | 2점      | 신고가 돌파 + 이평선 정배열      |
| **캔들형태**  | 1점      | 장대양봉, 윗꼬리 짧음            |
| **기간조정**  | 1점      | 횡보 후 돌파, 볼린저 수축        |
| **수급**      | 2점      | 외인+기관 동시 순매수            |

**등급 결정 기준**:
- **S급**: 10점+ & 거래대금 1조+
- **A급**: 8점+ & 거래대금 5천억+
- **B급**: 6점+ & 거래대금 1천억+
- **C급**: 그 외

---

### 4. AI 분석 (Dual LLM)

**파일**: `kr_ai_analyzer.py`, `engine/llm_analyzer.py`

#### Gemini 분석 (gemini-2.0-flash-exp)
```python
# 분석 항목:
- 뉴스 종합 분석 → 호재 점수 (0~3)
- 매매 추천 (BUY/HOLD/SELL)
- 투자 이유 요약
- 신뢰도 점수 (0~100)
```

#### GPT-4 분석 (gpt-4o)
```python
# 분석 항목:
- VCP 패턴 해석
- 수급 동향 분석
- 뉴스 기반 투자 의견
- 목표가/손절가 제안
```

#### 프롬프트 구조:
```
[시장 정보]
- KOSPI: {value} ({change}%)
- KOSDAQ: {value} ({change}%)

[종목 정보]
- 종목명: {name}
- VCP 점수: {score}
- 수축 비율: {contraction_ratio}
- 외국인 5일: {foreign_5d}
- 기관 5일: {inst_5d}

[최신 뉴스]
1. {news_title_1}
2. {news_title_2}
3. {news_title_3}

→ JSON 출력: {action, confidence, reason}
```

---

### 5. 뉴스 수집 시스템

**파일**: `engine/collectors.py` → `EnhancedNewsCollector`

**수집 소스**:
| 소스             | 방법               | 신뢰도 |
| ---------------- | ------------------ | ------ |
| 네이버 금융      | 종목별 뉴스 크롤링 | 0.9    |
| 네이버 뉴스 검색 | 키워드 검색        | 0.85   |
| 다음 뉴스        | 검색 크롤링        | 0.8    |

**주요 언론사 가중치**:
```python
MAJOR_SOURCES = {
    "한국경제": 0.9,
    "매일경제": 0.9,
    "머니투데이": 0.85,
    "서울경제": 0.85,
    "이데일리": 0.85,
    "연합뉴스": 0.85,
    "뉴스1": 0.8,
}
```

**뉴스 분석 흐름**:
```
네이버 금융 크롤링 → 본문 수집 → LLM 감성 분석 → 호재 점수 산출
```

---

### 6. Market Gate (시장 상태 분석)

**파일**: `market_gate.py` → `run_kr_market_gate()`

**분석 지표**:
| 지표          | 가중치 | 설명                 |
| ------------- | ------ | -------------------- |
| 추세 정렬     | 25점   | EMA20 > EMA60 정배열 |
| RSI           | 25점   | 50-70 구간 최적      |
| MACD          | 20점   | 골든크로스 여부      |
| 거래량        | 15점   | 20일 평균 대비       |
| 상대강도 (RS) | 15점   | KOSPI 대비 성과      |

**섹터 ETF 분석 (7개)**:
- KOSPI200 (069500.KS) - 벤치마크
- 반도체 (091160.KS)
- 2차전지 (305720.KS)
- 자동차 (091170.KS)
- IT (102780.KS)
- 은행 (102960.KS)
- 철강 (117680.KS)
- 증권 (102970.KS)

***주식 기술적 분석 시그널 판정 체계***

#### 1. 트렌드 정렬 (최대 25점)
| 조건                                | 점수  |
| :---------------------------------- | :---- |
| 현재가 > 20일 MA > 60일 MA (정배열) | +25점 |
| 현재가 > 20일 MA                    | +15점 |
| 현재가 > 60일 MA                    | +10점 |
| 모두 미충족 (하락추세)              | 0점   |

---

#### 2. RSI (최대 25점)
| RSI 범위 | 점수  | 해석             |
| :------- | :---- | :--------------- |
| 50 ~ 70  | +25점 | 상승 구간        |
| 40 ~ 50  | +15점 | 중립             |
| 30 ~ 40  | +20점 | 과매도 반등 기대 |
| < 30     | +10점 | 심한 과매도      |

---

#### 3. MACD (최대 20점)
| 조건                            | 점수  |
| :------------------------------ | :---- |
| MACD > Signal Line (골든크로스) | +20점 |
| MACD < Signal Line              | 0점   |

---

#### 4. 거래량 (최대 15점)
| 거래량 비율 (20일 평균 대비) | 점수  |
| :--------------------------- | :---- |
| > 1.2배 (활발)               | +15점 |
| 0.8 ~ 1.2배                  | +10점 |
| < 0.8배 (저조)               | 0점   |

---

#### 5. 상대강도 vs KOSPI (최대 15점)
| RS (20일 수익률 - KOSPI 수익률) | 점수  |
| :------------------------------ | :---- |
| > 2% (KOSPI 대비 아웃퍼폼)      | +15점 |
| 0 ~ 2%                          | +10점 |
| -2 ~ 0%                         | +5점  |
| < -2% (언더퍼폼)                | 0점   |

---

#### 🚦 시그널 판정 (최종 합계)
| 점수        | 시그널             |
| :---------- | :----------------- |
| **≥ 70**    | **Bullish (초록)** |
| **40 ~ 69** | **Neutral (노랑)** |
| **< 40**    | **Bearish (빨강)** |

---

## 📁 폴더 구조

```
kr_market_package/
├── flask_app.py              # Flask 서버 진입점
├── .env                      # API 키 설정
├── requirements.txt          # Python 의존성
│
├── engine/                   # 핵심 분석 엔진
│   ├── generator.py          # 종가베팅 V2 시그널 생성
│   ├── collectors.py         # 데이터 수집기 (pykrx, FDR, 뉴스)
│   ├── scorer.py             # 12점 점수 시스템
│   ├── llm_analyzer.py       # Gemini LLM 분석기
│   ├── position_sizer.py     # 자금 관리
│   ├── config.py             # 설정
│   └── models.py             # 데이터 모델
│
├── screener.py               # VCP + 수급 스크리너
├── kr_ai_analyzer.py         # Gemini + GPT 듀얼 AI 분석
├── market_gate.py            # 시장 상태 (섹터 분석)
│
├── app/routes/               # Flask API
│   ├── kr_market.py          # KR 시장 API
│   └── common.py             # 공통 API
│
├── data/                     # 생성된 데이터
│   ├── kr_ai_analysis.json   # AI 분석 결과
│   ├── jongga_v2_latest.json # 종가베팅 최신 결과
│   └── all_institutional_trend_data.csv
│
└── frontend/                 # Next.js 대시보드
    └── src/app/dashboard/
```

---

## ⚙️ 설치 및 실행

### 1단계: 환경 설정

```bash
cd kr_market_package

# Python 의존성 설치
pip install -r requirements.txt

# Node.js 의존성 설치
cd frontend && npm install && cd ..

# API 키 설정
nano .env
```

### 2단계: .env 파일 설정

```bash
# 필수: Gemini AI 분석
GEMINI_API_KEY=your_gemini_key

# 선택: GPT 추천 (없어도 작동)
OPENAI_API_KEY=your_openai_key

LOG_LEVEL=INFO
```

### 3단계: 서버 실행

**터미널 1 - Flask:**
```bash
python3 flask_app.py
# → http://localhost:5501
```

**터미널 2 - Next.js:**
```bash
cd frontend && npm run dev
# → http://localhost:3500
```

---

## 📱 API 발급 링크

| API        | 용도            | 발급 링크                                |
| ---------- | --------------- | ---------------------------------------- |
| **Gemini** | AI 분석 (필수)  | https://makersuite.google.com/app/apikey |
| **OpenAI** | GPT 추천 (선택) | https://platform.openai.com/api-keys     |

---

## 📞 문제 해결

### 데이터 수집 실패
```bash
# pykrx 폴백 확인
python3 -c "from pykrx import stock; print(stock.get_market_ohlcv('20240115'))"

# FDR 폴백 확인
python3 -c "import FinanceDataReader as fdr; print(fdr.DataReader('005930'))"
```

### AI 분석 실패
```bash
# API 키 확인
python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('GEMINI_API_KEY'))"
```
```

