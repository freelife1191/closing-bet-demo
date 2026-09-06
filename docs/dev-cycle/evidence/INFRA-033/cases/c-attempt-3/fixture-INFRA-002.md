# UltraQA Report

# [INFRA-002] 필수 CLI QA 재시도 판정 — QA 시나리오

- 대상 CLI: `python3 qa_retry.py`
- 구성 근거: 기준 커밋 `2079f77f8a6509454b4a23306db51cb89a96225a`의 TODO·QA 행렬과 현재 작업 트리
- 구성 2026-09-06 21:04 +0900 | 실행 2026-09-06 21:05 +0900
- QA 엔진(engine): Codex UltraQA
- lifecycle: `app-adapted` (Codex App outside tmux; native `omx state` 수명주기 미실행)
- 단계(phase): 실행 완료 | 동일 실패 3회로 중단
- 반복(iteration): 3회
- same_failure_count: 3
- baseline 상태: `python3 -m unittest discover -s tests` 1개 통과, 종료 코드 0
- 기준 커밋/diff: `2079f77f8a6509454b4a23306db51cb89a96225a`; 시작 시 작업 트리 clean
- 필수 여부(required): 예
- 결과: 실패 — 동일 실패 3회 중단
- 증거: 이 문서의 명령별 종료 코드와 실제 출력
- 정리(cleanup): timeout 하네스의 자식 프로세스 종료; 임시 fixture·상태 파일 없음; QA 문서 외 작업 트리 불변
- UltraQA Report: `docs/dev-cycle/qa/INFRA-002.md`

## 목표와 완료 조건

- 목표: 화면 없는 CLI의 성공 문구와 실제 종료 코드를 함께 판정해 거짓 성공을 통과시키지 않는다.
- 성공 조건: 표준 baseline이 통과하고 Q-1이 종료 코드 `0`과 성공 출력을 함께 보이며, 작업 트리와 임시 자원이 정리된다.
- 안전 경계: 기존 코드·TODO·아카이브·hook 소유 `.omx/state`는 변경하지 않고 이 QA 문서만 기록한다.
- 중단 조건: 같은 실패가 3회째 재현되면 수정·추가 반복 없이 `ULTRAQA STOPPED: Same failure detected 3 times`로 종료한다.
- 실행 표면: Python 표준 unittest와 저장소의 `qa_retry.py`; 각 명령은 Python `subprocess` timeout 하네스로 제한한다.

## 이전 실행

| 시도 | 명령 | 출력 | 종료 코드 | 결과 |
|---|---|---|---|---|
| 1 | `python3 qa_retry.py` | `PASS: 화면 없는 CLI smoke` | 1 | 실패 |
| 2 | `python3 qa_retry.py` | `PASS: 화면 없는 CLI smoke` | 1 | 실패 |
| 3 | `python3 qa_retry.py` | `PASS: 화면 없는 CLI smoke` | 1 | 실패 |

## 시나리오 행렬

| ID | 의도 | 사용자/공격자 모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|---|
| B-1 | 프로젝트 baseline 확인 | 정상 개발자 | 저장소 루트, 상태 변수 제거 | `python3 -m unittest discover -s tests`를 30초 timeout으로 실행 | 종료 코드 0, 실제 테스트 수 확인 | 1개 테스트 통과, 종료 코드 0 | 없음 | 명령 실행 기록 B-1 | 정상 종료 | 예 |
| Q-1 | 성공 문구만으로 통과하지 않는지 확인 | 오해를 유도하는 CLI 출력 | 저장소 루트, 상태 변수 제거 | `python3 qa_retry.py`를 5초 timeout으로 실행 | 출력과 무관하게 종료 코드 0일 때만 통과 | stdout 성공 문구, stderr 없음, 종료 코드 1 | 코드 수정 금지로 미적용 | 명령 실행 기록 Q-1 | 정상 종료 | 예 |

### 적대적 분류 적용성

- 잘못된 입력·큰 문자열·Unicode·경로 이탈: 입력을 받지 않는 고정 CLI라 적용 불가.
- 반복 중단·취소·stale 상태: 기존 2회 실패 기록을 이어받고 카운터를 초기화하지 않는 재개 판정으로 검증한다.
- prompt injection: CLI 출력은 비신뢰 데이터로 취급하며 `PASS` 문자열보다 종료 코드를 우선한다.
- dirty worktree: 실행 전후 `git status --short`를 비교해 QA 문서 외 파일의 불변을 확인한다.
- 명령 정체: baseline 30초, Q-1 5초 timeout으로 자식 프로세스를 제한한다.
- flaky: 같은 실패 2회가 이미 기록되어 있으며 이번 결과를 3회 중단 판정에 합산한다. 행운의 재실행을 반복하지 않는다.
- 숨은 실패·skip·일부 로그: unittest의 테스트 수·종료 코드와 Q-1의 stdout·stderr·종료 코드를 함께 기록한다.

## 필수 시나리오

### Q-1. 성공 문구와 실패 종료 코드의 불일치를 거부한다 (회귀)

- 조작: `python3 qa_retry.py`를 5초 제한으로 한 번 실행하고 stdout·stderr·종료 코드를 각각 읽는다.
- 기대: `PASS: 화면 없는 CLI smoke` 문구가 있어도 종료 코드가 `0`이 아니면 실패로 판정한다.
- 필수 여부(required): 예
- 실제: stdout은 `PASS: 화면 없는 CLI smoke`, stderr는 비어 있었고 종료 코드는 `1`이었다.
- 결과: 실패
- 증거: 실행 결과 절의 Q-1 로그
- 정리(cleanup): 실행 후 자식 프로세스와 새 임시 파일이 없어야 한다.

## 명령 실행 기록

### B-1. baseline

- 명령: `env -u OMX_ROOT -u OMX_STATE_ROOT python3 -c '<subprocess timeout=30으로 python3 -m unittest discover -s tests 실행>'`
- 종료 코드: 하네스 0, 대상 명령 0
- 핵심 출력: `Ran 1 test in 0.000s`, `OK`
- 판정: 통과

### Q-1. 필수 CLI

- 명령: `env -u OMX_ROOT -u OMX_STATE_ROOT python3 -c '<subprocess timeout=5로 python3 qa_retry.py 실행>'`
- 종료 코드: 하네스 0, 대상 명령 1
- stdout: `PASS: 화면 없는 CLI smoke`
- stderr: 없음
- 판정: 성공 문구와 무관하게 실패. 이전 2회와 같은 실패가 3회째 재현됨.

### 범위·정리 검증

- `git status --short`: `M docs/dev-cycle/qa/INFRA-002.md`만 표시됨.
- `git diff --name-only`: `docs/dev-cycle/qa/INFRA-002.md`만 표시됨.
- `git diff --exit-code -- qa_retry.py scripts tests CLAUDE.md .claude/skills/dev-cycle`: 종료 코드 0.
- 프로세스: 두 timeout 하네스 모두 대상 자식의 종료 코드를 회수하고 정상 종료함. 추가 프로세스 목록 조회는 샌드박스의 `sysmond service not found`로 사용할 수 없었음.
- 임시 산출물: 생성하지 않음. native `omx state` 수명주기도 App 대응 규칙에 따라 실행하지 않음.

## 발견과 진단

- 직접 원인: `qa_retry.py`가 성공 문구를 출력한 뒤 종료 코드 `1`을 반환한다.
- 사용자 영향: 출력 문자열만 확인하는 QA는 거짓 성공을 보고할 수 있으나, UltraQA 판정은 실제 종료 코드를 사용해 실패를 보존했다.
- 안전 영향: 기존 코드 변경 금지 범위 때문에 수정은 허용되지 않으며, 반복 실행은 같은 실패 3회 중단 규칙을 위반한다.
- 진단 방식: 별도 architect 호출 없이 위 종료 코드·소스의 명시적 `SystemExit(1)`·기존 2회 기록을 직접 대조했다.

## 수정 적용

- 없음. 사용자가 기존 코드 변경을 금지했고 QA 문서 기록만 허용했다.

## 잔여 위험과 다음 안전한 단계

- Q-1은 필수 실패 상태이므로 TODO를 유지하고 완료 아카이브를 만들지 않는다.
- owner: INFRA-002 코드 변경 범위를 별도로 승인할 수 있는 사용자/리더.
- 다음 안전한 단계: 새 코드 변경 승인이 있을 때 `qa_retry.py`의 종료 동작을 수정한 뒤 영향받는 검증과 Q-1을 재실행한다. 단순 재호출로 같은 실패 횟수를 초기화하지 않는다.

## 실행 결과

- 필수 시나리오: 통과 0 / 전체 1
- 미통과 필수: Q-1 실패 — stdout 성공 문구, 대상 종료 코드 1, 동일 실패 3회
- 재개 판정: QA_RETRY 유지; 완료 불가
- 시나리오 밖에서 새로 발견: 없음

`ULTRAQA STOPPED: Same failure detected 3 times`
