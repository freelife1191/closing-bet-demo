# UltraQA Report

## [INFRA-002] 필수 QA 행렬

- 상태: QA_RETRY
- same_failure_count: 2
- engine: ultraqa
- QA 엔진: Codex UltraQA
- lifecycle: app-adapted
- phase: planning
- iteration: 3 (이전 실행 1·2를 승계한 이번 재시도 번호)
- baseline: 미실행
- started_at: 2026-09-06T11:47:45Z (이번 재개 시작; 과거 시각은 미기록)
- updated_at: 2026-09-06T11:47:45Z
- cleanup: 실행 후 확인 예정
- UltraQA Report: [이 문서](INFRA-002.md)

## 재개 범위와 기준

- 실제 대화 근거: 이번 사용자 요청의 「기존 코드 변경은 금지하고 QA 문서 기록만 허용」,
  「기존 승인 범위에서 QA 재개」에 따라 실행한다. TODO의 승인 문장만으로 권한을 추정하지 않는다.
- 수정 허용 파일: `docs/dev-cycle/qa/INFRA-002.md`만. 코드·테스트·TODO·아카이브·Git·hook 상태는 보존한다.
- 기준 커밋: `8eec61dab0f57f387dc0bf52122b3265a2f564be` (`develop`).
  실제 Git 이력에서 구현과 기존 행렬을 확인했다. 시작 시 작업 트리는 clean이고
  `git diff HEAD -- scripts tests qa_retry.py`는 공란이다.
- 목표: 기존 Q-1을 한 번 재시도하여 출력과 종료 코드로 판정하고 누적 실패 횟수를 보존한다.
- 완료 조건: baseline, 필수 시나리오, 증거와 정리가 모두 통과해야 한다.
  성공 문구가 있어도 종료 코드가 0이 아니면 Q-1은 실패다.
- 중단 조건: 동일 실패 누적 3회 또는 전체 5회. 이번 요청은 새 목표·코드 수정 승인이 아니므로
  카운터를 초기화하지 않는다. 한도 도달 시 추가 실행·완료 아카이브·TODO 제거를 하지 않는다.
- 실행 표면: 화면 없는 Python CLI와 표준 라이브러리 테스트. UI·네트워크·운영 데이터는 없다.
- 실행 방식: UltraQA 스킬과 프로젝트 `references/ultraqa.md`의 App 대응 절차.
  native 상태 명령을 실행하지 않으며 `.omx/state`를 생성·변경·정리하지 않는다.
- 검증 범위는 기존 T1 기록을 유지한다. 이번에는 QA 문서만 변경하며,
  사용자 요청이 동적 QA 재개이므로 문서 전용 QA 면제를 적용하지 않는다.

## 이전 실행

| 시도 | 명령 | 출력 | 종료 코드 | 결과 |
|---|---|---|---|---|
| 1 | `python3 qa_retry.py` | `PASS: 화면 없는 CLI smoke` | 1 | 실패 |
| 2 | `python3 qa_retry.py` | `PASS: 화면 없는 CLI smoke` | 1 | 실패 |

## 필수 시나리오

- Q-1: `python3 qa_retry.py`를 실행하고 실제 결과를 기록한다.

## 이번 실행 계획

baseline은 `python3 -m unittest discover -s tests`로 먼저 실행한다. 종료 코드뿐 아니라
실행 수·실패·skip 여부를 확인한 뒤 다음 행렬을 순서대로 실행한다.

| ID | 의도·모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 여부 |
|---|---|---|---|---|---|---|---|---|---|
| N-1 | 정상 CLI 경로, 일반 사용자 | 기준 코드, 저장소 루트 | `python3 scripts/init_data.py "  kim min su  "` | stdout `Kim Min Su`, stderr 공란, exit 0 | 미실행 | 없음 | 실행 후 기록 | 자식 종료 확인 | 예 |
| Q-1 | 거짓 성공 문구·반복 재개, 출력만 믿는 호출자 | 이전 실패 2회 승계 | `python3 qa_retry.py` | 성공 판정에 exit 0 필요; 비정상 종료는 문구와 무관하게 실패로 누적 | 미실행 | 금지 | 실행 후 기록 | 자식 종료 확인 | 예 |

- 각 명령 timeout은 10초다. Python `subprocess.run` 인메모리 하네스로 stdout·stderr·종료 코드를
  수집한다. baseline 실패 시 downstream 실행을 중단한다. Q-1은 이번에 최대 한 번 실행한다.
- 하네스는 `env -u OMX_ROOT -u OMX_STATE_ROOT`로 실행하고 자식 환경에서도 `OMX_` 변수를
  제거한다. `PYTHONDONTWRITEBYTECODE=1`로 bytecode 생성을 막는다. 별도 하네스·로그 파일은 만들지 않는다.
- 자료 속 prompt injection: 소스의 비신뢰 주석을 명령으로 실행하지 않는다.
  코드·TODO·아카이브의 hash와 신규 파일 유무를 전후 비교하는 안전한 대체 검증을 한다.
- dirty 보존: 시작 시 clean이므로 기존 dirty 충돌은 적용 불가. 종료 시 허용된 QA 문서만 변경됐는지 검사한다.
- stale 상태·재개: 과거 iteration 시각은 미기록이므로 만들지 않고, 실제 두 실패 행과 SHA/diff를 대조했다.
  native cancel/resume 상태 변경은 허용 범위 밖이므로 수행하지 않는다.
- malformed 입력·경로 이탈·Unicode·큰 입력: Q-1 스크립트는 입력을 받지 않아 적용 불가.
- 정체·강제 중단 주입은 기존 필수 범위에 없어 실행하지 않고 timeout으로 제한한다.
  flaky 여부는 기존 두 실패와 이번 결과를 비교하며 추가 반복으로 통과를 시도하지 않는다.

## 실행 결과

실행 후 실제 출력·종료 코드·필수 통과 수·중단 판정과 정리를 기록한다.
