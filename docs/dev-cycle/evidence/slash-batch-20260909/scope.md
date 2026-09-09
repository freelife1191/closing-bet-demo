# CHAT-008·009 승인 범위

- 실제 대화 근거: 직전 두 항목 bounded 설계에 대한 사용자 `승인` 응답. 승인 시각 자체는 추정하지 않는다.
- 설계: 모델 미호출 슬래시 명령은 차감하지 않는다. 파일 첨부·앞공백 등 실제 모델 경로와 구분한다. 세션 제목은 첫 비명령 질문으로 만든 뒤 유지한다. 과거 자료 일괄 수정 없음.
- 티어 T2 공유 검토. 스키마·공통 SQLite·신원확정·시크릿 파일 변경 없음.
- 사용자 소유 루트 package.json 보존, develop 유지. 원본3500/5501·live 접근/재기동 없음. 실제 .env/data를 복사하지 않음.
- 테스트와 QA는 git archive 격리 사본, 외부 네트워크 차단, 원본 쓰기 차단. LLM 최외곽 경계 대역, 실제 UI와 변경한 서버 로직 유지.
- 절차: TDD RED/GREEN → ponytail 독립 검토 → code-reviewer/architect → 전체 pytest/Vitest 및 lint/typecheck → 첫 커밋 → UltraQA App 대응 및 agent-browser → 소유 환경 정리 → 아카이브.
- 상한: 개별 정적검사300초, 독립리뷰 각15분, QA 최대5회/동일실패3회. 되돌릴수있는 범위 내 재시도만 수행.

## 검증 준비 보완
- title 추가경계 RED: 기본제목과 같은 첫질문 덮어쓰기 및 첨부꼬리말추측을 재현한 뒤 수정했다.
- quota SESSION_REQUIRED 신규검사의 최초500은 Accept 누락으로 legacy JSON분기를 선택한 fixture문제. SSE Accept명시후 기존400계약을 검사한다.
- fixture 담당의 /clear 기록제거 제안은 승인범위와 다르므로 채택하지 않는다. 기존 /clear user/model2개 기록을 보존하고 일반질문후 history4개를 기대하도록 하네스의 잘못된 가정을 바로잡았다. 제품 저장행위를 테스트에맞춰 삭제하지 않았다.
