# [INFRA-105] Market Gate 섹터 ETF 등락률 조회 실패가 0.0 으로 저장되어 섹터 급락 감점이 희석되는 문제 — QA 기록

- 대상: `engine/market_gate_fetchers_external.py` 의 `get_sector_data`(실패·빈 결과·한 줄 결과를 `None` 으로), `engine/market_gate_logic_scoring.py` 의 `build_sector_signals`(`None` 은 `Neutral`), `frontend/src/app/dashboard/kr/page.tsx` 섹터 카드(null 은 `—`), `frontend/src/lib/api.ts` 타입
- 단계(phase): 완료 | 시나리오 구성 완료 | 실행 완료
- 구성 2026-09-25 10:05 | 실행 2026-09-25 10:10:45(S-1·S-3 수정 전), 10:10:46(S-1·S-3 수정 뒤), 10:13(S-2·S-4 수정 전), 10:14(S-2·S-4 수정 뒤)
- 검증 기준 커밋: `fe532dc2`(이 문서를 담은 첫 커밋). 대조는 수정 전 커밋 `adecec69`. 사본은 각 커밋의 `git archive` 다
- 구성 근거: 설계 승인(대화 09:57). 호출 경로는 스케줄러·관리자 POST → `MarketGate.analyze` → `analyze_market_state` → `_get_sector_data`(pykrx) → `_calculate_sector_crash_penalty`·`build_sector_signals` → `save_analysis`(`market_gate.json`) → `GET /api/kr/market-gate` → 대시보드 `/dashboard/kr` 섹터 카드, 챗봇 `collect_market_context`
- QA 엔진(engine): Claude Code. browser_applicability: required(browser_driver: agent-browser). 사용자 진입 흐름은 대시보드의 섹터 카드이며 이번 변경이 그 응답 값(null)과 렌더를 바꾼다. 분석 생성은 관리자 POST(되돌릴 수 없는 갱신이며 실제 pykrx·외부 조회를 부름) 대신 사본 모듈을 직접 부르는 서비스 하네스로 만든다
- 격리: `[INFRA-104]` 와 같다. 각 커밋의 `git archive` 사본에서 `secrets/`·`data/`·`.env` 를 지우고 빈 `data/` 를 만든다. 사본 Flask 는 gunicorn 1 worker·`SCHEDULER_ENABLED=false`(58101), 사본 Next dev(58102)는 `API_URL` 을 사본 Flask 로 둔다. 더미 비밀만 환경 변수로 준다. 원본 3500·5501·`data/`·`.env`·운영 주소는 쓰지 않는다
- 안전: 하네스는 `pykrx` 를 가짜 모듈로 바꾸고 `socket` 연결을 막는다. 지수·환율·벤치마크 조회는 인스턴스 메서드를 고정값으로 바꾼다. 가격은 사본 `data/daily_prices.csv` 에 만든 합성 069500 행이다
- 금지: Market Gate 갱신 POST, Refresh, AI 재분석, 챗봇 전송, 설정 저장, 모의 매수, 메시지 발송
- 필수 여부(required): S-1~S-4 예
- 실행: 세션 스크래치의 `infra105qa_harness.py`(S-1·S-3, 사본 루트에서)와 `infra105qa_run.sh <사본> <표식>`(S-2·S-4, agent-browser `--namespace infra105qa`), 두 사본을 차례로
- 반복(iteration): 1회. 사본 Next 첫 기동은 `frontend/node_modules` 를 저장소 쪽으로 심볼릭 링크해 Turbopack 이 「Symlink … points out of the filesystem root」 로 기동 전에 멈췄다(화면 조회 없음). 링크를 지우고 APFS 클론 복사(`cp -Rc`)로 바꿔 다시 띄웠다. 사본 `engine/market_gate_fetchers_external.py` 의 `INFRA-105` 표시는 수정 전 0건·수정 뒤 1건
- 결과: 통과 (필수 4/4)
- 증거: 아래 「실제」 줄(스크립트 출력 원문, scratchpad `qa-infra105-{old,new}-s1.txt`·`qa-infra105-{old,new}-run.txt`), 스크린샷 `infra105qa-new-s2.png`(열어 확인: 결측 6개 회색 `—` 카드, 5개 `-3.00%`, 점수 50 Neutral)·`infra105qa-old-s2.png`, 모든 실행 exit 0

## 시나리오

### S-1. 섹터 11개 중 5개만 -3% 로 조회되고 6개가 실패한다 (서비스 하네스, 필수)
- 조작: 사본의 실제 `MarketGate.analyze()` 와 `save_analysis()` 를 부른다. 가짜 pykrx 는 반도체·2차전지·자동차·헬스케어·IT 에 등락률 -3.0 을 주고 나머지 6개(KOSPI 200 포함)는 예외를 낸다. 지수 없음
- 기대: 수정 뒤 `error` 없음, `sector_penalty` 30, 실패 6개의 `change_pct` 는 `null`·`signal` `Neutral` 로 `market_gate.json` 에 저장. 수정 전은 실패 6개가 `0.0` 이고 `sector_penalty` 0(평균 -1.36%·하락 비율 0.45, 결함 재현)
- 실제: 수정 뒤(10:10:46) `error: None`, `tech_score` 80·`sector_penalty` 30·`market_drop_penalty` 30, `total_score` 50 「중립 (Neutral)」, 가짜 pykrx 호출 11, 저장된 `market_gate.json` 의 `change_pct` 는 `[-3.0 ×5, None ×6]`, 결측 6개 `signal` `Neutral`. 수정 전(10:10:45) 같은 입력에서 `sector_penalty` 0, `total_score` 80 「강세장 (Bullish)」, 저장값 `[-3.0 ×5, 0.0 ×6]`(결함 재현). 두 사본 모두 실패 6개마다 `Sector … fetch failed` WARNING. 통과

### S-2. 대시보드 섹터 카드가 결측을 `—` 로 보인다 (브라우저, 필수)
- 조작: S-1 이 만든 사본 `market_gate.json` 을 사본 Flask 가 읽게 두고 `/dashboard/kr` 를 연다
- 기대: 수정 뒤 API `sectors` 의 결측 6개가 `null`, 카드 6개는 `—`(회색), 5개는 `-3.00%`, 페이지 오류 0·「Application error」 0·`+0.00%` 0. 수정 전은 결측 6개가 `+0.00%` 로 보인다(결함 재현)
- 실제: 수정 뒤 `GET /api/kr/market-gate` 의 은행·철강·증권·조선·에너지·KOSPI 200 이 `None`/`Neutral`, 카드 문자열 `은행=—|text-gray-500` 등 6개와 `반도체=-3.00%|text-blue-400` 등 5개, `ab errors` 빈 출력, 「Application error」 0, `+0.00%` 0. 스크린샷에서 결측 카드는 회색 배경(보합 노란색 아님). 수정 전은 같은 6개가 `0.0` 으로 오고 카드 `은행=+0.00%|text-rose-400` 등 6개, `+0.00%` 6(결함 재현). 통과

### S-3. 챗봇 문맥이 결측 섹터를 0 으로 싣지 않는다 (서비스 하네스, 필수)
- 조작: 저장된 `market_gate.json` 을 `chatbot.payload_service.collect_market_context` 에 넣는다(LLM 호출·전송 없음)
- 기대: 수정 뒤 `sector_scores` 는 조회된 5개만 -3.0 으로 담는다. 수정 전은 11개 모두 담고 6개가 0.0 이다
- 실제: 수정 뒤 `{"반도체": -3.0, "2차전지": -3.0, "자동차": -3.0, "헬스케어": -3.0, "IT": -3.0}`. 수정 전 11개, 결측 6개가 `0.0`(프롬프트에 보합으로 실림). 통과

### S-4. 이 QA 가 자료를 바꾸지 않고 외부에 닿지 않는다 (필수)
- 기대: 하네스의 네트워크 차단이 걸린 채로 끝남, 화면 조회 전후 사본 `market_gate.json` 해시 같음, 사본 Flask 로그에 Market Gate 갱신·pykrx·KRX 로그인 줄 0, 원본 `data/` 수정 시각 불변
- 실제: 두 하네스 모두 `socket` 연결 차단 상태에서 exit 0(연결 시도가 있었다면 차단 예외로 분석이 `error` 가 되었을 것). 화면 조회 전후 해시 수정 전 `ee4373d68469`·수정 뒤 `aafdf00c78ec` 로 각각 같음, 사본 Flask 로그의 갱신·pykrx·KRX 로그인 줄 0. 원본 `data/` 수정 시각 불변(아래 정리). 통과

## 정리
- 실제: agent-browser 세션 둘 닫음, 사본 Next·gunicorn 정지 뒤 58101·58102 수신 0, 사본 경로 프로세스 0, 사본 둘(`q105old`·`q105new`) 리터럴 경로로 삭제 뒤 없음 확인. 원본 `data/kr_ai_analysis.json`(1788316016)·`signals_log.csv`(1789994506)·`update_status.json`(1777948277)·`market_gate.json`(1790042620) 수정 시각 그대로, 저장소 루트 `node_modules` 없음. 원본 3500·5501·`.env`·운영 주소 사용 없음. 결과: 필수 4/4 통과
