# 티어 판정 규칙

dev-cycle 의 리뷰와 검증 강도를 정하는 규칙이다. 판정은 계획 단계에서 하고, 구현 후
실제 diff 가 상위 티어에 해당하면 상향한다. 하향은 어떤 경우에도 하지 않는다.

## 1. 티어별 절차

| 티어 | 조건 | 리뷰 | 검증 |
|---|---|---|---|
| T1 | 변경 50줄 이하이고 위험 경로에 닿지 않는다 | `/simplify` | 변경 범위의 pytest 또는 vitest |
| T2 | 변경 300줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` → `/simplify` → `/code-review` | pytest·vitest 전체 + agent-browser 로 변경 화면 실측 |
| T3 | 변경 300줄을 초과하거나 위험 경로에 닿는다 | T2 전체 + `/review` | pytest·vitest 전체 + qa 스킬 전체 시나리오 |

`/ponytail-review` 를 `/simplify` 앞에 두는 순서를 지킨다. 지울 코드를 먼저 걷어내야
곧 사라질 코드를 다듬는 낭비가 생기지 않는다.

인증이나 시크릿에 닿으면 티어와 무관하게 `/security-review` 를 추가한다.

줄 수는 `git diff --stat` 의 추가와 삭제 합계를 쓴다. 구현 파일이 함께 바뀌는 경우에
한해, 거기에 딸린 테스트 파일과 의존성 잠금 파일(`package-lock.json`, `requirements.txt`
의 버전 핀 갱신)을 합계에서 제외한다. 구현 파일을 건드리지 않는 작업에서는 제외하지 않고
그대로 센다. 이 조항의 목적은 구현 변경의 규모를 테스트 분량에 가려지지 않게 보는 것이지,
테스트나 의존성만 바꾸는 작업을 합계 0줄로 만들어 T1 으로 떨어뜨리는 것이 아니다.

의존성 버전을 올리는 작업은 줄 수와 무관하게 최소 T2 다. 메이저 버전을 올리면 T3 이다.
잠금 파일에서 바뀌는 것은 몇 줄이지만 실제로 달라지는 것은 애플리케이션이 실행하는 코드
전체이기 때문이다.

## 2. 위험 경로

한 줄이라도 닿으면 T3 이다. 2026-09-01 기준 실측 결과이며 47개 파일, 약 16,197줄이다.

### 신호와 등급 결정
- `engine/grade_classifier.py`
- `engine/grade_decider.py`
- `engine/grade_filter_validator.py`
- `engine/generator.py`
- `engine/generator_helpers.py`
- `engine/generator_result_storage.py`
- `engine/generator_runtime_helpers.py`
- `engine/generator_runtime_mixin.py`
- `engine/phases.py` (파사드)
- `engine/phases_analysis.py`
- `engine/phases_base.py`
- `engine/phases_news_llm.py`
- `engine/phases_phase1_helpers.py`
- `engine/phases_phase4_helpers.py`
- `engine/phases_pipeline.py`

### 시장 진입 판정
- `engine/market_gate.py`
- `engine/market_gate_analysis.py`
- `engine/market_gate_fetchers_external.py`
- `engine/market_gate_fetchers_local.py`
- `engine/market_gate_logic.py`
- `engine/market_gate_logic_fetchers.py`
- `engine/market_gate_logic_scoring.py`
- `engine/market_gate_logic_utils.py`

### VCP 판정
- `engine/vcp_ai_analyzer.py`
- `engine/vcp_ai_analyzer_helpers.py`

### 모의투자 계좌와 거래
- `services/paper_trading.py`
- `services/paper_trading_constants.py`
- `services/paper_trading_db_setup.py`
- `services/paper_trading_history_mixin.py`
- `services/paper_trading_price_fetchers.py`
- `services/paper_trading_sync_service.py`
- `services/paper_trading_trade_account_mixin.py`
- `services/paper_trading_valuation_helpers.py`
- `services/paper_trading_valuation_service.py`

### 수급 집계
- `services/investor_trend_5day_service.py`
- `services/kr_market_flow_service.py`

### 스케줄러와 데이터 적재
- `services/scheduler.py`
- `services/scheduler_jobs.py`
- `services/scheduler_loop.py`
- `services/scheduler_runtime_status_service.py`
- `scripts/init_data.py`

### 저장소 스키마
파일명에 `sqlite` 를 포함하는 모든 모듈이 해당한다.
- `chatbot/storage_sqlite_common.py`
- `chatbot/storage_sqlite_helpers.py`
- `chatbot/storage_sqlite_history.py`
- `chatbot/storage_sqlite_memory.py`
- `services/kr_market_data_cache_sqlite_payload.py`
- `services/sqlite_utils.py`

### 시크릿과 인증

이 절은 파일 목록이 아니라 접촉 패턴이다. 아래 패턴에 해당하는 파일을 건드리면 그 파일이
지금 존재하는지와 무관하게 T3 이며 `/security-review` 를 추가한다.

- `.env` 로 시작하는 모든 파일 (`.env`, `.env.production`, `.env.example` 등)
- `secrets/` 아래 전부

## 3. 판정 절차

1. 계획에서 건드릴 파일 목록을 뽑는다.
2. 그 목록이 §2 와 하나라도 겹치면 T3 이다. 줄 수는 보지 않는다.
3. 목록이 Markdown 문서뿐이면 §5 를 적용한다. 아래 4번과 5번을 거치지 않는다.
4. 의존성 버전을 올리는 작업이면 최소 T2 이고, 메이저 버전이면 T3 이다.
5. 위 어디에도 해당하지 않으면 예상 변경 줄 수로 T1 과 T2 를 가른다. 이때 §1 마지막
   문단의 제외 조항을 적용할 수 있는지 먼저 확인한다.
6. 구현 후 `git diff --stat` 으로 재확인한다. 상위 티어에 해당하면 올리고, 낮게 나와도
   내리지 않는다.

## 4. 목록 갱신

위험 경로에 해당하는 파일이 새로 생기거나 이동하면, 그 파일을 만든 사이클의 게이트 2 에서
이 목록을 함께 갱신한다. 목록에 적힌 경로는 모두 실재해야 한다.

## 5. 문서만 바꾸는 작업

실행 코드를 한 줄도 바꾸지 않고 Markdown 문서만 바꾸는 작업에는 §1 표의 리뷰 열을 적용하지
않는다. 리뷰 스킬 네 종은 모두 코드를 읽도록 만들어져 있어서 문서에는 적용할 대상이 없다.
변경이 300줄을 넘어도 마찬가지다. 대신 다음 두 가지를 그 사이클의 검증으로 삼는다.

1. 문서가 참조하는 파일 경로와 절 번호가 실재하는지 확인한다.
2. `git diff --stat` 으로 실행 코드가 바뀌지 않았음을 증명한다.

사이클 규약 문서(`SKILL.md`, `references/` 아래 문서, `.claude/agents/dev-workflow.md`)를
바꿨다면 여기에 한 가지를 더한다. 바뀐 규정을 `docs/dev-cycle/TODO.md` 의 모든 항목에
대조하고, 판정이 달라지는 항목의 티어를 같은 커밋에서 갱신한다. 규약만 고치고 백로그를
그대로 두면 다음 사이클이 낡은 판정으로 시작한다.

문서와 코드를 함께 바꾸는 작업에는 이 절을 적용하지 않는다. 그때는 코드 쪽 변경 규모로
§1 표를 그대로 적용한다.

이 절을 적용한 항목은 아카이브의 티어 칸에 `문서` 라고 적는다. T1 부터 T3 까지 어느 것도
해당하지 않기 때문이다.
