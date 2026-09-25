# [INFRA-106] `get_last_trading_date` 의 지수 조회 실패가 DEBUG 로그로만 남고 휴장일을 거래일로 본다 — QA 기록

- 대상: `scripts/init_data.py` 의 `get_last_trading_date`(확인 실패 WARNING, `strict=True` 면 `RuntimeError`), `services/common_update_pipeline_steps.py` 의 `_resolve_expected_trading_date_str`(strict 호출)·`_validate_latest_date_not_stale`(기대 날짜가 없으면 파일·날짜 열 검사 뒤 날짜 비교만 보류)
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 10:38 | 실행 2026-09-25 10:41:43~10:41:49(수정 뒤·수정 전 사본 차례로)
- 검증 기준 커밋: `773f2fc3`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `965c22c5`. 사본은 각 커밋의 `git archive` 다. 사본 `scripts/init_data.py` 의 `INFRA-106` 표시는 수정 뒤 1건·수정 전 0건
- 구성 근거: 설계 승인(대화 10:29), critic 계획 검토 ACCEPT-WITH-RESERVATIONS, 코드 리뷰 APPROVE(지적 1 반영). 호출 경로는 관리자 `POST /api/system/start-update`·`/api/kr/refresh`·`/api/kr/init-data` → `run_background_update` → `run_daily_prices_step`·`run_institutional_trend_step` → `_resolve_expected_trading_date_str` → `get_last_trading_date(strict=True)`, 그리고 수집기 `create_daily_prices`·`create_institutional_trend` 의 비strict 호출
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 화면 진입점(데이터 상태 화면의 업데이트 시작)은 실제 KRX·Toss 수집과 LLM 분석을 일으키는 금지 조작이고(`[INFRA-101]` 과 같은 판단), 결과는 단계 항목 상태(`running`→`done`/`error`)와 로그로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 하네스는 사본 경로(`/scratchpad/`)가 아니면 실행을 거부하고, 소켓 연결을 막고, `pykrx` 를 가짜 모듈로 바꾸며, `create_daily_prices` 는 `True` 만 돌려주는 가짜다. 원본 `data/`·`.env`·3500·5501·운영 주소는 쓰지 않는다
- 하네스: 세션 스크래치의 `infra106qa_harness.py`(사본 루트에서 실행). 실제 `scripts.init_data.get_last_trading_date` 와 실제 `run_daily_prices_step` 을 부른다. 기준일은 추석 연휴 09-24(오늘이 아니므로 16시 당김 없음)
- 필수 여부(required): S-1~S-4 예
- 반복(iteration): 1회. 하네스 출력의 라벨은 문서와 다르다(하네스 `S-1a`·`S-1b` = 문서 S-1, `S-1c` = S-2, `S-2a`·`S-2b` = S-3, `S-3`·`S-4` = S-4)
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(하네스 출력 원문의 요약), scratchpad `qa-infra106-new.txt`·`qa-infra106-old.txt`, 두 실행 모두 exit 0

## 시나리오

### S-1. 개장일 미확인이면 휴장일 기대 날짜로 stale 실패하지 않는다 (하네스, 필수, 회귀)
- 조작: 사본 `daily_prices.csv` 마지막 날짜 09-23, 가짜 pykrx 가 (a) 예외 (b) 빈 프레임, `run_daily_prices_step(target_date="2026-09-24")`
- 기대: 수정 뒤 `statuses` `[running, done]`, WARNING 「개장일 미확인」과 「Daily Prices: trading date unconfirmed, stale check skipped」, 파일 해시 불변. 수정 전은 `[running, error]` 와 「stale data detected (2026-09-23 < 2026-09-24)」, 확인 실패는 DEBUG 로만(결함 재현)
- 실제: 수정 뒤 (a) 예외 (b) 빈 프레임 모두 `[('Daily Prices','running'),('Daily Prices','done')]`, WARNING 「[init_data] 개장일 미확인: pykrx 지수 조회 실패 ('지수명')」·「개장일 미확인: pykrx 지수 데이터 없음 (기준 20260924, 휴장일일 수 있음)」과 「Daily Prices: trading date unconfirmed, stale check skipped」, 파일 해시 `2dd29313d5a0` 그대로, 가짜 pykrx 호출 1회. 수정 전 두 경우 모두 `error` 와 「stale data detected (2026-09-23 < 2026-09-24)」, (a) 확인 실패는 DEBUG 「개장일 확인 실패 (pykrx): '지수명'. 기본 주말 처리만 적용합니다.」로만(결함 재현). 통과

### S-2. 미확인이어도 출력 파일이 없으면 error 다 (하네스, 필수, 리뷰 지적 1)
- 조작: 가짜 pykrx 예외, 사본 `daily_prices.csv` 없음
- 기대: 수정 뒤 `[running, error]` 와 「output file missing」. 수정 전은 기대 날짜가 채워지므로 같은 `error`
- 실제: 수정 뒤·전 모두 `[running, error]`, 「Daily Prices Failed: output file missing (…/data/daily_prices.csv)」. 수정 뒤에도 미확인 WARNING 뒤 파일 검사가 돌았다. 통과

### S-3. 개장일이 확인되면 stale 판정은 종전과 같다 (하네스, 필수, 인접)
- 조작: 가짜 pykrx 가 09-23 한 행 지수를 준다. 파일 마지막 (a) 09-23 (b) 09-22
- 기대: 수정 전후 모두 (a) `[running, done]` (b) `[running, error]` 와 「stale data detected (2026-09-22 < 2026-09-23)」. 「개장일 미확인」 없음
- 실제: 수정 뒤·전 모두 (a) `[running, done]`·DEBUG 「마지막 개장일 확인: 20260923」 (b) `[running, error]`·「stale data detected (2026-09-22 < 2026-09-23)」. 「개장일 미확인」 WARNING 없음. 통과

### S-4. 수집기 경로(비strict)는 주말 처리 날짜로 진행하고 외부에 닿지 않는다 (하네스, 필수)
- 조작: 가짜 pykrx 예외, `get_last_trading_date(reference_date=2026-09-24)`
- 기대: 수정 전후 모두 `20260924`. 수정 뒤 WARNING 「개장일 미확인」·「주말 처리 날짜로 진행합니다: 20260924」. 하네스 종료까지 소켓 차단 유지, 원본 `data/` 수정 시각 불변
- 실제: 수정 뒤·전 모두 `20260924`. 수정 뒤 WARNING 「개장일 미확인: pykrx 지수 조회 실패 ('지수명')」·「주말 처리 날짜로 진행합니다: 20260924」, 수정 전은 DEBUG 한 줄. 두 하네스 끝까지 소켓 차단 유지(`True`), 원본 `data/daily_prices.csv`(1789994444)·`all_institutional_trend_data.csv`(1789994453) 수정 시각 불변. 통과

## 정리
- 실제: 사본 둘(`q106new`·`q106old`) 리터럴 경로로 삭제 뒤 없음 확인, 사본 경로 프로세스 0. 서버·브라우저는 띄우지 않았다. 원본 `data/`·`.env`·3500·5501·운영 주소 사용 없음. 결과: 필수 4/4 통과
