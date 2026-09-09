# FE-041 Task 5 독립 보안 리뷰

## 최종 판정

**APPROVE**

- 기준 커밋: `c5f0ce9`
- 입력 manifest: `041-input.json`
- manifest SHA-256: `8d0367d28bcaf4c72a94c56030ddf7bed7b58929960ce0cfc227d5c675d4f727`
- 파일 SHA-256: manifest 5개와 현재 checkout **5/5 일치**
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## 보안 판정 근거

### 저장 성공 선행조건 — OWASP A04/A05

- `frontend/src/app/components/SettingsModal.tsx:285`–`frontend/src/app/components/SettingsModal.tsx:304`는 설정 저장의 HTTP `ok`와 JSON `status === "ok"`를 모두 확인합니다.
- 저장 400/403/502, network reject, invalid JSON, HTTP 200의 `status: error`는 모두 `설정 저장 실패`로 조기 반환하며 `/api/notification/send`를 호출하지 않습니다.
- 실제 발송도 `frontend/src/app/components/SettingsModal.tsx:306`–`frontend/src/app/components/SettingsModal.tsx:330`에서 HTTP `ok`와 JSON `status === "success"`를 함께 만족해야 성공으로 표시됩니다. 200의 error body도 성공으로 바뀌지 않습니다.
- 저장 실패의 inner return도 outer `finally`를 지나 `isTesting`을 해제합니다. 실패를 숨기는 silent default나 발송으로 우회하는 fallback이 없습니다.

### 인증·내부 헤더 — OWASP A01/A07

- `frontend/src/app/api/system/env/route.ts:21`–`frontend/src/app/api/system/env/route.ts:33`에서 NextAuth 세션 이메일을 `ADMIN_EMAILS`와 대조한 뒤에만 비공개 `ADMIN_API_TOKEN`을 얻습니다.
- 토큰이 없거나 익명·비관리자이면 no-store 403으로 끝나고 upstream fetch는 호출되지 않습니다.
- `X-Admin-Token`은 인증된 server-side upstream 요청에만 붙고 브라우저 응답에 추가되지 않습니다. 대상도 공개 `NEXT_PUBLIC_API_URL`이 아니라 server-only `API_URL` 또는 loopback 기본값입니다.
- UI의 `isAdmin` guard는 불필요한 저장 요청을 막는 보조선이며, 실제 권한 경계는 위 server route에 그대로 남아 있습니다.

### 시크릿·오류·캐시 — OWASP A02/A05/A09

- Next proxy의 upstream fetch와 upstream `response.text()`가 같은 try 경계에 있어 연결·본문 읽기 실패 모두 고정 `{status:"error", message:"Settings service unavailable"}` 502로 바뀝니다.
- catch는 예외 객체를 로그·응답에 넣지 않습니다. synthetic upstream/body canary가 502 body에 나타나지 않는 회귀가 있습니다.
- 인증 실패 403, upstream 전달 응답, proxy 502 모두 `Cache-Control: no-store`이며 upstream fetch도 `cache: "no-store"`입니다. 부분 마스킹된 환경 응답과 rejected 결과가 공유 캐시에 남지 않습니다.
- 설정 저장·발송 catch는 raw 예외를 console에 출력하지 않고 고정 사용자 문구를 사용합니다. 저장 오류 body도 UI에 반사하지 않습니다.
- 알림 테스트 저장 body는 기존 `pickNotificationEnv` allowlist를 거쳐 알림 관련 키만 담습니다. 다른 API 키나 전체 `envVars`를 발송 전 저장하지 않습니다.

### React 렌더링·XSS — OWASP A03

- 성공·실패 status는 unknown JSON 객체에서 문자열 리터럴과 비교해 판정합니다. 객체 자체를 DOM에 주입하지 않습니다.
- 발송 실패 `message`는 문자열일 때만 `testModal.content`에 포함되며 React 텍스트 노드로 렌더링됩니다. `dangerouslySetInnerHTML`, `innerHTML`, eval 계열 경로가 없습니다.
- `platform`은 `discord | telegram | email` union과 고정 버튼 호출로 제한됩니다.

## 실제 실행·확인

- `041-input.json` 5개 SHA-256 대조: 모두 일치
- `SettingsModal.notification.test.tsx` + `api/system/env/route.test.ts`: **19 passed**, test files 2 passed
  - 저장 HTTP 400/403/502, network 실패, 거짓 성공 2종: 발송 0건
  - 저장 완료 전 발송 0건, 완료 후 순서 `save → send`
  - 발송 502/503/200 error body의 성공 오판 없음
  - upstream fetch/body read canary 비노출, no-store 502
  - 익명 upstream 접근 0건
- `git diff --check`: 통과
- 정적 검색: raw saved/data console logging, HTML 직접 주입, eval 계열 없음
- 제공된 Task 5 대상 검사: **26 passed**, exit 0
- 제공된 전체 pytest: **2220 passed / 3 skipped**, exit 0
- 제공된 전체 Vitest: **389 passed / 58 files**, exit 0
- 제공된 typecheck: exit 0, lint: error 0 / 기존 warning 204
- 추적 `.env*`는 `.env.example`만 확인, 지정 파일에 실제 시크릿 패턴 없음

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다. typecheck·정적 검색·실제 회귀는 대체 근거이며 LSP PASS로 기록하지 않습니다.
- 전체 pytest/Vitest/typecheck/lint는 이 독립 리뷰에서 반복하지 않고 제공된 종료 코드와 개수를 확인했습니다.
- 실제 `.env`, `data`, `logs`, 원본·격리 HTTP 서버, 3500/5501, live URL, LLM·외부 발송·설정 쓰기·삭제는 실행하지 않았습니다.
- 실제 브라우저의 저장 실패/발송 0건, 내부 header, response cache, 번들·로그 canary 확인은 후속 격리 QA가 수행할 별도 완료 조건이며 이 정적 리뷰가 QA 성공을 대신하지 않습니다.

## Recommendation

**APPROVE.** 승인된 FE-041 범위에서 저장 실패 후 발송, HTTP 200 거짓 성공, 비관리자 upstream 접근, 관리자 토큰의 브라우저·캐시 노출, 원시 오류 반사, 사용자 메시지 XSS를 발견하지 못했습니다.
