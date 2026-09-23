# [INFRA-080] Next rewrite 프록시가 gunicorn 요청을 ECONNRESET 으로 잃고 500 을 낸다 — QA 시나리오

- 대상 화면: http://localhost:58120/dashboard/kr/closing-bet · /dashboard/kr/vcp · /chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[INFRA-080]` 의 QA 줄 + spike 실측(기본 keep-alive 2초에서 유휴 1.9~2.2초 무작위 요청 480건 중 12건 500) + 설계 승인(`restart_all.sh` 의 gunicorn 에 `--keep-alive 0`) + 코드 리뷰 요청 항목(SSE 스트림 부작용)
- 구성 2026-09-23 22:20 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기입)
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 대시보드 화면이므로 브라우저 실측을 필수로 둔다. `git archive HEAD` 사본에 원본 `data/` 와
  `frontend/node_modules` 를 APFS clone 으로 두고 `.env` 계열은 두지 않는다. gunicorn 은 `restart_all.sh` 와 같은 인자
  (`--workers 2 --threads 8 --timeout 120 --keep-alive 0`)에 S-1 의 연결 종료를 세기 위한 `--log-level debug` 만 더해 띄운다. `restart_all.sh` 자체는 의존성 동기화와 원본 PID·로그 경로를
  쓰므로 격리 실행에 쓰지 않는다. 챗봇 확인용으로 사본에만 `qa_flask_app.py` 를 두어 `engine.genai_client.build_genai_client` 를
  가짜 클라이언트(1초 간격 다섯 청크)로 바꾼다. gunicorn(`SCHEDULER_ENABLED=false`, 쿼터 가드용 더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·
  `GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다. 원본 `data/`·3500·5501·운영 주소는 건드리지 않는다.
  브라우저는 gstack `browse`, 익명 사용자로 쓴다
- 단계(phase): 시나리오 구성 완료
- 반복(iteration): 0회. 코드 리뷰 재판정(APPROVE) 의 low 지적에 따라 `--log-level debug` 를 구성에 명시했다
- baseline 상태: 고치기 전 동작은 spike 에서 관측했다(`docs/dev-cycle/TODO.md` 의 `[INFRA-080]` 재현 줄). 텍스트 단언 RED 1건
- 필수 여부(required): 예
- 결과: (미실행)
- 증거: (미실행)
- 정리(cleanup): (미실행)

## 시나리오

### S-1. 유휴 2초 경계의 동시 요청이 500 없이 끝난다 (결함 재현, 하네스)
- 조작: keep-alive 로 연결을 유지하는 클라이언트 6개가 `/api/kr/market-gate`·`/api/kr/signals`·`/api/kr/signals/status` 를 Next(58120)로
  동시에 보내고, 라운드 사이에 1.9~2.2초를 무작위로 쉰다. 80라운드(요청 480건)를 돈다. 이어서 0~0.3초 간격으로 80라운드를 돈다.
- 기대: 두 실행 모두 200 이 아닌 응답 0건. Next 로그의 `Failed to proxy` 증가 0건. gunicorn 기동 인자에 `--keep-alive 0` 이 있고,
  gunicorn 디버그 로그의 `Closing connection` 수가 처리한 GET 수와 같다(요청마다 연결을 닫음).
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 유휴 뒤 종가베팅·VCP 화면을 거듭 열어도 5xx 가 없다 (사용자 흐름)
- 조작: 브라우저로 `/dashboard/kr/closing-bet` 을 열고 요청이 끝난 뒤 2초 안팎을 쉬고 `/dashboard/kr/vcp` 를 연다. 이 왕복을 10회 한다.
  마지막에 각 화면을 한 번씩 스크린샷으로 남긴다.
- 기대: 브라우저 네트워크 기록에 `/api/` 5xx 0건, 콘솔 오류 0건. Next 로그의 `Failed to proxy` 증가 0건. 화면에 데이터가 표시된다.
  리뷰 발견 3 확인: Next 를 거친 `/api/kr/market-gate` 응답 헤더에 `Connection: close` 가 실리는지 기록한다(비용 기록용, 통과 판정과 무관).
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 챗봇 SSE 스트림이 끝까지 오고 무료 횟수가 1 차감된다 (인접 회귀)
- 조작: `/chatbot` 에서 사이드바의 「N회 남음」 을 읽고 「안녕」 을 보낸다. 답변이 끝나면 다시 읽는다.
- 기대: `조각0` 부터 `조각4` 까지 차례로 나타나고 오류 말풍선이 없다. 「N회 남음」 이 1 줄어든다. Flask 로그에
  `closed by client disconnect` 가 없고 `사용량 차감 완료` 가 있다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보낸다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 실행 결과

- (미실행)
