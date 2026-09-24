# [INFRA-089] KRX 가 끊은 세션을 곧바로 다시 로그인한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KRX 서버가 세션을 끊어 데이터 요청이 `400` + 본문 `LOGOUT` 을 받으면, pykrx 가 1시간 타이머를 기다리지 않고 재로그인 1회 뒤 같은 요청을 한 번 더 보내게 한다.

**Architecture:** 수정 자리는 저장소가 관리하는 pykrx 수정판(`vendor/pykrx/transport.patch` → wheel)의 `pykrx/website/comm/auth.py` 한 파일이다. 모든 KRX 데이터 요청이 `KRXSession._request` 를 지나므로 호출자(`scripts/init_data.py`, Market Gate, 수급 서비스)는 바꾸지 않는다. 재로그인은 모듈 함수 `_refresh_session(krxs, seen_login_time, reason)` 하나로 모으고 모듈 잠금으로 직렬화한다. 잠금 안에서 `login_time` 이 요청 시작 때 본 값과 다르면 다른 스레드가 이미 로그인한 것이므로 로그인하지 않는다. 재로그인이 실패하면 60초(`time.monotonic`) 동안 어느 경로에서도 로그인하지 않는다. 기존 1시간 타이머 재로그인(`get_auth_session`)도 같은 함수를 거치고, 세션이 없을 때의 첫 로그인 갈래도 같은 잠금과 차단 시각을 따른다(critic 권고 2). 별도로 `restart_all.sh` 의 gunicorn 실행에 `PYTHONUNBUFFERED=1` 을 준다.

**Tech Stack:** Python 3.11, requests, pytest, `patch`/`diff -U0`

**Spec:** 대화 설계(2026-09-25 07:09 승인), `docs/dev-cycle/TODO.md` `[INFRA-089]` 설계 승인 줄, 실측 근거 `docs/dev-cycle/qa/INFRA-089.md` 3·4차와 본문 판별 실측(07:07: 무효 세션 `400 b'LOGOUT'`, 잘못된 기간 `400 b'INVALIDPERIOD'`, 잘못된 bld `302` 빈 본문)

## Global Constraints

- 판별 조건은 정확히 `status_code == 400` 이고 `content.strip() == b"LOGOUT"` 이다. `INVALIDPERIOD`·`302`·그 밖의 응답에는 재로그인하지 않는다.
- 요청당 재로그인 시도는 최대 1회, 다시 보내기도 최대 1회다. 다시 보낸 응답이 여전히 `LOGOUT` 이면 그대로 돌려준다(호출자가 받는 오류는 종전과 같다).
- 재로그인 실패 뒤 60초(`_REFRESH_RETRY_SECONDS`) 동안은 타이머 경로와 LOGOUT 경로 모두 로그인하지 않는다.
- 자격 증명은 종전처럼 매번 `os.getenv("KRX_ID")`·`os.getenv("KRX_PW")` 로 읽는다. 값·응답 본문은 출력하지 않는다. 실패 출력에는 비밀이 아닌 범주(`krxs.last_error`)만 붙인다.
- `print` 는 `flush=True` 로 한다.
- `public_request`(미인증 경로)에는 재시도를 넣지 않는다.
- 로그인한 지 60초(`time.time() - seen_login_time`) 안에 받은 `LOGOUT` 에는 재로그인하지 않는다. 성공한 재로그인에는 실패 차단이 걸리지 않으므로, 프로세스끼리 서로 세션을 끊는 교대가 생겨도 프로세스당 로그인을 분당 1회로 묶는다. 다시 보내기 전 첫 응답은 `close()` 한다(보안 리뷰 Medium·Low 반영).
- 버전은 `1.2.9+cookie.3`. `rebuild.py` 의 `VERSION`, `requirements.txt` 핀, `vendor/pykrx/README.md` 의 제목·SHA·설치 문장을 함께 바꾸고 옛 wheel 을 지운다. 운영 반영은 `restart_all.sh` → `scripts/sync_dependencies.sh` 의 `pip install -r requirements.txt` 가 새 wheel 을 설치한다(장 마감 뒤 재기동).
- 패치는 upstream wheel 에 현재 패치를 적용한 트리와 upstream 원본을 `diff -U0 --label a/<경로> --label b/<경로>` 로 비교해 다시 만든다(현재 패치로 이 방법이 바이트까지 같게 재생성됨을 07:1x 에 확인).

## Review Focus

- 동시성: `refresh()` 는 로그인 전에 `self.session` 을 새 객체로 바꾼다. 그 틈에 다른 스레드가 반쯤 만든 세션으로 요청해 `LOGOUT` 을 받아도, 요청 시작 때 본 `login_time` 이 로그인 성공 뒤 바뀌므로 다시 로그인하지 않는다.
- 로그인 폭주: 재로그인 실패 뒤 대기 중인 스레드는 `login_time` 이 그대로이므로 차단 시각을 보고 로그인하지 않아야 한다.
- 무한 반복 없음: `_request` 는 재귀하지 않는다.
- 타이머 경로의 반환: 실패하면 `get_auth_session` 이 `None` 을 돌려 종전처럼 공개 요청으로 떨어진다.
- `response.content` 를 읽어도 스트리밍 요청이 없다(pykrx 는 `stream` 을 쓰지 않음).

## 알려진 한계

1. 서버가 세션을 끊는 원인은 다루지 않는다(재현되지 않음). 끊길 때마다 요청 하나가 재로그인 비용을 치른다.
2. KRX 점검 시간처럼 로그인 자체가 실패하면 60초마다 한 번 로그인을 시도하며, 그 동안의 요청은 종전처럼 빈 결과다.
3. 잠금은 프로세스 안에서만 유효하다. gunicorn 워커 둘과 별도 스크립트는 각자 로그인한다(종전과 같음).
4. `login_time` 은 `time.time()` 이다. 두 성공 로그인이 같은 값을 가지면 비교가 바뀐 것을 알아채지 못해 한 번 더 재로그인한다(드묾, 로그인 1회 추가). `refresh()` 는 `login_time` 을 인증 상태를 갖춘 뒤 마지막에 쓴다(코드 리뷰 low 1). LOGOUT 재로그인의 60초 간격도 이 벽시계로 재므로, 시계가 뒤로 조정되면 그 폭만큼 복구가 늦어진다(코드 리뷰 low 2).
5. `login_rejected`·`password_change_required` 처럼 다시 시도해도 성공하지 않는 실패도 60초마다 다시 로그인한다. 종전(호출마다 재시도)보다는 적지만, KRX 가 비밀번호 오류 횟수로 계정을 잠근다면 이 범주는 차단을 더 길게 두는 편이 안전하다(critic 권고 3, 이번 범위 밖).
6. 재로그인은 잠금을 쥔 채 네트워크 로그인(요청 timeout 15초, 최대 4요청)을 하므로, 세션이 무효인 동안 같은 프로세스에서 KRX 를 부르는 스레드는 모두 최대 약 60초 잠금에서 기다릴 수 있다(교착은 없음: `login_krx` 는 `_request` 를 거치지 않는다).
7. 서버가 「계정당 한 세션」이라 끊는 것이라면, 한 워커의 재로그인(CD011 → `skipDup=Y`)이 다른 워커의 세션을 끊는 교대가 생길 수 있다. 막지는 못하고, 로그인 뒤 60초 안의 LOGOUT 에는 재로그인하지 않는 규칙으로 프로세스당 분당 1회로 묶는다. 1·4차 실측에서 두 번째 로그인은 `CD001`·첫 세션 생존이라 가능성은 낮다. 버퍼링을 끈 뒤 운영 로그에서 워커별 「서버에서 끊김(LOGOUT)」 줄이 짧은 간격으로 번갈아 나오는지 본다(critic 권고 8).
8. `CLAUDE.md` 「Production」 절의 gunicorn 직접 실행 명령에는 `PYTHONUNBUFFERED` 가 없다. 그 명령으로 띄우면 버퍼링이 남는다. critic 권고 7 이며, 피어 제안만으로 `CLAUDE.md` 를 바꾸지 않는 규칙에 따라 사용자 판단으로 넘긴다.

---

### Task 1: LOGOUT 재로그인과 직렬화

**Files:**
- Modify: `vendor/pykrx/transport.patch` (재생성), `vendor/pykrx/pykrx-1.2.9+cookie.3-py3-none-any.whl` (새로 생성, `+cookie.2` 삭제), `vendor/pykrx/rebuild.py` (`VERSION`), `vendor/pykrx/README.md`, `requirements.txt`
- Modify: `restart_all.sh` (gunicorn 실행에 `PYTHONUNBUFFERED=1`)
- Test: `tests/test_pykrx_logout_relogin.py` (새 파일)

- [ ] **Step 1: 실패하는 테스트** — `pykrx` 패키지는 어느 하위 모듈을 import 해도 `webio` 가 import 시점 환경의 계정으로 로그인한다. 그래서 픽스처가 `KRX_ID`·`KRX_PW` 를 지운 뒤 `importlib.import_module` 로 늦게 import 하고, 그다음 더미 값을 넣는다(critic R1). `requests.Session.request` 를 스크립트된 가짜로, `auth.login_krx` 를 호출 수를 세는 가짜로 바꾸고 `KRX_ID`·`KRX_PW` 는 더미로 둔다. 각 테스트 전에 `auth._refresh_blocked_until = 0`.

```python
def test_logout_response_relogins_once_and_retries(...):
    # 첫 응답 400 LOGOUT → 로그인 1회 → 같은 요청 재전송 200. 요청 2회, 로그인 1회, 결과 200

def test_concurrent_logout_logs_in_once(...):
    # 로그인되지 않은 세션 객체면 400 LOGOUT, 가짜 로그인이 표시한 세션이면 200. 가짜 로그인은 0.2초 걸림
    # 4스레드 동시 요청 → 모두 200, 로그인 1회

def test_other_errors_do_not_relogin(...):
    # 400 INVALIDPERIOD, 302 빈 본문 → 로그인 0회, 요청 1회, 응답 그대로

def test_failed_relogin_blocks_retries_for_a_minute(...):
    # 가짜 로그인 실패. 첫 요청: 로그인 1회, 400 LOGOUT 반환. 바로 두 번째 요청: 로그인 여전히 1회
    # auth._refresh_blocked_until = 0 으로 만료를 흉내 내면 세 번째 요청에서 로그인 2회

def test_retry_still_logout_returns_without_loop(...):
    # 항상 400 LOGOUT, 로그인 성공 → 요청 2회, 로그인 1회, 400 LOGOUT 반환

def test_expired_timer_uses_same_guard(...):
    # auth._auth_session 을 만료된 세션으로 두고 가짜 로그인 실패 → get_auth_session() None, 로그인 1회
    # 바로 다시 get_auth_session() → None, 로그인 여전히 1회
```

- [ ] **Step 2: 실패 확인** — `venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pykrx_logout_relogin.py`. Expected: 설치된 `+cookie.2` 에서 LOGOUT·동시·실패 차단·재시도·타이머 테스트 5건이 동작 차이로 FAIL(`raising=False` 라 AttributeError 는 없음). `INVALIDPERIOD`·`302` 두 건은 종전 동작을 지키는 회귀 검사라 통과한다
- [ ] **Step 3: 구현** — 스크래치의 패치 적용 트리(`orig`)를 복사한 `new` 의 `auth.py` 에:

```python
import threading

_refresh_lock = threading.Lock()
_REFRESH_RETRY_SECONDS = 60
_refresh_blocked_until = 0.0


def _is_logout_response(response) -> bool:
    return response.status_code == 400 and response.content.strip() == b"LOGOUT"


def _refresh_session(krxs, seen_login_time: float, reason: str) -> bool:
    """재로그인을 직렬화한다. 다른 스레드가 이미 로그인했으면 로그인하지 않는다."""
    global _refresh_blocked_until
    with _refresh_lock:
        if krxs.login_time != seen_login_time:
            return krxs.is_authenticated
        if time.time() < _refresh_blocked_until:
            return False
        login_id, login_pw = os.getenv("KRX_ID"), os.getenv("KRX_PW")
        if not (login_id and login_pw):
            return False
        print(f"KRX 세션 {reason}, 재로그인 시도...", flush=True)
        if krxs.refresh(login_id, login_pw):
            print("KRX 세션 갱신 완료.", flush=True)
            return True
        _refresh_blocked_until = time.time() + _REFRESH_RETRY_SECONDS
        print(f"KRX 세션 갱신 실패: {krxs.last_error or 'login_rejected'}", flush=True)
        return False
```

`KRXSession._request` 의 KRX 갈래:

```python
        kwargs["allow_redirects"] = False
        seen_login_time = self.login_time
        response = self.session.request(method, url, headers=request_headers, **kwargs)
        if _is_logout_response(response) and _refresh_session(self, seen_login_time, "서버에서 끊김(LOGOUT)"):
            response = self.session.request(method, url, headers=request_headers, **kwargs)
        return response
```

`get_auth_session` 의 만료 갈래는 `is_valid()` 보다 먼저 `seen_login_time` 을 읽고(critic 권고 1) `if not _refresh_session(krxs, seen_login_time, "만료"): return None` 로 바꾸고 기존 print·자격 증명 분기는 `_refresh_session` 이 맡는다(자격 증명이 없으면 `False` → `None`, 종전과 같음). 이어 `diff -U0` 로 패치를 다시 만들고 `rebuild.py`(VERSION `1.2.9+cookie.3`)로 wheel 을 만든 뒤 `venv/bin/python -m pip install -r requirements.txt` 로 설치한다.

- [ ] **Step 4: 통과 확인** — 같은 명령 10 passed(권고 6 으로 자격 증명 없음·타이머 성공·세션 없음 갈래 차단 3건 추가). `tests/test_pykrx_login_guard.py tests/test_pykrx_transport_security.py` 통과
- [ ] **Step 5: 변이 검사** — (a) 잠금 안 `login_time` 비교 삭제 → 동시 테스트 FAIL (b) 차단 시각 검사 삭제 → 실패 차단 테스트 FAIL (c) 판별을 `status_code == 400` 만으로 → 다른 오류 테스트 FAIL. (d) 세션 없음 갈래의 차단 조건 삭제 → 세션 없음 테스트 FAIL. 각각 설치본에 직접 적용했다가 `pip install --force-reinstall --no-deps --find-links vendor/pykrx pykrx==1.2.9+cookie.3` 로 복원하고, 설치된 `auth.py` 가 빌드 트리와 같은지 `cmp` 로 확인한다(critic R2)
- [ ] **Step 6: pytest 전체** — `venv/bin/python -m pytest -q -p no:cacheprovider` exit 0

### QA (계획만, 실행은 dev-cycle [3])

로컬에서 실제 KRX 로 확인한다(로그인 2~3회, 과거 날짜 조회만, `data/` 쓰기 없음). (1) 정상 세션 기준 조회 (2) `KRXSession.session` 을 쿠키 없는 세션으로 바꿔 서버가 끊은 상태를 만든 뒤 `get_market_trading_value_by_date` 가 재로그인 1회로 6행을 받는지 (3) 같은 상태에서 4스레드 동시 조회가 로그인 1회로 모두 성공하는지 (4) 잘못된 기간 요청(`INVALIDPERIOD`)에는 재로그인하지 않는지. `restart_all.sh` 변경은 `bash -n` 과 로컬 격리 사본 기동 없이 문법·diff 확인으로 한다(운영 재기동은 장 마감 뒤 운영자).
