# [JONGGA-042] 상세 API 의 Naver·기본값 폴백이 결측 수급을 0 으로 채우던 결함 — QA 시나리오

- 대상 화면: http://localhost:3742/dashboard/kr/closing-bet (격리 Next dev) → 카드의 「상세 분석 보기」 모달의 「투자자 동향」 절
- 구성 근거: 설계 승인(대화 2026-09-26, TODO [JONGGA-042] 절). 호출 경로: 카드 클릭 → `fetch('/api/kr/stock-detail/<code>')`
  → Flask `fetch_stock_detail_payload` → `TossCollector.get_full_stock_detail` 실패 → `load_naver_stock_detail_payload`
  → `NaverFinanceCollector.get_stock_detail_info` → `_create_empty_result_dict` → `_get_investor_trend`(통합 5일 서비스)
  → Naver 가 None 이면 `build_default_stock_detail_payload` → 모달 `mapTossDataToDetail`(priceInfo 형태는 그대로) → `FlowAmount`
- 구성 2026-09-26(설계 승인 뒤, 첫 커밋 전) | 실행: 아래 「결과」 줄
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 사본은 그 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`(`~/.claude/skills/gstack/browse/dist/browse`)
- browser_applicability: required. 사용자가 보는 것은 모달의 글자다. browser_driver: gstack `browse`
- 격리: 첫 커밋의 `git archive` 를 scratchpad `qa-j042/` 에 풀고 `frontend/node_modules` 는 APFS clone. 사본에서 `secrets/`·`data/`·`.env*` 를 지운 뒤
  `data/` 를 새로 만들어 QA 고정 자료 `jongga_v2_latest.json`(세 종목) 하나만 둔다. 원본 3500/5501·live 주소·원본 `data/`·`.env` 는 쓰지 않는다
- 대역(QA 전용 진입점 `qa_j042_app.py`, 사본에만 둔다):
  - `TossCollector.get_full_stock_detail` 이 예외를 던진다(Toss 장애 → Naver 폴백)
  - `NaverRequestMixin._request` 는 `item/main.naver?code=900001|900002` 에 고정 HTML(종목명·시장·현재가)을 돌려주고, 900003 과 그 밖의 URL 에는 None 을 돌려준다
  - `NaverPykrxMixin._get_fundamental_data` 는 아무것도 하지 않는다(pykrx·KRX 에 닿지 않게)
  - 통합 5일 서비스의 `_resolve_pykrx_latest_market_date`·`_fetch_pykrx_reference_trend`·`_fetch_toss_reference_trend` 는 None. 900002 만
    `naver_pykrx_mixin.get_investor_trend_5day_for_ticker` 가 고정 값 `{foreign: 500000000, institution: -300000000}` 을 돌려주고, 나머지는 실제 통합 서비스를 부른다
  - loopback 이 아닌 소켓 연결은 모두 막는다. LLM·발송 경로는 부르지 않는다
- 기동: Flask `SCHEDULER_ENABLED=false KRX_ID= KRX_PW= gunicorn qa_j042_app:app --bind 127.0.0.1:5742 --workers 1 --threads 4 --keep-alive 0`,
  Next `PORT=3742 API_URL=http://127.0.0.1:5742 TZ=Asia/Seoul npm run dev`(더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`NEXTAUTH_URL`)
- 단계(phase): 시나리오 구성 완료
- 반복(iteration): 0회
- baseline 상태: 수정 전 동작은 pytest 회귀 테스트가 실패로 확인했다(`test_naver_pykrx_investor_trend_keeps_missing_when_unified_has_no_value[none|error]`,
  `test_default_stock_detail_payload_leaves_flow_missing` 3건 RED, `assert 0 is None`)
- 필수 여부(required): S-1~S-3 예
- 결과:
- 증거:
- 정리(cleanup):
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`

| 종목 | 경로 | 통합 5일 | 모달 기대 |
|---|---|---|---|
| 900001 QA네이버결측 | Toss 실패 → Naver(고정 HTML) | 실제 서비스, 빈 `data/`·참조 None → None | 외국인·기관 「자료 없음」 |
| 900002 QA네이버정상 | Toss 실패 → Naver(고정 HTML) | 고정 값 5억·-3억 | 외국인 「+5억」, 기관 「-3억」, 일수 표시 없음 |
| 900003 QA기본값 | Toss 실패 → Naver 요청 None → 기본 페이로드 | 호출 안 함 | 외국인·기관 「자료 없음」 |

## 시나리오

### S-1. Naver 경로에서 통합 5일 값이 없으면 「자료 없음」을 그린다 (회귀)
- 조작: `curl` 로 `/api/kr/stock-detail/900001` 을 받아 `name`·`investorTrend`·`investorTrend5Day` 를 읽는다. 브라우저에서 해당 카드의 「상세 분석 보기」를 눌러 외국인·기관 칸의 글자를 읽는다.
- 기대: API 는 `name` 「QA네이버결측」(Naver 경로 증거), `investorTrend.foreign`·`institution` null, `investorTrend5Day` 키 없음. 화면은 외국인·기관 모두 「자료 없음」이고 「-」가 아니다.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 기본값 경로에서도 「자료 없음」을 그린다 (회귀)
- 조작: 900003 에 같은 조작을 한다.
- 기대: API 는 `message` 가 기본 데이터 안내, `name` 「종목 900003」, `investorTrend.foreign`·`institution` null. 화면은 외국인·기관 모두 「자료 없음」.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 통합 5일 값이 있으면 기존처럼 금액을 그린다 (인접)
- 조작: 900002 에 같은 조작을 한다. 세 모달을 연 뒤 `console --errors` 와 Flask 로그의 error·traceback 을 읽는다.
- 기대: API 는 `investorTrend.foreign` 500000000·`institution` -300000000. 화면은 외국인 「+5억」, 기관 「-3억」이고 「일)」 글자가 없다. 이번 변경에서 나온 콘솔·런타임 오류 없음.
- 필수 여부(required): 예
- 실제:
- 결과:
