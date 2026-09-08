# UltraQA Report

## Goal and success criteria

- 항목: INFRA-063 | engine: ultraqa | lifecycle: app-adapted | phase: cleanup | active: true | iteration: 2 | same_failure_count: 0
- 목표: 관리자 JSON 객체만 발송 로직에 진입; 잘못된 입력·교차 사이트 요청은 조회/발송/guard 상태를 바꾸지 않는다.
- 승인: 현재 대화의 bounded 설계 및 설치 보완 후 사용자 「다음 진행해」/「계속 진행해」.
- 기준: 5aab1dc에서 독립 clone. 구현 commit 확정 후 HTTP실행.
- 안전: 원본.env/data/3500/5501/live 요청 금지. fake 자격과 가짜 발송; 실제 중복 guard는 tmpdir. native OMX 상태 변경 없음.
- 종료: baseline·필수 행렬·증거·cleanup 모두 통과. 최대5회/같은 실패3회; 검사180초·frontend300초·HTTP600초.

## Scenario matrix

| ID | 의도/사용자·공격자 | Setup/command | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| Q1 | 정상 관리자 | actual Next→Flask JSON {}, target_date, null날짜, vendor JSON | 200·정상 대역 발송 | 통과: 정상/날짜/null·vendor200, resolver전달일치 | JSON 객체 경계 | transport | own tmp | 예 |
| Q2 | 단순 요청 공격 | admin form/urlencoded·multipart·text/plain·MIME없음·빈POST | 415·load/construct/send/guard변화0 | 통과: MIME거부5개415, load/construct/send/guard변화0 | MIME검사 | boundary/transport | own tmp | 예 |
| Q3 | 잘못된 JSON | 문법오류·빈JSON본문·null·배열·scalar·Unicode/큰오류본문 | 400·부수효과0·입력비반사 | 통과: JSON거부7개400, 부수효과0·escaped/plain입력비반사 | 문법/객체검사 | boundary/transport/logs | own tmp | 예 |
| Q4 | 교차사이트/권한우회 | Next 세션 admin cross-site/same-site/없음, 익명/일반계정 각각 폼 및 malformed JSON·위조헤더 | 403·send0, proxy거부는Flask도달0 | 통과: 권한/CSRF10개403, proxy차단5개Flask도달0 | 기존게이트유지 | transport | servers off | 예 |
| Q5 | 중복/force/재시도 | 같은 날짜 두 번·force true·발송 예외 후 재시도·OPTIONS | 정상1회·중복skipped·force추가1회·claim회복·OPTIONS무발송 | 통과: 중복skipped·force추가발송·OPTIONS200무발송; claimretry는회귀검사통과 | 기존동작유지 | boundary/transport | guard tmp삭제 | 예 |
| Q6 | 시크릿/오류노출 | tracked env·client bundle sentinel·HTTP응답/Next/Flask로그 | 시크릿/서명/MAC 노출0 | 통과: 응답·Next/Flask로그·build31JS노출0 | 일반오류본문 | security evidence | fake자격제거 | 예 |
| Q7 | 회귀/dirty/정체 | 전체pytest/vitest/typecheck/lint·hash·timeout/프로세스정리 | exit0·skip공개·원본(복제본 밖) untracked package.json 보존·소유서버종료 | 정적검사·서버정리·원본hash통과; 원본반영/clone정리대기 | 필요한하네스수리 | full logs/preservation | clone제거 | 예 |

## Commands run
- baseline pytest: 외부 네트워크 차단 sandbox, SCHEDULER_ENABLED=false, exit0; 1936 passed/3 skipped, 28.37s.
- baseline vitest: frontend에서 npx vitest run, exit0; 57 files/373 passed, 23.50s.
- skip: Gemini 수동 통합2, 격리 환경 .env없음1. 원문 baseline-pytest.log.gz·baseline-vitest.log.gz를 보존한다.

## Failures found / Fixes applied
준비 중. 제품 실패와 하네스 실패를 구분한다.

## Cleanup and rollback
대기. 원본 상태는 clone 부모 preservation.json으로 고정했다.

## Residual risks
정상 JSON의 target_date/force 필드 의미·다른 라우트·nonce는 이번 범위 밖이다. 기존 발송 실패500의 str(error)·공통 wrapper 로그 정책은 INFRA-038/043 범위로 유지한다. Q6는 새 입력거부의 본문 sentinel과 통신 fake identity secret/서명/MAC의 비반사 검사다. 화면 변경이 없어 HTTP 하네스를 사용하고 브라우저 실측으로 보고하지 않는다.
프롬프트/CLI인수 입력기능은 없어 관련 prompt injection 분류는 적용 불가. continue는 기존 단계로 복구하며 관련없는 상태를 쓰지 않는다.


## 구현 후 정적 검증

- pytest exit0: **1965 passed/3 skipped**, 25.58s. 대상경계/기존회귀62PASS.
- vitest exit0: **57 files/373 passed**, 12.52s. Next build smoke포함. typecheck exit0, lint exit0(0errors/199warnings).
- client JS31개와 build로그에서 unique server-only sentinel 미노출. tracked.env.example만, NEXT_PUBLIC_API_URL·NEXT_PUBLIC_GOOGLE_CLIENT_ID만관측.
- root 하네스 소유프로세스 정리 selftest exit0. actualHTTP는첫구현commit뒤수행한다.

## 실제 전송 실행 전 확정

- actual HTTP 하네스는 28개 세부사례를 계획했다: 정상/중복/force/날짜/null5, 권한선행4, CSRF5, 위조헤더제거1, MIME거부5, JSON거부7, OPTIONS1.
- 기대 총계: HTTP200 6개, 403 10개, 415 5개, 400 7개. Flask도달23, load5, Messenger생성4, fake발송4.
- Q5의 발송실패→claim해제→재시도는 실제Flask test_client+tmpguard 회귀검사에서별도확인했다. 실제HTTP28개에발송실패주입을했다고보고하지않는다.
- 하네스준비수리: 실제객체생성카운터·날짜전달·crosssite폼·JSONescaped marker감지·JWT비노출·부분정리증거보완. source/test 제품코드변경없음.
- client bundle은unique sentinel을넣어생성한production build31JS검사와연결한다. API전용실측을브라우저화면검증으로표시하지않는다.

## 격리 환경 검수 보완

- deep review의Next telemetry지적에따라allowlist환경과telemetry/trace disable, 소유Next그룹즉시종료·분리프로세스/이벤트파일부재검사를추가했다.
- 강화된frontend검사2회에서build smoke2건실패. 첫deny-all의IPC차단을최소Nodeprobe로확인했고, loopback예외후남은실패는실패한.next생성물만분리한뒤해소됐다. 구체적캐시엔트리는미특정.
- 최종front baseline: localhost-only sandbox와allowlist로57files/373PASS(16.92s), 검증용API stub호출0·종료확인. fresh-loopback-vitest.log.gz가현재근거다.
- actualHTTP는root가동적선택한own2port를CLI로전달하고Seatbelt에서그포트만허용할예정이다.

- 심층 재검토 APPROVE. actual commit을첫구현commit후전달한다. 강화환경의type-check/lint도각exit0(180초상한)이며 isolated-frontend-checks.json에기록.

## 실제 실행 1회와 하네스 수리

- 기준 구현commit6b2069b. 1회차는HTTP0회·Next/Flask시작전에PermissionError로실패했다. macOS /bin/ps가setuid라Seatbelt에서exec자체가거부됨을확인했다.
- 네트워크정책을유지하고group/telemetry 관측만non-setuid /usr/bin/pgrep으로바꿨다. 동일sandbox에서alive/dead leader forcekill정리, 실제dummy telemetry process탐지·무관process제외·종료후부재검사가통과했다. pgrep-sandbox-selftest.json과attempt-1.json에보존한다.
- 제품소스·테스트변경없음. 실제실행2회차를준비한다.

## 확정 커밋 실제 QA 결과

- 구현 기준 **6b2069b**. 2회차 actual Next → 기존 proxy/rewrite → bare Flask 실제 request-context/admin/message route: **28/28 통과**, exit0, 4.6초.
- 응답 분포: 200 6개·403 10개·415 5개·400 7개. Flask도달23, 조회5, Messenger생성4, 가짜발송4. 정상1회·중복0회·force/날짜/null각추가1회가 기대와 일치했다.
- Next49535/Flask49534만 Seatbelt outbound허용. 원본3500/5501·live·외부서비스 호출없음. 프로세스환경은allowlist와가짜값만 사용했다.
- 소유Next그룹종료·Flaskthread/socket종료·임시fixture삭제완료. root가두listener부재를별도로확인했다. detached-flush process·_events파일은시작전/종료후/최종정리모두0.
- 실제응답/Next·Flask로그에서fake identity/JWT secret·전체서명·MAC미노출. 새입력오류marker비반사. build31JS는강화격리baseline의unique sentinel로별도검증했다.
- 같은commit의새경계29개도exit0. 검토입력16hash는리뷰/정적검증/실제QA뒤모두동일하다.
- 증거: evidence/INFRA-063/transport/transport.json, run-input.json, run-exit.json, next.log.gz, flask.log.gz, run-2.log.gz; post-qa-check.json.
- 개발 정적 검증의 격리 환경 수리와 실제 QA 실행 횟수는 구분한다. 첫 구현 커밋 뒤 실제QA는 서버전PermissionError 1회와 통과 1회, 총2회다.

## 남은 마감

필수동작은7/7통과했으며 원본반영·독립clone정리·최종아카이브를이어간다. 완료상태는그정리까지끝난뒤표시한다.
