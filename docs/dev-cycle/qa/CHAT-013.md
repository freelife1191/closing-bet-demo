# UltraQA Report

# CHAT-013 QA 시나리오

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

## S-1. 첫 청크 이후 중단 및 중복 전송 차단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 합성 대화 A에서 long 질문 전송, 첫 chunk 이후 Enter 재전송 시도, 답변 중단 클릭
- 기대: 중단 버튼 유지, POST 한 건, 중단 문구, 추가 chunk 없음
- 실제: 신규 batch-new 세션에서 첫 chunk 표시 후 중단 버튼 유지. 두번째 입력 Enter가 POST를 추가하지 않았고 중단 후 버튼 소실·종료 문구 확인. iteration3/4에서도 첫chunk후중단 재검증.
- 결과: 통과
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 long2-chunk.txt, duplicate-tree.txt, headers-verification.json, stopped2-state.txt, clean4-stopped-state.txt, clean4-stopped.png
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-2. 세션 전환과 오래된 응답 차단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: long 응답 중 합성 대화 B 클릭, A의 후속 chunk 전송 후 B에서 새 질문
- 기대: B 기록 보존, A delta/오류 미노출, B 응답 완료
- 실제: A에서 첫chunk를 받은 뒤 B를 클릭. B 고유 기록과 B 정상 JSON 응답만 남고 A의 지연 본문 없음. mock reader의 늦은 delta/finally는 회귀 검사로 보강.
- 결과: 통과
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 switch-before.txt, switch-after.txt, b-state.txt, session-b.png, chat013-target-green-final.txt.gz
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-3. 신규 세션·정상 완료·재시도
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 새 진입에서 normal 응답 전송, 서버 세션 배정 및 완료 후 다음 전송
- 기대: 세션 배정 유지, 각 응답 분리, 완료 후 전송 가능
- 실제: 신규 session=batch-new 배정 후 정상 SSE 완료, 다음 정상 JSON 전송 성공.
- 결과: 통과
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 normal-state.txt, final-parser-state.txt, final-normal-answer.txt, clean4-normal.txt
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-4. 모바일 중단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 375px 챗봇에서 long 첫 chunk 수신 후 중단
- 기대: 중단 버튼 클릭 가능, 정상 중단 문구
- 실제: 375x812에서 버튼 rect x311/y716/40x40, 첫chunk후실제클릭으로 종료 문구 표시.
- 결과: 통과
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/의 mobile-stop-rect.txt, mobile-stop-tree.txt, mobile-stopped.txt, mobile-stopped.png
- cleanup: 완료(두 scratch 제거, 전용 browser close, 소유 process group 종료·포트해제)

## S-5. 정적 검사·오류·정리·원본 보존
- 필수 여부(required): 예
- 모델: dirty worktree, 오해를 부르는 성공 출력
- 조작/하네스: pytest/vitest/typecheck/lint 종료 코드 대조, Next MCP와 브라우저 오류 확인, owned 프로세스 종료·포트 해제·scratch 제거·root package hash 확인
- 기대: 필수 검사 성공, 예상하지 않은 오류 없음, 원본 hash 동일, 소유 runtime 제거
- 실제: pytest2281/2skip, 최종vitest462/67files, type0/lint0errors198warnings. iteration3 URL없는SyntaxError1건은 보존; clean4에서 익명·인증상태 parser/stream/normal 및 각 단계오류0, Next config/session오류0. cleanup완료·원본packagehash동일.
- 결과: 통과
- 증거: ../evidence/chat-batch-20260909/의 baseline.json, browser-verification.json, clean4-final-errors.txt, clean4-next-errors.txt, clean4-cleanup.json
- cleanup: 완료(cleanup.json 및 clean4-cleanup.json)

## 실행 결과
- 필수 시나리오: 통과 5 / 전체 5
- 미통과 필수: 없음
- source: 212c719 (최초), 20869d0 (QA수정). final-source-verification.json·clean4-source.json으로 hash 일치.
- iteration2의 FE038/세션전환/모바일 결과는 해당경로hash변경없음 확인후유지. ThinkingProcess 영향은 iteration3/4 parser·중단 및 전체vitest462로재검증.
- 프레임워크 get_compilation_issues는 Webpack에서 -32602 미제공, PASS아님. 실제build를포함한Vitest와 Next get_errors로보완.
- 잔여 한계: 실제 LLM/IdP/backend저장·backend작업취소 미검증. iteration3 단발SyntaxError 원인은미확정이며 새환경에서는재현되지않음. 기록을삭제하거나제품수정성공으로주장하지않음.
- 재개 판정: 완료 가능
- ULTRAQA COMPLETE: Goal met after 4 cycles
