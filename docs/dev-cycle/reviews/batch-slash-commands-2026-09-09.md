# CHAT-008·009 묶음 검토

## 승인과 범위
- 사용자: 직전 두 항목의 bounded 설계에 `승인`. dev-cycle/brainstorming 설계 후 동일범위 구현·리뷰·검증 진행.
- CHAT-008: 파일없는 정확한슬래시명령6종과알수없는명령은 모델미호출이므로 quota한도/차감제외. 세션/서버설정/관리자가드보존. 앞공백·첨부는 기존모델경로. multipart의분류와파서해석을일치.
- CHAT-009: 신규세션의raw빈제목을미설정으로보존하고첫비슬래시질문에서정함. 외부목록에만기본문구표시. 기존제목·명령기록·스키마보존,과거자료일괄수정없음. 과거이미 /clear로정해진제목을자동교정하지않음.
- production변경31추가10삭제 예상(최종git통계확정). T2공유검토.

## 검증
- 테스트먼저재현후수정. 제목/쿼터/multipart대소문자/기본문구충돌+50절단+재시작 RED원문보존.
- 최종정적: pytest2296passed3skipped, Vitest459passed67files, lint0error194warnings, typecheckexit0, PythonAST7files통과. 실제PythonLSP사용불가,통과주장안함.
- ponytail: 중복코드정리와제거된스캔전용테스트정리후SHIP.
- code-reviewer: APPROVE,0issues. architect: 최종판정대기. 최초BLOCK은별도보존.
- UltraQA engine=ultraqa,lifecycle=app-adapted. 실제/chatbot→격리Flask제품라우트/저장소→fakeLLM. QA결과는 qa/CHAT-008.md와CHAT-009.md.
- 현재단계: 정적검증통과,QA진입준비. 완료아카이브없음.

## 증거
`../evidence/slash-batch-20260909/`의scope,review-input,검사JSON/log,독립리뷰원문,fixture,브라우저증거참조.
rootpackage사용자파일보존. 원본3500/5501/live/.env/data쓰기금지,현재소유scratch만조작/정리.
