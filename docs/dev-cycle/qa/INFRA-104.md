# [INFRA-104] 시작 처리와 스레드 진입 사이 틈에서 같은 워커의 재시작이 받아들여지는 문제 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`(상태 파일 잠금 안에서 `LOCAL_PIPELINE_ACTIVE` 를 켬), 해제는 `run_background_update_pipeline` 의 `finally`
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 구성 2026-09-25
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `3dc2558b`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 09:45), 호출 경로(`POST /api/system/start-update` → `api_start_update` → `start_update` → `Thread(run_background_update)` → `app/routes/common.run_background_update` 가 진입 때 `LOCAL_RUN_START_TIME` 을 읽음 → 파이프라인). 파이프라인은 모르는 항목 이름이면 어떤 단계도 돌리지 않고 `finish_update` 로 끝난다. `scripts/init_data` 임포트에는 네트워크·KRX 로그인이 없다
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자 진입 흐름은 데이터 상태 화면의 시작이며, 이번 변경이 그 경로의 워커 플래그를 바꾸므로 시작 뒤 플래그가 풀려 다시 시작할 수 있는지를 화면 세션으로 확인한다. 틈 자체(수 ms)는 화면으로 만들 수 없어 사본 모듈을 직접 부르는 서비스 하네스로 재현한다
- 격리: `[INFRA-103]` 과 같다. 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`(58101), 사본 Next dev(58102)는 `API_URL` 을 사본 Flask 로 둔다. 더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS=qa-admin@example.com` 을 환경 변수로만 주고 같은 더미 비밀로 만든 세션 토큰을 쿠키로 넣는다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 실제 시작 요청은 항목을 `QA Noop` 하나로만 보낸다(수집·LLM·KRX 로그인 없음). 알려진 항목의 「업데이트」 클릭은 상태 파일이 실행 중일 때만 해서 409 로 거부된다
- 금지: 알려진 항목으로 실행 중이 아닐 때의 시작, 중지 버튼, 메시지 발송, 설정 저장, Refresh, AI 재분석, 챗봇 전송, 모의 매수
- 필수 여부(required): S-1~S-4 예
- 실행: 세션 스크래치의 `infra104qa_harness.py`(S-1)와 `infra104qa_run.sh <사본> <표식>`(S-2~S-4, agent-browser `--namespace infra104qa`), 두 사본을 차례로
- 반복(iteration):
- 결과:
- 증거:

## 시나리오

### S-1. 시작 직후 스레드가 들어오기 전 다른 워커의 중단과 같은 워커의 재시작이 겹친다 (서비스 하네스, 필수)
- 조작: 사본의 `app.routes.common` 을 그대로 쓴다. `start_update(["QA Noop"])` → `stop_update()`(다른 워커의 중단과 같은 쓰기) → `start_update(["QA Noop"])`. 그 뒤 첫 시작의 스레드가 들어온 것처럼 `run_background_update(None, ["QA Noop"], False)` 를 부르고, 스레드가 묶은 실행 시각과 끝난 뒤 상태·플래그를 적는다
- 기대: 수정 뒤 두 번째 시작 `False`, 상태 파일은 중단된 첫 실행 그대로, 옛 스레드는 첫 실행의 시각을 묶고 끝난 뒤 `LOCAL_PIPELINE_ACTIVE=False`, 그 뒤 세 번째 시작 `True`. 수정 전은 두 번째 시작 `True` 이고 옛 스레드가 두 번째 실행의 시각을 묶어 그 실행을 끝낸다(결함 재현)
- 실제:

### S-2. 화면 세션의 시작이 끝나면 같은 워커에서 다시 시작할 수 있다 (브라우저, 필수)
- 조작: 관리자 세션으로 `/dashboard/data-status` 를 연 페이지에서 `fetch('/api/system/start-update', {items:['QA Noop']})` 를 보내고 `update-status` 가 실행 중 아님이 될 때까지 기다린 뒤 같은 요청을 한 번 더 보낸다
- 기대: 두 사본 모두 두 요청 200, 각각 5초 안에 `isRunning:false`, 화면에 진행 표시 없음. 수정 뒤 플래그가 남으면 두 번째가 409 다
- 실제:

### S-3. 실행 중에 「업데이트」를 누르면 409 중복 모달이 뜬다 (브라우저, 필수)
- 조작: 상태 파일을 실행 중으로 써 두고 첫 카드의 「업데이트」를 누른다
- 기대: `POST /api/system/start-update` 409, 「업데이트 중복」 모달, 상태 파일 해시 불변(`[INFRA-100]`·`[INFRA-102]` 경로 회귀 없음)
- 실제:

### S-4. 이 QA 가 자료를 바꾸지 않는다 (필수)
- 기대: 사본 Flask 로그에 수집·`init_data` 단계·KRX 로그인 줄 없음, 사본 `data/` 에 상태 파일과 서버 기동 파일 말고 새 자료 없음. 원본 `data/` 수정 시각 불변
- 실제:

## 정리
- 실제:
