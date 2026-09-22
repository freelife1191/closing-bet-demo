# [CHAT-032] 종목 질의 문맥이 언제나 비는 경로 복구 — QA 시나리오

- 대상 화면: http://localhost:3720/chatbot, http://localhost:3720/dashboard/kr/vcp (격리 Next). 백엔드는 격리 gunicorn http://127.0.0.1:5720
- 구성 근거: `[CHAT-032]` 의 QA 줄(「삼성전자 어때?」 → 최근 5일 종가와 외국인·기관 순매수 인용) + 설계 승인(종목 맵 연결, 빈
  vcp_stocks 경로 제거) + 코드 리뷰 지적 2(짧은 종목명 오탐)·6(맵에 없는 티커) + 심층 리뷰 지적 2(조사 붙은 티커).
  기대값은 원본 `data/` 를 pandas 로 읽기 전용으로 읽어 정했다(`daily_prices.csv`·`all_institutional_trend_data.csv`·
  `signals_log.csv` 의 005930·000270 최근 5행). 1단계 리포트 도구 대신 이 값과 TODO 의 QA 줄에서 시나리오를 만들었다
  (`[FLOW-019]` 와 같은 방식)
- 구성 2026-09-23 | 실행 (결과 공란)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. 원본 3500/5501·live 주소·원본 `.env` 는 쓰지 않는다. 챗봇 전송은
  LLM 비용과 기록이 남는 조작이므로 원본에서 하지 않는다. 저장소 작업 트리를 scratchpad `qa-chat032/` 로 복사(`.env*`·`.git`·
  `venv`·`logs` 제외, `frontend/node_modules` 는 APFS clone)하고, 사본에만 QA 전용 진입점 `qa_flask_app.py` 를 둔다. 이
  진입점은 `engine.genai_client.build_genai_client` 를 가짜 클라이언트로 바꾼다. 가짜 클라이언트는 모델이 받을 마지막 content
  part 에서 `[종목 조회 컨텍스트]` 절만 잘라 답변으로 돌려주고(없으면 「[종목 조회 컨텍스트] 없음」), 「## VCP 상위 종목」 절이
  프롬프트에 있는지를 한 줄로 덧붙인다. 그래서 화면의 답변이 곧 모델이 받은 종목 자료다(`[CHAT-031]` 의 방식). 더미 값
  (`NEXTAUTH_SECRET=qa-nextauth-secret`, `INTERNAL_IDENTITY_SECRET=qa-identity-secret`, `ADMIN_EMAILS=qa-admin@example.com`,
  `SCHEDULER_ENABLED=false`, 쿼터 가드의 「서버 키 있음」 판정용 `GOOGLE_GENAI_USE_VERTEXAI=true`·`GOOGLE_CLOUD_PROJECT=qa-stub`)만
  환경 변수로 준다. VCP 화면에서는 종목 선택과 채팅 입력만 하고 Refresh·재분석·모의 매수 버튼은 누르지 않는다
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0회
- 결과: (공란)
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
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 격리 사본의 챗봇 저장소에만 대화가 남는다. 사본 삭제로 정리

### S-2. VCP 상담 모드의 `[종목명(티커)]` 접두가 선택 종목 자료를 싣는다 (회귀)
- 조작: `/dashboard/kr/vcp` 에서 삼성전자 행을 선택하고 채팅 입력에 「전망은?」을 보낸다.
- 기대: 요청 본문 message 가 `[삼성전자(005930)] 전망은?` 이고, 답변에 S-1 과 같은 삼성전자 상세 자료가 보인다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): S-1 과 같다

### S-3. 짧은 종목명은 단어로 쓰일 때만 잡힌다 (인접, 리뷰 지적 2·심층 지적 2)
- 조작: `/chatbot` 에서 「데이트레이딩 전략 알려줘」, 「기아는 어때?」, 「005930은 어때?」를 차례로 보낸다.
- 기대: 첫 답변은 「[종목 조회 컨텍스트] 없음」. 두 번째는 `## [종목 상세 데이터: 기아 (000270)]` 와 `2026-09-21: 종가 120,000`,
  「과거 VCP 포착 이력 없음」. 세 번째는 삼성전자 상세 자료.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): S-1 과 같다

### S-4. 웰컴·도움말에서 지운 경로가 드러나지 않는다 (인접)
- 조작: 격리 Flask 에 `GET /api/kr/chatbot/welcome` 을 보내고, `/chatbot` 에서 `/help` 와 `/refresh` 를 보낸다.
- 기대: 웰컴은 「Top 3」 없이 인사와 예시 문구만. `/help` 목록에 `/refresh` 가 없다. `/refresh` 는 「알 수 없는 명령어」 응답이다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회와 명령 응답뿐이라 소유한 자료 없음

### S-5. 콘솔 오류와 컴파일 문제가 없다 (인접)
- 조작: `console --clear` 뒤 S-1~S-4 를 마치고 `console --errors` 를 읽는다. `/_next/mcp` 에 `get_errors` 와 `get_compilation_issues` 를 보낸다.
- 기대: 콘솔 오류 0, `/_next/mcp` 응답의 오류·컴파일 문제 목록이 비어 있다.
- 필수 여부(required): 예
- 실제:
- 결과:
- 증거:
- 정리(cleanup): 조회 전용
