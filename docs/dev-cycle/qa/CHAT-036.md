# [CHAT-036] 챗봇 스트림의 500 폴백 누락·프록시 30초 절단·평문 오류 노출 — QA 시나리오

- 대상 화면: http://localhost:3611/chatbot (격리 Next) 과 http://localhost:3611/dashboard/kr 의 챗봇 위젯. 백엔드는
  격리 gunicorn http://127.0.0.1:5611
- 구성 근거: `[CHAT-036]` 의 근거·QA 줄 + 설계 승인(폴백 판정 통일, 상태 코드 판정, `proxyTimeout` 120초, 공용 응답
  읽기와 절단 안내) + 이번 변경 여덟 파일. 1단계 리포트 도구 대신 원인 분석에서 확정한 세 실패 경로(500 폴백, 30초
  침묵, 평문 500)를 그대로 시나리오로 옮겼다
- 구성 2026-09-22 22:20 | 실행 2026-09-22 22:22~22:28 (1회차)
- 검증 기준 커밋: `d22f2a1` (첫 커밋). 실행은 그 커밋과 같은 작업 트리에서 했고 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면과 대시보드 위젯이므로 브라우저 실측을 필수로 두었다.
  원본 챗봇으로는 전송하지 않았다(LLM 비용과 로그가 생기는 되돌릴 수 없는 조작). 저장소 전체를 scratchpad
  `qa-chat036/` 에 rsync 로 복사(`.git`·`venv`·`logs`·`.env*`·`secrets/`·`backup/` 제외, `frontend/node_modules` 는
  APFS clone)하고 QA 전용 진입점 `qa_app.py` 를 사본에만 두어 `engine.genai_client.build_genai_client` 를 가짜
  클라이언트로 바꿨다. 가짜 클라이언트는 메시지 문구로 상황을 고른다: 「폴백」 이 들어가면 첫 모델 호출이
  `500 INTERNAL. {...}` 을 던지고 다음 모델이 답하며, 「지연35」 는 첫 청크 전 35초, 「지연130」 은 130초 침묵한 뒤
  답하고, 그 외는 즉시 스트리밍한다. 답변에는 실제로 답한 모델 이름이 들어간다. gunicorn(1 worker, 4 threads,
  `--timeout 120`, `SCHEDULER_ENABLED=false`, `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub` 는 쿼터
  가드의 「서버 키 있음」 판정용 더미, 5611)과 Next(`API_URL` → 5611, 3611, 기동 로그에 `proxyTimeout: 120000`)를
  띄웠다. 사본 `data/` 는 읽기만 하고 챗봇 저장소·사용량 DB 만 사본에 쓰인다. 원본 `data/`·3500·5501·운영 주소는
  건드리지 않는다. 브라우저는 gstack `browse`, `localhost` 로 열고 익명 사용자(무료 티어)로 보낸다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 고치기 전 코드의 동작은 pytest RED 5건·vitest RED 6건으로 고정했다(500 이 폴백을 타지 않음, 503
  세부 문구의 16400 이 인증 오류로 오분류, 평문 500 이 SyntaxError 문구로 노출, 끊긴 스트림에 안내 없음). 브라우저
  baseline 은 원본 코드의 Next 30초 제한(`proxy-request.js:37`)과 `httpxy` 의 `f.setTimeout(t, () => f.destroy())` 로
  코드에서 확정했다. 사본의 챗봇 기본 모델은 `gemini-3.7-flash`(`chatbot/core.py` `DEFAULT_GEMINI_MODEL`, 사본에
  `GEMINI_MODEL` 없음)이고 폴백 체인은 `[gemini-3.7-flash, gemini-3.5-flash-lite, gemini-2.5-flash-lite, gemini-2.5-flash]`
- 필수 여부(required): 예
- 결과: 통과 (필수 6/6)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 scratchpad `chat036-s1-fallback.png`·
  `chat036-s4-normal.png`·`chat036-s3-timeout.png`·`chat036-s5-widget.png`(열어서 확인) · 격리 Flask 로그 `qa-chat036-flask.log`
  12행·21행의 `gemini-3.7-flash Error (retryable). Details: 500 INTERNAL.` · 격리 Next 로그 `qa-chat036-next.log` 17~20행의
  `Failed to proxy http://127.0.0.1:5611/api/kr/chatbot Error: socket hang up … code: 'ECONNRESET'`(파일 mtime 22:25:56) ·
  `/_next/mcp` 응답 `{"issues":[]}`·`{"configErrors":[],"sessionErrors":[]}` · `pytest -q -p no:cacheprovider` 2611 passed
  2 skipped(exit 0) · `(cd frontend && npx vitest run)` 90 files 670 passed(exit 0) · `npm run type-check` 통과 · `npm run
  lint` 오류 0, 경고 184 는 전부 기존(변경 파일의 경고 7건도 모두 이번에 손대지 않은 줄)
- 정리(cleanup): 격리 gunicorn(5611)·Next(3611) 종료, browse 서버 정지. `qa_app.py` 는 사본에만 있고 저장소에 없음. 저장소
  루트에 `node_modules/.vite` 없음. 저장소에는 이번 항목의 파일만 남음

## 시나리오

### S-1. 첫 모델의 500 INTERNAL 이 다음 모델로 넘어간다 (회귀)
- 조작: /chatbot 을 열고 모델 표시가 `gemini-3.7-flash` 인지 읽는다. 입력창에 「폴백 검사」 를 넣어 Enter 로 보낸다.
  답변이 끝나면 마지막 말풍선 본문을 읽고, 격리 Flask 로그에서 `Error (retryable)` 줄을 찾는다.
- 기대: 말풍선 본문이 `gemini-3.5-flash-lite 가 답합니다: QA 가짜 응답입니다.` 이고 `⚠️` 가 없다. Flask 로그에
  `gemini-3.7-flash Error (retryable). Details: 500 INTERNAL.` 한 줄이 있다. 고치기 전에는 `⚠️ 오류: ⚠️ 스트리밍 응답
  처리 오류: 500 INTERNAL. {...}` 가 떴다.
- 필수 여부(required): 예
- 실제: 모델 표시 `FLASH`, `localStorage.chatbot_current_model` = `gemini-3.7-flash`, `/api/kr/chatbot/models` 의 current
  `gemini-3.7-flash`. 22:22:28 전송 → 7초 뒤 본문 `gemini-3.5-flash-lite 가 답합니다: QA 가짜 응답입니다.`, `⚠️` 없음. Flask
  로그 12행 `22:22:28,795 … gemini-3.7-flash Error (retryable). Details: 500 INTERNAL. {'error': {'code': 500, …}}`
- 결과: 통과
- 증거: 위 「실제」 줄, `chat036-s1-fallback.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 첫 토큰이 35초 늦어도 스트림이 끊기지 않는다 (회귀)
- 조작: 같은 대화에서 「지연35 검사」 를 보낸다. 40초 뒤 마지막 말풍선을 읽고, Next 로그에서 `Failed to proxy` 를
  찾는다.
- 기대: 말풍선 본문이 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.` 이고 Next 로그에 `Failed to proxy` 가 없다.
  고치기 전 30초 제한에서는 여기서 소켓이 끊기고 `⚠️ 오류가 발생했습니다: Unexpected token 'I', "Internal S"... is
  not valid JSON` 이 떴다.
- 필수 여부(required): 예
- 실제: 22:22:45 전송, 22:23:26 읽음 → 본문 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.`. Next 로그의
  `Failed to proxy` 0건(`grep -c`).
- 결과: 통과
- 증거: 위 「실제」 줄
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 120초를 넘는 침묵은 상태 코드 문구로 보인다 (회귀)
- 조작: 「지연130 검사」 를 보낸다. 전송 시각을 기록하고 125초 뒤 마지막 말풍선을 읽는다. Next 로그의 `Failed to
  proxy` 줄과 그 시각을 읽는다.
- 기대: 말풍선 본문이 `⚠️ 오류: 서버 응답을 받지 못했습니다 (HTTP 500). 잠시 후 다시 시도해주세요.` 이고
  `Unexpected token` 이 없다. Next 로그에 `Failed to proxy http://127.0.0.1:5611/api/kr/chatbot Error: socket hang up`
  이 전송 후 약 120초(115~125초) 지점에 찍힌다. 이 시각 차가 `proxyTimeout` 이 실제로 120초임을 보인다.
- 필수 여부(required): 예
- 실제: 22:23:56 전송, 22:26:02 읽음 → 본문 `⚠️ 오류: 서버 응답을 받지 못했습니다 (HTTP 500). 잠시 후 다시
  시도해주세요.`, `Unexpected token` 없음. Next 로그 17행 `Failed to proxy http://127.0.0.1:5611/api/kr/chatbot Error: socket
  hang up` + `code: 'ECONNRESET'`, 로그 파일 mtime 22:25:56, 브라우저 콘솔 `[2026-09-22T13:25:56.663Z] [error] Failed to load
  resource: … 500` → 전송 후 정확히 120초에 끊겼다. Flask 는 22:26:06 에 130초 침묵을 마치고 스트림을 끝냈다(19~20행).
- 결과: 통과
- 증거: 위 「실제」 줄, `chat036-s3-timeout.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 정상 스트림에는 끊김 안내가 붙지 않는다 (인접)
- 조작: 「안녕」 을 보낸다. 답변이 끝난 뒤 말풍선 본문과 입력창 상태를 읽는다.
- 기대: 본문이 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.` 로 끝나고 「응답이 중간에 끊겼습니다」 가 없다.
  입력창이 다시 활성이다(`disabled` 아님).
- 필수 여부(required): 예
- 실제: 「안녕」 전송 6초 뒤 본문 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.`, `응답이 중간에 끊겼습니다` 없음
  (`cut: false`), 입력창 `disabled: false`.
- 결과: 통과
- 증거: 위 「실제」 줄, `chat036-s4-normal.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-5. 대시보드 위젯도 같은 폴백과 오류 문구를 쓴다 (인접)
- 조작: /dashboard/kr 을 열어 우상단 챗봇 버튼으로 위젯을 연다. 「폴백 위젯 검사」 를 보내고 답변 본문을 읽는다.
- 기대: 위젯 말풍선이 `gemini-3.5-flash-lite 가 답합니다: QA 가짜 응답입니다.` 이고 `⚠️` 가 없다. 위젯은 모델을
  보내지 않으므로 서버 기본 모델 `gemini-3.7-flash` 가 첫 모델이다.
- 필수 여부(required): 예
- 실제: /dashboard/kr 의 `[button] "AI 상담"` 로 위젯을 열고 22:27:15 전송 → 8초 뒤 위젯 본문 `gemini-3.5-flash-lite 가
  답합니다: QA 가짜 응답입니다.`, `⚠️` 없음. Flask 로그 21행 `22:27:15,711 … gemini-3.7-flash Error (retryable). Details: 500
  INTERNAL.`. 대시보드 콘솔 오류 없음.
- 결과: 통과
- 증거: 위 「실제」 줄, `chat036-s5-widget.png`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-6. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-5 를 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보낸다. 각 시나리오 전에
  `console --clear` 로 비우고 `goto` 로 다시 열어 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건. 브라우저 콘솔은 S-3 에서 의도한 500 응답의 `Failed to load resource`
  한 줄 외에 오류가 없다.
- 필수 여부(required): 예
- 실제: `get_compilation_issues` → `{"issues":[]}`, `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. /chatbot 콘솔은
  S-3 의 의도한 500 한 줄뿐, /dashboard/kr 콘솔은 오류 없음(각각 `console --clear` 뒤 `goto` 로 다시 열어 읽음).
- 결과: 통과
- 증거: 위 「실제」 줄
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 이월한 발견

- S-3 에서 프록시가 120초에 끊은 뒤에도 Flask 는 130초 침묵을 마치고 스트림을 끝내며 무료 사용량을 차감했다(Flask 로그
  20행 `사용량 차감 완료 … -> 4회`, 화면의 「N회 남음」 도 한 번 줄었다). 사용자는 답변을 받지 못했는데 횟수는 쓰였다. 이번
  범위(폴백·타임아웃·표시)를 넘어 사용량 계약을 바꾸는 일이라 `[CHAT-037]` 로 올렸다.

## 실행 결과

- 필수 시나리오: 통과 6 / 전체 6
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 위 「이월한 발견」 1건
