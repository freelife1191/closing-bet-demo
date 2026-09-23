# [CHAT-038] 독립 단어로 쓰인 짧은 종목명이 종목 질의로 잡힌다 — QA 시나리오

- 대상 화면: http://localhost:58120/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[CHAT-038]` 의 QA 줄 + 설계 승인(두 글자 이하 이름은 바로 뒤 신호어나 메시지 전체일 때만, 6자리 뒤 「원」 은 티커 아님) + 코드 리뷰 발견 4(「298000 원」)
- 구성 2026-09-23 22:46 | 실행 2026-09-23 22:49~22:50 (1회차)
- 검증 기준 커밋: `9a4eff8` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면이므로 브라우저 실측을 필수로 둔다. `git archive HEAD` 사본에 원본 `data/` 와
  `frontend/node_modules` 를 APFS clone 으로 두고 `.env` 계열은 두지 않는다. 사본에만 `qa_flask_app.py` 를 두어
  `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 받은 `content_parts` 에
  `[종목 조회 컨텍스트]` 가 있으면 `[종목 상세 데이터: 이름 (티커)]` 의 이름·티커를, 없으면 `없음` 을 답변
  `[답변] QA 가짜 응답입니다. 종목 문맥=<값> 으로 확인했습니다.` 에 싣고, 같은 값을 사본의 로그 파일에 한 줄씩 남긴다(`[CHAT-042]` 에 따라
  답변은 20자를 넘고 `[답변]` 을 붙인다). gunicorn(`--workers 1 --threads 4 --keep-alive 0`, `SCHEDULER_ENABLED=false`,
  더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 실제 LLM 은 부르지 않는다. 브라우저는 gstack `browse`, 익명 사용자로 쓴다
- 기대값 출처: 원본 `data/korean_stocks_list.csv` 를 읽기 전용으로 조회. 대상 `001680`, 삼성전자 `005930`, 효성화학 `298000`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 22:48 의 첫 시도는 하네스 오류로 무효 처리했다. `data/paper_trading_sync.lock` 이 git 추적 파일이라 `git archive` 가 사본에 `data/` 를 먼저 만들었고, 그 위에 `cp -c -R data` 를 해서 원본이 `data/data/` 로 들어갔다. gunicorn 로그 `korean_stocks_list.csv not found` 로 종목 맵이 비었음을 확인하고, 서비스를 내린 뒤 사본의 `data/` 를 지우고 다시 복제해(파일 27,481개, 원본과 같음) 처음부터 실행했다
- baseline 상태: 고치기 전 동작은 RED 테스트 2건으로 고정했다(「대상 종목」 류가 문맥을 싣고, 「298000원」 이 효성화학으로 잡힘)
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 `docs/dev-cycle/evidence/CHAT-038/chat038-s{1,2,3}.png`(s3 를 열어서 확인: 세 답변과 「7회 남음」) · 가짜 LLM 이 받은 프롬프트 기록 `fake-llm-prompt-context.txt` · `/_next/mcp` 응답 · 전체 `pytest -q -p no:cacheprovider` 2725 passed 2 skipped(exit 0)
- 정리(cleanup): 격리 gunicorn(58121)·Next(58120) 종료(리스너 0, `pgrep -f chat038` 0건), browse 서버 정지, 사본과 `qa_flask_app.py`(사본에만 있었음) 삭제. 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. 일반 단어로 쓰인 짧은 종목명은 문맥을 싣지 않는다 (결함 재현)
- 조작: /chatbot 에서 「VCP 분석 대상 종목 알려줘」 를 보낸다.
- 기대: 답변에 `종목 문맥=없음`. 가짜 클라이언트 로그의 해당 줄도 `없음`.
- 필수 여부(required): 예
- 실제: 22:49:32 전송 → 답변 `종목 문맥=없음 으로 확인했습니다.`, 가짜 LLM 기록 `VCP 분석 대상 종목 알려줘	없음`
- 결과: 통과
- 증거: 위 「실제」 줄, `chat038-s1.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 신호어가 붙은 짧은 종목명은 문맥을 싣는다 (회귀)
- 조작: 「대상 주가 어때?」 를 보낸다.
- 기대: 답변에 `종목 문맥=대상 (001680)`.
- 필수 여부(required): 예
- 실제: 22:49:34 전송 → 답변 `종목 문맥=대상 (001680) 으로 확인했습니다.`, 기록 `대상 주가 어때?	대상 (001680)`
- 결과: 통과
- 증거: 위 「실제」 줄, `chat038-s2.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 「원」 이 붙은 6자리 가격은 티커로 보지 않는다 (결함 재현)
- 조작: 「삼성전자 298000원 가면 팔까?」 를 보낸다.
- 기대: 답변에 `종목 문맥=삼성전자 (005930)`. 효성화학이 아니다.
- 필수 여부(required): 예
- 실제: 22:49:35 전송 → 답변 `종목 문맥=삼성전자 (005930) 으로 확인했습니다.`, 기록 `삼성전자 298000원 가면 팔까?	삼성전자 (005930)`. 효성화학(298000) 이 아니다
- 결과: 통과
- 증거: 위 「실제」 줄, `chat038-s3.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보내고 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건, 콘솔 오류 없음.
- 필수 여부(required): 예
- 실제: `get_compilation_issues` → `{"issues":[]}`, `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. 첫 `console --errors` 는 browse 서버가 재시작되어 `about:blank` 를 읽었으므로 버렸다. /chatbot 을 다시 열고 콘솔을 비운 뒤 리뷰 발견 4 의 「298000 원이면 싸?」 를 22:49:53 에 보내(답변 `종목 문맥=없음`, 기록 `298000 원이면 싸?	없음`) 같은 세션의 /chatbot 에서 `console --errors` → `(no console errors)`
- 결과: 통과
- 증거: 위 「실제」 줄, `fake-llm-prompt-context.txt` 4행
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 알려진 한계 (판정과 무관)

- 「VCP 분석 대상 주식 알려줘」 처럼 신호어 「주식·매수·매도」 가 일반 명사 뒤에 오는 오탐과 「주가지수」 처럼 신호어가 긴 단어의 앞부분인 경우는 이 항목 범위 밖이며 `[CHAT-043]` 에서 다룬다.

## 실행 결과

- 1회차(2026-09-23 22:49~22:50, 기준 `9a4eff8`): 필수 4/4 통과. 첫 시도(22:48)는 사본의 `data/` 중첩으로 종목 맵이 비어 무효 처리했다
- 이월한 발견: `[CHAT-043]`(코드 리뷰 발견 1·2). QA 하네스 요령: `git archive` 사본에는 추적 파일 때문에 `data/` 가 이미 있으므로 지운 뒤 복제한다
