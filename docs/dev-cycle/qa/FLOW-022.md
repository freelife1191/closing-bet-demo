# [FLOW-022] 하루 빈 Toss 참조의 5일 집계 채택 — QA 시나리오

- 대상 화면: http://localhost:3749/dashboard/kr/closing-bet (격리 Next dev) → 카드의 「상세 분석 보기」 모달의 「투자자 동향」 절
- 구성 근거: 설계 승인(대화 2026-09-25 16:47, TODO [FLOW-022] 절). 호출 경로: 카드 클릭 → `fetch('/api/kr/stock-detail/<code>')`
  → Flask `fetch_stock_detail_payload` → `append_investor_trend_5day` → `get_investor_trend_5day_for_ticker(verify_with_references=True)`
  → `_resolve_best_payload` → Toss 참조 `_normalize_external_trend_payload` → `_reference_reject_reason`(이번 변경). 채택되면 응답에
  `investorTrend5Day` 가 들어가고 모달은 그 값을 일수 표시 없이 그린다. 버려지면 CSV 가 있으면 CSV 합계, 없으면 키가 빠져 모달이
  `[FE-048]` 의 Toss 합계 「(N일)」로 물러선다. 사용자 진입 흐름이 이 모달이므로 브라우저 실측이 필수다
- 구성 2026-09-25(설계 승인 16:47 뒤, 첫 커밋 전) | 실행 2026-09-25 17:10:04(두 서버 응답 확인)~17:11:07, 정리 확인 17:11:29
- 검증 기준 커밋: `d3dca8c9`(이 문서를 담은 첫 커밋). 사본은 그 커밋의 `git archive` 다
- QA 엔진(engine): Claude Code, 브라우저는 gstack `browse`(`~/.claude/skills/gstack/browse/dist/browse`). `[FE-048]` 과 같은 방식으로
  시나리오를 직접 구성했고 `/qa-only`·`/qa` 스킬 본체는 부르지 않았다(두 스킬의 전체 앱 탐색 대신 이 문서의 시나리오만 실행한다)
- browser_applicability: required. 사용자가 보는 것은 모달의 글자다. browser_driver: gstack `browse`
- 격리: 첫 커밋의 `git archive` 를 scratchpad `qa-flow022/` 에 풀고 `frontend/node_modules` 는 APFS clone. 사본에서 `secrets/`·`data/`·`.env*` 를 지운 뒤
  `data/` 를 새로 만들어 QA 고정 자료 두 개만 둔다: `jongga_v2_latest.json`(신호일 2026-09-24, 네 종목), `all_institutional_trend_data.csv`(900204 한 종목,
  2026-08-24~28 다섯 행, 낡은 CSV). 원본 3500/5501·live 주소·원본 `data/`·`.env` 는 쓰지 않는다
- 대역(QA 전용 진입점 `qa_flow022_app.py`, 사본에만 둔다): `TossCollector._safe_request` 를 URL 별 고정 응답으로 바꾼다(종목 정보·투자자 동향만 응답,
  나머지 None). `_fetch_pykrx_reference_trend`·`_resolve_pykrx_latest_market_date` 를 None 으로 바꿔 KRX 에 닿지 않게 한다. loopback 이 아닌 소켓
  연결은 모두 막는다. LLM·발송 경로는 부르지 않는다. 기동 환경에 `KRX_ID=`·`KRX_PW=` 를 빈 값으로 준다
- 기동: Flask `SCHEDULER_ENABLED=false KRX_ID= KRX_PW= gunicorn qa_flow022_app:app --bind 127.0.0.1:5749 --workers 1 --threads 4 --keep-alive 0`,
  Next `PORT=3749 API_URL=http://127.0.0.1:5749 TZ=Asia/Seoul npm run dev`(더미 `NEXTAUTH_SECRET`·`INTERNAL_IDENTITY_SECRET`·`NEXTAUTH_URL`)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 수정 전 동작은 pytest 회귀 검사가 실패로 확인했다(`test_reference_reject_reason_rejects_a_day_with_missing_volume`·
  `test_a_toss_reference_missing_one_day_does_not_replace_the_csv` RED, 수정 전에는 하루 빈 Toss 참조가 채택되어 `source == "toss"`)
- 필수 여부(required): S-1~S-4 예
- 결과: 통과 (필수 4/4)
- 증거: 각 시나리오의 「실제」 줄. API 응답 scratchpad `qa-flow022-api.txt`(17:10:09), 모달 글자·콘솔·네트워크·MCP `qa-flow022-browser.txt`, 스크린샷 `flow022-QA외국인빈날-flow.png`·
  `flow022-QACSV유지-flow.png`(열어 확인)와 `flow022-QA기관빈날-flow.png`·`flow022-QA실제0-flow.png`, 격리 로그 `qa-flow022-flask.log`·`qa-flow022-next.log`.
  사본에서 import 된 것이 사본 코드임은 사본 `services/__pycache__/investor_trend_5day_service.cpython-311.pyc` 생성과 사본 `data/` 에 생긴 런타임 파일로 확인했다
- 정리(cleanup): browse 서버 정지, 격리 gunicorn(5749)·Next(3749) 종료 뒤 3749/5749/3500/5501 리스너 0, 사본 경로 프로세스 0, browse 프로세스 0, 사본 `qa-flow022/` 삭제,
  원본 `data/` 에서 17:09:27 표식 이후 바뀐 파일 0, 저장소 루트 `node_modules/.vite` 없음. 원본 3500/5501 은 처음부터 떠 있지 않았다
- 실행 중 절차 이탈 1건: 사본을 만드는 명령에서 zsh 가 매치 없는 `frontend/.env.*` glob 으로 멈춰 `data/` 생성과 고정 자료 복사가 빠졌다. 서버 기동 전에 발견해
  `find -name '.env*' -delete` 로 `.env*` 를 지우고(`.env.example` 1개) `data/` 를 만들어 고정 자료를 넣었다. 원본에는 닿지 않았다
- 읽은 정본: `.claude/skills/closing-bet-python/SKILL.md`, `.claude/skills/closing-bet-verify/SKILL.md`. frontend 변경이 없어 Next 번들 문서는 읽지 않았다

고정 자료의 Toss 투자자 동향(다섯 행 모두 종가 10,000)과 판정 경로는 다음과 같다. 수량 단위는 주이며 합계는 수량×종가다.

| 종목 | 외국인 수량 | 기관 수량 | 파서 결과 | 확정 집계 판정 | 모달 기대 |
|---|---|---|---|---|---|
| 900201 QA외국인빈날 | [10,000, 20,000, 빈, 30,000, 40,000] | 4,000×5 | 외국인 1,000,000,000·4일, 기관 200,000,000·5일 | 외국인 하루 None → `insufficient_days` 로 버림, CSV 없음 → 키 없음 | 외국인 「+10억(4일)」, 기관 「+2억」 |
| 900202 QA기관빈날 | 4,000×5 | [-10,000, -20,000, -30,000, -40,000, 빈] | 외국인 200,000,000·5일, 기관 -1,000,000,000·4일 | 기관 하루 None → 버림 → 키 없음 | 외국인 「+2억」, 기관 「-10억(4일)」 |
| 900203 QA실제0 | [10,000, 0, 10,000, 10,000, 10,000] | -4,000×5 | 외국인 400,000,000·5일, 기관 -200,000,000·5일 | None 없음 → 채택 → 키 있음 | 외국인 「+4억」, 기관 「-2억」, 일수 표시 없음 |
| 900204 QACSV유지 | [10,000, 20,000, 빈, 30,000, 40,000] | 4,000×5 | 900201 과 같음 | 낡은 CSV(`stale_csv`) → Toss 참조 버림 → CSV 합계(외국인 100,000,000×5, 기관 -60,000,000×5) | 외국인 「+5억」, 기관 「-3억」 |

수정 전 코드였다면 900201·900202·900204 는 Toss 참조가 채택되어 `investorTrend5Day` 가 4일 합계(`1,000,000,000`·`200,000,000` 등)를 담고, 모달은 「(4일)」 없이 그렸다.

바뀌는 소비처는 상세 API 와, 통합 서비스를 거치는 스크리너 점수 폴백 `_calculate_supply_score_csv`(Toss 직접 조회가 실패했고 target_date 없이 돌 때만.
target 을 넘기면 오늘 날짜라도 Toss 참조를 조회하지 않는다)다. 참조는 CSV 에 이상 플래그가 붙었거나 종목이 없을 때만 조회하므로, CSV 가 매일 갱신되는 정상 운영에서는
판정에 닿는 종목이 적다. VCP 스크리너의 최신 점수
경로는 Toss 를 직접 읽어 이 판정을 지나지 않으며 부분 합계를 점수화하는 것은 `[INFRA-109]` 의 승인된 동작이다(리뷰 지적 (1)로 설계 기록을 정정). 점수 폴백은 화면에서
부를 수 없고 신호 생성은 외부 조회·LLM 이라 이 문서의 시나리오에 넣지 않았으며, pytest 통합 검사 `test_a_toss_reference_missing_one_day_does_not_replace_the_csv` 가
같은 `get_investor_trend_5day_for_ticker(verify_with_references=True)` 경로를 확인한다.

알려진 한계(리뷰 지적 (2)(3), 조치 없음):
- 참조를 버린 뒤 통합 서비스가 None 이면 상세 API 는 레거시 CSV 경로로 떨어진다. CSV 에 그 종목이 1~4행만 있으면 k일 합계가 「(N일)」 없이 나간다. 수정 전에도 같은 경우 Toss 4일 합계가
  표시 없이 나갔으므로 회귀는 아니며 `[FLOW-023]` 으로 이월했다. 이 문서의 900201~900203 은 CSV 에 종목이 없어 이 경로가 키를 넣지 않는다
- 부분 참조는 판정 전에 날짜 토큰으로 메모리·SQLite 에 캐시되므로 한 번 받은 부분 참조는 그날 내내 버려진다. 종전에는 그날 내내 채택된 채 고정되었다
- (T3 심층 리뷰 R1) CSV 가 `stale_csv`·`extreme_abs_total` 이고 pykrx 참조가 없을 때 하루 빈 Toss 참조를 버리면 낡거나 손상된 CSV 가 표시 없이 남는다. S-4 의 900204 가 그 예로,
  수정 전에는 최신 Toss 값(외국인 4일 +10억, 기관 5일 +2억)이 보였고 수정 뒤에는 한 달 전 창의 CSV(+5억, -3억)가 보인다. 완전했던 기관 값이 낡은 반대 부호 값으로 바뀐다.
  퇴화한 참조보다 CSV 를 남긴다는 기존 정책(`test_a_zero_reference_does_not_overwrite_a_stale_but_real_csv`)을 이 사유에도 적용한 결과이며, 승인된 설계가 허용한 갈래다.
  CSV 갱신이 5영업일 넘게 멈추고 pykrx 참조도 없고 Toss 에 빈 날이 있어야 하는 드문 조합이다. 참조를 모두 버렸고 CSV 가 stale·extreme 이면 None 을 돌려줄지는
  `[FLOW-023]` 의 설계 질문에 붙였다
- (T3 심층 리뷰 R3, 확신도 낮음) Toss 가 장중에 오늘 행의 종가는 주고 외국인·기관 수량을 비운다면 장중 Toss 참조는 모두 버려지고 날짜 토큰 캐시 때문에 그날 내내 버려진다.
  네트워크 없이 확인할 수 없는 전제다. 종가까지 비면 파서가 그 행을 빼므로 수정 전에도 4행이라 버려졌다
- (T3 심층 리뷰 R2) 「5행 미만」과 「5행 중 빈 값」이 같은 사유 `insufficient_days` 로 기록되므로 `discarded_references` 로 두 경우의 빈도를 가를 수 없다. 기존 사유를 다시 쓰는 것은 승인된 선택이다

## 시나리오

### S-1. 외국인 수량이 하루 빈 Toss 참조를 5일 집계로 쓰지 않는다 (회귀)
- 조작: `curl` 로 `/api/kr/stock-detail/900201` 을 받아 `investorTrend`·`investorTrend5Day` 를 읽는다. 브라우저에서 QA외국인빈날 카드의 「상세 분석 보기」를 눌러 외국인·기관 칸의 글자를 읽는다.
- 기대: API 는 `investorTrend5Day` 키 없음, `investorTrend.foreign` 1000000000·`foreignDays` 4, `institution` 200000000·`institutionDays` 5. 화면은 외국인 「+10억(4일)」, 기관 「+2억」(「일)」 없음).
- 필수 여부(required): 예
- 실제: API `investorTrend5Day` 없음, `foreign` 1000000000.0·`foreignDays` 4, `institution` 200000000.0·`institutionDays` 5. 모달 칸 textContent 「외국인+10억(4일)」「기관+2억」. 스크린샷 `flow022-QA외국인빈날-flow.png` 에서 외국인은 붉은 「+10억」 옆에 작은 회색 「(4일)」, 기관은 「+2억」만 보였다
- 결과: 통과

### S-2. 기관 수량이 하루 빈 Toss 참조도 같은 판정을 받는다 (회귀)
- 조작: 900202 에 같은 조작을 한다.
- 기대: API 는 `investorTrend5Day` 키 없음, `foreign` 200000000·`foreignDays` 5, `institution` -1000000000·`institutionDays` 4. 화면은 외국인 「+2억」, 기관 「-10억(4일)」.
- 필수 여부(required): 예
- 실제: API `investorTrend5Day` 없음, `foreign` 200000000.0·`foreignDays` 5, `institution` -1000000000.0·`institutionDays` 4. 모달 「외국인+2억」「기관-10억(4일)」
- 결과: 통과

### S-3. 실제 0 인 날이 있는 참조는 계속 채택한다 (인접)
- 조작: 900203 에 같은 조작을 한다. 네 모달을 연 뒤 `console --errors` 와 `/_next/mcp` `get_errors`·`get_compilation_issues` 를 읽고, Flask 로그에서 error·traceback·blocked 줄을 센다.
- 기대: API 는 `investorTrend5Day` 가 `{foreign: 400000000, institution: -200000000}`, `foreignDays`·`institutionDays` 5. 화면은 외국인 「+4억」, 기관 「-2억」이고 「일)」 글자가 없다. 콘솔·런타임·컴파일 오류 없음, Flask 로그 오류 0줄.
- 필수 여부(required): 예
- 실제: API `investorTrend5Day` `{foreign: 400000000, institution: -200000000}`, `foreignDays`·`institutionDays` 5. 모달 「외국인+4억」「기관-2억」, 「일)」 없음. 네 모달을 연 뒤 browse `console --errors` 는 「(no console errors)」,
  `/_next/mcp` `get_errors` 는 `configErrors:[]`·`sessionErrors:[]`, `get_compilation_issues` 는 `issues:[]`. `browse network` 의 `stock-detail`·`jongga-v2` 요청은 모두 200. Flask 로그의 error·traceback·blocked 0줄
- 결과: 통과

### S-4. CSV 가 있으면 하루 빈 Toss 참조 대신 CSV 합계가 남는다 (회귀)
- 조작: 900204 에 같은 조작을 한다.
- 기대: API 는 `investorTrend5Day` 가 `{foreign: 500000000, institution: -300000000}`(CSV 합계), `investorTrend.foreign` 1000000000·`foreignDays` 4. 화면은 외국인 「+5억」, 기관 「-3억」이고 「일)」 글자가 없다.
- 필수 여부(required): 예
- 실제: API `investorTrend5Day` `{foreign: 500000000, institution: -300000000}`, `investorTrend.foreign` 1000000000.0·`foreignDays` 4. 모달 「외국인+5억」「기관-3억」, 「일)」 없음. 스크린샷 `flow022-QACSV유지-flow.png` 에서 붉은 「+5억」, 푸른 「-3억」으로 보였다.
  이 결과는 승인된 설계대로이며, 위 「알려진 한계」의 R1 처럼 낡은 CSV 가 표시 없이 남는 갈래이기도 하다
- 결과: 통과

## 이월한 발견

- 수급 CSV 를 읽는 두 경로와 pykrx 참조의 빈 값 0 처리 → `[FLOW-023]`. 코드 리뷰에서 발견했고 위험 경로의 다른 함수라 이번 범위를 넘는다
- pytest 가 실제 pykrx 조회로 KRX 에 로그인하는 문제 → `[INFRA-121]`. 구현 중 RED 실행에서 발견했다

## 실행 결과

- 필수 시나리오: 통과 4 / 전체 4
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 없음(위 이월 두 건은 구현·리뷰 중 발견)
