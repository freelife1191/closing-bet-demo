# [INFRA-108] Market Gate 의 쓰이지 않는 수급 점수 경로 삭제 — QA 기록

- 대상: `engine/market_gate.py`(`KisCollector` 생성·`_load_supply_data`·`_score_supply` 삭제), `engine/market_gate_fetchers_local.py`(`load_supply_data` 삭제), `engine/market_gate_logic*.py`(재수출·`score_supply` 삭제), `engine/config.py`·`config.py`(`foreign_net_buy_threshold` 삭제)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25(설계 승인·구현·대상 테스트 뒤, 실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 11:43:20~11:43:27
- 검증 기준 커밋: `9e319725`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `2fbcb59a`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화, 확인 시각 11:34). 사용자 진입 흐름은 Market Gate 카드이며, 화면은 `analyze`·`save_analysis` 가 저장한 JSON 을 GET 으로 읽는다. 바뀐 것은 판정에 쓰이지 않는 함수의 삭제뿐이고 `analyze_market_state` 는 그대로다
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면이 읽는 값은 저장 JSON 과 같으므로, 같은 입력에서 수정 전후의 `analyze` 결과와 저장 JSON 이 같은지로 판정한다. 실제 갱신 요청(`POST /api/kr/market-gate/update`)은 외부 조회를 부르는 금지 조작이라 보내지 않는다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고, 하네스가 사본 `data/` 에 합성 가격(069500, 100 영업일)과 수급 파일(마지막 날짜 임의 종목 한 행, 외국인 순매수 9,000억)을 만든다. 벤치마크·환율·글로벌·섹터 조회는 고정값으로 바꾸고 소켓 연결을 막는다. 서버와 포트는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra108qa_harness.py`(사본 경로가 scratchpad 가 아니면 거부)
- 필수 여부(required): S-1~S-3 예
- 반복(iteration): 1회
- 결과: 통과 (필수 3/3)
- 증거: 아래 「실제」 줄(하네스 `RESULT` 줄의 비교 요약), scratchpad `qa-infra108-old.txt`·`qa-infra108-new.txt`, 두 실행 모두 exit 0

## 시나리오

### S-1. 같은 입력에서 수정 전후의 분석 결과가 같다 (하네스, 필수, 회귀)
- 조작: 두 사본에서 하네스를 실행해 마지막 날짜와 30 영업일 전 날짜의 `analyze` 결과(시각 필드 제외)를 JSON 으로 뽑아 비교한다
- 기대: 두 날짜 모두 `total_score`·`status`·`details` 를 포함한 결과 전체가 같다. 수급 파일의 9,000억 순매수가 어느 쪽 점수에도 들어가지 않는다
- 실제: 2026-09-17 결과 전체 동일(`total_score` 50, 「중립 (Neutral)」, `tech_score` 50), 2026-08-07 결과 전체 동일(75, 「강세장 (Bullish)」, `tech_score` 75). 두 쪽 모두 `total_score` 가 `tech_score` 와 같아 9,000억 수급 행이 반영되지 않았다. 통과

### S-2. 저장 JSON 의 키와 점수가 수정 전후로 같다 (하네스, 필수)
- 조작: 두 사본에서 `save_analysis` 로 사본 `data/` 에 저장한 파일을 읽는다
- 기대: 키 목록과 `total_score` 가 같다
- 실제: 키 목록 동일(`True`), `total_score` 50 대 50. 통과

### S-3. 수정 뒤 `MarketGate` 에 KIS 수집기와 수급 메서드가 없고, 네트워크 없이 끝난다 (하네스, 필수)
- 조작: 하네스 출력의 `has_kis_attr`·`has_supply_methods` 와 종료 코드를 읽는다
- 기대: 수정 전 `has_kis_attr=true`·`has_supply_methods=true`, 수정 뒤 둘 다 `false`. 두 실행 모두 소켓 차단 예외 없이 exit 0. 원본 `data/` 수정 시각 불변
- 실제: 수정 전 `has_kis_attr=True`·`has_supply_methods=True`, 수정 뒤 둘 다 `False`. 두 실행 exit 0, stderr 에 소켓 차단 예외 0건, 원본 `data/` 두 파일 수정 시각 실행 전후 동일(`diff` 무출력). 하네스 첫 시험 실행에서 가짜 벤치마크 열 이름(`close`)이 틀려 RS 계산 경고가 났고, `bench_close` 로 고친 뒤 본 실행에서는 경고가 없었다. 통과

## 정리
- 실제: 두 사본(`q108old`·`q108new`)을 리터럴 경로로 삭제, 하네스 프로세스 0. 서버·포트·브라우저는 쓰지 않았다. 원본 `data/`·`.env` 사용 없음. 결과: 필수 3/3 통과
