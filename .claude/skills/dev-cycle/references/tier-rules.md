# 티어 판정 규칙

dev-cycle 의 리뷰와 검증 강도를 정하는 규칙이다. 판정은 계획 단계에서 하고, 구현 후
실제 diff 가 상위 티어에 해당하면 상향한다. 하향은 어떤 경우에도 하지 않는다.

## 1. 티어별 절차

| 티어 | 조건 | 리뷰 | 검증 |
|---|---|---|---|
| T1 | 변경 50줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` | 변경 범위의 pytest 또는 vitest + QA 2단계 |
| T2 | 변경 300줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` → `/code-review` | pytest·vitest 전체 + QA 2단계. 웹 흐름은 §1-1에 따라 agent-browser로 실측한다 |
| T3 | 변경 300줄을 초과하거나 위험 경로에 닿는다 | T2 전체 + `/review` | pytest·vitest 전체 + QA 2단계. 웹 흐름은 §1-1에 따라 agent-browser로 실측한다 |

「QA 2단계」의 내용은 아래 §1-1 에 있다.

리뷰 열의 `/` 이름은 Claude Code 표기다. §1-1의 QA 표는 Claude Code와 Codex의 실행 단계를
각각 적으며, Codex의 실제 방법은 `SKILL.md`의 `## 실행 환경`과
`references/ultraqa.md`를 따른다. 과잉설계 리뷰를 맡는 Codex `code-reviewer` 에이전트의
사용법도 그 실행 환경 표를 따른다. 티어 판정 기준과 순서는 어느 환경에서든 이 문서의 것을
따른다.

검증 열의 「pytest」와 「vitest」가 어느 명령인지 여기에 적어 둔다. 매 사이클이 다시
알아내면 그만큼 시간이 든다.

    source venv/bin/activate && pytest      # 파이썬. 저장소 루트에서 실행한다
    cd frontend && npx vitest run           # `npm test`도 종료형 실행이며 감시는 `npm run test:watch`
    cd frontend && npm run type-check       # tsc --noEmit

`tsc` 는 표의 검증 열에 적혀 있지 않지만 `frontend/` 를 건드리는 항목에서는 함께 돌린다.
vitest 는 타입 오류를 잡지 못하고, 이 저장소의 화면 코드는 전부 타입스크립트다.

`/ponytail-review` 를 `/code-review` 앞에 두는 순서를 지킨다. 지울 코드를 먼저 걷어내야
곧 사라질 코드를 다듬는 낭비가 생기지 않는다.

리뷰 열에 `/simplify` 를 두지 않는다. 그런 이름의 스킬은 이 환경에 존재하지 않으며,
과잉설계를 걷어내는 일은 `/ponytail-review` 가 이미 맡고 있다. 그 스킬은 정의에서
"simplify review" 라는 문구까지 호출 신호로 삼는다. 둘을 나란히 세우면 같은 리뷰를 두 번
돌리게 된다.

표의 `/code-review` 는 Claude Code 내장 명령과 이름이 같지만 그 명령이 아니다. 내장 명령은
사용자만 실행할 수 있고 별도 비용이 들기 때문에 사이클이 부를 수 없다. 이 자리에 놓는 것은
`feature-dev:code-reviewer` 에이전트다. 이 에이전트는 확신도로 지적을 걸러 내므로, 부를 때
**확신도가 낮은 관찰도 확신도를 밝혀 함께 적어 달라고 요청한다.** 낮은 확신도로 분류된
관찰이 실제 결함이었던 사이클이 2026-09-03 에만 두 번 있었다.

아래 두 문단은 Claude Code 에서 그 에이전트를 띄울 때의 규칙이다. codex 에서는
`$code-review` 스킬이 그 자리를 대신하므로 해당하지 않는다. 낮은 확신도의 관찰도
확신도를 밝혀 보고하라는 앞 문단의 요청은 codex 리뷰에도 적용한다.

**이 에이전트를 띄울 때 `Agent` 도구에 `name` 을 반드시 준다.** 이름을 주면 teammate 로
등록되어 결과가 회신 메시지로 돌아오고, 이름을 주지 않으면 백그라운드 태스크가 되어 완료
알림 하나에만 의존하게 되는데 그 알림이 유실된다. 이 저장소의 세션 기록을 세어 보면
이름을 준 43건은 결과가 빠짐없이 도착했고, 이름 없이 띄운 22건 가운데 11건은 완료 알림이
끝내 오지 않았다.

**띄운 뒤에는 결과를 기다리며, 같은 리뷰를 다시 띄우지 않는다.** 리뷰 한 건에 78초에서
591초가 걸리므로 몇 분 동안 조용한 것이 정상이다. 응답이 늦으면 `ListAgents` 로 상태를
확인하고, `idle` 로 나오면 이미 일을 마친 것이므로 `SendMessage` 로 결과를 다시 요청한다.
2026-09-04 에 `vcp004-reviewer` 를 띄우고 2분 33초 만에 같은 리뷰를 두 번 더 띄운 일이
있었는데, 처음 띄운 것이 7분 44초 만에 정상 응답했으므로 나중의 둘은 전부 낭비였다.

### Codex 리뷰 실행과 체크포인트

티어별 리뷰 순서와 독립성은 유지한다. 과잉설계 검토 다음 `$code-review`의 code-reviewer·
architect 두 레인을 병렬 실행하고 두 결과를 받은 뒤, T3는 `$review`를 수행한다.
리더의 자기 검토를 누락된 독립 레인의 성공으로 대신하지 않는다.

- 각 리뷰에 항목·승인 요구사항·정확한 변경 파일·기준 SHA와 diff·이미 실행한 검증 결과를
  전달한다. 범위 밖 전체 감사나 동일 테스트 반복은 새 우려가 있을 때만 한다.
- 단계 시작 전에 현실적인 실행 상한을 정하고 기록한다. 라운드 상한에는 순차 리뷰와 QA·
  마감 시간을 함께 반영한다. 시간 초과는 해당 단계 미완료이며 PASS가 아니다.
- 각 결과를 받으면 TODO의 해당 체크와 연결된 검토 기록에 도구/역할·범위·검토 입력의
  파일별 SHA-256·결과·지적·증거 위치·다음 단계를 남긴다. 원본 결과를 요약으로 대체하지 않는다.
  `git diff`만으로 untracked 입력을 놓치지 않으며 관련 코드·테스트·명세·설정도 해시에 포함한다.
- 재개할 때 직전 결과와 현재 입력 해시가 모두 일치하면 완료한 리뷰를 재사용한다.
  코드·테스트·요구사항·설정·리뷰 기준이 바뀌거나 원본 증거가 없으면 영향받는 리뷰를 다시 한다.
  리뷰 결과를 적은 기록 자체만 바뀐 경우는 검토 대상 코드 변경과 구분한다.
- 사용할 수 없는 진단 도구는 실패 원문과 필요한 보장 범위를 남긴다. 프로젝트에서 가능한
  정적 검사 결과를 독립 reviewer에게 전달할 수 있지만, 그것을 실행하지 않은 LSP의 성공이나
  누락된 필수 진단의 통과로 표시하지 않는다. 필수 증거 부족으로 받은 판정은 그대로 유지한다.
- 외부 리뷰 스킬의 홈 기록·텔레메트리가 허용 범위를 벗어나면 그 쓰기를 생략하고 사유와
  실제 검토 결과를 저장소 기록에 남긴다. 검토 본체의 실패를 기록 실패로 바꿔 부르지 않는다.

최종 판정은 설치된 리뷰 스킬의 기준을 따른다. `COMMENT`·`WATCH`는 `APPROVE`·`CLEAR`로
바꾸지 않고, 차단 여부와 미반영 근거를 기록한다. 미완료 레인·필수 진단 누락·미해결 차단은
후속 QA의 성공으로 덮을 수 없다.

인증이나 시크릿에 닿으면 티어와 무관하게 아래 세 가지를 검증에 더한다. 보안 리뷰
에이전트와 `security-review` 스킬은 `.env` 추적 여부와 `NEXT_PUBLIC_` 번들 노출을 보장하지
않으므로 확인할 내용을 여기에 직접 적어 둔다.

1. `.env` 로 시작하는 파일이 추적 대상에 들어가지 않았는지 `git ls-files` 로 확인한다.
   `.env.example` 만 예외다.
2. 키 값이 로그나 API 응답 본문에 실려 나가지 않는지 확인한다.
3. 키가 프론트엔드 번들에 들어가지 않는지 확인한다. `NEXT_PUBLIC_` 접두사가 붙은 변수만
   브라우저로 나가므로 그 접두사가 붙은 목록을 먼저 본다.

세 가지를 직접 확인한 뒤 `oh-my-claudecode:security-reviewer` 를 `Agent` 도구에 `name` 을 주어
읽기 전용으로 띄우고, 변경 파일 목록과 기준 SHA 를 전달해 OWASP 관점의 지적을 받는다. 이
에이전트는 하드코딩된 키와 로그·오류 노출을 보며 위 세 가지를 대체하지 않는다. codex 에서는
`$security-review`로 보안 범위의 독립 `code-reviewer`를 호출한다. 설치된 OMX가 deprecated로
분류한 `security-reviewer` 역할은 재설치하지 않는다. 플러그인이 없는 Claude Code에서는
`security-review` 스킬로 대신하고
그 사실을 기록한다. 지적의 반영과 미반영 사유는 다른 리뷰와 같이 TODO 체크에 적는다.

줄 수는 `git diff --stat` 의 추가와 삭제 합계를 쓴다. 구현 파일이 함께 바뀌는 경우에
한해, 거기에 딸린 테스트 파일과 의존성 잠금 파일(`frontend/package-lock.json`, `requirements.txt`
의 버전 핀 갱신)을 합계에서 제외한다. 구현 파일을 건드리지 않는 작업에서는 제외하지 않고
그대로 센다. 이 조항의 목적은 구현 변경의 규모를 테스트 분량에 가려지지 않게 보는 것이지,
테스트나 의존성만 바꾸는 작업을 합계 0줄로 만들어 T1 으로 떨어뜨리는 것이 아니다.

의존성 버전을 올리는 작업은 줄 수와 무관하게 최소 T2 다. 메이저 버전을 올리면 T3 이다.
잠금 파일에서 바뀌는 것은 몇 줄이지만 실제로 달라지는 것은 애플리케이션이 실행하는 코드
전체이기 때문이다.

## 1-1. QA 2단계

검증의 QA 는 환경과 무관하게 두 단계다. 먼저 이번 변경을 보장할 **시나리오를 확정**하고,
그다음 그 시나리오를 **실제로 실행**한다. 실행 방법만 환경별로 다르다.

| 공통 단계 | Claude Code | Codex |
|---|---|---|
| 1단계: 시나리오 구성 | `/qa-only` | `$ultraqa`의 내부 계획 단계 |
| 2단계: 시나리오 실행 | `/qa` | `$ultraqa`의 내부 실행·진단·수정·정리 단계 |

Codex의 엔진, 단계, 반복 한도, baseline, 증거와 정리의 실제 절차는
[references/ultraqa.md](ultraqa.md)가 정본이다. 이 절은 두 환경에 공통인 시나리오와 완료 판정만
정하며, 그 절차를 복제하지 않는다.

`SKILL.md` [3] 검증 4번에서 1단계가 만든 근거와 이번 변경을 합쳐
`docs/dev-cycle/qa/<항목 ID>.md`에 시나리오를 기록한다. 형식은 `archive-format.md` §8을
따른다. 시나리오는 다음 세 종류를 담는다.

1. **회귀 시나리오** — 이번 사이클이 고친 결함의 재현 절차와 구체적인 기대값이다. 결함을
   고치는 항목에는 하나 이상 반드시 넣는다. `TODO.md`의 `QA 시나리오` 줄이 있으면 그
   줄에서 출발하고, 없으면 항목의 체크박스와 근거를 읽어 직접 만든다.
2. **인접 시나리오** — 같은 화면에서 함께 깨질 수 있는 동작이다. 필터, 정렬, 페이지 이동,
   탭 전환처럼 바꾼 값을 함께 읽는 조작이 해당한다.
3. **리포트 시나리오** — 1단계가 찾은 것 가운데 이번 항목의 범위 안에서 드러난 것이다.
   같은 파일을 고칠 수 있다는 사실은 범위 근거가 아니다.

시나리오 하나는 「조작 → 기대값」 한 쌍이며, 기대값은 눈으로 대조할 수 있는 구체적인
값이어야 한다. 범위 밖 발견만 새 TODO 항목으로 이월하고 `이월한 발견`에 사유와 ID를
쓴다. 범위 안의 필수 시나리오 실패는 이월 사유가 될 수 없다.

`SKILL.md` [3] 검증 6번의 실행은 시나리오 문서에 적힌 항목만 순서대로 검증하고, 7번에서
결과·종료 코드·증거·정리를 기록한다. 실패를 이번 범위 안에서 고치면 해당 시나리오와
필요한 리뷰를 다시 실행한다. 8번에 따라 필수 시나리오가 실패·차단·미실행 상태이면 TODO
항목을 유지하고 완료 아카이브를 만들지 않는다. 모든 필수 시나리오가 결과와 증거, 정리까지
갖춰 통과한 경우에만 10번을 거쳐 마감할 수 있다.

`SKILL.md` [3] 검증 5번의 첫 커밋에는 구현과 QA 시나리오 문서를 담되 TODO 항목을
유지한다. 최종 QA가 통과한 뒤, [4] 마감 3번의 아카이브 커밋에서만 TODO 항목을 제거한다.
과거 기록의 `실패 → 이월` 표기는 읽기 호환을 위해 그대로 두며, 소급 수정하거나 새 완료
규칙으로 해석하지 않는다.

실행 코드를 한 줄이라도 바꾸는 항목에는 티어와 무관하게 QA 2단계를 거친다. 화면이
바뀌었는지는 묻지 않는다. 문서 트랙과 테스트 파일만 바꾸는 작업만 제외한다. 구현 파일을
한 줄이라도 함께 바꾸면 제외가 아니다. 사용자가 해당 항목의 동적 검증을 명시했다면 문서·
테스트 전용 작업도 제외하지 않고, 가능한 안전한 동적 검사로 QA를 수행한다.

### agent-browser 와의 관계

Codex에서는 UltraQA가 계획한 웹 시나리오를 agent-browser로 실행한다. 구현 도중의 화면
관찰만으로 마감 QA를 대신하지 않으며, API 하네스만으로 사용자 조작·화면 결과를 검증한
것으로 세지 않는다. 기존 화면과 연결된 백엔드 변경도 포함하고 T1도 같은 기준을 적용한다.
필수 여부·안전한 대역·증거·BLOCKED 기준은 `references/ultraqa.md` §1-1이 정본이다.
Claude Code의 기존 QA 도구 순서는 실행 환경 표를 따른다.

두 도구를 다루는 요령과 겪었던 실수는 `browser-notes.md`에 있다. 실측을 시작하기 전에
읽는다.


## 2. 위험 경로

한 줄이라도 닿으면 T3 이다. 2026-09-07 기준 실측 결과이며 66개 파일, 23,695줄이다.

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
- `engine/signal_tracker_ai_helpers.py` — AI 추천 열을 직접 생성하므로 VCP-022에서 포함
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
- `services/sqlite_ready_gate.py`

`CREATE TABLE` 은 한 줄도 없지만 위 스물한 개 모듈이 모두 이 파일을 import 한다.
`connect_sqlite`, `build_sqlite_pragmas`, `prune_rows_by_updated_at_if_needed` 가 여기에
있어서, 접속 방식이나 프루닝 조건이 바뀌면 모든 저장소가 함께 달라진다.

두 번째 파일은 `[CHAT-003]` 이 2026-09-05 에 만들었다. 2단 캐시의 스키마 준비 단일 비행과
LRU 상한, 신규 키 판정, 강제 프루닝 주기, 스키마 복구 재시도를 담는다. 지금 이 파일을
import 하는 것은 바로 위 목록의 `chatbot/runtime_stock_map_cache.py` 와
`chatbot/stock_context_cache.py` 둘뿐이라 import 수만 보면 목록에 들 만하지 않다. 그런데도
넣는 이유는 그 둘이 이미 위험 경로이고, 이 파일이 두 저장소의 스키마 준비와 프루닝 시점을
한꺼번에 결정하기 때문이다. 판정 기준 2번이 말하는 「여기가 바뀌면 여러 모듈이 한꺼번에
영향을 받는다」에 그대로 해당한다. `[CHAT-012]` 와 `[INFRA-032]` 가 끝나면 이 파일을
import 하는 모듈은 열여섯 개가 된다.

목록을 갱신할 때는 다음 명령으로 다시 센다.

    git ls-files '*.py' | grep -v '^tests/' | xargs grep -li 'CREATE TABLE' | sort

### 신원 확정

- `frontend/src/proxy.ts`
- `services/identity_helpers.py`

`[INFRA-027]` 이 만든 두 파일이다. 앞의 것은 모든 API 요청에 신원 서명을 붙이고 뒤의 것은
그 서명을 검증한다. 저장소 전체에서 「이 요청자가 누구인가」를 정하는 자리가 이 둘뿐이라
판정 기준 2번의 「여기가 바뀌면 여러 모듈이 한꺼번에 영향을 받는다」에 그대로 해당한다.
한쪽만 고치면 모든 요청이 조용히 익명으로 떨어지는데, 화면은 멀쩡히 뜨고 로그인 표시도
남으므로 대화 목록이 비어 있는 것으로만 드러난다.

`[INFRA-040]` 에서 추가했다. `[INFRA-027]` 이 두 파일을 만들면서 §4 의 목록 갱신을
이행하지 않아 그동안 목록 밖에 있었다. 그 결과 `[INFRA-040]` 의 티어가 TODO 에 T2 로
적혀 있었다.

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
않는다. 리뷰 열의 스킬은 모두 코드를 읽도록 만들어져 있어서 문서에는 적용할 대상이 없다.
§1 의 시크릿 확인 세 가지와 보안 리뷰 보강도 실행 코드가 바뀌지 않으면 적용하지 않는다.
변경이 300줄을 넘어도 마찬가지다. 대신 다음 두 가지를 그 사이클의 검증으로 삼는다.

사용자가 이 문서 전용 항목에 동적 검증을 명시하면 이 예외를 적용하지 않는다. §1-1에 따라
안전한 동적 검사와 QA를 수행하고, 적용할 수 없는 동작은 `미실행` 또는 `차단`과 증거로
기록해 TODO를 유지한다.

1. 문서가 참조하는 파일 경로와 절 번호가 실재하는지 확인한다.
2. `git diff --stat` 으로 실행 코드가 바뀌지 않았음을 증명한다.

사이클 규약 문서(`SKILL.md`, `references/` 아래 문서, `.claude/agents/dev-workflow.md`,
`CLAUDE.md` 의 「개발 사이클」 절)를 바꿨다면 여기에 두 가지를 더한다.

첫째, 바뀐 규정을 `docs/dev-cycle/TODO.md` 의 모든 항목에 대조하고, 판정이 달라지는
항목의 티어를 같은 커밋에서 갱신한다. 규약만 고치고 백로그를 그대로 두면 다음 사이클이
낡은 판정으로 시작한다.

둘째, 위 네 자리가 서로를 가리키므로 한 곳을 고치면 나머지 세 곳에서 같은 주제를 다루는
대목을 함께 확인한다. 특히 `CLAUDE.md` 는 스킬을 부르지 않는 세션도 읽는 자리여서, 거기가
낡으면 사이클이 시작하기도 전에 어긋난 판정을 안고 들어간다.

문서와 코드를 함께 바꾸는 작업에는 이 절을 적용하지 않는다. 그때는 코드 쪽 변경 규모로
§1 표를 그대로 적용한다.

이 절을 적용한 항목은 아카이브의 티어 칸에 `문서` 라고 적는다. T1 부터 T3 까지 어느 것도
해당하지 않기 때문이다.
