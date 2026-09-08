# INFRA-062 신원 서명 요청 결합 설계

- 승인: 2026-09-08 현재 대화에서 메서드·경로 결합, 구형 서명 거부, Next/Flask 동시 수정과 T3/UltraQA 설계를 제안한 뒤 사용자 「진행해」 응답.
- 목표: 다른 API 경로 또는 HTTP 메서드로 옮긴 서명을 인증된 신원으로 받아들이지 않는다.
- 분류: architectural/T3. 기존 HMAC-SHA256·120초 TTL·NextAuth·익명 ID 규칙을 유지한다.

## Wire contract

헤더는 `v2.<base64url(email), no padding>.<expiry integer>.<lowercase hex mac>`다.
MAC 입력은 UTF-8 `v2.<encoded_email>.<expiry>.<UPPERCASE_METHOD>.<base64url(decoded_path_utf8), no padding>`다.
메서드와 경로는 헤더에서 신뢰하지 않고 실제 요청에서 얻는다. Python verifier는 필수 keyword-only `method: str, path: str`를 받으며 `now` 테스트 인자는 유지한다. TS signer는 `(email, secret, expiresAt, method, path)`를 받는다.

경로 계약은 Flask `request.path`와 같은, percent decoding을 한 번 적용한 URL pathname이며 `/api/` 접두사와 trailing slash를 보존한다. query·fragment는 포함하지 않는다. Next proxy는 `decodeURIComponent(request.nextUrl.pathname)`를 사용한다. 잘못된 percent/UTF-8은 일반 400으로 거부하고 인증된 요청으로 보내지 않는다. hostname·scheme·사용자가 보낸 path/identity 헤더는 서명 대상의 근거가 아니다. 이중 인코딩을 다시 decode하거나 path를 임의로 축약하지 않는다.

구형 3-part 형식과 알 수 없는 버전은 거부한다. 검증 실패는 기존처럼 None이며 보호된 경로의 기존 401/403 게이트가 이를 처리한다. public/anonymous 정책과 OPTIONS 처리, CSRF 검사는 그대로 유지한다. 동일 method/path의 재전송과 query/body 변경 방어는 이 범위에 포함하지 않는다. nonce 저장소는 추가하지 않는다.

## 연결과 영향

`frontend/src/lib/identity.ts`와 `frontend/src/proxy.ts`에서 생성한다. `services/identity_helpers.py`에서 검증하고 `app/__init__.py`와 `app/routes/common_portfolio_routes.py`가 실제 method/path를 전달한다. 일반 권한/챗봇/쿼터는 중앙 g.user_email, 포트폴리오는 직접 verifier 경로를 계속 사용한다. 새 auth 계층이나 DB를 추가하지 않는다.

직접 HMAC을 만드는 테스트 7곳(identity helper, identity gate, portfolio owner/refactor, admin gated, notification gate, verify_portfolio_api)과 frontend identity/proxy 테스트를 함께 바꾼다. 사용자 신원을 직접 심는 route 테스트는 인증 E2E 증거로 세지 않는다. 역사적 설계/아카이브는 소급 수정하지 않고 현행 CLAUDE/README/관련 주석을 갱신한다.

## 검증과 안전

먼저 구형 서명 재생 회귀 RED를 확인한다. 고정 cross-language vectors와 TypeScript 생성→Python 검증을 실제 실행하며 정상/다른 path/다른 method/위조/만료/구형/잘못된 Unicode·percent/HEAD·OPTIONS/trailing slash/double encoding을 검사한다. 실제 Next proxy→rewrite→bare Flask probe를 별도 loopback 포트·합성 JWT·가짜 secret으로 실행해 transport path 차이도 확인한다. probe는 요청별 검증 결과와 부수효과 카운터만 반환하며 발송/LLM/DB에 연결하지 않는다.

원본 `.env`/`data`, 원본 Next3500/Flask5501/live 및 외부 요청은 금지한다. 독립 clone develop과 복사한 Node 의존성·기존 venv 인터프리터에서 테스트한다. 원본 package.json은 hash로 보존한다. 운영 배포/재기동·키 회전은 하지 않는다. 구형/신형 혼용 중 로그인 기능이 실패하므로 향후 Next/Flask를 함께 적용해야 한다.

T3: critic → 구현 → ponytail → 독립 code/security + architect → deep review → 전체 pytest/vitest/typecheck/lint → 첫 구현/QA 행렬 커밋(TODO 유지) → UltraQA App 동적 검증/정리 → QA 증거 커밋 → 원본 fast-forward/clone 정리 → 완료 아카이브. 필수 미통과는 완료하지 않는다.

## 실제 전송 경로의 기대값

probe는 운영 endpoint가 아닌 `/api/__identity_probe/<path>`를 bare Flask에서 처리한다. CLI `http.client`로 원문 target을 보내 percent를 자동 재인코딩하지 않으며 redirect를 자동 추종하지 않는다. 응답은 검증 이메일·관측 method/path·부수효과 카운터만 담고 서명/secret은 포함하지 않는다. 전달된 서명은 같은 테스트 프로세스의 Flask 메모리에서만 읽어 재생 요청에 사용한다.

| Raw target | Next pathname | 서명에 넣는 decoded path | Flask request.path | HTTP/Flask hit |
|---|---|---|---|---|
| `/api/__identity_probe/a` | 동일 | 동일 | 동일 | 200, 1회 |
| `/api/__identity_probe/a%2Fb` | raw 그대로 | `/api/__identity_probe/a/b` | 같은 decoded path | 200, 1회 |
| `/api/__identity_probe/%252F` | raw 그대로 | `/api/__identity_probe/%2F` | 같은 decoded path | 200, 1회 |
| `/api/__identity_probe/%ED%95%9C%EA%B8%80` | raw 그대로 | `/api/__identity_probe/한글` | 같은 decoded path | 200, 1회 |
| `/api/__identity_probe/tail/` | redirect 전 raw pathname | utility에서는 slash 보존 | 첫 요청은 도달 안 함 | 308 Location `/api/__identity_probe/tail`, 0회 |
| redirect 목적지 `/api/__identity_probe/tail` | 동일 | 동일 | 동일 | 새 서명으로 200, 1회 |
| `/api/__identity_probe/%`, `/api/__identity_probe/%ZZ`, `/api/__identity_probe/%FF` | 생성/파싱 가능 여부와 무관 | 잘못된 percent/UTF8 거부 | 도달 안 함 | 실제 raw HTTP 400, 0회 |

trailing slash redirect는 설치된 Next `trailingSlash.md`의 기본 동작을 유지하며 전역 설정을 바꾸지 않는다. 순수 signer/verifier 시험에서는 `/tail`과 `/tail/`가 다른 서명임을 별도로 검사한다. Next가 proxy 이전에 malformed target을 400으로 거부해도 성공 기준은 동일하며, 도달하지 않은 함수가 실행됐다고 보고하지 않는다. OPTIONS 무서명204/부수효과0, HEAD 자체메서드 서명, GET→POST·A→B 재생401/부수효과0도 실제 transport로 확인한다.
