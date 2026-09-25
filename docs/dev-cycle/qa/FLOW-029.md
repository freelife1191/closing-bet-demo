# [FLOW-029]·[JONGGA-043] 수급 참조 캐시의 끝 날짜·거부 값·버전과 Naver 상세 캐시의 영문자 코드 — QA 시나리오

- 대상: 두 항목을 한 라운드로 묶은 T3(`docs/dev-cycle/TODO.md` 의 `[FLOW-029]` 「설계 승인」 줄, 2026-09-25 23:26)
- 대상 화면: http://localhost:3755/dashboard/kr/closing-bet (격리 Next dev) → 카드의 「상세 분석 보기」 모달의 「투자자 동향」 절
- 구성 근거: 호출 경로 카드 클릭 → `/api/kr/stock-detail/<code>` → `fetch_stock_detail_payload` → Toss 상세가 있으면
  `append_investor_trend_5day` → `get_investor_trend_5day_for_ticker(verify_with_references=True)` → CSV 에 없으면(`missing_csv`)
  `_get_reference_trend_cached(pykrx)` → 거부되면 Toss 참조. 기준일 없는 최신 창이라 pykrx 끝 날짜는 `_resolve_pykrx_latest_market_date`
  의 값이다. Toss 상세가 없으면 `load_naver_stock_detail_payload` → `NaverFinanceCollector.get_stock_detail_info`(`[JONGGA-043]`).
  사용자 진입 흐름이 이 모달이므로 브라우저 실측이 필수다
- 브라우저가 닿지 않는 흐름: 종가베팅 점수의 `KRXCollector.get_supply_data`(17시 체인, 기준일 실행, 뒤에 LLM 이 이어짐)와 워커 재기동·배포 뒤의
  SQLite 재사용은 화면에서 가를 수 없어 CLI 하네스로 검사한다(H-1~H-4). Naver 캐시 재사용은 서비스의 15분 상세 캐시가 앞에 있어 화면으로
  차이가 드러나지 않는다(계획 검토 Info-1). 화면은 모달이 그려지는지만 보고 재사용은 H-4 와 사본의 캐시 행으로 확인한다
- 검증 기준 커밋: 새 코드는 이 문서를 담은 첫 커밋, 대조용 수정 전 코드는 `13dac910`(첫 커밋의 부모). 사본은 각 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`. `[FLOW-025]` 와 같은 방식으로 시나리오를 직접 구성하고 `/qa-only`·`/qa` 스킬 본체의
  전체 앱 탐색은 하지 않는다
- browser_applicability: required(S-1~S-3). browser_driver: gstack `browse`(새 코드만). 수정 전 코드는 API 응답과 캐시 행만 대조한다
- 격리: 각 커밋의 `git archive` 를 scratchpad `flow029/qa/new/`·`flow029/qa/old/` 에 풀고 `secrets/`·`data/`·`.env*` 를 지운 뒤 사본마다 `data/` 에
  고정 자료(생성기 `flow029/qa/make_fixture.py`)만 둔다. CLI 하네스는 실행마다 새 자료 디렉터리를 쓴다(H-1~H-3 은 두 단계가 한 디렉터리를 공유).
  원본 3500/5501·live 주소·원본 `data/`·`.env` 는 쓰지 않는다
- 대역: Flask 는 QA 전용 진입점 `flow029/qa/qa_flow029_app.py`(사본에만 복사), CLI 는 `flow029/qa/qa_cli.py`. 둘 다 loopback 이 아닌 소켓 연결을 막아
  `QA-BLOCKED` 로 남기고 `sys.modules` 에 가짜 `pykrx` 를 넣는다. 가짜 지수(`get_index_ohlcv_by_date`)는 09-25 로 끝나 최근 거래일이 실행 시각과 무관하게
  2026-09-25 다. Flask 진입점은 `TossCollector._safe_request` 를 900271 의 종목 정보·투자자 동향만 응답하게, `NaverFinanceCollector._request` 를
  00680K 의 main 페이지만 응답하게 바꾼다. LLM·발송 경로는 부르지 않는다. 기동 환경에 `KRX_ID=`·`KRX_PW=` 빈 값
- 구성 2026-09-25(첫 커밋 `cea9cb05` 전) | 실행 2026-09-26 00:03:54(서버 기동)~00:06:20(마지막 API 대조), 정리 확인 00:07:20
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회(브라우저 실측 1차는 고정 자료 문제로 카드가 그려지지 않아 자료를 고쳐 다시 돌렸다. 아래 「실행 중 고친 것」)
- baseline 상태: 수정 전 코드 사본에 같은 고정 자료로 같은 API·하네스를 돌려 대조한다. 회귀 검사는 수정 전에 실패했다(TODO `[FLOW-029]` 의 RED 기록)
- 필수 여부(required): S-1~S-3, H-1~H-4 예
- 결과: 통과 (필수 7/7)
- 증거: 각 시나리오의 「실제」 줄. 모두 scratchpad `flow029/qa/` 아래에 있다. API 응답 `qa-api.txt`(00:06:20, 원문 `raw-<포트>-<종목>.json`, 캐시 행과 로그 집계 포함),
  모달 글자·콘솔·네트워크 `qa-browser.txt`(스크립트 `browse_run.sh`), 스크린샷 `flow029-QA전날끝-modal.png`·`flow029-QA우선네이버-modal.png`(열어 확인), CLI 출력 `qa-cli.txt`,
  격리 로그 `qa-new-flask.log`·`qa-old-flask.log`·`qa-new-next.log`. CLI 의 `QA-CODE` 줄과 로그의 `QA-PYKRX`·`QA-TOSS`·`QA-NAVER` 줄로 각 사본이 대역과 자기 코드를 거쳤음을 확인했다
- 실행 중 고친 것: 1차 브라우저 실측(00:04:47)에서 두 카드가 D 로 재분류되어 「표시할 수 있는 종목이 없습니다」가 떴다. 카드 JSON 에 저장된 수급 값이 없어
  `_recalculate_jongga_grades` 가 D 를 준 것이다(사본에서 `score_details` 를 비운 경우 D·D, 외국인·기관 50억을 넣은 경우 B·B 로 재현). 생성기의 카드에
  `score_details` 외국인·기관 50억을 넣고 두 사본의 JSON 만 바꿨다. 모달의 투자자 동향은 상세 API 에서 오므로 이 값과 무관하다. 그 사이 상세 요청은 0건이었다
  (로그 `QA-`·`stock-detail` 0줄, 사본 캐시 DB 없음). CLI `naver` 모드가 사본 `data/` 에 남긴 Naver 캐시는 S-2 전에 지웠다
- 정리(cleanup): browse 서버 정지(「Server stopped」). 격리 Next(3755)는 곧 내려갔으나 gunicorn(5755·5756)은 첫 `kill` 이 zsh 에서 PID 두 개를 한 인자로 넘겨 실패했고,
  PID·작업 디렉터리(사본)를 확인한 뒤 마스터를 다시 종료했다. 00:07:16 에 3755/5755/5756/3500/5501 리스너 0, 00:07:20 에 QA 프로세스 0. 사본 `new/`·`old/` 와
  CLI 자료 디렉터리를 리터럴 절대 경로로 삭제했다. 원본 `data/` 에서 기동 전 표식 이후 바뀐 파일 0, 저장소 루트 `node_modules/.vite` 없음, `git status` 는 깨끗했다(이 기록 전).
  원본 3500/5501 은 처음부터 떠 있지 않았다
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`. frontend 변경이 없어 Next 번들 문서는 읽지 않았다

## 고정 자료

- 수급 CSV: 900264(09-15~09-23, 하루 2억·3억) 한 종목만 둔다. S-1·S-2·H 의 대상 종목은 CSV 에 없어(`missing_csv`) 참조로 간다
- 카드: 900271 QA전날끝(Toss 경로), 00680K QA우선네이버(Toss 종목 정보 없음 → Naver 경로). 두 카드 모두 `score_details` 에 외국인·기관 50억(D 재분류 방지, 실행 중 추가)
- Flask 가짜 pykrx 거래대금: 900271 은 09-18·09-21·09-22·09-23·09-24(최근 거래일 09-25 의 전날로 끝남), 하루 외국인 1억·기관 2억. 그 밖은 빈 프레임
- Flask 가짜 Toss 투자자 동향(900271): 09-17~09-23 다섯 날, 종가 10,000, 외국인 −20,000주·기관 −40,000주 → 5일 합 외국인 −10억·기관 −20억

CLI 하네스 가짜 pykrx(기준일 2026-09-25, 1억 = 100,000,000). 단계 A 와 B 는 같은 자료 디렉터리를 쓰는 별개 프로세스다(워커 재기동·배포 흉내).

| 종목 | 단계 A 프레임 | 단계 B 프레임 |
|---|---|---|
| 900281 | 09-18~09-24(전날로 끝남), 하루 1억·1억 | 09-19~09-25, 하루 2억·2억 |
| 900282 | 09-19~09-25, 외국인 하루가 NaN(나머지 3억), 기관 3억 | 09-19~09-25, 하루 3억·3억 |

## 시나리오

### S-1 [FLOW-029] 최근 거래일 전날로 끝나는 pykrx 참조를 모달에 쓰지 않는다 (필수)
- 조작: 900271 QA전날끝 카드의 「상세 분석 보기」
- 기대(새 코드): 「투자자 동향」 외국인 「-10억」·기관 「-20억」(Toss 참조). API 응답 `investorTrend5Day` 가 −1,000,000,000·−2,000,000,000.
  사본의 `data/.investor_trend_reference_cache/pykrx/runtime_cache.db` 에 900271 행 없음, `.../toss/` 에 900271 행 있음(Toss 키는 달력상 실행 당일)
- 기대(수정 전, API): `investorTrend5Day` 500,000,000·1,000,000,000(09-24 로 끝나는 pykrx 5일), pykrx 캐시에 `900271__20260925` 행 있음
- 실제: 통과. 모달 「투자자 동향」 외국인 「-10억」·기관 「-20억」·개인 0(스크린샷). 새 코드 API `investorTrend5Day` {foreign −1,000,000,000, institution −2,000,000,000}.
  새 사본 pykrx 캐시에는 `latest_market_date__20260926` 행뿐이고 900271 행 없음, toss 캐시에 `900271__20260926`. 로그 `QA-PYKRX trading_value 900271` 1줄 뒤 `QA-TOSS trading-trend 900271` 이
  2줄(상세의 Toss 합계와 Toss 참조). 수정 전 API `investorTrend5Day` {500,000,000, 1,000,000,000}, pykrx 캐시에 `900271__20260925`(서명 593841111), toss 캐시 없음

### S-2 [JONGGA-043] 영문자 코드의 Naver 상세가 그려지고 캐시된다 (필수)
- 조작: 00680K QA우선네이버 카드의 「상세 분석 보기」
- 기대(새 코드): 모달 제목에 QA우선네이버, 코드 00680K. 로그 `QA-NAVER main 00680K` 1줄. 사본의
  `data/.naver_finance_cache/detail_info/runtime_cache.db` 에 `00680K__<슬롯>` 행 있음
- 기대(수정 전, API): 같은 이름·코드가 오지만 Naver 상세 캐시에 00680K 행 없음
- 실제: 통과. 모달 제목 QA우선네이버, 코드 00680K 표시, 투자자 동향은 값 없음(「-」·「자료없음」, Naver 경로는 대역이 main 페이지만 준다). 새 코드 로그 `QA-NAVER main 00680K` 1줄,
  새 사본 `detail_info` 캐시에 `00680K__202609260000` 행. 수정 전 API 도 name QA우선네이버·code 00680K 였고 로그 1줄, `detail_info` 캐시 DB 없음(행 0)

### S-3 콘솔·네트워크 (필수)
- 기대: S-1·S-2 동안 콘솔 오류 0, 상세 요청 둘 다 200, `QA-BLOCKED` 0줄
- 실제: 통과. `console --errors` 「no console errors」(00:06:08). 네트워크 `stock-detail/900271`·`stock-detail/00680K` 가 각각 2회 요청, 전부 200. 두 로그의 `QA-BLOCKED` 0줄,
  Traceback 0줄. 두 사본 모두 `QA-PYKRX unexpected get_market_fundamental_by_ticker` 2줄이 있는데, Naver 경로의 펀더멘털 조회가 대역에 없는 속성을 부른 것이며 수정 전 코드에도 같다(이번 변경 밖)

### H-1 [FLOW-029] 기준일 실행이 전날로 끝나는 pykrx 값을 기준일 키로 저장하지 않는다 (필수)
- 명령: `qa_cli.py <사본> <자료> supply A` 뒤 같은 자료로 `supply B`(새 코드끼리, 수정 전 코드끼리 각각)
- 기대(새 코드): 900281 단계 A `value=None pykrx_calls=1`, 단계 A 뒤 pykrx 캐시 행 없음, 단계 B `value=[1000000000, 1000000000] pykrx_calls=1`
- 기대(수정 전): 단계 A `value=[500000000, 500000000]`, 캐시 행 있음, 단계 B `value=[500000000, 500000000] pykrx_calls=0`
- 실제: 통과. 새 코드 단계 A `value=None pykrx_calls=1`, 단계 A 뒤 `QA-ROWS pykrx none`, 단계 B `value=[1000000000, 1000000000] pykrx_calls=1`.
  수정 전 단계 A `value=[500000000, 500000000]`, 행 `900281__20260925` 저장, 단계 B `value=[500000000, 500000000] pykrx_calls=0`

### H-2 [FLOW-029] 거부된 참조를 저장하지 않아 다음 워커가 다시 묻는다 (필수)
- 명령: H-1 과 같은 실행(900282)
- 기대(새 코드): 단계 A `value=None`, 캐시 행 없음, 단계 B `value=[1500000000, 1500000000] pykrx_calls=1`
- 기대(수정 전): 단계 A `value=None`, NaN 인 날이 든 행 저장, 단계 B `value=None pykrx_calls=0`(`/review` M2 재현)
- 실제: 통과. 새 코드 단계 A `value=None`, 행 없음, 단계 B `value=[1500000000, 1500000000] pykrx_calls=1`. 수정 전 단계 A `value=None` 에 행 `900282__20260925` 저장
  (details 외국인 셋째 날 None, foreign 1,200,000,000), 단계 B `value=None pykrx_calls=0`

### H-3 [FLOW-029] 배포 전 v1 행을 새 코드가 읽지 않는다 (필수)
- 명령: 수정 전 사본으로 `supply A` 를 돌린 자료 디렉터리에 새 사본으로 `supply B`
- 기대: 900281 `value=[1000000000, 1000000000] pykrx_calls=1`, 900282 `value=[1500000000, 1500000000] pykrx_calls=1`. 같은 키의 행이 v2 서명으로 덮어써진다
- 실제: 통과. 수정 전 단계 A 가 서명 (20260925, 593841111)으로 두 행을 남긴 자료에서 새 코드 단계 B 가 900281 `value=[1000000000, 1000000000] pykrx_calls=1`,
  900282 `value=[1500000000, 1500000000] pykrx_calls=1`. 두 행 모두 같은 키에서 서명 (20260925, 1120597247)로 덮어써졌다

### H-4 [JONGGA-043] Naver 상세를 메모리 캐시를 비운 뒤 다시 조회해도 스크랩하지 않는다 (필수)
- 명령: `qa_cli.py <사본> <자료> naver`
- 기대(새 코드): `get_stock_detail_info("00680K")` 두 번(사이에 메모리 캐시 비움), `requests=1`, 두 결과의 code 00680K.
  비교용 `005930` 도 `requests=1`
- 기대(수정 전): 00680K `requests=2`, 005930 `requests=1`
- 실제: 통과. 새 코드 00680K `requests=1 codes=['00680K', '00680K']`, 005930 `requests=1`, 캐시 행 `00680K__202609260000`·`005930__202609260000`.
  수정 전 00680K `requests=2`, 005930 `requests=1`, 캐시 행은 005930 하나

## 알려진 동작 변화와 비용(검사 대상 아님)

- 끝 날짜가 휴장일이면 pykrx 참조를 늘 거부하고 60초마다 다시 묻는다(계획 「알려진 한계」 Minor-2). 늘 거부되는 참조(전부 0 인 거래정지 종목 등)도
  하루 한 번이 아니라 60초 간격으로 다시 조회한다(Minor-3). 버린 참조의 사유는 조회한 호출의 `quality.discarded_references` 에만 남는다(Minor-1)
- 기준일 실행이 pykrx 를 못 쓰면 CSV 폴백이 전날 끝 5거래일을 쓸 수 있다. 이 라운드는 그것을 막지 않는다(`[FLOW-031]`)
