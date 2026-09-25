# [INFRA-116] 17시 스케줄러 체인과 수동 V2 실행의 실행권 공유 — QA 기록

- 대상: `run_jongga_v2_analysis`(`services/scheduler_jobs.py`)가 `_status_file_lock` 안에서 `v2_screener_status.json` 으로 실행권을 잡고(`_claim_v2_run`), 수동 실행 중이면 기다리며(`_wait_and_claim_v2_run`), 끝나면 내림. 저장은 `write_v2_status`(`services/kr_market_jongga_runtime_service.py`)로 라우트와 공유
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25(설계 승인 14:19 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 14:30:36~14:31:05
- 검증 기준 커밋: `964a5f81`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `c031d4c1`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 14:19). 체인은 리더 워커의 스케줄러 스레드에서 돌고, 수동 실행은 아무 워커의 요청 스레드가 받는다. 둘 다 cwd 기준 `data/v2_screener_status.json` 을 쓴다
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면의 실행 버튼이 부르는 라우트의 응답 형식(200·409 본문)은 바뀌지 않는다. 결함은 스케줄러 잡과 수동 요청이 서로 다른 스레드·프로세스에서 겹칠 때만 드러나고, 17시 잡은 브라우저로 부를 수 없다. 원본 서버에 실행 요청을 보내면 실제 LLM 분석이 돌기 때문에 금지다. 그래서 사본에서 체인 프로세스와 라우트 프로세스(Flask 테스트 클라이언트)를 따로 띄우고, 분석은 시작·끝 흔적만 남기는 가짜로 바꾼다. 대기 간격·한도는 하네스가 0.2초·수 초로 줄인다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지운다. 하네스는 소켓 연결을 막는다. 서버와 포트는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra116qa_harness.py main <사본>`(사본 경로가 scratchpad 가 아니면 거부)
- 필수 여부(required): S-1~S-4 예
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(하네스 `RESULT` 줄 원문, scratchpad `qa-infra116-old.txt`·`qa-infra116-new.txt`), 두 실행 모두 exit 0, stderr 소켓 차단 예외 0건

## 시나리오

### S-1. 체인이 분석하는 동안 들어온 수동 요청은 409 를 받는다 (하네스, 필수)
- 조작: `isRunning` False 에서 체인 프로세스가 3초짜리 분석을 시작한 뒤 다른 프로세스가 실행 라우트를 부른다
- 기대: 수정 뒤 수동 409, 수동 분석 시작 없음, 체인 True, 끝난 뒤 `isRunning` False. 수정 전은 수동 200 과 수동 분석 시작(결함 재현)
- 실제: 수정 뒤 수동 409, 수동 분석 시작 없음, 체인 True, 끝난 뒤 False. 수정 전 수동 200, 수동 분석 시작(결함 재현). 통과

### S-2. 수동 분석 중에 시작한 체인은 끝나기를 기다렸다가 분석한다 (하네스, 필수)
- 조작: 수동 요청으로 3초짜리 분석을 시작한 뒤 체인 프로세스를 띄운다(대기 한도 20초)
- 기대: 수정 뒤 순서 `manual-start, manual-end, chain-start, chain-end`, 겹침 없음, 체인 True, 끝난 뒤 False. 수정 전은 체인이 곧바로 시작해 겹침(결함 재현)
- 실제: 수정 뒤 순서 `manual-start, manual-end, chain-start, chain-end`, 겹침 없음, 수동 끝 뒤 0.08초에 체인 시작, 체인 True, 끝난 뒤 False. 수정 전 `manual-start, chain-start, chain-end, manual-end`, 겹침(체인이 수동 끝보다 2.14초 먼저 시작, 결함 재현). 통과

### S-3. 한도를 넘기면 분석 없이 False, 남의 실행권은 그대로 둔다 (하네스, 필수)
- 조작: `isRunning` True(수동 실행 중 가정)를 두고 한도 2초로 체인을 부른다
- 기대: 수정 뒤 체인 False, 분석 시작 없음, 소요 약 2초, `isRunning` True 유지. 수정 전은 곧바로 분석해 True 반환
- 실제: 수정 뒤 체인 False, 분석 시작 없음, 소요 3.0초(프로세스 기동·import 약 1초 + 한도 2초), `isRunning` True 유지. 수정 전 체인 True, 분석 시작, 1.5초. 통과

### S-4. 회귀: 아무것도 돌지 않으면 수동 200, 체인 단독 True (하네스, 필수)
- 조작: `isRunning` False 에서 수동 요청 한 번, 끝난 뒤 체인 한 번
- 기대: 수정 전후 모두 수동 200, 수동 뒤 False, 체인 True, 끝난 뒤 False
- 실제: 수정 전후 모두 수동 200, 수동 뒤 False, 체인 True, 끝난 뒤 False. 통과

## 정리
- 실제: 두 사본(`q116old`·`q116new`)을 리터럴 경로로 삭제(남은 사본 0), 하네스 프로세스 0. 원본 `data/` 에서 QA 직전(14:30:30) 뒤 수정된 파일 0개(`find data -newermt`, 14:31:13 확인). 서버·포트·브라우저는 쓰지 않았다. 원본 `data/`·`.env` 사용 없음. 결과: 필수 4/4 통과
