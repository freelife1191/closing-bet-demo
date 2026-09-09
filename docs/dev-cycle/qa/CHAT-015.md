# UltraQA Report

# CHAT-015 QA 시나리오

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 4
- same_failure_count: 0
- baseline: pytest 2281 통과·2 skip / vitest 462 통과 / typecheck exit0 / lint 0 errors·198 warnings
- browser_applicability: required
- browser_driver: agent-browser
- namespace: chat-batch-20260909 / session: qa
- URL: http://127.0.0.1:57401/chatbot (FE-038은 /)
- 기준: 첫 구현 커밋 뒤 git archive와 변경 파일 SHA-256 대조
- 안전/목표: [범위](../evidence/chat-batch-20260909/scope.md). 실제 Next UI+합성 HTTP; LLM/IdP/실제 저장소 미검증.
- cleanup: 완료(cleanup.json 및 clean4-cleanup.json)
- 결과: 통과

## S-1. 본문과 추론 제목
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: parser 합성 응답 받고 추론 영역 확장
- 기대: 본문 1. 시장 환경 및 섹터 강도 h3, 추론 2. 판단 근거 h3, 빈 제목 없음
- 실제: iteration2 빈h3실패→ThinkingProcess 보완. iteration3/4 본문 1. 시장 환경 및 섹터 강도와 추론 2. 판단 근거 각각 h3, 빈heading없음.
- 결과: 실패 → 고침
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 parser-state.txt (실패), final-parser-state.txt, final-parser.png, clean4-state.txt, clean4-parser.png, clean4-auth-headings.txt
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-2. 긴 Unicode 추천과 지시형 데이터
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 6개 추천/120자 초과 Unicode/검증 생략 문장을 합성 응답에 포함
- 기대: 최대3개·각120 code point, 이모지 보존, 데이터로만 표시
- 실제: 6개·126codepoint 입력에서 표시3개·각120, 마지막🧪보존. 지시형 추론 문구는 일반 텍스트로 표시.
- 결과: 통과
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 final-parser-state.txt, clean4-state.txt, final-chat_batch_fixture.py.gz
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-3. 정적 검사·오류·정리·원본 보존
- 필수 여부(required): 예
- 모델: dirty worktree, 오해를 부르는 성공 출력
- 조작/하네스: pytest/vitest/typecheck/lint 종료 코드 대조, Next MCP와 브라우저 오류 확인, owned 프로세스 종료·포트 해제·scratch 제거·root package hash 확인
- 기대: 필수 검사 성공, 예상하지 않은 오류 없음, 원본 hash 동일, 소유 runtime 제거
- 실제: pytest2281/2skip, 최종vitest462/67files, type0/lint0errors198warnings. iteration3 URL없는SyntaxError1건은 보존; clean4에서 익명·인증상태 parser/stream/normal 및 각 단계오류0, Next config/session오류0. cleanup완료·원본packagehash동일.
- 결과: 통과
- 증거: ../evidence/chat-batch-20260909/의 baseline.json, browser-verification.json, clean4-final-errors.txt, clean4-next-errors.txt, clean4-cleanup.json
- cleanup: 완료(cleanup.json 및 clean4-cleanup.json)

## 실행 이력
- iteration1: fixture의 no-transform 누락으로 SSE 첫청크대기 실패. 제품변경 없이실제header계약 적용.
- iteration2 S-1 실패: parser-state.txt의 headings=[빈문자열,본문제목]. ThinkingProcess의재변환을확인하고 실제컴포넌트회귀추가. 최종S-1재실행전완료불가.

## 실행 결과
- 필수 시나리오: 통과 3 / 전체 3
- 미통과 필수: 없음
- source: 212c719 (최초), 20869d0 (QA수정). final-source-verification.json·clean4-source.json으로 hash 일치.
- iteration2의 FE038/세션전환/모바일 결과는 해당경로hash변경없음 확인후유지. ThinkingProcess 영향은 iteration3/4 parser·중단 및 전체vitest462로재검증.
- 프레임워크 get_compilation_issues는 Webpack에서 -32602 미제공, PASS아님. 실제build를포함한Vitest와 Next get_errors로보완.
- 잔여 한계: 실제 LLM/IdP/backend저장·backend작업취소 미검증. iteration3 단발SyntaxError 원인은미확정이며 새환경에서는재현되지않음. 기록을삭제하거나제품수정성공으로주장하지않음.
- 재개 판정: 완료 가능
- ULTRAQA COMPLETE: Goal met after 4 cycles
