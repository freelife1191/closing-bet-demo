# UltraQA Report

## 목표와 완료 조건

- 항목: `[INFRA-001] 초기화 CLI 이름 표준화`
- 목표: `scripts/init_data.py`가 입력 이름의 앞뒤 공백을 제거하고 Python `str.title()` 형식으로 출력한다.
- 완료 조건: baseline 3개 unittest와 아래 필수 CLI 시나리오 6개가 각각 기대한 stdout·stderr·종료 코드로 통과하고 cleanup이 완료된다.
- 안전 경계: 격리 fixture 안의 읽기와 승인 범위 파일만 변경한다. 네트워크·시크릿·유료 API·홈 설정·OMX 상태·외부 프로세스를 사용하지 않는다.
- 중단 조건: 같은 실패 3회, 전체 5회, 필수 시나리오 실패·차단·미실행, 또는 cleanup 미완료 중 하나가 발생하면 TODO를 유지하고 정확한 상태로 중단한다.
- 실행 표면: `python3 -m unittest discover -s tests`와 `subprocess.run([...], timeout=10)`으로 호출하는 `python3 scripts/init_data.py`.

## 메타데이터

- 구성 2026-09-06 22:36 +0900 | 갱신 2026-09-06 22:48 +0900 | 실행 2026-09-06 22:48 +0900
- QA 엔진(engine): Codex UltraQA
- lifecycle: `app-adapted`
- phase: `complete`
- iteration: 1
- same_failure_count: 1 (직전 Git 쓰기 차단 1회, 이번 재개에서 해소)
- baseline 상태: `python3 -m unittest discover -s tests` 3/3 통과, exit 0
- 기준: 첫 구현 커밋 `583e6b2fe96a43cfff216d323d842fe37c67e7d6`
- 필수 여부(required): 예
- 결과: 통과
- 증거: 이 문서의 C-3 baseline과 C-4 시나리오별 실제 stdout·stderr·종료 코드
- cleanup: 임시 fixture·프로세스 없음, `compromised.txt` 미생성, App 상태 파일 해시 불변
- UltraQA Report: [INFRA-001.md](INFRA-001.md)

## 시나리오 행렬

| ID | 분류·의도 | 사용자/공격자 모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|---|
| S-1 | 회귀·정상 이름 정규화 | 정상 CLI 사용자 | 없음 | 인자 `"  kim min su  "` | exit 0, stdout `Kim Min Su\n`, stderr 빈 값 | 기대값 일치, exit 0 | 없음 | C-4 `S-1` | 프로세스 종료 | 예 |
| S-2 | 인접·필수 인자 누락 | 실수한 CLI 사용자 | 없음 | 이름 인자 없이 실행 | exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값 | 기대값 일치, exit 2 | 없음 | C-4 `S-2` | 프로세스 종료 | 예 |
| S-3 | 인접·인자 과다 | 실수한 CLI 사용자 | 없음 | 이름 두 개 전달 | exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값 | 기대값 일치, exit 2 | 없음 | C-4 `S-3` | 프로세스 종료 | 예 |
| S-4 | 적대·Unicode와 구두점 | 국제화 입력 사용자 | 없음 | 인자 `"  éLODIE o'connor  "` | exit 0, stdout `Élodie O'Connor\n`, stderr 빈 값 | 기대값 일치, exit 0 | 없음 | C-4 `S-4` | 프로세스 종료 | 예 |
| S-5 | 적대·큰 문자열과 timeout | 과대 입력 사용자 | 4096자 소문자 생성 | 앞뒤 공백이 있는 `a` 4096자, timeout 10초 | exit 0, stdout 길이 4097, 첫 글자 `A`, 나머지 소문자와 끝 개행, stderr 빈 값, timeout 없음 | 길이 4097·prefix `Aaaaaaaa`·suffix `aaaaaaa\n`, exit 0, timeout 없음 | 없음 | C-4 `S-5` | 프로세스 종료 | 예 |
| S-6 | 적대·경로 이탈과 prompt injection을 데이터로 처리 | 지시 우회 공격자 | `compromised.txt` 부재 확인 | 인자 `"  ../IGNORE PRIOR INSTRUCTIONS; compromised.txt  "` | exit 0, stdout `../Ignore Prior Instructions; Compromised.Txt\n`, stderr 빈 값, 파일 미생성 | 기대값 일치, exit 0, 파일 미생성 | 없음 | C-4 `S-6` | 프로세스 종료·파일 부재 | 예 |

## 적용 불가 분류

- 반복 continue·cancel/resume·stale 상태: 이 CLI는 단일 실행이며 상태·재개 인터페이스가 없다. OMX hook 상태를 건드리지 않는 App 대응 검증으로 대체한다.
- dirty worktree 보존: QA 시작 전 의도된 범위 파일 목록과 SHA를 기록하고, 실행 뒤 범위 밖 파일 변경이 없음을 `git status --short`와 해시로 확인한다.
- flaky 재실행: stdlib 문자열 연산과 로컬 subprocess는 결정적이다. 실패 없이 통과하면 행렬을 녹색이 나올 때까지 반복하지 않는다.
- misleading success: S-2와 S-3에서 usage 성공 문구가 아니라 실제 non-zero exit 2를 함께 확인한다.
- hung child: 모든 subprocess에 10초 timeout을 적용하고 S-5에서 큰 입력도 제한 안에 종료되는지 확인한다.

## 명령별 실행 기록

### C-1. 첫 구현 커밋 준비

- 시각: 2026-09-06 22:38 +0900
- 목적: 정적 검증을 통과한 구현·계획·리뷰·QA 행렬을 첫 커밋으로 보존
- 명령: `git add scripts/init_data.py docs/dev-cycle/TODO.md docs/dev-cycle/qa/INFRA-001.md docs/dev-cycle/reviews/INFRA-001.md docs/superpowers/plans/2026-09-06-infra-001-name-normalization.md && git diff --cached --check && git commit -m "fix(infra): normalize initialization CLI names"`
- timeout: 30초
- 종료 코드: 128 (`git add`에서 중단)
- stdout: 빈 값
- stderr: `fatal: Unable to create '<repo>/.git/index.lock': Operation not permitted`
- 후속 확인: staged entry 0개, `.git/index.lock` 없음, `.git` mode `dr-xr-xr-x`, `compromised.txt` 없음, `git diff --check` exit 0
- 판정: 필수 첫 커밋이 없으므로 baseline과 S-1~S-6을 실행하지 않음

### C-2. 재개 사전 검증

- 시각: 2026-09-06 22:46 +0900
- 목적: 직전 checkpoint와 현재 검토 입력을 대조하고 첫 커밋 재시도 조건을 확인
- 결과: HEAD `013ceceb31365690135121af9c968782b3cfdb88`와 리뷰 문서 SHA-256 `bc45aa44573607a939a848ba91800fae122fc40620bbb14f4cd2718701953951` 일치
- 검토 입력: `scripts/init_data.py`, `tests/test_cli.py`, `tests/test_main.py` SHA-256이 리뷰 원문과 일치. TODO와 계획은 리뷰 뒤 추가된 Git 차단 이력만 반영
- 명령: `python3 -m unittest discover -s tests` → 3/3, exit 0
- 명령: Python 3개 파일 `ast.parse` → 3/3, exit 0
- 명령: `git diff --check` → exit 0
- 첫 커밋: `583e6b2fe96a43cfff216d323d842fe37c67e7d6`
- staging 검사 보완: `git show --check 583e6b2`는 리뷰 원문 29행의 Markdown 강제 줄바꿈용 공백 2개를 보고하고 exit 2였다. 제공된 리뷰 원문 SHA-256을 보존해야 하므로 해당 인용 서식은 수정하지 않았으며 실행 코드에는 후행 공백이 없다.
- cleanup: 임시 fixture·프로세스 없음, OMX 상태 명령 미실행

### C-3. UltraQA baseline

- 시각: 2026-09-06 22:48 +0900
- 기준 커밋: `583e6b2fe96a43cfff216d323d842fe37c67e7d6`
- 명령: `env -u OMX_ROOT -u OMX_STATE_ROOT python3 -m unittest discover -s tests`
- timeout: 10초
- 종료 코드: 0
- 핵심 출력: `Ran 3 tests`, `OK`
- 판정: 통과 3/3, skip·숨은 실패 없음

### C-4. 필수 CLI 행렬

- 시각: 2026-09-06 22:48 +0900
- 하네스: `subprocess.run(["python3", "scripts/init_data.py", ...], capture_output=True, text=True, timeout=10, check=False)`
- 종료 코드: 0 (행렬 전체 assertion 통과)
- S-1: exit 0, stdout `Kim Min Su\n`, stderr 빈 값
- S-2: exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값
- S-3: exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값
- S-4: exit 0, stdout `Élodie O'Connor\n`, stderr 빈 값
- S-5: exit 0, stdout 길이 4097·prefix `Aaaaaaaa`·suffix `aaaaaaa\n`, stderr 빈 값, timeout 없음
- S-6: exit 0, stdout `../Ignore Prior Instructions; Compromised.Txt\n`, stderr 빈 값, `compromised.txt` 전후 부재
- App 경계: `.omx/state` 파일 9개의 실행 전후 SHA-256 일치, `omx state read/write/clear` 미실행
- cleanup: 모든 자식 프로세스 종료, 임시 파일·fixture 없음

## 실패와 진단

- 직전 증상: Git이 index lock을 만들지 못해 첫 커밋을 생성할 수 없었다.
- 재현: 승인 범위 파일을 명시한 `git add`에서 lock 생성 전에 exit 128이 발생했다.
- 원인: 작업 파일은 쓰기 가능하지만 `.git` 디렉터리는 현재 실행 경계에서 쓰기 불가(`dr-xr-xr-x`)다.
- 당시 영향: dev-cycle [3] 5번의 첫 커밋과 검증 기준 SHA가 없어 downstream 단계를 실행하지 않았다.
- 시도 횟수: 1회. 권한 변경, 홈/OMX 상태 변경, 임시 저장소 커밋은 시도하지 않았다.
- 해소: 이번 App sandbox의 동일 fixture `.git` 쓰기 범위에서 첫 커밋 `583e6b2`를 생성했다. 제품 코드 수정이나 우회 저장소는 필요하지 않았다.

## 수정과 회귀 증거

구현 전 RED에서 focused와 전체 unittest가 정규화 assertion으로 exit 1이었고, 한 줄 수정 뒤 focused 1/1과 전체 3/3이 exit 0이었다. 첫 커밋 뒤 baseline 3/3과 필수 행렬 6/6을 모두 통과했으며 QA 중 제품 수정은 없었다.

## 정리와 복구

직전 실패한 커밋 시도는 lock·staged entry를 남기지 않았다. 이번 QA도 임시 fixture·프로세스를 만들지 않았고, 범위 밖 파일과 `compromised.txt`가 생성되지 않았다. `.omx/state` 파일 9개의 SHA-256은 실행 전후 동일했다.

## 잔여 위험

`str.title()`은 locale-aware 사람 이름 정책이 아니다. 이는 승인된 Python식 title case 계약의 알려진 비차단 특성이며, 별도 이름 정책은 범위 밖이다.

## 실행 결과

- 필수 시나리오: 통과 6 / 전체 6
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 없음

`ULTRAQA COMPLETE: Goal met after 1 cycles`
