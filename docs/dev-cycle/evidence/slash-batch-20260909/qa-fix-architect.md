## Summary

두 파일의 QA 수정은 `CLEAR`입니다. Sidebar 쿼터 조회가 챗봇과 동일한 익명 세션 헤더를 사용하게 되었고, 최초 조회와 `quota-updated` 재조회가 같은 계약을 따릅니다. 전체 CHAT-008·009 판정은 이전의 비차단 `WATCH`를 유지합니다.

## Analysis

- 결함의 원인은 Sidebar만 `/api/kr/user/quota` 요청에 익명 세션 헤더를 보내지 않았던 것입니다. 서버는 검증된 이메일이 없으면 `X-Session-Id`에서 확정한 세션을 쿼터 키로 사용하므로, 헤더가 없으면 실제 사용량 대신 기본 10회를 반환합니다. `frontend/src/app/components/Sidebar.tsx:80-93`, `app/routes/kr_market_quota_http_routes.py:30-49`, `services/kr_market_quota_service.py:51-58`, `services/kr_market_quota_service.py:78-93`
- 수정은 이미 사용 중인 `getAuthHeaders()`를 재사용합니다. 이 함수는 저장된 `browser_session_id`를 읽거나 한 번 생성해 `X-Session-Id`로 반환하므로 챗봇과 Sidebar의 익명 집계 키가 같아집니다. `frontend/src/app/components/Sidebar.tsx:87`, `frontend/src/app/components/chatHelpers.ts:39-46`, `frontend/src/lib/session.ts:7-23`
- 로그인 사용자의 신원 경계도 유지됩니다. 브라우저의 세션 헤더는 익명 식별자일 뿐이고, proxy가 NextAuth 이메일을 별도 서명합니다. Flask 쿼터 해석은 인증 이메일을 익명 세션보다 우선합니다. `frontend/src/proxy.ts:24-45`, `frontend/src/proxy.ts:81-92`, `services/kr_market_quota_service.py:51-58`
- `refreshQuota`가 최초 effect와 `quota-updated` 이벤트의 공통 경로이므로 한 줄 수정이 두 호출을 함께 고칩니다. 회귀 검사는 두 호출 모두 동일한 저장 세션 헤더를 보내는지 확인합니다. `frontend/src/app/components/Sidebar.tsx:80-104`, `frontend/src/app/components/Sidebar.session.test.tsx:122-135`
- 검토 대상 SHA는 manifest와 격리 사본에서 일치합니다. `docs/dev-cycle/evidence/slash-batch-20260909/review-input.json:14-15`
- 최신 검증은 Vitest 67파일·460검사 통과, typecheck exit 0, lint 0 errors·194 warnings입니다. `docs/dev-cycle/evidence/slash-batch-20260909/vitest-qa-fix.json`, `docs/dev-cycle/evidence/slash-batch-20260909/typecheck-qa-fix.json`, `docs/dev-cycle/evidence/slash-batch-20260909/lint-qa-fix.json`
- 별도 LSP 인터페이스는 제공되지 않아 실행하지 못했습니다. 타입 검사와 전체 Vitest를 대체 증거로 확인했습니다.

## Root Cause

쿼터 조회가 인증 사용자와 익명 사용자의 신원 전달 차이를 고려하지 않고 URL만 호출했습니다. 서버는 URL이나 로컬 프로필을 신뢰하지 않으므로, 익명 사용자는 공용 브라우저 세션 헤더를 명시적으로 보내야 같은 쿼터 레코드를 조회할 수 있습니다.

## Recommendations

1. 현재 두 파일 수정은 그대로 유지합니다. 공용 헤더 유틸 재사용이라 추가 추상화가 필요하지 않습니다.
2. 이후 Sidebar 쿼터 조회 경로를 변경할 때 최초 조회와 `quota-updated` 재조회 검사를 함께 유지합니다.

## Architectural Status

- 이번 2파일 QA 수정: `CLEAR`
- CHAT-008·009 전체: `WATCH` 유지

기존 `WATCH` 사유인 HTTP 쿼터 계층과 챗봇 코어의 모델 경로 판정 중복은 이번 Sidebar 수정과 무관하며 해소되지 않았습니다. 이번 변경에서 새 차단 또는 추가 WATCH 항목은 없습니다.
