# [INFRA-115] 종가베팅 V2 실행 요청의 워커 사이 직렬화 — QA 기록

- 대상: `launch_jongga_v2_screener`(`services/kr_market_jongga_runtime_service.py`)의 확인·저장을 `status_lock` 안에서 수행, 라우트(`app/routes/kr_market_jongga_execution_routes.py`)가 `v2_screener_status.json.lock` 을 잡는 `_status_file_lock` 을 넘김, 기동 초기화(`app/__init__.py` `_reset_startup_status_files`)의 V2 읽기·쓰기를 같은 잠금으로 감쌈
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 구성 2026-09-25(설계 승인 14:03 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 (미실행)
- 검증 기준 커밋: (이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `ff61fbf7`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 14:03). 실행 요청은 관리자 `POST /api/kr/jongga-v2/run` 이고 gunicorn 워커(프로세스) 둘이 같은 `data/v2_screener_status.json` 을 공유한다. 기동 초기화는 워커가 뜰 때마다 돈다
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면의 실행 버튼은 이 라우트를 부르며 응답 형식(200·409 본문)은 바뀌지 않는다. 결함은 두 워커 프로세스가 동시에 요청을 받을 때만 드러나고, 브라우저 한 개로는 두 워커에 동시에 요청을 나눠 보낼 수 없다. 원본 서버에 실행 요청을 보내면 실제 LLM 분석이 돌기 때문에(되돌릴 수 없는 비용) 금지다. 그래서 사본에서 별도 프로세스 둘이 실제 라우트를 Flask 테스트 클라이언트로 부르고, 백그라운드 분석은 시작 흔적만 남기는 가짜로 바꾼다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지운다. 하네스는 소켓 연결을 막는다. 서버와 포트는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra115qa_harness.py main <사본>`(사본 경로가 scratchpad 가 아니면 거부)
- 필수 여부(required): S-1~S-3 예
- 반복(iteration): (미실행)
- 결과: (미실행)
- 증거: (미실행)

## 시나리오

### S-1. 두 프로세스가 같은 순간 실행을 요청하면 하나만 시작한다 (하네스, 필수)
- 조작: `isRunning` False 에서 프로세스 둘이 같은 시각에 실행 라우트를 부른다. 상태 읽기 뒤 0.3초 지연을 넣어 확인과 저장 사이의 틈을 넓힌다
- 기대: 수정 뒤 응답 `[200, 409]`, 백그라운드 시작 1회, 끝난 뒤 `isRunning` False. 수정 전은 `[200, 200]`, 시작 2회(결함 재현)
- 실제: (미실행)

### S-2. 다른 프로세스가 V2 잠금을 쥐고 있으면 기동 초기화가 기다린다 (하네스, 필수)
- 조작: `isRunning` True(소유자 없음)를 두고, 한 프로세스가 `v2_screener_status.json.lock` 을 1.0초 쥔 사이에 다른 프로세스가 `_reset_startup_status_files` 를 부른다
- 기대: 수정 뒤 소요 약 0.8초 이상, 끝난 뒤 `isRunning` False. 수정 전은 기다리지 않고(0.1초 미만) 곧바로 False
- 실제: (미실행)

### S-3. 회귀: 실행 중이면 409, 끝난 뒤에는 다시 200 (하네스, 필수)
- 조작: `isRunning` True 에서 한 번, False 로 바꾼 뒤 한 번 실행 라우트를 부른다
- 기대: 수정 전후 모두 409 다음 200, 백그라운드 시작 1회, 끝난 뒤 `isRunning` False
- 실제: (미실행)

## 정리
- 실제: (미실행)
