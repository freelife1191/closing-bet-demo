# 독립 아키텍처 리뷰 원문

`WATCH` — 비차단 판정입니다.

## Summary

현재 7개 파일에서 승인 범위를 막는 결함은 없습니다. 쿼터 예외, 기존 세션·서버 설정 가드, multipart 판정, 제목 유지 계약은 충족합니다. 다만 “모델 호출 여부” 판정이 HTTP 쿼터 계층과 챗봇 코어에 중복돼 있어 향후 명령 문법 변경 시 함께 갱신해야 합니다.

## Analysis

- 파일 없는 선두 `/` 요청만 무료 쿼터 검사와 차감에서 제외됩니다. 첨부 파일, 비문자 메시지, 앞 공백은 모델 경로로 분류됩니다. `services/kr_market_chatbot_quota_helpers.py:17-19`
- 라우트는 동일하게 정규화한 `content_type`을 사전 분류와 본문 파서에 전달하고, 파일명 판정도 실제 파서의 빈 파일 제외 규칙과 맞춥니다. 대소문자가 섞인 multipart 회귀도 고정됐습니다. `app/routes/kr_market_chatbot_http_routes.py:138-175`, `tests/app/test_kr_market_route_integration.py:539-561`, `tests/app/test_kr_market_route_integration.py:746-760`
- 세션 식별자와 서버 설정 검사는 명령 면제보다 먼저 실행됩니다. 따라서 명령도 기존 `SESSION_REQUIRED`와 `SERVER_CONFIG_MISSING` 경계를 우회하지 않습니다. `services/kr_market_chatbot_quota_helpers.py:37-60`, `tests/app/test_kr_market_route_integration.py:497-511`
- 제목 상태는 표시 문자열과 분리됐습니다. 신규 세션의 빈 제목만 미설정 상태이며, 첫 일반 질문 뒤에는 제목 내용과 무관하게 유지됩니다. 표시 단계에서만 `새로운 대화`로 대체합니다. `chatbot/storage.py:236-271`, `chatbot/storage.py:392-424`
- SQLite 저장은 빈 제목을 그대로 보존하고 `None`만 레거시 기본값으로 처리합니다. 스키마 변경이나 과거 행 일괄 수정은 없습니다. `chatbot/storage_sqlite_history.py:419-431`
- 첫 질문이 정확히 `새로운 대화`인 경우와 해당 질문이 50개 메시지 창 밖으로 밀린 뒤 재로드되는 조합도 회귀 검사로 고정됐습니다. `tests/chatbot/test_storage_sqlite.py:1261-1280`
- 현재 검토 대상 SHA와 격리 사본 SHA가 일치합니다. 전체 pytest는 2,296 passed, 3 skipped, 대상 검사는 92 passed입니다. Vitest 459/67, typecheck exit 0, lint 0 errors·194 warnings도 확인됐습니다. `docs/dev-cycle/evidence/slash-batch-20260909/review-input.json:6-34`, `docs/dev-cycle/evidence/slash-batch-20260909/pytest-approved.json:2-16`, `docs/dev-cycle/evidence/slash-batch-20260909/target-review-final.json:2-19`
- 전용 LSP 인터페이스는 현재 실행 환경에 제공되지 않아 LSP 진단은 수행하지 못했습니다. 최신 전체·대상 검사와 기존 타입·린트 결과를 대체 증거로 사용했습니다.

## Root Cause

기존 쿼터 계층은 실제 모델 호출 여부를 알지 못한 채 모든 무료 티어 성공 응답을 차감 대상으로 취급했습니다. 제목 결함은 `새로운 대화`라는 표시값을 미설정 상태의 sentinel로도 사용해, 실제 제목과 상태를 구분할 수 없었던 것이 근본 원인이었습니다.

## Recommendations

1. 현재 구현으로 QA를 진행해도 됩니다. 차단 결함은 없습니다.
2. 다음에 명령 문법을 변경할 때 `requires_chatbot_model_response()`와 `CoreCommandMixin._execute_command()`의 판정을 반드시 함께 검토하십시오. 현재 두 구현은 동일하지만 서로 다른 계층에 있습니다. `services/kr_market_chatbot_quota_helpers.py:17-19`, `chatbot/core_command_mixin.py:65-85`
3. 이 중복이 실제 변경 부담으로 드러날 때만 부작용 없는 공용 순수 판정 함수로 합치십시오. 현재 라운드에서 새 계층을 추가하면 범위와 결합만 커집니다.

## Architectural Status

`WATCH`

최강 반론은 과금 경계에서 모델 호출 여부를 추측하지 말고 코어 실행 결과를 단일 진실 공급원으로 삼아야 한다는 것입니다. 그러나 쿼터 한도 초과 요청은 코어 실행 전에 차단해야 하므로 사전 판정 자체는 필요합니다. 현재 한 줄 규칙과 회귀 행렬은 충분히 작고 명시적이므로 이번 범위에서는 중복을 유지하는 편이 낫습니다.

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 현재 사전 판정 유지 | 변경이 작고 한도 초과 명령을 코어까지 허용 가능 | 코어 명령 규칙 변경 시 동시 수정 필요 |
| 공용 판정 함수 도입 | 명령 의미가 한곳에 모임 | 서비스·챗봇 계층 사이 결합과 변경 범위 증가 |
| 코어 실행 결과로만 차감 | 실제 모델 호출 결과가 권위가 됨 | 한도 초과 요청을 실행 전에 구분할 수 없음 |

역할의 읽기 전용 제약에 따라 `architect-review.md`는 직접 작성하지 않았습니다. 위 내용이 보존할 원문 판정입니다.
