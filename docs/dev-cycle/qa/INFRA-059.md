# [INFRA-059] 무인증으로 남은 라우트 셋 — QA 시나리오

- 대상 화면: http://localhost:3500/dashboard/kr (비로그인 상태)
- 대상 API: `POST /api/kr/refresh`, `POST /api/kr/market-gate/update`,
  `POST /api/kr/config/interval` (모두 `http://127.0.0.1:5501`)
- 구성 근거: 이번 사이클의 변경 일곱 파일과 계획 문서
  `docs/superpowers/plans/2026-09-08-infra-059-unauthenticated-route-guards.md`
- 구성 2026-09-08 12:50 | 실행 2026-09-08 13:05
- QA 엔진(engine): Claude Code `/qa-only` → `/qa`
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 정적 검증 완료 (pytest 1860 passed, 2 skipped / vitest 55 파일 355건 /
  type-check 모두 exit=0)
- 필수 여부(required): 예
- 결과: 통과 (필수 7 / 7)
- 증거: 아래 각 시나리오의 실제 응답과 agent-browser 스크린샷 셋(`s5-anon-top.png`, `s6-anon-grid2.png`, `s6-anon-grid3.png`)
- 정리(cleanup): 임시 Flask(포트 5599)와 agent-browser 세션 `infra059-anon` 을 종료했다. 운영 5501·3500 은 건드리지 않았다

## 실행 전에 읽을 판정 기준

**Market Gate 상태가 바뀌었다고 해서 게이트가 뚫린 것이 아니다.**
`GET /api/kr/market-gate` 는 데이터가 낡으면 익명 요청에도 백그라운드 분석을 트리거한다
(`app/routes/kr_market_system_http_routes.py` 의 `_register_market_gate_routes`). QA 도중
대시보드를 열거나 그 GET 을 한 번 치기만 해도 분석이 돌 수 있다. 이번에 재는 것은 **POST
갈래뿐**이며, GET 트리거로 상태가 바뀌는 것은 예상된 결과다. 이 자리를 이번 라운드가 손대지
않는다는 것은 승인된 결정이다.

`isRunning` 쪽에는 그런 혼동이 없다. GET 트리거는 `_market_gate_lock` 과
`data/.market_gate_refresh.lock` 만 쓰고 공통 `update_status` 파일을 건드리지 않는다.

**요청 순서를 지킨다.** 게이트가 동작하지 않으면 두 라우트가 실제 갱신을 시작한다. 비용의
종류는 서로 다르다. `/refresh` 는 `items_list=['Market Gate', 'AI Analysis']` 로 도는
백그라운드 갱신이라 **LLM 호출 비용**이 발생하고, `/market-gate/update` 는
`engine/market_gate.py` 의 `analyze()` 가 pykrx·FDR 수집만 하므로 **LLM 이 아니라 CPU 와
외부 데이터 소스 호출량**을 쓴다(보안 리뷰가 확인). 어느 쪽이든 되돌릴 수 없는 조작이므로
**가장 안전한 `/config/interval` 을 먼저 친다.** 그것이 403 을 내면 같은 데코레이터를 쓰는
나머지 둘도 같게 동작한다. 그 확인 전에는 나머지 둘을 치지 않는다.

**돌고 있는 5501 워커는 이번 변경 이전 코드다.** 사용자가 띄운 서비스를 재기동하지 않기로
했으므로, API 시나리오는 **별도 포트에 임시로 띄운 Flask** 에서 실행한다. 임시 프로세스에는
`SCHEDULER_ENABLED=false` 와 `NOTIFICATION_ENABLED=false` 를 반드시 함께 넘긴다.

**관리자 갈래는 브라우저로 재지 않는다.** 관리자 계정으로 로그인하지 않기로 했으므로,
「관리자에게는 보인다」쪽은 `page.regression-infra-059.test.tsx` 의 두 번째 검사와
`tests/app/test_admin_gated_routes.py` 의 통과 갈래가 담당한다. 그 사실을 결과에 적는다.

## 시나리오

### S-1. 주기 변경이 익명에게 거부된다 (회귀)
- 조작: 임시 Flask(포트 5599)에 `curl -X POST -H 'Content-Type: application/json'
  -d '{"interval":15}' http://127.0.0.1:5599/api/kr/config/interval`
- 기대: `403`. 응답 본문은 `{"error": "Forbidden"}`
- 필수 여부(required): 예
- 실제: `HTTP 403`, 본문 `{"error": "Forbidden"}`
- 결과: 통과

### S-2. 주기 조회는 익명에게 계속 열려 있다 (회귀)
- 조작: 같은 서버에 `curl http://127.0.0.1:5599/api/kr/config/interval`
- 기대: `200` 이고 본문에 `interval` 키가 있다. 조회까지 막으면 화면이 현재 주기를 보여
  주지 못한다. 이 시나리오가 그 결정을 지킨다
- 필수 여부(required): 예
- 실제: `HTTP 200`, 본문 `{"interval": 1}`
- 결과: 통과

### S-3. 전체 갱신이 익명에게 거부된다 (회귀)
- 조작: **S-1 이 403 을 낸 뒤에 실행했다.** `curl -X POST -H 'Content-Type: application/json'
  -d '{}' http://127.0.0.1:5599/api/kr/refresh`. 앞뒤로 `GET /api/system/update-status` 의
  `isRunning` 을 읽었다
- 기대: `403`. `isRunning` 이 `false` 그대로다. 이 라우트가 `/init-data`·`/start-update` 와
  같은 `launch_background_update_job` 에 닿으므로, 익명이 성공하면 관리자 전용으로 만든
  두 라우트가 409 로 잠긴다
- 필수 여부(required): 예
- 실제: `HTTP 403`, `time=0.001215s`. `isRunning` 은 요청 전후 모두 `False`
- 결과: 통과

### S-4. Market Gate 강제 갱신이 익명에게 거부된다 (회귀)
- 조작: **S-1 이 403 을 낸 뒤에 실행했다.** `curl -X POST -H 'Content-Type: application/json'
  -d '{}' http://127.0.0.1:5599/api/kr/market-gate/update`
- 기대: `403`. 응답이 즉시 돌아온다. 게이트가 없으면 수급 재수집과 분석을 동기로 돌려
  응답까지 수십 초가 걸린다
- 필수 여부(required): 예
- 실제: `HTTP 403`, `time=0.001184s`. **1.2 밀리초는 게이트가 뷰에 닿기 전에 막았다는
  증거다.** 뷰에 닿았다면 `init_data.create_institutional_trend` 와 `MarketGate().analyze()`
  가 동기로 돌아 초 단위가 나온다
- 결과: 통과

### S-5. 비관리자 화면에서 세 자리가 사라진다 (회귀)
- 조작: 쿠키가 없는 agent-browser 세션(`infra059-anon`)으로
  http://localhost:3500/dashboard/kr 를 열고 상단을 읽었다
- 기대: `Refresh Data` 카드가 없고, Market Gate 제목 옆 새로고침 아이콘이 없으며, 주기
  선택 드롭다운 대신 값이 텍스트로만 보인다
- 필수 여부(required): 예
- 실제: `read` 출력에서 `Refresh Data` 0건. 「매크로 지표: 1분 마다 자동 갱신」이 텍스트로
  나오고 드롭다운이 없다. 스크린샷에서 `KR Market Gate` 제목 옆에는 물음표 아이콘만 있고
  새로고침 아이콘이 없다
- 증거: `s5-anon-top.png`
- 결과: 통과

### S-6. 세 자리를 감춰도 그리드 배치가 깨지지 않는다 (인접)
- 조작: 같은 화면에서 `Refresh Data` 가 빠진 그리드를 보았다
- 기대: 남은 세 칸이 가로로 나란히 놓이고 겹치거나 잘리지 않는다
- 필수 여부(required): 예
- 실제: 첫 측정에서 세 칸이 나란히 놓였고 겹치거나 잘리지 않았다. 다만 `lg:grid-cols-4` 를
  그대로 두어 **오른쪽 1/4 이 빈 채로 남았다**(`s6-anon-grid2.png`). 기대값은 그것을
  허용했지만, 로그인하지 않은 모든 방문자가 보는 화면이라 한 줄로 고쳤다. `canOperate` 로
  `lg:grid-cols-3` 과 `lg:grid-cols-4` 를 가른다. 두 클래스명이 소스에 문자열로 있으므로
  Tailwind 의 정적 추출에 걸린다. 재측정에서 세 칸이 폭을 채웠다(`s6-anon-grid3.png`)
- 증거: `s6-anon-grid2.png`(수정 전), `s6-anon-grid3.png`(수정 후)
- 결과: 통과 (수정 후 재측정)

### S-7. 화면의 나머지 값이 그대로 나온다 (인접)
- 조작: 같은 화면에서 Market Gate 점수와 두 전략 카드, 지수 카드를 읽었다
- 기대: 게이트를 세우기 전과 같은 값이 나온다. 이번 변경은 조작 요소의 노출만 바꾸므로
  조회 경로에는 영향이 없어야 한다
- 필수 여부(required): 예
- 실제: Market Gate `55 SCORE / Neutral`, VCP 전략 `33.3% / Avg. +1.7% / 15 trades`,
  종가베팅 전략 `34.3% / Avg. -0.1% / 199 trades`, KOSPI `7,157 (+2.3%)`,
  KOSDAQ `828 (+0.7%)`. 그리드 수정 후 재측정에서도 두 전략 카드의 값이 같았다
- 증거: `s5-anon-top.png`, `s6-anon-grid2.png`, `s6-anon-grid3.png`
- 결과: 통과

## 검사로 대신한 갈래

브라우저로 재지 않고 자동 검사에 맡긴 것을 적는다. 관리자 계정으로 로그인하지 않기로 한
제약 때문이다.

- 관리자에게 세 자리가 보인다 →
  `frontend/src/app/dashboard/kr/page.regression-infra-059.test.tsx` 의
  「관리자에게는 세 자리가 모두 보인다」
- 관리자 요청이 세 라우트를 통과한다 → `tests/app/test_admin_gated_routes.py` 의
  `test_refresh_passes_for_admin`·`test_market_gate_update_passes_for_admin`,
  `tests/app/test_kr_market_route_integration.py` 의
  `test_config_interval_post_parses_string_and_applies_update`
- **서명 검증 구간을 지나는 관리자 통과** → `test_gate_passes_through_the_real_identity_path`.
  위 검사들은 `g.user_email` 을 직접 심어 그 구간을 건너뛴다. 적대적 리뷰 F4 의 지적이다
- 주기 변경 실패의 롤백과 겹침 → 같은 회귀 파일의 「주기 변경이 실패하면 화면 값을
  되돌린다」와 「요청이 겹쳐 둘 다 실패하면 서버가 받아들인 값으로 되돌린다」
- 403 을 받았을 때의 알림과 노출 회수 → 「403 을 받으면 화면이 권한 없음을 알린다」

**서명을 위조해 실제 관리자 요청을 보내지 않았다.** `/refresh` 와 `/market-gate/update` 는
통과하면 실제 갱신이 시작되어 비용이 든다. `/config/interval` 은 안전하지만 운영 신원을
위조하는 것이라 하지 않았다. **Next 프록시가 실제로 서명 헤더를 붙이는 구간은 이번 QA 로도
재지 못했다.** 그 구간은 관리자 로그인이 필요하다.

돌연변이 넷으로 검사의 실효를 확인했다.

| 돌연변이 | 죽은 검사 |
|---|---|
| `canOperate` 를 `true` 로 고정 | 2건 |
| 화살표 조건에서 `canOperate` 제거 | 1건 |
| 롤백(`setUpdateInterval`) 삭제 | 1건 |
| 확정값 대신 직전 낙관값으로 되돌림 | 1건 |
| interval 의 403 처리 삭제 | 1건 |
| `setPermissionRevoked(true)` 삭제 | 1건 |
| `NOISY_ACTIVITY_PATHS` 를 옛 목록으로 되돌림 | 1건 (경로 넷 검출) |

## 이월한 발견

리뷰가 찾았으나 이번 범위 밖이라 백로그로 올린 것이다.

- 익명 GET 하나가 Market Gate 분석을 원하는 만큼 돌릴 수 있다 → `[INFRA-064]`.
  `GET /api/kr/market-gate` 를 열어 두는 것은 승인된 결정이지만, **그 승인의 근거로 전달한
  「프로세스 잠금이 동시 실행을 막는다」가 불완전했다.** 잠금은 겹침만 막고 빈도를 막지
  않으며, 적대적 리뷰가 `?date=` 로 매 요청마다 트리거 조건이 다시 서는 결정적 재현 경로를
  찾았다. 공유 파일 덮어쓰기 타이밍이 익명 요청자 손에 있다는 것이 더 실질적인 위험이다.
  쿨다운과 실패 억제를 함께 설계해야 하므로 별도 항목으로 둔다.
- 인가 불변식 검사가 `create_app()` 부작용으로 `data/` 를 쓰고 스케줄러를 띄운다 →
  `[INFRA-065]`. `[INFRA-042]` 가 만든 검사의 성질이며 이번 라운드는 그 목록에 세 줄을
  더했을 뿐이다.

**이번 범위 안에서 고친 것은 이월하지 않았다.** 관리자 전용 POST 다섯이 활동 로그에서
빠지던 것(`app/__init__.py` 의 `NOISY_ACTIVITY_PATHS` 접두사 일치)은 이번 라운드가 인가
경계를 세우는 라운드이므로 여기서 고쳤다.

## 실행 결과

- 필수 시나리오: 통과 7 / 전체 7
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 정적 검증 (QA 중 그리드를 고친 뒤 재실행): pytest 1860 passed 2 skipped,
  vitest 55 파일 355건, type-check 모두 exit=0
- 정리: 임시 Flask(PID 는 `scratchpad/tmpflask.pid`)와 agent-browser 세션 `infra059-anon`
  을 종료했다. 운영 5501·3500 은 건드리지 않았고 `data/` 아래 파일은 임시 서버 기동 시
  `_reset_startup_status_files()` 가 `v2_screener_status.json` 을 `isRunning: false` 로
  쓴 것 외에 변경이 없다
