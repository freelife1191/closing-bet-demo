# 🚀 Deployment Guide (Render & Vercel)

이 문서는 **Render (Backend)**와 **Vercel (Frontend)**에 프로젝트를 배포하는 상세 절차를 설명합니다.

---

## 1. 사전 준비 (Prerequisites)

1.  **GitHub 저장소 업로드**: 코드가 GitHub에 푸시되어 있어야 합니다.
2.  **API Key 준비**: `.env` 파일에 있는 키값들(`GOOGLE_API_KEY`, `OPENAI_API_KEY` 등)을 메모장에 준비해두세요.

---

## 2. Backend 배포 (Render)

Render는 파이썬 백엔드(Flask)를 무료/유료로 호스팅할 수 있는 클라우드 서비스입니다.

### 2.1 계정 생성 및 연결
1.  [Render.com](https://render.com/) 접속.
2.  **Sign up** 클릭.
    *   💡 **참고**: 구글 계정으로 가입/로그인해도 됩니다. 다만, **코드를 불러오기 위해** 나중에 GitHub 계정 연동(권한 부여) 과정이 반드시 필요합니다.
    *   가장 간편한 방법은 처음부터 **GitHub로 로그인**하는 것입니다.
3.  GitHub 권한 요청 시 승인 (저장소 접근 권한).

### 2.2 Web Service 생성
1.  Dashboard 우측 상단 **New +** 버튼 클릭 -> **Web Service** 선택.
2.  **Connect to a repository** 목록에서 이 프로젝트 저장소(`closing-bet-demo`) 선택. (안 보이면 `Configure account` 눌러서 권한 부여)

### 2.3 설정 입력
다음과 같이 설정합니다:

| 항목              | 입력값                            | 설명                                           |
| :---------------- | :-------------------------------- | :--------------------------------------------- |
| **Name**          | `closing-bet-backend`             | 원하는 이름                                    |
| **Region**        | `Oregon` or `Singapore`           | 가까운 곳 (무료 플랜은 지역 제한 있을 수 있음) |
| **Branch**        | `main`                            | 배포할 브랜치                                  |
| **Runtime**       | **Python 3**                      |                                                |
| **Build Command** | `pip install -r requirements.txt` | 패키지 설치                                    |
| **Start Command** | `gunicorn flask_app:app`          | 서버 실행                                      |
| **Plan Type**     | Free (또는 Hobby)                 | 무료는 15분 미사용 시 절전 모드됨              |

### 2.4 환경 변수 설정 (Environment Variables)
Render 대시보드에서 `Environment Variables` 섹션을 찾아 다음 변수들을 입력합니다.

#### 🔴 필수 입력 (Essential)
API 키와 핵심 엔진 작동을 위한 변수입니다.

| Key                  | 설명                                     | 비고                                    |
| :------------------- | :--------------------------------------- | :-------------------------------------- |
| `GOOGLE_API_KEY`     | Gemini 분석을 위한 필수 키               | 필수                                    |
| `PERPLEXITY_API_KEY` | 실시간 뉴스 검색(Sonar) 필수 키          | 필수                                    |
| `OPENAI_API_KEY`     | GPT 분석용 키                            | 선택 (Z.ai 사용 시 생략 가능)           |
| `VCP_AI_PROVIDERS`   | 사용할 AI 목록 (예: `gemini,perplexity`) | **중요** (선택한 AI에 따라 결과 달라짐) |
| `GEMINI_MODEL`       | 메인 분석에 사용할 구글 모델명           | 기본값: `gemini-flash-latest`           |

#### ⚙️ 시스템 로직 설정 (Recommended Tuning)
성능 최적화 및 분석 주기를 결정합니다. (입력하지 않으면 코드 내 기본값이 자동 적용됩니다.)

| Key                                   | 설명                                   | 추천값              |
| :------------------------------------ | :------------------------------------- | :------------------ |
| `MARKET_GATE_UPDATE_INTERVAL_MINUTES` | 지표 업데이트 주기 (분)                | `1` ~ `30`          |
| `ANALYSIS_LLM_CONCURRENCY`            | 동시 AI 요청 수 (Rate Limit 방지용)    | `1` (무료티어 추천) |
| `ANALYSIS_LLM_CHUNK_SIZE`             | 한 번에 분석할 종목 수                 | `2` ~ `5`           |
| `DATA_SOURCE`                         | 데이터 수집원 (`krx`, `naver`, `both`) | `krx` (정확도 우선) |
| `PRICE_CACHE_TTL`                     | 데이터 캐시 유지 시간 (초)             | `300` (5분)         |

#### 🟡 선택 입력 (Service & Notification)
> [!IMPORTANT]
> 아래 항목들은 **본인의 개인 채널**로 알림을 받고 싶을 때만 입력합니다. 타인의 정보를 입력하면 알림이 가지 않으므로, 반드시 본인이 생성한 Webhook 이나 Token을 사용하세요.

| Key                               | 설명                                     |
| :-------------------------------- | :--------------------------------------- |
| `DISCORD_WEBHOOK_URL`             | 본인의 디스코드 채널 웹후크 URL          |
| `TELEGRAM_BOT_TOKEN` / `_CHAT_ID` | 본인의 텔레그램 봇 토큰 및 채팅 ID       |
| `SMTP_USER` / `_PASSWORD`         | 알림 메일을 보낼 본인의 이메일 계정 정보 |

#### ⚪️ 무시해도 됨 (Auto-managed)
다음 값들은 배포 서비스가 자동 할당하므로 **절대 입력하지 마세요.**
*   `FLASK_PORT`, `FRONTEND_PORT`, `FLASK_HOST`, `LOG_FILE`, `FLASK_DEBUG`

**Create Web Service** 버튼 클릭하여 배포 시작.
> **완료 후 URL 복사**: 예) `https://closing-bet-backend.onrender.com`

---

## 3. Frontend 배포 (Vercel)

Vercel은 Next.js에 최적화된 호스팅 서비스입니다.

### 3.1 계정 생성 및 연결
1.  [Vercel.com](https://vercel.com/) 접속.
2.  **Sign Up**.
    *   💡 **참고**: Render와 마찬가지로 로그인 방식은 상관없으나, 프로젝트를 가져오기 위해 **Continue with GitHub**를 추천합니다.

### 3.2 프로젝트 생성
1.  Dashboard에서 **Add New...** -> **Project** 선택.
2.  **Import Git Repository**에서 GitHub 아이콘을 클릭하여 저장소를 연동합니다.
3.  프로젝트 저장소(`closing-bet-demo`) 옆의 `Import` 버튼 클릭.

### 3.3 설정 입력 (Configure Project)

*   **Framework Preset**: `Next.js` (자동 감지됨)
*   **Root Directory**: `Edit` 버튼 클릭 -> **`frontend`** 폴더 선택 -> 확인. (중요!)

### 3.4 환경 변수 설정 (Environment Variables) - **중요**
`Environment Variables` 섹션을 펼쳐서 입력합니다. **브라우저에서 접근 가능한 환경 변수는 반드시 `NEXT_PUBLIC_` 접두사가 필요합니다.**

| Key                            | Value                                      | 설명                                                  |
| :----------------------------- | :----------------------------------------- | :---------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`          | `https://closing-bet-backend.onrender.com` | **Render에서 받은 백엔드 URL** (끝에 슬래시 `/` 없음) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | `...`                                      | 구글 로그인 Client ID (콘솔에서 생성한 값)            |

> [!NOTE]
> `NEXT_PUBLIC_API_URL`은 프론트엔드가 백엔드 API를 호출할 때 사용됩니다. 이 값이 정확하지 않으면 404 에러가 발생합니다.

**Deploy** 버튼 클릭.

---

## 4. 최종 확인

1.  Vercel 배포가 완료되면 제공된 **Visit** 링크로 접속합니다.
2.  사이트가 로딩되는지 확인합니다.
3.  우측 상단 'Status' 또는 데이터가 로딩되는지 확인하여 백엔드 연결(`NEXT_PUBLIC_API_URL`)이 정상인지 테스트합니다.

---

### 💡 팁
*   **Render 무료 플랜**: 일정 시간 요청이 없으면 서버가 잠자기에 들어갑니다(Sleep). 첫 접속 시 30초~1분 정도 걸릴 수 있습니다.
*   **CORS 에러**: 만약 브라우저 콘솔에 CORS 에러가 뜬다면, 백엔드 코드(`flask_app.py` 또는 `app/__init__.py`)의 `CORS(app)` 설정이 모든 도메인(`*`)을 허용하는지 확인하세요. (현재 코드는 허용되어 있음)
