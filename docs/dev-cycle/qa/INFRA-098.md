# [INFRA-098] 수동 업데이트 상태 파일의 읽기-수정-쓰기를 워커 사이에서 직렬화한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`·`update_item_status`·`stop_update`·`finish_update`(`<상태 파일>.lock` 의 `fcntl.flock` 안에서 파일을 직접 읽음, `finish_update(start_time=...)` 의 대체 판정), `services/common_update_service.py` 의 `finally`(바깥 비교 제거), `app/routes/common.py` 의 `run_background_update`(`finish_update` 에 이 실행의 `startTime` 을 묶음)
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 구성 2026-09-25
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `8aff552b`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 07:34), 호출 경로(관리자 `POST /api/system/start-update` → `start_update` → 스레드 `run_background_update` → 단계 함수의 `update_item_status`, 관리자 `POST /api/system/stop-update` → `stop_update`, 파이프라인 `finally` → `finish_update`), 계획의 Review Focus
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 상태 화면의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 결함은 두 워커의 수 ms 틈에서만 드러난다. `[INFRA-097]`·`[INFRA-101]` 과 같은 방식으로, 실제 라우트 배선을 부르는 프로세스 둘이 사본의 상태 파일을 함께 쓰게 하고 결과는 그 파일과 각 프로세스의 출력으로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다(1초 동안 중단 플래그를 보며 머문 뒤 `True`). 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra098qa_harness.py`·`infra098qa_run.py <사본> <A 모드> -- <B 역할>`. 틈을 넓히려고 A 프로세스 안에서만 저장 함수나 `finish_update_impl` 을 감싸 머물게 한다. 잠금·판정 코드는 사본 그대로다
- 필수 여부(required): S-1~S-3 예. 시그니처 캐시 경합(같은 틱·같은 크기의 저장)은 프로세스 사이에서 결정적으로 만들 수 없어 단위 테스트 `test_mutation_reads_file_not_stale_signature_cache` 와 변이 확인으로 대신한다
- 반복(iteration): 1회
- 결과: 미실행

## 시나리오

### S-1. 항목 저장 틈에 끼어든 다른 워커의 중단이 남는다 (하네스, 필수)
- 조작: 두 사본에서 `infra098qa_run.py <사본> slow_item -- stop_in_item`. A 는 「Daily Prices running」 을 읽은 뒤 쓰기 전에 1.5초 머물고, B 는 그 틈에 `stop_update` 를 부른다
- 기대: 수정 전은 B 가 곧바로 돌아오고(`stop_update_seconds` 약 0), A 의 저장이 중단을 덮어 최종 `stopRequested` 가 없거나 false, A 는 중단을 보지 못함(`stop_seen_after` null, 결함 재현). 수정 뒤는 B 가 A 의 저장이 끝날 때까지 기다리고(약 1.5초 이내), 최종 `stopRequested` true·`isRunning` false, A 가 중단을 봄, 잠금 파일 존재
- 실제:

### S-2. 대체된 옛 실행의 finish 가 새 실행을 끝내지 않는다 (하네스, 필수)
- 조작: 두 사본에서 `infra098qa_run.py <사본> slow_finish -- restart_on_finish`. A 의 수집이 끝나 `finish_update_impl` 에 들어가면(수정 전은 바깥 비교를 통과한 뒤) B 가 새 실행을 시작하고, A 는 그 뒤에 원래 finish 를 부른다
- 기대: 수정 전은 최종 `startTime` 이 B 것인데 `isRunning` false(결함 재현). 수정 뒤는 `startTime` 이 B 것이고 `isRunning` true, A 로그의 「Finish skipped for replaced run」 1회
- 실제:

### S-3. 경합이 없으면 종전처럼 끝난다 (하네스, 필수, 회귀)
- 조작: 수정 뒤 사본에서 `infra098qa_run.py <사본> plain -- none`
- 기대: 최종 `isRunning` false, `startTime` 이 A 것, `Daily Prices` `done`, `stopRequested` false, 두 프로세스 exit 0·Traceback 없음, 잠금 파일 존재
- 실제:

## 정리
- 실제:
