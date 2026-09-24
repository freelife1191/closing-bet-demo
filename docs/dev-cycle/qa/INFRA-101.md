# [INFRA-101] 대체된 옛 수동 업데이트가 새 실행의 항목 상태를 덮어쓰지 않게 한다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `update_item_status`(`start_time` 이 상태의 `startTime` 과 다르면 쓰지 않음), `app/routes/common.py` 의 `run_background_update`(진입 때의 `LOCAL_RUN_START_TIME` 을 묶은 콜백)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-25 06:34
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `086a807`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 06:30), 호출 경로(관리자 `POST /api/system/start-update`·`/api/kr/refresh`·`/api/kr/init-data` → `start_update` → 스레드 `run_background_update` → 단계 함수의 `update_item_status(name, code)`), `[INFRA-099]` QA S-3 관찰(새 실행의 `Daily Prices` 가 시작 전에 `done`), 계획의 알려진 한계 4(같은 실행 안의 중단 뒤 쓰기는 판정 밖)
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 상태 화면의 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 결함은 워커 둘 사이에서만 드러난다. 결과는 공유 상태 파일의 항목 값과 워커 A 의 로그로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부한다. 소켓 연결을 막고, 수집기는 가짜 `init_data.create_daily_prices` 하나다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra101qa_run.py <사본> <A 인자> -- <B 역할>`. `[INFRA-097]` 하네스를 대화 기록에서 복원하고 INFO 로그 출력과 A 로그의 「Item status skipped for replaced run」 횟수 집계만 더했다. A 는 실제 `app.routes.common` 배선으로 시작해 파이프라인을 돌리고, 가짜 수집기는 중단 플래그를 보면 `<hold>` 초 뒤 `True` 로 끝난다. B 는 A 가 수집을 시작하면 중단하고, `stop_restart` 면 0.5초 뒤 새 실행을 `start_update` 로 시작한다(스레드 없이 상태만)
- 전제: S-1 의 거른 쓰기는 A 의 `done` 쓰기가 B 의 재시작 뒤에 일어날 때만 생긴다. A 는 중단을 본 뒤 `hold` 2초를 머물고, B 는 중단 0.5초 뒤 재시작하므로 이 순서가 성립한다(심층 리뷰 지적)
- 필수 여부(required): S-1~S-3 예
- 반복(iteration): 0회

## 시나리오

### S-1. 다른 워커의 새 실행 항목을 옛 실행이 덮어쓰지 않는다 (하네스, 필수)
- 조작: 두 사본에서 `infra101qa_run.py <사본> 2 -- stop_restart`
- 기대: 수정 전(`086a807`)은 최종 상태의 `startTime` 이 B 의 새 실행 것인데 그 `Daily Prices` 가 `done`(옛 실행이 씀, 결함 재현). 수정 뒤는 같은 상태에서 `Daily Prices` 가 `pending`, A 로그의 거른 쓰기 1회 이상
- 실제:

### S-2. 대체되지 않은 실행은 종전처럼 자기 항목을 쓴다 (하네스, 필수, 회귀)
- 조작: 수정 뒤 사본에서 `infra101qa_run.py <사본> 0 -- none`(A 하나, 중단 없음, 가짜 수집기는 10초 뒤 끝남)
- 기대: 최종 `isRunning` false, `startTime` 이 A 것, `Daily Prices` 가 `done`, 거른 쓰기 0
- 실제:

### S-3. 다른 워커 중단·재시작의 종전 동작은 그대로다 (하네스, 필수, 회귀)
- 조작: S-1 의 수정 뒤 출력
- 기대: `[INFRA-099]` QA S-3 와 같다. A 가 약 1초(2초 이내)에 중단을 봄, 최종 `isRunning` true·`startTime` 이 B 것, A 최종 플래그 false, 두 프로세스 exit 0·Traceback 없음
- 실제:

## 정리
- 실제:
