# [CHAT-036] 챗봇 스트림의 500 폴백 누락·프록시 30초 절단·평문 오류 노출 — QA 시나리오

- 대상 화면: http://localhost:3611/chatbot (격리 Next) 과 http://localhost:3611/dashboard/kr 의 챗봇 위젯. 백엔드는
  격리 gunicorn http://127.0.0.1:5611
- 구성 근거: `[CHAT-036]` 의 근거·QA 줄 + 설계 승인(폴백 판정 통일, 상태 코드 판정, `proxyTimeout` 120초, 공용 응답
  읽기와 절단 안내) + 이번 변경 여덟 파일. 1단계 리포트 도구 대신 원인 분석에서 확정한 세 실패 경로(500 폴백, 30초
  침묵, 평문 500)를 그대로 시나리오로 옮겼다
- 구성 2026-09-22 22:20 | 실행 (아래 「실행 결과」에 기록)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
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
- 단계(phase): 시나리오 구성 완료 | 실행 (아래)
- 반복(iteration): 1회
- baseline 상태: 고치기 전 코드의 동작은 pytest RED 5건·vitest RED 6건으로 고정했다(500 이 폴백을 타지 않음, 503
  세부 문구의 16400 이 인증 오류로 오분류, 평문 500 이 SyntaxError 문구로 노출, 끊긴 스트림에 안내 없음). 브라우저
  baseline 은 원본 코드의 Next 30초 제한(`proxy-request.js:37`)과 `httpxy` 의 `f.setTimeout(t, () => f.destroy())` 로
  코드에서 확정했다. 사본의 챗봇 기본 모델은 `gemini-3.7-flash`(`chatbot/core.py` `DEFAULT_GEMINI_MODEL`, 사본에
  `GEMINI_MODEL` 없음)이고 폴백 체인은 `[gemini-3.7-flash, gemini-3.5-flash-lite, gemini-2.5-flash-lite, gemini-2.5-flash]`
- 필수 여부(required): 예
- 결과: (실행 뒤 기록)
- 증거: (실행 뒤 기록)
- 정리(cleanup): (실행 뒤 기록)

## 시나리오

### S-1. 첫 모델의 500 INTERNAL 이 다음 모델로 넘어간다 (회귀)
- 조작: /chatbot 을 열고 모델 표시가 `gemini-3.7-flash` 인지 읽는다. 입력창에 「폴백 검사」 를 넣어 Enter 로 보낸다.
  답변이 끝나면 마지막 말풍선 본문을 읽고, 격리 Flask 로그에서 `Error (retryable)` 줄을 찾는다.
- 기대: 말풍선 본문이 `gemini-3.5-flash-lite 가 답합니다: QA 가짜 응답입니다.` 이고 `⚠️` 가 없다. Flask 로그에
  `gemini-3.7-flash Error (retryable). Details: 500 INTERNAL.` 한 줄이 있다. 고치기 전에는 `⚠️ 오류: ⚠️ 스트리밍 응답
  처리 오류: 500 INTERNAL. {...}` 가 떴다.
- 필수 여부(required): 예

### S-2. 첫 토큰이 35초 늦어도 스트림이 끊기지 않는다 (회귀)
- 조작: 같은 대화에서 「지연35 검사」 를 보낸다. 40초 뒤 마지막 말풍선을 읽고, Next 로그에서 `Failed to proxy` 를
  찾는다.
- 기대: 말풍선 본문이 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.` 이고 Next 로그에 `Failed to proxy` 가 없다.
  고치기 전 30초 제한에서는 여기서 소켓이 끊기고 `⚠️ 오류가 발생했습니다: Unexpected token 'I', "Internal S"... is
  not valid JSON` 이 떴다.
- 필수 여부(required): 예

### S-3. 120초를 넘는 침묵은 상태 코드 문구로 보인다 (회귀)
- 조작: 「지연130 검사」 를 보낸다. 전송 시각을 기록하고 125초 뒤 마지막 말풍선을 읽는다. Next 로그의 `Failed to
  proxy` 줄과 그 시각을 읽는다.
- 기대: 말풍선 본문이 `⚠️ 오류: 서버 응답을 받지 못했습니다 (HTTP 500). 잠시 후 다시 시도해주세요.` 이고
  `Unexpected token` 이 없다. Next 로그에 `Failed to proxy http://127.0.0.1:5611/api/kr/chatbot Error: socket hang up`
  이 전송 후 약 120초(115~125초) 지점에 찍힌다. 이 시각 차가 `proxyTimeout` 이 실제로 120초임을 보인다.
- 필수 여부(required): 예

### S-4. 정상 스트림에는 끊김 안내가 붙지 않는다 (인접)
- 조작: 「안녕」 을 보낸다. 답변이 끝난 뒤 말풍선 본문과 입력창 상태를 읽는다.
- 기대: 본문이 `gemini-3.7-flash 가 답합니다: QA 가짜 응답입니다.` 로 끝나고 「응답이 중간에 끊겼습니다」 가 없다.
  입력창이 다시 활성이다(`disabled` 아님).
- 필수 여부(required): 예

### S-5. 대시보드 위젯도 같은 폴백과 오류 문구를 쓴다 (인접)
- 조작: /dashboard/kr 을 열어 우상단 챗봇 버튼으로 위젯을 연다. 「폴백 위젯 검사」 를 보내고 답변 본문을 읽는다.
- 기대: 위젯 말풍선이 `gemini-3.5-flash-lite 가 답합니다: QA 가짜 응답입니다.` 이고 `⚠️` 가 없다. 위젯은 모델을
  보내지 않으므로 서버 기본 모델 `gemini-3.7-flash` 가 첫 모델이다.
- 필수 여부(required): 예

### S-6. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-5 를 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보낸다. 각 시나리오 전에
  `console --clear` 로 비우고 `goto` 로 다시 열어 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건. 브라우저 콘솔은 S-3 에서 의도한 500 응답의 `Failed to load resource`
  한 줄 외에 오류가 없다.
- 필수 여부(required): 예

## 실행 결과

(실행 뒤 기록)
