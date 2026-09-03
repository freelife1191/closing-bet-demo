# 티어 판정 규칙

dev-cycle 의 리뷰와 검증 강도를 정하는 규칙이다. 판정은 계획 단계에서 하고, 구현 후
실제 diff 가 상위 티어에 해당하면 상향한다. 하향은 어떤 경우에도 하지 않는다.

## 1. 티어별 절차

| 티어 | 조건 | 리뷰 | 검증 |
|---|---|---|---|
| T1 | 변경 50줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` | 변경 범위의 pytest 또는 vitest + QA 2단계 |
| T2 | 변경 300줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` → `/code-review` | pytest·vitest 전체 + QA 2단계. 화면이 바뀌면 agent-browser 로 값을 대조한다 |
| T3 | 변경 300줄을 초과하거나 위험 경로에 닿는다 | T2 전체 + `/review` | pytest·vitest 전체 + QA 2단계. 화면이 바뀌면 agent-browser 로 값을 대조한다 |

「QA 2단계」의 내용은 아래 §1-1 에 있다.

`/ponytail-review` 를 `/code-review` 앞에 두는 순서를 지킨다. 지울 코드를 먼저 걷어내야
곧 사라질 코드를 다듬는 낭비가 생기지 않는다.

리뷰 열에 `/simplify` 를 두지 않는다. 그런 이름의 스킬은 이 환경에 존재하지 않으며,
과잉설계를 걷어내는 일은 `/ponytail-review` 가 이미 맡고 있다. 그 스킬은 정의에서
"simplify review" 라는 문구까지 호출 신호로 삼는다. 둘을 나란히 세우면 같은 리뷰를 두 번
돌리게 된다.

인증이나 시크릿에 닿으면 티어와 무관하게 아래 세 가지를 검증에 더한다. `/security-review`
라는 명령은 이 환경에 없으므로 확인할 내용을 직접 적어 둔다.

1. `.env` 로 시작하는 파일이 추적 대상에 들어가지 않았는지 `git ls-files` 로 확인한다.
   `.env.example` 만 예외다.
2. 키 값이 로그나 API 응답 본문에 실려 나가지 않는지 확인한다.
3. 키가 프론트엔드 번들에 들어가지 않는지 확인한다. `NEXT_PUBLIC_` 접두사가 붙은 변수만
   브라우저로 나가므로 그 접두사가 붙은 목록을 먼저 본다.

줄 수는 `git diff --stat` 의 추가와 삭제 합계를 쓴다. 구현 파일이 함께 바뀌는 경우에
한해, 거기에 딸린 테스트 파일과 의존성 잠금 파일(`frontend/package-lock.json`, `requirements.txt`
의 버전 핀 갱신)을 합계에서 제외한다. 구현 파일을 건드리지 않는 작업에서는 제외하지 않고
그대로 센다. 이 조항의 목적은 구현 변경의 규모를 테스트 분량에 가려지지 않게 보는 것이지,
테스트나 의존성만 바꾸는 작업을 합계 0줄로 만들어 T1 으로 떨어뜨리는 것이 아니다.

의존성 버전을 올리는 작업은 줄 수와 무관하게 최소 T2 다. 메이저 버전을 올리면 T3 이다.
잠금 파일에서 바뀌는 것은 몇 줄이지만 실제로 달라지는 것은 애플리케이션이 실행하는 코드
전체이기 때문이다.

## 1-1. QA 2단계

검증의 QA 는 두 단계로 나뉜다. 먼저 `/qa-only` 로 화면을 훑어 **무엇을 검사할지**를
시나리오로 확정하고, 그다음 `/qa` 로 그 시나리오를 **하나씩 실제로 실행한다**.

앞서 이 자리에는 `/qa-only` 하나만 `--quick` 으로 돌리도록 적혀 있었다. 그 방식은 두 가지
이유로 충분하지 않았다. `--quick` 은 홈페이지와 상위 링크 다섯 개를 30초 동안 훑는 스모크
테스트여서 페이지를 넘겨야 드러나는 결함이나 특정 조작을 거쳐야 드러나는 결함에 닿지
못한다. 그리고 두 스킬 모두 탐색만 할 뿐 이번 변경이 무엇을 보장해야 하는지를 검사 항목으로
만들지 않으므로, 사이클이 고친 결함이 실제로 고쳐졌는지를 QA 가 확인해 주지 못했다.
`[FLOW-010]` 에서 등급 카드의 페이지 의존 결함을 잡아낸 것도 `/qa-only` 가 아니라
agent-browser 실측이었다.

### 1단계: 시나리오 구성 — `/qa-only`

`--quick` 을 붙이지 않고 바뀐 화면의 주소만 준다.

    /qa-only http://localhost:3500/dashboard/kr/cumulative

인자를 주지 않으면 스킬이 `git diff main...HEAD` 로 검사 범위를 잡는데, 이 저장소는
`develop` 이 `main` 보다 100커밋 넘게 앞서 있어서 사이클 하나가 아니라 앱 전체가 대상이
된다. 스킬은 규칙 5번에 따라 소스를 읽지 않으므로 스스로 범위를 좁히지 못한다. 백엔드만
바꿔서 대응하는 화면이 뚜렷하지 않으면 바뀐 값을 실제로 그리는 화면의 주소를 준다.

리포트를 받으면 그 리포트와 이번 사이클의 변경 내용을 합쳐 시나리오 문서를
`docs/dev-cycle/qa/<항목 ID>.md` 에 쓴다. 형식은 `archive-format.md` §8 에 있다.
시나리오는 다음 세 종류를 담는다.

1. **회귀 시나리오** — 이번 사이클이 고친 결함의 재현 절차와, 고쳐졌다면 나와야 할 기대값.
   결함을 고치는 항목에는 반드시 하나 이상 넣는다. 무엇을 고쳤는지가 곧 무엇을 검사해야
   하는지다.

   `TODO.md` 의 그 항목에 `- QA 시나리오:` 줄이 있으면 **거기서 출발한다.** 그 줄은
   `dev-workflow` 에이전트가 감사할 때 「화면에서 무엇을 확인하면 고쳐졌다고 말할 수
   있는가」를 미리 적어 둔 것이다. 항목을 발견한 사람이 남긴 판정 기준이므로 회귀
   시나리오의 초안으로 그대로 쓸 수 있다. 다만 그 줄은 기대값이 비어 있는 한 문장이므로,
   [3] 검증의 3번에서 실측한 값을 채워 넣어야 검사할 수 있는 시나리오가 된다. 줄과
   실측값이 어긋나면 실측값을 따르고, 어긋난 사실을 시나리오 문서에 한 줄로 적는다.
2. **인접 시나리오** — 같은 화면에서 이번 변경에 딸려 깨질 수 있는 동작. 필터, 정렬,
   페이지 이동, 탭 전환처럼 바꾼 값을 함께 읽는 조작이 해당한다.
3. **리포트 시나리오** — 1단계 리포트가 지적한 것 가운데 **이번 항목이 고치기로 한 것과
   같은 자리에서 드러난 것**. 판정 기준은 「고칠 수 있는가」가 아니라 「이번 항목의 범위
   안인가」다. 두 기준은 자주 어긋난다. 같은 파일이고 몇 줄이면 고칠 수 있어도, `TODO.md`
   의 그 항목이 고치기로 한 것이 아니면 범위 밖이다. 「고칠 수 있는가」로 판정하면
   `SKILL.md` 「규칙」의 「TODO 에 없는 작업을 즉흥으로 시작하지 않는다」와 충돌한다.
   시나리오에 넣는 순간 `/qa` 가 그것을 고쳐 커밋하기 때문이다.

   범위 밖으로 판단한 것은 `TODO.md` 에 새 항목으로 올리고, 시나리오 문서의 「이월한
   발견」에 무엇을 왜 이월했는지 한 줄로 적는다. 리포트가 지적한 것이 전부 범위 밖이어서
   리포트 시나리오가 하나도 없는 사이클은 정상이다. 억지로 만들지 않는다.

시나리오 하나는 「조작 → 기대값」 한 쌍이다. 기대값은 눈으로 대조할 수 있는 구체적인 값을
적는다. `정상 동작한다` 는 기대값이 아니다. `S 등급 카드가 16건 / 37.5% / +0.3% 이고
2페이지에서도 같다` 가 기대값이다. 개수는 다섯에서 열 사이가 적당하고, 세 개 미만이면
검사할 것을 덜 찾은 것이며, 열다섯을 넘으면 이번 사이클 밖까지 손을 뻗은 것이다.

### 2단계: 시나리오 실행 — `/qa`

**구현을 먼저 커밋한 뒤에 부른다.** `qa` 는 시작할 때 `git status --porcelain` 이 비어
있지 않으면 멈추고 커밋할지 스태시할지 묻는다. 자기가 만드는 수정 커밋을 원자적으로 남기기
위해서다. 그래서 `SKILL.md` 의 [3] 검증은 이 자리에서 첫 커밋을 만든다.

    /qa http://localhost:3500/dashboard/kr/cumulative

    시나리오 문서 docs/dev-cycle/qa/FLOW-010.md 의 검사를 번호 순서대로 실행하십시오.
    탐색 모드로 앱 전반을 훑지 말고 이 문서에 적힌 항목만 검사합니다.
    시나리오가 실패하면 고치되, 시나리오 밖에서 발견한 결함은 고치지 말고
    리포트에만 적어 주십시오.

마지막 두 줄의 제약이 중요하다. 이 제약이 없으면 `qa` 가 사이클 범위 밖의 결함까지 고쳐서
커밋하는데, 그것은 「TODO 에 없는 작업을 즉흥으로 시작하지 않는다」는 규칙을 어긴다.
시나리오 밖에서 발견한 것은 `TODO.md` 에 새 항목으로 올리고 지금 항목을 마저 끝낸다.

`qa` 가 시나리오 실패를 고쳤다면 **티어에 해당하는 리뷰를 그 수정에 대해 다시 돌린다.**
앞서 이 스킬을 검증에서 배제했던 이유가 바로 「고친 것이 리뷰를 거치지 않는다」였는데,
재실행이 그 구멍을 막는다. 재실행한 사실과 결과는 아카이브의 리뷰 줄에 적는다.

`qa` 가 실패를 고치지 못했거나, 고치려면 이번 항목의 범위를 넘는 경우가 있다. 그때는
고치지 않는다. `TODO.md` 에 새 항목으로 올리고 시나리오 문서의 결과를 `실패 → 이월` 로
적는다. 시나리오가 실패했는데도 사이클을 끝내는 유일한 경로이므로, 무엇을 왜 남겼는지
마감 보고와 아카이브 메모 줄에 함께 적는다. 남긴 사실이 기록에 없으면 다음 사이클이
그 결함을 다시 찾아내며 같은 시간을 쓴다.

`qa` 는 시나리오 실패를 고칠 때 회귀 테스트를 함께 작성해 별도 커밋으로 남긴다(Phase
8e.5). 그 테스트가 이 저장소의 테스트 정책에 맞는지 확인한다. 맞지 않으면 고치거나 지운다.
판단 기준은 `SKILL.md` 의 `## 테스트 정책` 에 있다.

`qa` 의 `--quick` 은 `qa-only` 의 `--quick` 과 뜻이 다르다. 앞의 것은 고칠 결함의 심각도를
critical 과 high 로 한정하는 옵션이고, 뒤의 것은 탐색 범위를 홈페이지 주변으로 좁히는
옵션이다. 시나리오 실행에는 둘 다 붙이지 않는다. 시나리오는 이미 범위를 확정한 목록이므로
더 좁힐 것이 없다.

### 적용 범위

실행 코드를 한 줄이라도 바꾸는 항목에는 티어와 무관하게 QA 2단계를 거친다. 화면이
바뀌었는지는 묻지 않는다. 앞서 이 자리에는 "백엔드만 바꾸면 열어 볼 화면이 없다" 고 적혀
있었으나 그 전제는 틀렸다. `[VCP-006]` 은 백엔드만 바꾼 항목이었는데 결함이 드러난 자리는
브라우저였고 `curl` 로는 정상으로 보였다. 스킬 자체도 "backend changes affect app behavior
— always open the browser and test" 를 규칙 12번으로 두고 있다.

제외는 두 가지다. §5 의 문서 트랙과, 테스트 파일만 바꾸는 작업이다. 둘 다 애플리케이션이
실행하는 코드가 그대로여서 브라우저로 확인할 동작이 없다. 구현 파일을 한 줄이라도 함께
바꾸면 제외가 아니다.

### 부르기 전에 갖출 것

두 가지가 갖춰져 있어야 한다. 갖춰지지 않으면 스킬이 접속할 곳을 찾지 못하고 멈춘다.
1단계를 부르기 직전에 확인한다. 두 단계가 같은 서버를 쓰므로 2단계에서 다시 확인할
필요는 없지만, 그 사이에 압축 지점이 두 번 있으므로 서버가 내려갔다면 다시 띄운다.

1. Flask 가 5501 에, Next.js 가 3500 에 떠 있어야 한다. `./restart_all.sh` 로 함께 띄운다.
2. `~/.claude/skills/gstack/browse/dist/browse` 가 빌드되어 있어야 한다. 없으면 스킬이
   `NEEDS_SETUP` 을 알리며 일회성 빌드를 요청한다.

두 단계 각각의 직전이 `SKILL.md` 의 `## 컨텍스트 관리` 가 정한 압축 지점이다.

### agent-browser 와의 관계

QA 2단계와 agent-browser 는 겹치지 않는다. 앞의 것은 확정한 시나리오를 사용자의 눈으로
실행하고 실패를 고친다. 뒤의 것은 구현 도중에 특정 값을 즉시 대조할 때 쓴다. 화면이 바뀌는
항목에서는 구현 단계에서 agent-browser 로 값을 확인하고, 검증 단계에서 QA 2단계로 시나리오
전체를 돌린다. 앞의 확인 결과가 시나리오의 기대값이 되므로 두 작업은 이어진다.


## 2. 위험 경로

한 줄이라도 닿으면 T3 이다. 2026-09-02 기준 실측 결과이며 63개 파일, 23,357줄이다.

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
- `engine/vcp_ai_orchestration_helpers.py`
- `engine/vcp_ai_provider_init_helpers.py`

뒤의 두 파일은 `[VCP-003]` 에서 추가했다. 둘 다 `vcp_ai_analyzer.py` 에서 분해되어 나왔고,
어느 AI 프로바이더를 실제로 호출할지 결정한다. `[VCP-003]` 의 결함이 두 파일에 걸쳐 있었다.
`orchestrate_stock_analysis` 의 분기가 두 번째 프로바이더를 고르고,
`resolve_perplexity_disabled` 가 그 분기의 입력을 만든다. 이 결정이 VCP 표의 AI 추천 열을
그대로 좌우하므로 「VCP 판정」에 해당한다.

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

판정 기준은 파일명이 아니라 그 모듈이 실제로 하는 일이다. 두 갈래가 해당한다.

1. `CREATE TABLE` 로 테이블을 정의하는 모듈. 스키마가 바뀌면 이미 저장된 파일과
   어긋나므로 마이그레이션 없이는 되돌릴 수 없다.
2. 모든 SQLite 접속이 거쳐 가는 공통 계층. 여기가 바뀌면 1번의 모든 모듈이 한꺼번에
   영향을 받는다.

앞서 이 자리에는 "파일명에 `sqlite` 를 포함하는 모든 모듈" 이라고 적혀 있었다. 그 규칙이
잡아낸 여섯 개 가운데 실제로 테이블을 정의하는 것은 `chatbot/storage_sqlite_common.py` 와
`services/kr_market_data_cache_sqlite_payload.py` 둘뿐인데, 저장소 전체에서 테이블을
정의하는 모듈은 스물한 개다. `[FLOW-003]` 에서 `services/kr_market_cumulative_cache.py` 가 목록 밖이라
판정이 T2 로 나왔고 실질을 보고 손으로 T3 으로 올렸다.

반대로 `chatbot/storage_sqlite_helpers.py`(재수출 파사드), `chatbot/storage_sqlite_history.py`,
`chatbot/storage_sqlite_memory.py` 는 파일명에 `sqlite` 가 들어가지만 스키마를 정의하지 않고 읽고
쓰기만 하므로 이 절에서 빠진다.

**테이블을 정의하는 모듈** — 뒤에 그 모듈이 만드는 테이블 이름을 적는다.

- `chatbot/runtime_stock_map_cache.py` — `chatbot_stock_map_cache`
- `chatbot/stock_context_cache.py` — `chatbot_stock_context_cache`
- `chatbot/storage_sqlite_common.py` — `chatbot_sessions`, `chatbot_messages`, `chatbot_memories`
- `engine/kr_ai_stock_info_cache.py` — `kr_ai_stock_info_cache`
- `engine/services/usage_tracker.py` — `api_usage`
- `engine/signal_tracker_analysis_source_cache.py` — `signal_tracker_csv_source_cache`
- `engine/signal_tracker_source_cache.py` — `signal_tracker_source_cache`
- `services/common_update_status_service.py` — `update_status_snapshot`
- `services/file_row_count_cache.py` — `file_row_count_cache`
- `services/kr_market_backtest_summary_cache.py` — `backtest_summary_cache`
- `services/kr_market_cumulative_cache.py` — `cumulative_performance_cache`
- `services/kr_market_data_cache_jongga.py` — `jongga_results_payload_cache`
- `services/kr_market_data_cache_sqlite_payload.py` — `csv_file_payload_cache`, `json_file_payload_cache`
- `services/kr_market_jongga_payload_helpers.py` — `jongga_recent_valid_payload_cache`
- `services/kr_market_realtime_latest_close_cache.py` — `realtime_latest_close_map_cache`
- `services/kr_market_realtime_market_map_cache.py` — `realtime_market_map_cache`
- `services/kr_market_realtime_price_cache.py` — `realtime_price_cache`, `yfinance_failed_ticker_cache`
- `services/kr_market_vcp_signals_cache.py` — `vcp_signals_payload_cache`
- `services/usage_tracker.py` — `usage_log`

`services/paper_trading.py`(`price_cache`)와 `services/paper_trading_db_setup.py`
(`balance`, `portfolio`, `trade_log`, `asset_history`, `price_cache`)도 테이블을 정의하지만
「모의투자 계좌와 거래」 절에 이미 있으므로 여기에 다시 적지 않는다.

**공통 접속 계층**

- `services/sqlite_utils.py`

`CREATE TABLE` 은 한 줄도 없지만 위 스물한 개 모듈이 모두 이 파일을 import 한다.
`connect_sqlite`, `build_sqlite_pragmas`, `prune_rows_by_updated_at_if_needed` 가 여기에
있어서, 접속 방식이나 프루닝 조건이 바뀌면 모든 저장소가 함께 달라진다.

목록을 갱신할 때는 다음 명령으로 다시 센다.

    git ls-files '*.py' | grep -v '^tests/' | xargs grep -li 'CREATE TABLE' | sort

### 시크릿과 인증

이 절은 파일 목록이 아니라 접촉 패턴이다. 아래 패턴에 해당하는 파일을 건드리면 그 파일이
지금 존재하는지와 무관하게 T3 이며, §1 의 시크릿 확인 세 가지를 검증에 더한다.

- `.env` 로 시작하는 모든 파일 (`.env`, `.env.production`, `.env.example` 등)
- `secrets/` 아래 전부

## 3. 판정 절차

1. 계획에서 건드릴 파일 목록을 뽑는다.
2. 그 목록이 §2 와 하나라도 겹치면 T3 이다. 줄 수는 보지 않는다.
3. 목록이 Markdown 문서뿐이면 §5 를 적용한다. 아래 4번과 5번을 거치지 않는다.
4. 의존성 버전을 올리는 작업이면 최소 T2 이고, 메이저 버전이면 T3 이다.
5. 위 어디에도 해당하지 않으면 예상 변경 줄 수로 T1 과 T2 를 가른다. 이때 §1 의 줄 수
   제외 조항을 적용할 수 있는지 먼저 확인한다.
6. 구현 후 `git diff --stat` 으로 재확인한다. 상위 티어에 해당하면 올리고, 낮게 나와도
   내리지 않는다.

## 4. 목록 갱신

위험 경로에 해당하는 파일이 새로 생기거나 이동하면, 그 파일을 만든 사이클의 첫 커밋에서
이 목록을 함께 갱신한다. 목록에 적힌 경로는 모두 실재해야 한다.

이미 목록 밖에 있던 파일에 `CREATE TABLE` 을 새로 넣는 경우도 같다. §2 의 저장소 스키마
판정은 파일명이 아니라 그 파일이 하는 일을 보므로, 테이블 정의가 들어온 순간 그 파일은
위험 경로가 된다. 그 변경을 담은 커밋에서 목록에 추가한다.

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
