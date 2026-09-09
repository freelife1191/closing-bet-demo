## Summary

FE-022/FE-039 범위는 요구사항과 현재 구현이 일치하며 Architect 판정은 `CLEAR`입니다. 공통 프로필 정규화·세션 표시 우선순위·저장 이벤트 전파·직무 상태 복원은 `chatHelpers`를 중심으로 Sidebar/Chatbot/SettingsModal에 연결되어 있고, 손상 캐시·비로그인 기본값·known/custom/empty persona 경로가 회귀 테스트로 고정되어 있습니다.

## Analysis

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.ts:54-101`
  - `UserProfile`과 `DEFAULT_USER_PROFILE`이 공통 계약입니다.
  - `normalizeUserProfile`은 null/비객체/배열/잘못된 필드를 `User` 기본값으로 정규화합니다.
  - `resolveUserProfile`은 authenticated session의 name/email을 표시용으로 우선하고, persona는 로컬 저장 프로필에서 유지합니다.
  - session name/email이 비어 있으면 저장 프로필, 그마저 비면 `User`/`user@example.com`으로 내려갑니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.tsx:43-88,215-254`
  - Chatbot은 `useSession` 상태가 authenticated일 때만 세션 표시값을 사용합니다.
  - 로컬 프로필은 `normalizeUserProfile`을 거쳐 복원하고 JSON 파싱 실패 시 공통 기본값으로 되돌립니다.
  - `user-profile-updated` 이벤트를 구독하므로 Sidebar 저장 성공 후 Chatbot 표시가 갱신됩니다.
  - 표시용 `displayProfile`만 세션 우선으로 계산하므로 저장 프로필 자체를 세션 표시값으로 덮어쓰지 않습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx:11,36-79,110-113`
  - Sidebar도 동일한 `resolveUserProfile`/`normalizeUserProfile`을 사용합니다.
  - 초기 localStorage 복원과 `user-profile-updated` 이벤트 재조회가 같은 `loadProfile` 함수로 수렴합니다.
  - 저장 시 `saveUserProfile` 성공 후 로컬 상태를 갱신하며, helper가 성공 이벤트를 발행합니다.
  - 이벤트 listener는 effect cleanup에서 제거되어 중복 listener 누적 결합이 없습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.ts:102-126`
  - `saveUserProfile`은 서버 POST가 성공한 뒤에만 localStorage를 쓰고 `user-profile-updated` 이벤트를 발행합니다.
  - 서버 실패 시 예외를 던지므로 저장 실패 상태가 로컬 캐시 성공으로 오인되지 않습니다.
  - email은 표시/로컬 저장 계약에 포함되지만 request body에는 기존처럼 name/persona만 전송되어 서버 API 범위를 넓히지 않습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/SettingsModal.tsx:20,63-68,511-547,1007-1013`
  - `ROLE_OPTIONS`가 known role의 단일 목록입니다.
  - 모달이 열릴 때 부모 profile의 persona를 다시 주입하고, known role이면 select를 표시하며 목록 밖 값과 빈 값은 custom input 상태로 복원합니다.
  - known role 선택은 persona에 직접 저장되고, custom 입력은 원문을 유지합니다.
  - 시스템 탭 textarea도 persona 변경 시 custom 상태를 동기화하므로 탭 간 값이 갈라지지 않습니다.
  - 이름만 저장하는 경우에도 `onSave(name, email, persona)`로 현재 persona를 함께 전달합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.test.ts:35-64`
  - session name/email 우선 + persona 보존, null 기본값, 손상 프로필 정규화를 검증합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.regression-chat-022.test.tsx:42-79`
  - authenticated session 표시는 세션 값을 사용하고 localStorage 원본은 그대로 유지하는지 검증합니다.
  - null 및 invalid JSON cache는 비로그인 `User` 표시로 복원되는지 검증합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.session.test.tsx:63-75`
  - `user-profile-updated` 이벤트 후 캐시 삭제 시 Sidebar가 `User` 기본값으로 되돌아가는지 검증합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/SettingsModal.profile.test.tsx:22-98`
  - 목록 밖 custom persona 원문 복원·저장·취소 후 재오픈을 검증합니다.
  - known role 선택·저장·재오픈을 검증합니다.
  - custom 입력이 known role 문자열을 거쳐도 custom mode가 유지되는 경로를 검증합니다.

- 제공된 검증 evidence
  - pytest: 2281 passed, 2 skipped
  - Vitest: 439 passed, 62 files
  - targeted: 27 passed, 4 관련 대상
  - type-check exit 0
  - lint 0 errors, 199 warnings
  - 지정된 bounded scope와 FE-022/039 acceptance criteria에 대한 정적·회귀 검증은 통과 상태입니다.

## Root Cause

기존 어긋남은 표시용 계정 정보와 편집 가능한 로컬 프로필을 같은 값처럼 다루고, 프로필 캐시 형식과 role UI 상태를 각각의 컴포넌트에서 독립적으로 해석한 데서 발생했습니다.

현재 구현은 표시 해석을 `resolveUserProfile`, 캐시 복원을 `normalizeUserProfile`, 저장 후 전파를 `saveUserProfile`의 단일 이벤트로 모았습니다. SettingsModal은 persona 원문과 known/custom 상태를 분리해 저장 계약에 전달합니다.

## Strongest Counterargument

세션 사용자의 name/email이 비어 있는 경우 로컬 프로필을 fallback으로 표시하므로, “authenticated session 값만 표시”를 엄격하게 해석하면 논쟁 여지가 있습니다. 그러나 요구사항은 세션 name/email 우선이며, 구현은 값이 존재할 때 우선하고 비어 있으면 저장 프로필/공통 기본값으로 내려갑니다. 현재 테스트와 표시 UX 계약에는 이 fallback이 일관됩니다.

또한 Chatbot과 Sidebar가 각각 localStorage listener를 등록하는 구조는 공유 상태 라이브러리보다 중복 해석 위험이 있지만, 두 곳 모두 같은 helper를 사용하고 listener cleanup이 있어 현재 범위에서는 blocker가 아닙니다.

## Recommendations

1. `CLEAR`: 현재 FE-022/039 구현은 승인 범위와 테스트 계약을 충족합니다.
2. 공통 프로필 상태를 React context/store로 추가 통합하는 것은 가능하지만, 새 의존성과 범위 확대가 필요하므로 이번 변경에 추가할 이유는 없습니다.
3. lint warning 199건은 오류가 아니며, 이 범위의 merge blocker로 판단할 근거가 없습니다.

## Architectural Status

`CLEAR`

## File Hashes

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.tsx`
  `2263a4614e0eda1642d4f6c3a63be3fd5124a83301c3bf554b5651d572da5458`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/SettingsModal.tsx`
  `dbb1ce22d60ae9347350a771772cc95d7e4d02b7e44439931a8c36a3799cb67c`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.session.test.tsx`
  `fdd3a4cc24bef0972494d5e671056000262e5e5a94485e1a48c4125f7ca2a43e`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx`
  `ef43b8f938f061cae43b363113fc7e304b9b0002f9cd36e410b715757e40a4ea`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.test.ts`
  `713d2da325b558691bcc2de0fcd4f0dd545b7980be1a1c27c1df849bc49b53e7`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.ts`
  `7dd840d2fab21daa0a90b9eb04e67a4d5e0759ea31b22b2eb9c00a8d7d4341e4`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.regression-chat-022.test.tsx`
  `9a5c8a0cf289b747be1144c52ad075b2f63d4a9eee6faee337a8aeff017beff4`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/SettingsModal.profile.test.tsx`
  `a98553ee152fbbc09df6f0480633c5d3a223781e18a7497815a0945a665bd529`

## References

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/profile-batch-20260909/review-input.json`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/profile-batch-20260909/scope.md`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/chatHelpers.ts:54-126`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/chatbot/page.tsx:43-88,215-254`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/Sidebar.tsx:11,36-79,110-113`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/components/SettingsModal.tsx:20,63-68,511-547,1007-1013`
