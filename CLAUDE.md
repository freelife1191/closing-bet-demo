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
- `chatbot.py` - AI chatbot entry

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

---

## Important Notes

1. **Ports**: Flask 5501, Next.js 3500
2. **Logs**: `logs/backend.log`, `logs/frontend.log`
3. **Data sources**: pykrx (default), Toss Securities API (priority for real-time), yfinance (fallback)
4. **Scheduler**: `services/scheduler.py` (15:20, 15:40 KST). 관련 모듈: `scheduler_jobs.py`, `scheduler_loop.py`, `scheduler_runtime_status_service.py`
5. **Tests**: pytest (Python), vitest (TypeScript)

---

## 개발 사이클 — dev-cycle

작업은 `docs/dev-cycle/TODO.md` 의 항목 단위로 진행합니다.
`/dev-cycle next` 로 시작하며, 절차와 티어 규칙은 스킬 정의를 따릅니다.

- 백로그: `docs/dev-cycle/TODO.md` (단일 관리 지점)
- 완료 기록: `docs/dev-cycle/archive/` (월별 요약 + 일별 상세)
- 사이클 절차: `.claude/skills/dev-cycle/SKILL.md`
- 티어와 위험 경로: `.claude/skills/dev-cycle/references/tier-rules.md`
- 기록 형식: `.claude/skills/dev-cycle/references/archive-format.md`
- 프론트엔드 스킬 매핑: `.claude/skills/dev-cycle/references/frontend-skills.md`
- 카테고리 감사: `dev-workflow` 에이전트

`frontend/` 를 건드리는 작업은 프론트엔드 스킬 매핑을 먼저 읽습니다. Next.js 관련 스킬
가운데 네 개는 16.3 을 하한선으로 두고 있어서, 현재 버전인 16.1.6 에서는 호출할 수
없습니다. 이 제약과 해소 방법은 매핑 문서에 정리되어 있습니다.

승인 게이트는 두 곳입니다. 계획이 확정되는 시점과 결과가 저장소에 반영되는 시점입니다.

TODO 에 없는 작업을 즉흥으로 시작하지 않습니다. 새로 발견한 개선점은
`TODO.md` 에 항목으로 추가한 뒤 순서에 따라 처리합니다. 이 파일에 할 일 목록을
따로 적지 않습니다. 백로그가 두 곳에 존재하면 반드시 어긋납니다.
