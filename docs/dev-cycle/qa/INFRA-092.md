# [INFRA-092] `all_institutional_trend_data.csv` 를 잠금 없이 원자적이지 않게 저장한다 — QA 기록

- 대상: `scripts/init_data.py` 의 `_merge_save_csv`(`[INFRA-091]` 의 `_save_daily_prices` 를 이름만 바꿔 공용화)를 부르는 수급 저장 지점 둘(pykrx 경로, `_backfill_institutional_trend_from_toss`)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-24 20:5x(이 문서를 담은 첫 커밋 시각 이전) | 실행 (기록 예정)
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `5e090fe`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 20:41), 호출 경로 추적(17:00 스케줄러 · 관리자 「Refresh VCP」 `kr_market_vcp_background_service` · 수동 갱신 `common_update_pipeline_steps` · 수급 화면 강제 갱신 `kr_market_flow_service` → `create_institutional_trend` → pykrx 경로 저장 또는 Toss 백필 저장)
- QA 엔진(engine): Claude Code. browser_applicability: 하네스 대체. 이 파일을 쓰는 진입점은 실제 수집으로 이어지는 금지 조작이고 화면 변화가 없다. 결과는 파일의 행과 바이트로 판정한다
- 격리: 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고, 사본 `data/` 에 원본 `all_institutional_trend_data.csv`(4,595,345바이트, 126,747행, 마지막 날짜 2026-09-21)·`korean_stocks_list.csv` 를 복사한다. pykrx 는 가짜 모듈, Toss 백필은 호출 여부만 출력하는 가짜, 소켓 연결은 막는다. 원본 `data/`·`.env`·3500·5501 은 쓰지 않는다
- 하네스: 세션 스크래치의 `infra092qa_harness.py`. 자식 프로세스 하나가 `create_institutional_trend(target_date="2026-09-22")` 한 번이다. 가짜 pykrx 는 20260922 에만 지정한 종목을 지연 뒤에 돌려준다

## 시나리오

### S-1. 겹친 두 실행이 저장한 행이 모두 남는다 (하네스, 필수)
- 조작: 실행 A(종목 목록 앞 절반, 수집 지연 4초)를 띄우고 1초 뒤 실행 B(뒤 절반, 지연 0초)를 띄운다. B 가 먼저 저장하고 A 가 나중에 저장한다
- 기대: 수정 뒤 2026-09-22 행이 A·B 합집합이고 09-21 이전 행 126,747 이 그대로다. 수정 전 사본은 A 가 시작 때 읽은 값으로 덮어 B 의 행이 사라진다
- 실제:

### S-2. 저장 중 강제 종료되어도 기존 파일이 온전하다 (하네스, 필수)
- 조작: 전 종목으로 한 번 실행하고, 저장이 시작된 순간(수정 뒤: 임시 파일 `all_institutional_trend_data.csv.*` 생성, 수정 전: 원본 파일 크기·수정 시각 변화)에 `SIGKILL` 한다
- 기대: 수정 뒤 원본이 실행 전과 바이트 단위로 같고, 남은 임시 파일은 `git check-ignore` 에 걸린다. 수정 전 사본은 파일이 잘린다
- 실제:

### S-3. 겹치지 않으면 출력이 수정 전과 바이트 단위로 같다 (하네스, 필수, 회귀 확인)
- 조작: 전 종목으로 수정 전후 사본에서 각각 한 번 실행하고 출력 파일을 `cmp` 로 비교한다
- 기대: 같다(BOM, 정렬, 숫자 표기 포함)
- 실제:

## 정리
- 실제:
