# VCP-022 실제 분석 경로 — UltraQA App 대응

범위: 구형 모의 생산 중단, 정확한 템플릿 조회 제외, 실제 VCP 엔진 재사용, 실패/과거 저장 보존, 구형 개인키 API 410. 사용자 승인 판단 위임과 critic ACCEPT 설계에 따른다. 특정 20260211 실행 요청 귀속은 조사 자료 없이 확정하지 않는다. 이번 라운드 시작 전 별도 역사 귀속 요구는 비상용 프로젝트의 재발 방지 완료 기준에서 제외했으며 QA 실패를 사후 면제하는 것이 아니다.

실행: Codex App에서 ultraqa 절차를 수행하고 OMX tmux/runtime state는 사용하지 않는다. 사용자 지정 ego-browser Space20/p1 재사용. 실제 외부 AI 품질/운영 데이터 검증은 포함하지 않는다. 실제 클래스·parser·writer·병합·화면을 실행하되 외부 모델 transport와 시장 자료만 합성한다.

| ID | 필수 시나리오 | 기대 결과 | 결과 |
|---|---|---|---|
| V1 | 구형 Gemini/GPT 키 유무와 정확 템플릿 3종 | 생산 None, 전체 템플릿 차단, 한 글자 변형·정상 문장 보존 | PASS: 정확 template 제외·정상75 유지 |
| V2 | 실제 VCP batch/model transport/parser/writer | 합성 transport 1회, 외부0, confidence75 저장 | PASS: 실제 Gemini class 합성 transport1·external0 |
| V3 | None/실패/부분 실패/빈 대상 | 이전 provider/news/다른 ticker와 파일 보존 | target PASS |
| V4 | 과거 실행 및 메모리 날짜선택 | 과거 dated만 갱신, latest 바이트 보존, 대상 날짜만 선택 | target PASS |
| V5 | VCP+AI 통합 선택 | 대상0 done, 날짜/ticker 불일치 error, 추가 모델0·쓰기0 | target PASS |
| V6 | 구형 개인키 API | 410, 파싱·쿼터·모델 호출0, 현재 VCP 경로 유지 | PASS: 실제 route410 |
| V7 | merged/raw UI 경로 및 정상 복구 | 정확 템플릿 미노출, 정상75/실제엔진 합성75, JS 오류 없음 | PASS: 4모드/8탭 확인·이미지4개 직접검토 |
| V9 | 날짜 조회 경로 탈출·빈값·잘못된 달력 | 파일 조회0, HTTP400, 정상ISO/compact 허용 | PASS: target29·브라우저4종400 |
| V8 | 전체 회귀/리뷰/정리 | 필수 검사 통과·원본 보존·소유 프로세스 종료·Space finish1 | PASS: 전체검사·정리·브라우저finish1 |

한도: 최대5 QA cycle, 동일 원인3회 실패 시 중단. 명령300초 이하. 최초 source-import 순환 오류·테스트 property setter 오류와 수정 이력은 progress.md 및 원문 로그에 보존한다. 원본 env/data/logs/3500/5501/live 미접근, root package 해시 보존. 조건부 완료 문구를 쓰지 않으며 모든 필수행 완료 전 TODO 유지.

## 최종 결과

필수9/9 PASS, UltraQA App 대응2 cycles. cycle1은 분석 없음 상태에서 숨겨진GPT탭을 클릭한 테스트 locator 실패다. 화면 상태를 읽어 legacy/raw는Gemini빈상태만, 정상/generated는3탭을 확인하도록 수정하고 cycle2 전체를 재실행했다. 제품 코드는 첫 커밋80770ac 이후 불변이다.

- pytest2458 passed/3 skipped, Vitest640/83파일, typecheck0, lint0errors/184기존warnings, build3/3.
- 정상문장과 실제VCP Gemini엔진+합성transport 결과75%, legacy/raw는미산출·AI분석데이터없음. generated모드의다른두탭은같은Gemini결과를복제한UIfixture이며 GPT/Perplexity모델실행을뜻하지않는다.
- 실제route에서구형API malformed JSON도410,날짜4종400. 단위경계9검사에서는loader0과정상고정basename 확인.
- JS error/unhandledrejection/console.error 행렬8탭모두빈배열. Next MCP configErrors/sessionErrors/compilation issues 모두빈배열.
- 합성 model transport1회 뒤None실패를주어기존JSON바이트보존. 외부요청0은OS 네트워크차단과합성boundary로보장한다. 원본시크릿/자료/서비스실행없음.
- root/scratch/80770ac frozen27경로일치(삭제null포함),사용자package해시보존. 소유fixture2PID/Next/gateway종료,57990~92닫힘,scratch삭제,공유Space20 finish정확히1회.
- 판정: ponytailSHIP,codeAPPROVE,architectWATCH(비차단역방향privateimport),securityREJECT→수정→APPROVE,T3REJECT→수정→ACCEPT. 별도외부CLI실행아닌native체크리스트검토. Python LSP진단은실행하지않았고pytest를LSP성공으로표기하지않음.

ULTRAQA COMPLETE: Goal met after 2 cycles. 독립 최종 증거 검수는 final-verifier.md에 이어 기록한다.
