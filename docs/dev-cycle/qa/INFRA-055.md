# UltraQA Report — INFRA-055 Next 환경 분리

- QA 엔진(engine): Codex UltraQA
- lifecycle: app-adapted
- phase: cleanup
- iteration: 1
- same_failure_count: 0
- active: true
- browser_applicability: required
- browser_driver: agent-browser 0.31.1
- 구성/실행 일자: 2026-09-09
- 설계 승인: 사용자 「진행해」로 승인한 동일 INFRA-055 범위 재개. 새 설계를 반복하지 않았다.
- 기준 커밋: d2c7291bc8f3f3e47b91f27dc76f854d244cdc36 (원본 기준97113d4)
- 검토·검증 범위: [review-input-v10.json](../evidence/INFRA-055/review-input-v10.json)의 7개 SHA-256과 실행 후 일치.
- 대상: http://127.0.0.1:49879/dashboard/kr, Flask fixture 127.0.0.1:49878
- namespace: devcycle-infra055-x_hko9la / sessions admin, viewer
- UltraQA Report: [INFRA-055.md](INFRA-055.md)

## 목표·완료 조건·안전 경계

Next에 필요한 키만 전달하고, 실제 dev의 cold/warm cache 및 build/start cache에서 백엔드 전용 비밀 전체값이 검출되지 않아야 한다. 인증·서명 신원·관리자 설정 조회를 보존한다. 모든 필수6행, 정적검증, 독립리뷰, 증거·정리를 통과해야 완료한다. 최대5회, 동일 실패3회에서 중단한다.

독립 clone와 합성 환경/계정만 사용했다. 원본3500/5501·live·실제env/data·LLM·알림발송·매매·설정저장·삭제·재수집·운영재시작은 수행하지 않았다. sandbox는 외부접속과 원본두포트를 거부하고, 브라우저는 loopback만 허용하며 외부 proxy는 전부403을 반환한다.

실제 제품 Next 화면·NextAuth 세션판정·proxy 신원서명·Flask 요청 신원검증·관리자 토큰 gate·env GET 마스킹을 사용했다. 시장·quota·요약 응답은 고정 대역이다. Flask의 모든 변경 메서드는405로 차단한다. 관측된 Flask 요청은 모두 GET이다. 실제 Google OAuth 로그인과 외부 아이콘/시세 콘텐츠의 완전성은 이 검증의 대상이 아니다.

## 필수 시나리오 행렬

| ID | 의도·사용자/공격자 | setup·실행 | 기대 | 실제·결과 | 수정·증거 | cleanup |
|---|---|---|---|---|---|---|
| S-1 required | 개발 실행 회귀 / 운영자 | 합성 root-env3개와 부모env3개 주입, 기존legacy링크, npm dev→실제dashboard→종료→warm 재실행 | 실제 SST>0, backend 일치0, mode0700 | cold/warm 각각 artifacts221·SST7·일치0·0700; 관리자 표시 유지. 통과 | cache-dev-cold.json, cache-dev-warm.json, admin-warm-dev.png, browser-commands | 양쪽 실행의 소유 Next/Flask 종료 |
| S-2 required | 빌드·운영 실행 회귀 / 운영자 | npm build→npm start→admin/viewer 실제dashboard·설정 | build0, 앱 정상, cache/bundle backend 일치0 | build0/start정상, artifacts386·SST7·일치0·0700. public/log35files 비밀전체값0. 통과 | cache-build.json, public-scan-build.json, admin-build.png, viewer-build.png, next.log | 소유 Next/Flask 종료 |
| S-3 required | 인접 / 관리자 | 실제설정→API & 기능·알림센터, 보강 GET env/admin-check | 관리자탭, 가려진SMTP, env200, admin=true | dev/build 관리자탭 있음·env200·admin=true; Flask서명신원admin. SMTP63자 중간55자별표, UI passwordbullet. 통과 | admin-api-dev.png, admin-masked-dev.png, request-summary.json, browser-commands | admin 브라우저 종료 |
| S-4 required | 권한 공격 / viewer·익명 | 별도viewer 세션의 설정 UI 및 env직접GET, 무쿠키GET | 관리자탭없음, env403, viewer신원검증/admin=false | dev/build 일반탭만 보임·env403·isAdmin=false, Flask신원viewer; 익명403. 통과 | viewer-dev.png, viewer-build.png, request-summary.json, browser-commands | viewer 브라우저 종료 |
| S-5 required | 입력·파일·프로세스 공격 / CLI호출자 | 실제launcher subprocess50회귀; 실제Next 추가인수·선택옵션 검사 | 우회차단·실패nonzero·파일보존·자식종료 | 50PASS; 실제추가directory exit1, bare선택옵션 help exit0. 통과 | security-green-v10.log.gz, syntax-and-cli-v10.json 및 RED원문 | pytest tmp/PID 정리 확인, clone삭제 대기 |
| S-6 required | 보존·정리 / 기존작업자 | 원본package SHA·source SHA·PID/port·namespace·통합후clone 확인 | 사용자파일불변, 동일source, 소유잔여0 | package해시불변·source7/7·포트/PID없음·namespace삭제; 통합후clone삭제 대기 | cleanup-preintegration.json | 최종 통합·임시clone 정리 후 확정 |

S1-S4는 agent-browser의 open→snapshot→ref click→새snapshot으로 실제 화면을 조작했다. 모든 PNG를 view_image로 직접 열어 확인했다. eval/fetch는 권한 응답과 마스킹의 보강 증거이며 UI를 대체하지 않는다. S5의 browser_driver는 none이다.

## 실행 명령과 baseline

작업 위치는 독립 clone의 root 또는 frontend다. 명령별 실제 argv·exit·실행시간은 JSON, 출력은 gzip으로 보존했다.

| 명령/하네스 | 제한 | 종료·핵심 결과 |
|---|---|---|
| venv/bin/python -B -m pytest -q --basetemp <owned> | 480초 | 0; baseline2027/3skip → 최종2077/3skip |
| frontend ./node_modules/.bin/vitest run | 480초 | 0; 57files/373PASS; 실제빌드 smoke 포함 |
| npm run lint | 480초 | 0; 오류0, 경고204(기존199+CommonJS require5) |
| npm run type-check | 480초 | 0 |
| node --check / bash -n / Python AST | 짧은 로컬 검사 | 0 |
| launch_qa.py start-dev --fresh-cache / start-dev | 준비45초·기동120초 | 각각0, 실제npm dev 기동 |
| launch_qa.py build-start --fresh-cache | build300초·기동120초 | 0, 실제npm build/start |
| browser_cli.py admin/viewer <command> | 각60초·kill5초 | 실행 명령 전체exit0; 콘솔/페이지 오류없음 |
| /_next/mcp tools/list 및 tools/call | 30~60초 | get_compilation_issues issues=[]; get_errors configErrors=[]/sessionErrors=[]; 실제 page metadata 확인 |
| qa_fixture.py scan-caches | 종료 후 로컬 전체byte검사 | 세 실행 모두0, backend sentinel6개 검사 |
| public_scan.py | 로컬 검사 | dev56/build35files; 합성비밀7개 전체값 일치0 |
| launch_qa.py stop·browser close·proxy stop | 서비스20초·브라우저60초 | 모두0, 실제lsof/프로세스부재 확인 |

NextAuth 같은 필수 서버키는 private cache 안의 잔존 금지를 주장하지 않는다. backend-only6개는 .next 전체를 검사했고, 필수키를 포함한7개 비밀 전체값은 public static·서버로그·브라우저출력에서 검사했다. private cache 접근은0700으로 제한한다. 악의적으로 비밀 리터럴을 NEXT_PUBLIC 값에 직접 붙이는 행위나 실행 중 파일변경 감시는 이 계약에 포함되지 않는다.

## 발견·원인·보완

구현 단계에서는 기존 코드의 실제cache누출(0건 기대 assertion exit1), 실제Next 추가위치인수 무시, symlink 교체 후 타경로chmod, raw/숫자/escaped/재귀 dollar 참조 우회, dotenv runtime키 경유 우회를 재현했다. 이 실패는 첫 구현커밋 이전이며 [리뷰 보고서](../reviews/INFRA-055.md)와 RED 원문을 보존한다. 최종v10은 raw+expanded 검증·runtime parent-only·fd/inode검증·고정Next경로/인수검증으로 해소했다. 독립 code APPROVE, architecture CLEAR, security APPROVE다.

실측 중 보강 마스킹 probe의 기대값을 두 번 바로잡았다. 첫 probe는 UI의 bullet문자를 API에도 기대했고, 둘째는 긴 값도 전부별표라 가정했다. 제품 _mask_env_value의 실제 계약(양끝4자+중간별표)을 읽고 올바른 길이·중간별표 assertion으로 통과했다. 두 false 출력도 원문에 남겼다. 이는 보강 하네스 기대값 오류이며 제품은 변경하지 않았다. architecture 원인진단은 리더가 직접 대체했고, 비밀전체값의 응답노출이 아니라 검증표현 오류임을 확인했다.

prompt injection은 실행기 입력을 명령으로 평가하지 않는 특수문자·고정경로 subprocess 검사로 다룬다. OMX native취소/상태는 App대응 범위라 조작하지 않으며 CLI자식 signal·exit/dirty파일보존으로 관련 경계를 검사한다. 무작정 반복하여 PASS를 얻거나 필수행을 optional로 낮춘 항목은 없다.

## 정리·복구와 잔여 범위

소유 서비스/브라우저/proxy가 종료됐으며 49878·49879·51760 listener없음, browserbackground PID5990·6084 없음, 정확한 browser namespace만 삭제했다. 합성env는 GET 전후 바이트가 같고, legacy frontend/.env 링크는 런처가 제거했다. 원본package SHA256은 `4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8`로 유지됐다. 최종clone·쿠키·프로필·cache·하네스삭제는 원본통합 후 확정한다.

기존 운영 프로세스와 원본의 과거 캐시는 재시작하거나 삭제하지 않았다. 새 실행기 계약은 다음 명시적 npm dev/build/start 또는 restart 때 적용된다. npm audit/외부CVE검사는 의존성변경이 없어 미실행이다. 보안 lane의 fresh MCP transport오류는 같은v10의 코드 lane LSP0/AST0 증거로 보완했다. Python LSP를 통과했다고 주장하지 않는다.

## 실행 결과

- 필수 통과: 5/6. S6 최종 통합·clone 정리 대기.
- 제품 필수실패: 없음. 신규 범위 밖 발견: 없음.
- 재개 판정: 통합·정리·아카이브 진행.
- 증거: [INFRA-055 evidence](../evidence/INFRA-055/)의 원문gzip·JSON·PNG. 쿠키나 합성env값 파일은 증거에 포함하지 않았다.
