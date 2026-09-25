# [INFRA-118] 수동 V2 실행 종료 시 실행권 해제 단일화 — QA 기록

- 대상: `run_jongga_v2_background_pipeline`(`services/kr_market_route_service.py`·`services/kr_market_jongga_runtime_service.py`)이 상태를 쓰지 않고, 실행권은 `launch_jongga_v2_screener` 가 잠금 안에서 잡아 `_run_wrapper` `finally` 에서 한 번만 내린다
- 단계(phase): 시나리오 구성 완료 | 실행 전
- 구성 2026-09-25(설계 승인 14:35 뒤, 실행 전, 분 단위 시각은 기록하지 않음)
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `025b51c5`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 14:35). 결함은 수동 실행이 끝날 때 두 번 쓰는 False 사이에 `[INFRA-116]` 체인이 실행권을 잡을 때만 드러난다
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 실행 라우트의 응답 형식(200·409 본문)은 바뀌지 않고, 결함은 17시 스케줄러 잡과 수동 실행이 서로 다른 프로세스에서 겹칠 때만 드러나며 스케줄러 잡은 브라우저로 부를 수 없다. 원본 서버에 실행 요청을 보내면 실제 LLM 분석이 돌기 때문에 금지다. 그래서 사본에서 체인 프로세스와 라우트 프로세스(Flask 테스트 클라이언트, 실제 라우트·launcher·파이프라인 본체)를 따로 띄우고, `engine.generator.run_screener` 만 시작·끝 흔적을 남기는 가짜로 바꾼다
- 틈 넓히기: 수정 전 두 False 사이의 틈은 로그 한 줄 길이라 폴링으로 맞추기 어렵다. 하네스의 logger 는 「Status reset to False」 로그에서 1.5초 멈춘다. 수정 전에는 이 로그가 두 False 사이에 있고, 수정 뒤에는 유일한 False 뒤에 있다. 체인 대기 간격은 0.2초로 줄인다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지운다. 하네스는 소켓 연결을 막는다. 서버와 포트는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra118qa_harness.py main <사본>`(사본 경로가 scratchpad 가 아니면 거부)
- 필수 여부(required): S-1·S-2 예
- 반복(iteration): 1회
- 결과:
- 증거:

## 시나리오

### S-1. 수동 실행이 끝날 때 대기하던 체인의 실행권을 덮지 않는다 (하네스, 필수)
- 조작: `isRunning` False 에서 수동 요청으로 1초짜리 분석을 시작하고, 그 사이 체인 프로세스(분석 5초, 대기 한도 20초)를 띄운다. 체인이 시작하고 2초 뒤 `isRunning` 을 읽고 두 번째 수동 요청을 보낸다
- 기대: 수정 뒤 체인이 도는 동안 `isRunning` True, 두 번째 수동 409, 두 번째 수동 분석 시작 없음, 체인 True, 체인이 수동 끝 뒤에 시작, 끝난 뒤 False. 수정 전은 두 번째 False 가 체인의 True 를 덮어 `isRunning` False, 두 번째 수동 200 과 분석 시작(결함 재현)
- 실제:

### S-2. 회귀: 아무것도 돌지 않으면 수동 요청 200, 끝난 뒤 False, 다시 요청해도 200 (하네스, 필수)
- 조작: `isRunning` False 에서 수동 요청 한 번, 끝난 뒤 한 번 더
- 기대: 수정 전후 모두 200, 끝난 뒤 False, 다시 200, 분석 시작 2회, 최종 False
- 실제:

## 정리
- 실제:
