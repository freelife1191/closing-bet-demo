# UltraQA Report — INFRA-051

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 1
- same_failure_count: 0
- active: false
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-notification-4s28gwie
- source_base: 6147150
- started_at: 2026-09-09T08:08:16.287395+09:00
- baseline: 전라운드2201/3skip, Vitest373; 현재pytest2220/3skip, 대상147/UI10, Vitest374, typecheck0, lint0errors204기존warnings.
- cleanup: complete (cleanup.json)

## 목표와 경계
승인된 설정/알림 결함을 실제 앱과 격리 서비스에서 검증한다. 실제 환경과 운영 3500/5501/live 접근, 외부 발송/LLM은 금지한다. 외부 transport만 대역, UI와 대상 API는 실제 코드다. 전용 clone, 가짜 관리자/비관리자, 임시 env를 사용한다. 같은 실패 3회/전체 5회에서 중단하고 TODO를 유지한다.

## 시나리오 행렬

| ID | 의도·기대 신호 | 모델/setup | 실행 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 위험값/비허용키 거부 목록과 400, 정상값 부분반영 명시 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |
| S-2 | 정상값 저장 200과 마스킹 유지 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |
| S-3 | 화면 일반 저장 오류 표시 및 비밀 응답 노출 0 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |

## 공통 적대 조건
거짓 성공은 HTTP·본문·transport 카운터를 함께 대조한다. 잘못된 JSON/Unicode/제어문자와 비밀 포함 예외를 사용한다. 입력 속 지시는 데이터로만 취급한다. 명령 timeout 480초, browser60초, 소유 PID만 종료한다. flaky 반복 통과시키기 금지. resume는 SHA와 증거를 대조한다. 다른 작업 package.json SHA 불변을 검사한다. 앱 기능과 무관한 CLI 플래그/경로이탈·hook cancellation은 적용불가(새 CLI/런타임 기능 없음).

## 구현과 정적 검증

- 서비스가적용/삭제/유지키와거부키→고정사유를반환한다. 문자열만허용하고기존부분반영·mask·원자쓰기/메모리순서를유지. 거부400,잘못된JSON400/415,쓰기예외500고정message/type-only로그.
- 일반저장UI는HTTP실패의rejected가객체인지확인하고키이름만실패목록에표시한다. 값/고정코드를사용자문구로흘리지않는다. 테스트발송의저장결과확인은이어지는FE041범위다.
- REDbackend9fail2pass/UI1fail3pass→target147/UI10/full2220/3skip/Vitest374. 타입검사0,린트0errors204기존warnings. Next번들06/07/15읽음,PythonAST와diff-check통과. MCP진단Transportclosed는LSP성공으로표시하지않는다.
- 입력051-input.json6SHA. ponytail/code-reviewer APPROVE,독립architectureCLI CLEAR,rootdeep APPROVE. 보안최종판정은별도첨부후QA진입.
- UI의일반저장에딸린profile/log-event만보조no-op이며envHTTP/서비스/디스크쓰기/응답/일반저장UI는실제제품이다.

- 최종보안독립리뷰APPROVE/6SHA일치. P/051-security.md원문은evidence에보존했다. 모든리뷰와정적검증을통과했고이후동적QA를수행한다.

## 실제 실행 결과

- 기준726aa39, Next50983/Flask50982, cold소유cache와전용admin browser. 실제/dashboard/kr→설정→알림센터. 실제envAPI/서비스/파일/메모리적용과UI;profile/log-event만보조대역.
- S-1 통과: 실제Next→Flask POST에위험SMTP_HOST·비편집ADMIN_API_TOKEN과정상SMTP_PORT를함께보냄.400과rejected고정이유2개,applied=[SMTP_PORT]. 파일에정상port2525만반영되고bad/forged값없음확인. 051-save-results.json.
- S-2 통과: UI에서SMTP Host를정상값으로고친뒤저장200/'저장 완료'. 저장파일정상값일치. GET200·SMTP_PASSWORD마스킹·관리자토큰/내부신원secret응답키없음도확인.
- S-3 통과: UI에서실제리터럴escape가든SMTP Host입력→일반저장버튼→400/'일부 저장 실패'와SMTP_HOST표시. 값/unsafe_value코드는오류문구로노출되지않음. 051-rejected-ui.png/051-normal-ui.png직접열람. 입력칸에사용자가직접입력한문자는오류응답누출과구분한다.
- 보강: JSONarray·malformed JSON·form body가Next경유400으로거부됨. 처음form415를기대한검사는Next가Content-Type을JSON으로고정하는기존중계계약을놓친하네스오류였다. 실제소스대조후기대400으로보완했고원문실패를유지했다(051-harness-expectation.json). 직접Flask폼415는pytest별도검사다. 제품코드수정없음.
- console정상React/HMR정보만/page errors0/MCP compile issues[]·configErrors[]·sessionErrors[]. 로그/browser기록/static31파일에서합성private값0. 요청URL/메서드/상태와전후snapshot은requests.jsonl.gz/browser-commands.jsonl.gz에보존.
- 필수3/3통과,iteration1. 소유Next/Flask/proxy/browser종료,namespace·합성env/cookie/profile삭제,원본packageSHA불변. clone은승인된FE041작업공간으로유지. cleanup.json참조.

ULTRAQA COMPLETE: Goal met after 1 cycles
