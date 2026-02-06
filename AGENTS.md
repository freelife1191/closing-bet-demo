# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-02
**Type:** Korean Stock Market Analysis System (Python Flask + Next.js)

## OVERVIEW
AI-powered Korean stock market analysis system combining institutional flow analysis with VCP technical analysis. Uses Gemini 2.0 Flash and GPT via Z.ai for AI reasoning, Flask for backend API, and Next.js for dashboard UI.

## BUILD / LINT / TEST COMMANDS

### Python Backend
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python run.py                    # Interactive menu
python flask_app.py              # Flask server (port 5501)

pytest                          # Run all tests
pytest tests/test_vcp.py        # Specific test file
pytest tests/test_vcp.py::test_function  # Specific function
pytest -v                       # Verbose output
pytest --cov=engine             # Coverage report

python scripts/init_data.py     # Initialize data
```

### Next.js Frontend
```bash
cd frontend && npm install
npm run dev                     # Dev server (port 3500)
npm run build                   # Production build
npm run start                   # Production server
npm run lint                    # ESLint
```

## CODE STYLE GUIDELINES

### Python
**File Header:** `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`

**Imports:** stdlib → third-party → local (separated by blank lines)

**Naming:** Classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_SNAKE_CASE`

**Type Hints:** Always include `List`, `Dict`, `Optional`, return types

**Dataclasses:** Use `@dataclass` with `field(default_factory=list)` for mutable defaults

**Enums:** English key, Korean value: `class MarketRegime(Enum): KR_BULLISH = "강세장"`

**Logging:** `logger = logging.getLogger(__name__)` at module level

**Error Handling:** Log exceptions before `continue`/`return`/`raise`

**Numeric:** Use underscores: `100_000_000` (1억원)

**Async:** Use `async/await` for LLM calls and I/O, `asyncio.run()` to execute

### TypeScript / React
**Header:** `'use client';` for client components

**Imports:** React/Next.js → external libraries → local components

**Naming:** Components `PascalCase`, functions/variables `camelCase`, constants `UPPER_SNAKE_CASE`

**Interfaces:** Define for all data structures

**Components:** Functional with hooks: `useState`, `useEffect`

**Client vs Server:** Mark client components with `'use client'` at top

## WHERE TO LOOK

| Task           | Location                                                |
| -------------- | ------------------------------------------------------- |
| Configuration  | `config.py`                                             |
| Entry Points   | `run.py`, `flask_app.py`                                |
| Core Engine    | `engine/` (screener, models, llm_analyzer, market_gate) |
| AI Integration | `engine/llm_analyzer.py`, `engine/kr_ai_analyzer.py`    |
| Data Models    | `engine/models.py`                                      |
| Flask Routes   | Check Blueprint imports in `flask_app.py`               |
| Testing        | `tests/` (pytest)                                       |
| Frontend       | `frontend/src/` (Next.js)                               |
| Data Storage   | `data/` (CSV/JSON)                                      |

## ANTI-PATTERNS

- **Type suppression:** Never `as any`, `@ts-ignore`, `@ts-expect-error`
- **Empty catch:** Never bare `except:` without logging
- **Deleting tests:** Never modify failing tests to pass
- **Hardcoded paths:** Use `os.path` and `__file__`
- **Mixed patterns:** Follow existing conventions

## UNIQUE STYLES

- **Dual AI:** Gemini 2.0 Flash (deep reasoning) + Z.ai/GPT (fast batch)
- **Market Gate:** Top-level market check before stock analysis
- **Korean-English Mix:** `MarketRegime.KR_BULLISH = "강세장"`
- **Dataclass config:** All config as typed dataclasses with defaults
- **Async LLM:** Non-blocking AI calls with `async/await`
- **Vectorized:** Pandas/numpy for performance

## ENVIRONMENT VARIABLES (.env)

```bash
FLASK_DEBUG=false
FLASK_PORT=5501
FLASK_HOST=0.0.0.0
LOG_LEVEL=INFO

GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
GEMINI_MODEL=gemini-flash-latest
OPENAI_MODEL=gpt-4o
```

## NOTES

- Flask on 5501, Next.js dev on 3500
- API keys required for AI functionality
- Logs written to `logs/app.log`
- Market data sources: pykrx, finance-datareader, yfinance
- Scheduler in `services/scheduler.py`
