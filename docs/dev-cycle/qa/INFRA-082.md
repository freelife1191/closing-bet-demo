# [INFRA-082] 캐시가 아닌 `data/` 절대 경로 여섯 곳이 격리 실행에서도 원본을 가리킨다 — QA 시나리오

- 대상: 격리 사본에서 CLI 두 개(`scripts/run_full_update.py`, `scripts/verify_collection_logic.py`)를 루트 밖 cwd 로 실행, 사본 서비스(backend 58121, frontend 58120)의 http://localhost:58120/dashboard/kr 와 `/api/kr/signals/status`
- 구성 근거: `[INFRA-082]` 설계 승인(2026-09-24 00:02, CLI 두 개의 루트 `os.chdir` + `VCP_STATUS` 를 `DATA_DIR` 기준으로)
- 구성 2026-09-24 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code. 사용자 진입 흐름은 운영자의 CLI 실행과 대시보드의 VCP 상태 조회 둘이다. 상태 조회는 기존 화면이 부르는 API 라 브라우저 실측을 필수로 둔다. 하네스:
  `git archive HEAD` 사본에서 추적 파일 때문에 생긴 `data/` 를 먼저 지우고 원본 `data/`·`venv`·`frontend/node_modules` 를 APFS clone 으로 둔다. `.env` 계열은 두지 않고, 사본의 `secrets/` 는 만들자마자 지운다.
  CLI 는 실제 수집·LLM·발송을 부르므로 **사본에서만** `scripts/init_data.py` 를 가짜로 바꾼다. 가짜는 불린 함수 이름과 `os.getcwd()` 를 사본의 기록 파일에 남기고 아무것도 수집하지 않는다(검사 대상은 CLI 머리의 `chdir` 이며 `init_data` 가 아니다).
  서비스는 `env -i` 로 `FLASK_PORT=58121 FRONTEND_PORT=58120 SCHEDULER_ENABLED=false API_URL=http://127.0.0.1:58121` 와 더미 `NEXTAUTH_*`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 를 주고 사본의 `./restart_all.sh` 로 띄운다.
  원본 `data/`·3500·5501·운영 주소는 건드리지 않고 Refresh VCP·LLM·발송·저장 조작은 하지 않는다. 브라우저는 gstack `browse`, 익명 사용자
- 기대값 출처: 설계 승인 범위, `run.py:14` 의 같은 `chdir`
- 단계(phase): 시나리오 구성 완료
- 필수 여부(required): 예
- 결과: (미실행)

## 시나리오

### S-1. `run_full_update.py` 를 루트 밖에서 실행해도 루트에서 돈다 (결함 재현)
- 조작: 사본 밖 임시 디렉터리를 cwd 로 두고 `<사본>/venv/bin/python <사본>/scripts/run_full_update.py` 를 실행한다.
- 기대: exit 0, 가짜 `init_data` 기록의 cwd 가 모두 사본 루트, 임시 cwd 에 `data/` 가 생기지 않는다.
- 필수 여부(required): 예

### S-2. `verify_collection_logic.py` 도 같다 (결함 재현)
- 조작: S-1 과 같은 방식으로 실행한다.
- 기대: exit 0, 기록의 cwd 가 사본 루트, 임시 cwd 에 `data/` 없음.
- 필수 여부(required): 예

### S-3. 대시보드의 VCP 상태가 cwd 기준 `data/vcp_status.json` 을 읽는다 (회귀)
- 조작: 사본의 `data/vcp_status.json` 에 `message` 를 `QA-INFRA-082` 로 둔 idle 상태를 쓰고 사본 서비스를 띄운다. browse 로 /dashboard/kr 를 열고, 같은 페이지에서 `fetch('/api/kr/signals/status')` 결과와 콘솔 오류를 읽는다.
- 기대: 페이지 200, 상태 응답의 `message` 가 `QA-INFRA-082`, `running` false, 콘솔 오류 없음.
- 필수 여부(required): 예

### S-4. `vcp_status.json` 이 없는 트리에서 pytest 가 원본을 만들지 않는다 (적대적)
- 조작: 서비스를 내린 뒤 사본의 `data/vcp_status.json` 을 지우고 사본에서 `venv/bin/python -m pytest -q -p no:cacheprovider tests/app/test_kr_market_route_integration.py` 를 실행한다.
- 기대: 테스트 통과, conftest 세션 끝 검사의 `[INFRA-083]` 경고 없음, 사본 `data/vcp_status.json` 이 여전히 없다.
- 필수 여부(required): 예
