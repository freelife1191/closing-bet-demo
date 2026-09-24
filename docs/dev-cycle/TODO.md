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

### [VCP-057] VCP 수급 결측의 남은 0 기본값과 실제 0 의 색 표기
- 카테고리: VCP | 티어: T2 | 근거: `[VCP-054]` 설계에서 범위 밖으로 남긴 것(2026-09-24 21:03)과 `closing-bet-reviewer` low
- 남은 것: (1) `engine/screener.py` `ScreenerResult` 의 `foreign_net_5d: int`·1일 기본값 0(현재 dict 경로에서 쓰이지 않음), (2) `_score_supply_core` 가 `details` 행에 키가 없으면 1일 값을 0 으로 씀, (3) 수동 스크립트 `tests/test_vcp.py:72`·`scripts/diagnose_screener.py:62` 가 None 에서 TypeError, (4) VCP 표의 실제 0 이 매도와 같은 빨간색(`frontend/src/app/dashboard/kr/vcp/page.tsx` 의 `supplyColorClass`, `[VCP-054]` 이전과 같은 표기), (5) `engine/kr_ai_data_service.py:436-437` 이 빈 칸을 0 으로 읽음(읽는 곳은 `run.py` 의 `KrAiAnalyzer` 뿐이며 그 전략은 종료되어 값을 쓰지 않음)
- 확인 수준: 코드로만 확인. 운영에서 드러나는 증상은 (4) 표기뿐이다
- 설계 승인: 승인 확인 시각 2026-09-25 08:40
  | 범위: (1) `engine/screener.py` 의 미사용 `ScreenerResult` 삭제, (2) `_score_supply_core` 의 1일 값을 키·값이 없으면 None(연속 매수는 None 에서 멈춤, 점수 불변), (3) 두 수동 스크립트가 None 을 `-` 로 출력, (4) `supplyColorClass` 의 실제 0 을 중립 회색 `text-gray-300`(결측 `text-gray-500`·매수·매도 불변), (5) `kr_ai_data_service` 는 `KrAiAnalyzer` 가 수급 값을 읽지 않아 변경 없음
  | 실제 대화 근거: 2026-09-25 사용자 「진행해」 응답, 현재 세션의 VCP-057 설계 제안
- QA 시나리오: VCP 표에서 실제 0 순매수 셀이 매도(빨강)와 다른 중립색이고 결측은 `-` 회색이다
- [x] 구현 (1)~(4), (5) 변경 없음(근거: `KrAiAnalyzer.analyze` 는 `stock_info` 에서 name·price·change_pct 만 읽고 전략 둘은 종료되어 읽지 않음, 리뷰어 확인)
- [x] pytest (2) 한 건(수정 전 TypeError 로 RED), vitest `page.regression-vcp-054.test.tsx` 에 0 색 한 건(수정 전 `text-red-400` 으로 RED)
- [x] ponytail 리뷰(자체 수행): shrink 1건(1일 값 변환 4줄→한 식) 반영
- [x] `closing-bet-reviewer`(vcp057-reviewer): APPROVE, 최대 low. low1(`tests/test_vcp.py` 가 NaN 을 `nan` 으로 출력) 반영해 `pd.isna` 로 판정, low2(정규화기 둘이 결측을 0 으로 채움)는 범위 밖이라 `[INFRA-109]` 에 추가, low3(음수 내림)은 종전 동작과 같아 미반영
- [x] pytest·vitest 전체와 lint·type-check(리뷰 반영 뒤 재실행): pytest 2803 passed·2 skipped, vitest 100파일 691 passed, lint·type-check exit 0
- [ ] 격리 사본 브라우저 QA(가짜 비밀)

### [VCP-045] Z.ai 폴백의 `zai_disabled_reason` 도 워커 수명 동안 풀리지 않는다 (운영자 단계)
- 카테고리: VCP | 티어: T1(남은 단계는 운영자 확인과 배포) | 근거: `[VCP-041]` 코드 리뷰(2026-09-24). 코드 수정분은 커밋 `22b197a`(`_expire_session_blocks` 가 `zai_disabled_reason` 도 10분 뒤 비움)로 끝났고 기록은 `archive/daily/2026-09-24.md`·`qa/VCP-045.md` 에 있다
- 남은 범위: 운영에서 실제로 발동했는지는 로그로만 확인된다. 배포는 gunicorn 워커를 모두 재기동해야 반영된다(장 중 금지). `[VCP-041]` 과 같은 재기동으로 함께 반영된다
- [x] 운영자 확인: 운영 `backend.log` 에서 「이번 세션에서 Z.ai를 비활성화합니다」 발생 여부 → 2026-09-25 확인: 발생 없음(`qa/VCP-045.md`)
- [ ] 배포와 워커 전부 재기동(운영자, 장 마감 뒤), 발동했다면 10분 뒤 「VCP 분석기 세션 차단 해제: … zai=prompt-echo responses」 로그 확인

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)

### [VCP-051] 시그널 가격 갱신이 청산(CLOSED)된 행의 수익률도 오늘 가격으로 덮는다
- 카테고리: VCP | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: `vcp-data-audit` 읽기 전용 감사(2026-09-24 17:4x, 사용자 질문 「과거 데이터가 사라지지 않는지」), 리더가 코드로 재확인
- 원인: `update_vcp_signals_recent_price`(`scripts/init_data.py:2006-2018`)가 `status` 를 보지 않고 모든 행의 `current_price`·`return_pct` 를 덮는다. 청산된 행의 실현 수익률이 사라진다
- 영향: 지금은 청산 행의 이 값을 읽는 화면이 없어 드러나지 않는 잠재적 이력 오염이다. 청산 행이 화면에서 빠지는 것(`[VCP-034]`)은 의도된 동작이며, 과거 날짜 조회에 청산 행을 보일지는 정책으로 따로 정한다
- [ ] 설계 승인, OPEN 행만 갱신하는 테스트, 리뷰와 pytest 전체

### [VCP-052] VCP AI JSON 의 읽기·병합·저장에 잠금이 없고 최신 파일 가격 동기화는 원자적이지 않다
- 카테고리: VCP | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: `vcp-data-audit` 읽기 전용 감사(2026-09-24 17:4x, 사용자 질문 「과거 데이터가 사라지지 않는지」), 리더가 코드로 재확인
- 원인: 수동 갱신 병합(`services/common_update_ai_analysis_service.py:117-146`, 원자적 교체는 함)·수집(`scripts/init_data.py:1522`)·재분석(`services/kr_market_vcp_reanalysis_service.py:750`)이 같은 날짜 파일을 잠금 없이 읽고 병합해 쓴다. `vcp_status` 는 워커 메모리에만 있어 서로 막지 못한다. 가격 동기화(`scripts/init_data.py:2056`)는 `open('w')` 로 직접 쓴다
- 영향: 동시 실행 시 한쪽이 더한 판정이 유실될 수 있고, 저장 중 중단되면 최신 파일이 깨진다. 실제로 겹치는지는 운영 로그로 확인해야 한다(추측)
- [ ] 설계 승인(파일 잠금 범위), 동시 병합 테스트, 리뷰와 pytest 전체

### [INFRA-103] 데이터 상태 화면의 진행 폴링이 조회 오류에도 멈추지 않고 500ms 간격으로 계속 요청한다
- 카테고리: 인프라 | 티어: T2(프론트엔드) | 근거: `[INFRA-102]` 코드 리뷰의 범위 밖 관찰(2026-09-25), 코드로 확인
- 원인: `frontend/src/app/dashboard/data-status/page.tsx` 의 `pollUpdateStatus` catch 는 `console.error` 만 남기고 interval 을 유지한다. 백엔드가 멈췄거나 네트워크가 끊기면 실행 중 표시가 남은 채로 요청이 끝없이 이어진다. 종전부터 있던 동작이다
- 확인 수준: 코드로만 확인. 화면에서 실측하지 않았다
- [ ] 설계 승인(연속 실패 횟수 뒤 멈추고 알릴지, 간격을 늘릴지), 테스트, 리뷰, 브라우저 QA

### [INFRA-104] 수동 업데이트의 실행 시각을 시작 처리에서 스레드로 넘기지 않아 스레드 진입 전의 틈에서 옛 실행이 새 실행으로 보인다
- 카테고리: 인프라 | 티어: T3(위험 경로 `services/common_update_status_service.py`) | 근거: `[INFRA-101]` critic 지적 2·`closing-bet-reviewer` low 1(2026-09-25), 코드로 확인
- 원인: `start_update` 는 이 실행의 `startTime` 을 워커 공용 `LOCAL_RUN_START_TIME` 에만 남기고, 스레드의 `run_background_update` 가 진입 때 그 값을 다시 읽는다. `LOCAL_PIPELINE_ACTIVE` 는 파이프라인 진입 뒤에 켜지므로, 시작 처리와 스레드 진입 사이에 다른 워커의 중단과 같은 워커의 재시작이 겹치면 옛 스레드가 새 실행 시각을 읽는다. 그러면 `[INFRA-097]` 감시는 옛 실행을 멈추지 않고(`_watch_stop_request` ponytail 주석), `[INFRA-101]` 가드는 옛 실행의 항목 쓰기를 새 실행에 통과시킨다
- 수정 후보: `start_update` 가 `startTime` 을 돌려주고 시작 경로가 스레드 인자로 넘긴다(리뷰 제안). 또는 `start_update` 안에서 `LOCAL_PIPELINE_ACTIVE` 를 켠다(스레드가 뜨지 못하면 고착 위험, `[INFRA-099]` 계획 제약)
- 확인 수준: 코드로만 확인. 창은 스레드 기동 시간(수 ms)이다
- [ ] 설계 승인
- [ ] 테스트, T3 리뷰와 pytest 전체

### [INFRA-105] Market Gate 섹터 ETF 등락률 조회가 실패하면 결측 대신 0.0 을 넣어 섹터 급락 감점이 사라진다
- 카테고리: 인프라 | 티어: T3(판정 경로 여부는 설계 때 §2 대조) | 근거: `[INFRA-089]` 영향 확인(2026-09-24)에서 분리(2026-09-25)
- 내용: `engine/market_gate_fetchers_external.py:88-135` 는 pykrx 를 직접 부르고 실패하면 종목마다 `0.0` 을 넣는다. `_calculate_sector_crash_penalty`(`engine/market_gate_analysis.py:77`)가 전부 0 을 받아 감점 0 이 되고, 화면 섹터 신호도 0.00% 로 보인다
- [ ] 설계 승인(실패를 `None` 으로 남기고 감점·화면이 결측을 구분)
- [ ] 테스트, 리뷰, pytest·vitest 전체

### [INFRA-106] `get_last_trading_date` 의 지수 조회 실패가 DEBUG 로그로만 남고 휴장일을 거래일로 본다
- 카테고리: 인프라 | 티어: T3(위험 경로 `scripts/init_data.py`) | 근거: `[INFRA-089]` 영향 확인에서 분리(2026-09-25)
- 내용: `scripts/init_data.py:119` 는 지수 조회가 실패하면 DEBUG 만 남기고 주말만 거른다. 세션이 인증되지 않았을 때 공휴일을 기대 날짜로 돌려주며, 호출자는 `create_daily_prices`·수급 수집·수동 갱신 stale 검증(`services/common_update_pipeline_steps.py:61-90`)이다. `[INFRA-089]` 의 재로그인 복구 뒤에도 KRX 점검 시간처럼 로그인 자체가 실패하면 남는다
- [ ] 설계 승인(WARNING 승격, 실패 때 판정 보류 여부)
- [ ] 테스트, 리뷰, pytest 전체

### [INFRA-107] 워커가 새로 기동하면 다른 워커에서 도는 수동 업데이트의 `isRunning` 과 항목을 지운다
- 카테고리: 인프라 | 티어: T3(판정은 설계 때 §2 대조) | 근거: `[INFRA-098]` 계획 검토(critic 권장 5, 2026-09-25), 코드로 확인
- 내용: `app/__init__.py` 의 `_reset_startup_status_files` 는 기동 때 `update_status.json` 이 `isRunning` 이면 `isRunning=False`·`items=[]` 로 저장한다. 서버 전체 재기동에는 맞지만, gunicorn 이 워커 하나만 다시 띄우면(워커 비정상 종료 등) 다른 워커의 실행 중 상태를 지운다. 잠금도 없어 그 사이의 중단 요청을 덮을 수 있다
- 확인 수준: 코드로만 확인. 운영에서 워커 단독 재기동 빈도는 확인하지 않았다
- [ ] 설계 승인(마스터 기동 때만 초기화할지, 소유 워커의 생존으로 판정할지)
- [ ] 테스트, T3 리뷰와 pytest 전체

### [INFRA-108] Market Gate 의 시장 수급 점수가 수급 파일 마지막 날짜의 임의 종목 한 행을 시장 전체로 쓴다
- 카테고리: 인프라 | 티어: T2(판정은 설계 때 §2 대조) | 근거: `[INFRA-095]` `closing-bet-reviewer` 범위 밖 관찰(2026-09-25), 코드로 확인
- 내용: `engine/market_gate_fetchers_local.py:150-165` 의 `load_supply_data` 는 KIS 가 없으면 `all_institutional_trend_data.csv` 를 종목 구분 없이 날짜로 정렬해 마지막 한 행(마지막 날짜의 임의 종목)의 `foreign_buy`·`inst_buy` 를 돌려준다. `score_supply`(`engine/market_gate_logic_scoring.py:112`)는 그 값으로 시장 수급 점수(최대 15점)를 준다. 시장 합계나 지수 대표 종목이 아니다
- 확인 수준: 코드로만 확인. 운영에서 KIS 키가 있어 이 경로를 타지 않는지는 확인하지 않았다
- [ ] 설계 승인(마지막 날짜 합계로 바꿀지, 069500 행으로 할지, 결측이면 점수를 빼는지)
- [ ] 테스트, 리뷰와 pytest 전체

### [INFRA-109] Toss 투자자 추이의 메모리 파서가 빈 순매수 수량을 0 으로 읽는다
- 카테고리: 인프라 | 티어: T2(판정은 설계 때 §2 대조) | 근거: `[INFRA-095]` 심층 리뷰 Minor 4(2026-09-25), 코드로 확인
- 내용: `engine/toss_collector_metric_parsers.py:87-89` 는 종가가 있는 행의 `netForeignerBuyVolume`·`netInstitutionBuyVolume`·`netIndividualsBuyVolume` 이 비면 `to_float(..., 0)` 으로 0 을 더하고, `services/investor_trend_5day_service.py:234-235` 는 `int(float(detail.get(..., 0)))` 으로 키가 없으면 0 을 쓴다. 파일에는 쓰지 않지만 화면·판정에 결측이 순매수 0 으로 보인다. `[INFRA-095]` 는 파일 저장 경로만 고쳤다
- 확인 수준: 코드로만 확인. Toss 가 수량만 비운 행을 실제로 주는지는 확인하지 않았다
- 추가 발견(`[VCP-057]` `closing-bet-reviewer` low2, 2026-09-25): `_score_supply_core` 로 가는 details 의 정규화기 둘도 같은 모양이다. `services/investor_trend_5day_service.py:462-463` 은 키가 없거나 None 이면 `_safe_int` 로 0 을 넣고, `engine/screener_supply_helpers.py:99-100` 은 키가 없으면 0, 값이 None 이면 그 행을 버려 전날 행이 `details[0]`(1일 순매수)이 될 수 있다(확신도 중간). `[VCP-057]` 이 `_score_supply_core` 에서 None 을 보존하게 했으므로 정규화기가 None 을 넘기면 끝까지 결측으로 남는다
- [ ] 설계 승인(행을 버릴지, 합계를 결측으로 돌릴지)
- [ ] 테스트, 리뷰와 pytest 전체
