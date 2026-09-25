# [INFRA-105] Market Gate 섹터 ETF 등락률 조회 실패가 0.0 으로 저장되어 섹터 급락 감점이 희석되는 문제 — QA 기록

- 대상: `engine/market_gate_fetchers_external.py` 의 `get_sector_data`(실패·빈 결과·한 줄 결과를 `None` 으로), `engine/market_gate_logic_scoring.py` 의 `build_sector_signals`(`None` 은 `Neutral`), `frontend/src/app/dashboard/kr/page.tsx` 섹터 카드(null 은 `—`), `frontend/src/lib/api.ts` 타입
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 구성 2026-09-25 10:05
- 검증 기준 커밋: 이 문서를 담은 첫 커밋. 대조는 수정 전 커밋 `adecec69`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 09:57). 호출 경로는 스케줄러·관리자 POST → `MarketGate.analyze` → `analyze_market_state` → `_get_sector_data`(pykrx) → `_calculate_sector_crash_penalty`·`build_sector_signals` → `save_analysis`(`market_gate.json`) → `GET /api/kr/market-gate` → 대시보드 `/dashboard/kr` 섹터 카드, 챗봇 `collect_market_context`
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자 진입 흐름은 대시보드의 섹터 카드이며 이번 변경이 그 응답 값(null)과 렌더를 바꾼다. 분석 생성은 관리자 POST(되돌릴 수 없는 갱신이며 실제 pykrx·외부 조회를 부름) 대신 사본 모듈을 직접 부르는 서비스 하네스로 만든다
- 격리: `[INFRA-104]` 와 같다. 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`(58101), 사본 Next dev(58102)는 `API_URL` 을 사본 Flask 로 둔다. 더미 비밀만 환경 변수로 준다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 하네스는 `pykrx` 를 가짜 모듈로 바꾸고 `socket` 연결을 막는다. 지수·환율·벤치마크 조회는 인스턴스 메서드를 고정값으로 바꾼다. 가격은 사본 `data/daily_prices.csv` 에 만든 합성 069500 행이다
- 금지: Market Gate 갱신 POST, Refresh, AI 재분석, 챗봇 전송, 설정 저장, 모의 매수, 메시지 발송
- 필수 여부(required): S-1~S-4 예
- 실행: 세션 스크래치의 `infra105qa_harness.py`(S-1·S-3, 사본 루트에서)와 `infra105qa_run.sh <사본> <표식>`(S-2·S-4, agent-browser `--namespace infra105qa`), 두 사본을 차례로

## 시나리오

### S-1. 섹터 11개 중 5개만 -3% 로 조회되고 6개가 실패한다 (서비스 하네스, 필수)
- 조작: 사본의 실제 `MarketGate.analyze()` 와 `save_analysis()` 를 부른다. 가짜 pykrx 는 반도체·2차전지·자동차·헬스케어·IT 에 등락률 -3.0 을 주고 나머지 6개(KOSPI 200 포함)는 예외를 낸다. 지수 없음
- 기대: 수정 뒤 `error` 없음, `sector_penalty` 30, 실패 6개의 `change_pct` 는 `null`·`signal` `Neutral` 로 `market_gate.json` 에 저장. 수정 전은 실패 6개가 `0.0` 이고 `sector_penalty` 0(평균 -1.36%·하락 비율 0.45, 결함 재현)
- 실제:

### S-2. 대시보드 섹터 카드가 결측을 `—` 로 보인다 (브라우저, 필수)
- 조작: S-1 이 만든 사본 `market_gate.json` 을 사본 Flask 가 읽게 두고 `/dashboard/kr` 를 연다
- 기대: 수정 뒤 API `sectors` 의 결측 6개가 `null`, 카드 6개는 `—`(회색), 5개는 `-3.00%`, 페이지 오류 0·「Application error」 0·`+0.00%` 0. 수정 전은 결측 6개가 `+0.00%` 로 보인다(결함 재현)
- 실제:

### S-3. 챗봇 문맥이 결측 섹터를 0 으로 싣지 않는다 (서비스 하네스, 필수)
- 조작: 저장된 `market_gate.json` 을 `chatbot.payload_service.collect_market_context` 에 넣는다(LLM 호출·전송 없음)
- 기대: 수정 뒤 `sector_scores` 는 조회된 5개만 -3.0 으로 담는다. 수정 전은 11개 모두 담고 6개가 0.0 이다
- 실제:

### S-4. 이 QA 가 자료를 바꾸지 않고 외부에 닿지 않는다 (필수)
- 기대: 하네스의 네트워크 차단이 걸린 채로 끝남, 화면 조회 전후 사본 `market_gate.json` 해시 같음, 사본 Flask 로그에 Market Gate 갱신·pykrx·KRX 로그인 줄 0, 원본 `data/` 수정 시각 불변
- 실제:

## 정리
- 실제:
