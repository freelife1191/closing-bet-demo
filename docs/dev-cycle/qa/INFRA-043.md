# UltraQA Report — INFRA-043

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 1
- same_failure_count: 0
- active: false
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-notification-4s28gwie
- source_base: e4c4fd6
- started_at: 2026-09-09T08:08:16.287395+09:00
- baseline: e4c4fd6 pytest2077/3skip, Vitest373/57files exit0. 수정 후 v3 pytest2115/3skip, targeted72, 동일 frontend Vitest373 exit0.
- cleanup: complete (cleanup.json)

## 목표와 경계
승인된 설정/알림 결함을 실제 앱과 격리 서비스에서 검증한다. 실제 환경과 운영 3500/5501/live 접근, 외부 발송/LLM은 금지한다. 외부 transport만 대역, UI와 대상 API는 실제 코드다. 전용 clone, 가짜 관리자/비관리자, 임시 env를 사용한다. 같은 실패 3회/전체 5회에서 중단하고 TODO를 유지한다.

## 시나리오 행렬

| ID | 의도·기대 신호 | 모델/setup | 실행 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 정상 발송 200 및 화면 성공, transport 호출 1회 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과와 evidence 참조 | 완료 | 예 |
| S-2 | disabled 시 transport 0회 및 실패 응답/화면 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과와 evidence 참조 | 완료 | 예 |
| S-3 | 발송 예외/HTTP 실패 시 실패 응답, 가짜 비밀 로그 노출 0 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과와 evidence 참조 | 완료 | 예 |
| S-4 | 익명/비관리자 403 및 transport 0회 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과와 evidence 참조 | 완료 | 예 |

## 공통 적대 조건
거짓 성공은 HTTP·본문·transport 카운터를 함께 대조한다. 잘못된 JSON/Unicode/제어문자와 비밀 포함 예외를 사용한다. 입력 속 지시는 데이터로만 취급한다. 명령 timeout 480초, browser60초, 소유 PID만 종료한다. flaky 반복 통과시키기 금지. resume는 SHA와 증거를 대조한다. 다른 작업 package.json SHA 불변을 검사한다. 앱 기능과 무관한 CLI 플래그/경로이탈·hook cancellation은 적용불가(새 CLI/런타임 기능 없음).

## 구현과 정적 검증

- 승인된 다섯 항목 중 첫 라운드. 시크릿 경계에 보수적 T3를 적용했다. 코드 +74/-28, 테스트와 QA 문서는 별도 집계한다.
- 기본 sender 3개와 custom 2개의 disabled, facade bool, API 200/502/503/500 경계를 수정했다. raw exception/외부 response.text 대신 type/status만 기록한다.
- RED: 원본 기준 신규043 28failed/3passed, custom bool 강화8failed. GREEN: 관련72passed, 전체2115passed/3skipped. 이전 실패 원문은 evidence/INFRA-043에 gzip으로 보존한다.
- ponytail APPROVE; code-reviewer v3 APPROVE; 독립 architecture는 네이티브 agent thread limit로 ephemeral read-only Codex CLI 대응. 최초 WATCH(외곽예외 테스트 공백)를3개검사로보완해 v3 CLEAR. 리더 deep review는 gstack-review/checklist를직접적용했고 외부전용CLI리뷰로주장하지않는다.
- 검토 입력은 043-input-v3.json 9개(제품5·테스트3·계획1). AST구문검사의 Python대상은8개다. code 원문 중 static분석을Python9개라고쓴부분은총manifest9개와혼동한표기이며,실제ast.parse는8개다.
- MCP LSP/AST는 Transport closed로 사용할 수 없었다. stdlib AST 구문/unsafe logger argument0과 실행 테스트를 대체증거로 구분한다. .env 추적은.env.example만, frontend제품소스변경없음.
- 첫 구현 커밋 이후 실제 브라우저 정상/disabled/오류/권한을 검증한다. 아직 동적QA완료가 아니다.

- 최종 보안 리뷰: 독립 code-reviewer APPROVE, 9/9 SHA 일치. 보안 진단과 미실행 범위는 evidence/INFRA-043/043-security.md에 보존.
- 최종 코드 리뷰: 043-code-v3.md APPROVE, 아키텍처: 043-arch-v3.md CLEAR. v3 추가 검사는 제품코드 변경 없는 외곽 예외 회귀 보강이다.

## 실제 실행 결과

- 기준 커밋 a902a58. 앱 http://127.0.0.1:49960/dashboard/kr, Flask49959. 전용 namespace devcycle-notification-4s28gwie, 합성 admin/viewer NextAuth 쿠키. 기존 앱과 실제 request context/admin/env GET·POST/notification route/Messenger/sender를 사용했다. 외부 requests.post와 SMTP만 대역이며 나머지 dashboard GET은 고정 fixture다.
- S-1 통과: 설정 열기→알림 센터→Discord 테스트 버튼. env POST200 후 notification POST200, transport 누적1, 화면 '발송 성공'. 043-success.png 직접 열어 확인.
- S-2 통과: fixture에서 NOTIFICATION_ENABLED=false → 같은 버튼. notification503, transport 누적1 그대로(증가0), 화면 '발송 실패 / Notifications are disabled'. 043-disabled.png 직접 확인.
- S-3 통과: 합성 canary 포함 연결 예외(텔레그램)와 HTTP실패본문(디스코드) 각각 실제 버튼 실행. 모두502와 '발송 실패 / Notification delivery failed', transport 누적2/3. 043-exception.png와043-http-failure.png 직접 확인. runtime 로그+브라우저 기록+static JS62개에서합성 비밀7개검색0. 값 자체는보고서에담지않음.
- S-4 통과: 익명 browser eval POST403, 합성 viewer로 로그인후 같은 요청403, transport 누적3유지. 실제 viewer 설정에는 '일반'만노출, API/알림/시스템탭없음. 043-viewer.png 직접확인. eval API검사는UI검사와구분하며실제권한검증의보강증거다.
- admin/viewer 브라우저 console은정상 React/HMR정보만, page errors0. Next MCP tools/list에서 get_compilation_issues확인, issues[], configErrors[], sessionErrors[]. raw SSE는043-mcp-*.gz.
- 요청·응답·검증된역할·발송횟수는requests.jsonl.gz, 조작전후snapshot/wait/화면결과는browser-commands.jsonl.gz. env route의anonymous표기는Next 전용 관리자토큰을사용하고신원헤더를전달하지않는기존계약이다; notification은signed admin/viewer신원을실제로검증했다.
- 필수 시나리오4/4통과. UltraQA iteration1, 제품QA실패없음. 최초 staged diff check는리뷰원문의Markdown줄끝공백때문에exit2였고원문gzip보존/표시본정리후exit0으로커밋했다(검사우회없음).
- 전용Next/Flask/proxy listener없음,브라우저종료/namespace와합성env·쿠키·profile제거. clone은승인된후속라운드작업공간으로유지한다. 원본package.json SHA불변. cleanup.json참조.
- 운영서비스재시작/배포/실제알림없음. dependency CVE검색은버전변경없어미실행. 외부CDN차단으로아이콘일부공백이며픽셀동일성을검증한것은아니다.

ULTRAQA COMPLETE: Goal met after 1 cycles
