# [INFRA-097] 관리자 중단 요청을 모든 워커에 전달한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`·`stop_update`(공유 상태의 `stopRequested`), `services/common_update_service.py` 의 `run_background_update_pipeline`(감시 스레드와 옛 실행의 `finally` 가드), `app/routes/common.py` 의 배선
- 단계(phase): 1차 실행 완료, S-3 일부 실패로 대기
- 구성 2026-09-24 22:52:06 | 1차 실행 2026-09-24 22:56:29~22:57:05
- 검증 기준 커밋: `3a87c29` (이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `d30ced0`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 22:48), 호출 경로(관리자 `POST /api/system/stop-update` → `ctx.stop_update` → `stop_update_impl`, `start-update` → 스레드 `run_background_update`), TODO 원인 줄
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 현황 페이지의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 결함은 워커가 둘일 때만 드러나 로컬 단일 dev 서버로는 재현되지 않는다. 결과는 프로세스별로 관측한 플래그 값과 공유 상태 파일로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다. 시작·중단·상태 읽기와 파이프라인은 라우트가 쓰는 실제 `app.routes.common` 함수를 부른다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra097qa_harness.py <run <hold>|stop|stop_restart>`. 워커 A(`run`)와 워커 B 를 별도 프로세스로 동시에 띄운다. 실행기 `infra097qa_run.py <사본> <A 인자> -- <B 역할>` 이 사본 `data/` 를 비우고 두 프로세스를 띄워 RESULT 를 모은다

- 범위 밖으로 확인한 동작(`closing-bet-reviewer` 지적 8, 승인된 설계): 중단 버튼은 17:00 체인을 멈추지 않는다. 체인이 도는 중 버튼을 누르면 화면은 `is_data_scheduling_running` 때문에 계속 실행 중으로 보이고, `stop_update` 는 지난 수동 실행의 항목을 cancelled/error 로 바꾸며 `stopRequested` 를 남긴다. 이 문서의 시나리오는 이 동작을 검사하지 않는다

## 시나리오

### S-1. 다른 워커에 닿은 중단 요청이 작업을 멈춘다 (하네스, 필수)
- 조작: 두 사본에서 A `run 0` 과 B `stop` 을 동시에 띄운다. B 는 A 가 수집을 시작한 것을 보고 중단한다
- 기대: 수정 전은 A 가 중단을 보지 못하고 10초를 채운다(`stop_seen_after` null), B 의 플래그 true. 수정 뒤는 A 가 약 1초(2초 이내) 안에 중단을 본다. A 의 최종 플래그 false, 상태 `isRunning` false
- 실제: 22:56 실행, 네 프로세스 모두 exit 0·Traceback 0. 수정 전(`d30ced0`)은 A `stop_seen_after` null(10초를 채움), 최종 항목 `done`(B 의 중단 표시를 A 의 저장이 덮음, `[INFRA-098]` 과 같은 lost update). 수정 뒤(`3a87c29`)는 A 가 1.02초에 중단을 봄, 최종 플래그 false, `isRunning` false. 통과

### S-2. 중단 요청을 받은 워커에 플래그가 남지 않는다 (하네스, 필수)
- 조작: S-1 의 B 출력
- 기대: 수정 전은 B 의 `flag_after_stop` true(그 워커의 개별 실행이 막힘). 수정 뒤는 false, 상태의 `stopRequested` true
- 실제: 수정 전 B `flag_after_stop` true, 상태 `stopRequested` 없음(null). 수정 뒤 B `flag_after_stop` false, 상태 `stopRequested` true, `stop_update` 인자에 `shared_state` 없음. 통과

### S-3. 중단된 옛 실행이 늦게 끝나도 새 실행의 상태를 끝내지 않는다 (하네스, 필수)
- 조작: A `run 2`(중단을 본 뒤 2초 더 머묾)와 B `stop_restart`(중단 0.5초 뒤 새 업데이트 시작)
- 기대: 수정 전은 A 가 중단을 보지 못한 채 끝나며, A 의 `finish_update` 가 새 실행의 `isRunning` 을 false 로 바꾼다. 수정 뒤는 A 가 중단을 본 뒤 끝나고, 최종 상태의 `startTime` 이 B 의 새 실행 것이며 `isRunning` true 로 남는다. A 의 최종 플래그는 false(리뷰 지적 1)
- 실제: 네 프로세스 모두 exit 0·Traceback 0. 수정 전은 A 가 중단을 보지 못하고(null) 끝나며 최종 `isRunning` false(새 실행 상태를 끝냄). 수정 뒤는 최종 `isRunning` true·`startTime` 이 B 의 새 실행 것(새 실행 상태를 끝내지 않음, 통과). **그러나 A 는 중단을 보지 못하고 10초를 채움(`stop_seen_after` null), 기대의 「A 가 중단을 본 뒤 끝나고」 실패.** 원인: B 가 중단 0.5초 뒤 새 실행을 시작해, A 의 감시가 1초 주기로 처음 읽을 때 이미 `startTime` 이 새 실행 것이었다. 감시는 자기 `startTime` 의 `stopRequested` 만 보므로 대체된 옛 실행은 멈추지 않고 새 실행과 함께 돈다. 수정 전에도 이 경우 옛 실행은 멈추지 않았다. 필수 실패 1회, 처리 방향은 사용자 확인 대기

### S-4. 같은 워커에서 재시작하면 옛 실행이 계속 돈다 (하네스, 기록용, 알려진 한계 `[INFRA-099]`)
- 조작: 한 프로세스(`local_restart` 모드)에서 파이프라인을 스레드로 돌리고, 수집이 시작되면 같은 프로세스에서 `stop_update` 뒤 0.5초에 `start_update`
- 기대: 수정 뒤는 옛 실행이 중단을 보지 못하고 10초를 채운다(한계의 실측). 수정 전은 같은 프로세스 중단이 플래그를 곧바로 켜므로 수집기가 0.05초 안에 중단을 본다
- 실제:

## 정리
- 실제:
