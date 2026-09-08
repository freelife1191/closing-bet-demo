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

- [ ] RED: 같은 구형 유효 header를 서로 다른 보호 경로에 주어 거부 기대가 현재 실패함을 확인한다.
- [ ] MAC payload는 `f"v2.{encoded}.{raw_exp}.{method.upper()}.{encoded_path}"`; header는 4 parts/versionv2만 허용한다. request path는 이미 decode됐으므로 재해석하지 않는다.
- [ ] 두 production caller에 `method=request.method, path=request.path`를 넣는다. 기존 anonymous/OPTIONS/owner정책 유지.
- [ ] 정상, crosspath/method, 구형·만료·위조·비ASCII MAC·기본이메일·예약ID 거부 테스트 GREEN. 서명/키를 로그에 쓰지 않는다.

## Task 2 — Next signer/proxy

Files: frontend/src/lib/identity.ts, identity.test.ts, frontend/src/proxy.ts, proxy.test.ts.
Interface: `signIdentity(email: string, secret: string, expiresAt: number, method: string, path: string): string`.

- [ ] RED: 실제 NextRequest를 이용해 path/method가 달라지면 서명이 달라지는 검사를 먼저 실행한다.
- [ ] payload는 ``v2.${encoded}.${expiresAt}.${method.toUpperCase()}.${Buffer.from(path,'utf8').toString('base64url')}``; 반환은 ``v2.${encoded}.${expiresAt}.${mac}``.
- [ ] proxy가 `decodeURIComponent(request.nextUrl.pathname)`와 method를 전달한다. URIError는 일반400, 신원헤더는 계속 제거하고 응답에 노출하지 않는다. CSRF/OPTIONS/익명행동 유지.
- [ ] 고정 vector·Unicode/percent/trailing slash/HEAD·구형계약 회귀를 갱신하고 vitest/typecheck를 실행한다. Next 번들 proxy/NextRequest 문서를 읽는다.

## Task 3 — Boundary fixtures and independent cross-runtime proof

Files: tests/app/test_identity_gate.py, test_portfolio_owner_boundary.py, test_common_portfolio_routes_refactor.py, test_admin_gated_routes.py, test_notification_admin_gate.py, tests/verify_portfolio_api.py; new tests/fixtures/identity_v2_vectors.json and tests/services/test_identity_cross_runtime.py if needed.

- [ ] 7개 직접 HMAC fixture를 actual route/method별로 갱신한다. HMAC을 검증한다고 주장하는 테스트에서 g.user_email을 직접 심지 않는다.
- [ ] 고정 vector에 '/api/portfolio', '/api/한글/%2F', trailing slash와 서로 다른 method를 담고 TS/코어Python이 같은MAC을 만드는 것을 확인한다.
- [ ] Node에서 TS signer를 실행한 실제 output을 Python verifier로 검증한다. 다른route/method로 복사하면 None/401/403이며 업무부수효과0을 단언한다.
- [ ] 기존 업무기대값을 유지하여 전체 pytest/vitest/typecheck/lint와 수동verify를 통과시킨다.

## Task 4 — Integration, review and UltraQA

Files: CLAUDE.md, README.md, app/routes/common_notification_routes.py(낡은 제한 주석), docs/dev-cycle/TODO.md, qa/INFRA-062.md, reviews/INFRA-062.md, evidence/INFRA-062/.

- [ ] 승인범위/critic판정 기록 후 코드 구현. ponytail→독립code/security/architect→deep review 순서를 지킨다. 각 원문과 입력hash를 기록한다.
- [ ] 실제 Next→rewrite→bare Flask probe를 합성JWT/가짜secret으로 준비한다. GET과POST정상→서명복사→메서드/경로변경→구형/위조/만료→Unicode/trailing/double encoding을 검사한다. 운영 endpoint 대신 부수효과없는 probe를 사용한다.
- [ ] 전체검사 후 allowlist staging, staged --check=0 후 첫 구현/행렬커밋(TODO유지). exactcommit QA를 같은턴에 수행한다.
- [ ] native hook 쓰기 없이 UltraQA app-adapted 보고서에 필수결과/실패/수정/정리를 기록한다. 기준sourcehash와서명/secret의응답·브라우저bundle비노출을 확인한다.
- [ ] QA실행용 임시프로세스/파일 정리, 증거커밋, 원본 develop ff, clone정리 후 최종 아카이브에서만 TODO를 제거한다. 검증된한항목에서 종료한다.
