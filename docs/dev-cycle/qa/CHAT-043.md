# [CHAT-043] 짧은 종목명 신호어 「주식·매수·매도」 가 일반 명사 뒤에서 오탐을 남긴다 — QA 시나리오

- 대상 화면: http://localhost:58120/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[CHAT-043]` 의 근거 줄(오탐 8건) + 설계 승인(신호어에서 주식·매수·매도·수급 제외, `주가(?!지수)`) + `[CHAT-038]` 의 회귀 경로
- 구성 2026-09-23 23:00 | 실행 (미실행)
- 검증 기준 커밋: 첫 커밋(정해지면 적는다). 사본은 그 커밋의 `git archive HEAD` 로 만든다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면이므로 브라우저 실측을 필수로 둔다. 하네스는 `[CHAT-038]` 과 같다:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/` 와 `frontend/node_modules` 를 APFS clone 으로 둔다.
  `.env` 계열은 두지 않는다. 사본에만 `qa_flask_app.py` 를 두어 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다.
  가짜 클라이언트는 받은 `content_parts` 에 `[종목 조회 컨텍스트]` 가 있으면 `[종목 상세 데이터: 이름 (티커)]` 의 이름·티커를, 없으면 `없음` 을
  `[답변] QA 가짜 응답입니다. 종목 문맥=<값> 으로 확인했습니다.` 에 싣고 같은 값을 사본의 로그 파일에 남긴다. gunicorn(`--workers 1 --threads 4 --keep-alive 0`,
  `SCHEDULER_ENABLED=false`, 더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 실제 LLM 은 부르지 않는다. 브라우저는 gstack `browse`, 익명 사용자로 쓴다
- 기대값 출처: 원본 `data/korean_stocks_list.csv` 를 읽기 전용으로 조회. 대상 `001680`, 기아 `000270`, 한창 `005110`
- 단계(phase): 시나리오 구성 완료
- baseline 상태: 고치기 전 동작은 RED 테스트로 고정했다(「VCP 분석 대상 주식 알려줘」→대상)
- 필수 여부(required): 예
- 결과: (미실행)

## 시나리오

### S-1. 일반 명사 뒤 「주식」 은 문맥을 싣지 않는다 (결함 재현)
- 조작: /chatbot 에서 「VCP 분석 대상 주식 알려줘」 를 보낸다.
- 기대: 답변에 `종목 문맥=없음`. 가짜 LLM 기록도 `없음`.
- 필수 여부(required): 예

### S-2. 일반 명사 뒤 「매수」 는 문맥을 싣지 않는다 (결함 재현)
- 조작: 「요즘 한창 매수 중인 섹터는?」 를 보낸다.
- 기대: 답변에 `종목 문맥=없음`. 한창(005110) 이 아니다.
- 필수 여부(required): 예

### S-3. 남긴 신호어가 붙은 짧은 종목명은 문맥을 싣는다 (회귀)
- 조작: 「대상 주가 어때?」, 이어서 「기아 실적발표 언제야?」 를 보낸다.
- 기대: 각각 `종목 문맥=대상 (001680)`, `종목 문맥=기아 (000270)`.
- 필수 여부(required): 예

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보내고, 같은 browse 세션의 /chatbot 에서 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건, 콘솔 오류 없음.
- 필수 여부(required): 예
