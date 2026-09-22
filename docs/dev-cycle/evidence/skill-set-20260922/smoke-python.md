# smoke-python — 읽기 전용 smoke 원문 (2026-09-22)

- 도구 호출: {'Read': 2, 'Bash': 9, 'ToolSearch': 1, 'SendMessage': 1}
- Read 로 연 파일: .claude/skills/closing-bet-python/SKILL.md, .claude/skills/dev-cycle/references/tier-rules.md
- Bash 명령 (원문, 전부 로컬 읽기 전용이었고 HTTP 요청은 없었다):

    echo "=== 함수 정의 위치 ===" && grep -n "def run_vcp_background_pipeline" services/kr_market_vcp_background_service.py && echo "=== 호출자 전체 grep ===" && grep -rn "run_vcp_background_pipeline" --include="*.py" .

    sed -n '1,80p' services/kr_market_vcp_background_service.py

    echo "=== 함수 나머지 부분 ===" && sed -n '80,111p' services/kr_market_vcp_background_service.py && echo "=== tier-rules.md 에 이 파일명이 있는지 ===" && grep -n "kr_market_vcp_background_service" .claude/skills/dev-cycle/references/tier-rules.md; echo "exit:$?" && echo "=== init_data.py 가 위험 경로 목록에 있는지 재확인 ===" && grep -n "init_data" .claude/skills/dev-cycle/references/tier-rules.md

    echo "=== 재사용 사다리 헬퍼 후보 확인 ===" && ls engine/error_handler*.py engine/pandas_utils*.py engine/llm_utils*.py services/file_backed_status.py 2>&1 && echo "=== error_handler 함수 시그니처 ===" && grep -n "^def \|^    def " engine/error_handler.py 2>/dev/null | head -30

    echo "=== 테스트 파일 확인 ===" && cat tests/services/test_kr_market_vcp_background_service_refactor.py

    echo "=== safe_execute / execute_with_fallback / validate_range 정의 위치 ===" && grep -rn "def safe_execute\|def execute_with_fallback\|def validate_range" engine/ && echo "=== file_backed_status.py 개요 ===" && sed -n '1,40p' services/file_backed_status.py

    echo "=== 호출부 컨텍스트 (routes) ===" && sed -n '500,545p' app/routes/kr_market_data_signals_routes.py && echo "=== VCP_STATUS 가 FileBackedStatus 인지 ===" && grep -rn "VCP_STATUS" services/*.py app/routes/*.py | grep -i "FileBackedStatus\|= FileBackedStatus\|^services" | head -10

    sed -n '1,80p' engine/error_handler_execution.py

    echo "=== FileBackedStatus import 여부 ===" && grep -n "FileBackedStatus\|file_backed_status" services/kr_market_vcp_background_service.py; echo "결과없으면 무관"; echo "=== engine/vcp.py 존재 및 STRONG_CONTRACTION_RATIO 예시 확인 ===" && ls engine/vcp.py 2>&1 && grep -n "STRONG_CONTRACTION_RATIO" engine/vcp.py engine/constants*.py 2>/dev/null

## 에이전트가 돌려준 보고 원문

`.claude/skills/closing-bet-python/SKILL.md` 전체와 관련 근거 파일들을 읽기 전용으로 확인했습니다. 어떤 파일도 쓰거나 고치지 않았고, 서버에는 요청을 보내지 않았으며, `data/`나 `.env` 계열 파일도 열지 않았습니다.

## (a) `run_vcp_background_pipeline` 의 계층 위치와 호출자

`services/kr_market_vcp_background_service.py:33`에 정의된 services 계층 함수입니다. `grep -rn "run_vcp_background_pipeline"`으로 확인한 호출자 전부는 다음과 같습니다.

- 실제 호출부: `app/routes/kr_market_data_signals_routes.py:533` (`deps["run_vcp_background_pipeline"](...)`)
- 의존성 조립: `app/routes/kr_market_dependency_builders.py:19,69`, `app/routes/kr_market_route_registry.py:79,110`
- 재수출: `services/kr_market_vcp_service.py:11,42`, `services/kr_market_route_service.py:57`
- 테스트: `tests/services/test_kr_market_vcp_background_service_refactor.py`(직접 호출), `tests/app/test_kr_market_data_signals_routes_refactor.py`, `tests/app/test_infra_boundary_errors.py`, `tests/app/test_kr_market_dependency_builders.py`(모두 `lambda **_kwargs: None` 스텁으로 대체)

라우트는 이 함수를 직접 import하지 않고 `deps` 딕셔너리를 통해 의존성 주입 형태로만 호출합니다.

## (b) 티어 판정

`tier-rules.md` §2에서 이 파일명(`kr_market_vcp_background_service.py`)을 직접 검색하면 어느 위험 경로 절에도 없습니다. 반면 이 함수가 내부에서 부르는 `scripts/init_data.py`는 §2 「스케줄러와 데이터 적재」절(238번째 줄)에 명시적으로 올라 있습니다.

판정 절차(§3)는 "계획에서 건드릴 파일 목록"과 §2 목록의 교집합으로 T3를 가릅니다. 따라서 결과는 실제로 무엇을 고치느냐에 갈립니다.

- `services/kr_market_vcp_background_service.py`만 고치고 `scripts/init_data.py`의 함수 시그니처나 호출 방식을 바꾸지 않는다면, §2 목록과 직접 겹치는 파일이 없어 자동 T3 근거는 약합니다. 이 경우 §3-5에 따라 예상 변경 줄 수로 T1/T2를 가릅니다.
- `scripts/init_data.py` 쪽도 함께 고쳐야 하는 변경(예: `create_signals_log`의 인자나 반환값을 바꾸는 리팩터)이라면 그 즉시 T3입니다.

다만 이 함수는 VCP 스크리닝 백그라운드 파이프라인 전체를 오케스트레이션하고 저장 성공/실패 판정(`if not saved: raise RuntimeError(...)`)을 직접 담당합니다. 실제로 `git log`의 `8ff9ed1 fix(vcp): [VCP-031] report a failed signal save as an error instead of "no match"` 커밋이 바로 이 함수의 버그를 고친 이력입니다. 이런 실질을 감안하면 이름만으로는 위험 경로 목록에 없더라도 신중한 판정이 필요한 지점입니다.

## (c) 재사용 사다리 2단 검토

- **`engine/error_handler_execution.py`의 `safe_execute`/`execute_with_fallback`**: 시그니처를 확인했으나 "예외 시 기본값 반환"이라는 패턴이라, 이 함수가 실제로 하는 일(진행률 갱신 + 상태 전이 + 예외 시 error 상태 기록 + finally에서 running=False 정리)과는 맞지 않습니다. 그대로 끼워 넣을 대상이 아닙니다.
- **`services/file_backed_status.py`의 `FileBackedStatus`**: 이 함수는 이 클래스를 import하지 않고 `status_state: dict[str, Any]`라는 덕타이핑 매개변수로만 받습니다. 실제 `FileBackedStatus` 인스턴스는 `app/routes/kr_market.py:186`에서 만들어져 호출부(`kr_market_data_signals_routes.py`)가 주입합니다. 즉 이 함수 파일만 보면 재사용 대상이 보이지 않고, 호출 경로 전체를 봐야 이미 간접적으로 쓰이고 있음을 알 수 있습니다.
- **`engine/pandas_utils*.py`, `engine/llm_utils*.py`**: 이 함수 자체는 DataFrame이나 LLM을 직접 다루지 않습니다(LLM 호출은 `scripts/init_data.py` 내부의 `create_signals_log(run_ai=True)`에서 일어남). 해당 없음.

결론적으로 이 함수 범위 안에서 새로 붙잡을 기존 헬퍼는 마땅치 않고, 지금 구조(try/except/finally + `_set_vcp_status`)가 이미 사다리 4단(최소 코드)에 해당한다고 판단했습니다.

## (d) 테스트와 검증 명령

테스트 파일은 `tests/services/test_kr_market_vcp_background_service_refactor.py`이며, `init_data`의 네 단계(`create_daily_prices`, `create_institutional_trend`, `create_signals_log`, `update_vcp_signals_recent_price`)를 `monkeypatch`로 대체해 저장 실패/시그널 카운트/0건 유지 세 가지 경로를 검증합니다.

검증 명령은 스킬이 정한 대로입니다.

    source venv/bin/activate && pytest
    pytest tests/services/test_kr_market_vcp_background_service_refactor.py -v

## 스킬 본문에서 모호하거나 실제와 어긋나는 문장 (최대 3개)

1. `SKILL.md:19-21`의 "등급·시장 진입·VCP 판정·...스케줄러와 적재·저장소 스키마 모듈은 한 줄이라도 닿으면 T3다"라는 요약은, `tier-rules.md` §2의 「VCP 판정」절 실제 목록(`vcp_ai_analyzer` 계열 4개 파일만 포함)과 대조하면 `kr_market_vcp_background_service.py`는 빠져 있습니다. 파일명에 "vcp"가 들어가고 VCP 스크리닝을 오케스트레이션하는 이 파일을, SKILL.md 요약만 보고 자동으로 "VCP 판정"에 해당하는 T3라고 오판하기 쉽습니다. 실제로는 상세 목록을 `grep`으로 대조해야 정확한 판정이 나옵니다.
2. `SKILL.md:44-46`은 재사용 후보로 `services/file_backed_status.py`를 나열하지만, 이 목록은 services 계층 전체를 향한 일반 안내이고 `run_vcp_background_pipeline` 자체 파일에는 해당 모듈의 import가 없습니다(위 (c) 참고). 이 함수만 열어 본 사람은 "이미 쓰고 있다"는 근거를 이 파일 안에서 찾지 못하므로, 호출부(`app/routes/kr_market.py`)까지 봐야 한다는 안내가 없는 점이 아쉽습니다.
3. `SKILL.md:83`의 검증 명령 예시 `pytest tests/engine/test_vcp_refactor.py -k name`은 `engine` 패키지 테스트를 예로 들고 있어, 이번 대상 함수의 실제 테스트가 `tests/services/` 아래에 있다는 사실과는 별개의 예시입니다. 오류는 아니지만 특정 함수 작업자가 그대로 따라 하면 잘못된 경로를 찾게 될 수 있어 모호합니다.

## 실제로 읽은 파일 경로

- `.claude/skills/closing-bet-python/SKILL.md`
- `services/kr_market_vcp_background_service.py`
- `.claude/skills/dev-cycle/references/tier-rules.md`
- `engine/error_handler_execution.py`
- `services/file_backed_status.py`
- `tests/services/test_kr_market_vcp_background_service_refactor.py`
- `app/routes/kr_market_data_signals_routes.py` (500~545줄)
- `engine/vcp.py`, `engine/constants_market_scoring.py` (SKILL.md 예시 검증용)
- 아래는 grep 결과로만 확인(전체 파일을 열지는 않음): `app/routes/kr_market_route_registry.py`, `app/routes/kr_market_dependency_builders.py`, `services/kr_market_vcp_service.py`, `services/kr_market_route_service.py`, `tests/app/test_kr_market_data_signals_routes_refactor.py`, `tests/app/test_infra_boundary_errors.py`, `tests/app/test_kr_market_dependency_builders.py`, `app/routes/kr_market.py`(186줄)
