# AGENTS.md

**Smart Money Bot: AI 기반 종가 베팅 & VCP 시그널 시스템**

기관 수급 분석과 VCP(변동성 수축 패턴) 기술적 분석을 결합한 한국 주식 시장 분석
시스템이다. Flask 백엔드와 Next.js 대시보드로 이루어져 있고, 추론에는 Gemini 와
Z.ai 계열 모델을 함께 쓴다.

**라이브**: https://close.highvalue.kr/dashboard/kr

---

## 이 파일의 자리

`AGENTS.md` 를 자동으로 읽는 도구(codex 등)의 진입점이다. **이 저장소의 규범 자체는
`CLAUDE.md` 에 있다.** 세션을 시작하면 `CLAUDE.md` 를 먼저 읽는다. codex 는 그 파일을
자동으로 읽지 않으므로 읽지 않으면 규범을 통째로 놓친다.

역할을 이렇게 나눈다. 규범과 아키텍처와 사이클 규정은 `CLAUDE.md` 한 곳에만 두고, 이
파일에는 진입 방법과 코드 작성 규칙만 둔다. 같은 내용을 두 파일에 적으면 반드시 어긋나기
때문이다.

읽는 순서는 다음과 같다.

1. `CLAUDE.md` — 규범, 아키텍처, ponytail 원칙, 환경 변수, 사이클 개요
2. `.claude/skills/dev-cycle/SKILL.md` — 작업을 시작하기 전에. `## 실행 환경` 절이 지금
   환경에서 부를 수 있는 도구의 이름을 정한다
3. `SKILL.md` 의 `[S] status` 절차 — 최근 완료 3건과 진행 중 사이클과 다음 항목을 이
   절차로 파악한다. 대화 맥락이 없는 새 세션이 어디까지 왔는지를 잡는 자리다. 무엇을
   할지는 `docs/dev-cycle/TODO.md` 에서만 고른다

---

## 개발 사이클

작업은 `docs/dev-cycle/TODO.md` 의 항목 단위로 진행한다. **TODO 에 없는 작업을 즉흥으로
시작하지 않는다.** 새로 발견한 개선점은 항목으로 추가한 뒤 순서에 따라 처리한다.

| 문서 | 내용 |
|---|---|
| `.claude/skills/dev-cycle/SKILL.md` | 사이클 절차. `[0]` 준비부터 `[4]` 마감까지 |
| `.claude/skills/dev-cycle/references/tier-rules.md` | 티어 판정, 위험 경로, QA 2단계 |
| `.claude/skills/dev-cycle/references/archive-format.md` | TODO·아카이브·QA 문서 형식 |
| `.claude/skills/dev-cycle/references/frontend-skills.md` | `frontend/` 를 건드릴 때만 |
| `.claude/agents/dev-workflow.md` | 카테고리 감사 에이전트 정의 |

**codex 에서는 `$dev-cycle` 로 부른다.** 저장소의 `.agents/skills/dev-cycle` 링크가
기존 `.claude/skills/dev-cycle/` 을 가리키므로 위 표의 문서가 계속 정본이다.
현재 스킬 목록(`/skills` 를 제공하는 환경이면 그 목록)에 `dev-cycle` 이 없으면
`docs/dev-cycle/codex-setup.md` 를 읽고 연결을 점검한다. 링크가 정상이지만 현재 세션에
노출되지 않으면 위 문서를 직접 읽고 절차를 수행하며, 자동 탐색 확인과 구분해 기록한다.

사이클이 부르는 리뷰와 QA 도구는 환경에 따라 있기도 하고 없기도 하다. 대응표는 `SKILL.md`
의 `## 실행 환경` 절에 있다. 없는 도구를 부르며 멈추지 말고 그 표가 정한 대체 수단으로
같은 판정을 내린 뒤, 무엇으로 대신했는지 마감 보고에 적는다.

새 TODO 라운드는 `superpowers:brainstorming` 설계·승인을 거친다. 승인된 동일 범위의
구현·리뷰·검증·커밋과 재개는 자동으로 이어간다. Codex QA는 `$ultraqa`를 사용하며,
실행 환경 대응은 `.claude/skills/dev-cycle/references/ultraqa.md`를 읽는다.
필수 검증이 미통과이면 TODO를 유지하고 완료 아카이브를 만들지 않는다.

---

## 명령

```bash
./restart_all.sh                 # venv·의존성·포트 정리까지 하고 두 서비스를 띄운다
./stop_all.sh                    # 3500 과 5501 을 내린다
```

검증은 세 가지를 쓴다. 세 명령의 실행 위치가 서로 다르므로 그대로 옮겨 쓴다.

```bash
source venv/bin/activate && pytest       # 저장소 루트에서 실행한다
(cd frontend && npx vitest run)          # npm run test 는 watch 모드라 끝나지 않는다
(cd frontend && npm run type-check)      # tsc --noEmit
```

`cd frontend` 를 서브셸로 감싸는 이유가 있다. 감싸지 않으면 셸의 작업 디렉터리가 바뀐 채
남아 뒤따르는 명령이 엉뚱한 위치에서 돈다. `npx vitest --root frontend` 도 쓰지 않는다.
설정 파일의 경로 해석이 어긋나 다수가 실패한다.

```bash
python run.py                    # 대화형 메뉴
python flask_app.py              # Flask 개발 서버 (5501)
cd frontend && npm run dev       # Next.js 개발 서버 (3500)

gunicorn flask_app:app --bind 0.0.0.0:5501 --workers 2 --threads 8 --timeout 120
```

**gunicorn 은 `--reload` 없이 돈다.** 파이썬 파일을 고쳤으면 QA 전에
`kill -HUP <마스터 PID>` 로 워커를 재기동해야 반영된다.

생존 확인 경로는 `/api/kr/market-gate` 다. `/api/health` 는 존재하지 않는다.

---

## 코드 스타일

### Python

파일 머리에 `#!/usr/bin/env python3` 와 `# -*- coding: utf-8 -*-` 를 둔다.

임포트는 표준 라이브러리 → 서드파티 → 로컬 순서로 쓰고 사이를 빈 줄로 나눈다.

```python
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from engine.models import StockData
from engine.config import config
```

- 이름: 클래스 `PascalCase`, 함수와 변수 `snake_case`, 상수 `UPPER_SNAKE_CASE`
- 타입 힌트: 인자와 반환값에 모두 붙인다
- 데이터클래스: 가변 기본값에 `field(default_factory=list)` 를 쓴다
- Enum: 키는 영어, 값은 한국어를 섞어 쓴다. `class Grade(Enum): S = "S"  # 최고`
- 로깅: 모듈 수준에 `logger = logging.getLogger(__name__)`
- 예외: `continue` 나 `return` 이나 `raise` 앞에서 반드시 로그를 남긴다
- 숫자: 자릿수를 밑줄로 끊는다. `1_000_000_000`
- 비동기: LLM 호출과 I/O 에 `async`/`await` 를 쓰고 `asyncio.run()` 으로 실행한다

임계값과 상수는 `engine/constants.py` 에 모여 있다. 새 상수를 파일 안에 직접 쓰기 전에
그곳을 먼저 본다.

```python
from engine.constants import TRADING_VALUES, VCP_THRESHOLDS, SCORING, VOLUME, PRICE_CHANGE
```

### TypeScript / React

클라이언트 컴포넌트는 첫 줄에 `'use client';` 를 둔다. 임포트는 React·Next.js → 외부
라이브러리 → 로컬 컴포넌트 순서로 쓴다.

- 이름: 컴포넌트 `PascalCase`, 함수와 변수 `camelCase`, 상수 `UPPER_SNAKE_CASE`
- 모든 데이터 구조에 인터페이스를 정의한다. props 와 state 를 모두 포함한다
- 함수형 컴포넌트와 훅을 쓴다
- 스타일은 Tailwind 유틸리티 클래스로 준다

`frontend/src/app` 아래를 하나라도 고치면
`frontend/node_modules/next/dist/docs/01-app/` 에서 그 주제의 문서를 예외 없이 읽는다.
어느 문서를 읽을지는 `frontend-skills.md` §2 의 표가 정한다.

`frontend/AGENTS.md` 와 `frontend/CLAUDE.md` 는 `next dev` 가 실행될 때마다 자동으로
만들고 되살리는 파일이다. 지우면 다음 실행에서 그대로 다시 생겨 작업 트리가 더러워지므로
지우지 않는다. 그 지침은 이 파일을 대체하지 않고 `frontend/` 아래 작업에 덧붙는다.

---

## 하지 않을 것

- **타입 억제**: `as any`, `@ts-ignore`, `@ts-expect-error` 를 쓰지 않는다
- **빈 except**: 로그 없는 `except:` 를 쓰지 않는다
- **테스트 손질**: 실패하는 테스트를 통과하도록 고쳐 넘기지 않는다. 지우는 기준은
  `SKILL.md` 의 `## 테스트 정책` 에 있다
- **경로 하드코딩**: `os.path` 와 `__file__` 을 쓴다
- **패턴 혼용**: 주변 코드의 관례를 따른다

---

## 되돌릴 수 없는 조작

검증이나 실측을 하다가 아래를 실행하면 실제 비용이 발생하거나 데이터가 사라진다. 사용자가
그 자리에서 명시적으로 요청하지 않는 한 실행하지 않는다.

**이 절의 제약은 서브에이전트를 띄울 때 프롬프트에 함께 넣는다.** 서브에이전트는 이 파일을
자동으로 읽지 않으므로, 「읽기 전용으로 작업하라」는 지시만으로는 부족하다. 파일을 고치지
않아도 `curl` 로 돌고 있는 서버에 요청을 보내면 아래 조작이 그대로 실행된다. 실행 중인
서버를 건드릴 수 있는 에이전트에게는 **어느 포트에 무엇이 떠 있고 어떤 메서드를 보내면
안 되는지**를 명시한다. 2026-09-07 `[INFRA-025]` 사이클에서 보안 리뷰 에이전트가 실측 중
`DELETE /api/system/env` 를 보냈고, 그때 서버가 이미 새 코드여서 405 로 거부된 덕분에
파괴적 핸들러에 닿지 않았다. 옛 코드가 떠 있었다면 `.env` 의 자격 증명이 비워지고
`data/` 의 사용자 자료가 지워졌을 요청이다.

**같은 사이클에서 인과를 성급하게 단정한 일도 함께 남긴다.** `.env` 의 자격 증명 11개가
비워진 것을 발견하고 시각이 가깝다는 이유만으로 그 에이전트의 요청을 원인으로 지목해
사용자에게 보고했는데, `logs/user_activity.log` 와 `logs/critical_errors.log` 를 읽어 보니
그 요청은 405 였고 성공한 DELETE·POST 는 한 건도 없었다. **자료가 사라진 것을 발견하면
먼저 활동 로그와 오류 로그에서 실제 요청 기록을 확인한다.** `logs/backend.log` 는
`restart_all.sh:80` 이 `>` 로 덮어쓰므로 재기동 이전 기록이 남지 않는다는 것도 함께 안다.

**대신 대조로 확정할 수 있는 것은 대조한다.** 위 건은 지워진 키 집합을 옛
`FACTORY_RESET_SENSITIVE_KEYS` 와 맞춰 보아 `reset_sensitive_env_and_user_data` 가
실행되었음을 특정했다. 값이 있던 대상 11개가 전부, 그리고 그것만 비워져 있었다. 어느
요청이 그것을 불렀는지는 접근 기록이 없어 재구성할 수 없지만, 무엇이 실행되었는지는
자료의 모양만으로 좁혀진다. 「기록에 없음」과 「일어나지 않음」을 구분한다.

- **`.env` 계열 파일**: `.env`, `.env.production`, `.env.vertex` 가 실제 시크릿을 담고
  있다. `.gitignore` 가 `.env.*` 를 덮고 `.env.example` 만 예외다. 조사할 일이 생기면
  변수 이름과 값의 유무만 확인하고 값 자체는 어디에도 옮겨 적지 않는다. 변수의 정본
  목록은 `.env.example` 이며 변수를 추가하면 그 파일도 함께 갱신한다
- **설정 모달의 「저장」**: 프로필과 환경 변수와 관심종목을 한꺼번에 저장하며, 환경 변수
  저장은 `POST /api/system/env` 로 서버의 `.env` 를 덮어쓴다. `[INFRA-025]` 이후 이
  경로는 관리자 전용이고 대상은 화면이 쓰는 12개 키(`EDITABLE_ENV_KEYS`)로 제한된다.
  비관리자에게는 그 탭 자체가 보이지 않으므로 「저장」은 프로필과 관심종목만 바꾼다
- **AI 재분석 버튼**: 종가베팅 화면의 「스크리너 전체 업데이트」와 「GEMINI AI 재분석」,
  카드마다 있는 「이 종목만 재분석」, VCP 화면의 「실패 AI 재분석」과 「Refresh VCP」
- **「Refresh Market Gate Only」**: 7일치 수급을 재수집해 3.7MB CSV 와 JSON 을 덮어쓴다
- **챗봇 전송**: 「보내기」, 입력창의 Enter, 추천 질문 카드, 하단 빠른 조회 버튼, 슬래시
  명령이 모두 실제 LLM 호출과 무료 사용량 차감을 일으킨다
- **모의투자**: 「계정 초기화」, 「모의 매수」, 「전체 10주 매수」, 충전 팝오버의
  「충전하기」가 잔고 상태를 바꾼다
- **삭제 계열**: 대화 삭제, 메시지 삭제, 「새 대화 시작」, 챗봇의 `/clear all`. 확인
  모달이 뜨면 「취소」만 누른다
- **`data/` 아래 파일**: git 추적 대상이 아니다. 실측할 때는 읽기 전용으로만 연다

---

## 어디를 볼 것인가

| 대상 | 위치 |
|---|---|
| 설정 | `config.py`, `engine/config.py`, `.env`(정본 목록은 `.env.example`) |
| 진입점 | `run.py`, `flask_app.py` |
| 엔진 | `engine/` (screener, models, phases, constants, market_gate) |
| AI 통합 | `engine/llm_analyzer.py`, `engine/kr_ai_analyzer.py` |
| 챗봇 | `chatbot/` (`chatbot/core.py` 가 오케스트레이터) |
| 데이터 모델 | `engine/models.py` |
| Flask 라우트 | `app/routes/` (Blueprint), 팩토리는 `app/__init__.py` |
| 스케줄러 | `services/scheduler.py` 와 `scheduler_jobs.py`, `scheduler_loop.py` |
| 테스트 | `tests/` (pytest), `frontend/src` (vitest) |
| 프론트엔드 | `frontend/src/app/` (App Router) |
| 데이터 저장 | `data/` (CSV·JSON), `data/paper_trading.db` (SQLite) |
| 로그 | `logs/backend.log`, `logs/frontend.log` |

---

## 이 저장소의 특징

- **이중 AI**: Gemini 가 심층 추론을, Z.ai 와 Perplexity 가 빠른 배치를 맡는다
- **Market Gate**: 종목 분석에 앞서 시장 전체를 먼저 판정한다
- **데이터 소스 이중화**: 기간 데이터는 `DataSourceManager`(FDR → pykrx → yfinance),
  단일 종목 실시간 시세는 `fetch_stock_price`(Toss → Naver → yfinance)로 서로 다른
  폴백 사슬을 탄다
- **한영 혼용**: Enum 의 키는 영어, 값은 한국어
- **벡터 연산**: 집계와 지표 계산에 pandas 와 numpy 를 쓴다
- **테스트**: 백엔드 pytest, 프론트엔드 vitest. 테스트 파일에서는
  `sys.path.insert(0, os.path.dirname(__file__))` 로 프로젝트 모듈을 임포트한다
