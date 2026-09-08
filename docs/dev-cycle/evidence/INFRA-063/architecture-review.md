## 요약

INFRA-063의 요청 경계 설계는 승인된 범위와 일치하며 아키텍처 차단 사유가 없습니다. 인증→MIME→JSON 문법→객체 형태→기존 발송 흐름의 순서가 명확하고, 기존 중복·force·재시도 계약도 유지됩니다.

## 분석

- `@require_admin`이 라우트 함수 바깥을 감싸므로 JSON 파싱보다 인증이 먼저 실행됩니다. 실제 신원은 서명 검증 후 `g.user_email`에 저장되고, 관리자 여부가 확인된 경우에만 뷰에 진입합니다.
  `app/routes/kr_market_jongga_execution_routes.py:204`
  `app/routes/route_guards.py:47`
  `app/routes/route_guards.py:51`
  `app/__init__.py:168`
  `app/__init__.py:179`

- 비JSON 415, malformed JSON 400, 비객체 JSON 400을 발송 래퍼 밖에서 확정합니다. 이는 모든 예외를 500으로 바꾸는 `execute_json_route`의 기존 계약과 충돌하지 않는 최소 경계입니다.
  `app/routes/kr_market_jongga_execution_routes.py:211`
  `app/routes/kr_market_jongga_execution_routes.py:214`
  `app/routes/kr_market_jongga_execution_routes.py:220`
  `app/routes/route_execution.py:26`

- 검증 완료 전에는 resolver, 파일 조회, Messenger 생성, 중복 guard에 도달하지 않습니다. 테스트도 조회·생성·발송 카운터와 실제 tmpdir guard 스냅샷을 함께 관측합니다.
  `app/routes/kr_market_jongga_execution_routes.py:223`
  `app/routes/kr_market_jongga_execution_routes.py:226`
  `app/routes/kr_market_jongga_execution_routes.py:263`
  `tests/app/test_jongga_message_request_boundary.py:50`
  `tests/app/test_jongga_message_request_boundary.py:118`
  `tests/app/test_jongga_message_request_boundary.py:123`

- `{}`, 날짜, `null` 날짜, force true/false, charset 및 vendor JSON MIME 호환이 고정되어 있습니다. 기존 프론트 호출도 명시적 JSON MIME과 객체 본문을 사용합니다.
  `tests/app/test_jongga_message_request_boundary.py:191`
  `tests/app/test_jongga_message_request_boundary.py:201`
  `frontend/src/app/dashboard/data-status/page.tsx:419`

- 기존 중복 차단, force 우회, 실패 후 claim 해제·재시도 흐름은 변경되지 않았고 전용 회귀 검사가 직접 확인합니다.
  `app/routes/kr_market_jongga_execution_routes.py:241`
  `app/routes/kr_market_jongga_execution_routes.py:246`
  `app/routes/kr_market_jongga_execution_routes.py:269`
  `tests/app/test_jongga_message_request_boundary.py:252`
  `tests/app/test_jongga_message_request_boundary.py:273`

- 입력 해시는 리뷰 manifest와 재계산 결과가 일치했습니다. 정적 증거는 전체 pytest 1965 passed/3 skipped, 대상 62 passed, vitest 373 passed, typecheck 0, lint 0 errors입니다. LSP는 transport 종료로 사용할 수 없었고 AST parse와 pytest가 대체 증거입니다.
  `docs/dev-cycle/evidence/INFRA-063/review-input-sha256.json:2`
  `docs/dev-cycle/evidence/INFRA-063/final-pytest-exit.json:2`
  `docs/dev-cycle/evidence/INFRA-063/impl-report.md:18`
  `docs/dev-cycle/evidence/INFRA-063/frontend-checks.json:2`
  `docs/dev-cycle/evidence/INFRA-063/lsp-unavailable.json:1`

## Root Cause

종전의 `request.get_json(silent=True) or {}`는 비JSON·malformed JSON·falsy 비객체를 빈 객체로 합쳐 정상 발송 경로로 넘기고, truthy scalar는 `.get()` 호출 예외를 공통 래퍼가 500으로 변환했습니다. 구현 RED가 각각 200/500으로 나타난 이 문제를 기록하고 있습니다.
`docs/dev-cycle/evidence/INFRA-063/impl-report.md:10`

## Recommendations

1. 현재 엔드포인트 로컬 경계를 유지 — 낮은 노력 — 승인 범위를 정확히 지키며 공통 래퍼와 다른 라우트의 동작을 건드리지 않습니다.
2. 첫 구현 커밋 뒤 계획된 actual Next→Flask HTTP 행렬을 완료 조건으로 유지 — 중간 노력 — 프록시·rewrite·Flask 조합의 통합 증거를 확보합니다.
   `docs/superpowers/plans/2026-09-08-infra-063-json-boundary.md:69`
   `docs/dev-cycle/qa/INFRA-063.md:45`
3. 동일 정책이 두 번째 엔드포인트에도 필요해질 때만 공통 JSON 객체 파서를 검토 — 낮은 노력 — 현재 한 군데만을 위한 추상화를 피합니다.

## Architectural Status

`CLEAR`

정적 아키텍처 리뷰 결과입니다. actual HTTP가 아직 미실행이므로 최종 완료·merge-ready 판정은 그 QA 뒤에 내려야 합니다.

## Trade-offs

| 선택 | 장점 | 단점 |
|---|---|---|
| 현재 라우트 로컬 경계 | 변경 범위가 작고 415/400이 catch-all 래퍼에 오염되지 않음 | 파싱 위치가 래퍼 밖이어야 한다는 결합을 유지해야 함 |
| 공통 JSON 객체 파서 | 여러 라우트의 정책 통일 가능 | 현재는 단일 사용처이며 다른 라우트 변경 금지 범위를 침범함 |

가장 강한 반론은 이 방어가 엔드포인트 로컬이며 Flask/Werkzeug 예외 및 catch-all 래퍼의 위치에 의존한다는 점입니다. 향후 누군가 파싱을 `_handler` 안으로 옮기면 malformed JSON이 다시 500으로 바뀔 수 있습니다. 다만 현재 테스트가 정확히 그 상태 코드와 부수효과 경계를 고정하고 있고, 공통화는 승인 범위를 넓히므로 현 설계가 더 적절합니다.
