# INFRA-001 이름 정규화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 초기화 CLI가 이름의 앞뒤 공백을 제거하고 각 단어를 제목 형식으로 출력하게 한다.

**Architecture:** 기존 `format_name(raw: str) -> str` 경계를 유지하고 Python 문자열 연산만으로 정규화한다. 기존 단위 테스트를 RED/GREEN 회귀 기준으로 사용하고, 실제 subprocess로 CLI 출력과 종료 코드를 검증한다.

**Tech Stack:** Python 3 표준 라이브러리, `unittest`, `subprocess`, Git

**Spec:** 현재 대화에서 2026-09-06 승인된 bounded 설계와 `docs/dev-cycle/TODO.md`의 `[INFRA-001]`

## Global Constraints

- 변경은 격리 fixture 저장소와 승인된 `INFRA-001` 범위에 한정한다.
- 외부 네트워크, 시크릿, `.env`, `data/`, 홈 설정, OMX 상태를 변경하지 않는다.
- 표준 검증 명령은 `python3 -m unittest discover -s tests`다.
- T3 절차로 ponytail, 코드, 심층 독립 리뷰를 순서대로 수행한다.
- App 대응 UltraQA 행렬의 필수 시나리오는 실제 stdout, stderr, 종료 코드로 판정한다.

---

### Task 1: 이름 정규화 결함 수정

**Files:**
- Modify: `scripts/init_data.py:8-11`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `format_name(raw: str) -> str`에 전달되는 CLI 이름 문자열
- Produces: 앞뒤 공백이 제거되고 각 단어가 제목 형식인 문자열

- [x] **Step 1: 기존 회귀 테스트가 결함을 재현하는지 확인**

Run: `python3 -m unittest tests.test_cli.CliTest.test_format_name_trims_and_title_cases_input`

Expected: `AssertionError: '  kim min su  ' != 'Kim Min Su'`, exit 1.

- [x] **Step 2: 최소 구현 적용**

```python
def format_name(raw: str) -> str:
    """사용자 입력을 표시 문자열로 바꾼다."""
    return raw.strip().title()
```

- [x] **Step 3: focused GREEN 확인**

Run: `python3 -m unittest tests.test_cli.CliTest.test_format_name_trims_and_title_cases_input`

Expected: 1 test passes, exit 0.

- [x] **Step 4: 전체 회귀 확인**

Run: `python3 -m unittest discover -s tests`

Expected: 3 tests pass, exit 0.

### Task 2: T3 리뷰와 QA 기준선 보존

**Files:**
- Modify: `docs/dev-cycle/TODO.md`
- Create: `docs/dev-cycle/qa/INFRA-001.md`
- Review: `scripts/init_data.py`, `tests/test_cli.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: Task 1의 GREEN 구현과 원본 커밋 `013cece`
- Produces: T3 독립 리뷰 verdict, 정적 검증 결과, App 대응 UltraQA 행렬, 첫 구현 커밋

- [x] **Step 1: ponytail 독립 리뷰 수행**

검토 범위는 원본 `013cece` 대비 승인 범위 diff이며, 삭제 가능성·중복·불필요한 추상화·테스트 비용을 검토한다.

- [x] **Step 2: 코드 독립 리뷰 수행**

정확성, 회귀, 보안 경계, 테스트 충분성을 검토하고 확신도 기준을 적용한다.

- [x] **Step 3: T3 심층 독립 리뷰 수행**

원본 대비 전체 diff에서 구조적 위험, 잘못된 성공 판정, 승인 범위 이탈을 검토한다.

- [x] **Step 4: 정적 검증 재실행**

Run: `python3 -m unittest discover -s tests`

Expected: 3 tests pass, exit 0.

- [x] **Step 5: UltraQA 계획 작성 및 첫 커밋**

정상 이름, 누락/초과 인자, Unicode/큰 문자열, 경로형 문자열, prompt-injection 문자열을 안전한 subprocess 행렬로 정의한다. 구현·계획·TODO 진행 기록·QA 행렬만 스테이징해 `fix(infra): normalize initialization CLI names`로 커밋한다.

차단 이력: 2026-09-06 22:39 +0900에 명시 파일을 `git add`하려 했으나 Git이 `.git/index.lock`을 만들 수 없어 exit 128로 실패했다. staged entry와 lock 잔재는 0개였다. 2026-09-06 22:46 +0900 재개에서 동일 HEAD·리뷰 해시와 검토 대상 코드 해시를 대조하고 정적 검증 3/3을 다시 통과해 첫 커밋을 재시도했다.

### Task 3: App 대응 UltraQA 실행과 완료 아카이브

**Files:**
- Modify: `docs/dev-cycle/qa/INFRA-001.md`
- Modify: `docs/dev-cycle/TODO.md`
- Create: `docs/dev-cycle/archive/2026-09.md`
- Create: `docs/dev-cycle/archive/daily/2026-09-06.md`

**Interfaces:**
- Consumes: Task 2의 첫 커밋 SHA와 확정된 필수 QA 행렬
- Produces: 실제 명령별 종료 코드·stdout·stderr 증거, 정리 판정, TODO 제거, 완료 아카이브

- [ ] **Step 1: baseline과 필수 행렬 실행**

각 명령은 timeout 10초로 실행하고 실제 종료 코드, stdout, stderr를 기록한다. 비용·네트워크·외부 상태 변경은 실행하지 않는다.

- [ ] **Step 2: QA 결과와 정리 기록**

모든 필수 시나리오 및 baseline이 통과하고 소유한 임시 프로세스·fixture가 없음을 확인한 경우에만 `ULTRAQA COMPLETE: Goal met after 1 cycles`를 기록한다.

- [ ] **Step 3: 최종 검증**

Run: `python3 -m unittest discover -s tests`

Expected: 3 tests pass, exit 0. 이어서 `git diff --check`가 exit 0이어야 한다.

- [ ] **Step 4: 완료 아카이브 커밋**

월별·일별 완료 기록에 첫 커밋 SHA와 실제 검증 수를 기록하고 `[INFRA-001]`을 TODO에서 제거한다. QA 문서·TODO·아카이브만 스테이징해 `docs(dev-cycle): archive INFRA-001 completion`으로 커밋한다.
