# [INFRA-027] X-User-Email 신원 위조 차단 — QA 시나리오

- 대상: `http://localhost:3500`(Next 경유)와 `http://localhost:5501`(Flask 직접) 두 경로
- 구성 근거: 이번 사이클의 변경 파일 전부와 `oh-my-claudecode:critic` 계획 검토의 C-1·M-4,
  `/review` critical pass 가 찾은 익명 ID 형식 결함
- 구성 2026-09-07 18:30 | 실행 2026-09-07 18:33 | 보안 리뷰 반영 후 재확인 18:52
- QA 엔진(engine): Claude Code — 시나리오 구성과 실행을 같은 문맥에서 이어감
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 임시 프로브 로그로 기준값 수집 완료 (실행 후 제거)
- 필수 여부(required): 예
- 결과: 필수 11/11 통과 (S-9 는 대체 수단)
- 증거: `logs/backend.log` 의 `[INFRA-027 probe]` 줄 (아래 각 시나리오에 인용)
- 정리(cleanup): 임시 프로브 제거 완료, 임시 스크립트 삭제 완료, `data/` 미변경

## 실측 방법에 관한 두 가지 사전 결정

**1. Google 로그인 대신 세션 쿠키를 직접 만들었다.** 이 세션은 사용자 자격 증명을 다루지
않기로 했으므로 실제 Google 로그인을 하지 않는다. 대신 `next-auth/jwt` 의 `encode` 로
`NEXTAUTH_SECRET` 을 써서 세션 토큰을 만들고 쿠키로 실어 보냈다. proxy 가 보는 것은
`getToken()` 의 반환값이므로, 이 방법과 실제 로그인은 proxy 입장에서 구분되지 않는다.
비밀과 토큰 값은 어디에도 출력하지 않았다.

**2. `data/` 를 바꾸는 시나리오는 실행하지 않았다.** 이 세션은 `data/` 를 읽기 전용으로
다룬다. 충전 하루 1회 제한은 화면에서 누르면 `data/user_quota.json` 을 만들고 고치므로,
아래 S-9 에서 대체 수단을 적었다. 챗봇 세션 목록 조회는 읽기 동작이라 수행했다.

## 임시 프로브에 관하여

계획 Task 3 Step 5 에 따라 `app/__init__.py` 의 `before_request` 끝에 아래 한 덩이를
임시로 넣고 실측한 뒤 제거했다. 헤더 값 자체는 찍지 않고 유무와 판정 결과만 남겼다.

```python
logging.getLogger(__name__).warning(
    "[INFRA-027 probe] %s %s identity_present=%s resolved=%s session=%s",
    request.method, request.path,
    bool(request.headers.get('X-Auth-Identity')),
    bool(g.user_email), bool(g.session_id),
)
```

제거는 `grep -c 'INFRA-027 probe' app/__init__.py` 가 `0` 을 내는 것과
`git diff --stat app/__init__.py` 가 `9 insertions, 2 deletions` 인 것으로 확인했다.

## 시나리오

### S-1. proxy 가 붙인 신원이 Flask 까지 닿는다 (회귀 · 이 라운드의 핵심 가정)
- 조작: NextAuth 세션 쿠키를 실어 `http://localhost:3500/api/kr/user/quota` 를 부른다.
- 기대: 프로브 로그가 `identity_present=True resolved=True`. 응답 본문에 `is_exhausted` 와
  `server_key_configured` 가 있다(익명이면 「무료 10회 사용 가능」 메시지가 나온다).
- 필수 여부(required): 예
- 실제: `2026-09-07 18:33:41,745 ... GET /api/kr/user/quota identity_present=True resolved=True session=False`.
  응답은 `{"is_exhausted": false, "limit": 10, "remaining": 10, "server_key_configured": true, "usage": 0}`.
- 결과: **통과**
- 증거: 위 로그 줄과 응답 본문
- 정리(cleanup): 임시 스크립트 `frontend/__infra027_probe.cjs` 실행 직후 삭제

**이 시나리오가 이 라운드에서 가장 중요하다.** 계획 전체가 「proxy 가 붙인 request 헤더가
`next.config.js` 의 afterFiles rewrite 목적지(`http://127.0.0.1:5501`)까지 전달된다」는
가정 하나 위에 서 있었다. 그 가정이 틀리면 로그인 사용자 전원이 조용히 익명으로 떨어지는데,
pytest 는 헤더를 스스로 만들어 넣고 vitest 는 서명 문자열 형식만 보므로 어느 자동 검사도
실패하지 않는다. 상태 코드 200 도 증거가 되지 않는다. 익명 응답도 200 이기 때문이다.

### S-2. proxy 가 클라이언트의 위조 헤더를 지운다 (회귀)
- 조작: 세션 없이 `X-User-Email: victim@example.com` 과
  `X-Auth-Identity: forged.9999999999.deadbeef` 를 실어 3500 포트로 부른다.
- 기대: 프로브 로그가 `identity_present=False resolved=False`. 두 헤더가 모두 지워져야 한다.
- 필수 여부(required): 예
- 실제: `18:33:09,613 ... identity_present=False resolved=False session=False`
- 결과: **통과**
- 증거: 위 로그 줄
- 정리(cleanup): 없음

### S-3. Flask 에 직접 닿는 위조 서명이 거부된다 (회귀)
- 조작: proxy 를 건너뛰고 5501 포트에 `X-Auth-Identity: Zm9yZ2Vk.9999999999.deadbeef` 를 보낸다.
- 기대: 헤더는 도착하지만(`identity_present=True`) 서명 검증에 실패해 `resolved=False`.
- 필수 여부(required): 예
- 실제: `18:34:06,886 ... identity_present=True resolved=False session=False`
- 결과: **통과**
- 증거: 위 로그 줄
- 정리(cleanup): 없음

개발 환경에서는 Flask 가 5501 로 직접 열려 있어 proxy 를 우회할 수 있다. 그래서 Flask 쪽
검증이 유일한 실효 방어선이며, 이 시나리오가 그것을 확인한다.

### S-4. X-Session-Id 에 남의 이메일을 넣어도 소유자가 되지 않는다 (회귀)
- 조작: 5501 포트에 `X-Session-Id: victim@example.com` 을 보낸다.
- 기대: `session=False`. 챗봇 세션 목록은 빈 배열.
- 필수 여부(required): 예
- 실제: `18:34:06,899 ... session=False` 와
  `18:34:38,191 ... GET /api/kr/chatbot/sessions ... session=False`. 응답은 `{"sessions": []}`.
- 결과: **통과**
- 증거: 위 두 로그 줄과 응답 본문
- 정리(cleanup): 없음

이 시나리오가 없으면 서명 게이트를 만들어 두고도 헤더 이름 하나로 우회된다. 챗봇 owner_id 와
쿼터 키가 검증된 이메일과 익명 ID 를 같은 문자열 공간에 담기 때문이다. 관리자 이메일을 넣으면
`services/kr_market_chatbot_quota_helpers.py:49` 의 `is_admin_email` 까지 통과해 쿼터가
무제한이 된다.

**실측 뒤 판정을 한 번 더 좁혔다.** 보안 리뷰가 `@` 배제만으로는 두 가지가 남는다고 지적했다.
`recharge_day:` 접두사와 충돌할 수 있고(충전을 익명에 다시 열면 자기 날짜 표지를 덮어써 하루
1회 제한을 우회한다), 길이 상한이 없어 헤더 한도만큼 큰 키가 `data/user_quota.json` 에 무제한
으로 쌓인다. 판정을 `re.fullmatch(r"[A-Za-z0-9_-]{1,128}")` 로 바꿔 셋을 함께 닫았다.

**바뀐 것은 판정 로직뿐이고 배선은 그대로다.** 라우트가 `g.session_id` 를 읽고 그 값이
`resolve_anonymous_id` 에서 온다는 사실은 위 프로브 로그가 이미 확인했다. 새 판정이 어떤
값을 받고 버리는지는 `tests/services/test_identity_helpers.py` 14건이 고정한다. 그 안에
이 시나리오의 다섯 입력이 모두 들어 있다.

### S-5. 정상 익명 ID 세 형식이 모두 통과한다 (회귀)
- 조작: 5501 포트에 세 형식을 각각 보낸다.
  `anon_qa_probe_1`(`frontend/src/lib/session.ts:16`),
  `vcp_005930_<uuid>`(`vcp/page.tsx:1043`),
  `0f8c2b1e-1a2b-4c3d-9e8f-7a6b5c4d3e2f`(`chatbot/storage.py:295` 가 배정하는 순수 uuid).
- 기대: 셋 모두 `session=True`.
- 필수 여부(required): 예
- 실제: `anon_` 은 `18:34:06,912 ... session=True`, 접두사 없는 uuid 는
  `18:34:06,925 ... session=True`. `vcp_` 형식은
  `tests/services/test_identity_helpers.py::test_anonymous_id_accepts_every_shape_the_code_makes`
  가 같은 판정을 고정한다.
- 결과: **통과**
- 증거: 위 두 로그 줄과 해당 단위 검사
- 정리(cleanup): 없음

**세 번째 형식이 이 라운드에서 두 번째로 중요하다.** 처음 구현은 `anon_` 접두사만 허용했는데,
`chatbot/session_access.py:82` 가 소유자 불일치를 발견하면 접두사 없는 새 세션을 배정하고
VCP 화면이 그것을 저장해(`page.tsx:1101`) 다음 요청의 `X-Session-Id` 로 쓴다. 그대로 두었으면
비로그인 사용자의 VCP 채팅이 영구히 끊겼을 것이고, **로그인한 채로 확인하면 이메일이 소유자라
멀쩡해 보여 발견하지 못했을 것이다.** `/review` 의 Enum & Value Completeness 가 찾았다.

### S-6. 위조한 X-User-Email 로 남의 챗봇 세션 목록을 읽지 못한다 (회귀)
- 조작: 5501 포트에 `X-User-Email: victim@example.com` 을 실어
  `/api/kr/chatbot/sessions` 를 부른다.
- 기대: `resolved=False` 이고 응답이 `{"sessions": []}`.
- 필수 여부(required): 예
- 실제: `18:34:38,249 ... identity_present=False resolved=False session=False`, 응답 `{"sessions": []}`
- 결과: **통과**
- 증거: 위 로그 줄과 응답 본문
- 정리(cleanup): 없음

저장된 대화가 없는 환경이라 빈 목록 자체는 약한 증거다. 직접 증거는 `resolved=False` 이며,
`tests/app/test_kr_market_chatbot_service.py` 의 두 검사가 `owner_id` 가 실제로 무엇이 되는지를
고정한다.

### S-7. 쿼리 파라미터로 남의 쿼터를 조회하지 못한다 (회귀)
- 조작: `/api/kr/user/quota?email=victim@example.com` 을 부른다.
- 기대: 그 이메일이 무시되고 요청자 자신의 신원으로 판정된다.
- 필수 여부(required): 예
- 실제: `tests/app/test_kr_market_quota_http_routes_refactor.py::test_get_user_quota_info_returns_expected_payload`
  가 이 URL 을 그대로 부르고 주입한 신원의 사용량이 나오는 것을 고정한다. 라우트에
  `request.args.get("email")` 이 남아 있지 않음을 `grep` 으로 확인했다.
- 결과: **통과**
- 증거: 해당 검사와 `grep -n 'args.get\|data.get' app/routes/kr_market_quota_http_routes.py` 의 빈 출력
- 정리(cleanup): 없음

### S-8. 만료된 서명이 거부된다 (회귀)
- 조작: `exp` 가 지난 서명을 검증한다.
- 기대: `None` 을 돌려준다. 경계값(`now == exp`)은 통과한다.
- 필수 여부(required): 예
- 실제: `tests/services/test_identity_helpers.py::test_rejects_expired_signature` 와
  `::test_accepts_at_exact_expiry` 가 통과한다.
- 결과: **통과**
- 증거: 위 두 검사
- 정리(cleanup): 없음

만료는 120초라 curl 로 재현하려면 그 시간을 기다려야 한다. 판정 자체는 순수 함수이므로 단위
검사가 같은 것을 더 정확히 본다.

### S-9. 충전이 하루 한 번만 된다 (회귀 · 대체 수단으로 확인)
- 조작: 같은 신원으로 충전을 두 번 시도한다.
- 기대: 첫 번째는 200 과 「5회 충전 완료」, 두 번째는 429 와 「충전은 하루 한 번만 가능합니다」.
  로그인하지 않았으면 401 과 「로그인이 필요합니다」.
- 필수 여부(required): 예
- 실제: 화면에서 누르면 `data/user_quota.json` 을 만들고 고치므로 이 세션의 `data/` 읽기 전용
  제약에 따라 실행하지 않았다. 대신 두 층의 검사로 확인했다.
  `tests/services/test_quota_recharge_daily_limit.py` 6건이 저장 계층의 판정을(같은 날 거절,
  다음 날 허용, 사용자별 분리, 날짜가 정수로 저장되는지) 고정하고,
  `tests/app/test_kr_market_quota_http_routes_refactor.py` 가 라우트의 401·429·200 응답을
  고정한다.
- 결과: **통과** (대체 수단)
- 증거: 위 두 검사 파일, 합계 11건
- 정리(cleanup): `data/` 미변경

### S-10. 비밀이 없으면 전원 익명으로 떨어진다 (설정 오류)
- 조작: `INTERNAL_IDENTITY_SECRET` 이 비어 있는 상태로 요청을 보낸다.
- 기대: 서명이 붙지 않거나 검증되지 않아 익명으로 처리된다. 열리는 방향이 아니라 닫히는
  방향으로 실패해야 한다.
- 필수 여부(required): 예
- 실제: 이 라운드 초반에 `.env` 에 키가 없는 상태였고, 그때 세션 쿠키 없이 보낸 요청이 전부
  `identity_present=False resolved=False` 였다. `verify_identity_header` 는 비밀이 비면 즉시
  `None` 을 돌려주며 `tests/services/test_identity_helpers.py::test_rejects_when_secret_unset`
  이 그것을 고정한다.
- 결과: **통과**
- 증거: 위 검사와 초기 프로브 로그
- 정리(cleanup): 없음

### S-11. 운영 설정의 NEXTAUTH_URL 이 https 다 (설정 오류)
- 조작: `.env.production` 의 값을 확인한다.
- 기대: `https://` 로 시작한다. http 이면 `getToken` 이 `__Secure-` 접두사 쿠키를 찾지 못해
  로그인 사용자 전원이 조용히 익명이 된다(`next-auth/jwt/index.js:65`).
- 필수 여부(required): 예
- 실제: `grep -c '^NEXTAUTH_URL=https://' .env.production` 이 `1`.
- 결과: **통과**
- 증거: 위 명령의 출력
- 정리(cleanup): 없음

## 이월한 발견

- **익명 챗봇 쿼터는 여전히 초기화할 수 있다.** 브라우저에서 `browser_session_id` 를 지우면 새
  익명 ID 가 발급되어 무료 10회가 다시 시작된다. 승인 범위가 「익명 유지 + 쿼터 경로만 로그인
  필수」였고 챗봇은 익명에게 열어 두기로 했으므로 이번에 막지 않았다. 막으려면 서버가 익명 ID 를
  발급해야 한다. `services/kr_market_chatbot_request_helpers.py` 의 `resolve_chatbot_usage_context`
  docstring 에 이 한계를 적어 두었다.
- **서명이 요청에 묶이지 않은 120초 bearer 다.** → `[INFRA-039]` 로 이월했다. 경로·메서드·nonce
  어디에도 묶여 있지 않아 한 번 새면 그동안 아무 엔드포인트에나 쓸 수 있다. 이것을 받아들인
  근거는 서명이 오가는 구간이 proxy 와 Flask 사이뿐이고 브라우저로 돌아가지 않는다는 것이었는데
  (`proxy.ts` 가 `NextResponse.next({ request: { headers } })` 를 쓰는 이유다), 보안 리뷰가
  **그 구간이 loopback 이라는 보장이 코드에 없다**고 지적했다. `restart_all.sh:80` 과 `Procfile`,
  `app/__init__.py:299` 가 모두 `0.0.0.0` 에 바인딩한다. 검토자는 서명에 경로와 메서드를 넣는
  것보다 바인딩 주소를 좁히는 편이 싸다고 했다. `Procfile` 배포에서는 `0.0.0.0` 이 필요해
  환경별로 나누는 방식을 먼저 정해야 하므로 이번 범위를 넘는다. nonce 저장소는 워커 간 공유가
  필요해 이 규모에 과잉이다.

## 실행 결과

- 필수 시나리오: 통과 11 / 전체 11 (S-9 는 대체 수단)
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 보안 리뷰가 `[INFRA-039]` 로 이월할 것 한 건과, 익명 ID 판정을
  더 좁혀야 할 근거 두 가지를 찾았다. 뒤의 둘은 이번 사이클에서 고쳤고 검사 3건을 더했다.
