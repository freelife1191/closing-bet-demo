# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-09
**Type:** Korean Stock Market Analysis System (Python Flask + Next.js)

## OVERVIEW
AI-powered Korean stock market analysis system combining institutional flow analysis with VCP technical analysis. Uses Gemini 2.0 Flash and GPT via Z.ai for AI reasoning, Flask for backend API, and Next.js for dashboard UI.

## BUILD / LINT / TEST COMMANDS

### Python Backend
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Entry points
python run.py                    # Interactive menu with 6 options
python flask_app.py              # Flask server (port 5501)

# Testing with pytest
pytest                          # Run all tests
pytest tests/test_vcp.py        # Specific test file
pytest tests/test_vcp.py::test_function  # Specific function
pytest -v                       # Verbose output
pytest --cov=engine             # Coverage report (if pytest-cov installed)

# Interactive scripts
python scripts/init_data.py     # Initialize data
python tests/test_vcp.py 2026-01-30  # Test with specific date
python tests/test_vcp.py 2026-01-30 100  # Test with date + max stocks
```

### Next.js Frontend
```bash
cd frontend && npm install
npm run dev                     # Dev server (port 3500)
npm run build                   # Production build
npm run start                   # Production server
npm run lint                    # ESLint check

# Testing with vitest
npm run test                    # Run all tests
npm run test:ui                 # Interactive test UI
npm run test:coverage           # Run with coverage report
npm run test:baseline           # Run specific baseline tests

# Type checking
npm run type-check              # TypeScript type check (tsc --noEmit)

# Full upgrade check
npm run upgrade:check           # Run baseline tests + type-check + lint
```

## CODE STYLE GUIDELINES

### Python
**File Header:** `#!/usr/bin/env python3` + `# -*- coding: utf-8 -*-`

**Imports:** stdlib → third-party → local (separated by blank lines)
```python
import sys
import os
import logging

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from engine.models import StockData
from engine.config import config
```

**Naming:** Classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_SNAKE_CASE`

**Type Hints:** Always include `List`, `Dict`, `Optional`, return types
```python
def calculate(self, stock: StockData) -> tuple[ScoreDetail, ChecklistDetail, Dict]:
    ...
```

**Dataclasses:** Use `@dataclass` with `field(default_factory=list)` for mutable defaults
```python
@dataclass
class ChartData:
    opens: List[float] = field(default_factory=list)
    highs: List[float] = field(default_factory=list)
```

**Enums:** English key, Korean value: `class Grade(Enum): S = "S"  # 최고`

**Logging:** `logger = logging.getLogger(__name__)` at module level

**Error Handling:** Log exceptions before `continue`/`return`/`raise`
```python
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Failed: {e}")
    raise
```

**Numeric:** Use underscores: `1_000_000_000` (1조원), `50_000_000` (5천만원)

**Async:** Use `async/await` for LLM calls and I/O, `asyncio.run()` to execute

**Docstrings:** Triple quotes at module and class/function level
```python
"""
Engine - Scorer (12점 점수 시스템)
"""
def main():
    """메인 함수"""
```

### TypeScript / React
**Header:** `'use client';` at top for client components

**Imports:** React/Next.js → external libraries → local components
```typescript
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { createChart } from 'lightweight-charts';

import Modal from './Modal';
```

**Naming:** Components `PascalCase`, functions/variables `camelCase`, constants `UPPER_SNAKE_CASE`

**Interfaces:** Define for all data structures (props, state, etc.)
```typescript
interface StockChartProps {
  data: { date: string; open: number; high: number; low: number; close: number }[];
  ticker: string;
  vcpRange?: { enabled: boolean; firstHalf: number; secondHalf: number };
}
```

**Components:** Functional with hooks: `useState`, `useEffect`, `useRef`
```typescript
export default function StockChart({ data, ticker, vcpRange }: StockChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // effect logic
    return () => {
      // cleanup
    };
  }, [dependencies]);
}
```

**Client vs Server:** Mark client components with `'use client'` at top

**Styling:** Tailwind CSS utility classes

## WHERE TO LOOK

| Task           | Location                                                |
| -------------- | ------------------------------------------------------- |
| Configuration  | `config.py`, `.env`                                    |
| Entry Points   | `run.py`, `flask_app.py`                                |
| Core Engine    | `engine/` (screener, models, llm_analyzer, market_gate) |
| AI Integration | `engine/llm_analyzer.py`, `engine/kr_ai_analyzer.py`    |
| Data Models    | `engine/models.py`                                      |
| Flask Routes   | `app/` (Blueprint-based routing)                         |
| Testing        | `tests/` (pytest), `frontend/src` (vitest)                |
| Frontend       | `frontend/src/app/` (Next.js App Router)                  |
| Data Storage   | `data/` (CSV/JSON), `paper_trading.db` (SQLite)         |

## ANTI-PATTERNS

- **Type suppression:** Never `as any`, `@ts-ignore`, `@ts-expect-error`
- **Empty catch:** Never bare `except:` without logging
- **Deleting tests:** Never modify failing tests to pass
- **Hardcoded paths:** Use `os.path` and `__file__`
- **Mixed patterns:** Follow existing conventions

## UNIQUE STYLES

- **Dual AI:** Gemini 2.0 Flash (deep reasoning) + Z.ai/GPT/Perplexity (fast batch)
- **Market Gate:** Top-level market check before stock analysis
- **Korean-English Mix:** `class Grade(Enum): S = "S"  # 최고`
- **Dataclass config:** All config as typed dataclasses with defaults
- **Async LLM:** Non-blocking AI calls with `async/await`
- **Vectorized:** Pandas/numpy for performance
- **Vitest for frontend:** Using vitest instead of Jest for Next.js testing
- **Toss API priority:** Toss Securities API for real-time data, fallback to pykrx/yfinance

## ENVIRONMENT VARIABLES (.env)

```bash
# Flask
FLASK_DEBUG=false
FLASK_PORT=5501
FLASK_HOST=0.0.0.0

# Frontend
FRONTEND_PORT=3500

# AI Keys
GOOGLE_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
PERPLEXITY_API_KEY=your_perplexity_key
ZAI_API_KEY=your_zai_key

# Models
GEMINI_MODEL=gemini-2.0-flash
ANALYSIS_GEMINI_MODEL=gemini-2.0-flash
OPENAI_MODEL=gpt-4o
VCP_GEMINI_MODEL=gemini-flash-latest
VCP_GPT_MODEL=gpt-4o
VCP_PERPLEXITY_MODEL=sonar-pro

# Concurrency
LLM_CONCURRENCY=2
ANALYSIS_LLM_CONCURRENCY=1

# Data Source
DATA_SOURCE=krx
PRICE_CACHE_TTL=300
MARKET_GATE_UPDATE_INTERVAL_MINUTES=30

# Scheduler
SCHEDULER_ENABLED=true
```

## NOTES

- Flask on 5501, Next.js dev on 3500
- API keys required for AI functionality
- Logs written to `logs/app.log`
- Market data sources: pykrx, Toss Securities API (priority), yfinance
- Scheduler in `app/services/scheduler.py`
- Test framework: pytest (Python), vitest (TypeScript/React)
- Use `sys.path.insert(0, os.path.dirname(__file__))` in test files to import project modules
