# FE-022·FE-039 검토 입력

기준 HEAD 2a37cfc. 기존 사용자 요청은 관련 TODO를 묶어 연속 처리하는 것이며, 앞선 프로필 묶음 제안 뒤 같은 요청으로 재개했다.
분류 bounded, 예상 T2: 위험 경로·인증 처리 자체는 변경하지 않고 기존 프로필 렌더링과 폼 상태를 맞춘다.

## 요구사항

- 비로그인 첫 화면은 공통 User 기본값. 저장된 로컬 프로필은 보존한다.
- Sidebar와 챗봇 표시 모두 authenticated 세션의 name/email 우선. 이 표시값을 편집 프로필에 덮어쓰지 않는다.
- 성공한 프로필 저장 이벤트가 두 진입 경로에 반영되고, 캐시가 없으면 기본값으로 돌아간다.
- 설정창은 저장된 알려진 직무/커스텀 직무/빈 직무를 정확히 복원한다.
- 직무 선택과 직접 입력은 저장 persona에 반영되고, 취소 후 다시 열면 마지막 저장값이 복원된다.
- 이름만 저장해도 직무를 보존한다. 시스템 탭의 persona도 같은 값이다.
- 원본 서버·실계정·.env·data·root package.json 불변. 새 의존성·타입 억제 없음.

## 검증

회귀 RED/GREEN, 전체 pytest/Vitest, typecheck/lint, ponytail 이후 code-reviewer/architect 독립 검토.
UltraQA App 대응 행렬: `docs/dev-cycle/qa/FE-022.md` 및 `docs/dev-cycle/qa/FE-039.md`.
agent-browser는 합성 HTTP 경계에 연결한 실제 Next UI를 조작한다. 원본 서버 3500/5501을 호출하지 않는다.
리뷰 단계별 15분, 라운드90분 상한. 시간 초과는 PASS가 아니다.
