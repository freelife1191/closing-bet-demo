# INFRA-073 의존성 자동 적용 QA

engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=baseline. T2.
사용자 요청: 업데이트가 필요하면 재시작 스크립트에서 자동으로 패키지 업데이트.
범위: restart_all.sh, scripts/sync_dependencies.sh, 실행 회귀. 받은 코드의requirements/lock만 적용하며gitpull/임의최신승격은하지않는다.

| ID | 시나리오/방법 | 기대 | 실제 | cleanup |
|---|---|---|---|---|
| D1 | 임시프로젝트 최초설치→재실행 | 최초ci1회,동일환경skip | PASS | tmp fixture |
| D2 | lock변경/next실행파일소실 | ci재실행 | PASS | tmp fixture |
| D3 | pip install/check, npm ci/ls 실패 | restart비정상종료,서버기동없음 | PASS | 종료명령/서버전부stub |
| D4 | 필수lock누락/공백경로/외부cwd | 누락거부,경로정상처리 | PASS | tmp fixture |
| R1 | 실제독립venv/node_modules 설치 | requirements/lock설치와검증성공 | 대기 | 자체scratch |
| R2 | 실제동일환경 재실행 | npm ci생략 | 대기 | 자체scratch |
| C1 | 기존환경보존 | 원본서비스/설정/데이터/rootpackage보존 | 대기 | 자체scratch만삭제 |

browser_applicability=not-applicable: 변경대상은CLI의존성설치/기동게이트이고앱UI/라우트/데이터동작은변경하지않는다. 실제패키지설치는격리환경에서검증하며서버종료명령은stub으로만실행한다. 원본3500/5501은건드리지않는다. 로그/설정값을업로드하지않으며. hiddenOMX상태쓰기없음.
