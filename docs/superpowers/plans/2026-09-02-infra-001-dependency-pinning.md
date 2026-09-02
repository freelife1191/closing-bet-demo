# [INFRA-001] 파이썬 의존성 버전 고정 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `requirements.txt` 를 실제 사용과 일치시키고 검증된 버전으로 고정해,
새 환경에서 `pip install -r requirements.txt` 를 돌렸을 때 오늘 동작하는 조합이
그대로 재현되게 만든다.

**Architecture:** 파일 하나를 다시 쓰고 파일 하나를 지운다. 실행 코드는 건드리지
않는다. 핀 방식은 직접 의존성 16개에 대한 `==` 정확 고정이다. 전이 의존성까지 잠그는
`package-lock.json` 수준의 재현성은 아니다. 그 수준을 노리면 `pip freeze` 전체를 박아야
하는데, 그렇게 만들어진 것이 이번에 폐기하는 `requirements.updated.txt` 이고 유지되지
않았다. 직접 의존성 고정과 `pip check` 통과를 실용적 절충선으로 삼는다.

**Tech Stack:** pip, venv, Python 3.11.16

**Spec:** `docs/dev-cycle/audits/AUDIT-INFRA.md` §203-213, `docs/dev-cycle/TODO.md`
의 `[INFRA-001]`

## Global Constraints

- 티어는 T3 이다. `TODO.md` 가 지정했고 `tier-rules.md` 는 하향을 금지한다.
- 실행 코드(`.py`)를 한 줄도 바꾸지 않는다. `np.float_` 수정은 이 항목의 범위 밖이며
  `[INFRA-018]` 로 넘긴다.
- 핀에 적는 버전은 2026-09-02 기준 `venv` 에 실제로 설치되어 pytest 1536건을
  통과시키고 있는 버전이다. 추측한 버전을 적지 않는다.
- `numpy` 상한은 코드 사정과 패키지 사정이 겹친 지점이다. 아래 조사 결과를 참조한다.
- `google-genai` 는 1.62.0 에 고정한다. 2.x 승격은 이 사이클에서 하지 않는다.

---

## 조사 결과 (구현 전 확정 사실)

536개 파이썬 파일을 AST 로 훑어 서드파티 import 를 전수 조사한 결과다.

### 실사용인데 `requirements.txt` 에 없는 것

| 패키지 | 사용처 수 | 대표 위치 |
|---|---|---|
| `numpy` | 11곳 | `engine/pandas_utils_safe.py`, `numpy_json_encoder.py` |
| `beautifulsoup4` (`bs4`) | 12곳 | `engine/collectors/naver.py`, `engine/collectors.py` |
| `httpx` | 3곳 | `engine/vcp_ai_analyzer.py:10` |
| `pytest` | 15곳 | `tests/**` |

세 패키지는 지금 `pandas`·`yfinance`·`openai` 의 전이 의존성으로 우연히 설치되어
있다. 상위 패키지가 의존을 떼면 즉시 `ImportError` 가 난다.

### `requirements.txt` 에 있는데 아무도 쓰지 않는 것

| 패키지 | 확인 |
|---|---|
| `apscheduler` | 저장소 전체에서 참조가 `requirements.txt:7` 한 줄뿐이다. 스케줄러는 `schedule` 을 쓴다 |
| `pytz` | 파이썬 코드에 직접 참조가 없다. `pandas` 와 `yfinance` 가 요구하므로 지워도 설치된다 |

### numpy 2.x 를 막는 것은 두 가지다

`numpy_json_encoder.py:38` 의 `np.float_` 참조가 하나이고, `pykrx` 의 의존성 제약이
다른 하나다. PyPI 메타데이터를 버전별로 조회한 결과는 이렇다.

| pykrx | numpy 제약 |
|---|---|
| 1.2.3 ~ 1.2.6 | `numpy<2.0,>=1.24.0` |
| 1.2.7 ~ 1.2.8 | `numpy>=2.0` |

지금 쓰는 1.2.3 이 이미 `numpy<2.0` 을 강제하므로, 코드에서 `np.float_` 을 없애도
pykrx 를 1.2.7 이상으로 올리기 전에는 numpy 2.x 가 설치되지 않는다. 반대로 pykrx 만
올리면 numpy 1.x 가 금지되어 `np.float_` 이 즉시 깨진다. 둘은 한 묶음이며
`[INFRA-018]` 이 그 묶음을 담당한다.

### `google-genai` 2.x 호환성 실측

격리한 venv(`python3.11 -m venv`)에 `google-genai==2.21.0` 을 설치해 이 저장소가
실제로 쓰는 API 표면 아홉 가지를 1.62.0 과 대조했다. 아홉 가지 모두 두 버전에서
동일하게 통과했다.

1. `genai.Client(vertexai=)` / `(project=)` / `(location=)` / `(http_options=)`
2. `client.models` · `client.aio.models` · `client.models.list`
3. `client.models.generate_content(model=, contents=, config=)`
4. `types.GenerateContentConfig(max_output_tokens=)`
5. `genai.GenerativeModel` 부재 (`chatbot/core.py:37` 의 호환 셸이 이를 전제한다)
6. `google.genai.errors.APIError` · `ClientError` (429 재시도 경로가 참조한다)

`AUDIT-INFRA.md:208` 은 2.x 승격 시 numpy 가 전이 의존성으로 따라 올라온다고
적었으나, 2.21.0 이 끌고 오는 24개 패키지에 numpy 는 없다. 두 문제는 독립이다.

의존성 부담도 우려만큼 크지 않다. PyPI 메타데이터상 필수 의존성은 두 버전 모두
10개(anyio, google-auth, httpx, pydantic, requests, tenacity, websockets,
typing-extensions, distro, sniffio)로 같다. 2.21.0 이 추가로 선언하는 torch,
torchvision, transformers, pillow, pyopenssl 은 모두 extras 라서 기본 설치에
들어오지 않는다. 실질적인 차이는 하한 세 개가 오르는 것뿐이다.

| 패키지 | 1.62.0 | 2.21.0 | 현재 설치본 |
|---|---|---|---|
| `google-auth` | `>=2.47.0` | `>=2.56.0` | 2.48.0 (승격 필요) |
| `pydantic` | `>=2.9.0` | `>=2.12.5` | 2.12.5 (충족) |
| `typing-extensions` | `>=4.11.0` | `>=4.14.0` | 4.15.0 (충족) |

그럼에도 이 사이클에서 승격하지 않는다. 확인한 것은 API 표면이지 호출 동작이
아니다. 응답 파싱, 예외 메시지, 재시도 거동이 같은지는 Vertex AI 로 실제 과금
호출을 해 봐야 알 수 있고, 그것은 이 항목의 범위가 아니다. 핀 고정과 메이저
승격을 한 커밋에 섞으면 문제가 생겼을 때 원인을 가릴 수 없기도 하다.
`TODO.md` 의 체크박스도 "호환성 확인" 만 요구한다.

---

## File Structure

- Modify: `requirements.txt` — 14줄에서 주석 포함 40줄 안팎으로. 용도별로 묶고
  각 핀에 이유가 필요한 것만 주석을 단다
- Delete: `requirements.updated.txt` — 2026-05-05 Vertex 마이그레이션 때의
  `pip freeze` 산출물. 어디서도 참조되지 않고 `google-auth==2.49.0.dev0` 처럼
  PyPI 에 없는 개발 버전이 들어 있어 그대로 설치하면 실패한다
- Modify: `docs/dev-cycle/TODO.md` — `[INFRA-001]` 제거, `[INFRA-018]` 추가

---

### Task 1: requirements.txt 를 실제 사용과 일치시키고 고정한다

**Files:**
- Modify: `requirements.txt`
- Delete: `requirements.updated.txt`

**Interfaces:**
- Consumes: `venv` 에 설치된 실제 버전 (`pip list`)
- Produces: `restart_all.sh:62` 와 `CLAUDE.md:28`, `AGENTS.md:14` 가 참조하는
  설치 명령이 재현 가능해진다

- [x] **Step 1: 현재 설치 버전을 근거로 확보한다**

```bash
source venv/bin/activate
pip list | grep -iE "^(flask|flask-cors|pandas|numpy|requests|httpx|beautifulsoup4|python-dotenv|google-genai|yfinance|pykrx|finance-datareader|gunicorn|schedule|openai|pytest)\b"
```

기대: 16개 패키지의 버전이 모두 출력된다. 하나라도 빠지면 그 패키지는 설치되어
있지 않은 것이므로 핀에 적기 전에 원인을 확인한다.

- [x] **Step 2: requirements.txt 를 다시 쓴다**

용도별로 묶고, 이유가 필요한 핀에만 주석을 단다. 버전은 Step 1 의 출력값을
그대로 옮긴다.

- [x] **Step 3: requirements.updated.txt 를 지운다**

```bash
git rm requirements.updated.txt
```

- [x] **Step 4: 새 환경에서 설치를 실측한다**

```bash
python3.11 -m venv /tmp/pinverify
/tmp/pinverify/bin/pip install -r requirements.txt
/tmp/pinverify/bin/pip check
```

기대: 설치가 성공하고 `pip check` 가 `No broken requirements found.` 를 낸다.
이 단계가 이 항목의 핵심 검증이다. 핀을 박았는데 그 조합이 설치되지 않으면
파일은 문서일 뿐 재현성이 아니다.

- [x] **Step 4-1: 새 환경에서도 pytest 가 통과하는지 확인한다**

전이 의존성은 고정하지 않으므로 새 환경에는 최신 버전이 들어온다. 그 조합에서도
테스트가 통과해야 핀이 의미를 갖는다.

```bash
/tmp/pinverify/bin/python -m pytest -q
```

기대: 1536 passed, 2 skipped.

- [x] **Step 5: 기존 venv 에서 pytest 전체를 돌린다**

```bash
source venv/bin/activate && pytest
```

기대: 1536 passed, 2 skipped. 실행 코드를 바꾸지 않았으므로 결과가 달라지면
안 된다.

---

### Task 2: numpy 2.x 승격을 백로그로 넘긴다

**Files:**
- Modify: `docs/dev-cycle/TODO.md`

- [x] **Step 1: `[INFRA-018]` 을 P1 에 추가한다**

`numpy_json_encoder.py:38` 이 numpy 2.x 에서 제거된 `np.float_` 을 참조한다.
`numpy==1.26.4` 핀이 지금은 막고 있으나 상한을 영구히 둘 수는 없다. 항목에는
`np.float_` 참조 위치와, 이 사이클에서 `numpy` 에 상한을 둔 이유를 함께 적는다.

- [x] **Step 2: `[INFRA-001]` 블록을 P0 에서 제거한다**

---

## Self-Review

**스펙 커버리지**: `TODO.md` 의 체크박스 네 개가 모두 대응한다. 버전 핀은 Task 1
Step 2, `google-genai` 호환성 확인은 위 "조사 결과" 절이 이미 실측으로 채웠고,
`requirements.updated.txt` 폐기는 Task 1 Step 3, pytest 통과는 Task 1 Step 5 다.

**플레이스홀더**: 없다. 버전 값은 Step 1 의 실제 출력에서 가져오고, 삭제 대상
파일과 명령은 모두 실재한다.

**타입 정합성**: 해당 없다. 실행 코드를 바꾸지 않는다.

---

## 진행 상황 (압축 대비 복구 지점)

- [x] Task 1 전부 (핀 적용, updated 파일 삭제, 새 venv 설치 + `pip check`, pytest)
- [x] Task 2 전부 (`[INFRA-018]` 추가, `[INFRA-001]` 제거)
- [x] `/ponytail-review` — 섹션 헤더 7개와 pip 상식 한 줄 제거, 주석 두 개 축약 (38줄 → 29줄)
- [x] `/code-review` — 7건 중 3건 반영. pykrx 의 numpy 제약, 전이 의존성 미고정,
      openai 에 잘못 걸리는 주석
- [x] `/review` — 1건 자동 수정. "전이 의존성 26개" 가 사실과 달라 실측값으로 교체
- [x] pytest 1536 통과 2 스킵 (기존 venv, 새 venv 양쪽)
- [x] vitest 22파일 188건 통과
- [x] `/qa-only http://localhost:3500/dashboard/kr --quick` — 95/100, 신규 발견 없음
- [x] [4] 마감 — 커밋 두 개
