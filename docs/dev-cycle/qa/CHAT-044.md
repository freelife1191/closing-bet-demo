# [CHAT-044] 짧은 종목명이 남은 신호어 「전망·실적·차트·어때」 앞에서도 일반 명사로 쓰인다 — QA 시나리오

- 대상 화면: http://localhost:58120/chatbot (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:58121
- 구성 근거: `[CHAT-044]` 의 근거 줄(「분석 대상 전망」 류 오탐) + 설계 승인(짧은 이름 앞의 수식 명사 「분석·투자·관심·매수·매도·편입·검토·적용·지원」 이면 잡지 않음) + `[CHAT-038]`·`[CHAT-043]` 의 회귀 경로
- 구성 2026-09-23 23:36 | 실행 2026-09-23 23:38 (1회차)
- 검증 기준 커밋: `9de84c6` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 사본의 `chatbot/stock_query_service.py` 가 작업 트리와 같음을 실행 전후 `diff` 로 확인했다. 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름이 챗봇 화면이므로 브라우저 실측을 필수로 둔다. 하네스는 `[CHAT-043]` 과 같다:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/` 와 `frontend/node_modules` 를 APFS clone 으로 둔다.
  `.env` 계열은 두지 않는다. 사본에만 `qa_flask_app.py` 를 두어 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다.
  가짜 클라이언트는 받은 `content_parts` 에 `[종목 조회 컨텍스트]` 가 있으면 `[종목 상세 데이터: 이름 (티커)]` 의 이름·티커를, 없으면 `없음` 을
  `[답변] QA 가짜 응답입니다. 종목 문맥=<값> 으로 확인했습니다.` 에 싣고 같은 값을 사본의 로그 파일에 남긴다. gunicorn(`--workers 1 --threads 4 --keep-alive 0`,
  `SCHEDULER_ENABLED=false`, 더미 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)과 Next dev 를 `env -i` 와 더미 비밀로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 실제 LLM 은 부르지 않는다. 브라우저는 gstack `browse`, 익명 사용자로 쓴다
- 기대값 출처: 원본 `data/korean_stocks_list.csv` 를 읽기 전용으로 조회. 대상 `001680`, 기아 `000270`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 사본 `data/` 는 먼저 지우고 복제해 중첩이 없었다(파일 27,525개, 원본과 같음, gunicorn 로그 `korean_stocks_list.csv not found` 0건)
- baseline 상태: 고치기 전 동작은 RED 테스트로 고정했다(「VCP 분석 대상 전망」→대상)
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄(browse `js` 출력 원문) · 스크린샷 `docs/dev-cycle/evidence/CHAT-044/chat044-s{1,2,3}.png`(s3 를 열어서 확인: 기아·대상 답변과 「6회 남음」) · 가짜 LLM 이 받은 프롬프트 기록 `fake-llm-prompt-context.txt` · `/_next/mcp` 응답 · 전체 `pytest -q -p no:cacheprovider` 2725 passed 2 skipped(exit 0)
- 정리(cleanup): 격리 gunicorn(58121)·Next(58120) 종료(리스너 0, `pgrep -f chat044` 0건), browse 서버 정지, 사본과 `qa_flask_app.py`(사본에만 있었음) 삭제. 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. 수식 명사 뒤의 짧은 이름은 문맥을 싣지 않는다 (결함 재현)
- 조작: /chatbot 에서 「VCP 분석 대상 전망 알려줘」 를 보낸다.
- 기대: 답변에 `종목 문맥=없음`. 가짜 LLM 기록도 `없음`.
- 필수 여부(required): 예
- 실제: 23:38:26 전송 → 답변 `종목 문맥=없음 으로 확인했습니다.`, 가짜 LLM 기록 `VCP 분석 대상 전망 알려줘	없음`
- 결과: 통과
- 증거: 위 「실제」 줄, `chat044-s1.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-2. 다른 수식 명사와 신호어 조합도 문맥을 싣지 않는다 (결함 재현)
- 조작: 「투자 대상 실적은?」 을 보낸다.
- 기대: 답변에 `종목 문맥=없음`. 대상(001680) 이 아니다.
- 필수 여부(required): 예
- 실제: 23:38:28 전송 → 답변 `종목 문맥=없음 으로 확인했습니다.`, 기록 `투자 대상 실적은?	없음`. 대상(001680) 이 아니다
- 결과: 통과
- 증거: 위 「실제」 줄, `chat044-s2.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-3. 앞에 일반 말이 붙은 정상 질문은 문맥을 싣는다 (회귀)
- 조작: 「요즘 기아 전망 어때?」, 이어서 「대상 주가 어때?」 를 보낸다.
- 기대: 각각 `종목 문맥=기아 (000270)`, `종목 문맥=대상 (001680)`.
- 필수 여부(required): 예
- 실제: 23:38:28 「요즘 기아 전망 어때?」 → `종목 문맥=기아 (000270)`, 23:38:30 「대상 주가 어때?」 → `종목 문맥=대상 (001680)`. 기록도 같다
- 결과: 통과
- 증거: 위 「실제」 줄, `chat044-s3.png`, `fake-llm-prompt-context.txt`
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

### S-4. 프레임워크 관점에 컴파일·런타임 오류가 없다 (인접)
- 조작: S-1~S-3 을 마친 뒤 `/_next/mcp` 에 `get_compilation_issues` 와 `get_errors` 를 보내고, 같은 browse 세션의 /chatbot 에서 `console --errors` 를 읽는다.
- 기대: 컴파일 이슈 0건, 런타임 오류 0건, 콘솔 오류 없음.
- 필수 여부(required): 예
- 실제: `get_compilation_issues` → `{"issues":[]}`, `get_errors` → `{"configErrors":[],"sessionErrors":[]}`. 콘솔을 비우고 /chatbot 을 다시 연 같은 browse 세션에서 S-1~S-3 을 보낸 뒤 `console --errors` → `(no console errors)`
- 결과: 통과
- 증거: 위 「실제」 줄
- 정리(cleanup): 이 시나리오가 소유한 임시 자료 없음

## 알려진 한계 (판정과 무관)

- 「진도 어때」·「노을 어때」·「한창 전망」 처럼 이름 자체가 일반 명사이고 앞말이 없는 질문은 여전히 문맥이 실린다(승인된 대가, 코드의 `ponytail:` 주석).
- 수식 명사 바로 뒤에 실제 종목이 오는 어순(「매수 기아 어때」)은 문맥이 빠진다. 드문 어순이고 빠지는 쪽이 안전하다(코드 리뷰 발견 2).
- 조사가 붙은 앞말(「분석의 대상 전망」)은 막지 않는다. 설계는 공백만 허용했다(코드 리뷰 발견 3).

## 실행 결과

- 1회차(2026-09-23 23:38, 기준 `9de84c6`): 필수 4/4 통과
- 이월한 발견: 없음(코드 리뷰 발견 2·3 은 위 한계로 기록)
