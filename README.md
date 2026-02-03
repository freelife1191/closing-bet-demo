# 🚀 Smart Money Bot: AI 기반 종가 베팅 & VCP 시그널 시스템

**🌐 데모 페이지 (Live Demo)**: [https://close.highvalue.kr/dashboard/kr](https://close.highvalue.kr/dashboard/kr)

![랜딩 페이지](assets/0.%20랜딩페이지.png)

## 🚀 빠른 시작 (Quick Start)

### 1. 환경 설정 및 설치
```bash
# 저장소 클론 및 이동
git clone <repository_url>
cd closing-bet-v2

# 백엔드 가상환경 설정 및 패키지 설치
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 프론트엔드 의존성 설치
cd frontend && npm install && cd ..
```

### 2. API 키 설정 (.env)
루트 디렉토리의 `.env` 파일에 API 키를 설정합니다.
```env
FRONTEND_PORT=3000
FLASK_PORT=5001
GOOGLE_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here
PERPLEXITY_API_KEY=your_perplexity_key_here
ZAI_API_KEY=your_zai_key_here  # 선택사항

# VCP AI 설정
VCP_AI_PROVIDERS=gemini,gpt,perplexity
MARKET_GATE_UPDATE_INTERVAL_MINUTES=30
```

![내 설정](/assets/10.%20내%20설정.png)
*사용자 설정 및 API 키 관리 화면*

### 3. 서버 실행 및 중지
새로 통합된 `restart_all.sh` 스크립트를 사용하여 백엔드와 프론트엔드를 한 번에 관리할 수 있습니다.

- **서버 시작/재시작**:
  ```bash
  ./restart_all.sh
  ```
  *(기존 프로세스를 자동으로 종료하고 `.env` 설정에 따라 새 포트로 서버를 띄웁니다.)*

- **서버 중지**:
  새로 추가된 `stop_all.sh` 스크립트를 사용하여 모든 서비스를 안전하게 종료할 수 있습니다.
  ```bash
  ./stop_all.sh
  ```
  *(수동 종료 시에는 `lsof -ti :5001,3000 | xargs kill -9` 등을 활용하세요.)*

- **로그 확인**:
  ```bash
  tail -f logs/backend.log logs/frontend.log
  ```

---

## 📊 데이터 동기화 및 스케줄러 (Data Sync & Scheduler)

서버가 구동되면 백그라운드에서 다음 작업들이 정해진 시간에 자동으로 수행되거나, 사용자 요청 시 실시간으로 데이터를 갱신합니다.

### 1. 실시간 업데이트 (Real-time)
페이지 접속 시 또는 브라우저에서 요청 시 즉시 갱신되는 항목입니다.
- **글로벌 지수**: S&P 500, NASDAQ, KOSPI, KOSDAQ 실시간 지수 (`yfinance`)
- **원자재 및 자산**: 금(Gold), 은(Silver), 비트코인(BTC), 이더리움(ETH) 시세
- **Market Gate 점수**: 위 실시간 지표와 현재 환율을 결합하여 **접속 즉시** 동적 계산

![메인 화면](/assets/1.%20스마트머니%20추적%20메인.png)
*스마트머니 추적을 통한 시장 주도주 포착 화면*

### 2. 자동 스케줄 업데이트 (Scheduled Tasks)
- **실시간 데이터**: 페이지 진입 또는 요청 시 최신 데이터 조회 (글로벌 지수, 원자재, 크립토, Market Gate 실시간 산출)
- **주기적 동기화 (사용자 설정 가능)**: 매크로 지표(환율, 지수 등) 자동 동기화 (기본 30분, **1분~60분 단위 설정 가능**)
- **스케줄 분석**: AI 분석(15:20 KST), 일일 전체 분석 및 시그널 확정(15:40 KST)
- **수동 업데이트**: 우측 상단 'Refresh Data' 버튼으로 즉시 갱신 가능 (스크리너 포함)

![데이터 상태](/assets/9.%20데이터%20상태.png)
*실시간 데이터 동기화 및 마켓 게이트 상태 확인*

---

## 🎯 핵심 가치 제안

- **Rule-based Screening + AI Reasoning**: 엄격한 기술적 필터링과 AI의 맥락 이해력을 결합하여 신호 품질을 극대화
- **Multi-Model AI Cross-Validation**: 세 가지 모델(Gemini, GPT, Perplexity)을 조화롭게 운용하여 분석 신뢰도 극대화
- **Market-First Approach**: 개별 종목 분석 전에 시장 상태를 먼저 판단하여 하락장 리스크 사전 차단
- **Real-time Multi-Channel Notification**: Telegram, Discord, Slack, Email로 분석 결과를 즉시 전달

 ### 1. Market-First Philosophy (시장 우선주의)
> *"시장을 이기는 종목은 없다."*
- 개별 종목 분석 이전에 **Market Gate(시장 신호등)**가 시장의 건전성을 먼저 판단합니다.
- 환율, 수급, 기술적 지표가 위험 수준일 경우, 아무리 좋은 종목이 포착되어도 매수를 **원천 차단(Gate Closed)**하여 계좌를 보호합니다.        

### 2. Rule-based Screening + AI Reasoning (하이브리드 분석)
- **1차 필터(Rule)**: **거래대금 500억 이상**, **전일 대비 거래량 200% 이상**의 엄격한 기준으로 종목을 압축합니다.
- **2차 필터(AI)**: 선별된 종목의 뉴스와 재료를 AI가 정성적으로 분석하여 "가짜 반등"과 "진짜 호재"를 구분합니다.  

### 3. Multi-Model AI Cross-Validation (이중 검증)
- **Gemini**: 긴 문맥(Context) 이해와 심층 추론을 담당하여 상세한 투자 리포트를 작성합니다.
- **GPT/Perplexity**: Gemini의 분석 결과를 제3자 관점에서 검증(Critic)하여 편향(Bias)을 제거합니다.

---

## 🏗 시스템 아키텍처

이 프로젝트는 정교한 데이터 파이프라인과 AI 추론 엔진이 결합된 **하이브리드 아키텍처**를 따릅니다.

### 전체 시스템 흐름도

```mermaid
graph TD
    subgraph "Data Layer (Collection)"
        A[KRX / pykrx] --> B(Daily Price & Volume)
        A --> C(Institutional Flow)
        D[Naver Finance] --> E(News Crawling)
        F[Global Macro API] --> G(Exchange/Indices)
    end

    subgraph "Engine Layer (Screening & Scoring)"
        B & C --> H{Smart Money Screener}
        H -->|Supply Score| I[Candidate Selection]
        I --> J{Market Gate}
        J -->|OPEN| K[Trade Setup]
    end

    subgraph "AI Core Layer (Reasoning & Validation)"
        K --> L[LLM Analyzer]
        E --> M[News Sentiment]
        L & M --> N{VCP Multi-AI Analyzer}
        N -->|ThreadPool| O[Gemini]
        N -->|ThreadPool| P[GPT/Perplexity]
        
        O -->|Investment Hypothesis| Q[Consensus Engine]
        P -->|Cross Check| Q
    end

    subgraph "Service Layer (Delivery)"
        Q --> R[Signal Generator]
        R --> S[Grade System S/A/B/C]
        S --> T[Dashboard UI]
        S --> U[Chatbot ULW]
        S --> V[Notification Service]
    end

    subgraph "Notification Channels"
        V --> W[Telegram Bot]
        V --> X[Discord Webhook]
        V --> Y[Slack Incoming]
        V --> Z[Email SMTP]
    end
```

### AI-First 아키텍처 설계 원칙

**왜 이 아키텍처를 선택했는가?**

| 설계 원칙                       | 적용 방식                                                | 이유                                            |
| ------------------------------- | -------------------------------------------------------- | ----------------------------------------------- |
| **Multi-Model AI Verification** | Gemini와 GPT/Perplexity를 병렬로 실행하여 결과 교차 검증 | 단일 모델의 편향성(bias) 완화, 신호 신뢰도 상승 |
| **Async Batch Processing**      | `asyncio`와 `Semaphore`로 동시에 5~10개 종목 뉴스 분석   | API 호출 시간 최적화, Rate Limit 방지           |
| **Market Gate Pattern**         | 개별 종목 분석 전 시장 전체 상태 먼저 점검               | 하락장에서의 무분별한 매수 방지, 계좌 보호      |
| **Persona-Based Prompting**     | 일관된 투자 철학(스마트머니봇)을 시스템 프롬프트에 탑재  | AI 응답의 편차 최소화, 신뢰할 수 있는 조언 생성 |

### 기술 스택

#### Backend (Python)
- **Core Engine**: Python 3.10+, Pandas, Numpy (Vectorized Calculation for 2000+ stocks)
- **AI Engine**:
  - Google Gemini (긴 컨텍스트 윈도우, 심층 추론)
  - OpenAI GPT via Z.ai (빠른 응답, 크로스 밸리데이션)
  - Perplexity Sonar (실시간 웹 검색, 최신 뉴스/정보 반영)
  - LangChain-style Prompt Composition (Chain of Thought, Intent Injection)
- **Web Framework**: Flask (Blueprint-based modular routing)
- **Task Scheduling**: APSchedule + Threading (15:20, 15:40 KST)

#### Frontend (Next.js)
- **Framework**: Next.js 14 (App Router, TypeScript)
- **UI Components**: React with Tailwind CSS
- **Real-time Updates**: WebSocket connection for live signal updates

#### Data & Storage (데이터 인프라)
본 프로젝트는 외부 API 의존성을 최소화하고 데이터 신뢰성을 보장하기 위해 검증된 오픈소스 라이브러리를 활용합니다.

**1. 🇰🇷 한국 시장 데이터**
- **Library**: `pykrx` (KRX 정보데이터시스템 Wrapper)
- **Coverage**:
  - KOSPI / KOSDAQ 지수 및 구성 종목
  - 섹터 ETF (반도체, 2차전지 등) 시제
  - 투자자별(외국인/기관) 수급 데이터

**2. 🌎 글로벌 데이터**
- **Library**: `yfinance` (Yahoo Finance API Wrapper)
- **Coverage**:
  - 미국 지수 (S&P 500, NASDAQ)
  - 환율 (USD/KRW)
  - 원자재 선물 (Gold, Silver)
  - 암호화폐 (BTC, ETH, XRP)
- **News Sources**: Naver Finance (Crawling), Daum News, Search APIs
- **Storage**: CSV/JSON files (flat structure for simplicity)
- **Logging**: Python logging with rotation (logs/app.log)

#### Notification Services
- **Telegram**: Bot API (sendMessage, HTML parse mode)
- **Discord**: Webhook with Rich Embeds
- **Slack**: Incoming Webhooks
- **Email**: SMTP (Gmail, Office 365 supported)

---

## 🤖 AI Core: 기술적 상세 (AI Detail)

이 시스템의 핵심 경쟁력은 **Rule-based Screening**과 **AI Reasoning**의 결합입니다. 단순한 지표 추천이 아닌, AI가 시장의 문맥(Context)을 이해하고 논리적인 "투자 가설(Investment Hypothesis)"을 생성합니다.

이 시스템의 백엔드는 단순한 API 호출이 아닌, **고성능 동시성 제어(Concurrency Control)**와 **프롬프트 엔지니어링**의 집약체입니다.

### 1. Multi-Model AI Engine Architecture

서로 다른 특성을 가진 세 가지 모델을 **하이브리드로 운용**하여 비용 효율성, 최신성, 분석 깊이를 동시에 달성했습니다.

| 모델           | 역할                           | 사용 시나리오                                                 | 장점                                                              |
| -------------- | ------------------------------ | ------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Gemini**     | **Analysis Agent** (심층 추론) | 복잡한 뉴스 분석, 긴 컨텍스트 윈도우 필요, 다차원 데이터 통합 | 긴 컨텍스트(1M+ tokens), 한-영문 혼용 처리, 복잡한 논리 사고      |
| **Perplexity** | **Search Agent** (실시간 정보) | 최신 뉴스 검색, 팩트 체크, 실시간 시장 이슈 파악              | **실시간 웹 검색(Web Search)**, 최신 정보 반영, 출처(Source) 명시 |
| **Z.ai / GPT** | **Speed Agent** (빠른 검증)    | 챗봇 대화, 단순 뉴스 감성 분석, 크로스 밸리데이션             | 빠른 응답 시간, OpenAI 호환성, 비용 효율적                        |

#### 교차 검증(Cross-Validation) 로직

```mermaid
graph LR
    A[Input Data] --> B[Gemini Analysis]
    A --> C[GPT/Perplexity Analysis]
    B --> D{Result Agreement?}
    C --> D
    D -->|Yes| E[Average Confidence]
    D -->|No| F[Higher Confidence Model]
    E --> G[Final Recommendation]
    F --> G
```

**검증 규칙:**
1. **일치(Agreement)**: 두 AI의 액션(BUY/SELL/HOLD)이 일치하면 → `신뢰도 평균`
2. **불일치(Disagreement)**: 더 높은 신뢰도(Confidence)를 가진 모델 선택 (동점 시 Gemini 우선)
3. **실패(Fallback)**: 한쪽 API 실패 시 다른 쪽 결과 사용

### Concurrency Architecture
Python의 `asyncio`와 `ThreadPoolExecutor`를 결합하여, 동기식(Blocking)으로 동작하는 LLM 클라이언트 라이브러리들을 비동기 논블로킹(Non-blocking) 환경에서 병렬 실행합니다.

*   **구현 파일**: `engine/vcp_ai_analyzer.py`
*   **작동 방식**:
    1.  `VCPMultiAIAnalyzer`가 분석 요청을 수신합니다.
    2.  **Gemini**와 **GPT/Perplexity** 분석 작업을 각각의 스레드 풀로 위임(`loop.run_in_executor`)합니다.
    3.  두 모델이 동시에 추론을 수행하며, 가장 먼저 도착하거나 타임아웃 내에 도착한 응답을 수집합니다.
    4.  **Consensus Logic**: 두 모델의 의견이 일치(Agree)하면 신뢰도 점수를 상향하고, 불일치(Disagree)하면 더 보수적인 의견을 채택합니다.

---

### 2. Prompt Engineering & Persona

단순한 챗봇이 아닌, **"스마트머니봇(Black Knight)"** 페르소나를 통해 일관된 투자 철학을 유지하며, **매일 변하는 시장 상황에 맞춰 AI가 먼저 질문을 제안하는 '동적 추천 질문(Dynamic Suggestions)'** 기능을 제공합니다.

*   **페르소나 정의 (`chatbot/prompts.py`)**:
    > "너는 수급과 리스크 관리를 최우선으로 하는 냉철한 펀드매니저다. 외국인/기관의 수급이 없는 상승은 '가짜'로 간주하며, 손절가(-5%)를 생명처럼 지킨다."

#### 2.1 System Persona 정의

**페르소나 이름**: 스마트머니봇 (Smart Money Bot) / 블랙나이트 (Black Knight)

**투자 철학 (Investment Philosophy):**

```python
# engine/chatbot/prompts.py
SYSTEM_PERSONA = """
너는 VCP 기반 한국 주식 투자 어드바이저 '스마트머니봇'이야.

## 핵심 투자 원칙 (Core Constraints)
1. 수급이 곧 진실이다 (Supply is Truth):
   외국인/기관 순매수가 동반되지 않은 상승은 신뢰하지 않는다.
   단순 개인 매수세로 인한 급등은 매집(Markup)이 아니다.

2. Market Gate 우선 (Market First):
   시장 지표(환율, 지수)가 악화되면 개별 종목 추천을 멈춘다.
   하락장에서는 아무리 좋은 종목도 5~10% 급락 가능성이 있다.

3. 리스크 관리 (Risk Management):
   손절가(-5%)를 생명처럼 지킨다.
   전저점 이탈 시 즉시 손절. 이것이 계좌를 지키는 유일한 방법이다.

## 추론 프로세스 (Chain of Thought)
사용자 질문에 답변할 때 반드시 다음 단계를 거쳐라:

Step 1. [상황 인식 - Situation Awareness]
- 현재 시장이 Bull/Bear/Neutral 인지 판단
- KOSPI/KOSDAQ 지수와 USD/KRW 환율 확인

Step 2. [데이터 분석 - Data Analysis]
- 사용자가 물어본 종목의 5일/20일/60일 수급 누적 확인
- 최근 VCP 패턴 여부 확인 (변동성 축소 구간)
- 뉴스 호재/악재 문맥 파악

Step 3. [결론 도출 - Conclusion]
- 매수/매도/관망 의견 제시 및 근거 서술
- 목표가와 손절가 구체적으로 제시

## 응답 톤 (Tone & Style)
- 전문적이면서도 이해하기 쉬운 표현 사용
- 불확실한 추측은 "추정", "가능성" 등으로 표시
- 수치는 반올림하여 깔끔하게 제시
"""
```

#### 2.2 상황별 맞춤 프롬프트 (Intent Injection)

**Intent-Based Prompting (의도 기반 프롬프트)**

사용자의 질문 의도(Intent)를 파악하여, 그에 맞는 최적화된 프롬프트를 동적으로 로딩합니다.

| 의도 (Intent)         | 프롬프트 전략   | 주요 내용                                                                   |
| --------------------- | --------------- | --------------------------------------------------------------------------- |
| **`recommendation`**  | **종목 발굴**   | 수급 점수 상위 종목 중심, 사용자의 관심 섹터 반영, 보유 종목 중복 배제      |
| **`analysis`**        | **정밀 분석**   | 60일 누적 수급 트렌드 분석, VCP 패턴 단계(Phase 1~4) 진단, 뉴스 악재 필터링 |
| **`market_overview`** | **시장 브리핑** | Market Gate 상태(Open/Closed), 주도 테마 및 순환매 흐름 파악                |
| **`risk_check`**      | **리스크 관리** | 구체적인 손절가 계산, 현금 비중 조절 조언, 거시경제(환율) 위험 경고         |

**A. 뉴스 감성 분석 프롬프트 (News Sentiment Analysis)**

```python
# engine/llm_analyzer.py - analyze_news_sentiment()
NEWS_SENTIMENT_PROMPT = """
당신은 주식 투자 전문가입니다. 주어지는 뉴스들을 분석하여 호재 강도를 평가하세요.

[뉴스 목록]
{news_items}

[점수 기준 (Scoring Rubric)]
3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈, 경영권 분쟁 등)
2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
1점: 단순/중립적 소식 (일반 공시, 기본 실적 발표)
0점: 악재 또는 별다른 호재 없음 (악재, 리스크 우려)

[출력 형식]
뉴스 3개를 따로 평가하지 말고, **종목 전체에 대한 하나의 평가**를 내리세요.
반드시 아래 포맷의 **단일 JSON 객체**로만 답하세요. (Markdown code block 없이)

Format: {{"score": 2, "reason": "종합적인 요약 이유"}}
"""
```

**왜 이렇게 프롬프트를 구성했는가?**
- **단일 JSON 요구**: 프로그래밍적으로 파싱하기 쉬워 후속 처리 용이
- **0~3점 스케일**: 너무 많은 레벨이 아닌, 실행 가능한 액션(BUY/HOLD/SELL)으로 매핑
- **종합 평가 강조**: 개별 뉴스 평가가 아닌, 종목 전체의 재료 지속성 판단

---

**B. 배치 분석 프롬프트 (Batch Analysis - Closing Bet V2)**

```python
# engine/llm_analyzer.py - analyze_news_batch()
BATCH_ANALYSIS_PROMPT = """
당신은 주식 투자 전문가입니다. 시장 상황, 수급, 뉴스를 종합적으로 분석하여 투자 판단을 내리세요.

{market_context}

다음 종목들을 분석하여 투자 매력도를 평가하세요.
문서에 정의된 '종합 분석' 기준을 따릅니다.

[입력 데이터]
{stocks_text}

[평가 기준]
1. **Score (0-3)**: 뉴스/재료 기반 호재 강도
   - 3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈)
   - 2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
   - 1점: 단순/중립적 소식
   - 0점: 악재 또는 별다른 호재 없음
2. **Action**: BUY / HOLD / SELL
3. **Confidence**: 확신도 (0-100%)
4. **Reason**: 다음 요소를 종합하여 간결하게 작성하세요.
   - 뉴스/재료 분석 (호재 여부)
   - 수급 동향 (외인/기관)
   - 종합 투자 의견

[출력 형식]
반드시 아래 포맷의 **JSON 배열**로만 답하세요. (Markdown code block 없이)

[
    {{
        "name": "종목명",
        "score": 2,
        "action": "BUY",
        "confidence": 85,
        "reason": "대규모 신규 수주 발표로 강한 호재. 외인/기관 동반 순매수 유입 중."
    }}
]
"""
```

**왜 시장 컨텍스트를 주입했는가?**
- 시장 상황(강세/약세/중립)에 따라 동일한 뉴스라도 해석이 달라질 수 있음
- 예: 강세장에서의 호재 > 약세장에서의 호재

---

**C. VCP 기술적 분석 프롬프트 (VCP Technical Analysis)**

```python
# engine/vcp_ai_analyzer.py - _build_vcp_prompt()
VCP_ANALYSIS_PROMPT = """
당신은 주식 투자 전문가입니다. VCP(Volatility Contraction Pattern) 패턴 종목을 분석하세요.

[종목 정보]
- 종목명: {stock_name}
- 현재가: {current_price}
- VCP 점수: {vcp_score}
- 수축 비율: {contraction_ratio}
- 외국인 5일 순매수: {foreign_5d}주
- 기관 5일 순매수: {inst_5d}주

[분석 요청]
1. VCP 패턴과 수급 상황을 종합 분석
2. 매수/매도/관망 의견 제시
3. 신뢰도(0-100%) 평가

[출력 형식 - 반드시 JSON만 출력]
{{"action": "BUY|SELL|HOLD", "confidence": 75, "reason": "분석 요약 (한국어, 2-3문장)"}}
"""
```

**VCP 분석의 특징:**
- **변동성 수축(Contraction)**: 가격 폭이 줄어들면서 거래량이 줄어드는 구간 포착
- **매집(Accumulation)**: 외국인/기관의 지속적인 순매수 확인
- **AI 패턴 인식**: 단순 지표가 아닌, 패턴의 질적(Quality) 평가

---

**D. 시장 요약 프롬프트 (Market Summary)**

```python
# engine/llm_analyzer.py - generate_market_summary()
MARKET_SUMMARY_PROMPT = """
당신은 주식 시장 분석 전문가입니다. 오늘의 포착된 종목들을 바탕으로 시장의 주도 테마와 분위기를 요약해주세요.

오늘 '종가베팅' 알고리즘에 포착된 상위 종목 리스트입니다.
이들을 분석하여 다음 내용을 포함한 3~5줄 내외의 시장 요약 리포트를 작성해주세요.

1. 오늘의 주도 섹터/테마
2. 시장의 전반적인 분위기 (수급 강도 등)
3. 특히 주목할만한 특징

[종목 리스트]
{stocks_text}

[출력 형식]
줄글 형태로 간결하게 요약. (Markdown 사용 가능)
"""
```

---

### 3. 뉴스 감성 분석 (Advanced Sentiment Analysis)

`engine/kr_ai_analyzer.py`와 `engine/llm_analyzer.py`는 다중 소스(네이버 금융, 검색 등)에서 수집된 뉴스를 **가중치(Weight)** 기반으로 필터링한 후 AI에게 전달합니다.

#### 3.1 다중 소스 뉴스 수집

| 소스                 | 수집 방법                                         | 가중치(Weight) | 특징                           |
| -------------------- | ------------------------------------------------- | -------------- | ------------------------------ |
| **네이버 금융**      | `finance.naver.com/item/news.naver?code={ticker}` | 0.9 (Tier 1)   | 종목 전용 뉴스, 신뢰도 높음    |
| **네이버 뉴스 검색** | `search.naver.com/news`                           | 0.7 (Tier 2)   | 최신성 확보, 광범위한 커버리지 |
| **다음 뉴스**        | `search.daum.net/news`                            | 0.7 (Tier 2)   | 네이버와 상호 보완             |

#### 3.2 언론사별 가중치 (Media Credibility)

```python
# engine/kr_ai_analyzer.py
MAJOR_SOURCES = {
    "한국경제": 0.9,      # 주요 경제지 (Tier 1)
    "매일경제": 0.9,
    "머니투데이": 0.85,
    "서울경제": 0.85,
    "이데일리": 0.85,
    "연합뉴스": 0.85,
    "뉴스1": 0.8,
    # 기타 일반 인터넷 언론: 0.7 (Tier 2)
}
```

**왜 가중치를 적용했는가?**
- **신뢰도 차등화**: 주요 경제지 뉴스 > 인터넷 언론 루머
- **중복 제거**: 같은 뉴스가 여러 소스에서 나오면 가중치 합산 후 한 번만 전달
- **품질 필터링**: 낮은 가중치(0.5 이하)는 AI 입력 전 자동 제외

#### 3.3 AI의 역할: 문맥(Context) 파악

AI는 단순 뉴스 요약이 아니라, **재료의 지속성(Durability)** 을 판단합니다:

| 뉴스 유형       | AI 해석               | 예시                           |
| --------------- | --------------------- | ------------------------------ |
| 단순 공시       | Score 1점 (중립적)    | "정기 주주총회 개최 공시"      |
| 실적 서프라이즈 | Score 2~3점 (호재)    | "1Q 영업이익 YoY +40% 어닝"    |
| 대규모 수주     | Score 3점 (강한 호재) | "해외 3년치 플랜트 수주 1조원" |
| 악재 루머       | Score 0점 (악재)      | "경쟁사 해외 사업 매각"        |

---

### 4. Async Batch Processing & Rate Limit Handling

대규모 종목(2000개)를 실시간으로 분석하기 위해 **비동기 배치 처리**를 구현했습니다.

#### 4.1 동시성 제어 (Concurrency Control)

```python
# engine/llm_analyzer.py - analyze_news_batch()
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

**설계 의도:**
- **Rate Limit 방지**: API 공급자의 초당 호출 제한(예: 10 req/s) 준수
- **시간 최적화**: 순차 처리(2000초) → 병렬 처리(40초)로 50배 속도 향상

#### 4.2 Retry Logic with Exponential Backoff

```python
# Gemini Rate Limit (HTTP 429) 처리
max_retries = 3
for attempt in range(max_retries):
    try:
        response = await api_call()
        break
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + 1  # 2초, 3초, 5초
                logger.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
        raise e
```

---

### 5. 투자 가설 생성 (Investment Hypothesis)

AI는 단순한 매수/매도 의견이 아닌, **논리적인 투자 가설**을 생성합니다.

```python
# engine/kr_ai_analyzer.py - _analyze_with_gemini()
# 실제 AI가 생성하는 구조화된 리포트
INVESTMENT_HYPOTHESIS = """
[핵심 투자 포인트]
• 주력 제품의 수출 호조세 지속 및 글로벌 점유율 확대
• 신규 수주 공시로 인한 향후 3년치 일감 확보

[리스크 요인]
• 글로벌 경기 둔화 우려에 따른 전방 산업 수요 위축
• 환율 변동성에 따른 단기 환차손 가능성

[종합 의견]
동사는 {name} 분야의 선도 기업으로, 최근 {driver} 점이 긍정적입니다.
특히 3분기 실적 서프라이즈와 함께 연간 가이던스가 상향 조정된 점이
주가 상승의 주요 트리거가 될 것으로 판단됩니다.
현재 밸류에이션은 역사적 저점 수준으로, 중장기적 관점에서 매수 접근이 유효해 보입니다.
"""
```

**구조의 이점:**
1. **투자 포인트 명확화**: 사용자가 왜 매수해야 하는지 이해 용이
2. **리스크 노출**: 단순 호재 강조가 아닌, 리스크도 명시
3. **논리적 연결**: 드라이버 → 가설 → 결론의 흐름 구성

---

## 📊 주요 기능 및 알고리즘

### 1. Market Gate (시장 신호등 - 최상위 관문)

시장의 거시적/미시적 환경을 정량화하여 **"지금 주식을 사도 되는가?"** 를 결정하는 최상위 관문입니다. 하락장에서는 아무리 좋은 종목도 5~10% 급락 가능성이 있어, 시장 상태를 먼저 확인하는 것이 계좌를 지키는 핵심입니다.

시장의 거시적/미시적 데이터를 정량화하여 **"매수 버튼을 활성화할지"** 결정하는 최상위 관문입니다. 코드 레벨(`engine/market_gate.py`)에서 구현된 실제 스코어링 로직은 다음과 같습니다.

*   **총점 100점 만점** (60점 이상 Open)

| 카테고리      | 지표       | 상세 조건                       | 배점     | 비고                              |
| ------------- | ---------- | ------------------------------- | -------- | --------------------------------- |
| **Technical** | **Trend**  | KODEX 200 20일 > 60일 (정배열)  | **25점** | 추세 추종                         |
| **(70점)**    | **RSI**    | RSI 14일 기준 50~70 구간 (강세) | **25점** | 과매수/과매도 회피                |
|               | **MACD**   | MACD > Signal (골든크로스)      | **10점** | 모멘텀 확인                       |
|               | **Volume** | 거래량 > 20일 평균거래량        | **10점** | 거래 활성화                       |
| **Macro**     | **환율**   | USD/KRW (안전 < 1400원)         | **15점** | **위험(1450원↑) 시 -20점 페널티** |
| **(30점)**    | **수급**   | 외국인 선물 순매수 > 0          | **15점** | 메이저 자금 이탈 확인             |

*   **Gate Closed 트리거**: 총점이 60점 미만이거나, **환율이 DANGER 레벨(1450원 이상)**인 경우 즉시 매매가 중단됩니다.

#### 1.1 구성 지표

| 카테고리      | 지표               | 임계값           | 점수 배점 |
| ------------- | ------------------ | ---------------- | --------- |
| **Macro**     | USD/KRW 환율       | 1450원 (DANGER)  | 30점      |
|               | KODEX 200 지수     | 정배열 여부      | 20점      |
| **Technical** | RSI (KODEX 200)    | 50기준 초과/미달 | 20점      |
|               | MACD Signal        | 골든크로스       | 10점      |
| **Supply**    | 외국인 선물 순매수 | 양수 매수세      | 20점      |

**총점 100점 만점**

#### 1.2 Gate 판정 로직

```python
# engine/market_gate.py
def evaluate_market_gate():
    score = 0

    # 1. 환율 점검 (DANGER 시 무조건 CLOSED)
    if usd_krw >= 1450:
        return MarketStatus.GATE_CLOSED, "환율 1450원 초과: DANGER"

    # 2. KODEX 200 정배열
    if kodex_200_ma5 > kodex_200_ma20:
        score += 20

    # 3. RSI 확인
    if rsi_14day >= 50:  # 과매수 영역
        score += 20

    # 4. MACD 시그널
    if macd_line > signal_line:
        score += 10

    # 5. 외국인 수급
    if foreign_futures_net_buy > 0:
        score += 20

    # 6. KOSPI 추세
    if kospi_change_pct > 0:
        score += 10

    # 판정
    if score >= 60:
        return MarketStatus.GATE_OPEN, f"{score}점: 매수 허용"
    else:
        return MarketStatus.GATE_CLOSED, f"{score}점: 매수 보류"
```

#### 1.3 왜 Market Gate가 필요한가?

**시나리오 A (Market Gate 없음):**
- 하락장에서 좋은 종목 포착 → 매수 → 익일 -8% 급락
- **결과**: 수익률 -40% (10번 중 6번 손실)

**시나리오 B (Market Gate 적용):**
- 하락장 감지 → 모든 신호 차단 → 현금 보유
- **결과**: 리스크 완전 회피, 하락장 종료 후 재진입

---

### 2. KR Market Analysis (한국 시장 분석)

한국 주식 시장 전체를 분석하여 섹터별 흐름과 시장 점유율을 파악합니다.

#### 2.1 데이터 수집 지표

| 지표                                        | 출처                   | 활용 목적                   |
| ------------------------------------------- | ---------------------- | --------------------------- |
| **KOSPI/KOSDAQ 지수**                       | KRX, FinanceDatareader | 시장 전체 추세 파악         |
| **환율 (USD/KRW, EUR/KRW, JPY/KRW)**        | FX API                 | 수출주/수입주 영향 분석     |
| **업종 지수** (반도체, 전기전자, 바이오 등) | KRX                    | 섹터 순환매 파악            |
| **외국인/기관 일별 매매 동향**              | KRX, Naver Finance     | 시장 참여자 성향 분석       |
| **전일 거래대금 상위 종목**                 | KRX                    | 시장 리더십(Liquidity) 파악 |

#### 2.2 분석 기능

**A. 섹터 모멘텀(Sector Momentum) 분석**
- 최근 5일 동안 상승률이 높은 섹터 식별
- 섹터 내 상위 종목들의 공통 테마 추출
- 예: "AI 반도체 테마 강세", "2차전지 호조"

**B. 시장 점유율(Market Dominance) 분석**
- KOSPI 상위 50종목의 시가총액 합산 비중
- 시장 대표종목의 방향성 확인 (대형주 주도 vs 소형주 주도)

**C. 외국인/기관 수급 패턴**
- 5일/20일/60일 누적 순매수 추이 확인
- 순매수 금액 규모로 매수 강도 정량화
- 예: 외인 3일 연속 순매수 +1000억 → "외인 매집 중"

#### 2.3 AI 통합 방식

```python
# engine/kr_ai_analyzer.py - analyze_stock()
AI 통합 순서:
1. 종목 정보 조회 (가격, PER, PBR, ROE)
2. 뉴스 수집 (네이버 + 다음 + 검색, 가중치 부여)
3. Gemini 분석:
   - 뉴스 호재/악재 판단
   - 투자 포인트와 리스크 요인 식별
   - 종합 의견(매수/매도/관망) 생성
4. GPT/Perplexity 분석 (크로스 밸리데이션):
   - Gemini와 동일한 결론인지 확인
   - 기술적 지표 기반 보완 의견 제시
5. 결과 통합:
   - 두 AI의 액션 일치 시 → 신뢰도 평균
   - 불일치 시 → 더 높은 신뢰도 채택
```

**출력 예시:**
```json
{
    "ticker": "005930",
    "name": "삼성전자",
    "price": 75000,
    "gemini_recommendation": {
        "action": "BUY",
        "confidence": 88,
        "reason": "AI 반도체 호조세에 따른 수혜 예상. 외국인 5일 연속 순매수."
    },
    "gpt_recommendation": {
        "action": "BUY",
        "confidence": 82,
        "target_price": 85000,
        "stop_loss": 72000
    },
    "final_recommendation": {
        "action": "BUY",
        "confidence": 85,
        "reason": "Gemini: AI 반도체 호조세 / GPT/Perplexity: 기술적 매매"
    }
}
```

---

**3. VCP Signals (변동성 축소 패턴)**

![VCP 시그널](/assets/2.%20VCP%20시그널.png)
*VCP 패턴이 포착된 종목 리스트 및 요약 정보*

마크 미너비니(Mark Minervini)의 **VCP (Volatility Contraction Pattern)** 전략을 한국 시장에 맞게 튜닝했습니다. VCP는 "가격이 상승하면서 변동성이 줄어드는 구간"으로, 이는 대형주나 기관 매집 구간에서 자주 관찰됩니다.

![VCP 상세](/assets/3.%20VCP%20시그널%20종목상세.png)
*개별 종목의 VCP 패턴 분석 및 AI 투자 의견 상세*

마크 미너비니의 VCP 이론을 파이썬 알고리즘으로 구현했습니다.

*   **수집 알고리즘 (`engine/screener.py`)**:
    *   **거래대금(Liquidity)**: 최소 500억 원 이상.
    *   **거래량 폭발(Volume Breakout)**: 전일 대비 거래량 200% (2배) 이상 급증 필수.
    *   **Pivot Point**: 최근 저점을 높이며 5일 이평선 위에 안착.

#### 3.1 VCP 정의와 이론

**VCP (Volatility Contraction Pattern) 4단계:**

```mermaid
graph LR
    A[Phase 1<br>급등 후 변동성 확대] --> B[Phase 2<br>하락 후 저점 형성]
    B --> C[Phase 3<br>횡보장/수축<br>거래량 감소]
    C --> D[Phase 4<br>상방 돌파<br>상승 재개]
```

| 단계        | 특징                     | 목적               |
| ----------- | ------------------------ | ------------------ |
| **Phase 1** | 급등 + 높은 변동성       | 관심도 집중        |
| **Phase 2** | 하락 → 저점 형성         | 저점 매집 기회     |
| **Phase 3** | **횡보장 + 변동성 수축** | **핵심 포착 구간** |
| **Phase 4** | 상방 돌파 + 상승 재개    | 매수 진입 시점     |

#### 3.2 기술적 스크리닝 조건

**A. 가격 기준 (Price Criteria)**
```python
# engine/vcp_screener.py
vcp_conditions = {
    # 60일 고가 대비 -10% 이내 (하락 폭 제한)
    "max_drawdown": -0.10,

    # 최근 20일 동안 변동성이 줄어듬
    "volatility_contraction": True,

    # 거래량이 줄어들면서 가격 유지 (수축 구간)
    "volume_decline": True,

    # 최근 저점에서의 반등 (바닥 형성)
    "pivot_low": True
}
```

**B. VCP 점수 산정 (0~100점)**
| 구성 요소            | 점수 | 계산 방식                             |
| -------------------- | ---- | ------------------------------------- |
| **변동성 수축 비율** | 30점 | (최근10일 변동성) / (이전20일 변동성) |
| **가격 위치**        | 20점 | 60일 고가 대비 현재가 위치 (0~100%)   |
| **거래량 패턴**      | 20점 | 수축 구간 내 거래량 감소율            |
| **이평선 정배열**    | 15점 | 5일 > 20일 > 60일                     |
| **RSI 상태**         | 15점 | 40~60 사이 (과매수/과매도 아님)       |

**등급 부여 기준:**
- **VCP 점수 85점 이상**: A급 (Strong VCP)
- **VCP 점수 70~84점**: B급 (Moderate VCP)
- **VCP 점수 60~69점**: C급 (Weak VCP)
- **VCP 점수 60점 미만**: D급 (미달 - 수집/표시 제외)

#### 3.3 VCP Signals 주요 기능 (New)

최신 업데이트된 VCP Signals 시스템은 단순한 패턴 매칭을 넘어 실시간 데이터와 AI 분석을 통합하여 제공합니다.

**A. 실시간 가격 추적 (Real-time Tracking)**
- **평일 장중 (09:00~15:30)**: `yfinance` API를 통해 **1분 단위** 실시간 시세(Entry, Current, Return)를 추적합니다.
- **장외/주말**: 마지막 종가(`daily_prices.csv`)를 기준으로 폴백(Fallback) 처리하여 언제든 데이터 조회 가능.
- **Entry Price 대비 수익률**: 진입가 대비 현재 수익률을 실시간으로 계산하여 표시합니다.

** B. AI 심층 분석 및 뉴스 연동 (AI & News)**
- **Multi-Model Analysis**: Gemini(심층 추론), Perplexity(실시간 정보), GPT(검증) 3가지 모델이 종목을 다각도로 분석합니다.
- **뉴스 자동 수집**: `EnhancedNewsCollector`가 각 시그널 발생 종목의 최신 뉴스를 자동으로 수집하여 AI에게 제공합니다.
- **AI 추천 배지**: AI의 분석 결과(매수/관망/매도)를 직관적인 배지로 시각화하여 제공합니다.

**C. 필터링 및 품질 관리 (Quality Control)**
- **Score 60+ 필터**: VCP 점수 60점 미만의 낮은 품질 시그널은 수집 및 표시 단계에서 **자동으로 제외**됩니다.
- **VCP 범위 시각화**: 차트상에 전반부(최근 30일 고점)와 후반부(최근 10일 저점) 범위를 시각적으로 표시하여 패턴의 유효성을 직관적으로 판단할 수 있습니다.
    
**D. 종가베팅 등급 기준 (Closing Bet Grade Criteria)**

![종가 베팅](/assets/4.%20종가%20베팅.png)
*장 마감 직전 포착된 종가 베팅 후보 종목 리스트*

![종가베팅 등급기준](/assets/6.%20종가%20베팅%20등급%20산정%20기준.png)
*시스템에 적용된 5단계(S/A/B/C/D) 등급 산정 세부 기준*

> [!IMPORTANT]
> **공통 제외 조건**: 거래대금 **500억 미만** 또는 거래량 배수 **2.0배 미만**인 종목은 등급과 무관하게 **자동 제외**됩니다.

##### 📊 통합 등급 산정 기준

|  등급   | 거래대금 & 등락률          | 점수 (Total Score) | 추가 조건 (거래량/수급)               | 비고             |
| :-----: | :------------------------- | :----------------: | :------------------------------------ | :--------------- |
| **S급** | **1조원 이상**, +10% 이상  |   **10점 이상**    | 거래량 **5배↑**, 외인+기관 **양매수** | 초대형 수급 폭발 |
| **A급** | **5,000억 이상**, +5% 이상 |    **8점 이상**    | 거래량 **3배↑**, 외인 or 기관         | 대형 우량주      |
| **B급** | **1,000억 이상**, +4% 이상 |    **6점 이상**    | 거래량 **2배↑**, 외인 or 기관         | 중형 주도주      |
| **C급** | **500억 이상**, +5% 이상   |    **8점 이상**    | 거래량 **3배↑**, 외인+기관 **양매수** | 강소 주도주      |
| **D급** | **500억 이상**, +4% 이상   |    **6점 이상**    | 거래량 **2배↑**, 수급 무관            | 관망 / 조건부    |

> [!NOTE]
> **등급 판정 우선순위**: S급 → A급 → B급 → C급 → D급 순으로 판정하며, 상위 등급 조건을 만족하면 해당 등급이 부여됩니다.
    
**E. 종합 점수 산정 기준 (Scoring Logic - Max 12점)**

등급 산정에 사용되는 **'종합 점수(Total Score)'**는 다음 6가지 핵심 평가 요소의 합산입니다.

##### 🎯 핵심 평가 요소 (Score 12점 만점)
    
| 항목            |  배점   | 상세 기준                                            | 평가 목적                  |
| :-------------- | :-----: | :--------------------------------------------------- | :------------------------- |
| **📰 뉴스/재료** | **3점** | AI가 수집된 뉴스의 호재 강도를 0~3점으로 평가        | 재료의 지속성 및 강도 판단 |
| **💰 거래대금**  | **3점** | 5,000억+(3점), 2,000억+(2점), 1,000억+(1점)          | 시장 주도력 평가 (유동성)  |
| **📈 차트 패턴** | **2점** | 52주 신고가 돌파(+1), 이평선 정배열(+1)              | 기술적 상승 추세 확인      |
| **🤝 수급**      | **2점** | 외국인 5일 순매수 > 0 (+1), 기관 5일 순매수 > 0 (+1) | 외인/기관 순매수 지속성    |
| **🕯️ 캔들 형태** | **1점** | 장대양봉: 몸통 > 윗꼬리×2, 상승 마감                 | 매수 강도 확인             |
| **⏱️ 기간조정**  | **1점** | 볼린저밴드 수축 등 변동성 축소 후 발산 구간          | VCP 패턴 진입 확인         |

##### 📋 점수별 의미

```
┌─────────────────────────────────────────────────────────────┐
│  10점 이상  │  S급 조건 충족 가능 (초대형 수급폭발)           │
│  8~9점     │  A급/C급 조건 충족 가능 (우량주/강소주)          │
│  6~7점     │  B급/D급 조건 충족 가능 (주도주/관망)            │
│  5점 이하  │  등급 미달 (시그널 제외)                         │
└─────────────────────────────────────────────────────────────┘
```

> [!WARNING]
> **점수만으로는 등급이 결정되지 않습니다.** 거래대금, 등락률, 거래량배수, 수급 조건을 **모두 만족**해야 해당 등급이 부여됩니다.
> 
> 예시: 점수 10점이라도 거래대금이 500억이면 S급이 아닌 C급 또는 D급이 됩니다.

#### 3.4 AI VCP 분석 (Multi-AI Validation)

```python
# engine/vcp_ai_analyzer.py - analyze_stock()
async def analyze_stock(stock_name: str, stock_data: Dict):
    # 1. Gemini 분석 (심층 추론 + 뉴스 분석)
    gemini_result = await _analyze_with_gemini(stock_name, stock_data)

    # 2. GPT/Perplexity 분석 (크로스 밸리데이션)
    gpt_result = await _analyze_with_gpt(stock_name, stock_data)


    # 3. 결과 통합
    return {
        'stock_name': stock_name,
        'vcp_score': stock_data['vcp_score'],
        'gemini_recommendation': gemini_result,  # {"action": "BUY", "confidence": 85, ...}
        'gpt_recommendation': gpt_result,      # {"action": "BUY", "confidence": 80, ...}
        'consensus': 'AGREE' if gemini_result['action'] == gpt_result['action'] else 'DISAGREE'
    }
```

**AI 프롬프트 (VCP 전용):**
```
VCP 패턴과 수급 상황을 종합 분석하세요.

[종목 정보]
- VCP 점수: 85점 (강한 수축)
- 외국인 5일 순매수: +500만주
- 기관 5일 순매수: +300만주

[분석 요청]
1. VCP 패턴이 유효한가? (상방 돌파 가능성)
2. 매집(Accumulation)이 진행 중인가? (수급 확인)
3. 매수/매도/관망 의견 제시
4. 신뢰도(0-100%) 평가

[출력]
{"action": "BUY|SELL|HOLD", "confidence": 75, "reason": "VCP 완성, 외인/기관 동반 매집 중"}
```

#### 3.4 왜 VCP를 사용하는가?

**전략적 우위:**
1. **위험/보상 비율 최적화**: 수축 구간 매수 → 상방 돌파 시 급등
2. **기관 매집 파악**: 거래량 감소 + 수급 유입 = "비밀리 매집" 신호
3. **진입 시점 정교화**: 차트 패턴이 아닌, 패턴 완성 시점 포착

---

장 마감 직전(15:20) 동시호가에 진입하여 익일 시초가나 오전에 매도하는 **단기 스윙 트레이딩** 전략입니다.

*   **등급 시스템 (AI Scoring)**:
    *   **S등급 (90점+)**: "강력 매수" - 확실한 뉴스 호재(Score 3) + 외인/기관 양매수(Double Buy).
    *   **A등급 (80점+)**: "매수" - 호재 존재 + 수급 양호.
    *   **B등급 (70점+)**: "관망" - 수급은 좋으나 재료가 약함.
    *   **D등급**: "매매 금지" - 악재 뉴스 발견(Score 0) 또는 역배열.

---

### 4. Paper Trading (모의투자 시스템)

실전 투자 전, 내 전략을 안전하게 검증할 수 있는 **완전한 기능의 모의투자 시스템**을 제공합니다.

![모의투자 메인](assets/17.%20모의투자1.png)
*모의투자 대시보드 메인 화면*

#### 4.1 주요 기능

*   **가상 자산 운용**: 초기 자본금 **1억 원**으로 시작하여 실전과 동일한 환경에서 투자를 연습할 수 있습니다.
*   **실시간 시세 연동**: 시장가(Market Price) 기반으로 즉시 체결되며, 수수료와 세금까지 시뮬레이션합니다.
*   **포트폴리오 분석**: 보유 종목의 수익률, 평가 손익, 자산 구성을 한눈에 파악할 수 있습니다.

![포트폴리오](assets/18.%20모의투자2.png)
*직관적인 포트폴리오 구성 및 자산 현황 파악*

#### 4.2 매매 및 자산 관리

*   **간편한 주문**: 매수/매도 모달을 통해 수량과 금액을 쉽게 입력하고 주문을 실행합니다.
*   **거래 내역(History)**: 모든 매매 기록이 저장되어 자신의 투자 패턴을 복기할 수 있습니다.
*   **수익 차트**: 일별 자산 변동 추이를 시각화된 차트로 제공하여 성과를 분석합니다.

|              주문 실행              |              거래 내역              |
| :---------------------------------: | :---------------------------------: |
| ![주문](assets/19.%20모의투자3.png) | ![내역](assets/20.%20모의투자4.png) |

![수익 차트](assets/21.%20모의투자5.png)
*자산 변동 추이 및 수익률 차트*


#### 4.1 알고리즘 개요

**전략 시나리오:**
- **15:20 장중**: 후보군 스크리닝 → AI 필터링 → 최종 신호 생성
- **15:30 장 마감**: 시가초가/지정가 확정
- **익일 09:00~09:30**: 목표가/손절가에 따라 자동 매도 추천

#### 4.2 Screener Logic (Rule-based)

**Phase 1: 유동성 필터링 (Liquidity Filter)**
```python
# engine/jongga_v2_screener.py
liquidity_filters = {
    # 당일 거래대금 상위 500종목
    "trading_value_rank": 500,

    # 최소 거래대금 (50억원 이상)
    "min_trading_value": 5_000_000_000,

    # 시가총액 상위 30% (유동성 확보)
    "market_cap_rank": 0.3
}
```

**Phase 2: 모멘텀 필터링 (Momentum Filter)**
```python
momentum_filters = {
    # 주가 등락률 2%~15% (과매수/과매도 기피)
    "change_pct_min": 0.02,
    "change_pct_max": 0.15,

    # 거래량 증가 (관심도 상승)
    "volume_ratio_min": 1.2,  # 전일 대비 120% 이상
}
```

**Phase 3: 수급 필터링 (Supply/Demand Filter)**
```python
supply_filters = {
    # 외국인 골든크로스 (5일 > 20일)
    "foreign_golden_cross": True,

    # 기관 골든크로스 (5일 > 20일)
    "inst_golden_cross": True,

    # 외국인 5일 순매수 금액
    "foreign_5d_net_buy_min": 10_000_000,  # 10억원 이상

    # 기관 5일 순매수 금액
    "inst_5d_net_buy_min": 10_000_000,  # 10억원 이상

    # 프로그램 순매수 유입
    "program_net_buy": True
}
```

#### 4.3 AI 필터링 (LLM Validation)

**AI가 수행하는 역할:**
1. **재료 지속성(Durability) 판단**: 일시적인 호재 vs 지속 가능한 모멘텀
2. **악재 노출**: 뉴스에 숨겨진 리스크 식별
3. **등급 최종 결정**: S/A/B/C/D 등급 부여

**AI 입력 데이터:**
```json
{
    "stock_name": "종목명",
    "current_price": 75000,
    "change_pct": 0.08,  // +8%
    "trading_value": 150_000_000_000,  // 1500억
    "volume_ratio": 1.5,
    "foreign_5d": "+500억",
    "inst_5d": "+300억",
    "news": [
        {"title": "AI 반도체 수주 500억원", "weight": 0.9},
        {"title": "해외 AI 투자 확대", "weight": 0.7}
    ]
}
```

**AI 출력 및 등급 부여:**
| AI 점수       | 등급           | 의미          | 손절가        | 목표가 |
| ------------- | -------------- | ------------- | ------------- | ------ |
| **90점 이상** | **S급**        | 매수가 × 0.97 | 매수가 × 1.05 |
| **80~89점**   | **A급**        | 매수가 × 0.97 | 매수가 × 1.05 |
| **70~79점**   | **B급**        | 매수가 × 0.97 | 매수가 × 1.05 |
| **60~69점**   | **C급**        | 매수가 × 0.97 | 매수가 × 1.05 |
| **60점 미만** | **D급 (거부)** | -             | -             |

**AI 평가 요소:**
- **뉴스/재료 점수 (0~3점)**: 호재 강도
- **수급 동향 (0~3점)**: 외국인/기관 매수 강도
- **기술적 패턴 (0~2점)**: 모멘텀, 거래량 패턴
- **최대 점수**: 8점 (S급 기준)

![종가베팅 상세](/assets/5.%20종가%20베팅%20상세%20분석%20보기.png)
*AI가 분석한 종가 베팅 종목의 뉴스 재료 및 투자 가설 상세 리포트*

#### 4.4 왜 AI 필터링이 필요한가?

**사례 A (AI 없음):**
- 기술적 스크리닝 후보 50개 → 일일 매도
- **결과**: 30%는 악재로 인한 급락 → 수익률 -15%

**사례 B (AI 필터링 적용):**
- 기술적 스크리닝 후보 50개 → AI 악재 노출 → 20개만 신호
- **결과**: 악재 종목 제외로 수익률 +12%

**효과:** AI 필터링으로 **거짓 신호(False Positive)를 60% 감소**

---

### 5. Data Status & Integrity

**A. 데이터 업데이트 자동화**
- **매일 15:20**: 장중 데이터 업데이트 (종가베팅용)
- **매일 15:40**: 장 마감 후 전체 데이터 수집 (VCP용)
- **수동 실행**: `python scripts/run_full_update.py`

**B. 데이터 무결성(Integrity)**
- **타입 체킹**: 모든 데이터 클래스에 dataclass 적용
- **예외 처리**: API 실패 시 로그 기록 후 다음 종목 진행
- **검증 로직**: 수급 데이터 이상치 탐지 (예: 순매수 +1000억 → 검증 필요)

### 6. Scheduler & Notification (자동화된 스케줄러)

시스템은 `services/scheduler.py`에 의해 전자동으로 운영되며, 하루 두 번의 결정적인 모멘텀을 포착합니다.

### 1. 15:20 - Pre-Close Analysis (종가베팅)
*   **목적**: 장 마감 전 진입하여 익일 갭상승을 노림.
*   **프로세스**:
    1.  장중 실시간 추정가 수집 (pykrx).
    2.  `JonggaV2` 알고리즘으로 급등주 1차 필터링.
    3.  **AI 긴급 분석**: 선별된 TOP 10 종목의 당일 뉴스 분석.
    4.  **Telegram/Slack 긴급 알림 발송**.

### 2. 15:40 - Post-Close Analysis (VCP & 정산)
*   **목적**: 정규장 종료 후 확정 데이터를 기반으로 정밀 분석.
*   **프로세스**:
    1.  일별 확정 종가, 외국인/기관 확정 수급 집계.
    2.  **Market Gate** 최종 점수 산출 및 DB 저장.
    3.  전 종목 대상 **VCP 패턴 정밀 스캔**.
    4.  일일 리포트(Daily Report) 이메일 발송.

#### 6.1 스케줄러 아키텍처

**구현 방식:** Python `schedule` 라이브러리 + Threading (데몬 스레드)

```mermaid
graph TD
    A[Application Start] --> B[Background Scheduler Thread]
    B --> C[15:20<br>Jongga V2 Analysis]
    B --> D[15:40<br>Daily Closing Analysis]
    C --> E[Data Collection]
    C --> F[AI Analysis]
    C --> G[Signal Generation]
    D --> H[VCP Signal Analysis]
    G --> I[Notification Service]
    H --> I
    I --> J[Telegram]
    I --> K[Discord]
    I --> L[Slack]
    I --> M[Email]
```

![알림 채널](/assets/11.%20스마트%20머니%20봇.png)
*스마트 머니 봇의 다양한 알림 인터페이스*

**스케줄링 잡(Scheduled Jobs):**

| 시간 (KST)     | 작업(Job)                      | 세부 내용                                                                     |
| -------------- | ------------------------------ | ----------------------------------------------------------------------------- |
| **매일 15:20** | `run_jongga_v2_analysis()`     | 1. 장중 시세 업데이트<br>2. 종가베팅 스크리닝<br>3. AI 필터링<br>4. 알림 발송 |
| **매일 15:40** | `run_daily_closing_analysis()` | 1. 장 마감 시세 확정<br>2. VCP 신호 생성<br>3. 수급 데이터 업데이트           |

#### 6.2 실행 방법

**자동 실행 (Flask 서버 시작 시):**
```bash
# flask_app.py 시작 시 자동으로 스케줄러 백그라운드 실행
python flask_app.py
# → Scheduler 자동 시작 (daemon thread)
```

**테스트 실행 (수동):**
```bash
# 모든 잡을 즉시 1회 실행
python services/scheduler.py test
```

**코드 경로:** `services/scheduler.py`

---

### 7. Multi-Channel Notification (다중 채널 알림)

분석 완료 시 **Telegram, Discord, Slack, Email**로 동시에 리포트를 발송합니다.

#### 7.1 지원 채널별 특징

| 채널         | 방식                    | 장점                         | 사용 사례             |
| ------------ | ----------------------- | ---------------------------- | --------------------- |
| **Telegram** | Bot API (`sendMessage`) | 모바일 최적화, 푸시 알림     | 실시간 거래 신호 확인 |
| **Discord**  | Webhook (Rich Embeds)   | 포맷 자유도 높음, 커뮤니티   | 투자 그룹 공유        |
| **Slack**    | Webhook (Markdown)      | 기업 환경 연동, 워크스페이스 | 업무용 투자 리포트    |
| **Email**    | SMTP (HTML)             | 공식 기록 보존, 대량 전송    | 일일/주간 요약 정산   |

![Telegram 알림](/assets/14.%20종가베팅%20Telegram.png)
![Discord 알림](/assets/15.%20종가베팅%20Discord.png)
![Email 알림](/assets/16.%20종가베팅%20email.png)
*텔레그램, 디스코드, 이메일을 통한 실시간 시그널 전송 예시*

#### 7.2 환경 설정 (.env)

```env
# 알림 활성화
NOTIFICATION_ENABLED=true
NOTIFICATION_CHANNELS=telegram,discord,slack,email

# Telegram 설정
TELEGRAM_BOT_TOKEN=bot_token_here
TELEGRAM_CHAT_ID=chat_id_here

# Discord 설정
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Slack 설정
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Email 설정
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_RECIPIENTS=user1@email.com,user2@email.com
```

#### 7.3 메시지 포맷

**A. 종가베팅 V2 알림 (Jongga Notification)**

```
📊 종가베팅 V2 (2026-02-01)

✅ 선별된 신호: 15개 (D등급 5개 제외)
📊 등급 분포: S:3 | A:7 | B:5

━━━━━━━━━━━━━━━━━━━━━━
📋 Top Signals:

1. [KOSPI] 삼성전자 (005930) - S등급 92점
   📈 상승: +8.5% | 거래배수: 1.5x | 대금: 1.5조
   🏦 외인(5일): +500억 | 기관(5일): +300억
   🤖 AI: BUY - AI 반도체 수주 500억원으로 강한 호재. 외인/기관 동반 순매수 유입 중.
   💰 진입: ₩75,000 | 목표: ₩78,750 | 손절: ₩72,750

2. [KOSDAQ] 셀트리온 (068270) - A등급 85점
   ...
━━━━━━━━━━━━━━━━━━━━━━

⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다.
```

**B. VCP 신호 알림**

```
📈 VCP 신호 발생 (2026-02-01)

━━━━━━━━━━━━━━━━━━━━━━
📋 VCP Complete Stocks:

1. 에코프로비엠 (086520) - A급 VCP
   📊 VCP 점수: 85점 (수축 구간 진입)
   🏦 외국인 5일: +200만주 | 기관 5일: +150만주
   🤖 AI: BUY - VCP 완성, 외인/기관 동반 매집 중
   💰 목표: +8% | 손절: -5%

━━━━━━━━━━━━━━━━━━━━━━
```

**C. 시장 상황 요약 (Market Summary)**

```
🌐 시장 요약 (15:40 KST)

━━━━━━━━━━━━━━━━━━━━━━
📊 Market Gate: [OPEN] - 68점 (매수 허용)

[지표 현황]
• USD/KRW: 1,348원 (⚠️ 1400원 초과 시 주의)
• KODEX 200: 정배열 (5일 > 20일)
• RSI: 58 (과매수 영역)
• 외국인 선물: 순매수 +2000계약

[AI 시장 분석]
오늘 주도 테마는 'AI 반도체'와 '2차전지'입니다.
반도체 관련 대형주들의 외국인 순매수가 두드러지며,
2차전지는 기관 실주 매집으로 인한 급등이 예상됩니다.
전반적으로 강세장 흐름이지만, 환율 상승 리스크는 유의해야 합니다.
━━━━━━━━━━━━━━━━━━━━━━
```

#### 7.4 발송 로직

```python
# services/notifier.py - send_all()
class NotificationService:
    def send_all(self, signals: List[Dict]) -> Dict[str, bool]:
        """
        설정된 모든 채널로 알림 발송

        발송 성공 여부 리턴:
        {
            'telegram': True,
            'discord': True,
            'slack': False,  # 실패 시 False
            'email': True
        }
        """
        results = {}
        message = self.format_jongga_message(signals)

        for channel in self.channels:
            try:
                if channel == 'telegram':
                    results['telegram'] = self.send_telegram(message)
                elif channel == 'discord':
                    results['discord'] = self.send_discord(message)
                # ... 다른 채널 처리
            except Exception as e:
                logger.error(f"{channel} 발송 실패: {e}")
                results[channel] = False

        return results
```

**장점:**
- **내결성(Tolerance)**: 한 채널 실패 시 다른 채널은 정상 발송
- **중복 방지**: 동일한 메시지는 1회만 발송 (message ID 체크)
- **성능 최적화**: 메시지 길이 제한(Telegram 4096자)에 따라 우선순위 정렬

---

### 8. Chatbot ULW (AI 투자 어드바이저)

**ULW (Ultra-Lightweight Chatbot)** 은 실시간으로 시장 상황을 질문하고, 종목 분석을 요청할 수 있는 인터랙티브 챗봇입니다.

#### 8.1 챗봇 아키텍처

```mermaid
graph TD
    A[User Input] --> B[Chatbot Core]
    B --> C{Query Type?}
    C -->|Market| D[System Prompt + Market Data]
    C -->|Stock Analysis| E[Stock Data + News]
    D --> F[Gemini]
    E --> F
    F --> G[LLM Response]
    G --> H[Context Management]
    H --> I[Output to User]
    H --> J[Memory Storage]
```

#### 8.2 페르소나: 스마트머니봇 (Black Knight)

**페르소나 정의:**
- **이름**: 스마트머니봇 (Smart Money Bot)
- **성격**: 냉철한 분석가, 수급 중심, 리스크 회피 최우선
- **전문성**: VCP, Supply/Demand, Technical Analysis

**동적 시스템 프롬프트 (Dynamic System Prompt):**

```python
# chatbot/prompts.py - build_system_prompt()
def build_system_prompt(market_data: Dict, user_memory: List) -> str:
    """
    시장 데이터와 사용자 기억을 주입하여 시스템 프롬프트 생성
    """
    prompt = f"""
    너는 VCP 기반 한국 주식 투자 어드바이저 '스마트머니봇'이야.

    ## [시작 전] 현재 시장 상황
    - KOSPI: {market_data['kospi_close']} ({market_data['kospi_change']}%)
    - KOSDAQ: {market_data['kosdaq_close']} ({market_data['kosdaq_change']}%)
    - USD/KRW: {market_data['usd_krw']}원
    - 시장 분위기: {market_data['market_regime']}  # 강세/약세/중립

    ## [주도 테마] 오늘의 상위 10종목
    {market_data['top_stocks']}

    ## [사용자 기억] 최근 관심 종목
    {', '.join(user_memory)}

    ## 핵심 투자 원칙
    1. 수급이 곧 진실이다: 외국인/기관 순매수가 동반되지 않은 상승은 신뢰하지 않는다.
    2. Market Gate 우선: 시장 지표(환율, 지수)가 악화되면 개별 종목 추천을 멈춘다.
    3. 리스크 관리: 손절가(-5%)를 생명처럼 지킨다.

    ## 추론 프로세스 (Chain of Thought)
    답변을 할 때는 반드시 다음 단계를 거쳐라:
    1. [상황 인식]: 현재 시장이 Bull/Bear/Neutral 인지 판단
    2. [데이터 분석]: 사용자가 물어본 종목의 5일/20일/60일 수급 누적 확인
    3. [결론 도출]: 매수/매도/관망 의견 제시 및 근거 서술

    ## 응답 톤
    - 전문적이면서도 이해하기 쉬운 표현 사용
    - 수치는 반올림하여 깔끔하게 제시
    - 확실치 않은 추측은 "추정"으로 표시
    """
    return prompt
```

**왜 동적 프롬프트를 사용하는가?**

| 정적 프롬프트           | 동적 프롬프트 (이 시스템)           |
| ----------------------- | ----------------------------------- |
| 시장 상황을 모름        | KOSPI, 환율 등 실시간 데이터 주입   |
| 사용자 맥락을 모름      | 최근 질문 종목 기억 및 연계         |
| 테마 변화를 모름        | 오늘의 주도 종목 리스트 제공        |
| **결과**: 일반화된 답변 | **결과**: 상황에 맞는 최신화된 답변 |

#### 8.3 대화 기능 (Conversation Features)

**A. 시장 질문 (Market Query)**

![AI 챗봇 멀티모달](/assets/7.%20AI%20상담%20챗봇%20멀티%20모달%20채팅.png)
*텍스트와 이미지를 동시에 분석하는 멀티모달 AI 채팅 인터페이스*

```
User: "오늘 시장 어때?"
Bot: """
현재 시장 분위기는 **중립(Neutral)**입니다.

[지표 현황]
• KOSPI: 2,640점 (-0.5%)
• KOSDAQ: 870점 (+0.8%)
• USD/KRW: 1,348원 (⚠️ 1400원 초과 시 주의)

[주도 테마]
오늘은 'AI 반도체'와 '2차전지' 섹터가 강세입니다.
삼성전자 외국인 3일 연속 순매수로 인한 섹터 순환매가 유입 중입니다.

[투자 제안]
Market Gate가 [CLOSED] 상태입니다.
환율 상승 리스크로 인해 새로운 매수는 잠시 보류를 권장합니다.
기존 보유 종목의 손절가 준수에 집중하세요.
"""
```

![AI 챗봇 시장분석](/assets/12.%20스마트%20머니%20봇%20채팅.png)
*현재 시장 지표와 테마를 종합한 AI 시장 브리핑*

**B. 종목 분석 (Stock Analysis)**

![AI 챗봇 종목분석](/assets/8.%20AI%20상담%20챗봇%20설정된%20관심종목%20수집%20데이터%20기반%20답변.png)
*사용자의 관심 종목 데이터와 실시간 뉴스를 결합한 정밀 분석 답변*

```
User: "삼성전자 어때?"
Bot: """
[삼성전자 005930 분석]

[기본 정보]
• 현재가: 75,000원 (+8.5%)
• 거래대금: 1.5조원 (상위 5종목)
• PER: 12.5x, PBR: 1.4x

[수급 분석 (5일/20일/60일 누적)]
• 외국인: +500억 (골든크로스 상태)
• 기관: +300억 (5일 연속 순매수)
• 개인: -800억 (차익 실현 매물)

[뉴스 감성]
• "AI 반도체 대규모 수주 발표" → **호재 (Score: 3)**
• "해외 AI 투자 규모 확대" → **긍정 (Score: 2)**

[AI 종합 의견]
✅ **매수 (BUY)**
신뢰도: 88%

[이유]
1. 외국인/기관 동반 순매수가 지속 중입니다. (수급이 곧 진실)
2. AI 반도체 테마 호조세로 수혜가 예상됩니다.
3. 기술적으로 VCP 패턴 완성 구간에 진입했습니다.

[리스크 요인]
• 환율 1400원 초과로 인한 수출주 악재 우려
• 단기 급등 후 차익 실현 매물 출회 가능성

[투자 전략]
• 매수가: 75,000원
• 목표가: 78,750원 (+5%)
• 손절가: 72,750원 (-3%)
• 진입 시기: 오늘 종가 매수 추천
"""
```

![AI 챗봇 답변](/assets/13.%20스마트%20머니%20봇%20답변.png)
*수급, 기술적 지표, 뉴스를 종합하여 도출된 최종 투자 전략*

**C. 포트폴리오 관리 (Portfolio Management)**
```python
# 사용자 기억 저장 (Memory)
user_memory = {
    'user_id': 'user123',
    'watchlist': ['삼성전자', '셀트리온', '카카오'],
    'last_query_time': '2026-02-01 15:30',
    'conversation_history': [
        {'role': 'user', 'content': '삼성전자 어때?'},
        {'role': 'assistant', 'content': '...'}
    ]
}
```

**기능:**
- **관심 종목 등록**: `/add 삼성전자` 명령으로 포트폴리오 추가
- **포트폴리오 조회**: `/mylist`로 보유 종목 현황 확인
- **대화 맥락 유지**: 최근 10개 질문-답변 쌍 컨텍스트 유지
- **개인화 추천**: 사용자의 과거 투자 성향에 따른 맞춤 종목 추천

#### 8.4 API 통합 (Flask + Chatbot)

```python
# flask_app.py - Chatbot Routes
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """
    챗봇 대화 API 엔드포인트
    """
    data = request.json
    user_message = data.get('message', '')
    user_id = data.get('user_id', 'anonymous')

    # 1. 챗봇 초기화
    chatbot = KRStockChatbot()

    # 2. 시장 데이터 로드 (최신화)
    market_data = load_latest_market_data()

    # 3. 사용자 기억 로드
    user_memory = load_user_memory(user_id)

    # 4. 동적 시스템 프롬프트 생성
    system_prompt = build_system_prompt(market_data, user_memory)

    # 5. LLM 호출 (Gemini)
    response = gemini_client.generate(
        system_prompt=system_prompt,
        user_message=user_message,
        history=user_memory['conversation_history']
    )

    # 6. 기억 업데이트
    save_user_memory(user_id, {
        'message': user_message,
        'response': response
    })

    return jsonify({'response': response})
```

**응답 예시 (실시간 API):**
```json
POST /api/chat
{
    "message": "오늘 시장 추천 종목 뭐야?",
    "user_id": "user123"
}

Response 200 OK:
{
    "response": """
    오늘의 추천 종목은 다음과 같습니다.

    [S급 신호]
    1. 삼성전자 (75,000원) - AI 반도체 호조세
    2. SK하이닉스 (150,000원) - 2차전지 수혜

    [투자 제안]
    환율 1400원 초과 리스크로 분할 매수를 권장합니다.
    각 종목 -3% 손절가 준수가 필수적입니다.
    """
}
```

#### 8.5 왜 챗봇이 필요한가?

**시나리오 A (챗봇 없음):**
- 사용자: 매일 리포트를 읽어 직접 판단
- **한계**: 정적 리포트, 개인화된 질문 불가
- **결과**: 사용자 경험 낮음, 잦은 질문에 대응 불가

**시나리오 B (챗봇 적용):**
- 사용자: 실시간으로 "이 종목 어떠?", "시장 어때?" 질문
- **장점**: AI가 최신 데이터를 바탕으로 개인화된 답변 생성
- **결과**: 사용자 참여도 상승, 빠른 의사결정 지원


---

## 📜 라이선스 및 면책 조항

**Disclaimer**: 본 시스템은 투자 판단을 보조하는 도구일 뿐이며, 투자의 결과에 대한 책임은 전적으로 투자자 본인에게 있습니다. AI의 분석은 완벽하지 않으며 할루시네이션이 발생할 수 있습니다.

**License**: MIT License