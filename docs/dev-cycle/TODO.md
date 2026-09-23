# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 최종 필수 QA가 통과한 완료 항목만 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.
>
> 2026-09-01 여섯 카테고리 감사(`[INFRA-004]`)로 30개 항목이 들어왔습니다. 각 항목의
> 근거에 적힌 `AUDIT-*` 문서는 `docs/dev-cycle/audits/` 에 있으며, 항목마다 위치를
> 절 번호까지 적어 두었으므로 사이클을 시작할 때 그 절을 먼저 읽습니다.
> 2026-09-07 `[INFRA-036]` 으로 백로그를 현행화했습니다. 해소된 항목 9건을 제거하고 같은 원인의
> 항목 26건을 병합했으며, 목록과 사유는 `archive/2026-09.md` 의 「백로그 정리」 절에 있습니다.

> 2026-09-09 비상용 검토 정정: 긴급성이 낮다는 이유로 제외했던 19건을 복구했습니다(검토 시점 68건). 이후 완료 건은 아카이브에 따라 제거합니다.
> 구조 통합·입력 보강·업그레이드·화면 개선도 유효한 작업입니다. 필요성과 실행 순서를 구분하고,
> 관련 코드와 검증을 공유하는 항목은 묶어서 진행합니다. 기존 체크리스트와 설계 선택지는 보존합니다.
> 판단 정정 기록: [백로그 검토](reviews/backlog-noncommercial-2026-09-09.md).

## P0 — 즉시

> 아래 VCP-040·041, INFRA-088·089 는 설계 전에 **실측 수집으로 원인을 확정**한다. 코드 읽기와 가짜 주입 재현은 가설의 근거일 뿐 확정 근거가 아니다. 실측 결과(명령, 시각, 날짜별 수치, 로그 원문)는 `docs/dev-cycle/qa/<ID>.md` 의 「원인 확정」 절에 남기고, 실측이 가설과 다르면 원인·수정 계획을 먼저 고친다.

### [VCP-040] VCP AI 판정 병합이 Gemini 추천만 보고 다른 프로바이더의 성공 결과를 버린다
- 카테고리: VCP | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: 운영자 제보(2026-09-24)와 코드 확인. 운영 `signals_log.csv` 의 09-18·09-21 VCP 4건이 전부 `ai_action` 공란·「분석 실패」인데, 같은 날 `kr_ai_analysis_20260921.json` 에는 `gpt_recommendation`(BUY, 75)이 정상으로 있다. 최근 14거래일 동안 gemini 0건, gpt 전 건 성공이다(원인은 `[VCP-041]`).
- 원인: 판정을 하나 고르는 곳 두 곳이 모두 `gemini_recommendation` 만 본다. (1) 수집: `scripts/init_data.py:1557-1576` 은 Gemini 가 비면 `N/A`/0/「분석 실패」로 덮는다(주석 「일단 Gemini 기준」). (2) 실패 재분석: `app/routes/kr_market_vcp_signal_helpers.py:94` `_extract_vcp_ai_recommendation` 도 Gemini 만 보고, `_apply_vcp_reanalysis_updates`(`:125`)가 이를 써서 CSV 행을 고친다. 반면 캐시 병합 `_merge_ai_data_into_vcp_signals`(`:378`)는 `VCP_AI_RECOMMENDATION_FIELDS` 세 필드를 모두 `_is_valid_ai_recommendation` 으로 검사하므로 화면 캐시에는 GPT 가 살아 있다. 두 곳이 한 선택 규칙을 쓰지 않아 생긴 불일치다.
- 수정 계획: `kr_market_vcp_signal_helpers.py` 에 「유효한 첫 추천」을 고르는 선택 함수 하나를 두고(기준은 기존 `_is_valid_ai_recommendation`, 순서는 `VCP_AI_RECOMMENDATION_FIELDS` 를 `VCP_AI_PROVIDERS` 순서로 정렬) `_extract_vcp_ai_recommendation` 과 `init_data.py` 병합이 함께 부른다. 모두 실패일 때만 「분석 실패」, 확신도는 0 이 아니라 결측(None)으로 남긴다(`_extract_vcp_ai_recommendation` 의 기존 계약). 어느 프로바이더를 썼는지는 CSV 열을 늘리지 않는 방향을 기본으로 설계 때 정한다. 이미 쌓인 `data/` 행은 되살리지 않는다.
- 확인 수준(2026-09-24): 코드 읽기로만 확인했다. 분기가 단순하고 운영 자료와 들어맞아 확신도는 높지만 `create_signals_log` 를 실제로 돌려 보지는 않았다.
- QA 시나리오: gemini 가 비고 gpt 만 성공한 날의 VCP 화면과 `signals_log` 행에 GPT 판정(BUY·확신도·사유)이 보인다
- [ ] 원인 확정(실측 수집, 실제 외부 조회·LLM 호출, **사용자 승인 필요**): 격리 사본(빈 `data/`, 대체 포트, `secrets/` 삭제, 운영과 같은 `VCP_AI_PROVIDERS`·`VCP_GEMINI_MODEL`·Vertex 설정)에서 스케줄러와 같은 진입점으로 VCP 수집(`create_signals_log(run_ai=True)`)을 실제로 한 번 돌린다. 그 결과 사본의 `signals_log.csv` 행(`ai_action`·`ai_confidence`·`ai_reason`)과 같은 날 `kr_ai_analysis_*.json` 의 세 추천 필드를 종목별로 나란히 기록한다. gemini 가 비고 gpt 가 있는데 CSV 가 「분석 실패」면 확정이다. 실측에서 gemini 가 성공해 증상이 안 나오면, 같은 실행 결과 파일을 입력으로 병합 코드만 gemini 를 비운 상태로 다시 돌려 분기를 확인하고 그 사실을 기록한다. 실패 재분석 경로(`execute_vcp_failed_ai_reanalysis`)도 사본에서 실제로 한 번 돌린다. 시그널 상한을 작게 잡아 호출 수를 줄이고, 발송·운영 `data/` 쓰기는 하지 않는다
- [ ] 설계 승인(선택 함수 위치, 출처 기록 여부, `init_data.py` 가 `app/routes` 헬퍼를 가져오는 방향이 맞는지)
- [ ] `tests/**/test_*_refactor.py` 관례로 세 경우 검사: gemini null + gpt 성공 → gpt / 전부 null → 「분석 실패」·확신도 결측 / gemini 성공 → gemini 우선. 재분석 경로 `_apply_vcp_reanalysis_updates` 에도 같은 경우 하나
- [ ] 선택 함수 구현과 두 호출자 교체, 재분석 서비스의 `skip_gemini`/`skip_second` 판정(`services/kr_market_vcp_reanalysis_service.py:631-679`)과 모순이 없는지 확인
- [ ] T3 리뷰(ponytail → closing-bet-reviewer → critic)와 pytest 전체
- [ ] 격리 사본 QA: 가짜 AI 결과로 병합만 돌려 CSV 행 확인(실제 LLM 호출 없음)

### [VCP-041] VCP 분석기가 429/503 을 받은 Gemini 모델을 워커 수명 동안 영구 제외한다
- 카테고리: VCP | 티어: T3(위험 경로 `engine/vcp_ai_analyzer.py`) | 근거: 운영자 제보(2026-09-24, 최근 14거래일 `gemini_recommendation` 전부 null, 같은 Vertex 설정의 종가베팅은 09-23 정상)와 로컬 재현(2026-09-24 01:2x, 가짜 클라이언트, 외부 호출 없음).
- 원인(재현으로 확인한 유력 원인): `get_vcp_analyzer()`(`engine/vcp_ai_analyzer.py:1248`)는 프로세스 싱글톤이고, `_analyze_with_gemini`(`:367`)는 429·503·resource exhausted 를 받은 모델을 `self.gemini_blocked_models` 에 넣는다. 이 집합을 비우는 코드가 없다. 체인(`build_gemini_retry_model_chain`, 설정 모델 + 6개)이 한 번의 429 폭주로 모두 들어가면 그 뒤로는 `model_chain` 이 비어 「사용 가능한 모델이 없습니다」를 로그에 남기고 **호출 없이** None 을 돌려준다. 재현: 1일차 전 모델 429 → `blocked=7`, 2일차 정상 클라이언트로 바꿔도 결과 None·호출 0회. 스케줄러를 쥔 gunicorn 워커는 며칠씩 살아 있으므로 재기동 전까지 Gemini 가 죽은 채로 남는다. 종가베팅 경로(`GeminiRetryStrategy`)에는 이런 영구 집합이 없어 같은 모델로 정상이다. 같은 형태의 영구 플래그 `gpt_quota_exhausted`·`perplexity_quota_exhausted` 도 설계 때 함께 본다.
- 부수 차이: VCP 호출은 `generate_content` 에 `config`(출력 토큰)와 타임아웃이 없다(종가베팅은 `GenerateContentConfig(max_output_tokens=16384)` + `wait_for`). 원인은 아니지만 같은 라운드에서 판단한다.
- 운영 확인(운영자): 다음 17:00 실행 뒤 `logs/backend.log` 에서 「사용 가능한 모델이 없습니다」「세션에서 제외합니다」가 찍히는지 본다. 찍히면 이 원인이 확정이다. 수정 배포는 gunicorn 워커를 모두 재기동해야 반영되며, 재기동만으로도 일시 회복된다(장 중 금지).
- 확인 수준(2026-09-24): 결함 자체(영구 제외)는 가짜 클라이언트로 재현해 확정했다. 운영에서 실제로 429·503 이 나서 이 결함이 발동했는지는 로그가 없어 **미확정**이다. 다음 대안을 아직 배제하지 못했다: `gemini-3.8-flash` 응답의 JSON 파싱 실패(코드펜스·thinking 텍스트), `response.text` 가 None, 체인 모델의 리전 404. 이 셋은 제외 집합에 들어가지 않으므로 영구 제외와 달리 매 호출 실패로 나타난다.
- [ ] 원인 확정 1(운영자, 비용 없음): 운영 `backend.log` 에서 위 두 문구와 「JSON 파싱 실패」「분석 실패 (Final)」 중 어느 것이 찍히는지 확인해 기록한다
- [ ] 원인 확정 2(실제 LLM 호출, **사용자 승인 필요**): 격리 사본에서 운영과 같은 `VCP_GEMINI_MODEL`·Vertex 설정으로 새 `VCPMultiAIAnalyzer` 를 만들어 종목 하나에 `_analyze_with_gemini` 를 한 번만 부른다. `generate_content` 원문(`response.text`, `candidates[0].finish_reason`), 예외와 상태 코드, `_parse_json_response` 결과를 기록한다. 체인 전환을 막도록 체인을 설정 모델 하나로 제한하고, 사본 `data/` 에만 쓴다. 정상 응답이면 영구 제외가 원인이라는 판단이 강해지고, 파싱·None 이면 원인을 그쪽으로 바꾼다
- [ ] 설계 승인(제외 범위를 배치 한 번으로 한정할지, 만료 시각을 둘지. 기본안은 `analyze_batch` 시작 시 초기화 + 모델 하나 실패로 전 종목이 막히지 않게)
- [ ] 재현 테스트를 `tests/engine/test_*_refactor.py` 로 추가(1차 배치 전 모델 429 → 2차 배치에서 다시 호출되는지)
- [ ] 수정 구현, 필요 시 VCP 호출에 출력 토큰·타임아웃 정렬
- [ ] T3 리뷰와 pytest 전체, 마감 기록에 「워커 전부 재기동 필요」 명시

## P1 — 이번 주기

### [INFRA-088] 일별 가격 수집이 yfinance 폴백의 부분 결과를 성공으로 저장하고 그 날짜를 다시 채우지 않는다
- 카테고리: 인프라 | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: 운영자 제보(2026-09-24, 운영 `daily_prices.csv` 날짜별 종목 수 09-16 967 / 09-17 1,375 / 09-08~09-21 약 1,810~1,920 / 09-22·23 약 2,870)와 로컬 확인.
- 원인: 두 출처의 유니버스가 다르다. pykrx `get_market_ohlcv(date, market="ALL")` 는 전 종목(09-16 2,871·09-22 2,869, 로컬에서 읽기 전용 조회로 확인)을 주고, 폴백 `fetch_prices_yfinance`(`scripts/init_data.py:691`)는 `korean_stocks_list.csv`(시총 상위 KOSPI·KOSDAQ 각 1,000, 로컬 1,997개)만 받는다. 그래서 09-22 의 +1,000 은 유니버스 변경이 아니라 **pykrx 가 다시 성공한 결과**다(로컬 파일도 09-10 에 같은 전환이 있다). yfinance 는 청크 일부만 받아도 행이 하나라도 있으면 개별 재시도 없이 넘어가고(`chunk_rows == 0` 일 때만 재시도), 결과가 부분이어도 `True` 를 돌려준다. 저장된 과거 날짜는 `create_daily_prices` 가 「데이터 존재 (Skip)」으로 건너뛰므로 구멍이 영구히 남는다. 완전성 검사(`last_date_count >= total*0.9`)는 한 갈래에서만, 마지막 날짜에만 쓰인다.
- 수정 계획: 날짜별 수집 종목 수를 기대치와 비교해 부족하면 성공으로 기록하지 않고 경고로 남기며, 부분 날짜는 다음 실행에서 다시 채우게 한다. 출처별 유니버스를 하나로 맞출지(pykrx 결과를 목록으로 제한하거나 목록을 넓히기)는 스크리너 입력에 영향이 있어 설계 때 정한다. 이미 저장된 운영 구멍(09-16 등)을 재수집할지는 설계 승인 때 결정한다(pykrx 로 복구 가능함은 로컬에서 확인).
- 확인 수준(2026-09-24): pykrx 지수·전종목 시세(09-16 2,871, 09-22 2,869)만 실제로 조회했다. `create_daily_prices` 와 yfinance 폴백은 실행하지 않았으므로 967·1,375 가 yfinance 부분 수집에서 나왔다는 것은 코드에서 추론한 것이다.
- [ ] 원인 확정(실측 수집, 실제 pykrx·yfinance 조회, LLM 없음): 격리 사본에서 (1) 정상 경로: 빈 `data/` 에 운영과 같은 방식으로 만든 `korean_stocks_list.csv` 만 두고 `create_daily_prices(target_date=...)` 를 실제로 돌려 날짜별 종목 수를 센다. (2) 폴백 경로: `fetch_prices_yfinance` 를 운영과 같은 인자(청크 100, 요청 8초, 전체 300초)로 실제 yfinance 에 대해 직접 호출해 날짜별 종목 수·반환값·청크별 실패 수·최대 실행시간 초과 여부를 기록한다. 같은 조회를 두세 번 반복해 종목 수가 흔들리는지 본다. (3) (2) 결과로 부분 날짜가 든 파일에 대해 `create_daily_prices` 를 다시 실제로 돌려 그 날짜가 「Skip」되는지 본다. 운영 수치(약 1,900·967·1,375)가 재현되면 확정, 아니면 가설을 고친다. 운영 `data/` 에는 쓰지 않는다
- [ ] 설계 승인(유니버스 기준, 부족 판정 기준, 과거 구멍 재수집 여부)
- [ ] 부분 수집 판정과 재수집 대상 선정 테스트(가짜 pykrx·yfinance)
- [ ] 구현, 결측과 실제 0 거래 구분 확인
- [ ] T3 리뷰와 pytest 전체, 격리 사본에서 가짜 출처로 CLI QA

### [INFRA-089] 운영에서 KRX(pykrx) 조회가 간헐적으로 빈 응답을 받아 가격·지수 수집이 폴백으로 떨어진다
- 카테고리: 인프라 | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: 운영 09-23 17:00 `backend.log` 의 `get_index_ohlcv_by_date: None of [Index(['TRD_DD', 'OPNPRC_IDX', ...])]`, `get_market_trading_value_and_volume_on_ticker_by_date: Expecting value: line 1 column 1`. 같은 코드가 로컬에서는 2026-09-24 01:25 로그인 후 지수·전종목 시세 모두 정상이었다. 따라서 KRX 응답 형식 변경보다 운영 세션 문제일 가능성이 높다.
- 가설(미확정, 운영 로그 필요): pykrx 1.2.9+cookie.2 는 로그인 세션 만료를 클라이언트 쪽 1시간 타이머로만 판단한다(`pykrx/website/comm/auth.py`). 같은 KRX 계정으로 gunicorn 워커 둘과 스케줄러·수동 스크립트가 각각 로그인하면 서버 쪽에서 앞 세션이 끊길 수 있고(vendor README 가 다루는 CD011 계열), 끊긴 세션의 요청은 빈 응답이 되어 위 두 오류로 나타난다. 운영에 `KRX_ID`·`KRX_PW` 가 없는 경우도 같은 증상이므로 먼저 배제한다.
- 영향: `create_daily_prices` 는 이 오류를 `_should_abort_daily_pykrx_bulk_fetch` 로 잡아 yfinance 로 넘어가며 이것이 `[INFRA-088]` 의 부분 저장을 부른다. `get_last_trading_date`(`scripts/init_data.py:119`)는 실패 시 DEBUG 로그만 남기고 주말만 거르므로 공휴일을 거래일로 볼 수 있다. VCP AI 파일의 `market_indices`(`:1508-1525`)는 빈 dict 로 저장되지만 AI 프롬프트 입력은 아니다(분석 뒤에 조립). Market Gate 는 `DataSourceManager` 폴백 체인을 거치므로 영향 여부를 이 항목에서 확인한다.
- 확인 수준(2026-09-24): 로컬에서는 오류가 재현되지 않았다. 원인은 가설 단계다.
- [ ] 운영자 확인: 운영 `.env` 에 `KRX_ID`·`KRX_PW` 존재 여부(값은 옮기지 않음), 오류 시각의 「KRX 로그인」「재로그인」 로그와 동시에 로그인한 프로세스 수
- [ ] 원인 확정(실측, 실제 KRX 조회): 같은 KRX 계정으로 프로세스 둘을 띄워 차례로 로그인한 뒤, 먼저 로그인한 쪽에서 `get_index_ohlcv_by_date`·`get_market_ohlcv(market="ALL")`·`get_market_trading_value_by_date` 를 실제로 불러 운영과 같은 두 오류가 나는지 본다(중복 로그인 가설). 이어 로그인 뒤 1시간 넘게 둔 세션으로 같은 조회를 해 만료 가설을, `KRX_ID` 를 비운 프로세스로 미설정 가설을 가린다. 조회만 하고 `data/` 에는 쓰지 않는다. 계정 잠금 위험이 있으므로 로그인 시도는 경우마다 1회로 제한한다. 로컬에서 재현되지 않으면 운영자 확인 결과로만 판정하고 그 한계를 기록한다
- [ ] 원인 확정 뒤 설계 승인(세션 공유·재로그인 트리거, 실패를 DEBUG 가 아닌 WARNING 으로)
- [ ] Market Gate 지수 입력과 `get_last_trading_date` 공휴일 판정 영향 확인과 테스트
- [ ] T3 리뷰와 pytest 전체

## P2 — 대기

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)
