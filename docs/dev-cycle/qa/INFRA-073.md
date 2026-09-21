# INFRA-073 의존성 자동 적용 QA

engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=complete. T2.
사용자 요청: 업데이트가 필요하면 재시작 스크립트에서 자동으로 패키지 업데이트.
범위: restart_all.sh, scripts/sync_dependencies.sh, 실행 회귀. 받은 코드의requirements/lock만 적용하며gitpull/임의최신승격은하지않는다.

| ID | 시나리오/방법 | 기대 | 실제 | cleanup |
|---|---|---|---|---|
| D1 | 임시프로젝트 최초설치→재실행 | 최초ci1회,동일환경skip | PASS | tmp fixture |
| D2 | lock변경/next실행파일소실 | ci재실행 | PASS | tmp fixture |
| D3 | pip install/check, npm ci/ls 실패 | restart비정상종료,서버기동없음 | PASS | 종료명령/서버전부stub |
| D4 | 필수lock누락/공백경로/외부cwd | 누락거부,경로정상처리 | PASS | tmp fixture |
| R1 | 실제독립venv/node_modules 설치 | requirements/lock설치와검증성공 | PASS:실제설치와pipcheck/npm ls exit0 | scratch삭제 |
| R2 | 실제동일환경 재실행 | npm ci생략 | PASS:두번째npm ci생략,exit0 | scratch삭제 |
| C1 | 기존환경보존 | 원본서비스/설정/데이터/rootpackage보존 | PASS:원본서비스/의존성디렉터리미변경,root파일해시보존 | scratch삭제 |

browser_applicability=not-applicable: 변경대상은CLI의존성설치/기동게이트이고앱UI/라우트/데이터동작은변경하지않는다. 실제패키지설치는격리환경에서검증하며서버종료명령은stub으로만실행한다. 원본3500/5501은건드리지않는다. 로그/설정값을업로드하지않으며. hiddenOMX상태쓰기없음.


최종검증: 표적18PASS, 실제신규가상환경/프론트엔드설치0→동일환경재실행0(프론트엔드재설치생략), 새환경전체pytest2519PASS3skip,Vitest641PASS. bash문법검사0. PonytailSHIP,codeAPPROVE,architectCLEAR. 기준구현869cb0c, 최종frozen4개일치.

최초기존node_modules에stamp가없으면한번재설치해기준을만든다. Python은매번requirements충족여부를확인하며이미맞는패키지는재설치하지않는다. Node환경/설치트리상태검사후필요할때만npmci한다. 시스템Python패키지는수정하지않는다.

원본실행서비스의실제재시작은하지않았다. 신규startup명령이아니라의존성준비게이트변경이므로실제설치는독립환경에서,기동차단은종료/서버stub경계에서확인했다. 새환경npm의install-scripts차단경고가있었지만npm ls와Vitest전체가통과했으며전역승인설정은바꾸지않았다.

설치실패시기존서비스는이미내려간상태다. 오류를해결하고다시실행해야한다. 이는활성환경의패키지를교체하지않기위한기존재시작순서이며자동rollback을추가하지않았다. 기존광범위프로세스종료방식은이번수정범위밖이다.

ULTRAQA COMPLETE: Goal met after 1 cycle. 시나리오7/7통과, 임시scratch삭제,원본사용자파일과실행서비스보존.
