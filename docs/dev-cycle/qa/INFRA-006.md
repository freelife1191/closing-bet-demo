# [INFRA-006] init_data 임포트 경로를 하나로 통일 — QA 시나리오

- 대상 화면: http://localhost:3500/dashboard/kr 과 하위 세 화면(`/closing-bet`, `/vcp`,
  `/cumulative`), `/dashboard/data-status`, 백엔드 http://localhost:5501
- 구성 근거: /qa-only 실측 + 이번 사이클이 건드린 아홉 파일
- 구성 2026-09-04 | 실행 2026-09-04

`TODO.md` 의 이 항목에는 `- QA 시나리오:` 줄이 없습니다. 인프라 항목이라 화면 동작을
바꾸지 않기 때문입니다. 그래서 시나리오를 실측으로 처음부터 구성했습니다.

이번 변경은 새 기능을 더하지 않고 임포트 경로만 정리합니다. `sys.path` 에 `scripts`
디렉터리를 주입하던 네 자리를 없애고 `scripts` 패키지 경로로 통일했으며, 그 주입에만
쓰이던 `project_root` 전달 체인 다섯 자리를 함께 걷어냈습니다. `scripts/init_data.py` 의
`NumpyEncoder` 사본을 지우고 공용 구현으로 바꿨고, 같은 파일의
`create_kr_ai_analysis_with_key` 가 열 수 없는 모듈을 임포트하던 것을 고쳤습니다.

그래서 이 문서가 검사하는 것은 **회귀 여부** 하나입니다. 주입을 걷어낸 뒤에도 앱이
기동하고 모든 경로가 살아 있는지 봅니다. 「`init_data` 와 `scripts.init_data` 가 동시에
메모리에 올라가지 않는다」는 이 항목의 본래 목표는 화면에서 관찰할 수 없으며,
`tests/scripts/test_init_data_module_contract.py` 의 정적 검사가 고정합니다. 그 검사는
임포트를 옛 형태로 되돌리면 실제로 실패하는 것을 확인했습니다.

## 시나리오

### S-1. 주입을 걷어낸 코드로 앱이 기동한다 (회귀)
- 조작: gunicorn 마스터에 `HUP` 신호를 보내 워커를 새 코드로 다시 띄운다. 그 직후
  `logs/backend.log` 에 새로 찍힌 줄을 읽는다.
- 기대: 워커 두 개가 `Booting worker with pid:` 로 뜨고 임포트 오류나 트레이스백이
  한 줄도 없다. `Scheduler started successfully` 가 나오고, 장 마감 분석의 `next_run` 이
  다음 날 17:00 으로 잡힌다. 지금 시각이 17:00 을 지났더라도 놓친 실행을 소급해 돌리지
  않는다. `sys.path` 주입이 하나라도 필요했다면 이 자리에서 `ModuleNotFoundError` 가 난다.
- 결과: 통과. 2026-09-04 18:12:23 에 마스터(pid 19400)로 HUP 을 보냈고 워커 15020 과
  15021 이 `Booting worker with pid:` 로 떴다. 임포트 오류와 트레이스백이 한 줄도 없다.
  `Scheduled Daily Closing Analysis at 17:00 (timezone=Asia/Seoul,
  next_run=2026-09-05 17:00:00)` 과 `Scheduler started successfully` 가 찍혔다.
  17:00 을 한 시간 넘게 지난 뒤 재기동했으나 놓친 실행을 소급하지 않았다.

### S-2. 백엔드 라우트 일곱이 모두 응답한다 (회귀)
- 조작: `/api/system/data-status`, `/api/system/update-status`, `/api/portfolio`,
  `/api/kr/backtest-summary`, `/api/kr/market-gate`, `/api/kr/signals`,
  `/api/kr/jongga-v2/latest` 를 차례로 GET 한다.
- 기대: 일곱 모두 200 이다. 앞의 넷은 `app/routes/common.py` 계열이며, 그 파일에서
  `scripts` 디렉터리를 `sys.path` 에 넣던 여섯 줄을 이번에 지웠다. 그 줄이 다른 임포트를
  떠받치고 있었다면 이 자리에서 500 이 난다.
- 결과: 통과. 일곱 모두 200 이다. `app/routes/common.py` 에서 `scripts` 주입 여섯 줄을
  지운 뒤에도 그 계열 라우트 넷이 정상 응답한다.

### S-3. 데이터 상태 화면이 여섯 파일의 상태를 그린다 (회귀)
- 조작: `/dashboard/data-status` 를 연다. 카드마다 파일 경로와 크기, 행 수를 읽는다.
- 기대: 카드 여섯이 나온다. `data/daily_prices.csv` 9.9 MB / 214,736 lines,
  `data/all_institutional_trend_data.csv` 3.7 MB / 105,528 lines,
  `data/kr_ai_analysis.json` 29.5 KB / 4 lines, `data/signals_log.csv` 1.7 KB / 15 lines,
  `data/jongga_v2_latest.json` 83.2 KB / 9 lines, `data/market_gate.json` 2.6 KB 다.
  콘솔 오류와 페이지 오류가 없다. Market Gate 동기화가 1분 간격으로 돌므로
  `data/market_gate.json` 의 크기와 수정 시각은 달라질 수 있다.
- 결과: 통과. 카드 여섯이 기대값과 정확히 같다. `data/daily_prices.csv` 9.9 MB /
  214,736 lines, `data/all_institutional_trend_data.csv` 3.7 MB / 105,528 lines,
  `data/kr_ai_analysis.json` 29.5 KB / 4 lines, `data/signals_log.csv` 1.7 KB / 15 lines,
  `data/jongga_v2_latest.json` 83.2 KB / 9 lines, `data/market_gate.json` 2.6 KB 다.
  콘솔 오류 0건, 페이지 오류 0건.

### S-4. 모의투자 모달이 잔고를 그린다 (회귀)
- 조작: `/dashboard/kr` 에서 사이드바의 「모의투자」 버튼을 누른다. 모달의 금액 네 자리를
  읽은 뒤 Escape 로 닫는다. **「계정 초기화」 탭과 「모의 매수」는 누르지 않는다.**
  잔고 상태를 되돌릴 수 없게 바꾸기 때문이다.
- 기대: 「모의투자 포트폴리오」 모달이 열리고 총 평가 자산 102,055,100원, 예수금
  91,733,700원, 총 평가 손익 +2,055,100원(+2.06%), 자산 구성이 주식 10.1%
  (10,321,400원)와 현금 89.9%(91,733,700원)로 나온다. Escape 를 누르면 모달이 닫히고
  URL 이 `/dashboard/kr` 로 그대로 남는다.
- 결과: 통과. 다만 **기대값 세 개가 실측과 어긋났고, 어긋난 쪽이 기대값이다.**
  모달은 정상적으로 열리고 Escape 로 닫히며 URL 이 `/dashboard/kr` 로 남는다.
  예수금 91,733,700원과 자산 구성 비율(주식 10.1% / 현금 89.9%)은 기대값과 일치한다.
  그러나 총 평가 자산은 102,066,600원, 총 평가 손익은 +2,066,600원, 주식 평가액은
  10,332,900원으로 나왔다. 시나리오를 구성할 때 읽은 값(102,055,100원 / +2,055,100원 /
  10,321,400원)과 다르다. 원인을 확인했다. 보유 주식이 시세로 재평가되기 때문이며,
  `/api/portfolio` 를 직접 불러 `cash` 91,733,700 과 `total_principal` 100,000,000 은
  고정이고 `total_stock_value` 만 몇 분 사이에 10,321,400 → 10,332,900 → 10,327,900 으로
  움직이는 것을 확인했다. 결함이 아니라 정상 동작이며, **이 세 값을 고정 기대값으로 삼은
  것이 시나리오의 잘못이다.** 다음 실행에서는 예수금과 원금, 모달의 개폐만 고정한다.

### S-5. 국내 시장 화면이 Market Gate 와 섹터를 그린다 (회귀)
- 조작: `/dashboard/kr` 을 연다. Market Gate 점수와 판정, 섹터 등락을 읽는다.
  **`title="Refresh Market Gate Only"` 버튼은 누르지 않는다.** 금전 비용은 없으나
  7일치 수급을 재수집해 3.7MB CSV 와 JSON 을 덮어쓴다.
- 기대: 「KR Market Gate」 아래 점수와 `Bullish`·`Neutral`·`Bearish` 가운데 하나의 판정이
  나오고, 「KOSPI 200 Sector Index」 아래 섹터별 등락률이 나온다. 콘솔 오류와 페이지
  오류가 없다. 동기화가 1분 간격이므로 점수 자체는 기대값으로 삼지 않는다.
- 결과: 통과. 「KR Market Gate」 아래 35 Score 와 `Bearish` 판정, 「하락장 (매도 우위)」가
  나온다. 「KOSPI 200 Sector Index」 아래 반도체 +3.70%, 2차전지 +0.61% 등 섹터별 등락률이
  나온다. 콘솔 오류 0건, 페이지 오류 0건. 점수는 1분 간격 동기화 대상이므로 판정에서 뺐다.

### S-6. 종가베팅 화면이 카드와 AI 리포트를 그린다 (회귀)
- 조작: `/dashboard/kr/closing-bet` 을 연다. 상단 집계 두 개와 첫 카드의 값들을 읽는다.
  **`aria-label="스크리너 전체 업데이트"` 와 `aria-label="GEMINI AI 재분석"` 버튼,
  「종가베팅 전체 10주 매수」는 누르지 않는다.**
- 기대: CANDIDATES 9, FILTERED 9, UPDATED 오후 05:05 이다. 첫 카드는 `A GRADE #1`
  로보티즈(108490)이며 상승률 +22.3%, 거래량 배수 13x, 종가 ₩304,500, 거래대금 9,003억,
  외인 5일 843억, 기관 5일 359억, 추천 `BUY`, 확신도 90% 다. AI 분석 리포트에
  `Gemini 3.7 flash` 배지가 붙고 본문이 ①부터 ⑤까지 다섯 항목으로 나온다.
  콘솔 오류와 페이지 오류가 없다.
- 결과: 통과. CANDIDATES 9, FILTERED 9, UPDATED 오후 05:05 로 기대값과 같다. 첫 카드는
  `A GRADE #1` 로보티즈(108490)이며 +22.3%, 13x, ₩304,500, 9,003억, 외인 843억,
  기관 359억, `BUY`, 확신도 90% 가 모두 기대값과 같다. AI 분석 리포트에 `Gemini 3.7 flash`
  배지가 붙고 본문에 ① ② ③ ④ ⑤ 다섯 항목이 모두 있다. 카드는 9장이며 FILTERED 수와 같다.
  콘솔 오류 0건, 페이지 오류 0건.

### S-7. VCP 화면이 스캔 결과를 그린다 (회귀)
- 조작: `/dashboard/kr/vcp` 를 연다. 안내 문구와 스캔 수를 읽는다.
  **「실패 AI 재분석」, 「Refresh VCP」, 「VCP 전체 10주 매수」는 누르지 않는다.**
- 기대: 「오늘(2026-09-04) 기준 VCP 시그널이 없습니다. 최신 저장 데이터는 2026-05-05
  입니다.」가 나오고 `TOP 0(Scanned: 1997)` 이 표시된다. 시그널이 없어도 화면이 빈 상태
  문구를 그리며 오류로 끝나지 않는다. 콘솔 오류와 페이지 오류가 없다.
- 결과: 통과. 「오늘(2026-09-04) 기준 VCP 시그널이 없습니다. 최신 저장 데이터는
  2026-05-05입니다.」와 `TOP 0(Scanned: 1997)`, 「오늘 VCP 시그널 매수 대상 종목이
  없습니다.」가 기대값대로 나온다. 시그널이 0건이어도 오류로 끝나지 않고 빈 상태 문구를
  그린다. 콘솔 오류 0건, 페이지 오류 0건.

### S-8. 누적 성과 화면이 집계를 그린다 (회귀)
- 조작: `/dashboard/kr/cumulative` 를 연다. 누적 추천수와 승률을 읽는다.
- 기대: 「2026-09-04 기준 누적 성과」 아래 누적 추천수 192, 승률 37.2% 가 나온다.
  목표 (+9%)와 손절 (-5%) 기준이 함께 표시된다. 콘솔 오류와 페이지 오류가 없다.
- 결과: 통과. 「2026-09-04 기준 누적 성과」 아래 누적 추천수 192, 승률 37.2% 가 기대값과
  같다. 목표 (+9%)와 손절 (-5%) 기준이 함께 표시된다. 같은 화면에 승률 37.5% 도 있는데
  집계 범위가 다른 별개 지표이며 이번 검사 대상이 아니다. 콘솔 오류 0건, 페이지 오류 0건.

### S-9. 관리자 경계가 그대로 유지된다 (회귀)
- 조작: `/dashboard/kr/closing-bet` 에서 카드별 재분석 버튼(`.fa-redo-alt`)의 개수와,
  화면 상단 비용 버튼 두 개의 개수를 센다. **어느 것도 누르지 않는다.**
- 기대: `.fa-redo-alt` 가 0개다. 이 세션(`caseedu.dev@gmail.com`)은 `ADMIN_EMAILS` 에
  없어 카드별 재분석 버튼이 렌더되지 않는다. `aria-label="스크리너 전체 업데이트"` 와
  `aria-label="GEMINI AI 재분석"` 은 각각 1개씩 존재하지만 누르면 권한 없음 모달이 뜨고
  네트워크 요청이 나가지 않는다. `project_root` 배선을 걷어낸 것이 이 경계에 영향을
  주지 않았음을 확인한다.
- 결과: 통과. `.fa-redo-alt` 가 0개다. 이 세션은 `ADMIN_EMAILS` 에 없어 카드별 재분석
  버튼이 렌더되지 않는다. `aria-label="스크리너 전체 업데이트"` 와
  `aria-label="GEMINI AI 재분석"` 은 각각 1개씩 존재하며 누르지 않았다. `project_root`
  배선 다섯 자리를 걷어낸 것이 관리자 경계에 영향을 주지 않았다.

## 실행하지 않는 조작과 그 이유

- `POST /api/kr/reanalyze-gemini` — 실제 Gemini 호출을 일으켜 비용이 발생한다. 이번
  사이클이 `services/kr_market_route_service.py` 의 `run_user_gemini_reanalysis` 와
  `scripts/init_data.py:2259` 의 임포트를 고쳤으므로 이 경로가 검사 대상이기는 하다.
  다만 비용 때문에 화면에서 확인하지 않고,
  `tests/scripts/test_init_data_module_contract.py` 의
  `test_init_data_imports_engine_modules_through_engine_package` 가 대신 고정한다.
  그 검사는 임포트를 옛 형태로 되돌리면 실제로 실패한다.
- 종가베팅 화면의 「스크리너 전체 업데이트」, 「GEMINI AI 재분석」, 카드별 「이 종목만
  재분석」, 「종가베팅 전체 10주 매수」 — 비용 또는 잔고 변경.
- VCP 화면의 「실패 AI 재분석」, 「Refresh VCP」, 「VCP 전체 10주 매수」 — 같은 이유.
- 국내 시장 화면의 「Refresh Market Gate Only」 — 금전 비용은 없으나 7일치 수급을
  재수집해 3.7MB CSV 와 JSON 을 덮어쓴다.
- 설정 모달 「알림 센터」 탭의 「테스트 발송」 세 개 — 실제로 텔레그램·디스코드·이메일을
  발송한다. API 탭의 휴지통 버튼과 「저장」 버튼 — 서버 `.env` 를 덮어쓰며 되돌릴 수 없다.
- 모의투자 모달의 「계정 초기화」와 「모의 매수」 — 잔고 상태를 바꾼다.

## 화면으로 검사할 수 없는 것

이 항목의 본래 목표인 「`init_data` 와 `scripts.init_data` 가 두 모듈 객체로 동시에
올라가지 않는다」는 브라우저에서 관찰할 수 없습니다. 아래 세 검사가 대신 고정합니다.

- `tests/scripts/test_init_data_module_contract.py::test_no_module_imports_init_data_as_top_level_name`
  — 저장소의 모든 파이썬 소스를 AST 로 훑어 최상위 이름 임포트를 찾는다. 판별기가
  `import init_data`, `from init_data import`, `import_module("init_data")`,
  `import_module(name="init_data")`, `__import__("init_data")` 다섯 형태를 잡고
  `scripts` 패키지 경로 네 형태를 오탐하지 않는 것을 직접 태워 확인했다.
- `tests/services/test_scheduler_jobs_refactor.py::test_scheduler_path_resolves_init_data_through_scripts_package`
  — 스케줄러 경로가 `scripts` 패키지 대역에 실제로 걸리는지 임포트를 그대로 태워 본다.
- `tests/scripts/test_init_data_module_contract.py::test_scheduler_entry_points_exist_on_init_data`
  — 스케줄러가 문자열 키로 꺼내는 다섯 함수가 실제 모듈에 있는지 확인한다.
