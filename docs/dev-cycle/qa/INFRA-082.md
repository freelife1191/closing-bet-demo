# [INFRA-082] 캐시가 아닌 `data/` 절대 경로 여섯 곳이 격리 실행에서도 원본을 가리킨다 — QA 시나리오

- 대상: 격리 사본에서 CLI 두 개(`scripts/run_full_update.py`, `scripts/verify_collection_logic.py`)를 루트 밖 cwd 로 실행, 사본 서비스(backend 58121, frontend 58120)의 http://localhost:58120/dashboard/kr 와 `/api/kr/signals/status`
- 구성 근거: `[INFRA-082]` 설계 승인(2026-09-24 00:02, CLI 두 개의 루트 `os.chdir` + `VCP_STATUS` 를 `DATA_DIR` 기준으로)
- 구성 2026-09-24 00:04 | 실행 2026-09-24 00:06 (1회차)
- 검증 기준 커밋: `d035905` (첫 커밋). 사본은 이 커밋의 `git archive HEAD` 이며 실행 전 사본의 `scripts/run_full_update.py`·`scripts/verify_collection_logic.py`·`app/routes/kr_market.py` 가 작업 트리와 같음을 `diff` 로 확인했다. 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 사용자 진입 흐름은 운영자의 CLI 실행과 대시보드의 VCP 상태 조회 둘이다. 상태 조회는 기존 화면이 부르는 API 라 브라우저 실측을 필수로 둔다. 하네스:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/`·`venv`·`frontend/node_modules` 를 APFS clone 으로 둔다. `.env` 계열은 두지 않고, 사본의 `secrets/` 는 만들자마자 지운다.
  CLI 는 실제 수집·LLM·발송을 부르므로 **사본에서만** `scripts/init_data.py` 를 가짜로 바꾼다. 가짜는 불린 함수 이름과 `os.getcwd()` 를 사본의 기록 파일에 남기고 아무것도 수집하지 않는다(검사 대상은 CLI 머리의 `chdir` 이며 `init_data` 가 아니다).
  서비스는 `env -i` 로 `FLASK_PORT=58121 FRONTEND_PORT=58120 SCHEDULER_ENABLED=false API_URL=http://127.0.0.1:58121` 와 더미 `NEXTAUTH_*`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 를 주고 사본의 `./restart_all.sh` 로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 Refresh VCP·LLM·발송·저장 조작은 하지 않는다. 브라우저는 gstack `browse`, 익명 사용자
- 기대값 출처: 설계 승인 범위, `run.py:14` 의 같은 `chdir`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 하네스 실수 없음
- 필수 여부(required): 예
- 결과: 통과 (필수 4/4)
- 증거: 아래 각 시나리오의 「실제」 줄(명령 출력 원문) · 스크린샷 `docs/dev-cycle/evidence/INFRA-082/infra082-s3.png`(열어서 /dashboard/kr 렌더 확인) · 대조 실행 두 건(변경 전 코드로 같은 조작을 해 결함이 재현됨)
- 정리(cleanup): 사본 서비스는 `stop_all.sh` 로 종료(리스너 0, `pgrep -fl infra082` 0건), browse 서버 정지, 사본·루트 밖 임시 디렉터리 삭제. 가짜 `init_data.py` 와 대조본은 사본에만 있었다. 원본 `data/`·3500·5501 은 건드리지 않음

## 시나리오

### S-1. `run_full_update.py` 를 루트 밖에서 실행해도 루트에서 돈다 (결함 재현)
- 조작: 사본 밖 임시 디렉터리를 cwd 로 두고 `<사본>/venv/bin/python <사본>/scripts/run_full_update.py` 를 실행한다.
- 기대: exit 0, 가짜 `init_data` 기록의 cwd 가 모두 사본 루트, 임시 cwd 에 `data/` 가 생기지 않는다.
- 필수 여부(required): 예
- 실제: 00:06:34 루트 밖 임시 디렉터리에서 `env -i` 로 실행 → exit 0, 「>>> Update Complete.」. 가짜 기록 `create_institutional_trend`·`create_daily_prices`·`create_jongga_v2_latest` 의 cwd 가 모두 사본 루트(`…/scratchpad/infra082-copy`), 임시 cwd 는 비어 있음(`ls -A` 출력 없음). 대조: `os.chdir` 줄만 뺀 사본 스크립트를 같은 방식으로 실행하면 세 기록의 cwd 가 모두 `…/scratchpad/infra082-outside`(루트 밖) 였다
- 결과: 통과

### S-2. `verify_collection_logic.py` 도 같다 (결함 재현)
- 조작: S-1 과 같은 방식으로 실행한다.
- 기대: exit 0, 기록의 cwd 가 사본 루트, 임시 cwd 에 `data/` 없음.
- 필수 여부(required): 예
- 실제: 같은 실행에서 exit 0, 「Closing Bet Analysis Result: True」. 기록 `create_signals_log`·`create_jongga_v2_latest` 의 cwd 가 사본 루트, 임시 cwd 비어 있음
- 결과: 통과

### S-3. 대시보드의 VCP 상태가 cwd 기준 `data/vcp_status.json` 을 읽는다 (회귀)
- 조작: 사본의 `data/vcp_status.json` 에 `message` 를 `QA-INFRA-082` 로 둔 idle 상태를 쓰고 사본 서비스를 띄운다. browse 로 /dashboard/kr 를 열고, 같은 페이지에서 `fetch('/api/kr/signals/status')` 결과와 콘솔 오류를 읽는다.
- 기대: 페이지 200, 상태 응답의 `message` 가 `QA-INFRA-082`, `running` false, 콘솔 오류 없음.
- 필수 여부(required): 예
- 실제: 사본 `./restart_all.sh` exit 0, 「🎉 Ready!」(backend PID 20959, frontend PID 21059). 00:07:16 /dashboard/kr 200, 로딩 오버레이가 사라진 뒤 페이지에서 `fetch('/api/kr/signals/status')` → `{"http":200,"running":false,"status":"idle","message":"QA-INFRA-082"}`, `console --errors` → `(no console errors)`
- 결과: 통과

### S-4. `vcp_status.json` 이 없는 트리에서 pytest 가 원본을 만들지 않는다 (적대적)
- 조작: 서비스를 내린 뒤 사본의 `data/vcp_status.json` 을 지우고 사본에서 `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_kr_market_route_integration.py` 를 실행한다.
- 기대: 테스트 통과, conftest 세션 끝 검사의 `[INFRA-083]` 경고 없음, 사본 `data/vcp_status.json` 이 여전히 없다.
- 필수 여부(required): 예
- 실제: `stop_all.sh` 「✅ 이 프로젝트가 관리하던 서비스가 종료되었습니다.」, 리스너 0. 파일을 지운 뒤 00:07:30 실행 → exit 0, 31 passed, 출력의 `INFRA-083` 0건, 실행 뒤 `ls data/vcp_status.json` 「No such file or directory」. 대조: 사본의 `app/routes/kr_market.py` 만 변경 전 커밋 `004c55e` 판으로 되돌려 같은 조작을 하면 exit 1, 「[INFRA-083] 테스트 중 저장소 data/·logs/ 가 바뀌었다 (1개): data/vcp_status.json」 과 새 테스트 실패, 파일이 생겼다(대조 뒤 삭제)
- 결과: 통과

## 실행 결과

- 1회차(2026-09-24 00:06, 기준 `d035905`): 필수 4/4 통과
- 이월한 발견: `[INFRA-086]`(코드 리뷰 발견 1·2)
