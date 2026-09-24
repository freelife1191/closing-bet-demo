# [INFRA-098] 수동 업데이트 상태 파일의 읽기-수정-쓰기를 워커 사이에서 직렬화한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`·`update_item_status`·`stop_update`·`finish_update`(`<상태 파일>.lock` 의 `fcntl.flock` 안에서 파일을 직접 읽음, `finish_update(start_time=...)` 의 대체 판정), `services/common_update_service.py` 의 `finally`(바깥 비교 제거), `app/routes/common.py` 의 `run_background_update`(`finish_update` 에 이 실행의 `startTime` 을 묶음)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 07:40 | 실행 2026-09-25 07:48:20~07:49:16
- 검증 기준 커밋: `8c75ba5b`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `8aff552b`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 07:34), 호출 경로(관리자 `POST /api/system/start-update` → `start_update` → 스레드 `run_background_update` → 단계 함수의 `update_item_status`, 관리자 `POST /api/system/stop-update` → `stop_update`, 파이프라인 `finally` → `finish_update`), 계획의 Review Focus
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 상태 화면의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 결함은 두 워커의 수 ms 틈에서만 드러난다. `[INFRA-097]`·`[INFRA-101]` 과 같은 방식으로, 실제 라우트 배선을 부르는 프로세스 둘이 사본의 상태 파일을 함께 쓰게 하고 결과는 그 파일과 각 프로세스의 출력으로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다(1초 동안 중단 플래그를 보며 머문 뒤 `True`). 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra098qa_harness.py`·`infra098qa_run.py <사본> <A 모드> -- <B 역할>`. 틈을 넓히려고 A 프로세스 안에서만 저장 함수나 `finish_update_impl` 을 감싸 머물게 한다. 잠금·판정 코드는 사본 그대로다
- 필수 여부(required): S-1·S-1b·S-2·S-3 예. S-1b 는 실행 중 추가했다(아래 S-1 판정). 시그니처 캐시 경합(같은 틱·같은 크기의 저장)은 프로세스 사이에서 결정적으로 만들 수 없어 단위 테스트 `test_mutation_reads_file_not_stale_signature_cache` 와 변이 확인으로 대신한다
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(실행기 출력 원문의 요약). 사본의 `_status_file_lock` 은 수정 전 0건·수정 뒤 5건으로 두 사본이 서로 다른 커밋임을 확인했다

## 시나리오

### S-1. 항목 저장 틈에 끼어든 다른 워커의 중단이 남는다 (하네스, 필수)
- 조작: 두 사본에서 `infra098qa_run.py <사본> slow_item -- stop_in_item`. A 는 「Daily Prices running」 을 읽은 뒤 쓰기 전에 1.5초 머물고, B 는 그 틈에 `stop_update` 를 부른다
- 기대: 수정 전은 B 가 곧바로 돌아오고(`stop_update_seconds` 약 0), A 의 저장이 중단을 덮어 최종 `stopRequested` 가 없거나 false, A 는 중단을 보지 못함(`stop_seen_after` null, 결함 재현). 수정 뒤는 B 가 A 의 저장이 끝날 때까지 기다리고(약 1.5초 이내), 최종 `stopRequested` true·`isRunning` false, A 가 중단을 봄, 잠금 파일 존재
- 실제: 07:48:20 실행. 수정 전: B `stop_update_seconds` 0.0, 최종 `stopRequested` false(덮임), 잠금 파일 없음. 그러나 A 는 중단을 봤다(`stop_seen_after` 0.0). 감시 주기(`STOP_WATCH_INTERVAL_SECONDS` 1.0초)가 하네스의 틈(1.5초)보다 짧아 A 의 저장 전에 감시가 파일의 중단을 먼저 읽었다. 파일의 중단 손실은 재현됐지만 파이프라인까지의 손실은 가려졌으므로 기대와 다르다. 운영의 틈은 수 ms 라 감시가 그 사이에 읽을 일은 드물다. 이 차이를 가리려고 S-1b 를 더했다. 수정 뒤: B 1.52초 대기, 최종 `stopRequested` true·`isRunning` false, A `stop_seen_after` 0.54, 잠금 파일 있음, 두 프로세스 exit 0·Traceback 없음. 수정 뒤 기대는 충족, 판정은 S-1b 와 함께 통과
- 관찰: 두 사본 모두 최종 `Daily Prices` 가 `done` 이다. 중단 뒤 같은 실행의 수집기가 끝나며 쓴 값으로, `[INFRA-101]` 계획의 알려진 한계 4(같은 실행 안의 중단 뒤 쓰기)와 같다

### S-1b. 감시가 틈 안에서 읽지 못할 때 중단이 파이프라인까지 사라지지 않는다 (하네스, 필수, 실행 중 추가)
- 조작: 두 사본에서 `infra098qa_run.py <사본> slow_item_slowwatch -- stop_in_item`. S-1 과 같되 A 프로세스에서만 감시 주기를 3초(틈 1.5초보다 김)로, 가짜 수집기의 최대 대기를 10초로 둔다
- 기대: 수정 전은 A 가 중단을 보지 못하고 10초를 다 돈다(`stop_seen_after` null), 최종 `stopRequested` false. 수정 뒤는 감시의 첫 읽기(파이프라인 시작 3초 뒤)에서 중단을 봄, 최종 `stopRequested` true
- 실제: 07:48:59 실행. 수정 전: `stop_seen_after` null(A 가 약 12초 뒤 끝남), 최종 `stopRequested` false, B 0.0초(결함 재현). 수정 뒤: `stop_seen_after` 1.5(수집 시작 1.5초 = 틈 뒤 감시 첫 읽기), 최종 `stopRequested` true·`isRunning` false, B 1.5초 대기, 두 프로세스 exit 0·Traceback 없음. 통과

### S-2. 대체된 옛 실행의 finish 가 새 실행을 끝내지 않는다 (하네스, 필수)
- 조작: 두 사본에서 `infra098qa_run.py <사본> slow_finish -- restart_on_finish`. A 의 수집이 끝나 `finish_update_impl` 에 들어가면(수정 전은 바깥 비교를 통과한 뒤) B 가 새 실행을 시작하고, A 는 그 뒤에 원래 finish 를 부른다
- 기대: 수정 전은 최종 `startTime` 이 B 것인데 `isRunning` false(결함 재현). 수정 뒤는 `startTime` 이 B 것이고 `isRunning` true, A 로그의 「Finish skipped for replaced run」 1회
- 실제: 07:48:27 실행. 수정 전: B 새 실행 수락(`accepted` true), 최종 `startTime` 이 B 것(`final_startTime_is_mine` false)인데 `isRunning` false(결함 재현), 거른 finish 0. 수정 뒤: 최종 `startTime` 이 B 것·`isRunning` true, A 의 거른 finish 1회, 두 프로세스 exit 0·Traceback 없음. 통과

### S-3. 경합이 없으면 종전처럼 끝난다 (하네스, 필수, 회귀)
- 조작: 수정 뒤 사본에서 `infra098qa_run.py <사본> plain -- none`
- 기대: 최종 `isRunning` false, `startTime` 이 A 것, `Daily Prices` `done`, `stopRequested` false, 프로세스 exit 0·Traceback 없음, 잠금 파일 존재
- 실제: 07:48:32 실행. `final_isRunning` false, `final_startTime_is_mine` true, `Daily Prices: done`, `stopRequested` false, 중단 없음(`stop_seen_after` null), 잠금 파일 있음, exit 0·Traceback 없음. 통과

## 정리
- 실제: 사본 둘(`q098old`·`q098new`)과 critic 이 변이 검사용으로 만든 스크래치 사본 `i098`(`.env` 없음, `data/` 에는 사본 테스트가 만든 `runtime_cache.db` 뿐)을 리터럴 경로로 지우고 없음 확인. 하네스 프로세스 0, 서버를 띄우지 않았고 3500·5501 리스너 0. 원본 `data/update_status.json` 수정 시각(1777948277) 실행 전후 그대로, 원본 `data/` 에 `update_status.json.lock` 없음. 소켓 차단으로 네트워크 없음, KRX 로그인·LLM 호출 없음. 결과: 필수 4/4 통과
