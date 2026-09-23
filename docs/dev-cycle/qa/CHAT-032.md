# [CHAT-032] 종목 질의 문맥이 언제나 비는 경로 복구 — QA 시나리오

- 대상 화면: http://localhost:3720/chatbot, http://localhost:3720/dashboard/kr/vcp (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5720
- 구성 근거: `[CHAT-032]` 의 QA 줄(「삼성전자 어때?」 → 최근 5일 종가와 외국인·기관 순매수 인용) + 설계 승인(종목 맵 연결, 빈
  vcp_stocks 경로 제거) + 코드 리뷰 지적 2(짧은 종목명 오탐)·6(맵에 없는 티커) + 심층 리뷰 지적 2(조사 붙은 티커).
  기대값은 원본 `data/` 를 pandas 로 읽기 전용으로 읽어 정했다(`daily_prices.csv`·`all_institutional_trend_data.csv`·
  `signals_log.csv` 의 005930·000270 최근 5행). 1단계 리포트 도구 대신 이 값과 TODO 의 QA 줄에서 시나리오를 만들었다
  (`[FLOW-019]` 와 같은 방식)
- 구성 2026-09-23 08:57 | 실행 2026-09-23 09:02~09:07 (1회차)
- 검증 기준 커밋: `55919c1` (첫 커밋). 사본의 범위 파일 다섯 개(`core_data_access_mixin.py`·`stock_query_service.py`·`payload_service.py`·`prompts.py`·`command_service.py`)가 이 커밋의 파일과 바이트 단위로 같음을 `cmp` 로 확인했고 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다. 챗봇 전송은
  LLM 비용과 기록이 남는 조작이므로 원본에서 하지 않는다. 저장소 작업 트리를 scratchpad `qa-chat032/` 로 복사(`.env*`·`.git`·
  `venv`·`logs` 제외, `frontend/node_modules` 는 APFS clone)하고, 사본에만 QA 전용 진입점 `qa_flask_app.py` 를 둔다. 이
  진입점은 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 모델이 받을 마지막 content
  part 에서 `[종목 조회 컨텍스트]` 절만 잘라 답변으로 돌려주고(없으면 「[종목 조회 컨텍스트] 없음」), 「## VCP 상위 종목」 절이
  프롬프트에 있는지를 한 줄로 덧붙인다. 그래서 화면의 답변이 곧 모델이 받은 종목 자료다(`[CHAT-031]` 의 방식). 더미 값
  (`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`, `ADMIN_EMAILS=qa-admin@example.com`,
  `SCHEDULER_ENABLED=false`, 쿼터 가드의 「서버 키 있음」 판정용 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)만
  환경 변수로 준다. VCP 화면에서는 종목 선택과 채팅 입력만 하고 Refresh·재분석·모의 매수 버튼은 누르지 않는다
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- 결과: 통과 (필수 5/5)
- 증거: 각 시나리오의 「실제」 줄(browse `js`·`network`·`console` 출력 원문, 사본 챗봇 저장소 조회) · 스크린샷 scratchpad `chat032-s1.png`·`chat032-s2.png`(열어 확인)·`chat032-s3.png`·`chat032-s4.png` · 격리 로그 `qa-chat032-flask.log`·`qa-chat032-next.log` · `/_next/mcp` 응답
- 사본 자료 변경(S-2 전용): 사본 `data/` 에는 오늘(2026-09-23) VCP 시그널이 없어 VCP 화면의 표가 비고 종목을 고를 수 없었다(`/api/kr/signals` count 0, 과거 날짜 목록 「데이터 파일 없음」). 그래서 **사본의** `signals_log.csv` 에만 기존 005930 행을 복제해 `signal_date=2026-09-23`, `is_vcp=True` 로 바꾼 합성 행 하나를 덧붙였다(`_is_vcp_signal_row` 가 `is_vcp` 를 요구함). 원본 `data/` 는 바꾸지 않았다. 이 행 때문에 S-2 의 시그널 이력 기대값은 `2026-09-23: 76점`·`2026-05-05: 76점` 두 줄이다. S-1·S-3 은 합성 행을 넣기 전에 실행했다
- 정리(cleanup): browse 서버 정지, 격리 gunicorn(5720)·Next(3720) 종료 뒤 두 포트 리스너 0, 사본 경로에 남은 Next 텔레메트리 전송 프로세스 두 개를 종료해 사본 경로 프로세스 0, 사본 `qa-chat032/`(합성 행과 챗봇 저장소 포함) 삭제. 스크린샷과 로그는 scratchpad 에만 있고 저장소에 없음. 저장소 루트 `node_modules/.vite` 없음. 원본 3500/5501 리스너 0(처음부터 떠 있지 않았고 건드리지 않음). 원본 `data/runtime_cache.db` 의 수정 시각은 QA 전후 모두 08:56:12 로 바뀌지 않았다(08:56 의 변경은 QA 전, 리뷰 레인의 읽기 전용 실측 시각대)
- 필수 여부(required): 예
- browser_applicability: required. 사용자가 챗봇 화면과 VCP 상담 모드에서 종목을 묻고 답변을 읽는 흐름이다. browser_driver: gstack `browse`
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`
- baseline 상태: 고치기 전 `_detect_stock_query` 는 늘 빈 `vcp_stocks`(mock)만 보아 「삼성전자 어때?」에도 `[종목 조회 컨텍스트]`
  가 붙지 않았다. vitest 대상 파일 변경 없음. pytest RED 1건(`test_core_data_access_mixin.py`, 옛 경로가 `_get_cached_data` 로 빠짐)
- 기대값 원천(원본 `data/` 읽기 전용):
  삼성전자(005930) 주가 최근행 `2026-09-21 종가 274,000 | 거래량 22,261,519 | 등락 +10,000`, 수급 최근행
  `2026-09-21 외인 +1,116,052,815,750 | 기관 +1,138,104,847,250`, 시그널 이력 `2026-05-05 76점 VCP 포착`.
  기아(000270) 주가 최근행 `2026-09-21 종가 120,000 | 거래량 800,591 | 등락 -1,500`, 시그널 이력 없음(「과거 VCP 포착 이력 없음」)

## 시나리오

### S-1. 챗봇 화면의 종목명 질의가 그 종목의 5일 자료를 싣는다 (회귀)
- 조작: `/chatbot` 에서 새 대화로 「삼성전자 어때?」를 보낸다.
- 기대: 답변에 `[종목 조회 컨텍스트]` 와 `## [종목 상세 데이터: 삼성전자 (005930)]`, 주가 5행(첫 행 `2026-09-21: 종가 274,000`),
  수급 5행(첫 행 `외인 +1,116,052,815,750 | 기관 +1,138,104,847,250`), `2026-05-05: 76점 VCP 포착` 이 보인다.
  「## VCP 상위 종목」 절은 없다.
- 필수 여부(required): 예
- 실제: `POST /api/kr/chatbot → 200 (410ms)`. 답변 원문: `[종목 조회 컨텍스트]` / `[종목 상세 데이터: 삼성전자 (005930)]` / `1. 최근 주가 (5일)` 5행(`2026-09-21: 종가 274,000 | 거래량 22,261,519 | 등락 +10,000` … `2026-09-15: 종가 248,500 | 거래량 11,435,506 | 등락 +500`) / `2. 수급 현황 (5일)` 5행(`2026-09-21: 외인 +1,116,052,815,750 | 기관 +1,138,104,847,250` …) / `3. VCP 시그널 이력` `2026-05-05: 76점 VCP 포착` / `VCP 상위 종목 절: 없음`
- 결과: 통과
- 증거: `chat032-s1.png`
- 정리(cleanup): 격리 사본의 챗봇 저장소에만 대화가 남는다. 사본 삭제로 정리

### S-2. VCP 상담 모드의 `[종목명(티커)]` 접두가 선택 종목 자료를 싣는다 (회귀)
- 조작: `/dashboard/kr/vcp` 에서 삼성전자 행을 선택하고 채팅 입력에 「전망은?」을 보낸다.
- 기대: 요청 본문 message 가 `[삼성전자(005930)] 전망은?` 이고, 답변에 S-1 과 같은 삼성전자 상세 자료가 보인다(시그널 이력은 합성 행 포함 두 줄).
- 필수 여부(required): 예
- 실제: 표 행 `삼성전자 005930 2026-09-23 …` 클릭 → 차트 모달의 「AI 상담 (VCP 전문가)」 입력에 「전망은?」 → `POST /api/kr/chatbot → 200`. 사본 챗봇 저장소의 사용자 메시지(세션 `vcp_005930_…`) `[{"text":"[삼성전자(005930)] 전망은?"}]`. 답변은 S-1 과 같은 주가 5행·수급 5행에 `2026-09-23: 76점 VCP 포착`·`2026-05-05: 76점 VCP 포착`, `VCP 상위 종목 절: 없음`. 입력 문장 자체에는 종목명이 없으므로 문맥은 접두의 티커에서 왔다
- 결과: 통과
- 증거: `chat032-s2.png`(열어 확인: 사용자 말풍선 `[삼성전자(005930)] 전망은?`, 답변 첫 줄 `[종목 조회 컨텍스트]`)
- 정리(cleanup): S-1 과 같다

### S-3. 짧은 종목명은 단어로 쓰일 때만 잡힌다 (인접, 리뷰 지적 2·심층 지적 2)
- 조작: `/chatbot` 에서 「데이트레이딩 전략 알려줘」, 「기아는 어때?」, 「005930은 어때?」를 차례로 보낸다.
- 기대: 첫 답변은 「[종목 조회 컨텍스트] 없음」. 두 번째는 `## [종목 상세 데이터: 기아 (000270)]` 와 `2026-09-21: 종가 120,000`,
  「과거 VCP 포착 이력 없음」. 세 번째는 삼성전자 상세 자료.
- 필수 여부(required): 예
- 실제: 「데이트레이딩 전략 알려줘」 → `[종목 조회 컨텍스트] 없음`. 「기아는 어때?」 → `[종목 상세 데이터: 기아 (000270)]`, `2026-09-21: 종가 120,000 | 거래량 800,591 | 등락 -1,500`, `3. VCP 시그널 이력` `과거 VCP 포착 이력 없음`. 「005930은 어때?」 → `[종목 상세 데이터: 삼성전자 (005930)]` 와 S-1 과 같은 주가·수급 행
- 결과: 통과
- 증거: `chat032-s3.png`
- 정리(cleanup): S-1 과 같다

### S-4. 웰컴·도움말에서 지운 경로가 드러나지 않는다 (인접)
- 조작: 격리 Flask 에 `GET /api/kr/chatbot/welcome` 을 보내고, `/chatbot` 에서 `/help` 와 `/refresh` 를 보낸다.
- 기대: 웰컴은 「Top 3」 없이 인사와 예시 문구만. `/help` 목록에 `/refresh` 가 없다. `/refresh` 는 「알 수 없는 명령어」 응답이다.
- 필수 여부(required): 예
- 실제: `GET /api/kr/chatbot/welcome` → `안녕하세요! **스마트머니봇**입니다 📈\n\nVCP 기반 수급 분석으로 투자 의사결정을 도와드릴게요.\n\n질문해주세요! 예: "오늘 뭐 살까?", "삼성전자 어때?"`(Top 3 없음). `/help` → `/status`·`/help`·`/clear`·`/clear all`·`/model`·`/memory ...` 여섯 줄, `/refresh` 없음. `/refresh` → `⚠️ 알 수 없는 명령어입니다: /refresh /help로 사용법을 확인하세요.`
- 결과: 통과
- 증거: `chat032-s4.png`, 위 응답 원문
- 정리(cleanup): 조회와 명령 응답뿐이라 소유한 자료 없음

### S-5. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-4 를 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와 `get_compilation_issues` 를 보낸다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다.
- 필수 여부(required): 예
- 실제: `console --clear` 는 S-1 전에 한 번 했고 그 뒤 두 화면(`/chatbot`, `/dashboard/kr/vcp`)을 거쳐 `console --errors` → `(no console errors)`. `/_next/mcp` `get_errors` → `{"configErrors":[],"sessionErrors":[]}`, `get_compilation_issues` → `{"issues":[]}`
- 결과: 통과
- 증거: 위 출력 원문
- 정리(cleanup): 조회 전용

## 이월한 발견

- `[CHAT-038]`(P2): 독립 단어로 쓰인 짧은 종목명(대상·전방·남성·동양·TP·DB 등)이 종목 질의로 잡힌다. 가격이 티커와 같으면 티커 갈래가 이름보다 먼저 이긴다. 두 글자 이하 이름 뒤의 두 글자 조사는 놓친다(코드 리뷰 지적 2, 심층 리뷰 유보 사항).
