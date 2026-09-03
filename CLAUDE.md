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
gunicorn flask_app:app --bind 0.0.0.0:5501 --workers 2 --threads 8 --timeout 120

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
npm run test                    # Vitest tests
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
4. **Scheduler**: `services/scheduler.py` 가 잡 두 개를 등록합니다. Market Gate 동기화는 `MARKET_GATE_UPDATE_INTERVAL_MINUTES`(코드 기본값 30분) 간격으로 돌고, 장 마감 분석은 `CLOSING_SCHEDULE_TIME`(기본 17:00 KST) 에 하루 한 번 돌며 종가베팅은 그 체인 안에서 이어집니다. 관련 모듈: `scheduler_jobs.py`, `scheduler_loop.py`, `scheduler_runtime_status_service.py`
5. **Tests**: pytest (Python), vitest (TypeScript)
6. **`frontend/AGENTS.md` 와 `frontend/CLAUDE.md`**: `next dev` 가 실행될 때마다
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
- 카테고리 감사: `dev-workflow` 에이전트

`frontend/` 를 건드리는 작업은 프론트엔드 스킬 매핑을 먼저 읽습니다. Next.js 관련 스킬
가운데 네 개는 16.3 을 하한선으로 두고 있어서, 현재 버전인 16.1.6 에서는 호출할 수
없습니다. 이 제약과 해소 방법은 매핑 문서에 정리되어 있습니다.

승인 게이트를 두지 않습니다. 계획과 결과는 알리되 승인을 기다리지 않고 사이클을 끝까지
진행합니다. 커밋도 묻지 않고 진행하며, 무엇을 어떻게 반영했는지는 커밋한 뒤에 보고합니다.

멈추는 자리는 압축 지점 네 곳입니다. `/qa-only` 를 부르기 직전, `/qa` 를 부르기 직전,
T3 항목의 구현이 끝난 뒤, 그리고 사이클을 마친 직후입니다. 그 자리에서 턴을 끝내고 알리므로 `/compact` 를 실행하면
다음 턴에서 이어집니다. 그 밖에는 되돌릴 수 없어 사용자만 결정할 수 있는 사항을 만났을
때만 멈춥니다. 압축 지점의 근거와 복구 방법은 스킬 정의의 `## 컨텍스트 관리` 절에
있습니다.

TODO 에 없는 작업을 즉흥으로 시작하지 않습니다. 새로 발견한 개선점은
`TODO.md` 에 항목으로 추가한 뒤 순서에 따라 처리합니다. 이 파일에 할 일 목록을
따로 적지 않습니다. 백로그가 두 곳에 존재하면 반드시 어긋납니다.
