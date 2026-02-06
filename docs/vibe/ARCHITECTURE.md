# 아키텍처 (Architecture)

## 개요 (Overview)

이 프로젝트는 AI 기반 한국 주식 시장 분석 시스템으로, 규제 기반 스크리닝과 AI 추론을 결합하여 스마트머니(Smart Money) 추적 및 VCP(Volatility Contraction Pattern) 패턴 분석을 수행합니다.

- **백엔드**: Python 3.10+ / Flask
- **프론트엔드**: Next.js 14 (App Router) / React / TypeScript
- **AI 엔진**: Gemini 2.0 Flash, GPT (Z.ai), Perplexity
- **데이터 소스**: pykrx, yfinance, 네이버/다음 뉴스 크롤링

---

## 시스템 구조 (System Structure)

```
closing-bet-demo/
├── app/                      # Flask 애플리케이션
│   ├── __init__.py           # 앱 팩토리 및 미들웨어
│   └── routes/              # API 라우트 (Blueprint)
│       ├── __init__.py
│       ├── kr_market.py       # 한국 시장 API 라우트
│       └── common.py          # 공통 라우트
│
├── engine/                    # 핵심 엔진 모듈
│   ├── config.py            # 엔진 설정 (LLM 공급자 등)
│   ├── models.py            # 데이터 모델 (dataclass)
│   ├── screener.py          # 스크리너 로직
│   ├── scorer.py            # 점수 산정 로직
│   ├── generator.py         # 시그널 생성
│   ├── collectors.py         # 데이터 수집
│   ├── llm_analyzer.py       # LLM 분석 (공통)
│   ├── kr_ai_analyzer.py    # 한국 시장 AI 분석
│   ├── vcp_ai_analyzer.py    # VCP AI 분석 (멀티 모델)
│   ├── market_gate.py       # 마켓 게이트 (시장 상태 판단)
│   ├── messenger.py          # 알림 메시지 생성
│   ├── position_sizer.py    # 포지션 사이징
│   └── signal_tracker.py     # 시그널 추적
│
├── services/                 # 서비스 레이어
│   ├── __init__.py
│   ├── scheduler.py          # 백그라운드 스케줄러
│   ├── notifier.py           # 멀티 채널 알림
│   ├── paper_trading.py      # 모의투자 시스템
│   └── usage_tracker.py      # 사용량 추적
│
├── chatbot/                  # 챗봇 모듈
│   ├── __init__.py
│   ├── core.py               # 챗봇 코어
│   └── prompts.py            # AI 프롬프트
│
├── scripts/                  # 유틸리티 스크립트
│   ├── init_data.py          # 데이터 초기화
│   ├── run_full_update.py   # 전체 업데이트
│   └── debug_*.py           # 디버깅 스크립트들
│
├── tests/                    # 테스트 (pytest)
│   ├── test_vcp.py
│   ├── test_jongga.py
│   └── ...
│
├── frontend/                 # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/     # 리액트 컴포넌트
│   │   │   ├── dashboard/kr/ # 한국 시장 대시보드
│   │   │   └── ...
│   │   │   └── lib/            # API 유틸리티, 타입
│   │   ├── layout.tsx          # 루트 레이아웃
│   │   └── page.tsx           # 랜딩 페이지
│   ├── package.json
│   └── next.config.js
│
├── data/                     # 데이터 저장소 (CSV/JSON)
│   ├── daily_prices.csv
│   ├── signals_log.csv
│   ├── market_gate.json
│   └── ...
│
├── logs/                     # 로그 파일
│   └── app.log
│
├── config.py                # 애플리케이션 설정 (dataclass)
├── flask_app.py            # Flask 진입점
├── run.py                   # 대화형 메뉴 진입점
├── requirements.txt         # Python 의존성
└── .env                     # 환경 변수
```

---

## 핵심 컴포넌트 (Core Components)

### 1. 백엔드 레이어 (Backend Layers)

#### 1.1 데이터 레이어 (Data Layer)
- **`engine/collectors.py`**: pykrx, yfinance API를 통해 주가, 거래량, 수급 데이터 수집
- **`data/` 디렉토리**: CSV/JSON 형태의 플랫 파일 저장소

#### 1.2 엔진 레이어 (Engine Layer)
- **`engine/screener.py`**: 기술적 필터링 (거래대금, 거래량, 등락률 등)
- **`engine/scorer.py`**: 종합 점수 산정 (뉴스, 거래대금, 차트, 수급)
- **`engine/market_gate.py`**: 시장 상태 판단 (강세/약세/중립, 매수 허용/차단)
- **`engine/generator.py`**: 시그널 생성 및 등급 부여 (S/A/B/C/D)

#### 1.3 AI 레이어 (AI Layer)
- **`engine/llm_analyzer.py`**: LLM 공통 기능 (뉴스 감성 분석, 배치 분석)
- **`engine/kr_ai_analyzer.py`**: 한국 시장 종목 분석 (Gemini + GPT 크로스 밸리데이션)
- **`engine/vcp_ai_analyzer.py`**: VCP 패턴 종목의 멀티 AI 분석 (Gemini, GPT, Perplexity 병렬)

#### 1.4 API 레이어 (API Layer)
- **`app/routes/kr_market.py`**: 한국 시장 관련 API (`/api/kr/*`)
  - `/api/kr/signals` - VCP 시그널 조회
  - `/api/kr/market-gate` - 마켓 게이트 상태
  - `/api/kr/jongga-v2/*` - 종가베팅 v2 관련
  - `/api/kr/stock-chart/<ticker>` - 종목 차트 데이터
  - `/api/kr/realtime-prices` - 실시간 가격 조회 (POST)
- **`app/routes/common.py`**: 공통 API (`/api/*`)

#### 1.5 서비스 레이어 (Service Layer)
- **`services/scheduler.py`**: APScheduler 기반 백그라운드 태스크 (15:20, 15:40 KST)
- **`services/notifier.py`**: Telegram, Discord, Slack, Email 다중 채널 알림
- **`services/paper_trading.py`**: 모의투자 시스템 (매수/매도, 포트폴리오, 수익 차트)

### 2. 프론트엔드 레이어 (Frontend Layers)

#### 2.1 페이지 레이어 (Page Layer)
- **`/dashboard/kr`**: 한국 시장 메인 대시보드 (Market Gate, VCP 시그널, 글로벌 지수)
- **`/dashboard/kr/vcp`**: VCP 시그널 상세 페이지
- **`/dashboard/kr/closing-bet`**: 종가베팅 페이지
- **`/dashboard/data-status`**: 데이터 상태 페이지
- **`/chatbot`**: AI 챗봇 페이지

#### 2.2 컴포넌트 레이어 (Component Layer)
- **`Header.tsx`**: 헤더 (네비게이션)
- **`Sidebar.tsx`**: 사이드바 (메뉴)
- **`ChatWidget.tsx`**: 챗봇 위젯
- **`SettingsModal.tsx`**: 설정 모달
- **`BuyStockModal.tsx`**: 모의투자 매수 모달
- **`SellStockModal.tsx`**: 모의투자 매도 모달
- **`PaperTradingModal.tsx`**: 모의투자 대시보드 모달

#### 2.3 API 클라이언트 (API Client Layer)
- **`src/lib/api.ts`**: 백엔드 API와 통신하는 타이핑된 API 클라이언트
  - `krAPI.getSignals()` - VCP 시그널 조회
  - `krAPI.getMarketGate()` - 마켓 게이트 조회
  - `krAPI.getStockChart()` - 종목 차트 데이터
  - `krAPI.runScreener()` - 스크리너 실행
  - `krAPI.runVCPScreener()` - VCP 스크리너 실행
  - `paperTradingAPI.*` - 모의투자 API

---

## 데이터 플로우 (Data Flow)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         데이터 수집 (Collection)                      │
│  pykrx (KRX)        │  yfinance (글로벌)           │
│  - 주가/거래량      │  - 지수/환율/원자재         │
│  - 외국인/기관 수급  │  - 크립토                  │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       데이터 처리 (Processing)                         │
│  1. 스크리닝 (Screener) - 규칙 기반 필터링                │
│     - 거래대금 500억 이상                                   │
│     - 거래량 200% 이상                                      │
│     - 전일 대비 등락률 2~15%                               │
│                                                                  │
│  2. 점수 산정 (Scorer) - 종합 점수 계산                   │
│     - 뉴스 호재 강도 (0~3점, AI 감성 분석)            │
│     - 거래대금 점수 (1~3점)                                │
│     - 차트 패턴 점수 (0~2점)                               │
│     - 수급 점수 (0~2점)                                     │
│                                                                  │
│  3. 마켓 게이트 (Market Gate) - 시장 상태 판단             │
│     - KODEX 200 추세 (정배열)                             │
│     - RSI (50~70)                                            │
│     - MACD 골든크로스                                         │
│     - USD/KRW 환율 (1450원 초과 시 DANGER)               │
│     - 외국인 선물 순매수                                     │
│     - 판정: GATE OPEN (60점 이상) / GATE CLOSED             │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI 분석 (AI Analysis)                           │
│  뉴스 크롤링 → 뉴스 감성 분석 (LLM Analyzer)             │
│                                                                  │
│  VCP 패턴 종목:                                             │
│  ├─ Gemini 분석 (심층 추론, 뉴스 맥락 이해)             │
│  ├─ GPT/Perplexity 분석 (크로스 밸리데이션)            │
│  └─ Consensus (일치 시 신뢰도 상향, 불일치 시 보수)   │
│                                                                  │
│  종가베팅 종목:                                               │
│  └─ AI 필터링 (악재 노출, 등급 산정)                      │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   시그널 생성 (Signal Generation)                     │
│  - 종합 점수 기반 등급 부여 (S/A/B/C/D)                   │
│  - 목표가/손절가 계산                                         │
│  - 시그널 저장 (signals_log.csv)                               │
│  - JSON 아카이브 생성 (날짜별)                               │
└───────────────────────────┬───────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  전송 및 표시 (Delivery & Display)                │
│  1. API (Flask) ←─── 2. 프론트엔드 (Next.js)              │
│                                                                  │
│  3. 알림 (Notifier)                                          │
│     - Telegram Bot                                               │
│     - Discord Webhook                                          │
│     - Slack Incoming Webhook                                   │
│     - Email (SMTP)                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 외부 서비스 통합 (External Service Integration)

### 1. 데이터 소스 (Data Sources)

| 소스            | 용도                                                  | 모듈                   |
| --------------- | ----------------------------------------------------- | ---------------------- |
| **pykrx**       | KRX 데이터 (KOSPI/KOSDAQ 종목, 지수, 수급)            | `engine/collectors.py` |
| **yfinance**    | 글로벌 데이터 (S&P 500, NASDAQ, 환율, 원자재, 크립토) | `engine/collectors.py` |
| **네이버 금융** | 종목 뉴스 크롤링                                      | `engine/collectors.py` |
| **다음 뉴스**   | 추가 뉴스 소스                                        | `engine/collectors.py` |

### 2. AI 서비스 (AI Services)

| AI 제공자           | 용도                                      | 사용 시나리오             | 모델                  |
| ------------------- | ----------------------------------------- | ------------------------- | --------------------- |
| **Google Gemini**   | 심층 추론, 뉴스 맥락 이해, 투자 가설 생성 | VCP 분석, 뉴스 감성, 챗봇 | `gemini-flash-latest` |
| **Z.ai (GPT 호환)** | 빠른 응답, 크로스 밸리데이션              | 챗봇, 배치 분석           | `gpt-4o`              |
| **Perplexity**      | 실시간 웹 검색, 최신 정보 반영            | 뉴스 검색, 팩트 체크      | `sonar-small-online`  |

### 3. 알림 서비스 (Notification Services)

| 채널         | 구현                               | 설정                                      |
| ------------ | ---------------------------------- | ----------------------------------------- |
| **Telegram** | Bot API (`sendMessage`, HTML 파싱) | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`  |
| **Discord**  | Webhook (Rich Embeds)              | `DISCORD_WEBHOOK_URL`                     |
| **Slack**    | Incoming Webhooks (Markdown)       | `SLACK_WEBHOOK_URL`                       |
| **Email**    | SMTP (HTML)                        | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` |

---

## 아키텍처 패턴 (Architecture Patterns)

### 1. Multi-Model AI Cross-Validation
- **목적**: 단일 모델의 편향성(bias) 완화, 신호 신뢰도 상승
- **구현**: Gemini와 GPT/Perplexity를 병렬로 실행하여 결과 교차 검증
- **검증 규칙**:
  - 일치(Agreement): 신뢰도 평균
  - 불일치(Disagreement): 더 높은 신뢰도 모델 선택 (동점 시 Gemini 우선)
  - 실패(Fallback): 한쪽 API 실패 시 다른 쪽 결과 사용

### 2. Async Batch Processing
- **목적**: API 호출 시간 최적화, Rate Limit 방지
- **구현**: `asyncio`와 `Semaphore`로 동시에 5~10개 종목 뉴스 분석
- **효과**: 순차 처리(2000초) → 병렬 처리(40초)로 50배 속도 향상

### 3. Market-First Approach
- **목적**: 하락장에서의 무분별한 매수 방지, 계좌 보호
- **구현**: 개별 종목 분석 전에 Market Gate(시장 신호등)가 시장 상태를 먼저 판단
- **결과**: 환율/지수/수급이 위험 수준일 경우, 아무리 좋은 종목도 매수 원천 차단(Gate Closed)

### 4. Persona-Based Prompting
- **목적**: AI 응답의 편차 최소화, 신뢰할 수 있는 조언 생성
- **구현**: 일관된 투자 철학(스마트머니봇)을 시스템 프롬프트에 탑재
- **페르소나**: "수급과 리스크 관리를 최우선으로 하는 냉철한 펀드매니저"

---

## 기술 스택 (Technology Stack)

### 백엔드 (Python)
- **Python**: 3.10+
- **Web Framework**: Flask (Blueprint 기반 모듈 라우팅)
- **데이터 처리**: Pandas, NumPy (벡터화 연산)
- **비동기 처리**: `asyncio`, `concurrent.futures`
- **AI SDK**: 
  - `google-genai` (Gemini)
  - `openai` (Z.ai 호환)
  - `perplexity` API
- **HTTP Client**: `requests`, `httpx`
- **스케줄링**: `APScheduler`, `threading`
- **로깅**: Python `logging` (rotation)

### 프론트엔드 (Next.js)
- **Framework**: Next.js 14 (App Router)
- **언어**: TypeScript, React 18
- **상태 관리**: Zustand
- **스타일링**: Tailwind CSS
- **아이콘**: React Icons, FontAwesome
- **차트**: Lightweight Charts
- **마크다운**: react-markdown, remark-gfm

### 데이터 스토리지 (Data Storage)
- **형태**: CSV/JSON (플랫 구조)
- **저장소**: `data/` 디렉토리
- **주요 파일**:
  - `daily_prices.csv` - 종가 데이터
  - `signals_log.csv` - 시그널 로그
  - `market_gate.json` - 마켓 게이트 상태
  - `kr_ai_analysis.json` - AI 분석 결과
  - `jongga_v2_latest.json` - 종가베팅 v2 최신 결과

---

## 동시성 및 성능 (Concurrency & Performance)

### 1. LLM 호출 병렬화
```python
# engine/vcp_ai_analyzer.py
import asyncio
from asyncio import Semaphore

# 최대 5개 동시 API 호출 제한
semaphore = Semaphore(5)

async def analyze_single_stock(item):
    async with semaphore:  # Rate Limit 방지
        # AI API 호출
        result = await llm.analyze(...)
        return result

# 병렬 실행
results = await asyncio.gather(*[analyze_single_stock(item) for item in items])
```

### 2. 데이터 캐싱
- API 응답 캐싱 (TTL 300초)
- 파일 시스템 기반 영구 캐싱 (CSV/JSON)

---

## 보안 및 인증 (Security & Authentication)

### 1. API Key 관리
- 환경 변수로 관리 (`.env` 파일)
- 사용자별 API Key 지원 (`X-Gemini-Key`, `X-User-Email` 헤더)
- 사용량 추적 (`services/usage_tracker.py`)

### 2. CORS 설정
- Render + Vercel 연동을 위해 구체적인 Origin 설정 또는 wildcard 사용
- `CORS(app, resources={r"/*": {"origins": cors_origins}})`

### 3. 에러 핸들링
- API 실패 시 로그 기록 후 다음 종목 진행
- Rate Limit (HTTP 429) 처리 - Exponential Backoff로 재시도

---

## 확장성 (Scalability)

### 1. 모듈화 아키텍처
- Blueprint 기반 라우팅으로 기능별 모듈화
- 엔진 모듈 독립적 설계로 새로운 전략 추가 용이
- 서비스 레이어 분리로 새로운 알림 채널 추가 용이

### 2. 비동기 처리
- 백그라운드 스레드로 장기 실행 작업 처리
- 사용자 요청 즉시 응답 후 비동기 작업 시작
- 상태 조회 API로 작업 진행률 확인

---

## 로깅 및 모니터링 (Logging & Monitoring)

### 1. 로그 파일
- **위치**: `logs/app.log`
- **포맷**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **로그 레벨**: INFO (설정 가능: `LOG_LEVEL`)

### 2. 중요 로그 이벤트
- 스크리너 실행 시작/완료
- AI API 호출 성공/실패
- 시그널 생성 완료 (종목 수, 등급 분포)
- 알림 발송 결과
- 예외 발생 및 스택 트레이스

---

## 트러블슈팅 (Troubleshooting)

### 1. 데이터 파일 누락
- 모든 데이터 파일이 존재하는지 확인
- 누락 시 빈 값 또는 기본값 반환

### 2. API 호출 실패
- 3회 재시도 (Exponential Backoff)
- 실패 시 로그 기록 후 다음 종목 진행
- 한쪽 API 실패 시 다른 쪽 결과 사용

### 3. 스케줄러 중복 실행
- 글로벌 플래그(`VCP_STATUS['running']`)로 중복 실행 방지
- 이미 실행 중이면 409 응답

---

## 개발 환경 설정 (Development Environment)

### 1. 환경 변수 (.env)
```bash
# 서버
FLASK_DEBUG=false
FLASK_PORT=5501
FLASK_HOST=0.0.0.0

# API Keys
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
PERPLEXITY_API_KEY=your_perplexity_key
ZAI_API_KEY=your_zai_key

# AI Models
GEMINI_MODEL=gemini-flash-latest
OPENAI_MODEL=gpt-4o

# VCP AI 설정
VCP_AI_PROVIDERS=gemini,gpt,perplexity
MARKET_GATE_UPDATE_INTERVAL_MINUTES=30

# 캐시
PRICE_CACHE_TTL=300
AI_CACHE_ENABLED=true

# Rate Limits
PYKRX_RATE_LIMIT=10
GEMINI_RATE_LIMIT=30
```

### 2. 실행 명령어
```bash
# 백엔드 시작
python flask_app.py

# 대화형 메뉴
python run.py

# 데이터 초기화
python scripts/init_data.py

# 전체 업데이트
python scripts/run_full_update.py

# 테스트 실행
pytest
pytest tests/test_vcp.py
```
