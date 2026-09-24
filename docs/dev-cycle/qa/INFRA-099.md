# [INFRA-099] 같은 워커에 끝나지 않은 수동 업데이트가 있으면 새 시작을 거부한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`(표시가 켜져 있으면 `False`), `services/common_update_service.py` 의 `run_background_update_pipeline`(`LOCAL_PIPELINE_ACTIVE` 켜고 끔), 시작 경로 둘(`app/routes/common_update_routes.py` 400, `services/kr_market_flow_service.py` 409)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 23:15:02
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `da46ee0`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 23:11), 호출 경로(관리자 `POST /api/system/start-update`·`/api/kr/refresh`·`/api/kr/init-data` → `start_update` → 스레드 `run_background_update`), `[INFRA-097]` QA S-4(같은 워커 재시작 한계 실측)
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 현황 페이지의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이다. 결과는 프로세스 안의 플래그·표시 값과 공유 상태 파일로 판정한다. 라우트의 400/409 응답은 단위 테스트(`test_start_update_route_rejects_when_start_update_refuses`, `test_launch_background_update_job_rejects_when_start_update_refuses`)가 잰다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra099qa_harness.py`(한 프로세스에서 시작 → 파이프라인 스레드 → 중단 → 0.5초 뒤 재시작 → 스레드 종료 대기 → 재시도). 다른 워커 회귀는 `[INFRA-097]` 의 `infra097qa_run.py <사본> run 2 -- stop_restart`

## 시나리오

### S-1. 같은 워커에서 중단 0.5초 뒤 재시작하면 거부되고 옛 실행이 멈춘다 (하네스, 필수)
- 조작: 두 사본에서 `infra099qa_harness.py`
- 기대: 수정 전은 재시작이 받아들여지고(`restart_result` null, `startTime` 바뀜) 옛 실행이 중단을 보지 못한 채 10초를 채운다(`stop_seen_after` null, `[INFRA-097]` S-4 와 같음). 수정 뒤는 `restart_result` false, 재시작 직후 상태의 `startTime` 이 처음 것 그대로이고 `stopRequested` true, 옛 실행이 약 1초(2초 이내)에 중단을 본다
- 실제:

### S-2. 옛 실행이 끝난 뒤의 재시도는 받아들여지고 표시와 플래그가 남지 않는다 (하네스, 필수)
- 조작: S-1 의 스레드 종료 뒤 출력
- 기대: 수정 뒤 `active_after_join` false, `flag_after_join` false, `retry_result` true, 재시도 뒤 상태 `isRunning` true·`stopRequested` false
- 실제:

### S-3. 다른 워커로 간 재시작은 종전처럼 받아들여지고 옛 실행이 멈춘다 (하네스, 필수, 회귀)
- 조작: 수정 뒤 사본에서 `infra097qa_run.py <사본> run 2 -- stop_restart`
- 기대: `[INFRA-097]` QA S-3 2차와 같다. A 가 약 1초에 중단을 봄, 최종 `isRunning` true·`startTime` 이 B 의 새 실행 것, A 최종 플래그 false
- 실제:

## 정리
- 실제:
