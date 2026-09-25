# [INFRA-113] 수동 갱신 stale 검증이 날짜 열이 모두 결측인 파일을 최신으로 본다 — QA 기록

- 대상: `services/common_update_pipeline_steps.py` 의 `_validate_latest_date_not_stale`(날짜 앞 10자리를 `%Y-%m-%d` 로 엄격 변환, 결측·형식 오류 제외, 유효 날짜가 없으면 error)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 10:49~10:53 사이(설계 승인 뒤·실행 전, 분 단위 시각은 기록하지 않음) | 실행 2026-09-25 10:53:05~10:53:07(수정 뒤·수정 전 사본 차례로)
- 검증 기준 커밋: `f4fd0e58`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `3307fd06`. 사본은 각 커밋의 `git archive` 다. 사본 `services/common_update_pipeline_steps.py` 의 `INFRA-113` 표시는 수정 뒤 1건·수정 전 0건
- 구성 근거: 설계 승인(대화 10:49), `/ponytail-review` 지적 없음. 호출 경로는 관리자 `POST /api/system/start-update`·`/api/kr/refresh`·`/api/kr/init-data` → `run_background_update` → `run_daily_prices_step`·`run_institutional_trend_step` → `_validate_latest_date_not_stale`
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 상태 화면의 업데이트 시작)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이다(`[INFRA-106]` 과 같은 판단). 결과는 단계 항목 상태(`running`→`done`/`error`)와 로그로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부하고, 소켓 연결을 막고, `pykrx` 를 09-23 을 개장일로 확인해 주는 가짜 모듈로 바꾸며, `create_daily_prices`·`create_institutional_trend` 는 `True` 만 돌려주는 가짜다. 원본 `data/`·`.env`·3500·5501·운영 주소는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra113qa_harness.py`(사본 루트에서 실행). 실제 `scripts.init_data.get_last_trading_date` 와 실제 `run_daily_prices_step`·`run_institutional_trend_step` 을 부른다. 기준일 09-24(휴장일, 기대 날짜는 지수로 확인한 09-23)
- 필수 여부(required): S-1~S-4 예
- 반복(iteration): 1회
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(하네스 출력 원문의 요약), scratchpad `qa-infra113-new.txt`·`qa-infra113-old.txt`, 두 실행 모두 exit 0

## 시나리오

### S-1. 날짜 열이 전부 결측이면 error 다 (하네스, 필수, 회귀)
- 조작: 사본 `daily_prices.csv` 의 `date` 두 행 모두 빈 값, `run_daily_prices_step(target_date="2026-09-24")`
- 기대: 수정 뒤 `[running, error]` 와 「no valid date in …/daily_prices.csv」. 수정 전은 `[running, done]`(결함 재현)
- 실제: 수정 뒤 반환 `False`, `[('Daily Prices','running'),('Daily Prices','error')]`, ERROR 「Daily Prices Failed: no valid date in …/q113new/data/daily_prices.csv」. 수정 전 반환 `True`·`done`, 오류 없음(결함 재현). 두 사본 모두 DEBUG 「마지막 개장일 확인: 20260923」. 통과

### S-2. 결측·형식 오류가 섞여도 유효 날짜로 stale 을 판정한다 (하네스, 필수, 회귀)
- 조작: `date` 가 `2026-09-22`·빈 값·`abc`
- 기대: 수정 뒤 `[running, error]` 와 「stale data detected (2026-09-22 < 2026-09-23)」. 수정 전은 `done`(결함 재현)
- 실제: 수정 뒤 `error` 와 「Daily Prices Failed: stale data detected (2026-09-22 < 2026-09-23)」. 수정 전 `done`(결함 재현). 통과

### S-3. 유효 날짜가 최신이면 결측이 섞여도 통과한다 (하네스, 필수, 인접)
- 조작: `date` 가 `2026-09-23`·빈 값
- 기대: 수정 전후 모두 `[running, done]`
- 실제: 수정 뒤·전 모두 반환 `True`, `[running, done]`, WARNING·ERROR 없음. 통과

### S-4. 수급 파일도 같은 판정을 받는다 (하네스, 필수, 인접)
- 조작: 사본 `all_institutional_trend_data.csv` 의 `date` 전부 빈 값, `run_institutional_trend_step`
- 기대: 수정 뒤 반환 `False`·`[running, error]`(VCP 게이트 닫힘). 수정 전은 `True`·`done`. 원본 `data/` 수정 시각 불변, 소켓 차단 유지
- 실제: 수정 뒤 반환 `False`, `[('Institutional Trend','running'),('Institutional Trend','error')]`, 「Institutional Trend Failed: no valid date in …/all_institutional_trend_data.csv」. 수정 전 `True`·`done`(결함 재현). 두 하네스 끝까지 소켓 차단 유지(`True`), 원본 `data/daily_prices.csv`(1789994444)·`all_institutional_trend_data.csv`(1789994453) 수정 시각 실행 전후 불변. 통과

## 정리
- 실제: 사본 둘(`q113new`·`q113old`) 리터럴 경로로 삭제 뒤 없음 확인, 사본 경로 프로세스 0. 서버·브라우저는 띄우지 않았다. 원본 `data/`·`.env`·3500·5501·운영 주소 사용 없음. 결과: 필수 4/4 통과
