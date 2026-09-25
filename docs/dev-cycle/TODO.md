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

> 아래 VCP-041, INFRA-088·089 는 설계 전에 **실측 수집으로 원인을 확정**한다. 코드 읽기와 가짜 주입 재현은 가설의 근거일 뿐 확정 근거가 아니다. 실측 결과(명령, 시각, 날짜별 수치, 로그 원문)는 `docs/dev-cycle/qa/<ID>.md` 의 「원인 확정」 절에 남기고, 실측이 가설과 다르면 원인·수정 계획을 먼저 고친다.

### [VCP-041] VCP 분석기가 429/503 을 받은 Gemini 모델을 워커 수명 동안 영구 제외한다 (운영자 단계)
- 카테고리: VCP | 티어: T1(남은 단계는 운영자 확인과 배포) | 근거: 운영자 제보(2026-09-24, 최근 14거래일 `gemini_recommendation` 전부 null). 코드 수정분은 커밋 `7470475`(세션 차단 플래그 10분 만료)로 끝났고 기록은 `archive/daily/2026-09-24.md`·`qa/VCP-041.md` 에 있다
- 남은 범위: 원인 확정 실호출(08:49)에서 새 프로세스의 Gemini 는 정상이었으므로, 운영 null 은 영구 제외 결함이 유력하다. 운영에서 실제로 발동했는지는 로그로만 확정된다. 배포는 gunicorn 워커를 모두 재기동해야 반영된다(장 중 금지). 재기동만으로도 지금의 차단은 풀린다
- [x] 원인 확정 1(운영자, 비용 없음): 운영 `logs/backend.log` 에서 「사용 가능한 모델이 없습니다」「세션에서 제외합니다」「JSON 파싱 실패」「분석 실패 (Final)」 중 어느 것이 찍혔는지 확인해 기록한다. 앞의 두 문구가 아니면 원인을 다시 본다 → 2026-09-25 확인: 09-24 17:01:25 「gemini-3.8-flash 모델을 429/503 계열 오류로 세션에서 제외합니다」 한 줄. 원인 확정(`qa/VCP-041.md` 운영자 확인)
- [ ] 배포와 워커 전부 재기동(운영자, 장 마감 뒤), 첫 17:00 실행 뒤 `kr_ai_analysis_<날짜>.json` 의 `gemini_recommendation` 이 채워졌는지와 「VCP 분석기 세션 차단 해제」 로그 여부 확인

### [INFRA-090] 일별 가격 수집이 평일 휴장일을 전 종목 0원 행으로 저장한다 (운영자 단계)
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 배포) | 근거: `[INFRA-088]`·`[INFRA-089]` 실측 중 발견(2026-09-24). 코드 수정분은 커밋 `d4adaa8`(전 종목 종가 0 인 날짜 건너뜀, 저장된 0원 날짜는 다음 저장 때 정리, 휴장일만 있는 구간은 폴백 생략)로 끝났고 기록은 `archive/daily/2026-09-24.md`·`qa/INFRA-090.md` 에 있다
- 남은 범위: 운영 반영은 gunicorn 재기동이 필요하다(장 중 금지). 추석 연휴 뒤 첫 거래일 17:00 실행 전에 반영해야 연휴 날짜가 0원으로 저장되지 않는다. 이미 저장된 0원 행은 다음 저장 때 빠지지만, 그 전까지 VCP·종가베팅 화면은 마지막 날짜의 0원을 현재가로 읽어 수익률 -100% 로 보인다(QA S-3)
- [x] 운영자 확인: 운영 `daily_prices.csv` 에 종가 0 비율이 높은 날짜가 있는지(100% 가 아닌 날짜가 있는지도), 특히 09-24 이후 연휴 날짜 → 2026-09-25 확인: 12-25·12-31·01-01·02-16~18 여섯 날짜가 비율 1.0, 부분 0 날짜 없음, 연휴 날짜는 아직 없음(`qa/INFRA-090.md`)
- [ ] 배포와 재기동(운영자, 장 마감 뒤), 연휴 뒤 첫 17:00 실행 뒤 로그 「전 종목 종가 0, 저장 생략」과 파일에 연휴 날짜가 없는지 확인

## P1 — 이번 주기

### [INFRA-088] 일별 가격 수집이 yfinance 폴백의 부분 결과를 성공으로 저장하고 그 날짜를 다시 채우지 않는다
- 카테고리: 인프라 | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: 운영자 제보(2026-09-24, 운영 `daily_prices.csv` 날짜별 종목 수 09-16 967 / 09-17 1,375 / 09-08~09-21 약 1,810~1,920 / 09-22·23 약 2,870)와 로컬 확인.
- 원인: 두 출처의 유니버스가 다르다. pykrx `get_market_ohlcv(date, market="ALL")` 는 전 종목(09-16 2,871·09-22 2,869, 로컬에서 읽기 전용 조회로 확인)을 주고, 폴백 `fetch_prices_yfinance`(`scripts/init_data.py:691`)는 `korean_stocks_list.csv`(시총 상위 KOSPI·KOSDAQ 각 1,000, 로컬 1,997개)만 받는다. 그래서 09-22 의 +1,000 은 유니버스 변경이 아니라 **pykrx 가 다시 성공한 결과**다(로컬 파일도 09-10 에 같은 전환이 있다). yfinance 는 청크 일부만 받아도 행이 하나라도 있으면 개별 재시도 없이 넘어가고(`chunk_rows == 0` 일 때만 재시도), 결과가 부분이어도 `True` 를 돌려준다. 저장된 과거 날짜는 `create_daily_prices` 가 「데이터 존재 (Skip)」으로 건너뛰므로 구멍이 영구히 남는다. 완전성 검사(`last_date_count >= total*0.9`)는 한 갈래에서만, 마지막 날짜에만 쓰인다.
- 수정 계획: 날짜별 수집 종목 수를 기대치와 비교해 부족하면 성공으로 기록하지 않고 경고로 남기며, 부분 날짜는 다음 실행에서 다시 채우게 한다. 출처별 유니버스를 하나로 맞출지(pykrx 결과를 목록으로 제한하거나 목록을 넓히기)는 스크리너 입력에 영향이 있어 설계 때 정한다. 이미 저장된 운영 구멍(09-16 등)을 재수집할지는 설계 승인 때 결정한다(pykrx 로 복구 가능함은 로컬에서 확인).
- 확인 수준(2026-09-24): pykrx 지수·전종목 시세(09-16 2,871, 09-22 2,869)만 실제로 조회했다. `create_daily_prices` 와 yfinance 폴백은 실행하지 않았으므로 967·1,375 가 yfinance 부분 수집에서 나왔다는 것은 코드에서 추론한 것이다.
- [ ] 원인 확정(실측 수집, 실제 pykrx·yfinance 조회, LLM 없음): 격리 사본에서 (1) 정상 경로: 빈 `data/` 에 운영과 같은 방식으로 만든 `korean_stocks_list.csv` 만 두고 `create_daily_prices(target_date=...)` 를 실제로 돌려 날짜별 종목 수를 센다. (2) 폴백 경로: `fetch_prices_yfinance` 를 운영과 같은 인자(청크 100, 요청 8초, 전체 300초)로 실제 yfinance 에 대해 직접 호출해 날짜별 종목 수·반환값·청크별 실패 수·최대 실행시간 초과 여부를 기록한다. 같은 조회를 두세 번 반복해 종목 수가 흔들리는지 본다. (3) (2) 결과로 부분 날짜가 든 파일에 대해 `create_daily_prices` 를 다시 실제로 돌려 그 날짜가 「Skip」되는지 본다. 운영 수치(약 1,900·967·1,375)가 재현되면 확정, 아니면 가설을 고친다. 운영 `data/` 에는 쓰지 않는다
  - 1차 결과(2026-09-24 09:16~09:41, 기록 `qa/INFRA-088.md`, KRX 로그인 없이 실제 yfinance): 구멍이 다음 실행에서 채워지지 않음과 「종목 수 부족」 분기(`:936-946`)가 도달 불가임은 확정. 과거 날짜 조회는 날짜마다 1,974~1,977/1,997 로 안정적이라 967·1,375 는 재현되지 않았고, 청크 부분 수신 경로도 발동하지 않았다. 운영 인자로는 배치 한 번(22~25초)이 20초 호출 제한을 넘어 300초 초과·저장 없음(`False`)으로 끝났다. 가설을 「17:00 실행이 당일 봉이 덜 올라온 yfinance 결과를 저장한다」로 고쳤다
  - 3차 결과(09-24 09:46~09:48, 휴장일): 하루 구간 조회 09-23 은 1,974종목, 09-24(휴장일) 조회는 09-24 행 없이 **09-23 날짜 행 1,921종목**을 돌려줬다. 봉이 없는 구간을 물으면 yfinance 가 구간 밖 직전 봉을 일부 종목만 주고, 폴백은 그것을 `keep="last"` 로 병합해 `True` 를 돌려준다. 967·1,375 는 여전히 미재현
- [ ] 원인 확정 2(실측): 추석 연휴 뒤 첫 거래일 16:00~17:30 사이 yfinance 로 당일 하루치를 시각별로 조회해 봉이 있는 종목 수를 센다(조회만, 사본에만 씀). 운영자 확인: 운영 `backend.log` 09-16·09-17 17:00 무렵 「yfinance 진행」「백업 수집 완료」 줄과 운영 `korean_stocks_list.csv` 종목 수
  - 2026-09-25 사용자 전달: 운영 목록 1,997줄로 로컬과 같음, 운영 날짜별 종목 수 확인(`qa/INFRA-088.md`). yfinance 로그 줄은 현재 운영 로그에 없음(09-16·17 실행분이 로그에 남아 있지 않음)
- [ ] 설계 승인(유니버스 기준, 부족 판정 기준, 과거 구멍 재수집 여부)
- [ ] 부분 수집 판정과 재수집 대상 선정 테스트(가짜 pykrx·yfinance)
- [ ] 구현, 결측과 실제 0 거래 구분 확인
- [ ] T3 리뷰와 pytest 전체, 격리 사본에서 가짜 출처로 CLI QA

### [VCP-045] Z.ai 폴백의 `zai_disabled_reason` 도 워커 수명 동안 풀리지 않는다 (운영자 단계)
- 카테고리: VCP | 티어: T1(남은 단계는 운영자 확인과 배포) | 근거: `[VCP-041]` 코드 리뷰(2026-09-24). 코드 수정분은 커밋 `22b197a`(`_expire_session_blocks` 가 `zai_disabled_reason` 도 10분 뒤 비움)로 끝났고 기록은 `archive/daily/2026-09-24.md`·`qa/VCP-045.md` 에 있다
- 남은 범위: 운영에서 실제로 발동했는지는 로그로만 확인된다. 배포는 gunicorn 워커를 모두 재기동해야 반영된다(장 중 금지). `[VCP-041]` 과 같은 재기동으로 함께 반영된다
- [x] 운영자 확인: 운영 `backend.log` 에서 「이번 세션에서 Z.ai를 비활성화합니다」 발생 여부 → 2026-09-25 확인: 발생 없음(`qa/VCP-045.md`)
- [ ] 배포와 워커 전부 재기동(운영자, 장 마감 뒤), 발동했다면 10분 뒤 「VCP 분석기 세션 차단 해제: … zai=prompt-echo responses」 로그 확인

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)

## P2 — 대기

### [FLOW-025] 수급 CSV 의 5행 창이 빠진 거래일을 모르고 6거래일 이상의 합을 5일 값으로 쓴다
- 카테고리: 수급·백테스트 | 티어: T3(위험 경로 `services/investor_trend_5day_service.py`) | 근거: `[FLOW-023]` 코드 리뷰(closing-bet-reviewer F1, 2026-09-25), 코드로 확인
- 내용: `[INFRA-095]` 이후 수급 CSV 작성부(`scripts/init_data.py:389-395` Toss 경로, `:1294-1303` pykrx 경로)는 값이 빈 날을 빈 칸으로 쓰지 않고 그 행을 저장하지 않는다. `_build_trend_map`(`services/investor_trend_5day_service.py:396-400`)은 종목별 `tail(5)` 와 `len(recent) < 5` 만 보므로, 창 안의 하루가 빠진 종목은 6거래일 이상에 걸친 합을 `days: 5` 로 내보낸다. 가장 최근 날만 빠지면 전날 값이 details[0] 이 되고, `stale_csv` 는 영업일 4일을 넘어야 붙으므로 플래그도 없다. `[FLOW-023]` 은 빈 칸만 걸러 낸다
- 확인 수준: 코드로만 확인. 운영·로컬 CSV 에서 창 안의 행이 빠진 종목 수는 확인하지 않았다
- 설계 방향(제안): 종목의 최근 5개 날짜를 CSV 전체의 최근 5거래일(기준일 이하)과 대조해 다르면 map 에서 빼거나 플래그를 붙인다. 시그널 추적기(`engine/signal_tracker_supply_helpers.py` 의 `groupby.tail(5)`)도 같은 창을 써서 같은 문제가 있다. `[FLOW-024]` 는 빈 칸만 고치고 이 문제는 이 항목에 남겼으므로(2026-09-25 설계 (C)) 두 경로를 같은 기준으로 설계한다. 최신 날짜만 일부 종목에 들어온 CSV 에서 전 종목이 빠지지 않게 하는 기준도 함께 정한다
- 관련 관찰(`[FLOW-023]` /review L1, 확신도 중간): `_detect_csv_anomaly_flags`(`services/investor_trend_5day_service.py:577`)는 target 이 None 일 때만 `stale_csv` 를 판정한다. 스크리너가 오늘 날짜 target 으로 Toss 실패 대체 경로(`engine/screener.py:367-373`)를 타면 CSV 전체가 낡아도 플래그 없이 채택된다. 창을 기준일의 최근 5거래일과 대조하면 이 경우도 함께 잡힌다. 운영 파이프라인(`services/kr_market_vcp_background_service.py:69-77`)은 CSV 를 먼저 갱신하므로 가능성은 낮다
- 설계 때 집계(2026-09-25, 로컬 `data/all_institutional_trend_data.csv` 09-21 파일 읽기 전용): 2,002종목 중 1,897종목이 최근 5거래일(09-15~09-21)을 모두 가짐. 창 안에 빠진 날이 있는 종목 17(예: `000325` 의 5행이 09-07~09-21, 11거래일), 창이 최신 날짜 전에 끝나는 종목 88(1~57거래일 전, 59종목이 09-09 에서 멈춤)
- 설계 승인: 승인 일자 2026-09-25 | 승인 확인 시각 21:54 | 범위: bounded·T3, 권장안 (A)~(D) 채택. (1) `services/kr_market_csv_utils.py` 에 공통 함수: 기준일 이하 날짜별 행 수가 최근 10개 날짜 중 최대의 80% 이상인 날만 거래일로 세고 마지막 5개를 창으로 쓴다(80% 는 `scripts/init_data.py:1236` 의 부분 날짜 기준과 같음) (2) `_build_trend_map` 은 그 5일에 행이 모두 있는 종목만 map 에 넣는다(A: 플래그 대신 제외, 빠진 종목은 기존 「CSV 에 없음」 경로) (3) `build_supply_score_frame` 도 같은 함수·조건, 두 경로 모두 제외 수 로그 한 줄 (4) SQLite 스냅숏 키 접미사 서비스 `_unified_v2`, 시그널 추적기 `_v3` (B) `stale_csv` 기준 시각을 target 이 있으면 target 으로 (C) 80%·최근 10개 날짜 (D) `normalize_ticker` 의 K 끝 우선주 코드 결함은 `[FLOW-028]` 로 등록만. 한계: CSV 전체에서 빠진 날은 알 수 없음(`ponytail:` 주석). `engine/screener.py` docstring 의 「정상 자료면 참조 비용 0」 문장 갱신 | 실제 대화 근거: 2026-09-25 설계 제시 → 사용자 `/effort high` 후 「승인」
- [x] 구현 계획 문서(`docs/superpowers/plans/2026-09-25-flow-025-supply-window-trading-days.md`, 태스크 2개)와 계획 검토(`oh-my-claudecode:critic`, 2026-09-25) REVISE, 재설계 불필요·코드 대조와 새 검사 기대값 직접 계산 일치: M1 기존 `test_build_supply_score_frame_filters_by_score_and_foreign_min` 고정 자료(행 수 3,3,3,3,2)가 새 규칙으로 깨짐 → 고정 자료만 고침(단언 불변) | M2 승인안 (C) 에서 바꾼 것이 둘(비교 대상 최대→전날, 판정 범위 전 날짜→끝쪽 이어진 날짜) → Ruling 과 `ponytail:` 주석에 둘 다 기록, 사용자 보고 대상 | M3 새로 빠지는 종목이 verify=False 믹스인에서 0 저장 경로를 탐 → `[FLOW-026]` 내용에 추가 | L1 수집 오류 Expected 정정 | L2 순환 import 검사 등 3개 파일 추가 | L3 창 밖 행만 빠진 종목 `000040` 추가 | Nit: `count` 인자 제거, 모듈 수준 import. 순환 import 위험 없음(engine 의 collectors 는 지연 import)
- [x] 구현(공통 함수·서비스·시그널 추적기·캐시 키·docstring)과 테스트: 새 검사 6건(함수 2, 서비스 3, 시그널 추적기 1). RED 는 함수 import 수집 오류, map 에 `000020`·`000030` 잔존, `latest_date` 02-24 섞임, 기준일 `stale_csv` 없음, 시그널 결과에 `000001`·`000002`. 기존 고정 자료 1건 수정(계획 검토 M1, 단언 불변). GREEN: Task 1 인접 15개 파일 238 passed, Task 2 시그널 추적기·순환 import 31 passed
- [x] `/ponytail-review`(2026-09-25): Lean already. Ship.(지적 0)
- [x] 리뷰 전 pytest 전체(2026-09-25): 2859 passed·2 skipped exit 0(2853 + 새 검사 6), 「KRX 로그인」 출력 0회. 출력 scratchpad `flow025/pytest-full.txt`. T3 리뷰 직전 effort 정지(xhigh 로 올린 뒤 재개)
- 묶음 진행: `[FLOW-025]`~`[FLOW-028]` 을 한 라운드로 진행한다(T3 공유 검토, 계획 `docs/superpowers/plans/2026-09-25-flow-025-supply-window-trading-days.md` 태스크 3~5, QA 문서 `qa/FLOW-025.md` 하나). 진행 체크는 `[FLOW-025]` 에 적는다 | 실제 대화 근거: 2026-09-25 사용자 「FLOW-025, FLOW-026, FLOW-027, FLOW-028 모두 묶어서 한번에 처리할 수 있으면 한번에 처리해」
- [x] 묶음 계획 보강(태스크 3 `[FLOW-028]`·4 `[FLOW-027]`·5 `[FLOW-026]`)과 계획 검토(`oh-my-claudecode:critic`, 2026-09-25) REVISE, 재설계 불필요·기대값 실측 일치(pykrx 재호출 없음, None 하류 안전): M1 `test_collectors_refactor.py` 의 `test_naver_finance_investor_trend_uses_pykrx_sqlite_summary_cache` 도 삭제 대상 → 삭제 | M2 새 Naver 검사가 옛 코드에서도 통과하고 원본 `data/` 캐시에 쓸 수 있음 → 호출 기록 단언, `_get_latest_market_date`·`BASE_DIR` 대역 | L1 재호출 없음을 지키는 실제 서비스 검사 추가(4행·NaN, 호출 1회) | L2 우선주 보유 평가 가격이 자기 코드로 조회됨 → Task 3 인접 실행에 모의투자·실시간 가격 검사 10개 파일, 보고·QA 에 기록 | L3 전부 0 사례 추가 | Nit: `5930KS` 고정은 호출처 근거 없어 미반영, 낡은 docstring 둘 고침, `has_csv_anomaly_flags` 단언 삭제, 쓰지 않는 import 삭제. pykrx 참조가 끝 날짜를 기준일과 대조하지 않는 것은 범위 밖 → `[FLOW-029]` 로 등록
- [x] 태스크 3~5 구현과 테스트(2026-09-25). RED: 정규화 3건(`000088`·`000220`·`000680` 반환), 서비스 5건(`get_pykrx_trend_5day` 없음), 수집기 3건, Naver 2건(False 전달·pykrx 직접 호출), 등급 1건(AttributeError), 실제 서비스 경로 2건(4행 부분합 외국인 10·기관 40 을 5일 값으로 반환). 원본 `data/` 새 파일 0. GREEN: Task 3 인접 14개 파일 301 passed, Task 4 스크리너 6개 파일 40 passed, Task 5 인접 9개 파일 128 passed. 삭제한 검사(대상 코드 삭제): FLOW-027 CSV 점수 함수 4건, 믹스인 pykrx 요약 캐시 SQLite 재사용 2건(`test_collectors_refactor.py`), Naver 요약 캐시 적중 1건(새 기본값 유지 검사로 대체), `_deserialize_pykrx_supply_payload` 개인 값 6건, `has_csv_anomaly_flags` 2건. 수집기 통합 서비스 검사 2건은 새 계약 3건으로 다시 씀. 쓰이지 않던 import 셋(`math`·`_CSV_SOURCE_SQLITE_READY`·`asyncio`)은 HEAD 부터 있던 것이라 두었다
- [x] `/ponytail-review`(2026-09-25, 묶음): Lean already. Ship.(묶음 diff 26파일 +371/−773)
- [x] 리뷰 전 pytest 전체(2026-09-25, 묶음): 2857 passed·2 skipped exit 0(2859 − 삭제 16 + 추가 14), 「KRX 로그인」 출력 0회. 출력 scratchpad `flow025/pytest-full-bundle.txt`. T3 묶음 리뷰 직전 effort 정지(xhigh 로 올린 뒤 재개)
- 설계 대비 변경(계획 Ruling, 2026-09-25): 승인안 (C) 의 비교 대상을 「최근 10개 날짜 중 최대」에서 「바로 전 날짜」로, 판정 범위를 「최근 10개 날짜 각각」에서 「끝에서부터 이어진 모자란 날짜」로 바꿨다(비율 80% 는 승인대로). 22:11 정지 보고에서 사용자에게 표로 알리고 되돌릴지 물었으며, 사용자는 되돌림 요청 없이 묶음 설계를 승인했다(22:26). 알려진 한계(묶음 리뷰 F2·M1): 끝쪽 부분 날짜가 둘 이상 이어지고 행 수가 서로 80% 안쪽이면 둘 다 창에 남아 그날 행이 없는 종목이 빠진다(틀린 값 대신 결측)
- [x] 묶음 리뷰(2026-09-25, xhigh, 같은 diff(TODO 제외 SHA-256 `e9c71268…`)를 두 리뷰가 병렬로 받음): `closing-bet-reviewer` CHANGES_REQUIRED(max medium, 코드 결함은 low 이하): F1 승인안 (C) 를 바꾼 Ruling 의 사용자 확인·기록 → 위 「설계 대비 변경」 줄(22:11 보고, 22:26 승인) | F2 끝쪽 부분 날짜가 이어지면 둘 다 창에 남음 → 코드 불변(대안인 앞선 날짜 최대 비교는 종목 목록이 줄어든 CSV 에서 창이 옛 날짜에 머묾), `ponytail:` 주석·검사 docstring 반영, 사용자 보고 | F3 `[FLOW-023]` 이전 pykrx 참조 SQLite 캐시의 NaN→0 항목을 기준일 실행이 먼저 읽음 → 회귀 아님, `[FLOW-029]` 에 추가 | F4 영문자로 끝나는 6자 토큰이 먼저 잡힘(`5930KS`·`5000KRW`) → 호출처 48곳에 그런 입력 근거 없음, QA 문서 「알려진 동작 변화」 | F5 상수 주석의 「init_data 기준과 같다」 → 「숫자만 같다」 반영 | nit N1 「최근 5행」 주석·로그, N2 docstring 상한 거부, N3 v2 주석에 `[FLOW-028]`, N4 캐시 비우기 중복, N5 정확히 80% 경계 검사, N6 `grade_decider` 의 supply 타입 힌트 Optional, N9 빈 줄 → 반영 | N7 스크리너 docstring 「약 100개」 → `/review` 가 로컬 CSV 로 100개를 확인해 그대로 | N8 검사 수 집계 → 아카이브에서 파일별로 다시 세어 기록 · `/review`(T3, `oh-my-claudecode:code-reviewer` opus) COMMENT, Critical·Important 0: M1 = F2 → 같은 조치 | M2 거부된 pykrx 참조(NaN 인 날·전부 0)도 기준일 키로 SQLite 에 영구 저장돼 같은 날 다시 묻지 않음 → 회귀 아님(옛 요약 캐시는 부분합 저장), `[FLOW-029]` 에 추가 | N1 스크리너 우선순위 정렬의 종목별 `tail(5)` → `[FLOW-024]` (A) 에서 유지하기로 한 부분이라 그대로 | N2 = N4 | O1 Naver 상세 캐시가 영문자 코드를 거부 → `[JONGGA-043]` 등록 | O2 가격 파생 캐시의 옛 `000680` 키 → 설계가 수용 | O3 = F1. 보안 리뷰 보강: 인증·시크릿 경로 변경이 없어 해당 없음
- [x] 정적 검증(2026-09-25, 리뷰 반영 뒤): pytest 전체 2858 passed·2 skipped exit 0(리뷰 반영의 80% 경계 검사 1건 추가, 부등호를 `<=` 로 바꾼 변이에서 창 끝이 09-21 로 바뀌어 그 검사가 잡음을 확인), 「KRX 로그인」 출력 0회, 원본 `data/` 최근 15분 변경 0. vitest 전체 104개 파일 701 passed exit 0(frontend 변경 없음). 출력 scratchpad `flow025/pytest-full-after-review.txt`·`vitest-full.txt`. QA 행렬 `docs/dev-cycle/qa/FLOW-025.md` 작성
- [ ] QA(격리 사본, 상세 모달 브라우저 실측(창 안 누락 종목·`000680`·`00680K`) + CLI 하네스(시그널 추적기, 가짜 pykrx 로 `get_supply_data`·Naver 투자자 동향))

### [FLOW-026] 수집기 믹스인의 자체 pykrx 수급 폴백이 결측을 0 이나 부분합으로 5일 값에 쓴다
- 카테고리: 수급·백테스트 | 티어: 판정은 설계 때 §2 대조 | 근거: `[FLOW-023]` T3 심층 리뷰(/review M2, 2026-09-25), 코드로 확인
- 내용: `get_investor_trend_5day_for_ticker` 를 verify=False 로 부르는 두 믹스인은 플래그가 붙거나 None 이면 자기 pykrx 경로로 빠진다. (a) `engine/collectors/krx_local_data_mixin.py:1168-1186` 은 pykrx 가 빈 프레임이면 플래그 붙은 CSV(`stale_csv`·`extreme_abs_total` 포함)를 그대로 쓰고, CSV 가 없으면 0·0 을 요약 캐시(SQLite)에 저장한다. 예외 갈래(`:1209-1214`)도 CSV 를 그대로 쓴다. `engine/collectors/naver_pykrx_mixin.py:489-503` 은 빈 프레임이면 0·0 을 저장하고 표시한다 (b) 프레임이 있으면 `df.tail(5)` 뒤 `int(df[col].sum())` 으로 합치므로(`krx_local_data_mixin.py:1188-1195`, `naver_pykrx_mixin.py:506-519`) NaN 인 날을 건너뛴 부분합과 5행 미만의 합이 `foreign_buy_5d` 로 남는다. `[FLOW-023]` (1) 로 map 에서 빠진 종목도 이 경로를 탄다. `[FLOW-025]` 로 최근 5거래일 중 하루라도 행이 없어 map 에서 빠진 종목(로컬 09-21 파일 약 100개)도 같다. `get_supply_data` 는 `engine/phases_analysis.py:104`·`engine/generator_helpers.py:145` 가 불러 종가베팅 점수에 닿는다
- 확인 수준: 코드로만 확인. pykrx 가 예외 대신 빈 프레임을 주는 빈도와 NaN 을 주는 조건은 확인하지 않았다
- 설계 승인: 승인 일자 2026-09-25 | 승인 확인 시각 22:26 | 실제 대화 근거: 2026-09-25 묶음 설계 제시 → 사용자 `/effort high` 후 「승인」 | 범위: bounded·T3, 권장안 (E)~(G) 채택. (E) 서비스에 공개 함수 `get_pykrx_trend_5day` 를 두어 기존 pykrx 참조 조회(`_get_reference_trend_cached`)의 값 중 `_reference_reject_reason` 을 통과한 것만 돌려준다(5행 미만·NaN 인 날·전부 0 은 None, 조회 기간 14일). `KRXCollector.get_supply_data` 는 기준일이 있으면 그 함수를 먼저, 없거나 값이 없으면 검증 켠 `get_investor_trend_5day_for_ticker` 를 쓰고 결과가 없으면 None. 정규 종가베팅은 기준일을 항상 넘기고(`engine/generator_runtime_mixin.py:132`) 스케줄러는 수급 CSV 수집이 실패해도 종가베팅을 돌리므로(`services/scheduler_jobs.py:152-164`) 기준일 실행의 pykrx 우선은 유지 (F) pykrx 가 비면 검증 켠 서비스 규칙대로 깨끗한·`single_day_spike` 만 붙은 CSV 는 쓰고 `stale_csv`·`extreme_abs_total` 은 버림, 0·0 저장 갈래 삭제. Naver `_get_investor_trend` 도 검증 켠 서비스 한 번으로 줄이고 값이 없으면 기본값 유지(결측 0 표시는 `[JONGGA-042]`). 호출자가 사라지는 믹스인 pykrx 요약 캐시(메서드 넷·클래스 속성 넷)와 `has_csv_anomaly_flags` 삭제, 운영의 옛 `pykrx_supply_5d` SQLite 파일은 지우지 않음 (G) `engine/grade_decider.py` `_has_dual_buy` 에 None 가드(지금은 AttributeError 로 「기타」 탈락). `verify_with_references` 매개변수는 테스트 격리용으로 유지
- 진행: `[FLOW-025]` 묶음 체크리스트

### [FLOW-027] 호출자가 없는 스크리너 CSV 수급 점수 함수와 읽히지 않는 `_inst_by_ticker` 를 지운다
- 카테고리: 수급·백테스트 | 티어: 판정은 설계 때 §2 대조(`engine/screener.py` 를 고침) | 근거: `[FLOW-024]` 설계 조사(2026-09-25), 코드로 확인
- 내용: `score_supply_from_csv`(`engine/screener_scoring_helpers.py:132`)와 `calculate_supply_score_from_csv`(`engine/screener_supply_helpers.py:240`)는 2026-02-26 `dd5a011e` 에서 스크리너의 호출이 사라진 뒤 테스트만 부른다. 둘 다 5행 합에서 빈 칸을 건너뛰고 `int(NaN)` 에서 예외가 난다. 이 함수에 넘기던 `SmartMoneyScreener._inst_by_ticker`(`engine/screener.py:96`·`:179`)는 실행마다 수급 CSV 전체를 종목별로 나누지만 읽는 곳이 없다. 사용자에게 보이는 결함은 없고, 다시 연결되면 결함이 되살아난다
- 설계 승인: 승인 일자 2026-09-25 | 승인 확인 시각 22:26 | 실제 대화 근거: 2026-09-25 묶음 설계 제시 → 사용자 `/effort high` 후 「승인」 | 범위: `score_supply_from_csv`·`calculate_supply_score_from_csv`·`_inst_by_ticker` 와 그 테스트 4건(`tests/engine/test_screener_helpers_refactor.py`·`test_screener_supply_helpers_refactor.py` 각 2건, `test_screener_data_cache_refactor.py:24` 한 줄) 삭제. `inst_df` 는 우선순위 정렬이 읽어 유지
- 진행: `[FLOW-025]` 묶음 체크리스트

### [FLOW-028] `normalize_ticker` 가 K 로 끝나는 옛 우선주 코드를 다른 여섯 자리 코드로 바꾼다
- 카테고리: 수급·백테스트 | 티어: 판정은 설계 때 §2 대조(`engine/ticker_utils.py`, 호출 68곳) | 근거: `[FLOW-025]` 설계 조사(2026-09-25), 로컬 실행으로 확인
- 내용: `_TICKER_PATTERN`(`engine/ticker_utils.py:15`)은 마지막 글자가 숫자여야 해서 `00088K`(한화3우B) 같은 「숫자 다섯 + K」 코드를 잡지 못하고, 대체 갈래가 숫자만 남겨 `zfill` 하므로 `000088` 이 된다(`0009K0` 같은 새 형식은 그대로). 로컬 수급 CSV 에 이런 종목이 19개 있고, 통합 수급 map(`get_ticker_padded_series`) 키가 `000088` 로 들어가 `get_investor_trend_5day_for_ticker` 의 `zfill(6)` 조회(`00088K`)와 어긋난다. 스크리너 묶음 조회는 양쪽을 `normalize_ticker` 로 맞춰 우연히 맞는다. 실제 `000088` 종목이 생기면 두 종목의 행이 한 키에 섞인다
- 확인 수준: `normalize_ticker("00088K") == "000088"` 과 로컬 CSV 종목 수만 확인. 다른 호출처(가격·시그널·챗봇)의 영향은 확인하지 않았다
- 설계 때 확인(2026-09-25, 로컬 `data/` 읽기 전용): 이미 충돌이 있다. 수급 CSV 에서 `00680K`(미래에셋증권2우B)의 65일치 행이 `000680`(LS네트웍스) 키에 섞이고, 가격 CSV 에서는 `000680` 과 `000220`(유유제약, `0220WL` 8행)이 섞인다. 영문자로 끝나는 코드는 수급 CSV 22개(모두 숫자 다섯+영문자), 가격 CSV 24개
- 설계 승인: 승인 일자 2026-09-25 | 승인 확인 시각 22:26 | 실제 대화 근거: 2026-09-25 묶음 설계 제시 → 사용자 `/effort high` 후 「승인」 | 범위: `_TICKER_PATTERN` 을 `[0-9][0-9A-Z]{5}` 로 바꿔 마지막 자리 영문자를 받음, 기존 파라미터 검사에 `00088K`·`0220WL` 추가. 수급 map·시그널 추적기 캐시 키는 `[FLOW-025]` 에서 올렸으므로 함께 배포, 다른 파생 캐시는 CSV 서명이 바뀌는 다음 수집 때 새로 만들어짐
- 진행: `[FLOW-025]` 묶음 체크리스트

### [FLOW-029] pykrx 수급 참조가 끝 날짜를 기준일과 대조하지 않고 기준일 키로 영구 캐시된다
- 카테고리: 수급·백테스트 | 티어: T3(위험 경로 `services/investor_trend_5day_service.py`) | 근거: `[FLOW-025]` 묶음 계획 검토(critic Nit 5, 2026-09-25), 코드로 확인
- 내용: `_fetch_pykrx_reference_trend` 는 기준일까지 14일을 받아 `tail(5)` 를 쓰지만 마지막 행이 기준일인지 보지 않는다. 그날 자료가 아직 없으면 전날까지의 5일이 기준일의 5일 값으로 채택되어 `_get_reference_trend_cached` 가 기준일 키로 SQLite 에 저장하고, 이후 같은 기준일 조회는 다시 받지 않는다. `[FLOW-026]` 로 종가베팅 기준일 실행이 이 경로를 1순위로 쓴다. 옛 믹스인 요약 캐시도 같은 동작이었으므로 회귀는 아니다
- 확인 수준: 코드로만 확인. 17시 체인에서 pykrx 가 당일 행을 늦게 주는 빈도는 확인하지 않았다
- 같은 캐시의 관찰 둘(`[FLOW-025]` 묶음 리뷰, 2026-09-25): (1) `/review` M2 — `_reference_reject_reason` 이 거부하는 값(NaN 인 날의 `insufficient_days`, `zero_total`)도 정규화를 통과해 기준일 키로 SQLite 에 저장된다. `get_pykrx_trend_5day` 는 저장한 뒤에 거부하므로 같은 날 새 워커가 다시 실행해도 pykrx 를 다시 묻지 않는다(가짜 pykrx 로 2회차 정상 값에도 None·호출 1회 확인). 4행·빈 프레임은 메모리 60초 실패 캐시라 다시 묻는다 (2) `closing-bet-reviewer` F3 — `930525be` 이전 `_fetch_pykrx_reference_trend` 는 NaN 을 0 으로 저장했고 참조 캐시의 네임스페이스·서명에 버전이 없어, 그 항목이 기준일 실행에서 부분합으로 채택될 수 있다. 존재 여부는 확인하지 않았다. 설계 때 「거부 값은 저장하지 않음」과 캐시 버전 올림을 함께 본다
- [ ] 설계 승인(끝 날짜가 기준일과 다르면 거부할지, 캐시하지 않을지, 거부 값 저장과 캐시 버전), 테스트, 리뷰, QA

### [JONGGA-042] 상세 API 의 Naver·기본값 폴백이 결측 수급을 0 으로 채운다
- 카테고리: 종가베팅 | 티어: T2(판정은 설계 때 §2 대조) | 근거: `[FE-048]` 구현 중 코드로 확인(2026-09-25)
- 내용: Toss 종목 정보 조회가 실패하면 상세 API 는 Naver(`engine/collectors/naver_extractors_mixin.py:42-45` 의 `investorTrend` 기본값 0)나 기본 페이로드(`services/kr_market_stock_detail_service.py:216` 의 `foreign`·`institution` 0)를 돌려준다. 확정 집계도 없으면 모달은 결측을 실제 0 과 같은 「-」로 그린다. `[FE-048]` 은 Toss 갈래만 고쳤다
- 확인 수준: 코드로만 확인. Naver 수집기가 값을 채우지 못하는 조건과 운영 빈도는 확인하지 않았다
- [ ] 설계 승인(Naver·기본값의 결측을 None 으로 둘지), 테스트, 리뷰, 브라우저 QA

### [JONGGA-043] Naver 상세 캐시가 영문자로 끝나는 종목코드를 저장하지 않아 모달을 열 때마다 다시 스크랩한다
- 카테고리: 종가베팅 | 티어: 판정은 설계 때 §2 대조 | 근거: `[FLOW-025]` 묶음 T3 심층 리뷰(/review O1, 2026-09-25), 코드로 확인
- 내용: `NaverFinanceCollector._normalize_stock_detail_payload`(`engine/collectors/naver.py:228-229`)는 코드가 숫자 여섯 자리가 아니면 None 을 돌려준다. `[FLOW-028]` 이후 `00680K` 같은 코드가 자기 코드로 상세 API 에 오므로, Toss 가 실패해 Naver 로 넘어가면 결과가 캐시되지 않고(`naver.py:304` 가 정규화 전 결과를 그대로 반환) 모달을 열 때마다 Naver 를 다시 스크랩하고 통합 수급 서비스(참조 조회 포함)를 다시 부른다. 읽기 캐시 갈래(`:264`)도 같은 함수로 거른다. 예전에는 숫자 코드로 바뀌어 다른 종목 키로 캐시되었으므로 회귀가 아니라 비용 문제다
- 확인 수준: 코드로만 확인. Toss 상세가 실패하는 빈도와 영문자 코드 종목의 모달 조회 빈도는 확인하지 않았다
- [ ] 설계 승인(검증을 `normalize_ticker` 기준으로 바꿀지), 테스트, 리뷰, QA
