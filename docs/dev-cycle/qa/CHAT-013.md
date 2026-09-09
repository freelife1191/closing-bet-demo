# UltraQA Report

# CHAT-013 QA 시나리오

- engine: ultraqa
- lifecycle: app-adapted
- phase: planning
- iteration: 1
- same_failure_count: 0
- baseline: pytest 2281 통과·2 skip / vitest 460 통과 / typecheck exit0 / lint 0 errors·198 warnings
- browser_applicability: required
- browser_driver: agent-browser
- namespace: chat-batch-20260909 / session: qa
- URL: http://127.0.0.1:57401/chatbot (FE-038은 /)
- 기준: 첫 구현 커밋 뒤 git archive와 변경 파일 SHA-256 대조
- 안전/목표: [범위](../evidence/chat-batch-20260909/scope.md). 실제 Next UI+합성 HTTP; LLM/IdP/실제 저장소 미검증.
- cleanup: 미실행
- 결과: 미실행

## S-1. 첫 청크 이후 중단 및 중복 전송 차단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 합성 대화 A에서 long 질문 전송, 첫 chunk 이후 Enter 재전송 시도, 답변 중단 클릭
- 기대: 중단 버튼 유지, POST 한 건, 중단 문구, 추가 chunk 없음
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-2. 세션 전환과 오래된 응답 차단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: long 응답 중 합성 대화 B 클릭, A의 후속 chunk 전송 후 B에서 새 질문
- 기대: B 기록 보존, A delta/오류 미노출, B 응답 완료
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-3. 신규 세션·정상 완료·재시도
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 새 진입에서 normal 응답 전송, 서버 세션 배정 및 완료 후 다음 전송
- 기대: 세션 배정 유지, 각 응답 분리, 완료 후 전송 가능
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-4. 모바일 중단
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 375px 챗봇에서 long 첫 chunk 수신 후 중단
- 기대: 중단 버튼 클릭 가능, 정상 중단 문구
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-5. 정적 검사·오류·정리·원본 보존
- 필수 여부(required): 예
- 모델: dirty worktree, 오해를 부르는 성공 출력
- 조작/하네스: pytest/vitest/typecheck/lint 종료 코드 대조, Next MCP와 브라우저 오류 확인, owned 프로세스 종료·포트 해제·scratch 제거·root package hash 확인
- 기대: 필수 검사 성공, 예상하지 않은 오류 없음, 원본 hash 동일, 소유 runtime 제거
- 실제: 미실행
- 결과: 미실행
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 미실행
