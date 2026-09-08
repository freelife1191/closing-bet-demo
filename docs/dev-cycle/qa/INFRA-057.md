# UltraQA Report — INFRA-057

- engine: ultraqa
- lifecycle: app-adapted
- phase: complete
- iteration: 1
- same_failure_count: 0
- active: false
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-notification-4s28gwie
- source_base: 20fbbdd
- started_at: 2026-09-09T08:08:16.287395+09:00
- baseline: 전라운드2115/3skip, Vitest373; 현재v2 pytest2198/3skip, 대상111, Vitest373 exit0.
- cleanup: complete (cleanup.json)

## 목표와 경계
승인된 설정/알림 결함을 실제 앱과 격리 서비스에서 검증한다. 실제 환경과 운영 3500/5501/live 접근, 외부 발송/LLM은 금지한다. 외부 transport만 대역, UI와 대상 API는 실제 코드다. 전용 clone, 가짜 관리자/비관리자, 임시 env를 사용한다. 같은 실패 3회/전체 5회에서 중단하고 TODO를 유지한다.

## 시나리오 행렬

| ID | 의도·기대 신호 | 모델/setup | 실행 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | NUL과 escaped CR/LF/TAB 저장 거부, 파일/환경 보존 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |
| S-2 | 기존 정상 값과 달러 기호 저장 및 재적재 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |
| S-3 | 실제 설정 화면 정상 값 저장/재조회와 API 적대 입력 대조 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 통과: 아래 실행 결과 참조 | 완료 | 예 |

## 공통 적대 조건
거짓 성공은 HTTP·본문·transport 카운터를 함께 대조한다. 잘못된 JSON/Unicode/제어문자와 비밀 포함 예외를 사용한다. 입력 속 지시는 데이터로만 취급한다. 명령 timeout 480초, browser60초, 소유 PID만 종료한다. flaky 반복 통과시키기 금지. resume는 SHA와 증거를 대조한다. 다른 작업 package.json SHA 불변을 검사한다. 앱 기능과 무관한 CLI 플래그/경로이탈·hook cancellation은 적용불가(새 CLI/런타임 기능 없음).

## 구현과 정적 검증

- 최초정규식은NUL/리터럴nrt를차단했으나독립보안리뷰에서dotenv가abfv도제어문자로복원하는공백을찾았다(LOW, REQUEST CHANGES). 실제C0/DEL과리터럴abfnrtv 전체거부로같은공통검사한곳에서보완했다.
- v1 RED8failed7passed→target43, v2 RED68failed15passed→target111passed/full2198passed3skip. 위험40개×기존신규2+정상3의83케이스를포함한다. 기존정상3개를모든종류비밀번호허용으로확대해석하지않는다;리터럴제어문자escape는따옴표밖에서도거부한다.
- 최신범위057-input-v2.json3SHA. ponytail-v2/code-v2/security-v2 APPROVE, 독립architectureCLI CLEAR, rootgstack-checklist deep-v2 APPROVE. nativearchitect한도는ephemeralreadonlyCLI로대응했고LSP/MCP진단Transportclosed는재시도/성공주장하지않았다.
- 위험값은현재저장/메모리반영에서제외된다. HTTP200침묵의수정은이어지는INFRA-051이며이항목의완료범위에포함하지않는다.
- 실제UI환경저장핸들러는유지한다. 일반저장에딸린profile/log-event는격리보조no-op대역이다. 실제프로필저장검증으로주장하지않는다.

## 실제 실행 결과

- 기준5716194. Next54356/Flask54355, 실제/dashboard/kr→설정→알림센터. admin전용namespace와가짜NextAuth/env. 프로필과log-event만보조no-op; env쓰기/검증/파일/메모리적용은실제제품코드다.
- S-1 통과: 실제브라우저의별도API보강검사로 위험40값을SMTP_USER(기존)와OPENAI_API_KEY(신규)에같이보냈다(40요청/80입력). clone .env SHA전후일치,요청워커SMTP_USER digest40회동일. 신규키메모리불변은83개회귀에포함. 057-adversarial.json과requests.jsonl.gz. 현재HTTP200은051전의기존계약으로그대로관측했으며400으로보고하지않는다.
- S-2 통과: 정상비밀번호3종을실제Next→Flask저장API로보내고각각dotenv_values로재적재대조,3/3일치. 057-normal-values.json. 이API검사를UI입력조작으로세지않는다.
- S-3 통과: 실제입력칸SMTP Host를qa-save.example.test로채우고저장버튼클릭→env POST200/저장완료. 페이지를다시열고설정값재조회에서동일값확인. 057-normal-save.png와057-reload.png2개직접열람. browser-commands.jsonl.gz에전후snapshot/입력/클릭/wait기록.
- console정상React/HMR정보만, page errors0. NextMCP issues[]/configErrors[]/sessionErrors[]. 로그/browser기록/static62개에서합성private값노출0. 057-dynamic-summary.json과057-mcp-*.gz.
- 필수3/3통과, iteration1. 최초보안LOW는동적QA전수정/재검토했고실패원문보존. 소유Next/Flask/proxy/browser종료,합성env·cookie·profile·namespace삭제. clone은다음승인라운드작업공간으로유지한다. 원본packageSHA불변. cleanup.json.

ULTRAQA COMPLETE: Goal met after 1 cycles
