# [INFRA-037] `/api/notification/send` 관리자 게이트 — QA 시나리오

- 대상: `http://127.0.0.1:5501`(Flask 직접)과 `http://localhost:3500`(Next 경유) 두 경로
- 구성 근거: 이번 사이클의 변경 두 파일과 `[INFRA-027]` 이 세운 신원 서명 경로,
  그리고 이 라운드의 과잉설계·코드·보안 리뷰 지적
- 구성 2026-09-07 20:08 | 실행 2026-09-07 20:14
- 검증 기준 커밋: `b34a4ac` (서버를 이 커밋으로 재기동한 뒤 실행)
- QA 엔진(engine): Claude Code — 시나리오 구성과 실행을 같은 문맥에서 이어감
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 기준값 수집 완료 (게이트 도입 전 동작은 pytest 로 확인)
- 필수 여부(required): 예
- 결과: 필수 9/9 통과
- 증거: 아래 각 시나리오의 실제 응답. 발송이 한 건도 일어나지 않았음은
  `logs/backend.log` 에 발송 관련 줄이 0개인 것과, 게이트를 통과한 두 시나리오가
  플랫폼 판정에서 400 으로 끊긴 것으로 확인했다.
- 정리(cleanup): 임시 스크립트 `frontend/__infra037_qa.cjs` 실행 직후 삭제 완료
  (`git status` 에 남지 않음). `data/` 미변경. 서명 생성기는 스크래치패드에만 둠

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
- 실제: `403` 과 `{"message": "Forbidden", "status": "error"}`. 로그에 발송 흔적 없음
- 결과: **통과**

### S-2. 위조한 신원 서명이 막힌다 (회귀)
- 조작: S-1 에 `-H 'X-Auth-Identity: YWRtaW5AZXhhbXBsZS5jb20.4000000000.deadbeef'` 를 더한다.
- 기대: `403` 과 `Forbidden`. HMAC 이 맞지 않으므로 신원이 서지 않는다.
- 필수 여부(required): 예
- 실제: `403` 과 같은 본문. HMAC 이 맞지 않아 신원이 서지 않았다
- 결과: **통과**

### S-3. 종전의 `X-User-Email` 로는 관리자가 되지 못한다 (회귀)
- 조작: S-1 에 `-H 'X-User-Email: <관리자>'` 를 더한다.
- 기대: `403` 과 `Forbidden`. 이 헤더는 `[INFRA-027]` 이후 신원이 아니다.
- 필수 여부(required): 예
- 실제: `403` 과 같은 본문. 관리자 이메일을 그대로 넣어도 신원이 되지 못했다
- 결과: **통과**

### S-4. 관리자가 아닌 유효한 신원이 막힌다 (회귀)
- 조작: `ADMIN_EMAILS` 에 없는 주소로 만든 유효 서명을 붙여 S-1 을 반복한다.
- 기대: `403` 과 `Forbidden`. 서명이 유효해도 관리자 목록 밖이면 통과하지 못한다.
- 필수 여부(required): 예
- 실제: `403` 과 같은 본문. 유효한 서명이지만 `ADMIN_EMAILS` 밖이라 막혔다
- 결과: **통과**

### S-5. 관리자 신원은 게이트를 통과한다 (회귀 · 발송은 일으키지 않음)
- 조작: `<관리자>` 로 만든 유효 서명을 붙이고 `{"platform":"carrier-pigeon"}` 을 보낸다.
- 기대: `400` 과 `{"status":"error","message":"Unknown platform: carrier-pigeon"}`.
  403 이 아니라 400 이라는 것이 게이트를 지나 페이로드 검증까지 갔다는 증거다.
- 필수 여부(required): 예
- 실제: `400` 과 `{"message": "Unknown platform: carrier-pigeon", "status": "error"}`.
  403 이 아니므로 게이트를 지났고, 400 이므로 발송은 시작되지 않았다
- 결과: **통과**

### S-6. 게이트가 페이로드 검증보다 먼저 선다 (회귀)
- 조작: 신원 없이 `{}` 를 보낸다.
- 기대: `403` 과 `Forbidden`. `400 Platform not specified` 가 나오면 게이트 밖에서
  어떤 페이로드가 유효한지 떠볼 수 있다는 뜻이다.
- 필수 여부(required): 예
- 실제: `403` 과 `Forbidden`. `Platform not specified` 가 아니므로 게이트가 먼저 선다
- 결과: **통과**

### S-7. 같은 blueprint 의 다른 라우트가 영향받지 않는다 (인접)
- 조작: 신원 없이 `GET /api/system/update-status` 와 `GET /api/admin/check?email=<관리자>` 를 부른다.
- 기대: 둘 다 종전처럼 `200`. 이번 게이트는 알림 발송 라우트에만 걸린다.
- 필수 여부(required): 예
- 실제: `GET /api/system/update-status` 가 `200`, `GET /api/admin/check?email=<관리자>` 가
  `200` 과 `{"isAdmin": true}`. 이번 게이트는 알림 발송 라우트에만 걸린다
- 결과: **통과**

### S-8. Next 를 거친 관리자 세션이 게이트를 통과한다 (인접 · 통합 경로)
- 조작: `<관리자>` 이메일로 만든 NextAuth 세션 쿠키를 실어
  `POST http://localhost:3500/api/notification/send` 에 `{"platform":"carrier-pigeon"}` 을 보낸다.
- 기대: `400 Unknown platform`. proxy 가 서명을 붙이고 Flask 가 관리자로 인정했다는 뜻이다.
  여기서 403 이 나오면 게이트가 실제 관리자까지 막아 화면의 알림 테스트가 죽는다.
- 필수 여부(required): 예
- 실제: `400` 과 `Unknown platform: carrier-pigeon`. proxy 가 세션 쿠키에서 서명을 만들어
  붙였고 Flask 가 관리자로 인정했다. 관리자의 알림 테스트가 죽지 않는다
- 결과: **통과**

### S-9. Next 를 거친 익명 요청이 막힌다 (인접 · 통합 경로)
- 조작: 쿠키 없이 S-8 과 같은 요청을 보낸다.
- 기대: `403` 과 `Forbidden`.
- 필수 여부(required): 예
- 실제: `403` 과 `Forbidden`
- 결과: **통과**

## 이월한 발견

시나리오 실행이 아니라 이 라운드의 리뷰가 찾은 것이며, 모두 이번 범위 밖이다.

- `[INFRA-042]` — `/api/kr/jongga-v2/message` 와 `/run` 이 같은 자격 증명·같은 채널로
  권한 검사 없이 발송한다. 두 리뷰가 각각 확신도 높음으로 지적했다. 이 항목이 닫은 것은
  `/api/notification/send` 하나뿐이므로 위협 자체는 아직 열려 있다.
- `[INFRA-043]` — `engine/messenger_senders.py:66`·`:92` 의 예외 로그가 텔레그램 봇 토큰과
  디스코드 웹훅을 그대로 적을 수 있다. `NOTIFICATION_ENABLED=false` 가 이 경로를 덮지
  못한다는 지적과 발송 실패에도 `success` 가 나간다는 지적을 같은 항목에 담았다.
- `[INFRA-044]` — `POST /api/system/env` 가 인가 근거인 `ADMIN_EMAILS` 를 요청을 처리한
  워커의 `os.environ` 에만 쓰므로, 워커가 둘이면 같은 관리자의 같은 요청이 통과와 거부로
  갈릴 수 있다. 이번 변경이 그 값을 인가 근거로 만들면서 무게가 커졌다.
- `[INFRA-039]` 에 덧붙임 — `_resolve_real_ip` 의 `X-Forwarded-For` 무조건 신뢰(검토자는
  `ProxyFix(app.wsgi_app, x_for=1)` 를 제안했고, 신뢰 홉 수는 바인딩 결정과 같은 시점에
  정해야 한다고 했다), `.env.example` 의 `INTERNAL_IDENTITY_SECRET` 주석에 알림 테스트
  발송을 더할 것.

## 실행 결과

- 필수 시나리오: 통과 9 / 전체 9
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 없음

## 이 라운드에서 일어난 사고

코드 리뷰 에이전트가 경계 조건을 실측하다가 관리자 신원으로 `/api/notification/send` 를
통과시켜 **운영 디스코드 채널에 `[Test] DISCORD Notification` 한 건이 실제로 도착했다.**
검토자가 탐침 출력을 다시 열어 확인한 결과 다섯 번의 호출이 모두 discord 였고 200 이 난
것은 한 번이며, 실패했다면 찍혔을 `logger.error` 줄이 없었으므로 도달이 확정이다.
텔레그램과 이메일은 요청 자체가 없었다. 보안 리뷰 에이전트는 HTTP 요청을 한 번도 보내지
않았다(파일 읽기와 grep, pytest 한 번).

원인은 이 세션이 지키던 「알림 테스트 발송을 하지 않는다」 제약을 리뷰 프롬프트에 적지
않은 것이다. 위 시나리오가 `carrier-pigeon` 을 쓰는 이유가 여기에 있고, 두 에이전트에도
같은 방법을 전달했다. `NOTIFICATION_ENABLED=false` 로 이런 사고를 막으려 해도 지금
구조에서는 막히지 않으므로 `[INFRA-043]` 에 그 사실을 함께 적었다.
