# UltraQA Report

# CHAT-015 QA 시나리오

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

## S-1. 본문과 추론 제목
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: parser 합성 응답 받고 추론 영역 확장
- 기대: 본문 1. 시장 환경 및 섹터 강도 h3, 추론 2. 판단 근거 h3, 빈 제목 없음
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-2. 긴 Unicode 추천과 지시형 데이터
- 필수 여부(required): 예
- 모델: 일반 사용자, 합성 서버 응답
- 조작/하네스: 6개 추천/120자 초과 Unicode/검증 생략 문장을 합성 응답에 포함
- 기대: 최대3개·각120 code point, 이모지 보존, 데이터로만 표시
- 실제: 미실행
- 결과: 미실행
- 수정: 없음
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 전용 브라우저·프로세스·fixture 종료 예정

## S-3. 정적 검사·오류·정리·원본 보존
- 필수 여부(required): 예
- 모델: dirty worktree, 오해를 부르는 성공 출력
- 조작/하네스: pytest/vitest/typecheck/lint 종료 코드 대조, Next MCP와 브라우저 오류 확인, owned 프로세스 종료·포트 해제·scratch 제거·root package hash 확인
- 기대: 필수 검사 성공, 예상하지 않은 오류 없음, 원본 hash 동일, 소유 runtime 제거
- 실제: 미실행
- 결과: 미실행
- 증거: ../evidence/chat-batch-20260909/
- cleanup: 미실행
