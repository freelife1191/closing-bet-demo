# KR Market 종가베팅 V2

> VCP 패턴 + 수급 분석 기반 한국 주식 시장 분석 시스템

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📖 개요

**종가베팅 V2**는 마크 미너비니의 VCP(Volatility Contraction Pattern) 전략과 외국인/기관 수급 분석을 결합한 한국 주식 시장 분석 시스템입니다.

### 핵심 기능

- 🎯 **VCP 스크리너**: 변동성 수축 패턴 자동 감지
- 📊 **수급 분석**: 외국인/기관 순매수 60일 트렌드 추적
- 🚦 **Market Gate**: 섹터별 시장 강도 분석 (GREEN/YELLOW/RED)
- 🤖 **AI 챗봇**: Gemini 기반 투자 어드바이저
- 📈 **대시보드**: Apple Dark Mode 스타일 UI

---

## 🏗️ 프로젝트 구조

```
closing-bet-v2/
├── flask_app.py              # Flask 앱 엔트리포인트
├── run.py                    # CLI 실행 스크립트
├── config.py                 # 시스템 설정
├── models.py                 # 데이터 모델
├── screener.py               # VCP 스크리너
├── market_gate.py            # 시장 상태 분석
├── kr_ai_analyzer.py         # GPT+Gemini 듀얼 AI
├── requirements.txt
├── .env.example
│
├── app/                      # Flask 앱
│   ├── __init__.py
│   └── routes/
│       ├── kr_market.py      # KR 시장 API
│       └── common.py         # 공통 API
│
├── engine/                   # 핵심 분석 엔진
│   ├── generator.py          # 시그널 생성
│   ├── scorer.py             # 점수 계산
│   ├── collectors.py         # 데이터 수집
│   ├── llm_analyzer.py       # LLM 뉴스 분석
│   └── position_sizer.py     # 자금 관리
│
├── chatbot/                  # AI 챗봇
│   ├── core.py               # 메인 챗봇
│   ├── prompts.py            # 시스템 프롬프트
│   ├── memory.py             # 장기 메모리
│   └── history.py            # 대화 히스토리
│
├── scripts/
│   └── collect_data.py       # pykrx 데이터 수집
│
├── data/                     # 데이터 저장소
│
└── frontend/                 # Next.js 14 + Tailwind
    └── src/app/
        └── dashboard/kr/
            ├── page.tsx      # 메인 대시보드
            ├── vcp/          # VCP 시그널
            └── closing-bet/  # 종가베팅
```

---

## 🚀 시작하기

### 1. 환경 설정

```bash
# 레포지토리 클론
git clone <repository-url>
cd closing-bet-v2

# 환경변수 설정
cp .env.example .env
```

`.env` 파일 수정:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
```

### 2. 백엔드 설치 및 실행

```bash
# 가상환경 생성
python3.13 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate     # Windows

# Python 의존성 설치
pip install -r requirements.txt

# Flask 서버 실행
python flask_app.py
```

서버가 `http://localhost:5000`에서 시작됩니다.

### 3. 프론트엔드 설치 및 실행

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

대시보드가 `http://localhost:3500`에서 시작됩니다.

### 4. 데이터 수집 (선택)

```bash
# 가상환경 활성화
source venv/bin/activate  # macOS/Linux

# pykrx를 이용한 데이터 수집
pip install pykrx

python scripts/collect_data.py
```

> ⚠️ 최초 실행 시 전체 주식 데이터 수집에 시간이 소요됩니다.

---

## 📡 API 엔드포인트

### KR Market API

| Endpoint                       | 설명                    |
| ------------------------------ | ----------------------- |
| `GET /api/kr/market-gate`      | 시장 상태 (Market Gate) |
| `GET /api/kr/signals`          | VCP 시그널 목록         |
| `GET /api/kr/ai-analysis`      | AI 분석 결과            |
| `GET /api/kr/jongga-v2/latest` | 종가베팅 최신 결과      |
| `POST /api/kr/vcp-scan`        | VCP 스캔 실행           |
| `POST /api/kr/jongga-v2/run`   | 종가베팅 스캔 실행      |

### Chatbot API

| Endpoint                  | 설명           |
| ------------------------- | -------------- |
| `POST /api/chatbot/chat`  | 대화 요청      |
| `GET /api/chatbot/status` | 챗봇 상태 확인 |

---

## 🎯 주요 기능 상세

### VCP 스크리너 (`screener.py`)

**점수 구성 (100점 만점)**:
- 외국인 순매매량: 40점
- 기관 순매매량: 30점
- VCP 패턴 점수: 10점
- 쌍끌이 보너스: +10점

```python
from screener import SmartMoneyScreener

screener = SmartMoneyScreener()
signals = screener.scan(min_score=60)
```

### Market Gate (`market_gate.py`)

섹터 ETF 기반 시장 상태 분석:

| 상태     | 점수  | 의미                 |
| -------- | ----- | -------------------- |
| 🟢 GREEN  | 70+   | 강세장 - 공격적 진입 |
| 🟡 YELLOW | 40-69 | 중립 - 선택적 진입   |
| 🔴 RED    | 0-39  | 약세장 - 관망        |

### AI 챗봇 (`chatbot/`)

Gemini 기반 투자 어드바이저:

```python
from chatbot import KRStockChatbot

bot = KRStockChatbot(user_id="user_001")
response = bot.chat("오늘 뭐 살까?")
```

**주요 명령어**:
- `/memory view` - 저장된 정보 보기
- `/memory add 키 값` - 정보 저장
- `/clear` - 대화 초기화
- `/help` - 도움말

---

## 🖥️ 대시보드

### KR Market Overview
![Dashboard](docs/dashboard.png)

- **Market Gate**: 실시간 시장 상태
- **섹터 점수**: KOSPI 200 섹터별 강도
- **Today's Signals**: 오늘의 VCP 시그널
- **Performance**: 백테스트 승률

### VCP Signals
- 종목별 VCP 점수
- 외국인/기관 수급 현황
- AI 추천 (BUY/HOLD/SELL)

### Closing Bet V2
- 종가베팅 후보 종목
- 등급별 필터 (S/A/B)
- 뉴스 및 체크리스트

---

## ⚙️ 설정

### `config.py` 주요 설정

```python
# 스크리닝 조건
MIN_TRADING_VALUE = 100_000_000_000  # 최소 거래대금 (1000억)
MIN_CHANGE_PCT = 2.0                  # 최소 등락률 (2%)
MAX_CHANGE_PCT = 30.0                 # 최대 등락률 (30%)

# 포지션 관리
R_RATIO = 0.02        # 총자본의 2% 리스크
STOP_LOSS_PCT = 0.03  # 손절 3%
TAKE_PROFIT_PCT = 0.05  # 익절 5%
```

---

## 📋 의존성

### Python (requirements.txt)
```
flask>=3.0.0
flask-cors>=4.0.0
pandas>=2.0.0
numpy>=1.24.0
google-generativeai>=0.5.0
python-dotenv>=1.0.0
pykrx>=1.0.0
yfinance>=0.2.0
```

### Node.js (frontend/package.json)
```json
{
  "dependencies": {
    "next": "14.2.0",
    "react": "^18",
    "tailwindcss": "^3.4.1"
  }
}
```

---

## 📄 라이선스

MIT License

---

## 🤝 기여

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📞 문의

프로젝트 관련 문의사항은 Issue를 통해 남겨주세요.
