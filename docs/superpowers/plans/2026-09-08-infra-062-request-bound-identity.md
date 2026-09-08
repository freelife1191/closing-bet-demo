# INFRA-062 Request-Bound Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 또는 executing-plans. root가 통합과 단계별 검증/커밋을 소유한다.

**Goal:** 다른 method/path에 복사된 신원 서명을 거부한다.
**Architecture:** 기존 HMAC에 버전과 actual method/path를 추가하며 상태 저장소를 늘리지 않는다. Next에서 한 번 decode한 pathname과 Flask request.path를 결합한다.
**Tech Stack:** Next.js 16.3.4, TypeScript, Python/Flask, HMAC-SHA256, pytest/vitest.
**Spec:** docs/superpowers/specs/2026-09-08-infra-062-request-bound-identity-design.md

## Global Constraints

사용자 「진행해」가 같은 설계/계획/구현을 승인했다. 재승인 없이 진행한다. 원본 .env/data/3500/5501/live 및 외부 네트워크 호출 금지. clone develop만 변경. 새 의존성/DB/nonce/배포 없음. package.json 보존. 리뷰 각 12분·검증 명령 각 180초·동적 하네스 15분 상한(초과는 실패/진단, 자동PASS 금지). QA 최대5회/동일실패3회.

## Task 1 — Python verifier and actual request callers

Files: services/identity_helpers.py, app/__init__.py, app/routes/common_portfolio_routes.py, tests/services/test_identity_helpers.py.
Interface: `verify_identity_header(header, now=None, *, method: str, path: str) -> str | None`.

- [x] RED: 같은 구형 유효 header를 서로 다른 보호 경로에 주어 거부 기대가 현재 실패함을 확인한다.
- [x] MAC payload는 `f"v2.{encoded}.{raw_exp}.{method.upper()}.{encoded_path}"`; header는 4 parts/versionv2만 허용한다. request path는 이미 decode됐으므로 재해석하지 않는다.
- [x] 두 production caller에 `method=request.method, path=request.path`를 넣는다. 기존 anonymous/OPTIONS/owner정책 유지.
- [x] 정상, crosspath/method, 구형·만료·위조·비ASCII MAC·기본이메일·예약ID 거부 테스트 GREEN. 서명/키를 로그에 쓰지 않는다.

## Task 2 — Next signer/proxy

Files: frontend/src/lib/identity.ts, frontend/src/lib/identity.test.ts, frontend/src/proxy.ts, frontend/src/proxy.test.ts.
Interface: `signIdentity(email: string, secret: string, expiresAt: number, method: string, path: string): string`.

- [x] RED: 실제 NextRequest를 이용해 path/method가 달라지면 서명이 달라지는 검사를 먼저 실행한다.
- [x] payload는 ``v2.${encoded}.${expiresAt}.${method.toUpperCase()}.${Buffer.from(path,'utf8').toString('base64url')}``; 반환은 ``v2.${encoded}.${expiresAt}.${mac}``.
- [x] proxy가 `decodeURIComponent(request.nextUrl.pathname)`와 method를 전달한다. URIError는 일반400, 신원헤더는 계속 제거하고 응답에 노출하지 않는다. CSRF/OPTIONS/익명행동 유지.
- [x] 고정 vector·Unicode/percent/trailing slash/HEAD·구형계약 회귀를 갱신하고 vitest/typecheck를 실행한다. Next 번들 proxy/NextRequest 문서를 읽는다.

## Task 3 — Boundary fixtures and independent cross-runtime proof

Files: tests/app/test_identity_gate.py, tests/app/test_portfolio_owner_boundary.py, tests/app/test_common_portfolio_routes_refactor.py, tests/app/test_admin_gated_routes.py, tests/app/test_notification_admin_gate.py, tests/verify_portfolio_api.py. Create: tests/fixtures/identity_v2_vectors.json, tests/services/test_identity_cross_runtime.py, tests/app/test_identity_replay.py.

- [x] 7개 직접 HMAC fixture를 actual route/method별로 갱신한다. HMAC을 검증한다고 주장하는 테스트에서 g.user_email을 직접 심지 않는다.
- [x] 고정 vector에 '/api/portfolio', '/api/한글/%2F', trailing slash와 서로 다른 method를 담고 TS/코어Python이 같은MAC을 만드는 것을 확인한다.
- [x] Node에서 TS signer를 실행한 실제 output을 Python verifier로 검증한다. 다른route/method로 복사하면 None/401/403이며 업무부수효과0을 단언한다.
- [x] 기존 업무기대값을 유지하여 전체 pytest/vitest/typecheck/lint와 수동verify를 통과시킨다.

## Task 4 — Integration, review and UltraQA

Files: CLAUDE.md, README.md, app/routes/common_notification_routes.py(낡은 제한 주석), docs/dev-cycle/TODO.md, docs/dev-cycle/qa/INFRA-062.md, docs/dev-cycle/reviews/INFRA-062.md, docs/dev-cycle/evidence/INFRA-062/.

- [x] 승인범위/critic판정 기록 후 코드 구현. ponytail→독립code/security/architect→deep review 순서를 지킨다. 각 원문과 입력hash를 기록한다.
- [x] 실제 Next→rewrite→bare Flask probe를 합성JWT/가짜secret으로 준비한다. GET과POST정상→서명복사→메서드/경로변경→구형/위조/만료→Unicode/trailing/double encoding을 검사한다. 운영 endpoint 대신 부수효과없는 probe를 사용한다.
- [x] 전체검사 후 allowlist staging, staged --check=0 후 첫 구현/행렬커밋(TODO유지). exactcommit QA를 같은턴에 수행한다.
- [x] native hook 쓰기 없이 UltraQA app-adapted 보고서에 필수결과/실패/수정/정리를 기록한다. 기준sourcehash와서명/secret의응답·브라우저bundle비노출을 확인한다.
- [x] QA실행용 임시프로세스/파일 정리, 증거커밋, 원본 develop ff, clone정리 후 최종 아카이브에서만 TODO를 제거한다. 검증된한항목에서 종료한다.

## Critic 보완 실행 규칙

- spec의 실제 전송 경로 기대값 표를 그대로 assertion으로 구현한다. raw target→Next pathname→decoded path→Flask path와 client-visible status/Location, Flask-hit 증가량을 함께 검사한다.
- actual HTTP malformed `%`, `%ZZ`, `%FF` 3개는 단위 NextRequest 생성실패로 대신하지 않는다. `http.client` 원문요청 400/Flask hit0을 확인한다.
- `/tail/`은 Next 기본308(Location slash없음)/Flask hit0, 그 목적지는 재서명200/Flask hit1. utility level에서는 slash 유무 MAC 차이를 별도로 검사한다.
- probe는 UI변경이 없는 protocol 작업이므로 실제 Next 서버+bare Flask+CLI HTTP로 실행한다. 브라우저 화면을 봤다고 주장하지 않는다. NextAuth JWT는 설치된 next-auth/jwt.encode로 합성하고 실제 proxy getToken 경로를 사용한다. 응답에 서명/secret이 없음을 단언하며 captured header는 Python 프로세스 메모리에서만 controller가 읽는다.

- 인증 필수검증1: `git ls-files`의 basename이 `.env`로 시작하는 모든 추적 경로를 검사해 `.env.example` 외 0개를 단언한다. 실제 .env 내용은 열지 않는다. 결과: docs/dev-cycle/evidence/INFRA-062/security-checks.json.
- 인증 필수검증2: HTTP 하네스의 unique fake secret, 포착한 전체 v2 header와 MAC가 API본문·client-visible response headers·proxy/backend 실행 로그·증거 로그에 없는지 검사한다. `x-auth-identity`와 `x-middleware-request-*` 응답 header도 부재를 단언한다. 테스트의 의도적인 고정벡터 입력 파일과 가짜값이 적힌 테스트 소스는 실행 로그가 아니며 별도로 표기한다. TDD RED는 boolean/상태 단언으로 민감문자열을 로그에 출력하지 않는다. 결과: docs/dev-cycle/evidence/INFRA-062/security-checks.json.
- 인증 필수검증3: 소스의 `NEXT_PUBLIC_` 변수 이름 목록을 먼저 수집하고 `NEXT_PUBLIC_INTERNAL_IDENTITY_SECRET` 등 신원비밀공개설정 0개를 단언한다. unique sentinel secret을 server env에 둔 build/실행 뒤 `frontend/.next/static` client chunks에서 그 값과 실제 v2 header/MAC 0건을 단언한다. 결과: docs/dev-cycle/evidence/INFRA-062/security-checks.json. 네트워크 의존성감사는 신규 dependency가 없어 수행하지 않는다.
