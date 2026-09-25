# [FLOW-023] 수급 CSV 와 pykrx 참조의 빈 값을 결측으로 읽기 — QA 시나리오

- 대상 화면: http://localhost:3753/dashboard/kr/closing-bet (격리 Next dev) → 카드의 「상세 분석 보기」 모달의 「투자자 동향」 절
- 구성 근거: 설계 승인(대화 2026-09-25 19:49, TODO [FLOW-023] 절). 호출 경로: 카드 클릭 → `fetch('/api/kr/stock-detail/<code>')`
  → Flask 라우트(`app/routes/kr_market_data_backtest_stock_routes.py`, 이번에 `load_csv_file=` 인자를 뺐다) → `fetch_stock_detail_payload`
  → `append_investor_trend_5day` → `get_investor_trend_5day_for_ticker(verify_with_references=True)` → `_build_trend_map`(변경 (1))
  → `_resolve_best_payload`(변경 (3)) → pykrx 참조 `_fetch_pykrx_reference_trend`(변경 (4)) → Toss 참조. 값이 있으면 응답에
  `investorTrend5Day` 가 들어가고 모달은 그 값을 일수 표시 없이 그린다. 없으면 키가 빠지고(변경 (2), 레거시 CSV 경로 삭제) 모달이
  `[FE-048]` 의 Toss 합계로 물러서며 Toss 일수가 5 보다 적으면 「(N일)」을 붙인다. 사용자 진입 흐름이 이 모달이므로 브라우저 실측이 필수다
- 구성 2026-09-25(첫 커밋 `930525be` 뒤) | 실행 2026-09-25 21:05:54(서버 기동)~21:07:22, 정리 확인 21:07:58
- 검증 기준 커밋: 새 코드 `930525be`, 대조용 수정 전 코드 `dfb508fd`(`930525be` 의 부모). 사본은 각 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`(`~/.claude/skills/gstack/browse/dist/browse`). `[FLOW-022]` 와 같은 방식으로
  시나리오를 직접 구성했고 `/qa-only`·`/qa` 스킬 본체는 부르지 않았다(두 스킬의 전체 앱 탐색 대신 이 문서의 시나리오만 실행한다)
- browser_applicability: required. 사용자가 보는 것은 모달의 글자다. browser_driver: gstack `browse`(새 코드만). 수정 전 코드는 API 응답만 대조한다
- 격리: 각 커밋의 `git archive` 를 scratchpad `flow023/qa-new/`·`flow023/qa-old/` 에 풀고, 새 코드 사본의 `frontend/node_modules` 는 APFS clone.
  사본에서 `secrets/`·`data/`·`.env*` 를 지운 뒤 `data/` 를 새로 만들어 QA 고정 자료 두 개만 둔다: `jongga_v2_latest.json`(신호일 2026-09-24, 네 종목),
  `all_institutional_trend_data.csv`(아래 표). 원본 3500/5501·live 주소·원본 `data/`·`.env` 는 쓰지 않는다
- 대역(QA 전용 진입점 `qa_flow023_app.py`, 사본에만 둔다): `TossCollector._safe_request` 를 URL 별 고정 응답으로 바꾼다(종목 정보·투자자 동향만 응답,
  나머지 None). `sys.modules` 에 가짜 `pykrx` 를 넣어 `stock.get_market_trading_value_by_date` 는 아래 표의 프레임을, `get_index_ohlcv_by_date` 는 빈 프레임을
  돌려주고 그 밖의 속성은 실패하게 한다. 실제 `_fetch_pykrx_reference_trend` 가 이 프레임을 읽으므로 변경 (4) 를 그대로 지난다. loopback 이 아닌 소켓 연결은
  모두 막고 로그에 `QA-BLOCKED` 로 남긴다. LLM·발송 경로는 부르지 않는다. 기동 환경에 `KRX_ID=`·`KRX_PW=` 를 빈 값으로 준다
- 기동: 새 코드 Flask `SCHEDULER_ENABLED=false KRX_ID= KRX_PW= gunicorn qa_flow023_app:app --bind 127.0.0.1:5753 --workers 1 --threads 4 --keep-alive 0`,
  Next `PORT=3753 API_URL=http://127.0.0.1:5753 TZ=Asia/Seoul npm run dev`(더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`NEXTAUTH_URL`).
  수정 전 코드 Flask 는 같은 명령으로 `127.0.0.1:5754`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 수정 전 코드 사본(5754)에 같은 고정 자료로 같은 API 를 불러 대조한다. pytest 회귀 검사도 수정 전에 실패했다(TODO Task 1·2 의 RED)
- 필수 여부(required): S-1~S-4 예
- 결과: 통과 (필수 4/4)
- 증거: 각 시나리오의 「실제」 줄. API 응답 scratchpad `flow023/qa-api.txt`(21:06:09, 원문 `flow023/raw-<포트>-<종목>.json`), 모달 글자·콘솔·네트워크·MCP·로그 집계
  `flow023/qa-browser.txt`, 스크린샷 `flow023/flow023-QA세줄-flow.png`·`flow023-QA낡은CSV-flow.png`(열어 확인)와 `flow023-QA빈칸-flow.png`·`flow023-QA정상-flow.png`,
  격리 로그 `flow023/qa-new-flask.log`·`qa-old-flask.log`·`qa-new-next.log`. 로그의 `QA-PYKRX`·`QA-TOSS` 줄로 각 사본이 대역을 거쳤음을 확인했다
- 정리(cleanup): browse 서버 정지(「Server stopped」), 격리 gunicorn(5753·5754)·Next(3753) 종료 뒤 21:07:44 에 3753/5753/5754/3500/5501 리스너 0, 사본 경로 프로세스 0,
  사본 `flow023/qa-new/`·`flow023/qa-old/` 삭제, 원본 `data/` 에서 기동 전 표식 이후 바뀐 파일 0, 저장소 루트 `node_modules/.vite` 없음, `git status` 는 이 문서 한 개만 추가.
  원본 3500/5501 은 처음부터 떠 있지 않았다
- 실행 중 절차 이탈 1건: 사본을 만드는 첫 명령에서 zsh 가 `set -- $pair` 를 단어로 나누지 않아 `git archive` 가 인자 오류로 멈추고 이름에 공백이 든
  디렉터리 둘(`qa-new 930525be`·`qa-old dfb508fd`, 고정 자료만 들어 있음)이 생겼다. 서버 기동 전에 발견해 그 두 경로를 지우고 함수로 다시 만들었다. 원본에는 닿지 않았다
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`. frontend 변경이 없어 Next 번들 문서는 읽지 않았다

고정 자료와 판정 경로는 다음과 같다. CSV 값은 원 단위다. Toss 투자자 동향의 종가는 모두 10,000 이며 합계는 수량×종가다.
pykrx 「NaN 프레임」은 2026-09-18~24 다섯 행으로, 외국인합계 [3억, 3억, 3억, NaN, 3억], 기관합계 5천만×5 다.

| 종목 | CSV | pykrx | Toss 투자자 동향 | 새 코드 판정 | 새 코드 모달 기대 | 수정 전 코드 기대 |
|---|---|---|---|---|---|---|
| 900231 QA세줄 | 09-22~24 세 행, 외국인 1억·기관 -1억 | 빈 프레임 | 세 행, 외국인 2만주·기관 1만주 | 행 부족으로 map 에 없음 → pykrx 없음 → Toss `insufficient_days` → None → 키 없음 | 외국인 「+6억(3일)」, 기관 「+3억(3일)」 | 레거시 CSV 경로가 세 행 합 `{300000000, -300000000}` 를 넣음 |
| 900232 QA낡은CSV | 08-24~28 다섯 행, 외국인 1억·기관 -6천만(`stale_csv`) | NaN 프레임 | 다섯 행, 외국인 [1만, 2만, 빈, 3만, 4만]·기관 4천주 | pykrx 하루 None → 버림, Toss 하루 None → 버림, 참조 없음 + `stale_csv` → None → 키 없음 | 외국인 「+10억(4일)」, 기관 「+2억」 | pykrx NaN 을 0 으로 읽어 채택 `{1200000000, 250000000}` |
| 900233 QA빈칸 | 09-18~24 다섯 행, 09-23 외국인 빈 칸, 기관 -6천만 | NaN 프레임 | 다섯 행, 외국인 5만주·기관 -2천주 | 빈 칸 행을 건너뛰어 map 에 없음 → pykrx 버림 → Toss 채택 → 키 있음 | 외국인 「+25억」, 기관 「-1억」, 「일)」 없음 | 빈 칸을 0 으로 읽어 플래그 없는 CSV `{400000000, -300000000}` |
| 900234 QA정상 | 09-18~24 다섯 행, 외국인 2억·기관 4천만 | 7억×5(조회되면 안 됨) | 다섯 행, 외국인·기관 -1만주 | 플래그 없음 → 참조 조회 없이 CSV | 외국인 「+10억」, 기관 「+2억」, 「일)」 없음 | 같음 `{1000000000, 200000000}` |

한 종목의 결과가 어느 갈래에서 나왔는지는 값으로 가른다. 예를 들어 900232 가 +5억·-3억이면 변경 (3) 이, +12억·+2.5억이면 변경 (4) 가 빠진 것이다.
900233 이 +4억·-3억이면 변경 (1) 이, +12억·+2.5억이면 변경 (4) 가 빠진 것이다. 900234 는 이번 변경이 정상 종목을 건드리지 않았다는 인접 확인이며, Flask 로그의
`QA-PYKRX trading_value 900234` 줄이 0 이어야 한다.

알려진 한계(리뷰 기록, 조치 없음):
- (closing-bet-reviewer F9) 참조 조회가 일시적으로 실패해 통합 서비스가 None 을 주면, 키가 빠진 상세 페이로드가 상세 API 캐시(메모리·SQLite, 15분 슬롯)에 남아
  그 슬롯 동안 모달이 Toss 합계로 물러선다. 종전에는 같은 경우 레거시 CSV 합계가 캐시되었다. 표시가 결측 쪽으로 기우는 방향이라 조치하지 않았다
- (closing-bet-reviewer F2) 스크리너의 Toss 실패 대체 경로(`engine/screener.py:367`)도 변경 (3) 으로 낡은 CSV 대신 MISSING_SUPPLY 가 된다. 의도한 동작이며
  화면에서 부를 수 없고 신호 생성은 외부 조회·LLM 이라 이 문서의 시나리오에 넣지 않았다
- (critic (1)) 과거 기준일 pykrx 참조 캐시는 날짜 토큰이라 만료되지 않아, 수정 전에 NaN 을 0 으로 저장한 참조가 계속 채택될 수 있다. 빈도를 확인하지 않았다
- 수급 CSV 작성부가 빈 값인 날을 행 누락으로 남기는 문제는 `[FLOW-025]`, 수집기 믹스인의 자체 pykrx 폴백은 `[FLOW-026]` 으로 이월했다

## 시나리오

### S-1. 1~4행 종목은 k일 합계를 5일 값으로 내보내지 않는다 (회귀, 변경 (1)(2))
- 조작: `curl` 로 새 코드(5753)와 수정 전 코드(5754)의 `/api/kr/stock-detail/900231` 을 받아 `investorTrend`·`investorTrend5Day` 를 읽는다. 브라우저에서
  QA세줄 카드의 「상세 분석 보기」를 눌러 외국인·기관 칸의 글자를 읽는다.
- 기대: 새 코드 API 는 `investorTrend5Day` 키 없음, `investorTrend.foreign` 600000000·`foreignDays` 3, `institution` 300000000·`institutionDays` 3.
  화면은 외국인 「+6억(3일)」, 기관 「+3억(3일)」. 수정 전 코드 API 는 `investorTrend5Day` `{foreign: 300000000, institution: -300000000}`.
- 필수 여부(required): 예
- 실제: 새 코드 API `investorTrend5Day` 없음, `foreign` 600000000.0·`foreignDays` 3, `institution` 300000000.0·`institutionDays` 3. 모달 칸 「외국인+6억(3일)」「기관+3억(3일)」.
  스크린샷 `flow023-QA세줄-flow.png` 에서 붉은 「+6억」「+3억」 옆에 작은 회색 「(3일)」이 보였다. 개인 칸은 「자료 없음」이었다(개인 값은 이번 범위 밖이며 수정 전 코드와 같은 Toss 응답이다).
  수정 전 코드 API `investorTrend5Day` `{foreign: 300000000, institution: -300000000}`(레거시 CSV 세 행 합)
- 결과: 통과

### S-2. 낡은 CSV 는 참조로 확인하지 못하면 표시하지 않고, pykrx 의 NaN 은 채택하지 않는다 (회귀, 변경 (3)(4))
- 조작: 900232 에 같은 조작을 한다. Flask 로그에서 `QA-PYKRX trading_value 900232`·`QA-TOSS trading-trend 900232` 줄을 확인한다.
- 기대: 새 코드 API 는 `investorTrend5Day` 키 없음, `investorTrend.foreign` 1000000000·`foreignDays` 4, `institution` 200000000·`institutionDays` 5.
  화면은 외국인 「+10억(4일)」, 기관 「+2억」(「일)」 없음). 로그에 pykrx·Toss 조회가 각각 있다. 수정 전 코드 API 는 `investorTrend5Day` `{foreign: 1200000000, institution: 250000000}`.
- 필수 여부(required): 예
- 실제: 새 코드 API `investorTrend5Day` 없음, `foreign` 1000000000.0·`foreignDays` 4, `institution` 200000000.0·`institutionDays` 5. 모달 「외국인+10억(4일)」「기관+2억」.
  스크린샷 `flow023-QA낡은CSV-flow.png` 에서 외국인만 회색 「(4일)」이 붙었다. 새 코드 로그에 `QA-PYKRX trading_value 900232` 1줄, `QA-TOSS trading-trend 900232` 2줄(상세 시세 1·참조 1).
  수정 전 코드 API `investorTrend5Day` `{foreign: 1200000000, institution: 250000000}`(pykrx NaN 을 0 으로 읽은 부분합). 수정 전 로그의 Toss 조회는 1줄로, pykrx 를 채택해 Toss 참조를 부르지 않았다
- 결과: 통과

### S-3. 빈 칸이 있는 CSV 는 0 으로 읽지 않고 참조로 넘어간다 (회귀, 변경 (1)(4))
- 조작: 900233 에 같은 조작을 한다.
- 기대: 새 코드 API 는 `investorTrend5Day` `{foreign: 2500000000, institution: -100000000}`, `foreignDays`·`institutionDays` 5. 화면은 외국인 「+25억」, 기관 「-1억」이고
  「일)」 글자가 없다. 수정 전 코드 API 는 `investorTrend5Day` `{foreign: 400000000, institution: -300000000}`.
- 필수 여부(required): 예
- 실제: 새 코드 API `investorTrend5Day` `{foreign: 2500000000, institution: -100000000}`, `foreignDays`·`institutionDays` 5. 모달 「외국인+25억」「기관-1억」, 「일)」 없음.
  새 코드 로그에 `QA-PYKRX trading_value 900233` 1줄(버려짐), `QA-TOSS trading-trend 900233` 2줄. 수정 전 코드 API `investorTrend5Day` `{foreign: 400000000, institution: -300000000}` 이고
  수정 전 로그에는 900233 pykrx 조회가 없다(빈 칸을 0 으로 읽어 플래그 없는 CSV 로 끝났다)
- 결과: 통과

### S-4. 정상 종목은 CSV 합계를 그대로 쓰고 참조를 조회하지 않는다 (인접, 라우트 시그니처 F10 포함)
- 조작: 900234 에 같은 조작을 한다. 네 모달을 연 뒤 `console --errors` 와 `/_next/mcp` `get_errors`·`get_compilation_issues` 를 읽고, `browse network` 의
  `stock-detail` 응답 코드와 Flask 로그의 error·traceback·`QA-BLOCKED`·`QA-PYKRX unexpected`·`QA-PYKRX trading_value 900234` 줄을 센다.
- 기대: 새 코드·수정 전 코드 API 모두 `investorTrend5Day` `{foreign: 1000000000, institution: 200000000}`. 화면은 외국인 「+10억」, 기관 「+2억」이고 「일)」 글자가 없다.
  `stock-detail` 요청은 모두 200(인자를 뺀 라우트가 서비스 시그니처와 맞는다), 콘솔·런타임·컴파일 오류 없음, Flask 로그의 세어 본 줄은 모두 0.
- 필수 여부(required): 예
- 실제: 새 코드·수정 전 코드 API 모두 `investorTrend5Day` `{foreign: 1000000000, institution: 200000000}`(Toss 는 -5억·-5억이라 CSV 값임을 가른다). 모달 「외국인+10억」「기관+2억」, 「일)」 없음.
  모달을 13회 연 뒤(네 종목 각 3회: 글자 읽기, 선택자 오류로 캡처하지 못한 순회, 캡처 순회. 선택자 확인에 900231 1회) browse `console --errors` 는 「(no console errors)」, `/_next/mcp` `get_errors` 는 `configErrors:[]`·`sessionErrors:[]`, `get_compilation_issues` 는 `issues:[]`.
  `browse network` 의 `stock-detail` 요청 26건(dev 모드에서 한 번 열 때 2건) 모두 200. Flask 로그(두 사본 각각) error 0·traceback 0·`QA-BLOCKED` 0·`QA-PYKRX trading_value 900234` 0.
  `QA-PYKRX unexpected` 는 기대(0)와 달리 두 사본 모두 1줄이다. 기동 확인에 쓴 `/api/kr/jongga-v2/latest` 가 21:05:56 에 `engine/market_schedule.py:180` 의
  `get_nearest_business_day_in_a_week` 를 부른 것으로, 첫 `stock-detail` 요청(21:06:09) 전이고 상세 API 경로가 아니다. 그 라우트는 200 을 돌려주었다.
  이 집계로 확인하려던 「상세 API 경로에서 가짜 pykrx 에 없는 함수를 부르지 않는다」는 충족되어 통과로 판정하고 기대 문구와의 차이를 여기에 남긴다
- 결과: 통과

## 이월한 발견

- 수급 CSV 작성부가 빈 값인 날을 행 누락으로 남기는 문제 → `[FLOW-025]`(closing-bet-reviewer F1, /review L1 관찰 포함)
- 수집기 믹스인의 자체 pykrx 폴백이 빈 값을 0·부분합으로 쓰는 문제 → `[FLOW-026]`(/review M2)
- 시그널 추적기 수급 점수의 NaN 건너뛴 합 → `[FLOW-024]`(critic (2))

## 실행 결과

- 필수 시나리오: 통과 4 / 전체 4. 수정 전 코드는 네 종목 중 세 종목에서 표의 수정 전 기대값을 냈고(900234 는 같음), 시나리오가 수정 전후를 가른다
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 없음(`QA-PYKRX unexpected` 1줄은 기존 `jongga-v2` 라우트가 가짜 pykrx 에 없는 함수를 부른 대역의 한계다)
