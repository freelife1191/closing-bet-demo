# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Smart Money Bot: AI 기반 종가 베팅 & VCP 시그널 시스템**

AI-powered Korean stock market analysis system combining institutional flow analysis with VCP (Volatility Contraction Pattern) technical analysis. Uses hybrid AI approach (Gemini 2.0 Flash, GPT via Z.ai, Perplexity) with Flask backend and Next.js dashboard.

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
- `.env` - Environment variables (API keys, ports)
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

## Environment Variables

Required for AI functionality:
```bash
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
PERPLEXITY_API_KEY=your_perplexity_key
ZAI_API_KEY=your_zai_key

GEMINI_MODEL=gemini-2.0-flash
ANALYSIS_GEMINI_MODEL=gemini-2.0-flash
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
4. **Scheduler**: `app/services/scheduler.py` (15:20, 15:40 KST)
5. **Tests**: pytest (Python), vitest (TypeScript)

---

## Remaining Refactoring Tasks

1. **Refactor market_gate.py** (HIGH): Extract 400-line `_get_global_data()` using `DataSourceStrategy`
2. **Refactor generator.py** (HIGH): Replace inline phase logic with `phases.py` classes
3. **Add type hints** (MEDIUM): Missing in many functions
