# [CHAT-037] 프록시가 끊은 뒤 완료된 챗봇 스트림도 무료 사용량을 차감한다 — QA 시나리오

- 대상 화면: http://localhost:58120/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[CHAT-037]` 의 QA 줄 + 설계 승인(쓰기 실패 뒤 `GeneratorExit` 면 차감 생략) + 코드 리뷰 발견 1 에 대한
  사용자 결정(사용자 「중단」 도 차감하지 않음) + `[CHAT-036]` S-3 의 재현 절차
- 구성 2026-09-23 21:30 | 실행 2026-09-23 21:34~21:38 (1회차)
- 검증 기준 커밋: `633f253` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면이므로 브라우저 실측을 필수로 둔다. 원본 챗봇으로는
  전송하지 않는다(LLM 비용과 로그가 생기는 되돌릴 수 없는 조작). `git archive HEAD` 사본에 원본 `data/` 와
  `frontend/node_modules` 를 APFS clone 으로 두고 `.env` 계열은 두지 않는다. QA 전용 진입점 `qa_flask_app.py` 를
  사본에만 두어 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 메시지
  문구로 상황을 고른다: 「지연130」 은 130초 침묵한 뒤 세 청크, 「느린」 은 3초 간격 열 청크, 그 외는 즉시 두 청크.
  gunicorn(1 worker, 4 threads, `--timeout 120`, `SCHEDULER_ENABLED=false`, 쿼터 가드의 「서버 키 있음」 판정용 더미
  `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않는다. 브라우저는 gstack `browse`, 익명 사용자(무료 티어)로 보낸다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 고치기 전 동작은 `[CHAT-036]` S-3 에서 관측했다(끊긴 뒤 `[QUOTA] … stream_has_error=False` →
  `사용량 차감 완료`, 「N회 남음」 감소). pytest RED 1건으로 고정했다
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 `docs/dev-cycle/evidence/CHAT-037/chat037-s{1,2,3}.png`(열어서 확인) · 격리 Flask 로그 발췌 `flask-quota.txt`(익명 키는 `anon_…` 로 가림) · 격리 Next 로그 발췌 `next-proxy.txt` · `/_next/mcp` 응답 · 전체 `pytest -q -p no:cacheprovider` 2721 passed 2 skipped(exit 0)
- 정리(cleanup): 격리 gunicorn(58121)·Next(58120) 종료(리스너 0, `pgrep -f qa037` 0건), browse 서버 정지, 사본 `qa037/` 와 래퍼 삭제. `qa_flask_app.py` 는 사본에만 있었고 저장소에 없음. 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. 정상 응답은 무료 횟수를 1 차감한다 (회귀)
- 조작: /chatbot 을 열어 사이드바의 「N회 남음」 을 읽는다. 「안녕」 을 보내고 답변이 끝난 뒤 다시 읽는다.
- 기대: 답변이 끝까지 보이고 「N회 남음」 이 1 줄어든다. Flask 로그에 `[QUOTA] … stream_has_error=False` 와
  `사용량 차감 완료` 가 있고 `closed by client disconnect` 는 없다.
- 필수 여부(required): 예
- 실제: 「10회 남음」 → 21:34:28 「안녕」 전송, 8초 뒤 본문 `QA 가짜 응답입니다.`, 「9회 남음」. Flask 로그 8행 `[QUOTA] use_free_tier=True, stream_has_error=False` → 9행 `사용량 차감 완료 … -> 1회`, `closed by client disconnect` 없음
- 결과: 통과
- 증거: 위 「실제」 줄, `chat037-s1.png`, `flask-quota.txt` 8~9행
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 프록시가 120초에 끊은 스트림은 차감하지 않는다 (결함 재현)
- 조작: 「지연130 검사」 를 보낸다. 전송 시각을 적고 125초 뒤 마지막 말풍선을 읽는다. Flask 가 130초 침묵을 마친 뒤
  (전송 후 135초 이상) 페이지를 다시 열어 「N회 남음」 을 읽는다.
- 기대: 말풍선이 `⚠️ 오류: 서버 응답을 받지 못했습니다 (HTTP 500)` 로 시작한다. 「N회 남음」 이 S-1 직후 값과 같다.
  Flask 로그에 `Chat stream closed by client disconnect` 와 `[QUOTA] … stream_has_error=True`, `차감 스킵` 이 있다.
- 필수 여부(required): 예
- 실제: 21:34:41 「지연130 검사」 전송. 브라우저 콘솔 `[2026-09-23T12:36:41.620Z] [error] Failed to load resource: … 500` 과 Next 로그 13행 `Failed to proxy http://127.0.0.1:58121/api/kr/chatbot Error: socket hang up`·`code: 'ECONNRESET'` → 전송 후 정확히 120초에 끊김. 말풍선 `⚠️ 오류: 서버 응답을 받지 못했습니다 (HTTP 500). 잠시 후 다시 시도해주세요.`. Flask 는 130초 침묵을 마친 21:36:51 에 10행 `Chat stream closed by client disconnect` → 11행 `stream_has_error=True` → 12행 `차감 스킵`. 페이지를 다시 연 뒤 「9회 남음」(S-1 직후와 같음)
- 결과: 통과
- 증거: 위 「실제」 줄, `chat037-s2.png`, `flask-quota.txt` 10~12행, `next-proxy.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 사용자가 「답변 중단」 을 누른 스트림은 차감하지 않는다 (정책)
- 조작: 「느린 검사」 를 보내고 첫 청크가 보이면 「답변 중단」 버튼을 누른다. 15초 뒤 「N회 남음」 을 다시 읽는다.
- 기대: `🛑 답변 생성이 중단되었습니다.` 가 보이고 「N회 남음」 이 그대로다. Flask 로그에 `closed by client disconnect` 와
  `차감 스킵` 이 있다.
- 필수 여부(required): 예
- 실제: 21:37:09 「느린 검사」 전송, 21:37:25 `조각0` 표시 뒤 `[button] "답변 중단"` 클릭(21:37:31). 본문 `조각0 조각1 조각2` 와 `🛑 답변 생성이 중단되었습니다.`. Flask 21:37:36 13행 `Chat stream closed by client disconnect` → 14행 `stream_has_error=True` → 15행 `차감 스킵`. 페이지를 다시 연 뒤 「9회 남음」
- 결과: 통과
- 증거: 위 「실제」 줄, `chat037-s3.png`, `flask-quota.txt` 13~15행
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보내고 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건. 콘솔은 S-2 의 의도한 500 응답 줄 외에 오류가 없다.
- 필수 여부(required): 예
- 실제: `get_compilation_issues` → `{"issues":[]}`, `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. S-2 콘솔은 의도한 500 한 줄뿐, S-3 과 재로드 뒤 콘솔 `(no console errors)`
- 결과: 통과
- 증거: 위 「실제」 줄
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 실행 결과

- 1회차(2026-09-23 21:34~21:38, 기준 `633f253`): 필수 4/4 통과. S-2 에서 130초 침묵이 끝난 21:36:51 에 끊김이 감지되어 차감을 건너뛰었다. 몇 번째 쓰기가 실패했는지는 로그로 구분할 수 없으므로, 리뷰 발견 3 의 추론(헤더 전에 끊기면 첫 쓰기부터 실패)을 직접 확인한 것은 아니다
- 이월한 발견: 없음
