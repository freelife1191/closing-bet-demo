# [INFRA-037] `/api/notification/send` 관리자 게이트 — QA 시나리오

- 대상: `http://127.0.0.1:5501`(Flask 직접)과 `http://localhost:3500`(Next 경유) 두 경로
- 구성 근거: 이번 사이클의 변경 두 파일과 `[INFRA-027]` 이 세운 신원 서명 경로,
  그리고 이 라운드의 과잉설계·코드·보안 리뷰 지적
- 구성 2026-09-07 20:1x | 실행 (미기재)
- QA 엔진(engine): Claude Code — 시나리오 구성과 실행을 같은 문맥에서 이어감
- 단계(phase): 시나리오 구성 완료 | 실행 (미기재)
- 반복(iteration): (미기재)
- baseline 상태: (미기재)
- 필수 여부(required): 예
- 결과: (미기재)
- 증거: (미기재)
- 정리(cleanup): (미기재)

## 실측 방법에 관한 세 가지 사전 결정

**1. 실제 발송은 한 번도 일으키지 않는다.** 이 세션은 알림 테스트 발송을 실행하지
않기로 했고, `.env` 에는 디스코드 웹훅·텔레그램 봇 토큰·SMTP 계정이 모두 실제 값으로
설정되어 있다. 그래서 게이트를 **통과하는** 시나리오는 존재하지 않는 플랫폼 이름
(`carrier-pigeon`)을 보낸다. 게이트를 지나면 `400 Unknown platform` 이 나오고, 그것이
「게이트를 통과해 페이로드 검증까지 갔다」는 증거가 되면서 발송은 시작되지 않는다.
발송 직전 단계까지 갔음은 `tests/app/test_common_routes_refactor.py` 의 가짜 Messenger
테스트가 따로 고정한다.

**2. Google 로그인 대신 세션 쿠키를 직접 만든다.** 이 세션은 사용자 자격 증명을 다루지
않는다. `[INFRA-027]` 의 QA 와 같은 방법으로 `next-auth/jwt` 의 `encode` 에
`NEXTAUTH_SECRET` 을 주어 세션 토큰을 만들고 쿠키로 싣는다. proxy 가 보는 것은
`getToken()` 의 반환값이라 실제 로그인과 구분되지 않는다.

**3. 비밀과 관리자 이메일은 어디에도 출력하지 않는다.** 서명 생성은 스크래치패드의
스크립트가 `.env` 에서 값을 읽어 처리하고, 이 문서에는 이메일을 `<관리자>` 로 적는다.

## 시나리오

### S-1. 신원 서명 없는 요청이 막힌다 (회귀 · 이 라운드의 핵심)
- 조작: `curl -s -o - -w '\n%{http_code}' -X POST http://127.0.0.1:5501/api/notification/send
  -H 'Content-Type: application/json' -d '{"platform":"discord"}'`
- 기대: `403` 과 `{"status":"error","message":"Forbidden"}`. `logs/backend.log` 에
  디스코드 발송 시도 흔적이 남지 않는다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-2. 위조한 신원 서명이 막힌다 (회귀)
- 조작: S-1 에 `-H 'X-Auth-Identity: YWRtaW5AZXhhbXBsZS5jb20.4000000000.deadbeef'` 를 더한다.
- 기대: `403` 과 `Forbidden`. HMAC 이 맞지 않으므로 신원이 서지 않는다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-3. 종전의 `X-User-Email` 로는 관리자가 되지 못한다 (회귀)
- 조작: S-1 에 `-H 'X-User-Email: <관리자>'` 를 더한다.
- 기대: `403` 과 `Forbidden`. 이 헤더는 `[INFRA-027]` 이후 신원이 아니다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-4. 관리자가 아닌 유효한 신원이 막힌다 (회귀)
- 조작: `ADMIN_EMAILS` 에 없는 주소로 만든 유효 서명을 붙여 S-1 을 반복한다.
- 기대: `403` 과 `Forbidden`. 서명이 유효해도 관리자 목록 밖이면 통과하지 못한다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-5. 관리자 신원은 게이트를 통과한다 (회귀 · 발송은 일으키지 않음)
- 조작: `<관리자>` 로 만든 유효 서명을 붙이고 `{"platform":"carrier-pigeon"}` 을 보낸다.
- 기대: `400` 과 `{"status":"error","message":"Unknown platform: carrier-pigeon"}`.
  403 이 아니라 400 이라는 것이 게이트를 지나 페이로드 검증까지 갔다는 증거다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-6. 게이트가 페이로드 검증보다 먼저 선다 (회귀)
- 조작: 신원 없이 `{}` 를 보낸다.
- 기대: `403` 과 `Forbidden`. `400 Platform not specified` 가 나오면 게이트 밖에서
  어떤 페이로드가 유효한지 떠볼 수 있다는 뜻이다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-7. 같은 blueprint 의 다른 라우트가 영향받지 않는다 (인접)
- 조작: 신원 없이 `GET /api/system/update-status` 와 `GET /api/admin/check?email=<관리자>` 를 부른다.
- 기대: 둘 다 종전처럼 `200`. 이번 게이트는 알림 발송 라우트에만 걸린다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-8. Next 를 거친 관리자 세션이 게이트를 통과한다 (인접 · 통합 경로)
- 조작: `<관리자>` 이메일로 만든 NextAuth 세션 쿠키를 실어
  `POST http://localhost:3500/api/notification/send` 에 `{"platform":"carrier-pigeon"}` 을 보낸다.
- 기대: `400 Unknown platform`. proxy 가 서명을 붙이고 Flask 가 관리자로 인정했다는 뜻이다.
  여기서 403 이 나오면 게이트가 실제 관리자까지 막아 화면의 알림 테스트가 죽는다.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

### S-9. Next 를 거친 익명 요청이 막힌다 (인접 · 통합 경로)
- 조작: 쿠키 없이 S-8 과 같은 요청을 보낸다.
- 기대: `403` 과 `Forbidden`.
- 필수 여부(required): 예
- 실제: (미기재)
- 결과: (미기재)

## 이월한 발견

(실행 후 기재)

## 실행 결과

(실행 후 기재)
