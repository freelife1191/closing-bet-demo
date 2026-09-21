# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Smart Money Bot: AI 기반 종가 베팅 & VCP 시그널 시스템**

AI-powered Korean stock market analysis system combining institutional flow analysis with VCP (Volatility Contraction Pattern) technical analysis. Uses hybrid AI approach (Gemini 3.7 Flash, GPT via Z.ai, Perplexity) with Flask backend and Next.js dashboard.

**Live Demo**: https://close.highvalue.kr/dashboard/kr

---

## Development Commands

### Quick Start (All-in-One)
```bash
./restart_all.sh    # Automated setup: venv, deps, port cleanup, start both services
./stop_all.sh        # Stop all services on ports 3500 and 5501
```

### Python Backend
```bash
# Environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Entry points
python run.py                    # Interactive menu (6 options)
python flask_app.py              # Flask server on port 5501

# Production
# 바인딩은 loopback 이다. 이유는 .env.example 의 FLASK_HOST 주석에 있다
gunicorn flask_app:app --bind 127.0.0.1:5501 --workers 2 --threads 8 --timeout 120

# Testing
pytest                          # All tests
pytest tests/test_vcp.py        # Specific file
pytest -v                       # Verbose
```

### Next.js Frontend
```bash
cd frontend
npm install
npm run dev                     # Port 3500
npm run build                   # Production build
npm run lint                    # ESLint
npm run type-check              # TypeScript check (tsc --noEmit)
npm run test                    # Vitest tests (run once and exit)
npm run test:watch              # Vitest watch mode
npm run test:coverage           # Coverage report
```

---

## Architecture Overview

### System Flow
```
Data Layer → Engine Layer (Modular) → AI Core Layer → Service Layer
```

### Refactored Modular Structure (SOLID Principles)

**Core Refactored Modules** (use these patterns for new code):
- `engine/constants.py` - All magic numbers/thresholds centralized (dataclass)
- `engine/phases.py` - Signal generation 4-phase pipeline (SRP)
- `engine/data_sources.py` - Strategy pattern for data fetching
- `engine/error_handler.py` - Standardized error handling decorators
- `engine/exceptions.py` - Custom exception hierarchy
- `engine/pandas_utils.py` - DataFrame operations, NaN handling
- `engine/llm_utils.py` - LLM retry logic decorators

**Phase Pipeline** (phases.py):
```python
Phase1Analyzer: Base analysis & pre-screening
Phase2NewsCollector: News collection
Phase3LLMAnalyzer: AI batch analysis
Phase4SignalFinalizer: Signal generation
SignalGenerationPipeline: Orchestrator
```

### Design Patterns to Follow

1. **Strategy Pattern** (data_sources.py): Abstract data source with FDR/pykrx/yfinance implementations
2. **Single Responsibility**: Each Phase class has one job
3. **Decorator Pattern**: `@handle_data_error`, `@async_retry_with_backoff`
4. **Template Method**: `BasePhase` with `execute()` template

### Constants Usage (engine/constants.py)
```python
from engine.constants import TRADING_VALUES, VCP_THRESHOLDS, SCORING, VOLUME, PRICE_CHANGE

TRADING_VALUES.S_GRADE      # 1조
TRADING_VALUES.MINIMUM      # 500억
VCP_THRESHOLDS.CONTRACTION_RATIO  # 0.7
SCORING.MIN_S_GRADE         # 15점
VOLUME.RATIO_MIN            # 2.0
PRICE_CHANGE.MIN            # 5%
```

---

## Key Files

### Entry Points
- `flask_app.py` - Flask application entry (port 5501)
- `run.py` - Interactive CLI menu
- `chatbot/` - AI chatbot package (`chatbot/core.py` is the orchestrator)

### Configuration
- `.env` - Environment variables (API keys, ports). `.env.production`, `.env.vertex`
  hold real secrets too; `.gitignore` covers `.env.*` with `.env.example` as the only exception.
- `.env.example` - The tracked reference for every variable. Update it when adding one.
- `config.py` - Main configuration (dataclass-based)
- `engine/config.py` - Engine-specific config

### Flask Routes (Blueprint-based)
- `app/__init__.py` - Application factory
- `app/routes/kr_market.py` - Korean market API
- `app/routes/common.py` - Common API routes

---

## Code Style

### Python
- File header: `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`
- Imports: stdlib → third-party → local (blank line separated)
- Type hints: Always include `List`, `Dict`, `Optional`
- Dataclasses: Use `field(default_factory=list)` for mutable defaults
- Logging: `logger = logging.getLogger(__name__)` at module level
- Numeric: Use underscores: `1_000_000_000`

### TypeScript/React
- Client components: `'use client';` at top
- Functional components with hooks
- Define interfaces for all data structures

---

## Code Philosophy — ponytail

Code work, reviews, and tests in this repo default to ponytail rules. Where the
ponytail plugin is installed, its SessionStart hook injects the full ruleset
automatically (flag file: `~/.claude/.ponytail-active`), so this section carries
only the repo-specific reading of it — and keeps it available where the plugin
is not installed.

**The ladder** — stop at the first rung that holds, before writing new code:
1. Does this need to exist at all? (YAGNI)
2. Does this repo already have it? Check `engine/constants.py`,
   `engine/pandas_utils.py`, `engine/error_handler.py`, `engine/llm_utils.py`
   before writing a new helper.
3. Does stdlib or an already-installed dependency (pandas, pykrx) cover it?
4. Only then: the minimum code that works.

**Relation to "Design Patterns to Follow" above**: that list applies when
*modifying modules that already use those structures*, not as a mandate to
introduce them in new code. No interface with one implementation, no config for
a value that never changes, no scaffolding "for later". Items under "Remaining
Refactoring Tasks" start when a real problem is observed, not preemptively.

**Bug fixes hit root cause**: one guard in the shared function beats a guard in
every caller. `grep` the callers before editing.

**Tests**: any branch, loop, parser, or signal/scoring decision leaves one
runnable check behind. Follow the existing `tests/**/test_*_refactor.py`
pattern; do not add a new framework or fixture layer. Trivial one-liners need
no test.

**Deliberate shortcuts**: when leaving a known ceiling in place, mark it —
`# ponytail: global lock, per-account locks if throughput matters`.

---

## Environment Variables

Required for AI functionality:
```bash
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
PERPLEXITY_API_KEY=your_perplexity_key
ZAI_API_KEY=your_zai_key

# Models — see .env.example for the authoritative list
GEMINI_MODEL=gemini-3.7-flash            # chatbot / bulk pre-analysis
ANALYSIS_GEMINI_MODEL=gemini-3.7-flash   # Phase 3 synthesis
VCP_GEMINI_MODEL=gemini-3.7-flash        # VCP signal analysis
CHATBOT_AVAILABLE_MODELS=gemini-3.5-flash-lite,gemini-3.7-flash,gemini-3.6-flash
```

Ports and data source:
```bash
FLASK_PORT=5501
FRONTEND_PORT=3500
DATA_SOURCE=krx
SCHEDULER_ENABLED=true
```

`ADMIN_API_TOKEN` 은 `/api/system/env` 의 관리자 게이트가 쓰는 서버 전용 값입니다. Next.js
라우트 핸들러가 NextAuth 세션으로 관리자를 확인한 뒤 이 토큰을 붙여 Flask 로 넘기고, Flask 는
그 토큰만 확인합니다. **비어 있으면 그 경로는 모든 요청을 403 으로 막습니다.** `.env` 와
`.env.production` 양쪽에 각각 두며 `NEXT_PUBLIC_` 접두사를 붙이지 않습니다. 붙이면 브라우저
번들에 실려 게이트가 무의미해집니다.

**이 토큰은 만료도 폐기 목록도 없는 순수 소지 비밀입니다.** `ADMIN_EMAILS` 에서 어떤 관리자를
지워도 토큰 값을 아는 사람은 loopback 으로 Flask 에 직접 요청해 그대로 통과합니다.

**두 게이트의 차이는 폐기 수단이 하나인가 둘인가입니다.** `services/admin_helpers.py` 의
`is_admin_email` 은 「이 사람이 누구인가」를 보고 `verify_admin_api_token` 은 「이 값을
아는가」만 봅니다. 둘 다 매 요청 `os.environ` 을 읽지만, **그 `os.environ` 을 바꾸는 수단은
워커 재기동 하나뿐입니다.** `ADMIN_EMAILS` 와 `ADMIN_API_TOKEN` 은 둘 다
`services/common_env_service.py` 의 `EDITABLE_ENV_KEYS` **밖**이라 설정 화면으로 바꿀 수
없고(관리자가 화면에서 자기 자신을 잠그는 것을 막으려는 의도적 설계입니다), `.env` 파일을
손으로 고쳐도 돌고 있는 워커에는 반영되지 않습니다.

그런데 `ADMIN_EMAILS` 에는 **두 번째 폐기 수단이 있습니다.** 그 사람의 NextAuth 로그인을
끊으면 `frontend/src/proxy.ts` 가 매 요청 `getToken` 으로 세션을 확인하므로 **재기동 없이
즉시 듣습니다.** `ADMIN_API_TOKEN` 뒤에는 계정이 없어 그 길이 없고, 값을 바꾸고 모두
재기동하는 것 외에는 막을 방법이 없습니다. 그래서 관리자를 내보낼 때는 `ADMIN_EMAILS` 에서
지우는 것만으로 끝나지 않고 이 토큰도 함께 돌려야 합니다.

**`[INFRA-042]` 이후로는 `INTERNAL_IDENTITY_SECRET` 이 더 넓은 것을 지킵니다.** 관리자
전용으로 닫은 라우트 열둘의 판정이 그 키로 서명된 신원에 걸려 있으며, 그 안에 구독자에게
실제 메시지를 보내는 경로가 들어 있습니다. 이 키가 새면 서명을 위조해 그 전부를 통과할 수
있으므로, 회전 대상을 `ADMIN_API_TOKEN` 하나로 좁혀 생각하지 않습니다.

`frontend/src/lib/identity.ts` 의 `IDENTITY_TTL_SECONDS`(120 초)를 폐기 수단으로 오해하지
않습니다. 그것은 **서명의 신선도만 정하며 인가와 무관합니다.** 만료되면
`frontend/src/proxy.ts` 가 NextAuth 세션으로 다시 서명하는데, 그 경로는 `ADMIN_EMAILS` 를
보지 않습니다.

`[INFRA-062]`부터 신원 헤더는 `v2.<이메일 base64url>.<만료 시각>.<HMAC>` 형식입니다.
HMAC은 이 버전·이메일·만료와 실제 HTTP 메서드, 한 번 decode한 API pathname을 함께
검증합니다. Next proxy와 Flask가 각각 관측한 요청을 사용하므로 다른 경로나 메서드로
옮긴 서명은 인증되지 않습니다. 구형 3-part 서명은 허용하지 않습니다.

경로에는 `/api/`가 포함되고 query·본문은 포함되지 않습니다. 같은 메서드·경로의 재전송을
막는 nonce 저장소는 두지 않습니다. TTL과 내부 비밀 보호는 계속 필요합니다.
Next와 Flask는 같은 릴리스로 적용해야 합니다. 구형·신형 워커를 섞으면 정상 로그인 요청도
검증에 실패할 수 있으며, 호환성을 위해 구형 서명을 다시 허용하지 않습니다.


회전 절차입니다. 순서를 지키지 않으면 관리자 화면이 그 사이 동안 막힙니다.

1. 새 값을 만듭니다. `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. `.env` 와 `.env.production` **양쪽**의 `ADMIN_API_TOKEN` 을 새 값으로 바꿉니다. 한쪽만
   바꾸면 배포 환경에 따라 갈립니다.
3. **Flask 워커를 모두 재기동합니다.** `verify_admin_api_token` 은 부를 때마다 `os.environ` 을
   읽지만, `.env` 파일을 고치는 것은 **이미 돌고 있는 워커의 `os.environ` 을 바꾸지
   않습니다.** 그 값을 채우는 것은 기동 시점의 `load_dotenv()` 한 번뿐입니다. 설정 화면도
   길이 아닙니다. `ADMIN_API_TOKEN` 은 `EDITABLE_ENV_KEYS` 밖이라 그 화면으로 바꿀 수
   없습니다. 재기동 외에 다른 수단이 없습니다.
4. **Next 쪽도 재기동합니다.** 라우트 핸들러는 `process.env` 를 부를 때마다 읽지만
   (`frontend/src/app/api/system/env/route.ts` 의 `resolveAdminToken`), 그 `process.env` 를
   루트 `.env` 에서 채우는 것은 기동 시점 한 번뿐입니다. `[INFRA-055]`의 npm 실행기는
   루트 설정을 자식 환경으로 전달하므로 dev/start 모두 루트 설정 변경 후 재기동해야 합니다.
5. 관리자 화면의 설정 모달을 열어 값이 읽히는지 확인합니다. 403 이 나면 3번이나 4번이 덜
   끝난 것입니다.

**`INTERNAL_IDENTITY_SECRET` 도 같은 4단계로 돌리되 실패의 파급이 훨씬 큽니다.**
`ADMIN_API_TOKEN` 을 잘못 돌리면 관리자 설정 화면만 403 이 되지만, 이 키가 Flask 와 Next
사이에서 어긋나면 `verify_identity_header` 가 모든 요청에 `None` 을 돌려주므로 **모든
사용자의 신원이 익명으로 떨어집니다.** 관리자 화면만이 아니라 챗봇 소유자 판정과 쿼터 키도
함께 무너집니다. 두 값이 같은 `.env` 에 나란히 있으므로, 한쪽이 샜다고 판단해 회전에 들어가는
상황이면 다른 쪽도 샜다고 보고 함께 돌립니다.

**회전을 장 중에 하지 않습니다.** 재기동 자체는 발송을 일으키지 않습니다.
`_bootstrap_scheduler_after_lock_acquired` 가 `schedule.every(...)` 로 **다음** 실행 시각만
잡고 놓친 잡을 따라잡는 갈래가 없어, 17시를 지나 재기동해도 그날의 종가 분석이 다시 돌지
않습니다. 다만 재기동은 `isRunning` 을 강제로 내리므로 **백그라운드 갱신이 도는 중에
재기동하면 그 작업이 죽고 상태만 초기화됩니다.**

설정 화면에서 자격 증명을 바꿔도 **요청을 처리한 워커의 `os.environ` 만 바뀝니다.**
`services/notifier.py` 와 `engine/messenger_config.py` 는 객체를 만들 때 `os.getenv` 로
값을 읽으므로, 워커가 둘 이상이면 나머지 워커는 재기동 전까지 옛 값을 계속 씁니다. 유출된
키를 이 화면으로 교체했다면 반드시 워커를 모두 재기동해야 실제로 바뀝니다.

`VCP_AI_PROVIDERS` 와 `VCP_SECOND_PROVIDER`, 그리고 `PERPLEXITY_API_KEY` 의 유무는
`VCPMultiAIAnalyzer` 가 만들어질 때 한 번 읽혀 두 번째 AI 프로바이더를 확정합니다. 확정한
값은 실행 경로와 재분석 캐시 판정이 함께 씁니다. 그래서 `.env` 에서 이 값을 바꾸면 워커를
모두 재기동해야 반영됩니다. gunicorn 이 워커별로 이 값을 따로 확정하므로, 일부 워커만
재기동하면 같은 요청이 어느 워커에 닿느냐에 따라 다르게 동작합니다.

---

## Important Notes

1. **Ports**: Flask 5501, Next.js 3500
2. **Logs**: `logs/backend.log`, `logs/frontend.log`
3. **Data sources**: two separate fallback chains. Period data goes through `DataSourceManager` (FDR → pykrx → yfinance); single-ticker realtime quotes go through `fetch_stock_price` (Toss → Naver → yfinance)
4. **Market Gate GET은 저장 자료만 조회합니다.** `[INFRA-047]`부터 최신·과거 조회 모두
   외부 분석이나 백그라운드 갱신을 시작하지 않습니다. 날짜는 유효한 YYYY-MM-DD/
   YYYYMMDD만 허용하며 잘못된 값은 파일 조회 전에400으로 거부합니다. 유효 저장값·스냅샷 또는 데이터 없음
   응답을 반환합니다. 갱신은 관리자 `POST /api/kr/market-gate/update`와 스케줄러가 담당합니다.
   이전 GET 전용 쿨다운 코드도 제거했습니다. 기존 원본 잠금 파일을 삭제하지는 않습니다.
   포트폴리오 가격 동기화는 scheduler lock을 획득한 bootstrap에서 시작합니다.
   리더는 매분 가격 루프 시작을 재확인해 기동 실패나 종료 후 복구합니다.
   `SCHEDULER_ENABLED=false`이면 자동 가격 동기화도 시작하지 않습니다. 비리더 워커의
   포트폴리오 조회는 공유 SQLite 가격을 읽으며 외부 조회를 시작하지 않습니다.
   GET의 기존 계정 초기화·자산이력 기록은 유지하므로 완전한 DB 무쓰기 계약은 아닙니다.
5. **Scheduler**: `services/scheduler.py`가 업무 잡 두 개와 분당 가격 동기화 복구 잡 하나를 등록합니다. Market Gate 동기화는 `MARKET_GATE_UPDATE_INTERVAL_MINUTES`(코드 기본값 30분) 간격으로 돌고, 장 마감 분석은 `CLOSING_SCHEDULE_TIME`(기본 17:00 KST) 에 하루 한 번 돌며 종가베팅은 그 체인 안에서 이어집니다. 관련 모듈: `scheduler_jobs.py`, `scheduler_loop.py`, `scheduler_runtime_status_service.py`
6. **Tests**: pytest (Python), vitest (TypeScript)
7. **루트 `AGENTS.md`**: codex 처럼 `AGENTS.md` 만 자동으로 읽는 도구의 진입점입니다.
   그 도구들은 이 파일을 읽지 않으므로 `AGENTS.md` 가 첫 절에서 이 파일을 먼저 읽도록
   지시합니다. 규범과 아키텍처는 이 파일에만 두고 `AGENTS.md` 에는 진입 방법과 코드
   작성 규칙만 둡니다. 같은 내용을 양쪽에 적으면 반드시 어긋납니다.
8. **`frontend/AGENTS.md` 와 `frontend/CLAUDE.md`**: `next dev` 가 실행될 때마다
   자동으로 만들고 되살리는 파일입니다. Next.js 16.2 부터 생긴 동작이며 공식 문서가
   커밋을 권합니다. 지우면 다음 실행에서 그대로 다시 생겨 작업 트리가 더러워지므로
   지우지 않습니다. `frontend/CLAUDE.md` 는 `@AGENTS.md` 한 줄이며, 그 지침은 이 파일을
   대체하지 않고 `frontend/` 아래 작업에 덧붙습니다. 내용은 설치된 Next.js 버전에 맞는
   문서를 `node_modules/next/dist/docs/` 에서 읽으라는 안내입니다.

---

## 개발 사이클 — dev-cycle

작업은 `docs/dev-cycle/TODO.md` 의 항목 단위로 진행합니다.
`/dev-cycle next` 로 시작하며, 절차와 티어 규칙은 스킬 정의를 따릅니다.

- 백로그: `docs/dev-cycle/TODO.md` (단일 관리 지점)
- 완료 기록: `docs/dev-cycle/archive/` (월별 요약 + 일별 상세)
- QA 시나리오: `docs/dev-cycle/qa/` (항목별 검사 목록과 실행 결과)
- 사이클 절차: `.claude/skills/dev-cycle/SKILL.md`
- 티어와 위험 경로: `.claude/skills/dev-cycle/references/tier-rules.md`
- 기록 형식: `.claude/skills/dev-cycle/references/archive-format.md`
- 프론트엔드 스킬 매핑: `.claude/skills/dev-cycle/references/frontend-skills.md`
- 브라우저 실측 요령: `.claude/skills/dev-cycle/references/browser-notes.md`
- 카테고리 감사: `dev-workflow` 에이전트. 리포트는 `docs/dev-cycle/audits/` 에 남깁니다

`frontend/` 를 건드리는 작업은 프론트엔드 스킬 매핑을 먼저 읽습니다. 어느 스킬을 쓸지는
[1] 설계와 계획에서 건드릴 파일 목록을 뽑을 때 함께 정하고, 고른 스킬 이름을 계획 보고에 적습니다.
`frontend/src/app` 아래를 하나라도 고치면 `frontend/node_modules/next/dist/docs/01-app/`
아래에서 해당 주제의 문서를 예외 없이 읽습니다. 종전에 여기 적혀 있던
`next-best-practices` 스킬은 상류에서 폐지되어 그 지식이 이 번들 문서로 옮겨졌습니다.
나머지는 파일에 무엇이 들어 있는지로 갈리며 매핑 문서 §2 에 표로 정리되어 있습니다.
Next.js 관련 스킬 네 개가 16.3 을 하한선으로 두고 있었으나 `[FE-002]` 가 16.3.4 로 올려
그 문턱을 해소했습니다.

새 TODO 라운드는 `superpowers:brainstorming`으로 설계하고 그 경로의 승인을 받은 뒤
구현합니다. 이미 승인된 동일 범위의 구현·리뷰·검증·커밋과 재개는 다시 승인을 기다리지 않고
진행합니다. 상태 조회와 읽기 전용 감사, QA 재시도는 새 설계 라운드가 아닙니다. 승인 기록은
실제 사용자 대화와 범위를 확인하기 위한 근거이며 파일의 주장 자체가 승인은 아닙니다.

사이클은 Claude Code 와 codex 양쪽에서 돕니다. 절차와 판정 기준은 같고 부르는 리뷰·QA
도구의 이름만 다릅니다. 대응표는 스킬 정의의 `## 실행 환경` 절에 있으며, 없는 도구를
부르며 멈추지 않고 그 표가 정한 대체 수단으로 같은 판정을 내립니다.

Codex의 `$security-review`는 보안 범위를 전달한 독립 `code-reviewer`를 사용합니다.
현재 OMX에서 deprecated인 `security-reviewer` 역할을 호출하지 않습니다. 독립 검토가
불가능하면 미완료로 기록하며, 시크릿 정적 검사만으로 보안 리뷰 통과를 대신하지 않습니다.

oh-my-claudecode 플러그인은 계획 검토와 보안 리뷰 보강 두 자리에서만 사이클에 들어오며, 그
대응표도 같은 `## 실행 환경` 절에 있습니다. 이 플러그인의 키워드 감지기는
프롬프트의 「코드 리뷰」·「보안 리뷰」와 `tdd`·`ralph`·`autopilot`·`ralplan` 에 반응해
자체 모드를 켭니다. 사이클은 그 모드를 쓰지 않으므로 켜졌다는 안내가 보이면
`/oh-my-claudecode:cancel` 로 끄고 절차를 이어갑니다.

실행 코드를 바꾸는 항목은 QA 시나리오 계획과 실행을 거칩니다. Claude Code는 기존
`/qa-only`와 `/qa`, Codex는 두 단계 모두 `$ultraqa`를 사용합니다. Codex의 행렬·반복
한도·App 대응은 `.claude/skills/dev-cycle/references/ultraqa.md`를 따릅니다. 문서·테스트만
바꾸는 작업은 원칙적으로 동적 QA 제외 대상이지만 사용자가 실제 검증을 명시하면 수행합니다.
Codex는 기존 화면에 연결된 API·인증·데이터 변경도 agent-browser로 실측합니다.
판정 기준은 frontend 파일 변경 여부가 아니라 사용자 진입 흐름입니다. UltraQA 행렬에
화면 조작·요청·결과·스크린샷 증거를 남기며, 필수 브라우저 검증 불가는 BLOCKED입니다.
자세한 기준은 위 ultraqa.md §1-1을 따릅니다.
정적 검증 후 첫 커밋에서도 TODO를 유지하며, 필수 QA·정리가 통과한 최종 아카이브 커밋에서만
항목을 제거합니다. 필수 실패·차단·미실행은 완료로 이월하지 않습니다. 과거 기록은 보존합니다.

권장 압축 지점은 QA 구간 진입 직전과 사이클 완료 직후입니다. 연속 진행을 요청받았다면
불필요하게 중단하지 않습니다. 재개는 승인 근거·해당 항목의 변경·QA 증거를 먼저 대조합니다.
진행 항목에 속하는 dirty diff는 이어가며 다른 작업의 변경은 보존합니다. 새 설계의 승인
미완료나 필수 검증 실패 한도·권한 부재에서는 그 상태와 다음 단계를 기록하고 멈춥니다.

**QA 계획·실행·결과 기록은 가능하면 한 문맥에서 이어갑니다.** 앞 단계에서 읽은 값이 뒤 단계의 기대값이
되므로 중간에서 끊으면 그 출처를 되짚느라 오히려 맥락을 더 씁니다. **리뷰 하나를 마친
자리와 검증 명령 하나를 돌린 자리도 압축 지점이 아닙니다.** 리뷰 스킬이 리포트를 산출하면
할 일이 끝난 것처럼 보이지만, 사이클에서 리포트는 결과물이 아니라 다음 단계의 입력입니다.
압축 지점의 근거와 복구 방법은 스킬 정의의 `## 컨텍스트 관리와 재개` 절에 있습니다.

TODO 에 없는 작업을 즉흥으로 시작하지 않습니다. 새로 발견한 개선점은
`TODO.md` 에 항목으로 추가한 뒤 순서에 따라 처리합니다. 이 파일에 할 일 목록을
따로 적지 않습니다. 백로그가 두 곳에 존재하면 반드시 어긋납니다.


`[INFRA-056]`부터 관리자 Market Gate 주기 변경은 공통 `resolve_env_path`가 정한
루트 `.env`에 `MARKET_GATE_UPDATE_INTERVAL_MINUTES`를 저장합니다. 일반 설정 저장과
동일한 `.env.lock`으로 읽기·원자적 교체·요청 워커 적용을 직렬화합니다. 파일이 없으면
주기 키만 가진0600 파일을 만들고, 다른 키·여러 줄 값·줄바꿈은 보존합니다. 대상 키의
중복은 한 줄로 정규화하며 파싱 오류·파일/잠금 링크는 거부합니다.

읽기·파싱·교체 실패 시 런타임을 바꾸지 않습니다. 교체 뒤 적용 콜백이 실패하면 파일은
새 값으로 남고 요청은 오류가 됩니다. 디스크 롤백은 하지 않습니다. 실제 스케줄러 갱신은
종전처럼 실패를 로그에 남기는 best-effort이며, 스케줄러를 소유한 워커에서만 적용됩니다.
다른 워커의 메모리까지 즉시 전파하지 않으며 다음 프로세스 기동은 저장한 값을 읽습니다.


### Next 실행 환경 분리 — INFRA-055

`frontend`에서 `npm run dev`, `npm run build`, `npm run start`를 사용합니다.
세 명령은 `scripts/run-next.js`를 거쳐 Next를 실행하며 `restart_all.sh`도 같은 경계를
사용합니다. `npx next`나 Next 바이너리 직접 실행은 이 필터를 거치지 않습니다.

실행기는 부모 환경의 애플리케이션 값을 우선하고, frontend의 활성 환경 파일, 루트의
활성 환경 파일 순으로 빠진 값을 채웁니다. 각 디렉터리 안에서는 Next의
`.env.<mode>.local` → `.env.local` → `.env.<mode>` → `.env` 순서입니다.
`dev`는 development, `build/start`는 production으로 `NODE_ENV`를 고정합니다.
루트 `.env.vertex`는 읽지 않습니다. 값은 셸 코드로 실행하지 않고 설치된 Next env 파서로
읽습니다. 별도의 비밀 복사 파일을 만들지 않습니다.

Google 로그인, NextAuth URL/secret, 관리자 목록·토큰, 내부 신원 secret, API URL처럼
실제 Next가 쓰는 키와 명시한 프로세스 실행 변수만 자식에게 전달합니다. 실행용 변수는
부모 프로세스에서만 받으며 루트 환경 파일에서 채우지 않습니다. 정확한 허용 목록은
실행기에 있습니다. `ADMIN_API_TOKEN`과 `INTERNAL_IDENTITY_SECRET`은 Next 서버에도
필요하며 공개 키가 아닙니다. SMTP·LLM·알림 등의 백엔드 전용 키는 부모 환경에 있어도
Next 자식으로 전달하지 않습니다. 임의의 `NEXT_PUBLIC_*`나 `NODE_OPTIONS`도 전달하지
않습니다. 이 필터는 Next 자식의 환경 경계이며 실행기 자체가 시작되기 전의 부모 Node
초기화 옵션까지 차단하는 기능은 아닙니다.

변수 확장 전 참조도 검사합니다. 애플리케이션 값은 허용된 애플리케이션 키만 참조할 수
있으며, `NEXT_PUBLIC_*` 값은 허용된 공개 키만 참조할 수 있습니다. 따라서 공개 값의
`$ADMIN_API_TOKEN` 참조나 애플리케이션 값의 `$SMTP_PASSWORD` 참조는 기동 전에
거부됩니다. 숫자로 시작하는 참조도 같은 기준을 적용합니다. `$$`나 이스케이프된 변수
참조처럼 재확장 때 다른 이름을 만들 수 있는 표현은 거부하고, 비참조 `$()` 같은 문자와
안전한 정적 참조만 허용합니다. 공개 변수에 비밀 문자열을 직접 붙여 넣은 경우까지
자동 식별하지는 않습니다.

기존 `frontend/.env -> ../.env` 링크만 사전 검사가 끝나면 제거합니다. 다른 링크나
일반 파일을 임의로 덮어쓰지 않습니다. 활성 frontend 환경 파일에 허용하지 않은 키가
있거나 환경 입력이 일반 파일이 아니면 Next를 시작하지 않습니다. 설정을 추가·변경할 때는
실행기를 다시 거쳐야 합니다. 실행 중 frontend 파일을 편집하는 동작을 지속 감시하는
보안 장치로 해석하지 않습니다.

`.next`는 no-follow로 연 디렉터리의 파일 디스크립터를 통해 권한을 `0700`으로 좁히고
기존 캐시를 보존합니다. `O_NOFOLLOW`·`O_DIRECTORY`를 지원하지 않는 플랫폼은
안전 플래그를 생략하지 않고 기동을 거부합니다.
필요한 Next 서버 인증키는 private compiler cache에 남을 수 있으므로 이 권한 보호는
계속 필요합니다. 예전에 생성된 캐시의 삭제나 실행 중 운영 프로세스 재시작은 이 라운드가
수행하지 않았습니다. 새 환경은 다음 명시적 실행부터 적용됩니다.

## 감사 IP와 지원 배포 경계

`[INFRA-045]`의 감사 IP는 Flask가 직접 관측한 연결 상대(`remote_addr`)입니다.
활동 로그·화면 이벤트 로그·챗봇 로그 모두 `X-Forwarded-For`를 신뢰하지 않습니다.
프록시 뒤에서는 프록시 주소일 수 있으며 실제 사용자 주소로 해석하지 않습니다.
`[INFRA-046]`에서 Flask만 공개하던 Procfile을 제거했습니다. 지원 운영은 Next와
loopback Flask 두 프로세스입니다. 별도 PaaS 구성을 만들거나 실제 배포를 변경하지 않습니다.
