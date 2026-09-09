# CHAT-013 · CHAT-015 · FE-038 묶음

- 사용자 근거: 현재 턴의 「연관된 라운드들 쭉 이어서」「최대한 한번에 묶어서」 및 AGENTS AUTO-CONTINUE. bounded 설계를 대화에 제시하고 명확하고 가역적인 로컬 작업을 진행한다. 별도 승인 응답을 받은 것으로 꾸미지 않는다.
- 설계: 스트림 완료까지 busy, 중복 전송 거부, 중단/세션 전환 뒤 이전 요청의 delta/JSON/error/finally 차단. 신규 세션 자동 배정 유지. 파서 제목 줄 보존, 공통 번호목록 분리, 추천 3개/120 code point. Sidebar·ChatWidget은 기존 getAuthHeaders 재사용.
- FE-038의 VCP는 이미 공용 helper를 사용하지만 종목 대화 ID를 X-Session-Id에 덮어쓰는 기존 계약이 있다. 세 화면의 값이 무조건 동일하다고 주장하거나 그 계약을 변경하지 않는다. 이번 회귀 검사는 남은 두 호출과 공용 profile 요청의 browser ID 일치를 검증한다.
- 티어: 위험 경로 없음. CHAT-013 T2, CHAT-015 및 FE-038 T1 예상, 묶음 T2 검토·전체 검사 공유. 실제 production diff로 재판정.
- 변경 소유: executor test_stability_impl(useChatStream 및 회귀), executor vcp_plan(parser 및 회귀), 부모(Sidebar/ChatWidget/헤더 회귀 및 QA/기록).
- 스킬: dev-cycle, brainstorming(bounded), TDD, vercel-react-best-practices(요청 수명주기와 상태), Next 번들 05-server-and-client-components·06-fetching-data(브라우저 경계/조회), code-review, ultraqa(app-adapted), agent-browser.
- 리뷰 상한 각 15분, 전체 QA 45분. 같은 실패3회/전체5회 중단 규칙 유지.
- 안전: 3500/5501/live 사용 금지, .env/data 원본 복사 금지. 격리 Next + 합성 HTTP만, 실제 LLM·거래·설정·삭제 없음. root package.json 사용자 파일 보존. OMX writable scope 없음: state 명령 사용하지 않음.

- 확정 production diff: 191줄(추가141+삭제50), 위험 경로 없음, 묶음 T2. ponytail APPROVE(원문 보존); 원문의 existing suggestion cap은 기존값이 아니라 이번에 새로 추가한 3/120 제한이며 low-confidence 문단의 confidence 표기는 모순이 있어 사실 판정 근거로 사용하지 않는다.

- 독립 리뷰: ponytail APPROVE → code-review lane APPROVE + architect lane CLEAR. 두 읽기전용 child에 설치된 역할 prompt를 적용한 대체 호출이며 전용역할 호출 성공으로 주장하지 않는다. 각 원문과 입력hash 보존.
- 발견 및 보완: queued React setter가 finally 이후 sending=false를 보면 정상 JSON/종료 SSE도 버렸다. RED2건 확인 후 request token과 전송 lock을 분리, 최종 full vitest460 통과.

- QA내 추가 범위: ThinkingProcess.tsx 및 실제 ChatMessage 통합회귀. CHAT015의 원래 필수 추론제목 보존을 완성하기 위한 기존호출부 보완. production추가18줄로T2유지. 중간ponytail판정은 이후dense목록회귀발견으로최종승인에재사용하지 않는다.
