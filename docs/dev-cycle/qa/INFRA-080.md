# [INFRA-080] Next rewrite 프록시가 gunicorn 요청을 ECONNRESET 으로 잃고 500 을 낸다 — QA 시나리오

- 대상 화면: http://localhost:58120/dashboard/kr/closing-bet · /dashboard/kr/vcp · /chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[INFRA-080]` 의 QA 줄 + spike 실측(기본 keep-alive 2초에서 유휴 1.9~2.2초 무작위 요청 480건 중 12건 500) + 설계 승인(`restart_all.sh` 의 gunicorn 에 `--keep-alive 0`) + 코드 리뷰 요청 항목(SSE 스트림 부작용)
- 구성 2026-09-23 22:20 | 실행 2026-09-23 22:23~22:30 (1회차)
- 검증 기준 커밋: `4c4115a` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 대시보드 화면이므로 브라우저 실측을 필수로 둔다. `git archive HEAD` 사본에 원본 `data/` 와
  `frontend/node_modules` 를 APFS clone 으로 두고 `.env` 계열은 두지 않는다. gunicorn 은 `restart_all.sh` 와 같은 인자
  (`--workers 2 --threads 8 --timeout 120 --keep-alive 0`)에 S-1 의 연결 종료를 세기 위한 `--log-level debug` 만 더해 띄운다. `restart_all.sh` 자체는 의존성 동기화와 원본 PID·로그 경로를
  쓰므로 격리 실행에 쓰지 않는다. 챗봇 확인용으로 사본에만 `qa_flask_app.py` 를 두어 `engine.genai_client.build_genai_client` 를
  가짜 클라이언트(1초 간격 다섯 청크)로 바꾼다. gunicorn(`SCHEDULER_ENABLED=false`, 쿼터 가드용 더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·
  `GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다. 원본 `data/`·3500·5501·운영 주소는 건드리지 않는다.
  브라우저는 gstack `browse`, 익명 사용자로 쓴다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 코드 리뷰 재판정(APPROVE) 의 low 지적에 따라 `--log-level debug` 를 구성에 명시했다
- baseline 상태: 고치기 전 동작은 spike 에서 관측했다(`docs/dev-cycle/TODO.md` 의 `[INFRA-080]` 재현 줄). 텍스트 단언 RED 1건
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄 · 스크린샷 `docs/dev-cycle/evidence/INFRA-080/infra080-s2-{closing-bet,vcp}.png`·`infra080-s3-chatbot.png`(열어서 확인) · `s2-network-summary.txt`(browse network 의 /api 상태 분포) · `s3-flask-quota.txt`(익명 키는 `anon_…` 로 가림) · `/_next/mcp` 응답 · 전체 `pytest -q -p no:cacheprovider` 2722 passed 2 skipped(exit 0)
- 정리(cleanup): 격리 gunicorn(58121)·Next(58120) 종료(리스너 0, 사본 경로 프로세스 0), browse 서버 정지, 사본·래퍼·`qa_flask_app.py` 삭제(사본에만 있었음). 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. 유휴 2초 경계의 동시 요청이 500 없이 끝난다 (결함 재현, 하네스)
- 조작: keep-alive 로 연결을 유지하는 클라이언트 6개가 `/api/kr/market-gate`·`/api/kr/signals`·`/api/kr/signals/status` 를 Next(58120)로
  동시에 보내고, 라운드 사이에 1.9~2.2초를 무작위로 쉰다. 80라운드(요청 480건)를 돈다. 이어서 0~0.3초 간격으로 80라운드를 돈다.
- 기대: 두 실행 모두 200 이 아닌 응답 0건. Next 로그의 `Failed to proxy` 증가 0건. gunicorn 기동 인자에 `--keep-alive 0` 이 있고,
  gunicorn 디버그 로그의 `Closing connection` 수가 처리한 GET 수와 같다(요청마다 연결을 닫음).
- 필수 여부(required): 예
- 실제: 22:23:30~22:26:32. 1.9~2.2초 80라운드 `requests=480 non200=0`, 0~0.3초 80라운드 `requests=480 non200=0`. Next 로그 `Failed to proxy` 0건. gunicorn 설정 덤프 `keepalive: 0`·`workers: 2`·`threads: 8`, 마스터 프로세스 인자에 `--keep-alive 0`. 이 구간 gunicorn 디버그 로그의 GET 960건·`Closing connection` 960건. 같은 하네스가 고치기 전(spike, 기본 keep-alive)에는 1.9~2.2초 480건 중 12건 500 이었다
- 결과: 통과
- 증거: 위 「실제」 줄(하네스 출력 원문)
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 유휴 뒤 종가베팅·VCP 화면을 거듭 열어도 5xx 가 없다 (사용자 흐름)
- 조작: 브라우저로 `/dashboard/kr/closing-bet` 을 열고 요청이 끝난 뒤 2초 안팎을 쉬고 `/dashboard/kr/vcp` 를 연다. 이 왕복을 10회 한다.
  마지막에 각 화면을 한 번씩 스크린샷으로 남긴다.
- 기대: 브라우저 네트워크 기록에 `/api/` 5xx 0건, 콘솔 오류 0건. Next 로그의 `Failed to proxy` 증가 0건. 화면에 데이터가 표시된다.
  리뷰 발견 3 확인: Next 를 거친 `/api/kr/market-gate` 응답 헤더에 `Connection: close` 가 실리는지 기록한다(비용 기록용, 통과 판정과 무관).
- 필수 여부(required): 예
- 실제: 22:26:44~22:27:43 왕복 10회. browse network 의 `/api/` 요청 180건이 모두 `→ 200`(market-gate·signals·signals/status·jongga-v2/latest·jongga-v2/dates·ai-analysis·user/quota 각 20, auth/session 40). `console --errors` → `(no console errors)`. Next 로그 `Failed to proxy` 증가 0건. 두 화면은 틀과 값을 그렸으나 종가베팅 「NO DATA」·「분석된 종목이 없습니다」, VCP 「No signals found」다. Flask 직접 응답이 `signals` 는 `source: no_data, count 0`, `jongga-v2/latest` 는 `status: no_data` 이므로 원본 `data/` 에 오늘 자료가 없어 생긴 빈 상태이며 화면이 API 응답과 일치한다. 기대의 「데이터가 표시된다」는 이 자료로 확인할 수 없었다. 이 항목의 판정 근거(5xx 0·`Failed to proxy` 0)와는 별개로 적어 둔다. 리뷰 발견 3: Next 를 거친 `/api/kr/market-gate` 응답이 `HTTP/1.1 200 OK`·`connection: close` 로, 브라우저와 Next 사이 연결도 응답마다 닫힘을 확인했다
- 결과: 통과
- 증거: 위 「실제」 줄, `infra080-s2-closing-bet.png`, `infra080-s2-vcp.png`, `s2-network-summary.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 챗봇 SSE 스트림이 끝까지 오고 무료 횟수가 1 차감된다 (인접 회귀)
- 조작: `/chatbot` 에서 사이드바의 「N회 남음」 을 읽고 「안녕」 을 보낸다. 답변이 끝나면 다시 읽는다.
- 기대: `조각0` 부터 `조각4` 까지 차례로 나타나고 오류 말풍선이 없다. 「N회 남음」 이 1 줄어든다. Flask 로그에
  `closed by client disconnect` 가 없고 `사용량 차감 완료` 가 있다.
- 필수 여부(required): 예
- 실제: 「10회 남음」 → 22:28:32 「안녕」 전송 → 본문 `조각0,조각1,조각2,조각3,조각4`, 오류 문구 없음 → 다시 연 뒤 「9회 남음」. Flask 22:28:37 `[QUOTA] use_free_tier=True, stream_has_error=False` → `사용량 차감 완료 … -> 1회`, `closed by client disconnect` 없음. 「차례로」 는 충족하지 못했다: 페이지 안 MutationObserver 로 잰 새 청크 수는 `[[70,5],[5141,10]]`(직전 대화의 5개 위에 새 5개가 전송 뒤 5.1초에 한꺼번에 나타남). 같은 측정을 gunicorn 기본 keep-alive(2초)로 다시 띄워 반복하니 `[[83,0],[5122,5]]` 로 같았다. 고치기 전에도 같은 동작이므로 이번 변경의 회귀가 아니며 인접 회귀 판정은 통과로 둔다. 원인은 범위 밖 발견으로 `[CHAT-042]` 에 이월. 이후 `[CHAT-042]` spike 가 원인을 하네스로 확정했다: 가짜 응답 전체가 「조각0,」~「조각4,」 20자였고, `chatbot/response_flow_stream.py` 가 답변 머리표를 보기 전에는 마지막 20자(`_STREAM_HEADER_TAIL_GUARD`)를 다음 청크까지 붙잡으므로 끝까지 나가지 못했다. 청크를 30자 넘게 하거나 `[답변]` 을 붙이면 Flask·Next·화면 모두 1초 간격이었다
- 결과: 통과
- 증거: 위 「실제」 줄, `infra080-s3-chatbot.png`(청크 시각을 재려고 22:29:46 에 한 번 더 보낸 뒤의 최종 화면이라 두 답변과 「8회 남음」 이 보인다. 두 번째 차감도 `s3-flask-quota.txt` 끝 두 줄에 있다), `s3-flask-quota.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보낸다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건.
- 필수 여부(required): 예
- 실제: `get_compilation_issues` → `{"issues":[]}`, `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. 챗봇 뒤 `console --errors` → `(no console errors)`. Next 로그의 `Failed to proxy` 전체 0건
- 결과: 통과
- 증거: 위 「실제」 줄
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 실행 결과

- 1회차(2026-09-23 22:23~22:30, 기준 `4c4115a`): 필수 4/4 통과. S-2 의 「데이터 표시」 는 원본 자료가 `no_data` 라 확인하지 못했고, S-3 의 「차례로」 는 고치기 전과 같은 동작이라 회귀가 아니다. 두 점을 판정과 분리해 각 「실제」 줄에 적었다
- 이월한 발견: `[CHAT-042]` 챗봇 스트림 청크가 끝에 한꺼번에 나타난다(기본 keep-alive 에서도 같음)
