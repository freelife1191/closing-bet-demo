# 테스트 격리 묶음 검수

- 완료 기록: 2026-09-09 20:51 KST. 소스 커밋 `38fab47`.
- FE-042 완료. INFRA-035 재발 방지 수정·검증 완료, 기존 파일 처리 결정은 TODO에 보존. TODO49→48 (P0 0/P1 11/P2 37).
- FE: Vitest가 실행하던 빌드2회·tsc3검사를 독립 `npm run test:build`로 이동. 빌드1회결과로 성공/5개필수라우트를 확인하며 타입검사까지3개 모두 유지. 기본 Vitest459개. 실제 전체검증에는 두 명령을 모두 실행한다.
- INFRA: 테스트의 직접 db_name 생성5개를 tmp_path로 변경. 자체 DB/WAL/SHM만정리하고 이웃파일보존. 공통helper/자동연결닫기는 이미 적용되어 추가 제품변경 없음.
- 코드/테스트 net -19줄 (FE -23, INFRA +4); README +9줄. 새 의존성/제품 API/UI 변경 없음.
- 독립 ponytail SHIP, code-reviewer APPROVE, architect 초기BLOCK→경로수정→CLEAR. 새 테스트 build/폴더가 ignore규칙에걸린 문제를 build-checks로해결하고 git추적/실제명령재검증.
- pytest2279passed/3skip, Vitest459passed/67files, Node빌드검증3passed/0skip, lint0errors194warnings, 타입검사exit0. Python LSP성공은 주장하지 않음.
- UltraQA App 대응 iteration1 필수5/5통과. 커밋소스해시일치, 동시빌드·Vitest2회모두통과, 가짜성공문구+exit7은Node검증실패로판정, data쓰기차단모의투자테스트86개통과, 정확한sidecar정리2회/이웃보존.
- 원본 package.json/소스해시불변. 원본data WAL/SHM27396개 이름해시불변. 소유프로세스0, scratch삭제. 원본서비스/실제LLM/시크릿/기존자료삭제 없음.
- 재현된현재오류는 동일.next 동시빌드충돌. 과거09-08원인까지확정하지 않음. 빌드검증끼리는 동일checkout에서동시실행하지않는다.
- 상세: [FE QA](../qa/FE-042.md), [INFRA QA](../qa/INFRA-035.md), [검토입력](../evidence/test-isolation-20260909/review-input.json), [정리증거](../evidence/test-isolation-20260909/cleanup.json).
