# [INFRA-096] 남은 사용자 중단 플래그를 끈다 — QA 기록

- 대상: `services/common_update_service.py` 의 `run_background_update_pipeline` `finally`(플래그 해제), `services/scheduler_jobs.py` 의 `run_daily_closing_analysis` 시작(남은 플래그 해제와 경고 로그)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 22:41:35 | 실행 (공란)
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `55799f7`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 22:29), 호출 경로(관리자 중단 `stop_update` → 17:00 `run_daily_closing_analysis`·관리자 개별 실행), 계획 Review Focus
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(관리자 업데이트 시작·중단)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고, 17:00 체인은 화면이 없는 스케줄러 경로다. 결과는 단계별로 관측한 플래그 값과 저장된 CSV 로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부하고, 매 실행 사본 `data/` 를 비운다. 소켓 연결을 막고 가짜 pykrx(두 종목)를 넣으며 `get_last_trading_date` 를 09-22 로 고정한다. 가격·VCP·종가베팅·알림 단계는 그 시점의 플래그 값을 기록하는 가짜다. 중단·시작·상태 저장은 실제 `start_update`·`stop_update`·`finish_update` 를 사본 `data/` 에 대해 부른다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra096qa_harness.py <sched|plain|pipeline>`

## 시나리오

### S-1. 중단 요청이 남은 워커에서 17:00 체인이 수집을 끝까지 돈다 (하네스, 필수)
- 조작: 두 사본에서 `sched` 모드. 실제 `start_update`→`stop_update` 로 플래그를 켠 뒤 실제 `run_daily_closing_analysis(test_mode=True)`. 수급은 실제 `create_institutional_trend`
- 기대: 수정 전은 모든 단계가 켜진 플래그를 보고(`seen` 전부 true), pykrx 호출 0, 수급 파일 없음, 최종 플래그 true. 수정 뒤는 모든 단계가 false 를 보고, 경고 로그 「남아 있던 사용자 중단 요청을 해제하고」 1회, 수급 44행(두 종목 22거래일) 저장, 최종 플래그 false
- 실제: (공란)

### S-2. 중단 요청이 없으면 17:00 체인 결과가 수정 전과 같다 (하네스, 필수, 회귀 확인)
- 조작: `plain` 모드
- 기대: 두 사본의 JSON 출력이 `cmp` 로 같다. 경고 로그 없음
- 실제: (공란)

### S-3. 중단된 수동 업데이트가 끝나면 다음 개별 실행이 막히지 않는다 (하네스, 필수)
- 조작: `pipeline` 모드. 실제 `start_update`→`stop_update` 뒤 실제 `run_background_update_pipeline(Institutional Trend)`, 이어 관리자 개별 실행처럼 `create_institutional_trend` 를 직접 부른다
- 기대: 두 사본 모두 파이프라인 중 pykrx 호출 0(중단은 여전히 듣는다), 상태 `isRunning` false. 수정 전은 파이프라인 뒤 플래그 true, 개별 실행 `False`·수급 파일 없음. 수정 뒤는 플래그 false, 개별 실행 `True`·44행 저장
- 실제: (공란)

## 정리
- 실제: (공란)
