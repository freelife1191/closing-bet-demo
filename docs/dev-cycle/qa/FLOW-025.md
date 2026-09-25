# [FLOW-025]~[FLOW-028] 수급 5일 창·수집기 pykrx 경로·죽은 CSV 점수·영문자 종목코드 — QA 시나리오

- 대상: 네 항목을 한 라운드로 묶은 T3 공유 검토(`docs/dev-cycle/TODO.md` 의 `[FLOW-025]` 묶음 진행 줄). `[FLOW-027]` 은 호출자가 없는 코드
  삭제라 사용자 진입 흐름이 없고 pytest(스크리너 6개 파일)로 갈음한다
- 대상 화면: http://localhost:3755/dashboard/kr/closing-bet (격리 Next dev) → 카드의 「상세 분석 보기」 모달의 「투자자 동향」 절
- 구성 근거: 설계 승인(대화 2026-09-25 21:54 `[FLOW-025]`, 22:26 묶음 `[FLOW-026]`~`[FLOW-028]`). 호출 경로:
  카드 클릭 → `fetch('/api/kr/stock-detail/<code>')` → Flask 라우트 → `fetch_stock_detail_payload`(`normalize_ticker`, `[FLOW-028]`)
  → Toss 상세가 있으면 `append_investor_trend_5day` → `get_investor_trend_5day_for_ticker(verify_with_references=True)` → `_build_trend_map`
  (`recent_trading_dates` 창, `[FLOW-025]`) → CSV 에 없으면 pykrx 참조 → Toss 참조. Toss 상세가 없으면 Naver 수집기 →
  `_get_investor_trend`(`[FLOW-026]`, 검증 켠 서비스 한 번). 값이 있으면 응답에 `investorTrend5Day` 가 들어가고 모달은 그 값을 그린다.
  없으면 모달은 Toss 합계(`investorTrend`)로 물러선다. 사용자 진입 흐름이 이 모달이므로 브라우저 실측이 필수다
- 브라우저가 닿지 않는 흐름: 종가베팅 점수의 `KRXCollector.get_supply_data`(17시 체인, 뒤에 LLM 이 이어짐)와 시그널 추적기
  (`run.py` 메뉴 2 의 `scan_today_signals`, 뒤에 AI 분석)는 화면이 없어 CLI 하네스로 검사한다(H-1~H-3)
- 검증 기준 커밋: 새 코드는 이 문서를 담은 첫 커밋, 대조용 수정 전 코드는 `14ede4f2`(첫 커밋의 부모). 사본은 각 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. `[FLOW-022]`~`[FLOW-024]` 와 같은 방식으로 시나리오를 직접 구성했고
  `/qa-only`·`/qa` 스킬 본체는 부르지 않았다(두 스킬의 전체 앱 탐색 대신 이 문서의 시나리오만 실행한다)
- browser_applicability: required(S-1~S-5). browser_driver: gstack `browse`(새 코드만). 수정 전 코드는 API 응답만 대조한다
- 격리: 각 커밋의 `git archive` 를 scratchpad `flow025/qa/new/`·`flow025/qa/old/` 에 풀고 `secrets/`·`data/`·`.env*` 를 지운 뒤, 사본마다 `data/` 를
  새로 만들어 고정 자료(생성기 `flow025/qa/make_fixture.py`)만 둔다. 새 코드 사본의 `frontend/node_modules` 는 APFS clone. CLI 하네스는 실행마다
  고정 자료를 새 디렉터리에 복사해 쓴다. 원본 3500/5501·live 주소·원본 `data/`·`.env` 는 쓰지 않는다
- 대역: Flask 는 QA 전용 진입점 `flow025/qa/qa_flow025_app.py`(사본에만 복사), CLI 는 `flow025/qa/qa_cli.py`. 둘 다 loopback 이 아닌 소켓 연결을
  막아 `QA-BLOCKED` 로 남기고 `sys.modules` 에 가짜 `pykrx` 를 넣는다(`get_market_trading_value_by_date` 는 아래 표의 프레임, 그 밖의 속성은
  호출을 기록하고 실패). Flask 진입점은 `TossCollector._safe_request` 를 종목 정보·투자자 동향만 응답하게, `NaverFinanceCollector._request` 를
  900253 의 main 페이지(종목명만 든 HTML)만 응답하게 바꾼다. LLM·발송 경로는 부르지 않는다. 기동 환경에 `KRX_ID=`·`KRX_PW=` 빈 값
- 기동: 새 코드 Flask `SCHEDULER_ENABLED=false KRX_ID= KRX_PW= gunicorn qa_flow025_app:app --bind 127.0.0.1:5755 --workers 1 --threads 4 --keep-alive 0`,
  Next `PORT=3755 API_URL=http://127.0.0.1:5755 TZ=Asia/Seoul npm run dev`(더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`NEXTAUTH_URL`).
  수정 전 코드 Flask 는 같은 명령으로 `127.0.0.1:5756`
- 단계(phase): 시나리오 구성 완료
- 반복(iteration): 0회
- baseline 상태: 수정 전 코드 사본에 같은 고정 자료로 같은 API·하네스를 돌려 대조한다. 회귀 검사는 수정 전에 실패했다(TODO `[FLOW-025]` 의 RED 기록)
- 필수 여부(required): S-1~S-5, H-1~H-3 예
- 결과:
- 증거:
- 정리(cleanup):
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`. frontend 변경이 없어 Next 번들 문서는 읽지 않았다

## 고정 자료

수급 CSV(원 단위, 1억 = 100,000,000). 날짜별 행 수는 09-15~09-18·09-22~09-23 이 6, 09-21 이 5, 09-24 가 1, 8월 닷새가 각 1 이다.
09-24 는 전날(6)의 80% 에 못 미쳐 창에서 빠지므로 새 코드의 창은 09-17·09-18·09-21·09-22·09-23 이다.

| 종목 | 날짜 | 외국인·기관(하루) | 새 코드 창 합계 | 수정 전 종목별 `tail(5)` 합계 |
|---|---|---|---|---|
| 900251 QA부분일 | 09-15~09-23 + 09-24 | 3억·2억, 09-24 만 9억·6억 | 15억·10억 | 09-18~09-24: 21억·14억 |
| 900252 QA창빈날 | 09-15~09-23 중 09-21 없음 | 3억·2억, 09-16 만 6억·4억 | 창에 4행 → map 제외 | 09-16~09-23(6거래일): 18억·12억 |
| 000680 QA보통 | 09-15~09-23 | 4억·1억 | 20억·5억 | `00680K` 행과 한 키에 섞임 |
| 00680K QA우선 | 09-15~09-23 | -1억·-2억 | -5억·-10억 | `000680` 으로 바뀌어 위와 섞임 |
| 900264 QA깨끗 | 09-15~09-23 | 2억·3억 | 10억·15억 | 같음 |
| 900265 QA정상pykrx | 09-15~09-23 | 1억·1억 | 5억·5억 | 같음 |
| 900266 QA8월 | 08-17~08-21 | 1억·1억 | 창에 행 없음 → map 제외 | 8월 닷새: 5억·5억 |
| 900253 QA네이버, 900261~900263 | 없음 | | | |

가짜 pykrx 거래대금 프레임(인덱스 09-17~09-23). 목록에 없는 종목은 빈 프레임이다.

| 종목 | 외국인합계 | 기관합계 | 새 코드 판정 |
|---|---|---|---|
| 900252 (Flask) | 1억×5 | 2억×5 | 채택 5억·10억 |
| 900253 (Flask) | 3억, 3억, 3억, NaN, 3억 | 1억×5 | NaN 인 날 → `insufficient_days` 로 버림 |
| 900261 (CLI) | 1억×4(4행) | 1억×4 | 5행 미만 → 버림 |
| 900262 (CLI) | 2억, 2억, NaN, 2억, 2억 | 1억×5 | 버림 |
| 900265 (CLI) | 5억×5 | 1억×5 | 채택 25억·5억 |

Toss 대역은 900251·900252·000680·00680K 의 종목 정보에 응답하고 투자자 동향은 모두 하루 -3만주(종가 10,000, 5일 -15억)로 준다.
모달이 「-15억」을 그리면 `investorTrend5Day` 가 빠진 것이다. 900253 은 종목 정보에 응답하지 않아 Naver 로 넘어가고, 투자자 동향 참조에도 None 을 준다.

알려진 동작 변화(리뷰 기록, 조치 없음):
- (`closing-bet-reviewer` F4) `normalize_ticker` 는 이제 영문자로 끝나는 6자 토큰을 먼저 잡는다. `5930KS`·`5930KQ` 는 `005930` 에서 그대로로, `5000KRW` 는
  `005000` 에서 `5000KR` 로, `00000K` 는 빈 문자열에서 `00000K` 로 바뀐다. 호출처 48곳(23개 파일)은 CSV·pykrx·Toss·시그널 JSON 의 코드만 넘기고 챗봇은
  이 함수를 쓰지 않아 이런 입력의 근거가 없다. 의도한 변화는 `00088K`·`0220WL`·`00680K.KS`·`A00680K` 가 자기 코드로 남는 것이다
- (`closing-bet-reviewer` F2, `/review` M1) 끝쪽 부분 날짜가 둘 이상 이어지고 행 수가 서로 80% 안쪽이면 둘 다 창에 남아 그날 행이 없는 종목이
  map 에서 빠진다(틀린 값 대신 결측). 이 문서의 고정 자료는 부분 날짜가 하루다
- (`/review` O1) Naver 상세 캐시는 숫자 코드만 저장한다. 영문자 코드가 Naver 로 넘어가면 모달을 열 때마다 다시 스크랩한다 → `[JONGGA-043]`
- (`closing-bet-reviewer` F3, `/review` M2) pykrx 참조 SQLite 캐시가 거부 값과 `[FLOW-023]` 이전의 NaN→0 값을 기준일 키로 남긴다 → `[FLOW-029]`
- 모의투자 보유 종목 가운데 영문자로 끝나는 우선주는 이제 자기 코드로 평가 가격을 조회한다(계획 검토 L2). 가격이 없으면 평균단가와 `is_stale` 로 떨어진다

## 시나리오

### S-1. 창 안의 하루가 빠진 종목은 6거래일 합을 5일 값으로 내지 않는다 (`[FLOW-025]` 회귀)
- 조작: `curl` 로 새 코드(5755)와 수정 전 코드(5756)의 `/api/kr/stock-detail/900252` 를 받아 `investorTrend5Day` 를 읽는다. 브라우저에서
  QA창빈날 카드의 「상세 분석 보기」를 눌러 외국인·기관 칸의 글자를 읽는다. Flask 로그의 `QA-PYKRX trading_value 900252` 줄을 센다.
- 기대: 새 코드 API `investorTrend5Day` `{foreign: 500000000, institution: 1000000000}`(map 에서 빠져 pykrx 참조 채택), 화면 외국인 「+5억」·
  기관 「+10억」, 로그 1줄. 수정 전 코드 API `{foreign: 1800000000, institution: 1200000000}`(09-16~09-23 여섯 거래일 합), 로그 0줄.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 일부 종목에만 들어온 최신 날짜는 창에서 빠진다 (`[FLOW-025]` 회귀)
- 조작: 900251 에 S-1 과 같은 조작을 한다.
- 기대: 새 코드 API `{foreign: 1500000000, institution: 1000000000}`(09-24 제외), 화면 「+15억」·「+10억」. 수정 전 코드 API
  `{foreign: 2100000000, institution: 1400000000}`(09-24 포함). 두 사본 모두 `QA-PYKRX trading_value 900251` 0줄.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. `00680K` 와 `000680` 은 다른 종목이다 (`[FLOW-028]` 회귀)
- 조작: 두 사본에서 `/api/kr/stock-detail/000680`·`/api/kr/stock-detail/00680K` 를 받아 `code`·`name`·`investorTrend5Day` 를 읽는다. 브라우저에서
  QA보통·QA우선 카드의 모달을 각각 열어 제목과 외국인·기관 칸을 읽는다.
- 기대: 새 코드 `000680` 은 `code` 000680·`name` QA보통·`{2000000000, 500000000}`, 화면 「+20억」·「+5억」. `00680K` 는 `code` 00680K·`name` QA우선·
  `{-500000000, -1000000000}`, 화면 「-5억」·「-10억」. 수정 전 코드 `00680K` 는 `code` 000680·`name` QA보통이고, 두 요청의 `investorTrend5Day` 는
  같으며 두 종목 행이 섞인 값이다(20억·5억도 -5억·-10억도 아니다).
- 필수 여부(required): 예
- 실제:
- 결과:

### S-4. Naver 대체 경로는 pykrx 부분합을 쓰지 않는다 (`[FLOW-026]` 회귀)
- 조작: 두 사본에서 `/api/kr/stock-detail/900253` 을 받아 `investorTrend` 를 읽는다. 브라우저에서 QA네이버 카드의 모달을 열어 외국인·기관 칸을 읽는다.
  Flask 로그의 `QA-NAVER main 900253`·`QA-PYKRX trading_value 900253`·`QA-TOSS trading-trend 900253` 줄을 센다.
- 기대: 새 코드 API `investorTrend.foreign` 0·`institution` 0(통합 서비스가 값을 주지 않아 Naver 기본값이 남음. 결측의 0 표시는 `[JONGGA-042]`),
  화면은 두 칸 모두 「-」. 로그 `QA-NAVER` 1줄, pykrx 1줄(참조 조회, 버림), Toss 1줄(참조 조회). 수정 전 코드 API `foreign` 1200000000·`institution`
  500000000(NaN 인 날을 건너뛴 4일 합).
- 필수 여부(required): 예
- 실제:
- 결과:

### S-5. 오류·외부 연결 없음 (인접)
- 조작: 다섯 모달을 연 뒤 `console --errors` 와 `/_next/mcp` `get_errors`·`get_compilation_issues` 를 읽고, `browse network` 의 `stock-detail` 응답 코드와
  두 Flask 로그의 error·traceback·`QA-BLOCKED` 줄을 센다.
- 기대: `stock-detail` 요청 모두 200, 콘솔·런타임·컴파일 오류 없음, Flask 로그의 세어 본 줄 모두 0. `QA-PYKRX unexpected` 는 Naver 펀더멘탈 조회
  (`get_market_fundamental_by_ticker`)와 기동 확인 라우트에서만 나온다.
- 필수 여부(required): 예
- 실제:
- 결과:

### H-1. 기준일을 준 `get_supply_data` 는 부분합·0·낡은 CSV 를 5일 값으로 쓰지 않는다 (`[FLOW-026]`, CLI)
- 조작: `qa_cli.py <사본> <고정 자료 복사본> supply`. 900261~900266 을 기준일 `20260924` 로, 900264 를 기준일 없이 부른다. 종목별 가짜 pykrx 호출 수와
  사본 `data/` 아래 파일(수정 전 믹스인의 요약 캐시 `pykrx_supply_5d`)을 출력한다.
- 기대(새 코드 → 수정 전 코드):
  - 900261 4행: None, 호출 1 → `[4억, 4억]`
  - 900262 NaN 인 날: None, 호출 1 → `[8억, 5억]`
  - 900263 빈 프레임·CSV 없음: None, 호출 1 → `[0, 0]`
  - 900264 빈 프레임·깨끗한 CSV: `[10억, 15억]`, 호출 1 → 같음
  - 900265 정상 5행: `[25억, 5억]`(CSV 5억·5억이 아니라 pykrx), 호출 1 → 같음
  - 900266 빈 프레임·8월에 멈춘 CSV: None, 호출 1 → `[5억, 5억]`
  - 900264 기준일 없음: `[10억, 15억]`, 호출 0 → 같음
  - 새 코드는 사본 `data/` 에 `pykrx_supply_5d` 가 없다. 수정 전 코드는 900261·900262·900263·900265 의 요약 캐시 4행(부분합과 0·0 포함)을 남긴다
- 필수 여부(required): 예
- 실제:
- 결과:

### H-2. 시그널 추적기도 같은 창을 쓰고 영문자 코드의 가격이 섞이지 않는다 (`[FLOW-025]`·`[FLOW-028]`, CLI)
- 조작: `qa_cli.py <사본> <고정 자료 복사본> tracker`(`create_tracker(data_dir).scan_today_signals()`).
- 기대: 새 코드 결과는 900251 `15억·10억`·100, 000680 `20억·5억`·90, 900264 `10억·15억`·85, 900265 `5억·5억`·60 이고 로그에 「최근 5거래일에 빠진 날이
  있어 점수에서 제외: 2개 종목」(900252·900266). 수정 전 코드는 900251 `21억·14억`, 900252 `18억·12억`, 900266 `5억·5억` 이 들어가고 000680 이 없다
  (가격 CSV 에서 `00680K` 행이 `000680` 키에 섞여 VCP 판정에서 빠짐). 00680K 는 두 코드 모두 외국인 순매도라 없다.
- 필수 여부(required): 예
- 실제:
- 결과:

### H-3. 종목코드 정규화의 입력별 결과 (`[FLOW-028]`, CLI)
- 조작: `qa_cli.py <사본> <빈 디렉터리> ticker`.
- 기대: 새 코드 `00680K`→`00680K`, `45226K`→`45226K`, `0220WL`→`0220WL`. 수정 전 코드는 차례로 `000680`·`045226`·`000220`. `0007C0`·`005930`·`A005930`·
  `005930.KS`·`5930` 은 두 코드 모두 `0007C0`·`005930`, `20260211` 은 빈 문자열.
- 필수 여부(required): 예
- 실제:
- 결과:

## 이월한 발견

- 끝쪽 부분 날짜가 이어지는 경우의 한계 → 코드 주석과 이 문서의 알려진 동작 변화(두 리뷰)
- pykrx 참조 캐시가 거부 값과 옛 NaN→0 값을 남김 → `[FLOW-029]`
- Naver 상세 캐시가 영문자 코드를 저장하지 않음 → `[JONGGA-043]`

## 실행 결과

- 필수 시나리오:
- 미통과 필수:
- 재개 판정:
- 시나리오 밖에서 새로 발견:
