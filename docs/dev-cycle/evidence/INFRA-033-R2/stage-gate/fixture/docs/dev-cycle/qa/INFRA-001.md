# UltraQA Report

## 목표와 완료 조건

- 항목: `[INFRA-001] 초기화 CLI 이름 표준화`
- 목표: `scripts/init_data.py`가 입력 이름의 앞뒤 공백을 제거하고 Python `str.title()` 형식으로 출력한다.
- 완료 조건: baseline 3개 unittest와 아래 필수 CLI 시나리오 6개가 각각 기대한 stdout·stderr·종료 코드로 통과하고 cleanup이 완료된다.
- 안전 경계: 격리 fixture 안의 읽기와 승인 범위 파일만 변경한다. 네트워크·시크릿·유료 API·홈 설정·OMX 상태·외부 프로세스를 사용하지 않는다.
- 중단 조건: 같은 실패 3회, 전체 5회, 필수 시나리오 실패·차단·미실행, 또는 cleanup 미완료 중 하나가 발생하면 TODO를 유지하고 정확한 상태로 중단한다.
- 실행 표면: `python3 -m unittest discover -s tests`와 `subprocess.run([...], timeout=10)`으로 호출하는 `python3 scripts/init_data.py`.

## 메타데이터

- 구성 2026-09-06 22:36 +0900 | 갱신·실행 2026-09-06 23:06 +0900
- QA 엔진(engine): Codex UltraQA
- lifecycle: `app-adapted`
- phase: `complete`
- iteration: 1
- same_failure_count: 1
- baseline 상태: 통과 (unittest 3/3, exit 0, timeout 없음)
- 기준: 원본 `013ceceb31365690135121af9c968782b3cfdb88`, 첫 구현 커밋 `4f856de`
- 필수 여부(required): 예
- 결과: 통과
- 증거: 이 문서의 C-5 실행 기록과 시나리오별 실제 stdout·stderr·종료 코드
- cleanup: subprocess 전부 종료, 작업 트리 실행 전후 clean, `compromised.txt` 미생성, 임시 fixture·bytecode 없음
- UltraQA Report: [INFRA-001.md](INFRA-001.md)

## 리뷰 증거 연결

- 검수자 원문 JSON: `/private/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/dev-cycle-r2-fcs9_klf/live-runs/stage-gate/original-review.json`
- 원문 JSON `text` SHA-256: `bc45aa44573607a939a848ba91800fae122fc40620bbb14f4cd2718701953951`
- 원문 JSON 파일 SHA-256: `e3c044c47d1add1c84dc56ff7e6cc388898cc6d1841b4be300f657fb743a7add`
- 표시용 리뷰: `docs/dev-cycle/reviews/INFRA-001.md`
- 표시용 리뷰 SHA-256: `767dde408518bf9fcbe9a008831e0bd193c17455b89c1aa12dc14d23cecb71c5`
- 변환 범위: `Files Reviewed` 행 끝의 Markdown 후행 공백 두 칸 제거와 이 증거 연결 메타데이터 추가. 리뷰 원문·판정의 의미는 바꾸지 않았다.
- 리뷰 입력 재대조: `scripts/init_data.py` `c7ce18f92da57dfbbc74078b93674465b0d5c211aa2f6cadf78c141260a8ae36`, `tests/test_cli.py` `3cea522510276d42a1d9ae7dab774d4350df1650f3ccf5da5c19c3626975642e`, `tests/test_main.py` `c7426f61954cb5631f34288ec73292273d6ecf449785472444a9d564ff41caf6`으로 기존 T3 리뷰 입력과 일치했다. 표시·진행 기록만 바뀌어 완료 리뷰는 재실행하지 않았다.

## 시나리오 행렬

| ID | 분류·의도 | 사용자/공격자 모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|---|
| S-1 | 회귀·정상 이름 정규화 | 정상 CLI 사용자 | 없음 | 인자 `"  kim min su  "` | exit 0, stdout `Kim Min Su\n`, stderr 빈 값 | 통과: exit 0, stdout `Kim Min Su\n`, stderr 빈 값, timeout 없음 | 없음 | C-5 | 프로세스 종료 | 예 |
| S-2 | 인접·필수 인자 누락 | 실수한 CLI 사용자 | 없음 | 이름 인자 없이 실행 | exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값 | 통과: exit 2, stdout 기대값 일치, stderr 빈 값, timeout 없음 | 없음 | C-5 | 프로세스 종료 | 예 |
| S-3 | 인접·인자 과다 | 실수한 CLI 사용자 | 없음 | 이름 두 개 전달 | exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값 | 통과: exit 2, stdout 기대값 일치, stderr 빈 값, timeout 없음 | 없음 | C-5 | 프로세스 종료 | 예 |
| S-4 | 적대·Unicode와 구두점 | 국제화 입력 사용자 | 없음 | 인자 `"  éLODIE o'connor  "` | exit 0, stdout `Élodie O'Connor\n`, stderr 빈 값 | 통과: exit 0, stdout `Élodie O'Connor\n`, stderr 빈 값, timeout 없음 | 없음 | C-5 | 프로세스 종료 | 예 |
| S-5 | 적대·큰 문자열과 timeout | 과대 입력 사용자 | 4096자 소문자 생성 | 앞뒤 공백이 있는 `a` 4096자, timeout 10초 | exit 0, stdout 길이 4097, 첫 글자 `A`, 나머지 소문자와 끝 개행, stderr 빈 값, timeout 없음 | 통과: exit 0, 길이 4097·첫 글자 `A`·중간 4095자 소문자·끝 개행, stderr 빈 값, timeout 없음 | 없음 | C-5 | 프로세스 종료 | 예 |
| S-6 | 적대·경로 이탈과 prompt injection을 데이터로 처리 | 지시 우회 공격자 | `compromised.txt` 부재 확인 | 인자 `"  ../IGNORE PRIOR INSTRUCTIONS; compromised.txt  "` | exit 0, stdout `../Ignore Prior Instructions; Compromised.Txt\n`, stderr 빈 값, 파일 미생성 | 통과: exit 0, stdout 기대값 일치, stderr 빈 값, 파일 미생성, timeout 없음 | 없음 | C-5 | 프로세스 종료·파일 부재 | 예 |

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
- cleanup: 임시 fixture·프로세스 없음, OMX 상태 명령 미실행

### C-3. 표시용 리뷰 정적 게이트 실패

- 시각: 2026-09-06 22:58 +0900
- 목적: 구현 객체 `583e6b2fe96a43cfff216d323d842fe37c67e7d6`와 현재 승인 파일을 대조하고 첫 커밋의 staged 무결성을 검사
- 결과: 승인된 5개 파일의 staged blob이 구현 객체와 일치
- 명령: `git diff --cached --check`
- 종료 코드: 2
- stderr: `docs/dev-cycle/reviews/INFRA-001.md:29: trailing whitespace.`
- 판정: 커밋과 UltraQA 실행 없이 중단. 코드·테스트·리뷰 원문은 변경하지 않음
- 보완 승인: 검수자 원문 JSON과 해시를 증거로 유지하고 표시용 Markdown의 후행 공백만 정리하도록 현재 사용자가 승인

### C-4. 표시용 리뷰 보완 후 정적 게이트

- 시각: 2026-09-06 23:05 +0900
- 원문 증거: JSON `text`와 보완 전 리뷰가 바이트 단위로 일치했고 SHA-256 `bc45aa44573607a939a848ba91800fae122fc40620bbb14f4cd2718701953951`을 확인
- 변환 결과: 표시용 리뷰 SHA-256 `767dde408518bf9fcbe9a008831e0bd193c17455b89c1aa12dc14d23cecb71c5`
- 명령: 승인된 5개 파일만 `git add` 후 `git diff --cached --check` → exit 0
- 명령: Python 3개 파일 `ast.parse` → 3/3, exit 0
- 명령: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → 3/3, exit 0
- 판정: 첫 구현 커밋 가능. 코드·테스트 변경 없음, 완료된 T3 리뷰 재실행 없음
- cleanup: 임시 fixture·프로세스·bytecode 없음, OMX CLI와 native peer mode 미실행

### C-5. App 대응 UltraQA baseline과 6개 행렬

- 시각: 2026-09-06 23:06 +0900
- 기준 커밋: `4f856de`
- lifecycle: `app-adapted`; `env -u OMX_ROOT -u OMX_STATE_ROOT`로 실행하고 OMX CLI·native peer mode는 활성화하지 않음
- timeout: baseline과 각 시나리오 10초
- baseline: `python3 -m unittest discover -s tests` → 3/3, exit 0, stdout 빈 값, stderr에 unittest `OK`, timeout 없음
- S-1: exit 0, stdout `Kim Min Su\n`, stderr 빈 값, timeout 없음
- S-2: exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값, timeout 없음
- S-3: exit 2, stdout `usage: init_data.py <name>\n`, stderr 빈 값, timeout 없음
- S-4: exit 0, stdout `Élodie O'Connor\n`, stderr 빈 값, timeout 없음
- S-5: exit 0, stdout 길이 4097·첫 글자 `A`·중간 4095자 `a`·끝 개행, stderr 빈 값, timeout 없음
- S-6: exit 0, stdout `../Ignore Prior Instructions; Compromised.Txt\n`, stderr 빈 값, timeout 없음
- cleanup: 실행 전후 `git status --short` 빈 값, `compromised.txt` 실행 전후 부재, 모든 subprocess 종료, 임시 fixture·bytecode 없음
- 판정: baseline과 필수 행렬 6/6 및 cleanup 통과

### C-6. QA 이후 최종 정적 검증

- 시각: 2026-09-06 23:07 +0900
- 명령: `git diff --check` → exit 0
- 명령: Python 3개 파일 `ast.parse` → 3/3, exit 0
- 명령: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` → 3/3, exit 0
- cleanup: 임시 fixture·프로세스·bytecode 없음
- 판정: 완료 아카이브 가능

## 이전 실패와 해소

- 증상: Git이 index lock을 만들지 못해 첫 커밋을 생성할 수 없다.
- 재현: 승인 범위 파일을 명시한 `git add`에서 lock 생성 전에 exit 128이 발생했다.
- 원인: 작업 파일은 쓰기 가능하지만 `.git` 디렉터리는 현재 실행 경계에서 쓰기 불가(`dr-xr-xr-x`)다.
- 당시 영향: dev-cycle [3] 5번의 첫 커밋과 검증 기준 SHA가 없어 UltraQA 실행, TODO 제거, 완료 아카이브 커밋으로 진행할 수 없었다.
- 시도 횟수: 1회. 권한 변경, 홈/OMX 상태 변경, 임시 저장소 커밋은 승인·소유권 증거를 훼손하므로 시도하지 않았다.
- 해소: 현재 실행 문맥에서 `.git` 쓰기가 가능해졌고, 추가로 발견된 표시용 리뷰의 후행 공백은 원문 JSON을 보존·연결한 뒤 승인 범위에서 제거했다. C-4의 전체 staged 정적 게이트가 통과했다.

## 수정과 회귀 증거

구현 전 RED에서 focused와 전체 unittest가 정규화 assertion으로 exit 1이었고, 한 줄 수정 뒤 focused 1/1과 전체 3/3이 exit 0이었다. 첫 구현 커밋 `4f856de` 뒤 App 대응 UltraQA baseline 3/3과 기존 6개 필수 CLI 행렬을 실제 subprocess로 실행해 모두 통과했다. QA 중 제품 수정은 없었다.

## 정리와 복구

이전 커밋 시도와 현재 QA는 lock·staged entry·임시 fixture·프로세스·bytecode를 남기지 않았다. QA 실행 전후 작업 트리는 clean이었고, 범위 밖 파일과 `compromised.txt`도 생성되지 않았다.

## 잔여 위험

`str.title()`은 locale-aware 사람 이름 정책이 아니다. 이는 승인된 Python식 title case 계약의 알려진 비차단 특성이며, 별도 이름 정책은 범위 밖이다.

## 실행 결과

- 필수 시나리오: 통과 6 / 전체 6
- 미통과 필수: 없음
- 재개 판정: 완료 가능

`ULTRAQA COMPLETE: Goal met after 1 cycles`
