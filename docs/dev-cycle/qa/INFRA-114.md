# [INFRA-114] 기동 초기화가 `v2_screener_status.json` 과 스케줄러 런타임 상태를 조건 없이 지운다 — QA 기록

- 대상: `app/__init__.py` 의 `_reset_startup_status_files`(V2 보존 판정), `services/scheduler_runtime_status_service.py` 의 `set_scheduler_runtime_status`(pid 기록)·`reset_scheduler_runtime_status`(보존 판정), `app/routes/kr_market_jongga_execution_routes.py` 의 `_save_v2_status`(pid 기록), `services/common_update_status_service.py` 의 `owned_by_live_sibling`, `services/kr_market_jongga_runtime_service.py` 의 저장 순서
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25(설계 승인·계획 검토·리뷰 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 11:26:45~11:27:22(수정 뒤)·11:27:22~11:28:00(수정 전)
- 검증 기준 커밋: `803d298d`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `003105ef`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화, 확인 시각 11:13), critic ACCEPT-WITH-RESERVATIONS, `closing-bet-reviewer` APPROVE, 심층 리뷰 차단 0. 호출 경로는 gunicorn 워커 기동 → `flask_app` → `create_app` → `_reset_startup_status_files`
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 결함의 계기는 화면 조작이 아니라 gunicorn 이 워커 하나를 다시 띄우는 일이다. 화면이 읽는 값은 공개 GET 세 개(`/api/kr/jongga-v2/status`, `/api/system/update-status`, `/api/kr/signals/status`)의 응답과 같으므로 그 응답과 상태 파일로 판정한다. 실제 V2 실행과 스케줄러 체인은 LLM·KRX 를 부르는 금지 조작이라 실행 중 상태는 상태 파일에 직접 써서 만든다(pid 기록 자체는 단위 테스트가 맡는다)
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 루트에서 `SCHEDULER_ENABLED=false` 로 저장소 venv 의 gunicorn 을 `--workers 2 --threads 4 --keep-alive 0` 으로 띄운다. 포트는 5613(수정 뒤)·5614(수정 전)이며 원본 3500·5501·운영 주소·원본 `data/`·`.env` 는 쓰지 않는다. 보내는 요청은 위 GET 세 개뿐이다
- 하네스: 세션 스크래치의 `infra114qa_harness.py`(사본 경로가 아니거나 포트가 3500·5501 이면 거부). 워커 교체 뒤 새 워커의 `create_app` 완료를 12초 기다린 다음 읽는다
- 필수 여부(required): S-1~S-4 예
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(하네스 출력 원문의 요약), scratchpad `qa-infra114-new.txt`·`qa-infra114-old.txt`, 두 실행 모두 exit 0

## 시나리오

### S-1. 소유하지 않은 워커가 다시 떠도 V2 실행과 스케줄러 표시가 남는다 (gunicorn 실측, 필수, 회귀)
- 조작: 워커 A·B 가 뜬 뒤 V2 파일에 `isRunning:true`, 스케줄러 파일에 `is_data_scheduling_running:true`·`is_vcp_scheduling_running:true` 를 `ownerPid=A`·`ownerPpid=마스터` 로 쓴다. 워커 B 를 `kill -9`, 새 워커 C 가 응답할 때까지 기다린다
- 기대: 수정 뒤 두 파일 그대로, GET V2 `isRunning:true`, update-status `isRunning:true`·「전체 스케쥴링 작업 진행 중인 상태」, signals `schedulerRunning:true`, 세 응답 모두 `ownerPid` 없음, 로그 「V2 reset skipped」. 수정 전은 V2 `{"isRunning": false}`·스케줄러 세 플래그 false(결함 재현)
- 실제: 수정 뒤 마스터 47148, A=47196·B=47197, B 교체 워커 47753. 파일 V2 `isRunning:true`·`ownerPid 47196`·`ownerPpid 47148`, 스케줄러 data·vcp true 그대로. GET V2 `isRunning:true`, update-status `isRunning:true`·「전체 스케쥴링 작업 진행 중인 상태」, signals `running:true`·`schedulerRunning:true`, 세 응답 모두 `ownerPid` 없음, 로그 「V2 reset skipped」 1회. 수정 전(마스터 48271, B 교체 48354) 두 파일 모두 초기화(V2 `{"isRunning": false}`, 세 플래그 false)·세 GET 실행 중 아님(결함 재현). 통과

### S-2. 소유 워커가 죽으면 대체 워커가 두 상태를 내린다 (gunicorn 실측, 필수)
- 조작: S-1 뒤 워커 A 를 `kill -9`, 새 워커 D 가 응답할 때까지 기다린다
- 기대: 수정 전후 모두 V2 `{"isRunning": false}`, 스케줄러 세 플래그 false, 세 GET 실행 중 아님
- 실제: 수정 뒤 A(47196) 교체 워커 48006 기동 뒤 V2 `{"isRunning": false}`·세 플래그 false, 세 GET 실행 중 아님, 「V2 reset skipped」 누계 1회 그대로. 수정 전도 같은 결과. 통과

### S-3. 전체 재기동은 소유자 pid 가 살아 있어도 초기화한다 (gunicorn 실측, 필수, 회귀)
- 조작: gunicorn 을 끝낸 뒤 두 파일에 `ownerPid=하네스 자신(살아 있음)`·`ownerPpid=옛 마스터` 로 실행 중 상태를 쓰고 새 마스터로 다시 띄운다
- 기대: 수정 전후 모두 V2 `{"isRunning": false}`, 스케줄러 세 플래그 false
- 실제: 수정 뒤 `ownerPid=47104`(하네스, 살아 있음)·`ownerPpid=47148`(옛 마스터)를 새 마스터로 기동 → V2 `{"isRunning": false}`·세 플래그 false, 세 GET 실행 중 아님. 수정 전도 같은 결과. 통과

### S-4. 배포 직후의 옛 형식 파일(pid 없음)은 종전처럼 초기화한다 (gunicorn 실측, 필수)
- 조작: gunicorn 을 끝낸 뒤 pid 없는 실행 중 상태를 두 파일에 쓰고 다시 띄운다
- 기대: 수정 전후 모두 V2 `{"isRunning": false}`, 스케줄러 세 플래그 false. 원본 `data/` 두 파일 수정 시각 불변, 띄운 gunicorn 모두 종료
- 실제: 수정 뒤·전 모두 V2 `{"isRunning": false}`·세 플래그 false, 세 GET 실행 중 아님. 두 하네스에서 원본 `data/` 두 파일 수정 시각 실행 전후 불변(`True`), 종료 뒤 해당 포트 프로세스 없음(`False`). 통과

## 범위와 한계 기록(시나리오 아님)
- graceful 재기동(HUP)이나 같은 마스터 안의 pid 재사용으로 V2 `isRunning` 이 남으면 다음 전체 재기동까지 409 가 남는다. 스케줄러 플래그는 다음 잡의 `finally` 가 푼다. `restart_all.sh` 는 HUP 를 쓰지 않는다
- 저장 순서와 스레드 시작 실패 되돌림은 단위 테스트(`tests/services/test_kr_market_jongga_runtime_service_refactor.py`)가 맡는다. 실제 V2 실행 요청은 LLM 비용이 드는 금지 조작이라 QA 에서 보내지 않는다
- V2 실행 요청의 워커 사이 경쟁은 `[INFRA-115]`, 17시 체인과 수동 실행 겹침은 `[INFRA-116]` 으로 이월했다

## 정리
- 실제: 두 사본(`q114new`·`q114old`)의 gunicorn 을 하네스가 끝냈고, 사본을 리터럴 경로로 삭제한 뒤 없음 확인. 포트 5613·5614 LISTEN 0, 사본 경로 프로세스 0. 브라우저는 띄우지 않았다. 원본 `data/`·`.env`·3500·5501·운영 주소 사용 없음. 결과: 필수 4/4 통과
