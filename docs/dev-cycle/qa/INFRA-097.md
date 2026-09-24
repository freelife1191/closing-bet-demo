# [INFRA-097] 관리자 중단 요청을 모든 워커에 전달한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`·`stop_update`(공유 상태의 `stopRequested`), `services/common_update_service.py` 의 `run_background_update_pipeline`(감시 스레드와 옛 실행의 `finally` 가드), `app/routes/common.py` 의 배선
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 22:52:06
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `d30ced0`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 22:48), 호출 경로(관리자 `POST /api/system/stop-update` → `ctx.stop_update` → `stop_update_impl`, `start-update` → 스레드 `run_background_update`), TODO 원인 줄
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 현황 페이지의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 결함은 워커가 둘일 때만 드러나 로컬 단일 dev 서버로는 재현되지 않는다. 결과는 프로세스별로 관측한 플래그 값과 공유 상태 파일로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다. 시작·중단·상태 읽기와 파이프라인은 라우트가 쓰는 실제 `app.routes.common` 함수를 부른다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra097qa_harness.py <run <hold>|stop|stop_restart>`. 워커 A(`run`)와 워커 B 를 별도 프로세스로 동시에 띄운다

- 범위 밖으로 확인한 동작(`closing-bet-reviewer` 지적 8, 승인된 설계): 중단 버튼은 17:00 체인을 멈추지 않는다. 체인이 도는 중 버튼을 누르면 화면은 `is_data_scheduling_running` 때문에 계속 실행 중으로 보이고, `stop_update` 는 지난 수동 실행의 항목을 cancelled/error 로 바꾸며 `stopRequested` 를 남긴다. 이 문서의 시나리오는 이 동작을 검사하지 않는다

## 시나리오

### S-1. 다른 워커에 닿은 중단 요청이 작업을 멈춘다 (하네스, 필수)
- 조작: 두 사본에서 A `run 0` 과 B `stop` 을 동시에 띄운다. B 는 A 가 수집을 시작한 것을 보고 중단한다
- 기대: 수정 전은 A 가 중단을 보지 못하고 10초를 채운다(`stop_seen_after` null), B 의 플래그 true. 수정 뒤는 A 가 약 1초(2초 이내) 안에 중단을 본다. A 의 최종 플래그 false, 상태 `isRunning` false
- 실제:

### S-2. 중단 요청을 받은 워커에 플래그가 남지 않는다 (하네스, 필수)
- 조작: S-1 의 B 출력
- 기대: 수정 전은 B 의 `flag_after_stop` true(그 워커의 개별 실행이 막힘). 수정 뒤는 false, 상태의 `stopRequested` true
- 실제:

### S-3. 중단된 옛 실행이 늦게 끝나도 새 실행의 상태를 끝내지 않는다 (하네스, 필수)
- 조작: A `run 2`(중단을 본 뒤 2초 더 머묾)와 B `stop_restart`(중단 0.5초 뒤 새 업데이트 시작)
- 기대: 수정 전은 A 가 중단을 보지 못한 채 끝나며, A 의 `finish_update` 가 새 실행의 `isRunning` 을 false 로 바꾼다. 수정 뒤는 A 가 중단을 본 뒤 끝나고, 최종 상태의 `startTime` 이 B 의 새 실행 것이며 `isRunning` true 로 남는다. A 의 최종 플래그는 false(리뷰 지적 1)
- 실제:

## 정리
- 실제:
