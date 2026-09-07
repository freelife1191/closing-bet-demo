# [INFRA-040] 교차 출처 비안전 요청 차단 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 쿠키에서 신원이 확정된 비안전 요청이 같은 오리진에서 왔는지를 `proxy.ts` 가
직접 확인하게 하여, 지금은 next-auth 의 `sameSite: 'lax'` 기본값에만 기대고 있는 CSRF
방어를 이 저장소의 코드로 옮긴다.

**Architecture:** `frontend/src/proxy.ts` 의 `if (email)` 블록 안, 서명을 붙이기 직전에
검사 하나를 넣는다. 검사를 그 블록 안에 두는 것이 설계의 핵심이다. 쿠키로 신원이 확정된
요청만 CSRF 의 대상이므로, 세션이 없는 curl·서버 간 호출·익명 브라우저는 검사에 닿지
않는다. 통과 조건은 `Sec-Fetch-Site: same-origin` 하나이며 헤더가 없으면 차단된다.

**Tech Stack:** Next.js 16.3.4 (`proxy.ts` 규약), next-auth v4, vitest

**Spec:** 대화 설계다. 2026-09-07 세션에서 세 가지 선택지를 제시해 승인받았다.
① 교차 출처 비안전 요청은 403 으로 즉시 거부한다. ② 신원이 확정된 요청에서만 검사하고
그때는 헤더 부재도 차단한다. ③ `proxy.ts` 와 `services/identity_helpers.py` 를 위험 경로
목록에 넣고 이번 항목을 T3 으로 올린다.

## Global Constraints

- 티어는 T3 이다. 리뷰는 `/ponytail-review` → `oh-my-claudecode:critic`(계획) →
  `feature-dev:code-reviewer` → `/review` → `oh-my-claudecode:security-reviewer` 순서다.
- 검증은 `pytest` 전체, `cd frontend && npx vitest run`, `cd frontend && npm run type-check`
  세 가지를 모두 돌린다.
- 인증 경로이므로 `tier-rules.md` §1 의 시크릿 확인 세 가지를 더한다. `.env` 추적 여부,
  키의 로그·응답 노출, `NEXT_PUBLIC_` 번들 노출이다.
- `.env` 값을 출력하지 않는다. 키 이름과 값의 유무까지만 다룬다.
- 비용이 들거나 되돌릴 수 없는 조작을 하지 않는다. 알림 테스트 발송, 재분석, 모의투자
  주문, Market Gate 갱신을 실행하지 않는다.
- 루트의 추적되지 않는 `package.json` 은 그대로 둔다. 다른 작업의 파일을 스테이징하지
  않는다.

---

### Task 1: `proxy.ts` 에 교차 출처 차단을 넣는다

**Files:**
- Modify: `frontend/src/proxy.ts:22-42`
- Test: `frontend/src/proxy.test.ts`

**Interfaces:**
- Consumes: `NextRequest.method`, `NextRequest.headers`, `getToken` 의 결과
- Produces: 없다. `proxy()` 의 시그니처는 그대로이며 반환 형식만 403 응답이 하나 는다.

- [ ] **Step 1: 실패하는 검사를 먼저 쓴다**

`requestWith` 가 메서드를 받지 못하므로 함께 고친다. 기존 호출 일곱 자리를 깨지 않도록
두 번째 인자를 선택적으로 둔다.

```ts
function requestWith(headers: Record<string, string>, method = 'GET') {
  return { headers: new Headers(headers), method } as never;
}
```

검사 네 개를 더한다.

```ts
describe('proxy 의 교차 출처 차단', () => {
  it('로그인한 사용자의 교차 출처 POST 를 403 으로 끊는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(403);
  });

  it('Sec-Fetch-Site 가 없는 비안전 요청도 끊는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({}, 'DELETE'));

    expect(res.status).toBe(403);
  });

  it('같은 오리진의 POST 에는 서명을 붙인다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'same-origin' }, 'POST'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeTruthy();
  });

  it('교차 출처라도 GET 은 막지 않는다', async () => {
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'GET'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeTruthy();
  });

  it('세션이 없으면 교차 출처 POST 도 막지 않고 익명으로 넘긴다', async () => {
    mockGetToken.mockImplementation(async () => null);

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(200);
    expect(forwardedHeaders(res).get('x-auth-identity')).toBeNull();
  });

  it('비밀이 없으면 교차 출처 POST 도 막지 않는다', async () => {
    vi.stubEnv('INTERNAL_IDENTITY_SECRET', '');
    mockGetToken.mockImplementation(async () => ({ email: 'owner@example.com' }));

    const res = await proxy(requestWith({ 'Sec-Fetch-Site': 'cross-site' }, 'POST'));

    expect(res.status).toBe(200);
  });
});
```

마지막 두 검사가 설계의 핵심을 고정한다. 검사가 `if (email)` 밖으로 나가면 첫째가 깨지고,
`if (secret)` 밖으로 나가면 둘째가 깨진다. 비밀이 없는 배포에서는 모든 요청이 이미
익명이므로 CSRF 의 대상이 아니고, 그때 차단이 켜지면 아무도 쓰기를 하지 못한다.

- [ ] **Step 2: 검사가 실패하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/proxy.test.ts`
Expected: 새 검사 다섯 개 가운데 403 을 기대하는 둘이 FAIL. 나머지 셋은 지금도 PASS
한다(현재 코드가 아무것도 막지 않으므로). 기존 일곱 개는 계속 PASS 여야 한다.

- [ ] **Step 3: `proxy.ts` 를 고친다**

```ts
// 브라우저가 붙이는 금지 헤더라 스크립트가 덮어쓸 수 없다. same-origin 이 아니면 다른
// 사이트의 페이지가 이 요청을 일으켰다는 뜻이고, 헤더가 아예 없어도 막는다.
//
// 검사를 이 블록 안에 두는 근거는 「신원이 없으면 어차피 익명이라」가 아니다. 익명
// 신원인 X-Session-Id 는 브라우저가 자동으로 붙이는 값(ambient credential)이 아니라
// localStorage 에서 읽어 JS 가 붙이는 값이라(`frontend/src/lib/session.ts:7`) 교차 출처
// 페이지가 피해자의 값을 실을 수 없다. 누군가 그 값을 쿠키로 옮기면 이 전제가 깨지므로
// 그때는 검사를 블록 밖으로 내야 한다.
//
// 지금 이 경로가 뚫려 있지 않은 이유는 우리 코드가 아니라 next-auth 의 기본값이다.
// 세션 쿠키가 sameSite: 'lax' 라(next-auth/core/lib/cookie.js:24) 교차 출처 POST 에
// 쿠키가 실리지 않는다. 그 기본값을 누가 바꾸면 조용히 무너지므로 여기서 직접 본다.
//
// 사파리는 16.4(2023-03)부터 이 헤더를 보낸다. iOS 16.3 이하와 그 계열 인앱 웹뷰에서는
// 로그인한 사용자의 모든 POST·DELETE 가 여기서 막힌다. Origin 을 예비로 대조하면 그
// 브라우저도 살릴 수 있으나, 검사를 한 줄로 두는 쪽을 택했다. 문의가 들어오면 그때
// Origin 대조를 더한다.
if (UNSAFE_METHODS.has(request.method) &&
    request.headers.get('sec-fetch-site') !== 'same-origin') {
  return NextResponse.json({ error: '교차 출처 요청은 처리하지 않습니다' }, { status: 403 });
}
```

본문 문구를 한국어로 적는다. `frontend/src/lib/api.ts:33` 이 응답 본문의 `error` 를
그대로 `Error.message` 로 올리므로 이 문구가 화면에 그대로 뜬다.

`UNSAFE_METHODS` 는 모듈 최상단에 둔다.

```ts
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
```

- [ ] **Step 4: 검사가 통과하는 것을 확인한다**

Run: `cd frontend && npx vitest run src/proxy.test.ts`
Expected: 열두 개 전부 PASS

---

### Task 2: 상태를 바꾸는 GET 라우트가 없음을 전수 확인한다

**Files:**
- Read only: `app/routes/*.py`
- 기록: `docs/dev-cycle/qa/INFRA-040.md`

**Interfaces:**
- Consumes: Task 1 의 결과에 의존하지 않는다. 병렬로 진행할 수 있다.
- Produces: QA 문서에 실릴 감사 결과 표

- [ ] **Step 1: GET 을 받는 라우트를 모두 뽑는다**

Flask 는 `methods` 를 적지 않으면 GET 만 허용한다. 그래서 두 가지를 함께 센다.

```bash
grep -rhn "\.route(" app/routes/*.py app/__init__.py | grep -v "methods=\['POST'\]\|methods=\[\"POST\"\]" | sort
```

- [ ] **Step 2: 각 라우트의 GET 분기가 쓰기를 하는지 확인한다**

기준을 둘로 나눈다. 「요청자의 신원으로 상태를 바꾸는가」가 CSRF 의 기준이고,
「요청 한 번으로 외부 비용이나 공유 파일 쓰기가 일어나는가」는 CSRF 는 아니지만 설계상
짚어 둘 자리다. 뒤의 기준을 「캐시 갱신 제외」로 뭉뚱그리면 Market Gate 갱신이 조용히
「읽기」로 분류된다. 이 계획의 Global Constraints 가 그 갱신을 비용 작업으로 금지하는
것과 어긋나므로 기준을 나눠 적는다.

실측했다. 백그라운드 작업을 띄우는 자리는 저장소 전체에서 다섯 곳이며 다음 명령으로
찾았다.

    grep -rn "start_background\|trigger_.*background\|Thread(" app/routes/*.py

**신원으로 상태를 바꾸는 GET 라우트는 없다.** `g.user_email` 을 읽는 GET 분기는 조회만
한다. `/api/kr/chatbot/sessions` 는 `get_all_sessions`,
`/api/kr/chatbot/history` 는 `get_messages`, `/api/kr/chatbot/profile` 은
`get_user_profile`, `/api/kr/user/quota` 는 `build_quota_info_payload` 를 부른다. 생성과
삭제는 모두 POST·DELETE 분기로 갈라져 있다
(`services/kr_market_chatbot_request_helpers.py:36,63,105`).

**신원과 무관하게 백그라운드 작업을 띄우는 GET 라우트는 둘이다.**

`GET /api/portfolio` 가 `ctx.paper_trading.start_background_sync()` 를 부른다
(`app/routes/common_portfolio_routes.py:61`). `GET /api/kr/market-gate` 는 자료가
오래되었으면 `trigger_market_gate_background_refresh()` 로 분석 스레드를 띄운다
(`app/routes/kr_market_system_http_routes.py:83` → `app/routes/kr_market.py:270`).

이 둘은 CSRF 로 악용해도 공격자가 얻는 것이 없다. 요청자의 신원을 보지 않으므로 공격자가
자기 브라우저에서 직접 불러도 결과가 같고, 피해자의 쿠키가 필요하지 않다. 그래서 이번
차단의 대상이 아니다. 다만 조회 요청이 외부 API 호출과 파일 쓰기를 일으키는 것은 별개의
설계 문제이므로 새 TODO 항목으로 이월한다.

나머지 셋은 모두 POST 라 이번 차단이 덮는다. `POST /api/system/start-update`
(`common_update_routes.py:141`), `POST /api/kr/signals/reanalyze-failed-ai`
(`kr_market_data_signals_routes.py:386`), 그리고 위 Market Gate 갱신 함수를 공유하는
`POST /api/kr/market-gate/update` 다.

- [ ] **Step 3: 결과를 QA 문서에 적는다**

한 건이라도 쓰기가 발견되면 그것은 이번 범위 안의 결함이다. 그 라우트를 POST 로 옮기는
것이 아니라, 발견 사실을 기록하고 새 TODO 항목으로 이월한 뒤 이번 라운드는 차단
자체를 마친다. 메서드를 바꾸면 프론트엔드의 호출부까지 함께 고쳐야 해서 승인 범위를
넘는다.

---

### Task 3: 위험 경로 목록에 신원 확정 자리를 추가한다

**Files:**
- Modify: `.claude/skills/dev-cycle/references/tier-rules.md` (§2 의 「시크릿과 인증」 앞)

**Interfaces:**
- Consumes: 없다
- Produces: 다음 사이클이 이 두 파일을 건드릴 때 T3 으로 판정하게 되는 근거

- [ ] **Step 1: 절을 하나 더한다**

```markdown
### 신원 확정

- `frontend/src/proxy.ts`
- `services/identity_helpers.py`

`[INFRA-027]` 이 만든 두 파일이다. 앞의 것은 모든 API 요청에 신원 서명을 붙이고 뒤의
것은 그 서명을 검증한다. 저장소 전체에서 「이 요청자가 누구인가」를 정하는 자리가 이 둘
뿐이므로, 한쪽만 고치면 모든 요청이 조용히 익명으로 떨어진다. 화면은 멀쩡히 뜨고
로그인 표시도 남으므로 대화 목록이 비어 있는 것으로만 드러난다.

`[INFRA-040]` 에서 추가했다. `[INFRA-027]` 이 두 파일을 만들면서 §4 의 목록 갱신을
이행하지 않아 그동안 목록 밖에 있었다.
```

- [ ] **Step 2: §2 머리글의 수치를 갱신한다**

머리글이 「2026-09-02 기준 실측 결과이며 63개 파일, 23,357줄이다」로 적혀 있다. 실측하면
지금 목록은 64개이고(`[CHAT-003]` 이 더한 `sqlite_ready_gate.py` 가 반영되지 않았다), 이번
둘을 더하면 66개 23,695줄이다. 세는 명령을 함께 적어 다음 갱신이 다시 알아내지 않게 한다.

- [ ] **Step 3: 목록의 파일이 실재하는지 확인한다**

Run: `ls frontend/src/proxy.ts services/identity_helpers.py`
Expected: 둘 다 존재. §4 는 「목록에 적힌 경로는 모두 실재해야 한다」고 정한다.

---

### Task 4: 검증하고 첫 커밋을 남긴다

**Files:**
- Create: `docs/dev-cycle/qa/INFRA-040.md`
- Modify: `docs/dev-cycle/TODO.md`

- [ ] **Step 1: 정적 검증 셋을 돌린다**

```bash
source venv/bin/activate && pytest
cd frontend && npx vitest run
cd frontend && npm run type-check
```
Expected: 세 명령 모두 종료 코드 0

- [ ] **Step 2: 시크릿 확인 세 가지**

```bash
git ls-files | grep '^\.env'          # .env.example 만 나와야 한다
grep -rn "NEXT_PUBLIC_" frontend/src/ # 신원 관련 값이 없어야 한다
```

- [ ] **Step 3: QA 시나리오 문서를 만든다**

`/qa-only` 로 시나리오를 확정해 `docs/dev-cycle/qa/INFRA-040.md` 에 적는다. 회귀
시나리오는 「다른 오리진의 페이지에서 보낸 `POST /api/kr/user/quota/recharge` 가 403 을
받는다」에서 출발한다.

- [ ] **Step 4: 첫 커밋**

```bash
git add frontend/src/proxy.ts frontend/src/proxy.test.ts \
        .claude/skills/dev-cycle/references/tier-rules.md \
        docs/dev-cycle/qa/INFRA-040.md docs/dev-cycle/TODO.md \
        docs/superpowers/plans/2026-09-07-infra-040-csrf-gate.md
git diff --cached --check
git commit -m "fix(infra): [INFRA-040] 교차 출처 비안전 요청을 proxy 에서 끊는다"
```

TODO 항목은 이 커밋에서 지우지 않는다. QA 가 실패하면 재개할 자리가 사라진다.

---

## Self-Review

**1. 승인 범위 대조**

승인받은 세 가지가 각각 Task 1(403 거부), Task 1 Step 3(신원 확정 요청에서만 검사,
헤더 부재 차단), Task 3(위험 경로 목록과 T3)에 들어 있다. TODO 의 체크박스 셋 가운데
「상태를 바꾸는 GET 라우트 전수 확인」이 Task 2 다.

**2. 자리 표시자 점검**

TBD 와 「적절히 처리」류의 문구가 없다. 코드 단계에는 모두 실제 코드가 있다.

**3. 이름과 형식의 일관성**

`UNSAFE_METHODS`, `requestWith(headers, method)`, `forwardedHeaders(res)` 세 이름이
Task 1 의 검사와 구현에서 같은 철자로 쓰였다. `NextResponse.json` 은
`frontend/src/app/api/system/env/route.ts:38` 이 이미 쓰는 방식이다.

**4. 설계 검토에서 미리 짚어 둘 것**

`proxy.test.ts` 의 기존 `requestWith` 는 `{ headers }` 만 담은 객체를 `as never` 로
넘긴다. `request.method` 를 읽는 코드를 넣으면 그 객체에 `method` 가 없어 `undefined` 가
되고, `UNSAFE_METHODS.has(undefined)` 는 `false` 라 검사가 조용히 통과한다. **기존
검사 일곱 개가 계속 통과하는 것이 이 함정을 가려 준다.** Step 1 에서 `requestWith` 를
먼저 고치는 이유가 이것이다.

---

## 계획 검토 반영 (2026-09-07)

`oh-my-claudecode:critic` 의 판정은 **REVISE** 였다. 지적 일곱 개 가운데 여섯을 반영했다.

**반영한 것**

- 판정 기준을 「캐시 갱신 제외」에서 「요청 한 번으로 외부 비용이나 공유 파일 쓰기가
  일어나는가」로 나눴다. 종전 기준이면 Market Gate 갱신이 조용히 「읽기」가 된다.
  `methods=` 없는 GET 전용 라우트가 21개로 표의 7개보다 많다는 지적도 함께 받아, 표를
  버리고 백그라운드 작업 트리거를 grep 으로 전수 조사한 결과로 바꿨다.
- 익명 경로가 전제를 깨지 않는 근거를 「어차피 익명이라」에서 「익명 신원은 브라우저가
  자동으로 붙이는 값이 아니다」로 고쳤다. 누가 그 값을 쿠키로 옮기면 전제가 깨진다는 것이
  이 서술에서만 보인다.
- 403 본문의 문구를 한국어로 바꿨다. `frontend/src/lib/api.ts:33` 이 본문의 `error` 를
  `Error.message` 로 올려 화면에 그대로 띄운다.
- 비밀이 비어 있을 때 차단이 켜지지 않는 것을 고정하는 검사를 더했다.
- `tier-rules.md` §2 머리글의 「63개 파일, 23,357줄」을 갱신하는 단계를 Task 3 에 더했다.
- 내부 경로가 깨지지 않는다는 확인(`app/api/system/env/route.ts:44` 가 `FLASK_BASE` 로
  직행해 proxy 를 지나지 않는다)과 위험 경로 추가가 §4 에 부합한다는 확인을 받았다.

**반영하지 않은 것**

지적 1 은 「`Sec-Fetch-Site` 부재를 차단하면 사파리 16.4 미만에서 로그인 사용자의 모든
POST·DELETE 가 403 이 되므로, 헤더가 없을 때 `Origin` 을 대조하자」였다. 사실 확인 결과
지적이 맞았다. 사파리는 16.4(2023-03)부터 이 헤더를 보낸다.

이 사실과 대안을 사용자에게 다시 여쭈었고, **「승인한 대로 헤더 부재를 차단한다」로
결정되었다**(2026-09-07 AskUserQuestion 응답). 그래서 검사를 한 줄로 유지하고, 대신 그
결과를 코드 주석에 명시해 다음에 문의가 들어왔을 때 무엇을 더하면 되는지 남긴다.

---

## 구현 중 바뀐 것 (2026-09-07)

이 계획의 Task 1 은 검사를 `if (email)` 블록 **안**에 두었습니다. 구현과 리뷰를 거치며
두 가지가 달라졌으므로, 계획을 읽는 사람이 코드와 대조할 때 혼동하지 않도록 적어 둡니다.

**1. 검사를 신원 서명 블록 밖으로 옮겼습니다.**

`oh-my-claudecode:security-reviewer` 의 지적입니다(확신도 높음). 계획대로 `if (secret)`
안에 두면 `INTERNAL_IDENTITY_SECRET` 이 빈 배포에서 차단이 통째로 꺼집니다. 그런데
`frontend/src/app/api/system/env/route.ts:26` 의 `resolveAdminToken` 은 `getServerSession`
만 보므로 그 값과 무관하게 관리자를 통과시키고, 그 라우트는 `.env` 쓰기까지 닿습니다.
기본값이 빈 문자열이라 개발기와 신규 배포에서 현실적인 상태입니다.

`getToken` 은 `NEXTAUTH_SECRET` 을 읽으며 `INTERNAL_IDENTITY_SECRET` 과 무관합니다. 쿠키가
없거나 복호화에 실패하면 예외 없이 `null` 을 돌려주므로(`next-auth/jwt/index.js:89,95`)
블록 밖에서 불러도 안전합니다. 그래서 지금 구조는 「`getToken` → 차단 검사 → 서명」입니다.

검사도 뒤집었습니다. 「비밀이 없으면 교차 출처 POST 도 막지 않는다」였던 것이
「`INTERNAL_IDENTITY_SECRET` 이 비어도 로그인 사용자의 교차 출처 POST 는 막는다」가
되었습니다.

**2. 메서드를 대문자로 정규화합니다.**

`/review` 의 Enum & Value Completeness 항목이 `UNSAFE_METHODS` 의 완전성을 물어 소문자
메서드를 실측했습니다. 지금은 Node 와 gunicorn 의 HTTP 파서가 400 으로 끊지만 그 방어가
저장소 코드 밖에 있습니다. 이 항목이 고치는 결함 자체가 「방어의 근거가 라이브러리
기본값에만 있다」이므로 `request.method.toUpperCase()` 로 닫고 검사를 하나 더했습니다.

검사는 여섯 개에서 일곱 개가 되어 파일 전체로는 열넷입니다.
