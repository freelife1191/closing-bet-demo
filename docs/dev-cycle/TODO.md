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
- [x] 원인 확정 완료(2026-09-24 08:09~08:11, 사용자 승인 「수집+재분석 모두」, 기록 `docs/dev-cycle/qa/VCP-040.md` 「원인 확정」). 로컬 실측에서는 Gemini 가 성공해 증상이 재현되지 않았다. 그래서 같은 실제 결과에서 gemini 만 비운 입력으로 두 진입점을 다시 돌렸고, 수집은 「분석 실패」·확신도 0, 재분석은 `updated_count 0`·`still_failed 2` 가 나와 두 경로 모두 확정했다. 수정 계획은 그대로 둔다. 원래 절차: 격리 사본(빈 `data/`, 대체 포트, `secrets/` 삭제, 운영과 같은 `VCP_AI_PROVIDERS`·`VCP_GEMINI_MODEL`·Vertex 설정)에서 스케줄러와 같은 진입점으로 VCP 수집(`create_signals_log(run_ai=True)`)을 실제로 한 번 돌린다. 그 결과 사본의 `signals_log.csv` 행(`ai_action`·`ai_confidence`·`ai_reason`)과 같은 날 `kr_ai_analysis_*.json` 의 세 추천 필드를 종목별로 나란히 기록한다. gemini 가 비고 gpt 가 있는데 CSV 가 「분석 실패」면 확정이다. 실측에서 gemini 가 성공해 증상이 안 나오면, 같은 실행 결과 파일을 입력으로 병합 코드만 gemini 를 비운 상태로 다시 돌려 분기를 확인하고 그 사실을 기록한다. 실패 재분석 경로(`execute_vcp_failed_ai_reanalysis`)도 사본에서 실제로 한 번 돌린다. 시그널 상한을 작게 잡아 호출 수를 줄이고, 발송·운영 `data/` 쓰기는 하지 않는다
- 설계 승인: 승인 일자 2026-09-24 | 승인 확인 시각 2026-09-24 08:13
  | 범위: `kr_market_vcp_signal_helpers.py` 에 `_select_vcp_ai_recommendation`(필드 고정 순서 gemini→gpt→perplexity, 기준 `_is_valid_ai_recommendation`), `_extract_vcp_ai_recommendation` 과 `init_data.py` 수집 병합(함수 안 import)이 공유. 전부 실패 시 확신도 결측. `updated_recommendations` 는 Gemini 선택분만(캐시 `gemini_recommendation` 칸을 덮으므로). CSV 열 추가 없음, 기존 `data/` 복구 없음. `VCP_AI_PROVIDERS` 순서 정렬은 제외
  | 실제 대화 근거: 2026-09-24 사용자 「승인, 진행해」 응답, 현재 세션의 설계 제안
  | 범위 추가 승인 2026-09-24 08:22(대화 기록 시각, 계획 검토 critic REVISE 뒤 사용자 선택): (a) 자동 모드(`force_provider` 없음) 재분석만 유효한 기존 CSV 판정을 실패한 재시도로 덮지 않는다, 강제 모드의 `[VCP-039]` 계약은 유지 (b) `_merge_ai_data_into_vcp_signals` 에서 캐시 gemini 칸이 비고 다른 추천이 유효하면 CSV 가 만든 `gemini_recommendation` 을 비워 화면 Gemini 열에 GPT 판정이 뜨지 않게 한다. 화면 흐름이 바뀌므로 QA 에 브라우저 실측이 들어간다
- [x] 설계 승인
- [x] 계획 `docs/superpowers/plans/2026-09-24-vcp-040-ai-recommendation-fallback.md`, critic REVISE 반영: 가드 자동 모드 한정, 화면 라벨 수정 추가, `tests/services` 를 단계 검증에 포함. 기록만: 별도 `_select_vcp_ai_recommendation` 대신 `_extract_vcp_ai_recommendation` 안에 규칙을 둠(결과 동일), 강제 Second 재분석은 CSV 를 쓰지 않아 CSV 의 GPT 판정이 캐시보다 오래될 수 있음, 재분석 버튼마다 Gemini 만 다시 부르며 「여전히 실패」로 셈(`[VCP-041]` 해결 전), `engine/signal_tracker_ai_helpers.py:91` 의 세 번째 선택 규칙은 `[VCP-043]` 로 등록
- [x] 테스트: `tests/app/test_kr_market_vcp_signal_helpers_refactor.py` 9건(폴백·우선순위·전부 실패·재분석 캐시 칸·자동/강제 가드·화면 라벨 둘), `tests/scripts/test_init_data_vcp_scheduler.py` 2건(수집 GPT 판정, 전부 실패 시 확신도 공란, 옛 코드에서 실패 확인), `tests/services/test_vcp_reanalysis_keep_valid_verdict_refactor.py` 1건(서비스 연결, 연결을 지우면 실패 확인)
- [x] 구현: `_extract_vcp_ai_recommendation` 폴백, `_apply_vcp_reanalysis_updates(keep_valid_verdicts=)`·Gemini 유효분만 `updated_recommendations`, 서비스 연결, `init_data.py` 병합 교체, `_drop_csv_verdict_copied_from_another_provider`. `skip_gemini`/`skip_second` 와의 모순 없음(critic·reviewer 확인)
- [x] ponytail 리뷰(별도 에이전트): 「Lean already. Ship.」 지적 없음
- [x] closing-bet-reviewer: CHANGES_REQUIRED(medium 1, low 4). 반영: (1) 강제 Second 재분석 뒤 옛 GPT 판정이 Gemini 라벨로 남는 누출. 판정·사유 대조로 좁혔던 구현을 승인 원안 규칙(캐시 gemini 무효 + 다른 추천 유효 → 비움)으로 되돌림. 캐시 gemini 실패 + CSV 진짜 Gemini 판정인 드문 경우는 Gemini 열이 빈다(라벨 오표시보다 안전). 캐시 파일이 없거나 병합이 건너뛰어지면 CSV 의 GPT 판정이 Gemini 라벨로 나가는 한계는 출처 열 없이는 막을 수 없어 알려진 한계로 둔다 (2) 서비스 연결 테스트 추가 (4) 지연 import 주석 수정. 미반영: (3) `_valid_recommendations` 의 대문자 비교는 분석기가 action 을 대문자로 정규화하므로(`engine/vcp_ai_analyzer_helpers.py:219`, `:274-301`) 가능성 낮음 (5) 건너뛴 행 idx 가 `target_indexes` 에 남는 것은 기존 경쟁 구간이고 `[VCP-035]` 행 이동 검사가 있어 이번 범위에서 두지 않음
- [x] critic 심층 리뷰: ACCEPT-WITH-RESERVATIONS. 앞선 지적 해소·`[VCP-018]`·legacy 보강 상호작용 문제 없음, 미반영 두 건 타당(인용 줄 번호 정정 반영). 유보: 재분석이 캐시에 없는 종목(수집 때 전부 실패해 `_write_ai_analysis_files` 가 넣지 않은 종목)을 GPT 로 채우면 `update_vcp_ai_cache_files` 가 없는 종목을 추가하지 않아 화면 교정이 돌지 않고 GPT 판정이 Gemini 열에 뜬다. 종전에는 「분석 실패」였으므로 이번 변경이 연 경로다. 근본 수정(캐시에 종목 추가)은 날짜 없는 캐시 파일 문제와 얽혀 `[VCP-044]` 로 이월했다. 알려진 한계: CSV 의 GPT 판정이 Gemini 라벨로 나가는 경우는 (1) 이 재분석 경로 (2) 수집 중 캐시 쓰기가 예외로 실패한 경우 (3) 시그널 날짜가 섞여 병합이 건너뛰어진 경우다
- [x] pytest 전체: `venv/bin/python -m pytest -q -p no:cacheprovider` 2708 passed, 2 skipped, exit 0(리뷰 반영 뒤)
- [ ] 격리 사본 QA(`docs/dev-cycle/qa/VCP-040.md` S-1~S-6, 필수 5, 브라우저 포함, LLM 호출 없음)

### [VCP-041] VCP 분석기가 429/503 을 받은 Gemini 모델을 워커 수명 동안 영구 제외한다
- 카테고리: VCP | 티어: T3(위험 경로 `engine/vcp_ai_analyzer.py`) | 근거: 운영자 제보(2026-09-24, 최근 14거래일 `gemini_recommendation` 전부 null, 같은 Vertex 설정의 종가베팅은 09-23 정상)와 로컬 재현(2026-09-24 01:2x, 가짜 클라이언트, 외부 호출 없음).
- 원인(재현으로 확인한 유력 원인): `get_vcp_analyzer()`(`engine/vcp_ai_analyzer.py:1248`)는 프로세스 싱글톤이고, `_analyze_with_gemini`(`:367`)는 429·503·resource exhausted 를 받은 모델을 `self.gemini_blocked_models` 에 넣는다. 이 집합을 비우는 코드가 없다. 체인(`build_gemini_retry_model_chain`, 설정 모델 + 6개)이 한 번의 429 폭주로 모두 들어가면 그 뒤로는 `model_chain` 이 비어 「사용 가능한 모델이 없습니다」를 로그에 남기고 **호출 없이** None 을 돌려준다. 재현: 1일차 전 모델 429 → `blocked=7`, 2일차 정상 클라이언트로 바꿔도 결과 None·호출 0회. 스케줄러를 쥔 gunicorn 워커는 며칠씩 살아 있으므로 재기동 전까지 Gemini 가 죽은 채로 남는다. 종가베팅 경로(`GeminiRetryStrategy`)에는 이런 영구 집합이 없어 같은 모델로 정상이다. 같은 형태의 영구 플래그 `gpt_quota_exhausted`·`perplexity_quota_exhausted` 도 설계 때 함께 본다.
- 부수 차이: VCP 호출은 `generate_content` 에 `config`(출력 토큰)와 타임아웃이 없다(종가베팅은 `GenerateContentConfig(max_output_tokens=16384)` + `wait_for`). 원인은 아니지만 같은 라운드에서 판단한다.
- 운영 확인(운영자): 다음 17:00 실행 뒤 `logs/backend.log` 에서 「사용 가능한 모델이 없습니다」「세션에서 제외합니다」가 찍히는지 본다. 찍히면 이 원인이 확정이다. 수정 배포는 gunicorn 워커를 모두 재기동해야 반영되며, 재기동만으로도 일시 회복된다(장 중 금지).
- 확인 수준(2026-09-24): 결함 자체(영구 제외)는 가짜 클라이언트로 재현해 확정했다. 운영에서 실제로 429·503 이 나서 이 결함이 발동했는지는 로그가 없어 **미확정**이다. 다음 대안을 아직 배제하지 못했다: `gemini-3.8-flash` 응답의 JSON 파싱 실패(코드펜스·thinking 텍스트), `response.text` 가 None, 체인 모델의 리전 404. 이 셋은 제외 집합에 들어가지 않으므로 영구 제외와 달리 매 호출 실패로 나타난다.
- 추가 관찰(2026-09-24 08:10, `[VCP-040]` 실측): 로컬 `.env` 의 같은 모델·Vertex `global` 설정으로 새 프로세스에서 VCP 배치 2종목을 돌렸더니, Gemini 가 두 종목 모두 정상 JSON(BUY 68 / HOLD 65)을 돌려주었고 `gemini_blocked_models` 는 비어 있었다. 이 결과로 모델·리전·파싱 문제일 가능성은 낮아졌지만 배제한 것은 아니다. 로컬과 운영의 설정이 같다는 것은 확인하지 않았다. 새 프로세스에서는 정상인데 오래 산 워커에서만 null 이라는 형태는 영구 제외 가설과 들어맞는다. 기록은 `docs/dev-cycle/qa/VCP-040.md`
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
- 확인 수준(2026-09-24): 01:25 조회에서는 로컬에서 오류가 재현되지 않았다. 원인은 가설 단계다.
- 추가 관찰(2026-09-24, `[VCP-040]` 실측 중, 기록 `docs/dev-cycle/qa/VCP-040.md`): (1) 08:10 에 KRX 계정 값을 환경에 넣은 프로세스에서 `create_signals_log` 의 지수 조회가 운영과 같은 `None of [Index(['TRD_DD', ...])]` 로 두 번 실패했다. 이 조회는 시그널 날짜가 아니라 `datetime.now()`(09-24, 장 시작 전)의 하루치를 묻는다. 그래서 세션 문제가 아니라 「아직 자료가 없는 날짜」를 물어도 같은 문구가 나올 수 있다. 운영 17:00 실행은 당일 자료가 있는 시각이므로 이 설명만으로는 부족하지만, 판정 전에 같은 날짜로 로그인 상태에서 다시 조회해 가린다. (2) 08:11 에 KRX 계정 값을 넣지 않은 프로세스에서는 같은 조회가 운영의 두 번째 문구와 같은 `Expecting value: line 1 column 1 (char 0)` 로 실패했다. 미로그인 상태가 운영의 두 번째 오류와 같은 모양을 낸다는 점은 확인됐다
- [ ] 운영자 확인: 운영 `.env` 에 `KRX_ID`·`KRX_PW` 존재 여부(값은 옮기지 않음), 오류 시각의 「KRX 로그인」「재로그인」 로그와 동시에 로그인한 프로세스 수
- [ ] 원인 확정(실측, 실제 KRX 조회): 같은 KRX 계정으로 프로세스 둘을 띄워 차례로 로그인한 뒤, 먼저 로그인한 쪽에서 `get_index_ohlcv_by_date`·`get_market_ohlcv(market="ALL")`·`get_market_trading_value_by_date` 를 실제로 불러 운영과 같은 두 오류가 나는지 본다(중복 로그인 가설). 이어 로그인 뒤 1시간 넘게 둔 세션으로 같은 조회를 해 만료 가설을, `KRX_ID` 를 비운 프로세스로 미설정 가설을 가린다. 조회만 하고 `data/` 에는 쓰지 않는다. 계정 잠금 위험이 있으므로 로그인 시도는 경우마다 1회로 제한한다. 로컬에서 재현되지 않으면 운영자 확인 결과로만 판정하고 그 한계를 기록한다
- [ ] 원인 확정 뒤 설계 승인(세션 공유·재로그인 트리거, 실패를 DEBUG 가 아닌 WARNING 으로)
- [ ] Market Gate 지수 입력과 `get_last_trading_date` 공휴일 판정 영향 확인과 테스트
- [ ] T3 리뷰와 pytest 전체

## P2 — 대기

### [VCP-044] VCP 재분석 결과가 캐시에 없는 종목을 캐시에 넣지 않고, 날짜 없는 캐시 파일을 날짜 확인 없이 읽고 쓴다
- 카테고리: VCP | 티어: 판정 시 파일 목록으로 정함 | 근거: `[VCP-040]` 심층 리뷰(critic, 2026-09-24). `update_vcp_ai_cache_files` 는 파일이 없으면 건너뛰고(`services/kr_market_vcp_cache_update_service.py:84`) 파일 안에 이미 있는 종목만 고친다(`:98`). 수집 때 모든 AI 가 실패한 종목은 `_write_ai_analysis_files` 가 캐시에 넣지 않으므로(`services/common_update_ai_analysis_service.py:113-116`), 뒤의 재분석이 그 종목을 GPT 로 채워도 캐시에는 남지 않는다. `[VCP-040]` 이후 CSV 에는 GPT 판정이 들어가므로 화면의 Gemini 열에 GPT 판정이 뜨고 GPT 열은 빈다. 또 `load_vcp_ai_cache_map`(`services/kr_market_vcp_reanalysis_service.py:145-150`)과 `update_vcp_ai_cache_files`(`:70-75`)는 날짜 없는 `ai_analysis_results.json`·`kr_ai_analysis.json` 을 날짜 확인 없이 쓰므로, 날짜 파일이 없는 날 재분석하면 전날 파일의 겹치는 종목에 결과가 쓰일 수 있다.
- [ ] 설계 승인(없는 종목 추가, 날짜 파일이 없을 때 새로 만들지, 날짜 없는 파일의 `signal_date` 확인)
- [ ] 재현 테스트와 수정, 격리 사본 QA(재분석 뒤 화면 GPT 열), 리뷰

### [VCP-043] `signal_tracker` 경로의 AI 추천 선택이 실패 dict 도 고르고 VCP 수집과 다른 규칙을 쓴다
- 카테고리: VCP | 티어: 판정 시 파일 목록으로 정함 | 근거: `[VCP-040]` 계획 검토(critic, 2026-09-24). `engine/signal_tracker_ai_helpers.py:91` `_pick_recommendation` 은 gemini → gpt → perplexity 순서로 `isinstance(Mapping)` 만 보고 고르므로 `{"action":"N/A","reason":"분석 실패"}` 도 선택된다. `run.py:56` 메뉴 2 가 이 경로로 `signals_log.csv` 에 쓰며 `ai_provider` 열도 남긴다(`:145`). `[VCP-040]` 이후 수집·재분석은 `_extract_vcp_ai_recommendation`(유효성 검사 포함)을 쓴다.
- [ ] 이 경로가 운영에서 쓰이는지 확인, 설계 승인(같은 선택 함수로 통일할지, `ai_provider` 열을 유지할지)
- [ ] 테스트와 수정, 리뷰

### [VCP-042] 실패 재분석 저장이 `signals_log.csv` 전체를 숫자 티커로 다시 써 앞자리 0 이 사라진다
- 카테고리: VCP | 티어: T3(재분석 저장 경로) | 근거: `[VCP-040]` 원인 확정 실행 2(2026-09-24 08:11, 격리 사본, 기록 `docs/dev-cycle/qa/VCP-040.md`). 수집 직후 원문 `033530` 이던 행이 재분석(갱신 0건) 뒤 원문 `33530` 이 되었다.
- 원인(코드 확인): `write_vcp_signals_csv_atomic`(`services/kr_market_vcp_reanalysis_service.py:320`)은 `load_csv_file_for_persist` 로 전체 파일을 다시 읽어 병합한 뒤 `to_csv` 로 통째로 쓴다. 이 로더가 `ticker` 를 문자열로 고정하지 않으면 정수로 읽혀 앞자리 0 이 빠진 채 저장된다. 갱신 행이 없어도 파일을 다시 쓰는지는 확인이 필요하다.
- 영향(미확인): 읽는 쪽 대부분(`kr_market_vcp_signal_helpers.py`, `init_data._read_signals_log`)이 `zfill(6)` 으로 되돌리므로 화면 영향은 제한적일 수 있다. `zfill` 없이 티커를 비교하는 소비자가 있는지와 운영 파일에 이미 5자리 티커가 있는지는 확인하지 않았다.
- [ ] 소비자 전수 확인(`signals_log.csv` 를 읽는 곳에서 zfill 여부), 운영자에게 운영 파일의 5자리 이하 티커 수 확인 요청
- [ ] 설계 승인(로더 dtype 고정 또는 저장 직전 zfill, 갱신 0건일 때 쓰기 생략 여부)
- [ ] 재현 테스트와 수정, T3 리뷰와 pytest 전체

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)
