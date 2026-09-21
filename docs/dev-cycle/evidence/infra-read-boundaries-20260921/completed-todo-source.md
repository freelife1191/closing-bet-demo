# 완료 전 원본 항목

### [INFRA-045] 감사 로그의 IP 를 요청자가 헤더 한 줄로 정할 수 있다
- 진행: 2026-09-21 조회·감사 경계 T3 묶음. 사용자 「승인도 알아서 진행하고 완료」 위임에 따라 리더 설계·계획 결정, 독립 critic ACCEPT. `evidence/infra-read-boundaries-20260921/design.md`, `plan.md`. 구현 및 격리 검증 진행 중.
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-039]` 사이클의
  `oh-my-claudecode:critic` 지적(확신도 높음). 실측으로 확인했습니다.
- Next.js 16.3.4 는 `frontend/node_modules/next/dist/server/base-server.js:612` 에서
  `req.headers['x-forwarded-for'] ??= originalRequest?.socket?.remoteAddress` 로 헤더를
  붙입니다. **`??=` 이므로 클라이언트가 보낸 값을 덮어쓰지 않습니다.** 브라우저가
  `X-Forwarded-For: 203.0.113.9` 를 보내면 그 값이 그대로 감사 기록에 남습니다.
- `POST /api/system/log-event` 로 실측한 결과입니다. 헤더 없이 Next 를 거치면
  `::ffff:127.0.0.1`, 위조 헤더를 붙이면 `203.0.113.9`, Flask 에 직접 보내면
  `198.51.100.4` 가 기록되었습니다.
- 같은 패턴이 세 자리에 있습니다. `app/__init__.py:207` 의 `_resolve_real_ip`,
  `app/routes/common_update_routes.py:97` 의 `_resolve_request_ip`,
  `services/kr_market_chatbot_request_helpers.py:212` 의 `extract_chatbot_client_ip`
  입니다. 세 번째는 챗봇 대화 로그, 두 번째는 `/api/system/log-event` 의 IP 입니다.
- **`ProxyFix(app.wsgi_app, x_for=1)` 로는 막지 못합니다.** 위조 값이 이미 헤더에 들어
  있으므로 홉 수를 세는 것으로는 걸러지지 않습니다.
- **`proxy.ts` 에서는 헤더를 지울 수는 있어도 다시 쓸 수는 없습니다.** Next 15 에서
  `request.ip` 가 사라졌고, proxy 는 `??=` 가 실행된 뒤에 돌아 이미 채워진 헤더만
  봅니다. 그 값이 클라이언트가 보낸 것인지 Next 가 붙인 것인지 구분할 방법이 없습니다.
  그러므로 proxy 에서 지우는 것은 Flask 에서 헤더를 안 읽는 것과 결과가 같고,
  「위조를 막으면서 진짜 IP 를 지키는」 길은 어느 쪽에도 없습니다.
- 그러므로 이 항목은 앞단 배포 구조를 먼저 정해야 합니다. Flask 앞에 신뢰할 수 있는
  리버스 프록시(nginx·Cloudflare 등)가 서는지, 아니면 Next 가 유일한 앞단인지에 따라
  답이 갈립니다. 전자면 그 프록시가 헤더를 다시 쓰고 `ProxyFix` 의 홉 수를 그에 맞춥니다.
  후자면 헤더를 버리고 `remote_addr` 만 쓰는 편이 정직합니다.
- `[INFRA-039]` 가 바인딩을 좁혀 Flask 직접 경로는 막혔습니다. 남은 것은 Next 경유
  위조이며, 그 경로로는 브라우저가 보낸 헤더가 그대로 통과합니다.
- 기존 테스트 `tests/app/test_common_routes_refactor.py:288` 의
  `assert captured["ip_address"] == "10.0.0.1"` 과
  `tests/app/test_kr_market_chatbot_service.py:483` 이 지금의 헤더 신뢰 동작을 못 박고
  있습니다. 방향을 바꾸면 이 둘도 함께 고쳐야 합니다.
- QA 시나리오: 브라우저 개발자 도구로 `X-Forwarded-For` 를 붙여 요청해도 감사 로그에
  그 값이 남지 않는다
- [ ] 앞단 배포 구조를 확인해 헤더를 신뢰할지 버릴지 결정
- [ ] 세 자리를 그 결정에 맞춤 (한 자리만 고치지 않는다)
- [ ] 기존 테스트 두 건을 새 계약에 맞게 고침
- [ ] 감사 로그의 IP 가 무엇을 뜻하는지 코드 주석에 적음

- 이전 상태 (2026-09-09): 실제 앞단 프록시 구성·Procfile 기반 PaaS 사용 계획 정보 대기. 사용자의 연속 진행 요청에 따라 독립적으로 처리 가능한 INFRA-017·038을 먼저 완료했으며, 이 항목의 배포 정책은 아직 변경하지 않았다.

### [INFRA-046] `Procfile` 이 지금 아키텍처에서 동작하지 않는 배포 방식을 남겨 둔다
- 진행: 2026-09-21 조회·감사 경계 T3 묶음. 사용자 「승인도 알아서 진행하고 완료」 위임에 따라 리더 설계·계획 결정, 독립 critic ACCEPT. `evidence/infra-read-boundaries-20260921/design.md`, `plan.md`. 구현 및 격리 검증 진행 중.
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-039]` 사이클의
  `oh-my-claudecode:security-reviewer` 지적(심각도 중, 확신도 높음). 파일을 열어 확인했습니다.
- `Procfile` 은 `web: gunicorn flask_app:app` 한 줄이며 **Flask 만 띄웁니다.** Next.js 를
  띄우는 줄이 없습니다.
- 그런데 `[INFRA-027]` 이후 신원 확정은 `frontend/src/proxy.ts` 가 맡습니다. proxy 가 없으면
  `X-Auth-Identity` 를 붙이는 자리가 없어 **모든 요청이 익명으로 처리됩니다.** 챗봇 소유자
  판정과 AI 분석, `[INFRA-037]` 이 세운 관리자 알림 게이트가 전부 막힙니다.
- 동시에 PaaS 라우터가 그 프로세스를 인터넷에 공개하므로 Flask 가 직접 노출됩니다.
  `[INFRA-039]` 가 다른 자리를 loopback 으로 좁힐 때 이 파일만 `0.0.0.0` 을 남긴 이유가
  그 노출이며, 그래서 「앞단에서 이 포트를 막는다」는 지시가 성립하지 않습니다. 그 포트가
  곧 서비스 포트이기 때문입니다.
- 저장소에 PaaS 설정 파일(`app.json`·`render.yaml`·`fly.toml`·`Dockerfile` 등)이 하나도
  없고, `Procfile` 은 2026-02-03 「Deployment Ready」 커밋 한 번으로 들어온 뒤 손대지
  않았으며 어느 문서에도 언급이 없습니다. 실제로 쓰이는 경로가 아닐 가능성이 높습니다.
- `[INFRA-039]` 는 이 파일에 「이 경로로 배포하지 않는다」는 주석을 달아 두었습니다.
  주석은 임시 조치이며 파일 자체의 처리를 정해야 합니다.
- 선택지는 셋입니다. (가) 파일을 지웁니다. 쓰이지 않는 것이 확인되면 가장 정직합니다.
  (나) Next 와 Flask 를 함께 띄우도록 고칩니다. 그러려면 프로세스 두 개와 그 사이의
  loopback 연결을 정의해야 합니다. (다) 지금처럼 주석만 두고 남깁니다.
- 어느 쪽이든 실제 배포 계획을 먼저 확인해야 합니다.
- [ ] 이 저장소가 PaaS 배포를 쓸 계획이 있는지 확인
- [ ] 그 답에 따라 파일을 지우거나 두 프로세스로 고침
- [ ] `services/identity_helpers.py` 와 `.env.example` 의 `Procfile` 언급을 결과에 맞춤

- 이전 상태 (2026-09-09): 실제 앞단 프록시 구성·Procfile 기반 PaaS 사용 계획 정보 대기. 사용자의 연속 진행 요청에 따라 독립적으로 처리 가능한 INFRA-017·038을 먼저 완료했으며, 이 항목의 배포 정책은 아직 변경하지 않았다.

### [INFRA-047] 조회용 GET 라우트 둘이 백그라운드 작업과 외부 호출을 일으킨다
- 진행: 2026-09-21 조회·감사 경계 T3 묶음. 사용자 「승인도 알아서 진행하고 완료」 위임에 따라 리더 설계·계획 결정, 독립 critic ACCEPT. `evidence/infra-read-boundaries-20260921/design.md`, `plan.md`. 구현 및 격리 검증 진행 중.
- 카테고리: 인프라 | 티어: T2 | 근거: 2026-09-07 `[INFRA-040]` 사이클에서 「상태를 바꾸는
  GET 라우트가 없는지 전수 확인」을 하다 찾았습니다. `oh-my-claudecode:security-reviewer` 도
  같은 판정을 냈습니다(확신도 높음).
- `app/routes/common_portfolio_routes.py:61` 의 `GET /api/portfolio` 가
  `paper_trading.start_background_sync()` 를 부릅니다. 조회 한 번이 동기화 스레드를 띄웁니다.
- `app/routes/kr_market_system_http_routes.py:83` 의 `GET /api/kr/market-gate` 는 자료가
  낡았으면 `trigger_market_gate_background_refresh()` 로 분석 스레드를 띄웁니다
  (`app/routes/kr_market.py:270`). 외부 API 호출과 파일 쓰기가 따라옵니다.
- **CSRF 는 아닙니다.** 둘 다 요청자의 신원을 보지 않으므로 공격자가 자기 브라우저에서
  직접 불러도 결과가 같고 피해자의 쿠키가 필요하지 않습니다. 그래서 `[INFRA-040]` 의
  차단 대상이 아니었습니다.
- 문제는 다른 데 있습니다. 조회 요청이 비용과 부작용을 내면 캐시·프리페치·크롤러가 그것을
  일으킵니다. 브라우저가 링크를 미리 가져오기만 해도 분석이 돌 수 있습니다.
- QA 시나리오: `GET /api/kr/market-gate` 를 연달아 불러도 분석 스레드가 새로 뜨지 않는다
- [ ] 두 라우트의 갱신 트리거를 조회에서 떼어낼지, 아니면 별도 POST 로 옮길지 정함
- [ ] 프론트엔드에서 그 갱신을 부르던 자리를 찾아 함께 고침
- [ ] 갱신이 조회로 일어나지 않는 것을 고정하는 검사 추가
