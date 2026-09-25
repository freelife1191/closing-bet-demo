# [INFRA-107] 워커가 새로 기동하면 다른 워커에서 도는 수동 업데이트의 `isRunning` 과 항목을 지운다 — QA 기록

- 대상: `services/common_update_status_service.py` 의 `start_update`(`ownerPid`·`ownerPpid` 기록)·`reset_orphaned_update_status`(잠금 안에서 같은 마스터의 살아 있는 다른 워커가 소유하면 보존), `app/__init__.py` 의 `_reset_startup_status_files`, `app/routes/common_update_routes.py` 의 공개 GET 이 두 pid 를 빼는 것
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25(설계 승인·계획 검토 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 11:07:24~11:08:01(수정 뒤)·11:08:07~11:08:44(수정 전)
- 검증 기준 커밋: `8f83b557`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `bf72577c`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화, 확인 시각 10:56), critic ACCEPT-WITH-RESERVATIONS(지적 1·3·4·5 반영, 2 는 알려진 한계). 호출 경로는 gunicorn 워커 기동 → `flask_app` → `create_app` → `_reset_startup_status_files` → `reset_orphaned_update_status`
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 결함의 계기는 화면 조작이 아니라 gunicorn 이 워커 하나를 다시 띄우는 일이다. 화면이 읽는 값은 공개 GET `/api/system/update-status` 응답과 같으므로 그 응답과 상태 파일로 판정한다. 실제 업데이트 시작은 KRX·LLM 을 부르는 금지 조작이라 실행 중 상태는 상태 파일에 직접 써서 만든다(`ownerPid` 기록 자체는 단위 테스트 `test_start_update_records_owner_pid` 가 맡는다)
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 루트에서 `SCHEDULER_ENABLED=false` 로 저장소 venv 의 gunicorn 을 `--workers 2 --threads 4 --keep-alive 0` 으로 띄운다. 포트는 5611(수정 뒤)·5612(수정 전)이며 원본 3500·5501·운영 주소·원본 `data/`·`.env` 는 쓰지 않는다. 보내는 요청은 GET `/api/system/update-status` 하나뿐이다
- 하네스: 세션 스크래치의 `infra107qa_harness.py`(사본 경로가 아니거나 포트가 3500·5501 이면 거부). 워커 교체 뒤 새 워커의 `create_app` 완료를 12초 기다린 다음 읽는다
- 필수 여부(required): S-1~S-4 예
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(하네스 출력 원문의 요약), scratchpad `qa-infra107-new.txt`·`qa-infra107-old.txt`, 두 실행 모두 exit 0

## 시나리오

### S-1. 소유하지 않은 워커가 다시 떠도 실행 중 상태가 남는다 (gunicorn 실측, 필수, 회귀)
- 조작: 워커 A·B 가 뜬 뒤 상태 파일에 `isRunning:true`, `items:[{Daily Prices, running}]`, `ownerPid=A`, `ownerPpid=마스터` 를 쓴다. 워커 B 를 `kill -9`, 마스터가 새 워커 C 를 띄우고 C 가 GET 에 응답할 때까지 기다린다
- 기대: 수정 뒤 파일과 GET 응답 모두 `isRunning:true`·항목 그대로, 파일에는 `ownerPid` 가 있고 GET 응답에는 없음, 로그 「Startup reset skipped: update owned by live worker A」. 수정 전은 `isRunning:false`·`items:[]` 와 「Reset stuck update_status.json」(결함 재현)
- 실제: 수정 뒤 마스터 97232, A=97234·B=97235, B 교체 워커 97375. 파일 `isRunning:true`·항목 그대로·`ownerPid 97234`·`ownerPpid 97232`, GET `isRunning:true`·항목 그대로·`ownerPid`·`ownerPpid` 없음, 로그 「Startup reset skipped: update owned by live worker 97234」(11:07:29), 「Reset stuck」 0회. 수정 전 파일·GET 모두 `isRunning:false`·`items:[]`, 「Reset stuck」 1회(결함 재현). 수정 전 GET 에는 파일에 쓴 pid 가 그대로 실렸다. 통과

### S-2. 소유 워커가 죽으면 대체 워커가 상태를 내린다 (gunicorn 실측, 필수)
- 조작: S-1 뒤 워커 A 를 `kill -9`, 새 워커 D 가 응답할 때까지 기다린다
- 기대: 수정 전후 모두 `isRunning:false`·`items:[]`, 「Reset stuck update_status.json」
- 실제: 수정 뒤 A(97234) 교체 워커 97517 기동 뒤 파일·GET `isRunning:false`·`items:[]`, 「Reset stuck」 누계 1회. 수정 전도 같은 결과. 통과

### S-3. 전체 재기동은 소유자 pid 가 살아 있어도 초기화한다 (gunicorn 실측, 필수, 회귀·critic 지적 1)
- 조작: gunicorn 을 끝낸 뒤 상태 파일에 `ownerPid=하네스 자신(살아 있음)`·`ownerPpid=옛 마스터` 를 쓰고 새 마스터로 다시 띄운다
- 기대: 수정 전후 모두 `isRunning:false`·`items:[]`
- 실제: 수정 뒤 `ownerPid=97213`(하네스, 살아 있음)·`ownerPpid=97232`(옛 마스터)를 새 마스터로 기동 → 파일·GET `isRunning:false`·`items:[]`. 수정 전도 같은 결과. 통과

### S-4. 배포 직후의 옛 형식 파일(`ownerPid` 없음)은 종전처럼 초기화한다 (gunicorn 실측, 필수)
- 조작: gunicorn 을 끝낸 뒤 `ownerPid`·`ownerPpid` 가 없는 실행 중 상태를 쓰고 다시 띄운다
- 기대: 수정 전후 모두 `isRunning:false`·`items:[]`. 원본 `data/` 수정 시각 불변, 띄운 gunicorn 모두 종료
- 실제: 수정 뒤·전 모두 파일·GET `isRunning:false`·`items:[]`. 두 하네스에서 원본 `data/update_status.json` 수정 시각 실행 전후 불변(`True`), 종료 뒤 해당 포트 프로세스 없음(`False`). 두 사본의 gunicorn 로그 「Reset stuck」 합계 각 3회(수정 뒤 S-2·S-3·S-4, 수정 전 S-1·S-3·S-4. 수정 전 S-2 는 S-1 에서 이미 내려진 상태라 쓰지 않았다). 통과

## 범위와 한계 기록(시나리오 아님)
- graceful 재기동(HUP)이나 같은 마스터 안의 pid 재사용으로 `isRunning` 이 남으면 관리자 `POST /api/system/stop-update` 로 푼다(critic 지적 2, `closing-bet-reviewer` low 1). `restart_all.sh` 는 HUP 를 쓰지 않는다
- 상태 파일이 없거나 깨졌고 SQLite 스냅샷이 `isRunning` 이면, 이제 기동이 초기화한 상태를 파일로 새로 쓴다. 종전에는 파일이 없으면 아무것도 하지 않았다(`closing-bet-reviewer` low 3, 계획 Review Focus)

## 정리
- 실제: 두 사본(`q107new`·`q107old`)의 gunicorn 을 하네스가 끝냈고, 사본을 리터럴 경로로 삭제한 뒤 없음 확인. 포트 5611·5612 LISTEN 0, 사본 경로 프로세스 0. 브라우저는 띄우지 않았다. 원본 `data/`·`.env`·3500·5501·운영 주소 사용 없음. 결과: 필수 4/4 통과
