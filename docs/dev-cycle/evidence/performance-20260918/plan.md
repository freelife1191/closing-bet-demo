# 성과 집계·표시 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Repository dev-cycle controls review/QA/archive ordering. Parent owns all execution and commits.

**Goal:** FLOW-013·015·009, VCP-025, JONGGA-036을 묶어 집계와 화면 설명을 일치시킨다.
**Architecture:** 기존 Python 집계/계산 helper와 React 화면을 보완한다. 거래 정책·저장 자료는 유지하고 KPI 응답만 확장한다. 코드 레인은 분리하고 정적 검사·리뷰·브라우저 QA를 공유한다.
**Tech Stack:** 기존 Flask/pandas, Next.js/React, pytest/Vitest. 새 의존성 없음.
**Spec:** 2026-09-18 현재 대화의 5건 설계 제안 및 사용자 「진행해」. D 표시/전체 거래 ROI 합계/최근 종료10건/입력 계약 거부/성과 설명 구분에 대한 승인. 실제 승인 시각은 추정하지 않는다.

## Global Constraints
- T3 공유 라운드: 누적 cache schema version 모듈과 여러 화면/API 계약. 티어 하향 없음.
- 원본 3500/5501/live 요청·재시작 없음. .env 값 열람·복사 금지, data는 목록만 보존 대조한다.
- 원본에서 테스트 실행 금지. 부모만 git archive 사본과 합성 데이터에서 실행한다. 외부 네트워크 및 원본 쓰기를 sandbox로 차단한다.
- 실제 LLM·수집·발송·거래·설정 저장·삭제 금지. 비용 경계만 합성 대체한 실제 화면·제품 라우트를 검증한다.
- 사용자 root package.json 보존. 범위 외 파일·과거 QA를 덮어쓰지 않는다. qa/FLOW-013.md는 과거 다른 제목의 기록이므로 별도 dated report를 사용하고 링크로 연결한다.
- 각 명령 최대300초, 리뷰 레인15분, QA최대5회/동일실패3회. 통과하지 못하면 TODO 유지.

### Task 1: KPI와 입력 경계 (FLOW-013·015)
Files: services/kr_market_backtest_kpi_helpers.py, services/kr_market_backtest_trade_helpers.py, services/kr_market_cumulative_cache.py, tests/services/test_performance_batch_20260918.py.
Interfaces: existing signatures preserved. roiByGrade adds D; recentWinRate: float|null, recentClosedCount: int, consecutiveLosses: int. Recent uses WIN/LOSS only, descending (date,code,id), N=10. Consecutive losses uses the same full closed order until first WIN. No completed trades => null/0/0. Dates are recommendation dates, not exit dates.
- [x] Write regressions: D contribution and totalSignals/ROI, >10 mixed WIN/LOSS/OPEN with deliberately shuffled dates, tie order, empty closed; three invalid nonempty price frames (missing ticker in date frame, numeric YYYYMMDD date, string OHLC DatetimeIndex) raise ValueError. Normal numeric OHLC DatetimeIndex and ticker+ISO-date production input preserve results.
```python
kpi = aggregate_cumulative_kpis([
 {"grade":"D", "outcome":"LOSS", "roi":-3, "days":1, "date":"2026-09-17", "code":"000002"},
 {"grade":"S", "outcome":"WIN", "roi":5, "days":1, "date":"2026-09-16", "code":"000001"},
], pd.DataFrame(), datetime(2026,9,18))
assert kpi["totalSignals"] == 2 and kpi["totalRoi"] == 2
assert kpi["roiByGrade"]["D"]["count"] == 1
assert kpi["recentWinRate"] == 50 and kpi["consecutiveLosses"] == 1
```
- [x] Parent copies test only to scratch, pytest targeted RED; then authorize implementation.
- [x] Extend existing grade accumulator to D. Compute sorted closed list once, recent numerator/denominator and prefix losses. Public metrics boundary `calculate_cumulative_trade_metrics` validates nonempty DataFrame before date conversion; log and raise ValueError for unsupported shapes/types. Preserve empty/no-data behavior and production normalization, do not change exit-price or outcome policy.
- [x] Bump _CUMULATIVE_CACHE_SCHEMA_VERSION 5→6 once for new response. No SQL schema migration.
- [x] Parent targeted GREEN plus existing service/cache regressions.

### Task 2: 누적성과 UI (FLOW-013)
Files: frontend/src/app/dashboard/kr/cumulative/CumulativeClientPage.tsx and new sibling regression-performance-batch.test.tsx.
Consumes: task1 KPI fields. No recent statistics from page-local trades. Four grades S/A/B/D. Main average/total ROI uses kpi.avgRoi/kpi.totalRoi and explains simple sum, not portfolio compound return. Default table includes D; add D filter and card; wrap grade details safely at 1280×720/mobile.
- [x] Write regression rendering D and total 2% from fixture above, pagination uses different rows but same recent KPI, null recent shows no completed data. Parent RED.
- [x] Update local interfaces/defaults, existing card list/filter, tooltip data binding and concise labels. Remove stale S+A+B recomputation, don't create a new component framework.
```typescript
const recentWinRate = kpi.recentWinRate;
const recentLabel = recentWinRate == null ? '집계 전' : `${recentWinRate.toFixed(0)}%`;
```
- [x] Parent GREEN, screenshots at 1280×720/375×812 and page/grade transitions during QA.

### Task 3: 홈·랜딩 설명 (FLOW-009·VCP-025·JONGGA-036)
Files: frontend/src/app/dashboard/kr/page.tsx, frontend/src/app/page.tsx, app/routes/common_market_mock_routes.py, frontend/src/app/dashboard/kr/vcp/page.tsx (Stop/Target tooltip copy only), new dashboard sibling regression-performance-batch.test.tsx; required mock route regression in tests/app/test_performance_mock_20260918.py.
- [x] Read actual status source and VCP policy. Both strategy cards map Accumulating, OK (New), PENDING distinctly from EXCELLENT/GOOD/BAD. Undefined data is unknown/loading, never a poor-performance assertion. No change to server judgment thresholds.
- [x] Write six status × two card regression and user-visible policy copy checks; parent RED. Preserve the mock routes; use EXCELLENT for VCP 62.5 and GOOD for closing58.3, verify the actual standalone mock route response with a Flask test client.
- [x] Add minimal page-local status presentation mapping. Display count plus neutral labels for not-yet-judged; no misleading 0%/미흡 badge. VCP summary says backtest +15/-5 and distinguishes per-signal targets/default +5/-3. Landing jongga says saved target/stop prices, missing defaults +5/-3, unclosed OPEN rather than forced15day. Hypothetical expectancy at60% uses 0.6*5 - 0.4*3 = 1.8%, clearly hypothetical and excluding costs.
- [x] Parent GREEN and native UI checks for all six statuses, both strategies, landing tabs/mobile.

### Task 4: 통합 검증·리뷰·마감
- [x] Plan critic OKAY. Read frontend/AGENTS and Next bundled docs 02/03/05/06; React best practices for effect/default bindings.
- [x] Parent executes isolated pytest, Vitest, lint, build checker then type-check sequentially after build. Preserve RED/failure logs; don't weaken unrelated tests.
- [x] ponytail → code-review + architect parallel → T3 review. Provide exact source/test hashes, approve only resolved findings. QA fixes repeat affected review/checks.
- [x] Commit owned source, plan and QA matrix; retain TODOs. UltraQA App-adapted: actual application + seeded history/prices/status fixtures, ego-browser 단일 TaskSpace + Next MCP (실측 중 사용자 지정으로 변경). No native OMX state writes.
- [x] Matrix: D/table/KPI consistency; stable recent stats across pages and OPEN exclusion; no closed; contract rejects vs normal frames; six statuses in both cards; VCP distinct policy; landing real/hypothetical copy; viewport wrapping; error/empty paths; source/user-file preservation and owned process cleanup.
- [x] All required checks pass and scratch cleanup verified before final TODO removal. Archive five with implementation/QA fix commits, update counts once. Preserve older same-ID QA history and show dated current report.

## 실행 계약 보완 (계획 검토 지적 반영)

### 입력 경계
`calculate_cumulative_trade_metrics`가 검증 진입점이다. 빈 DataFrame/기존 no-data 입력은 기존 OPEN 결과를 유지한다. nonempty frame은 high/low/close 숫자 열을 필수로 가지며, date 열 경로는 ticker 열과 유효한 YYYY-MM-DD 문자열 또는 SQLite가 복원한 naive/no-NaT/자정 datetime64 날짜를 필수로 한다. date 열 없는 경로는 유효한 DatetimeIndex가 필요하다. numeric date(YYYYMMDD 포함), ticker 누락 date frame, 문자열 OHLC, 필수 열 누락, 유효하지 않은 날짜/index는 경고 로그 후 ValueError다. 이미 정규화된 정상 생산 입력의 결과와 무입력 동작은 바꾸지 않는다. raw CSV 문자열 가격은 생산 정규화 함수가 처리한 뒤 들어오며 그 함수를 변경하지 않는다.

### 두 성과 카드의 공통 상태 표
| status | label | 승률·평균 | theme/판정 아이콘 |
|---|---|---|---|
| Accumulating | 축적 중 | 미표시, 데이터 축적 안내 | 중립/없음 |
| OK (New) | 신규 · 판정 전 | 미표시, 신규 자료 안내 | 중립/없음 |
| PENDING | 집계 전 | 미표시, 종료 거래 없음 안내 | 중립/없음 |
| EXCELLENT | 우수 | 실제 win_rate·avg_return | 긍정/있음 |
| GOOD | 양호 | 실제 win_rate·avg_return | 보통/있음 |
| BAD | 미흡 | 실제 win_rate·avg_return, 실제 0% 포함 | 주의/있음 |
| unknown/undefined | 확인 전 | 미표시, 상태 확인 전 안내 | 중립/없음 |
loading에는 기존 로딩 표시를 유지한다. Tooltip도 비판정 상태에 성적 조언을 하지 않는다. mock status는 기존 수치(62.5/58.3)를 유지해 EXCELLENT/GOOD로 맞추며 mock의 다른 라우트는 건드리지 않는다.

### QA 합성 수치
누적성과는 24건, 네 등급 각6건. 추천일 순 첫14건 WIN(+5), 다음7건 LOSS(-3), 마지막3건 OPEN(0). 전체 ROI49%, 평균2.04%, 승률66.7%, 최근 종료10건 승률30%, 최근 종료 연패7이다. 순서대로 S/A/B/D를 배정해 D는6건/ROI9%. 실제 제품 build_cumulative_trade_record와 aggregate_cumulative_kpis 및 라우트/캐시에 합성 파일과 가격만 넣는다. 페이지 전환에서도 recent30%/7이 유지되고 200개 보기에서24행/추천24/등급합24가 같아야 한다. no closed/empty/error는 별도 합성 모드다. 6상태는 두 카드에 같은 seed상태를 제공해 실제 화면 표시를 대조한다.

Task3 범위내판정: VCP 전용 Stop/Target 툴팁은 저장된 시그널 가격이며 -3%/+5%는 기본값이라고 명시한다. 현재 값과 모든 계산·삭제·채팅 로직은 그대로 둔다. 숫자고정 오해를 풀기 위한 두 문구만 같은 승인 범위에서 고친다.

## 구현 중 구체화와 검사 이관
- 정상 DatetimeIndex는 생산 정규화 결과와 같은 timezone-naive/no-NaT/오름차순이다. timezone-aware/비정렬/복소 OHLC는 공개 계산 경계에서 로그 후 ValueError로 거부하며 지원 형식을 새로 늘리지 않는다. 각각 실제 RED→GREEN을 확인했다.
- 미집계 최근 통계는 '집계 전'·중립색·종료 거래 없음 안내만 표시한다.
- unknown status는 Object prototype 키도 포함하므로 own-key lookup으로 보호한다. toString의 실제 UI TypeError를 RED에서 확인했다.
- 기존 regression-005의 60% 기대는 유지한다. 페이지 행을 계산하던 코드를 제거했으므로 입력을 서버 recent KPI로 이관했고 대문자 WIN/LOSS 집계는 백엔드 새 회귀에서 검증한다. 실패를 숨기기 위해 삭제하지 않았다.
- 새로운 테스트의 nullable fixture 타입과 Vitest 기본 matcher 타입을 명시했다. 전역 설정·타입 억제·새 의존성을 넣지 않는다.

QA 브라우저 자산 경계: 서비스/테스트 프로세스의 외부 네트워크 차단은 유지한다. 브라우저는 실제 layout.tsx가 참조하는 cdnjs.cloudflare.com의 Font Awesome 정적 CSS/폰트 읽기만 localhost 외에 허용한다. 아이콘이 0×0인 대체 화면에서 tooltip을 검사하지 않기 위한 조치이며, 실제 LLM/데이터수집/로그인/프로필 재사용은 계속 금지한다. allowlist+실패 프록시의 bypass로 두 호스트만 열고 DOM/CSS를 주입하지 않는다.

QA 페이지 크기 보정: 실제 selector는50/100/200/500뿐이므로 존재하지않는10개선택을실측하지않는다. S-1은기존24건/49% fixture, S-2는별도paginated60건(50WIN/7LOSS/3OPEN,total229%,recent30%/7)으로기본50개페이지를왕복한다. 사용자UI에테스트용10개옵션을추가하지않는다.

## 독립 리뷰 WATCH 보완
실제 최근 표본 수와 '현재 페이지 내' 필터 범위를 표시했다. 재현 가능한 StrictMode 초기 이중 요청의 늦은 응답을 effect cleanup으로 차단하고, client-only 결과/등급 필터는 현재 페이지를 유지한다. 기존 콜백의 page1 reset 때문에 P2 D행이 사라지는 것을 RED로 확인한 뒤 해당 reset만 제거했다. 페이지 크기 변경의 reset은 유지한다. ROI 두 카드만 auto height/min-height로 바꾸고 다른 카드와 공통Tooltip은 바꾸지 않았다. 상태 union 추가 권고는 기존 unknown-safe 계약과 정확한 6상태를 유지하는 편이 간결해 채택하지 않았다. 실제 시각 검증은 아직 진행 전이다.

## T3 검토로 확인한 생산 계약 정정
초기 '생산date열은ISO문자열뿐' 가정은 틀렸다. 실제SQLite CSV snapshot의 read_json이date열을datetime64로되살린다. 메모리캐시를비우고warmSQLite만남긴실제경로에서종가판정이ValueError로실패함을재현했다. 공통serializer를바꾸지않고 metrics 경계에기존생산형태인naive/no-NaT/자정datetime64를허용한다. 숫자YYYYMMDD/문자열OHLC/tz/NaT/시간있는date열은계속거부한다. 실제cold→memoryclear→warm→jongga의count1/win100/avg5 보존을회귀로확인한다. 기준표승률분모와평균OPEN평가포함설명도실제모달열기회귀로맞춘다.

## 최종 실행 현황
2026-09-18: 구현·영향 리뷰·정적 검사·ego-browser 필수10/10·정리 완료. 위 중간 시점의 미완료 서술은 경과 기록이다. 최종 보고서 batch-performance-2026-09-18.md 참조. 최종 문서 검수 후 TODO 제거와 아카이브를 완료한다. 계획 밖 인증 요청은 실행 금지 계약을 만족했다고 주장하지 않으며 별도 편차 기록에 주체·세션 영향 미확정으로 보존했다.

최종 독립 검수 PASS—APPROVE 후 다섯 TODO를 아카이브로 이동했다. 잔여38건(P1 9/P2 29).
