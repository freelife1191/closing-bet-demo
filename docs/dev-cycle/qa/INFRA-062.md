# UltraQA Report

## Goal and success criteria

- 목표: actual method/path에 맞는 v2 신원만 허용하고 다른 경로/메서드·구형·위조·만료 서명을 거부한다.
- engine: ultraqa | lifecycle: app-adapted | phase: ready-for-e2e | iteration: 1 | same_failure_count: 0
- 승인: 2026-09-08 현재 대화 사용자 「진행해」. method/path결합, 구형거부, Next/Flask 동시수정, T3 리뷰/UltraQA.
- 기준: a464a30 → 설계 9fdb1f9. 정확한 구현 커밋은 첫 구현 커밋 후 기록한다.
- 준비 baseline: 독립 clone pytest 1914 PASS/3 skip(수동Gemini2·.env없음1), vitest365 PASS/57files. 모두exit0.
- 안전: 원본.env/data/3500/5501/live/외부HTTP 금지. fake secret·합성JWT·부수효과없는bareFlask probe만. 원본package.json 보존. native OMX상태변경없음.
- 상한: 개별 검사180초, 리뷰12분, 동적하네스15분, 최대5cycles/동일실패3회. 필수미통과시TODO유지.

## Scenario matrix

| ID | 의도/공격자 | Setup/command | 기대 | 실제 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| Q1 | 정상 로그인 사용자 | TS signer→Python verifier vectors, 실제 Next→Flask | 이메일보존·GET/POST/HEAD정상 | 대기 | v2계약 | 테스트/HTTP결과 | child종료 | 예 |
| Q2 | 헤더를 복사한 공격자 | 경로A→B, GET→POST, portfolio/notification gate fake서비스 | None/401/403·부수효과0 | 대기 | method/path MAC | 경계회귀 | tmpDB자동정리 | 예 |
| Q3 | 구형/위조/만료/잘못된 버전 | unit 및 actualHTTP | 인증거부, 구형fallback없음, secret없는환경차단 | 대기 | 형식검증 | 테스트결과 | fixture정리 | 예 |
| Q4 | URL해석 차이 | spec transport표 raw HTTP %2F/%252F/한글/tail/ | exact decoded path동일, trailing308뒤새요청성공 | 대기 | 1회decode | 관측값표 | 서버종료 | 예 |
| Q5 | 비정상URL·Unicode | rawHTTP %/%ZZ/%FF, malformedMAC | 400·Flask hit0, verifier500없음 | 대기 | 경계검사 | rawHTTP기록 | 서버종료 | 예 |
| Q6 | 인접권한·정보유출 | 익명/OPTIONS/CSRF·samepath재전송·query 차이·응답/번들scan | 기존정책유지, 서명/secret비노출, 승인된잔여범위명시 | 대기 | 기존가드유지 | 테스트/scan | fake자격만 | 예 |
| Q7 | 회귀/다른작업보존 | 전체pytest/vitest/typecheck/lint·수동verify·원본hash | 새실패없음, sourcehash일치, package보존 | 대기 | 필요한fixture갱신 | 전체로그/manifest | clone정리 | 예 |

## Commands run

- `env -u OMX_ROOT -u OMX_STATE_ROOT SCHEDULER_ENABLED=false PYTHONDONTWRITEBYTECODE=1 sandbox-exec -p '(version 1)(allow default)(deny network-outbound)' <original>/venv/bin/python -m pytest -q -rs` (cwd clone): exit0, 1914 passed/3skipped, 27.73s.
- `npx vitest run` (cwd clone/frontend): exit0, 57files/365tests, 22.31s, Next build smoke포함.

## Failures found / Fixes applied

계획 critic의 transport기대값/실제 malformed HTTP/정확한파일경로 지적을 설계·계획에 반영했다. 제품 구현 전 검토이며 원문/최종판정은 리뷰 기록에 보존한다.

## Cleanup and rollback

진행중. 운영 DB/시크릿/프로세스는 접근하지 않는다. 실행용소유하네스는 정리하고증거만저장소에보존한다.

## Residual risks

same method/path 재전송과 query/body 변경방어는 승인된범위밖이며 nonce저장소를추가하지않는다. 향후배포는 Next/Flask함께적용해야한다.

## Evidence

`docs/dev-cycle/evidence/INFRA-062/`에 원문로그·crossruntime/transport결과·입력hash·정리증거를 보존한다. LLM/CLI플래그/파일경로를받는기능이없어 그입력종류의 prompt injection은 해당없다. 성공문구만으로판정하지않고각명령exit와assertion·skip내역을확인한다.

## 구현 후 정적 검증

- root 전체 pytest: exit0, 1936 passed/3 skipped, 25.75s. 관련 경계112 PASS, 수동 verify_portfolio_api.py exit0.
- root 전체 vitest: exit0, 57 files/373 tests, 12.72s. typecheck exit0, lint exit0(0errors/199warnings).
- 독립 cross-runtime: 실제TSsigner→Python 9 PASS. 병렬구현이 먼저 끝나 해당테스트의첫실행은GREEN이었으며, baseline actual TS(v1)를동일런타임경로에넣은반증은exit1/baseline_contract_match=false였다. root의구형헤더200→401 기대RED와구분한다.
- 인증 사전 검사: security-static.json. 추적env는.env.example만, NEXT_PUBLIC 신원secret없음, server-only unique sentinel이client JS31개와build로그에없음을확인했다. 실제HTTP응답·로그·MAC검사는후속transport QA에서확인한다.
- 구현 하네스의 accepted counter와 Flask도달counter를분리하고root URL readiness호출을없애도록보완을요청했다. 이는제품실패가아닌QA관측정확성검토다.

원본 실행 로그는 `.log.gz`로 압축하여 공백·ANSI를 바꾸지 않고 보존한다. 리뷰 원문의 `.log` 경로는 같은 이름 `.log.gz`를 `gzip -dc`로 푼 내용에 해당한다.

- 준비단계 하네스 수리: Flask/Next 로그를 종료 후 별도 검사하고, alive/dead leader 두 조건의 자식 정리 시험을 통과했다. 정리 보장은 정상·포착한 예외·KeyboardInterrupt에 한정하며 외부 강제 종료까지 보장하지 않는다. 증거: transport/cleanup-selftest.json.
