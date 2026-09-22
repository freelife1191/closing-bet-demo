# [INFRA-077] 종료 판정의 거짓 음성 제거(`lifecycle_pid_alive` 경합) — QA 시나리오

- 대상 화면: 없음. `scripts/service_lifecycle.sh` 를 쓰는 `./restart_all.sh`·`./stop_all.sh` 의 CLI 흐름
- 구성 근거: TODO 의 QA 줄(하네스 회귀 2건 + macOS 실기동 1회) + 이번 변경 두 파일
  (`scripts/service_lifecycle.sh`, `tests/scripts/test_lifecycle_adversarial.py`)
- 구성 2026-09-22 23:20 | 실행 (기록 전)
- QA 엔진(engine): Claude Code. 하네스는 pytest, 실기동은 저장소의 두 진입점 스크립트
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 반복(iteration): 1회
- baseline 상태: 로컬 3500·5501 모두 비어 있고 `logs/*.pid` 없음(2026-09-22 23:06 `lsof` 확인)
- 필수 여부(required): 예
- 결과: (기록 전)
- 증거: (기록 전)
- 정리(cleanup): (기록 전)
- browser_applicability: not-applicable. 화면 없이 셸 스크립트만 바뀌었고 사용자 진입 흐름은
  터미널 명령이다. browser_driver: none
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

## 시나리오

### S-1. `ps` 가 상태를 돌려주지 않으면 「살아 있음」이 아니라 「알 수 없음」이다 (회귀)
- 조작: `tests/scripts/test_lifecycle_adversarial.py::test_pid_alive_returns_unknown_when_ps_state_is_blank`.
  PATH 앞에 아무것도 출력하지 않는 `ps` 를 두고 살아 있는 셸 자신의 PID 로 `lifecycle_pid_alive` 를 부른다.
- 기대: 반환 코드 2. 구현 전에는 0(살아 있음)이었다(RED 확인). 호출자 대부분은 0 이 아닌 값을 모두 종료로
  읽고, 자식 정리 지점(S-5)만 2 를 즉시 실패로 가른다.
- 필수 여부(required): 예
- 실제: 1차 구현(`!= 0` 단언) `pytest -q tests/scripts/test_lifecycle_adversarial.py -k 'blank_ps_state or term_to_kill_escalation'` → `2 passed, 29 deselected in 0.38s`.
  리뷰 2차 지적으로 이름·단언을 `== 2` 로 고친 뒤 두 파일 `52 passed`(아래 S-3).
- 결과: 통과
- 증거: 위 명령 출력. 구현 전 같은 명령은 `assert 0 != 0` 으로 실패
- 정리(cleanup): pytest `tmp_path` 만 사용

### S-2. TERM 대기 만료 뒤 KILL 로 올릴 때 stderr 에 한 줄 남긴다 (회귀)
- 조작: `tests/scripts/test_lifecycle_adversarial.py::test_terminate_reports_term_to_kill_escalation`.
  첫 `lifecycle_wait_for_exit` 만 실패하도록 대역을 두고 `lifecycle_terminate_recorded_process frontend` 를 부른다.
- 기대: 반환 코드 0, 신호 기록이 `TERM 100`·`KILL 100` 순서, stderr 에 `⚠️  frontend PID 100` 과 `KILL` 이 있다.
  구현 전에는 stderr 가 비어 있었다(RED 확인).
- 필수 여부(required): 예
- 실제: 구현 후 통과(S-1 과 같은 명령, 2 passed). 구현 전 같은 명령은 `assert '⚠️  frontend PID 100' in ''` 으로 실패
- 결과: 통과
- 증거: S-1 과 같은 출력
- 정리(cleanup): pytest `tmp_path` 만 사용

### S-3. 기존 종료 계약이 그대로다 (인접)
- 조작: `pytest -q tests/scripts/test_lifecycle_adversarial.py tests/scripts/test_service_lifecycle.py`
  와 전체 `pytest -q`.
- 기대: 수명주기 두 파일 52 통과(기존 49 + 신규 3). 전체는 기준 커밋 `662868a` 의 통과 수에 신규 3건이
  더해지고 실패 0. `[INFRA-076]` 이 기록한 2571 은 그 뒤 라운드들이 검사를 더해 현재 기준이 아니다.
- 필수 여부(required): 예
- 실제: 1차(리뷰 전, 신규 2건) 두 파일 `51 passed in 11.28s`, 전체 `2614 passed, 2 skipped in 109.42s`(종료
  코드는 zsh 에서 `PIPESTATUS` 를 읽어 비었으나 요약 줄에 `failed`·`error` 없음). 2차(리뷰 반영 후, 신규 3건)
  두 파일 `52 passed in 10.35s`, 전체 `pytest -q` → `2615 passed, 2 skipped in 94.03s`, 종료 코드 0
  (zsh `pipestatus` 로 읽음). 1차 대비 +1 은 리뷰 반영으로 더한 S-5 다.
- 결과: 통과
- 증거: 위 명령들의 요약 줄
- 정리(cleanup): 없음

### S-4. macOS 실기동 한 사이클에서 종료가 거짓 실패 없이 끝난다 (인접)
- 조작: 로컬 서비스가 내려간 상태에서 `./restart_all.sh` 를 돌려 두 포트 응답을 읽고,
  `./stop_all.sh` 로 내린 뒤 포트와 PID 파일을 확인한다.
- 기대: `restart_all.sh` exit 0 과 `🎉 Ready!`, `http://127.0.0.1:5501/api/kr/market-gate` 200,
  `http://localhost:3500/` 200. `stop_all.sh` exit 0, 출력에 `❌` 와 새 `⚠️ … KILL 로 올립니다` 줄이
  없음(정상 TERM 종료), 두 포트 비어 있음, `logs/backend.pid`·`logs/frontend.pid` 삭제.
- 필수 여부(required): 예
- 실제: (기록 전)
- 결과: (기록 전)
- 증거: (기록 전)
- 정리(cleanup): 사이클이 끝나면 서비스는 내려간 상태로 둔다

### S-5. `ps` 가 막힌 환경에서 시작한 자식의 정리가 `wait` 로 막히지 않는다 (회귀)
- 조작: `tests/scripts/test_lifecycle_adversarial.py::test_terminate_started_child_fails_fast_when_ps_is_blank`.
  아무것도 출력하지 않는 `ps` 아래에서 3초짜리 background 자식으로 `lifecycle_terminate_started_child` 를 부른다.
  리뷰어(`infra077-reviewer`)가 1차 지적으로 격리 재현한 경로다(`restart_all.sh` 의 EXIT 트랩 정리).
- 기대: 반환 코드가 0 이 아니고 2초 안에 끝난다. 1차 구현에서는 `wait` 에 막혀 3.13초 뒤 0 을 돌려줬다(RED 확인).
- 필수 여부(required): 예
- 실제: 세 갈래 판정 도입 후 통과. `pytest -q tests/scripts/test_lifecycle_adversarial.py -k 'blank_ps_state or term_to_kill_escalation or fails_fast_when_ps_is_blank'` → `3 passed, 29 deselected in 0.44s`
  (S-1 의 검사 이름을 바꾸기 전 명령. 바꾼 뒤에는 `-k 'ps_state_is_blank or term_to_kill_escalation or fails_fast_when_ps_is_blank'`).
  이 검사는 기준 커밋 `662868a` 에서도 통과한다. 원래 결함이 아니라 이번 라운드의 1차 구현이 만들 뻔한 회귀를
  고정하는 검사다(리뷰어 실측).
- 결과: 통과
- 증거: 위 명령 출력. 구현 전 같은 검사는 `assert 0 != 0` 으로 3.13초 뒤 실패
- 정리(cleanup): 검사 안에서 자식을 KILL 하고 `wait` 로 회수

## 이월한 발견

(기록 전)

## 실행 결과

(기록 전)
