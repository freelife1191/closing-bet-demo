# [INFRA-059] 무인증으로 남은 라우트 셋 — QA 시나리오

- 대상 화면: http://localhost:3500/dashboard/kr (비로그인 상태)
- 대상 API: `POST /api/kr/refresh`, `POST /api/kr/market-gate/update`,
  `POST /api/kr/config/interval` (모두 `http://127.0.0.1:5501`)
- 구성 근거: 이번 사이클의 변경 일곱 파일과 계획 문서
  `docs/superpowers/plans/2026-09-08-infra-059-unauthenticated-route-guards.md`
- 구성 2026-09-08 | 실행 (미실행)
- QA 엔진(engine): Claude Code `/qa-only` → `/qa`
- 단계(phase): 시나리오 구성 완료 | 실행 미완료
- 반복(iteration): 0회
- baseline 상태: 정적 검증 완료 (pytest 1860 passed, 2 skipped / vitest 55 파일 355건 /
  type-check 모두 exit=0)
- 필수 여부(required): 예
- 결과: (미기록)
- 증거: (미기록)
- 정리(cleanup): (미기록)

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
- 조작: 임시 Flask 에 `curl -s -o /dev/null -w '%{http_code}' -X POST
  -H 'Content-Type: application/json' -d '{"interval":15}'
  http://127.0.0.1:<임시포트>/api/kr/config/interval`
- 기대: `403`. 응답 본문은 `{"error": "Forbidden"}`
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-2. 주기 조회는 익명에게 계속 열려 있다 (회귀)
- 조작: 같은 서버에 `curl -s http://127.0.0.1:<임시포트>/api/kr/config/interval`
- 기대: `200` 이고 본문에 `interval` 키가 있다. 조회까지 막으면 화면이 현재 주기를 보여
  주지 못한다. 이 시나리오가 그 결정을 지킨다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-3. 전체 갱신이 익명에게 거부된다 (회귀)
- 조작: **S-1 이 403 을 낸 뒤에만 실행한다.** `curl -X POST -H 'Content-Type: application/json'
  -d '{}' http://127.0.0.1:<임시포트>/api/kr/refresh`
- 기대: `403`. 이어서 `GET /api/system/update-status` 의 `isRunning` 이 `false` 그대로다.
  이 라우트가 `/init-data`·`/start-update` 와 같은 `launch_background_update_job` 에 닿으므로,
  익명이 성공하면 관리자 전용으로 만든 두 라우트가 409 로 잠긴다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-4. Market Gate 강제 갱신이 익명에게 거부된다 (회귀)
- 조작: **S-1 이 403 을 낸 뒤에만 실행한다.** `curl -X POST -H 'Content-Type: application/json'
  -d '{}' http://127.0.0.1:<임시포트>/api/kr/market-gate/update`
- 기대: `403`. 응답이 즉시 돌아온다. 게이트가 없으면 수급 재수집과 분석을 동기로 돌려
  응답까지 수십 초가 걸린다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-5. 비관리자 화면에서 세 자리가 사라진다 (회귀)
- 조작: 로그인하지 않은 상태로 http://localhost:3500/dashboard/kr 를 연다. 화면 상단의
  「매크로 지표」 줄과 KR Market Gate 카드 제목, 그리고 네 칸 그리드를 본다
- 기대: `Refresh Data` 카드가 없고, Market Gate 제목 옆 새로고침 아이콘이 없으며, 주기
  선택 드롭다운 대신 「30분 마다 자동 갱신」처럼 값이 텍스트로만 보인다. 「매크로 지표」
  줄에 마우스를 올려도 드롭다운 화살표가 나타나지 않는다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-6. 세 자리를 감춰도 그리드 배치가 깨지지 않는다 (인접)
- 조작: 같은 화면에서 `Refresh Data` 가 빠진 네 칸 그리드를 본다
- 기대: 남은 세 칸이 가로로 나란히 놓이고 겹치거나 잘리지 않는다. 네 번째 자리가 비는
  것은 허용한다. `lg:grid-cols-4` 를 조건부로 바꾸지 않기로 했다. Tailwind 가 클래스를
  정적으로 추출하므로 조건부 클래스명은 빠질 수 있다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

### S-7. 화면의 나머지 값이 그대로 나온다 (인접)
- 조작: 같은 화면에서 KR Market Gate 점수와 두 전략 카드(VCP·종가베팅)의 승률과 거래
  건수를 읽는다
- 기대: 게이트를 세우기 전과 같은 값이 나온다. 이번 변경은 조작 요소의 노출만 바꾸므로
  조회 경로에는 영향이 없어야 한다
- 필수 여부(required): 예
- 실제: (미기록)
- 결과: (미기록)

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
- 주기 변경이 거부되면 화면 값이 되돌아온다 → 같은 회귀 파일의
  「주기 변경이 거부되면 화면 값을 되돌린다」

세 갈래 모두 돌연변이로 실효를 확인했다. `canOperate` 를 `true` 로 고정하면 검사 2건이,
화살표 조건에서 `canOperate` 를 빼면 1건이, `setUpdateInterval(previousInterval)` 을
지우면 1건이 죽는다.

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

(미기록)
