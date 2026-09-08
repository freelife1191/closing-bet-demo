# [INFRA-059] 무인증으로 남은 라우트 셋에 인가 게이트를 세운다

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /api/kr/refresh`·`POST /api/kr/market-gate/update`·`POST /api/kr/config/interval`
셋을 관리자 전용으로 닫고, 그 셋을 부르는 화면 세 자리의 노출 조건을 함께 고친다.

**Architecture:** `[INFRA-042]` 가 만든 `app/routes/route_guards.py` 의 `require_admin`
데코레이터와 `frontend/src/hooks/useAdmin` 훅을 그대로 쓴다. 새 추상을 만들지 않는다.
`/config/interval` 만 GET 을 열어 두어야 하므로 라우트를 GET 과 POST 두 함수로 나누고
POST 에만 데코레이터를 붙인다.

**Tech Stack:** Flask blueprint, pytest, Next.js App Router, vitest

**Spec:** 대화 설계다(bounded 경로). 승인 근거는 2026-09-08 세션에서 AskUserQuestion 네 번
(제품 결정 셋 + 설계 승인 하나)이며 그 내용은 아래 「승인된 결정」에 그대로 옮겨 적었다.

## 승인된 결정

| 질문 | 답 |
|---|---|
| `Refresh Data`·Market Gate 새로고침 버튼의 대상 | 관리자 전용 |
| 매크로 지표 주기 선택 | 관리자 전용. GET 은 열어 두어 값은 모두에게 보인다 |
| 익명 `GET /market-gate` 의 자동 트리거 | 이번에 손대지 않고 사실만 기록한다 |
| 구현 방식 | `/config/interval` 을 GET·POST 두 라우트로 나눈다 |

## Global Constraints

- **티어는 T3 이다.** 인가 경계에 닿는다. 리뷰는 `/ponytail-review` → `feature-dev:code-reviewer`
  → `/review` 순서를 지키고, 인증에 닿으므로 `oh-my-claudecode:security-reviewer` 를 더한다.
- **커밋은 dev-cycle `[3]` 5번을 따른다.** Task 마다 커밋하지 않는다. 정적 검증을 통과한
  구현과 QA 시나리오 문서를 첫 커밋 하나로 남기고 TODO 항목은 유지한다.
- **기록에 「익명이 Market Gate 분석을 못 돌린다」고 쓰지 않는다.** `GET /api/kr/market-gate` 가
  데이터가 낡았을 때 `_trigger_market_gate_background_refresh()` 로 같은 `MarketGate().analyze()`
  를 익명에게도 돌린다(`kr_market_system_http_routes.py:84`). 이번에 막는 것은 POST 쪽의
  **즉시·동기·날짜 지정·`force=True` 수급 재수집** 갈래뿐이다.
- **`/config/interval` 이 `.env` 를 쓴다고 쓰지 않는다.** `project_env_path(__file__)` 이
  `app/.env` 를 가리키는데 그 파일이 없어 `persist_market_gate_interval_to_env` 가 첫 줄에서
  반환한다(실측 확인). 지금 바뀌는 것은 **요청을 처리한 워커의 `app_config` 값**과, 그 워커가
  스케줄러 잠금을 쥐고 있을 때의 `schedule` 등록뿐이다. 이 사실은 `[INFRA-056]` 의 전제이기도
  하다.
- 데코레이터 순서는 `@route` 가 바깥, `@require_admin` 이 안쪽이다.
- 운영 `.env` 파일에 쓰지 않는다. 값을 출력하지 않는다.

---

### Task 1: `/refresh` 와 `/market-gate/update` 에 게이트를 세운다

**Files:**
- Modify: `app/routes/kr_market_system_http_routes.py:105`, `:172`
- Test: `tests/app/test_admin_gated_routes.py`

`require_admin` 은 이 파일에 이미 import 되어 있다(`:17`). 새 import 는 필요 없다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/app/test_admin_gated_routes.py` 에 기존 `_build_app` 관례를 그대로 써서 넷을 더한다.
거부만 재면 게이트가 전부를 막아도 통과하므로 통과 쪽도 함께 잰다.

```python
def test_refresh_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_system_http_routes import _register_refresh_route

    def register(bp):
        _register_refresh_route(bp, logger=_LOGGER, deps={"launch_background_update_job": _must_not_run})

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/refresh", json={})
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_market_gate_update_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_system_http_routes import _register_market_gate_routes

    def register(bp):
        _register_market_gate_routes(bp, logger=_LOGGER, deps=_market_gate_deps(update=_must_not_run))

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/market-gate/update", json={})
    assert res.status_code == 403
```

`_register_market_gate_routes` 는 `kr_market_system_http_routes.py:53` 이고 `deps` 키 열여섯
개는 `app/routes/kr_market_dependency_builders.py:119-150` 에 있다. **키를 다시 적지 말고**
`tests/app/test_kr_market_system_http_routes_refactor.py` 의 `_build_base_deps(**overrides)`
를 import 해서 쓴다.

`GET /market-gate` 도 같은 등록 함수에 들어 있으므로 **그 GET 이 익명에게 계속 열려 있는지
재는 검사를 함께 넣는다.** 이번 결정이 「GET 은 그대로 둔다」이므로 그 결정을 코드가 지키는지
재는 자리가 된다. `test_kr_market_system_http_routes_refactor.py:80-94` 가 이미 익명으로 그
GET 을 쳐서 200 을 확인하지만, 그쪽은 initializing payload 를 재는 검사라 목적이 다르다.

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_admin_gated_routes.py -v`
Expected: 새 검사가 **`assert 500 == 403`** 으로 FAIL

403 이 아니라 500 인 것이 맞다. `app/routes/route_execution.py:26-30` 의 `execute_json_route`
가 `except Exception` 으로 잡는데 `AssertionError` 가 그 하위라, 게이트가 없는 동안에는
`_must_not_run` 이 던지는 것을 그 자리가 삼켜 `error_response_builder` 로 500 을 낸다. 어느
쪽이든 FAIL 이지만 기대값이 틀리면 「다른 것이 깨졌나」를 되짚느라 시간을 쓴다.

- [ ] **Step 3: 데코레이터를 붙인다**

```python
    @kr_bp.route('/market-gate/update', methods=['POST'])
    @require_admin
    def update_kr_market_gate():
```

```python
    @kr_bp.route('/refresh', methods=['POST'])
    @require_admin
    def refresh_kr_data():
```

- [ ] **Step 4: 게이트에 막히게 된 기존 검사 하나를 고친다**

`tests/app/test_kr_market_system_http_routes_refactor.py:112` 의
`test_refresh_route_uses_common_update_handlers_and_adds_success_message` 가 `:131` 에서
`_create_client(deps)` 를 부른다. 그 헬퍼(`:22-37`)의 `before_request` 가 `g.user_email` 에
기본값 `None` 을 심으므로 게이트가 403 을 내고 `:135` 의 `assert response.status_code == 200`
이 실패한다.

```python
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client(deps, user_email="admin@example.com")
```

그 검사는 이미 `monkeypatch` 를 인자로 받으므로 시그니처는 그대로 둔다. 같은 파일의 나머지는
GET 이거나 게이트 밖 라우트라 깨지지 않는다.

`/market-gate/update` 쪽은 POST 를 실제로 치는 파이썬 검사가 저장소에 없다.
`tests/verify_route.py:17` 은 `url_map` 만 훑어 데코레이터와 무관하고 pytest 가 수집하지도
않으며, `frontend/src/lib/api.test.ts` 는 `fetch` 를 목한다. 그래서 Task 1 Step 1 이 만드는
검사가 그 라우트의 유일한 게이트 증거가 된다.

- [ ] **Step 5: 통과를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_admin_gated_routes.py tests/app/test_kr_market_system_http_routes_refactor.py -v`
Expected: PASS

---

### Task 2: `/config/interval` 을 GET 과 POST 로 나눈다

**Files:**
- Modify: `app/routes/kr_market.py:155-171`
- Modify: `tests/app/test_kr_market_route_integration.py:478`, `:498`
- Test: `tests/app/test_admin_gated_routes.py`

**Interfaces:**
- Consumes: `services/kr_market_interval_http_service.handle_interval_config_request`
  (`method`, `req_data`, `current_interval`, `apply_interval_fn`, `persist_interval_fn`).
  **서비스는 고치지 않는다.** `method` 인자를 각 라우트에서 고정해 넘긴다.

- [ ] **Step 1: 실패하는 검사를 쓴다**

```python
def test_interval_post_refuses_anonymous(monkeypatch):
    """GET 은 열려 있고 POST 만 막힌다."""
```

`kr_market.py` 는 모듈 수준에서 블루프린트에 라우트를 등록하므로 `_build_app` 의 등록 함수
패턴을 쓸 수 없다. `tests/app/test_kr_market_route_integration.py` 의 `_create_client()` 와
`_create_client_with_user(user_email=...)` 를 쓰는 쪽이 기존 관례에 맞는다. 그 파일에 넣는다.

```python
def test_config_interval_post_refuses_anonymous(monkeypatch):
    # RED 를 도는 동안에는 게이트가 없어 요청이 실제로 뷰를 통과한다. 두 함수를 목하지
    # 않으면 app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES 가 15 로 바뀌고
    # services.scheduler.update_market_gate_interval 이 불려, 같은 프로세스의 다른
    # 검사로 그 값이 새어 들어간다. GREEN 이 되면 닿지 않지만 RED 구간이 남는다.
    monkeypatch.setattr(kr_market, "_apply_market_gate_interval", lambda _interval: None)
    monkeypatch.setattr(kr_market, "_persist_market_gate_interval_to_env", lambda _interval: None)

    client = _create_client()
    response = client.post("/api/kr/config/interval", json={"interval": 15})
    assert response.status_code == 403


def test_config_interval_get_stays_open_for_anonymous():
    client = _create_client()
    response = client.get("/api/kr/config/interval")
    assert response.status_code == 200
    assert "interval" in response.get_json()
```

GET 쪽은 목이 필요 없다. `handle_interval_config_request` 가 GET 에서 두 함수를 부르지 않고
바로 반환한다(`services/kr_market_interval_http_service.py:21-22`).

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_route_integration.py -k interval -v`
Expected: `test_config_interval_post_refuses_anonymous` 가 `assert 200 == 403` 으로 FAIL

- [ ] **Step 3: 라우트를 나눈다**

몸통을 두 벌 복사하지 않는다. 기존 뷰의 25 줄에서 실제로 갈리는 것은 `method` 와 `req_data`
두 인자뿐이므로 지역 헬퍼로 뺀다. 라우트를 나누는 것은 승인된 결정이므로 그대로 두되, 중복은
남기지 않는다.

```python
def _interval_config_response(method: str, req_data: dict):
    from engine.config import app_config
    try:
        status_code, payload = handle_interval_config_request_service(
            method=method,
            req_data=req_data,
            current_interval=app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES,
            apply_interval_fn=_apply_market_gate_interval,
            persist_interval_fn=_persist_market_gate_interval_to_env,
        )
        return jsonify(payload), int(status_code)
    except Exception as e:
        logger.error(f"Interval Config Error: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/config/interval', methods=['GET'])
def get_interval_config():
    """Market Gate 업데이트 주기 조회. 화면이 현재 값을 보여 주므로 열어 둔다."""
    return _interval_config_response("GET", {})


# GET 과 한 뷰에 두지 않는 이유가 있다. require_admin 은 메서드를 가리지 않으므로 한 뷰에
# 붙이면 조회까지 막히고, 화면이 현재 주기를 보여 주지 못한다. 나누면 어느 메서드가 열려
# 있는지가 라우트 선언에서 바로 보이고, tests/app/test_admin_gated_routes.py 의 목록
# 불변식이 POST 라우트만 훑으므로 이 자리가 그 목록에 자동으로 걸린다.
@kr_bp.route('/config/interval', methods=['POST'])
@require_admin
def set_interval_config():
    """Market Gate 업데이트 주기 설정. 서버 전역 스케줄러 주기라 관리자만 바꾼다."""
    return _interval_config_response("POST", request.get_json(silent=True) or {})
```

GET 에 `apply_interval_fn` 과 `persist_interval_fn` 을 그대로 넘겨도 무해하다.
`services/kr_market_interval_http_service.py:21-22` 가 GET 에서 두 함수를 아예 부르지 않고
바로 반환한다.

`app/routes/route_guards` 의 `require_admin` 을 `kr_market.py` 에 import 한다. 이 파일에는
아직 없다.

- [ ] **Step 4: 게이트에 막히게 된 기존 검사 둘을 고친다**

`test_config_interval_post_parses_string_and_applies_update`(`:478`)와
`test_config_interval_post_rejects_invalid_value`(`:498`)가 `_create_client()` 를 쓴다.
`_create_client_with_user(user_email="admin@example.com")` 로 바꾸고
`monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")` 을 더한다.

**뒤엣것은 시그니처도 함께 고친다.** `def test_config_interval_post_rejects_invalid_value():`
는 인자가 없어서 `monkeypatch` 를 그대로 쓸 수 없다. `(monkeypatch)` 를 받도록 고친다.
앞엣것은 이미 `monkeypatch` 를 받으므로 시그니처를 건드리지 않는다.

`_create_client_with_user`(`:82-95`)는 `_register_request_context` 를 부르지 않고
`before_request` 에서 `g.user_email` 을 직접 심는다. 게이트 판정에는 그것으로 충분하므로
그 형태를 그대로 쓴다.

- [ ] **Step 5: 규칙 수 검사가 그대로 통과하는지 확인한다**

`test_routes_do_not_overlap_for_interval_and_chatbot_history`(`:459`)는 메서드별로 세므로
라우트를 나눠도 GET·POST 각각 1을 유지한다. 이 검사는 고치지 않는다. 값이 2가 되면 등록이
잘못된 것이므로 그때 원인을 찾는다.

Run: `source venv/bin/activate && pytest tests/app/test_kr_market_route_integration.py -v`
Expected: PASS

---

### Task 3: 게이트 목록 불변식을 갱신한다

**Files:**
- Modify: `tests/app/test_admin_gated_routes.py:315` (`GATED_ROUTES`)

`_decorated_paths` 가 `is_admin_email` 을 참조하는 POST 라우트를 모으므로, Task 1·2 를
마치면 이 검사가 **먼저 실패한다**(`게이트가 붙었는데 목록에 없다`). 그 실패가 목록
불변식이 살아 있다는 증거다.

- [ ] **Step 1: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_admin_gated_routes.py::test_gated_route_list_matches_reality -v`
Expected: FAIL, 메시지에 세 경로가 나온다

- [ ] **Step 2: 목록에 셋을 더한다**

```python
        "/api/kr/refresh",
        "/api/kr/market-gate/update",
        "/api/kr/config/interval",
```

`/api/kr/config/interval` 은 GET 라우트도 같은 rule 을 쓰지만 `_decorated_paths` 가
`"POST" in rule.methods` 로 거르므로 POST 라우트만 걸린다.

- [ ] **Step 3: 통과를 확인한다**

Run: `source venv/bin/activate && pytest tests/app/test_admin_gated_routes.py -v`
Expected: PASS

---

### Task 4: 화면 세 자리의 노출 조건을 고친다

**Files:**
- Modify: `frontend/src/app/dashboard/kr/page.tsx` (`:196` 근처, `:657-710`, `:750`, `:977`)

**읽을 문서와 스킬을 먼저 정한다.** CLAUDE.md 와 `references/frontend-skills.md` §2 가
`frontend/src/app` 아래를 하나라도 고치면 해당 주제의 번들 문서를 예외 없이 읽으라고 규정하며,
그 매핑 문서는 「보고에 문서 이름이 없으면 건너뛴 것」이라고까지 적어 두었다.

- 번들 문서: `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`.
  이번 변경이 클라이언트 컴포넌트에 `useEffect` 기반 훅(`useAdmin`)을 하나 더하는 것이기 때문이다.
- 스킬: 새 화면이나 새 상호작용을 만들지 않고 기존 요소의 노출 조건만 바꾸므로 디자인 계열
  스킬은 고르지 않는다. `references/frontend-skills.md` §2 표에서 이번 파일에 해당하는 것을
  구현 직전에 다시 대조하고, 고른 이름을 라운드 보고에 적는다.

`[INFRA-042]` 가 남긴 교훈을 그대로 적용한다. 게이트를 세우고 화면을 그대로 두면 비관리자에게
버튼이 보이고, 눌러도 `catch` 가 `console.error` 뿐이라 **화면에 아무 반응이 없다.**

- [ ] **Step 1: `useAdmin` 을 들여온다**

```tsx
import { useAdmin } from '@/hooks/useAdmin';
```

```tsx
const { isAdmin, isLoading: isAdminLoading } = useAdmin();
```

형제 화면인 `frontend/src/app/dashboard/kr/vcp/page.tsx:12`·`:230` 과 형태를 맞춘다.

- [ ] **Step 2: `Refresh Data` 버튼(`:977`)을 감싼다**

```tsx
{!isAdminLoading && isAdmin && (
  <button onClick={refreshData} ...>
```

이 버튼은 `:841` 의 `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4` 네 번째 칸이다. 감추면
비관리자 화면이 세 칸이 된다. **Step 5 에서 실측한다.**

- [ ] **Step 3: Market Gate 새로고침 아이콘(`:750`)을 감싼다**

같은 조건을 쓴다. 이 버튼은 `<h3>` 안의 인라인 요소라 감춰도 배치가 흔들리지 않는다.

- [ ] **Step 4: 주기 선택(`:657-700`)을 관리자에게만 보인다**

`select` 와 `number` 입력을 감추고, 비관리자에게는 현재 값을 텍스트로 보인다. GET 이 열려
있으므로 `:196` 의 조회는 그대로 두어 값이 온다.

```tsx
{!isAdminLoading && isAdmin ? (
  /* 기존 select / number input */
) : (
  <span className="text-[10px] font-bold text-gray-400 ml-0.5">{updateInterval}분</span>
)}
```

`updateInterval` 로 도는 로컬 `setInterval`(`:220`)은 건드리지 않는다. 비관리자도 화면 자동
갱신은 그대로 받는다.

**`select` 만 감싸면 화살표가 남는다.** `:708-710` 에 별도의 조건부 요소가 있다.

```tsx
{[1, 5, 10, 15, 30, 60].includes(updateInterval) && (
  <i className="fas fa-chevron-down ... opacity-0 group-hover:opacity-100"></i>
)}
```

그 `group` 은 `:654` 의 부모 `div` 이므로, 비관리자가 「매크로 지표: 30분 마다 자동 갱신」
줄에 마우스를 올리면 **없는 드롭다운의 화살표가 나타난다.** `updateInterval` 이 기본 목록
안의 값일 때 걸리며 그것이 대부분의 경우다. 이 조건에도 `isAdmin` 을 함께 건다.

- [ ] **Step 5: 주기 변경 실패를 화면에 되돌린다**

`:204-217` 의 `handleIntervalChange` 는 낙관적 갱신이다. `setUpdateInterval(minutes)` 를 먼저
하고 POST 가 실패하면 `console.error` 만 찍는다. 코드 주석 자체가 「실패 시 롤백 로직이
필요할 수 있음」이라고 적어 두었고, 이번 게이트가 **403 이라는 새 실패 경로를 만든다.**
관리자 세션이 페이지를 연 채 만료되면 화면의 주기 값과 서버 값이 조용히 갈린다.

```tsx
const handleIntervalChange = async (minutes: number) => {
  const previous = updateInterval;
  try {
    setUpdateInterval(minutes);
    const res = await fetch('/api/kr/config/interval', { ... });
    if (!res.ok) throw new Error('Failed to update interval');
  } catch (error) {
    console.error('Error changing interval:', error);
    setUpdateInterval(previous);
  }
};
```

**세 핸들러 모두 403 을 처리한다.** 적대적 리뷰(F1)가 이 자리의 초안 판단을 무너뜨렸다.
초안은 「비관리자가 이 핸들러에 닿는 정상 경로가 없고, 세션이 만료되면 `useAdmin` 이 곧
버튼을 거둔다」를 근거로 `data-status` 의 권한 모달을 따르지 않기로 했는데 둘 다 코드와
어긋난다.

- `frontend/src/app/components/Providers.tsx` 의 `SessionProvider` 에 `refetchInterval` 이
  없어 폴링하지 않는다. `useAdmin` 의 의존성은 `[session, status]` 뿐이므로 그 둘이 바뀌지
  않으면 `/api/admin/check` 를 **다시 부르지 않는다.** 포커스가 유지되는 탭은 영원히
  재판정하지 않는다.
- NextAuth 세션 기본값이 30일이라 「세션 만료」는 가장 드문 경로다. 실제로 일어나는 것은
  **`ADMIN_EMAILS` 에서 관리자를 빼는 것**이고, `CLAUDE.md` 는 그 경로를 「재기동 없이 즉시
  듣습니다」라고 적어 두었다. 서버는 즉시 듣지만 **열려 있는 탭은 듣지 않는다.**
- 그 상태에서 `refreshData` 를 누르면 403 인데 `setLoading(true)` → `loadData()` → 스피너
  종료로 **성공한 갱신과 구분되지 않는다.** `refreshMarketGate` 도 아이콘만 잠깐 돈다.

그래서 셋 다 403 에서 `reportPermissionDenied` 를 부른다. 그 함수는 모달을 띄우고
`permissionRevoked` 를 세워 **세 자리를 함께 거둔다.** 알림만 띄우고 버튼을 남기면 같은
사용자가 계속 눌러 같은 403 을 반복해서 받는다. `useAdmin` 자체는 고치지 않는다. 그 훅은
다른 화면 여섯이 함께 쓰고, 여기서 필요한 것은 「이 탭의 판정이 낡았다」 하나뿐이다.

- [ ] **Step 6: agent-browser 로 비관리자 화면을 실측한다**

`references/browser-notes.md` 를 먼저 읽는다. 로그인하지 않은 상태로 `/dashboard/kr` 를 열어
세 자리가 사라졌는지, 네 칸 그리드가 세 칸이 되었을 때 배치가 깨지지 않는지 본다. 깨지면
그 칸의 `lg:grid-cols-4` 를 관리자 여부에 따라 바꾸는 대신 **남는 칸을 그대로 둔다**. 그리드
클래스를 조건부로 바꾸면 Tailwind 가 정적 추출을 못 해 클래스가 빠질 수 있다.

**비용이 드는 버튼을 누르지 않는다.** 새로고침·재분석·발송 어느 것도 누르지 않는다.

---

### Task 5: 화면 결정을 검사로 고정한다

**Files:**
- Create: `frontend/src/app/dashboard/kr/page.regression-infra-059.test.tsx`
- Modify: `frontend/src/app/dashboard/kr/page.regression-flow-004.test.tsx`

**이 Task 가 이번 라운드에서 가장 중요하다.** Task 4 의 노출 조건을 재는 검사가 없으면
다음 사람이 `{!isAdminLoading && isAdmin && ...}` 를 지워도 프론트 검사가 전부 초록으로
남는다. `[INFRA-042]` 에서 실제로 일어난 일이 그것이고, 그때는 리뷰가 잡아 주었다.

- [ ] **Step 1: 기존 검사에 `useAdmin` mock 을 더한다**

`page.regression-flow-004.test.tsx` 는 `@/lib/api` 만 목하고 `next-auth/react` 는 목하지
않는다. `useAdmin` 이 `useSession` 을 부르므로 SessionProvider 없이 터진다. 이 검사가 재는
것은 `i.fa-check-circle` 개수뿐이라 어느 쪽으로 목해도 결과가 같다.

```tsx
vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: false, isLoading: false }),
}));
```

Run: `cd frontend && npx vitest run src/app/dashboard/kr/page.regression-flow-004.test.tsx`
Expected: PASS

- [ ] **Step 2: 노출 조건을 재는 검사를 새로 쓴다**

항목별로 파일을 나누는 저장소 관례(`page.regression-jongga-015.test.tsx` 등)를 따른다.
`flow-004` 파일에 섞지 않는다. 목 구성은 `flow-004` 의 것을 그대로 가져다 쓴다.

```tsx
// Regression: [INFRA-059] 세 자리를 관리자에게만 보인다
//
// 서버는 require_admin 으로 세 라우트를 닫았다. 화면이 그 조건을 함께 지키지 않으면
// 비관리자에게 버튼이 보이고 눌러도 403 만 돌아오는데, 두 핸들러의 catch 가
// console.error 뿐이라 화면에는 아무 반응도 없다.

describe('[INFRA-059] 관리자 전용 조작의 노출', () => {
  it('비관리자에게는 세 자리가 보이지 않는다', async () => {
    // useAdmin: () => ({ isAdmin: false, isLoading: false })
    expect(screen.queryByText('Refresh Data')).toBeNull();
    expect(screen.queryByTitle('Refresh Market Gate Only')).toBeNull();
    expect(container.querySelector('select')).toBeNull();
  });

  it('관리자에게는 세 자리가 보인다', async () => {
    // useAdmin: () => ({ isAdmin: true, isLoading: false })
    expect(screen.getByText('Refresh Data')).toBeTruthy();
    expect(screen.getByTitle('Refresh Market Gate Only')).toBeTruthy();
    expect(container.querySelector('select')).toBeTruthy();
  });
});
```

**두 갈래를 모두 잰다.** 감추는 쪽만 재면 게이트가 관리자에게까지 전부를 감춰도 통과한다.
`tests/app/test_admin_gated_routes.py:77` 이 백엔드에서 같은 이유로 통과 갈래를 함께 재고
있으므로 관례에도 맞는다.

`vi.mock` 은 파일 단위로 끌어올려지므로 한 파일에서 `isAdmin` 을 두 값으로 쓰려면 목 팩터리가
변수를 읽게 만들거나 파일을 둘로 나눈다. `data-status/page.test.tsx` 가 어느 쪽을 쓰는지 보고
같은 형태를 고른다.

`select` 로 고르는 것은 이 화면에 주기 선택 외에 `select` 요소가 없다는 사실에 기댄다.
구현 시점에 다른 `select` 가 있으면 `title` 이나 접근성 이름으로 바꾼다.

- [ ] **Step 3: 통과를 확인한다**

Run: `cd frontend && npx vitest run`
Expected: PASS

---

### Task 6: 정적 검증과 첫 커밋

**Files:**
- Modify: `CLAUDE.md` (「Important Notes」)
- Create: `docs/dev-cycle/qa/INFRA-059.md`

- [ ] **Step 1: 셋을 모두 돌린다**

```bash
source venv/bin/activate && pytest
cd frontend && npx vitest run
cd frontend && npm run type-check
```

**종료 코드를 파이프라인 뒤 `${PIPESTATUS[0]}` 로 읽지 않는다.** zsh 에서 그 변수는 비어
있고, 마지막이 `echo` 면 전체 종료 코드가 언제나 0 이라 실패를 못 본다. 리다이렉트로 받아
`echo "exit=$?"` 를 별도 줄에 둔다.

- [ ] **Step 2: 익명 GET 트리거를 지속되는 문서에 적는다**

승인된 결정은 「사실만 기록하고 남긴다」이므로 **새 TODO 항목을 세우지 않는다.** 다만 그
사실이 이 계획 파일에만 있으면 안 된다. 계획 파일은 항목이 끝나면 더 이상 읽히지 않는다.

`CLAUDE.md` 의 「Important Notes」에 한 줄로 적는다. 그 절은 데이터 소스 이중 체인과 스케줄러
잡처럼 **구조적 사실을 적어 두는 자리**이고, `[INFRA-042]` 도 관리자 토큰 절을 그렇게 보강했다.
적을 내용은 「`GET /api/kr/market-gate` 는 데이터가 낡으면 익명 요청에도 백그라운드 분석을
트리거한다. `POST /market-gate/update` 에 인가 게이트가 있다고 해서 익명이 Market Gate 분석을
돌릴 수 없다는 뜻이 아니다」이다.

- [ ] **Step 3: QA 시나리오 문서를 쓴다**

`docs/dev-cycle/qa/INFRA-059.md`. 형식은 `archive-format.md` §8.

**판정 기준을 문서 첫머리에 미리 적는다.** QA 도중 대시보드를 열거나 `GET /api/kr/market-gate`
를 한 번 치기만 해도, 데이터가 낡았으면 `kr_market_system_http_routes.py:84` 가 백그라운드
분석을 돌려 **Market Gate 상태가 실제로 바뀐다.** 그것을 「POST 게이트가 뚫렸다」로 읽으면
안 된다. 이번에 재는 것은 POST 갈래뿐이며 GET 트리거로 상태가 바뀌는 것은 예상된 결과다.

`isRunning` 쪽은 그런 혼동이 없다. `GET /market-gate` 의 트리거는 `_market_gate_lock` 과
`.market_gate_refresh.lock` 만 쓰고 공통 `update_status` 파일을 건드리지 않는다.

- [ ] **Step 4: 첫 커밋**

허용 경로만 스테이징한 뒤 `git diff --cached --name-only | wc -l` 로 **줄 수를 함께 센다.**
`git add` 는 목록에 없는 경로가 섞이면 아무것도 스테이징하지 않으면서 종료 코드 0 을 내고,
이어지는 `git diff --cached --check` 도 빈 인덱스를 보고 0 을 낸다. 두 신호가 모두 통과로
보인다.

TODO 항목은 유지한다. 최종 QA 통과 후 아카이브 커밋에서만 지운다.

## Self-Review

- **승인 범위 대조**: 제품 결정 셋과 구현 방식 하나가 모두 Task 에 반영되었다. `GET /market-gate`
  자동 트리거는 Task 어디에도 고치는 단계가 없고, Task 1 Step 1 이 그 GET 이 계속 열려 있는지
  재는 검사로 결정을 고정하며, Task 6 Step 2 가 사실을 `CLAUDE.md` 에 남긴다.
- **누락 확인**: TODO 체크 넷 가운데 「호출 그래프를 핸들러와 상태 파일 기준으로 훑는다」는
  설계 단계에서 이미 수행했고 그 결과가 Global Constraints 두 항목(GET 트리거, `app/.env`)이다.
  「오류 처리」는 Task 4 Step 5 가 맡는다.
- **타입 일관성**: `handle_interval_config_request` 의 인자 이름을 Task 2 에서 그대로 쓴다.
  서비스 시그니처를 바꾸지 않으므로 어긋날 자리가 없다.

## 계획 검토 반영 기록

`oh-my-claudecode:critic`(`infra059-critic`)이 지적 아홉을 냈고 전부 코드로 확인한 뒤
반영했다. 회신이 두 번 잘려 세 번에 나누어 받았다.

| 지적 | 반영 |
|---|---|
| 1. `test_kr_market_system_http_routes_refactor.py:112` 이 깨진다 | Task 1 Step 4 신설 |
| 2. 화면 노출 조건을 재는 검사가 없다 | Task 5 를 다시 씀. 새 회귀 검사 파일에서 두 갈래를 잰다 |
| 3. TODO 체크의 「오류 처리」가 빠졌다 | Task 4 Step 5 신설. 권한 모달을 따르지 않는 판단과 근거를 함께 적음 |
| 4. 주기 선택을 감춰도 화살표가 남는다 | Task 4 Step 4 에 `:708-710` 조건 추가 |
| 5. RED 기대값이 403 이 아니라 500 이다 | Task 1 Step 2 정정 |
| 6. `test_config_interval_post_rejects_invalid_value` 의 시그니처 | Task 2 Step 4 에 명시. 줄 번호 `:498`·`:459` 로 정정 |
| 7. GET 트리거 기록 위치와 QA 오판 위험 | Task 6 Step 2·3 신설 |
| 8. 프론트엔드 스킬과 번들 문서 미지정 | Task 4 머리에 번들 문서 경로와 스킬 판단 명시 |
| 9. Task 2 Step 3 의 25 줄 중복, `_build_base_deps` 재사용, import 참조 | 지역 헬퍼로 바꾸고 Task 1 Step 1 과 Task 4 Step 1 을 고침 |
| 10. RED 구간의 전역 오염 | Task 2 Step 1 의 새 검사에 두 함수 목을 추가 |

판정은 `REVISE` 다. 열 가지 모두 반영했고 미반영은 없다.
