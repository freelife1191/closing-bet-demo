# INFRA-051 Task 4 독립 보안 리뷰

## 최종 판정

**APPROVE**

- 기준 커밋: `6147150`
- 입력 manifest: `051-input.json`
- manifest SHA-256: `c4c70ea556322af12b92817a061e8e1cbf36a89444725e2a62c68789cba8676f`
- 파일 SHA-256: manifest 6개와 현재 checkout **6/6 일치**
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## 보안 판정 근거

### 입력 유형·부분 반영 — OWASP A03/A05

- `services/common_env_service.py:201` 이후 결과는 `applied`, `removed`, `preserved` 키 목록과 `rejected` 키→고정 사유만 가집니다.
- JSON 값은 문자열만 허용하며 비문자열은 `invalid_type`, allowlist 밖 키는 `unsupported_key`, 제어문자·보간 입력은 `unsafe_value`로 분류됩니다. 세 사유에 입력값이나 예외 원문이 포함되지 않습니다.
- mixed 요청에서 rejected 값은 `accepted`에 들어가지 않아 파일·`environ`에 반영되지 않고, 정상 문자열만 기존 lock·atomic write 경로로 반영됩니다. HTTP 400 응답도 부분 반영 사실을 고정 문구로 명시해 전체 롤백처럼 오인시키지 않습니다.
- atomic write 또는 메모리 적용 전 예외는 결과를 성공으로 반환하지 않습니다. 이전 INFRA-058의 성공 후 삭제·적용 순서와 마스킹 보존 분기는 유지됩니다.

### 시크릿 비노출 — OWASP A02/A09

- 응답의 `applied`, `removed`, `preserved`는 키 이름만, `rejected`는 키와 세 고정 사유만 반환합니다. 기존값·요청값·마스킹 전 시크릿은 포함하지 않습니다.
- `app/routes/common_update_routes.py:249`–`app/routes/common_update_routes.py:260`에서 JSON 오류는 예외 타입만 warning으로 남기고 고정 400/415를, 저장 예외는 타입만 error로 남기고 고정 500을 반환합니다.
- synthetic IO canary가 응답과 `caplog`에 나타나지 않는 회귀가 있고, 부분 반영 결과를 문자열화해도 rejected 시크릿 값이 없음을 확인합니다.
- 추적 `.env*`는 `.env.example`뿐이며 지정 파일에 실제 key/private-key 패턴이 없습니다.

### 관리자 게이트 — OWASP A01/A07

- `app/routes/common_update_routes.py:235`의 `X-Admin-Token` 검증이 GET/POST 분기와 JSON 파싱보다 먼저 실행됩니다. 유효한 내부 관리자 토큰 없이는 입력 형태·허용 키·저장 결과를 관측하거나 변경할 수 없습니다.
- token 검증, allowlist, `O_NOFOLLOW`, lock, atomic replace 자체는 이번 diff에서 약화되지 않았습니다.

### React 렌더링·XSS — OWASP A03

- `frontend/src/app/components/SettingsModal.tsx`는 non-2xx JSON의 `rejected`가 일반 객체인지 확인한 뒤 `Object.keys`만 가져옵니다. reason과 값은 UI 상태에 넣지 않습니다.
- rejected 키 문자열은 `testModal.content`의 React 텍스트 노드로 렌더링되며 `dangerouslySetInnerHTML`·`innerHTML` 경로가 없습니다. HTML 모양 키도 markup으로 실행되지 않습니다.
- 응답 JSON이 없거나 형태가 다르면 고정 `API 설정` 문구로 떨어지고, raw body나 예외 응답을 사용자 화면에 반사하지 않습니다.
- 비관리자는 기존 `isAdmin` 분기 때문에 env 저장 요청을 보내지 않습니다.

## 실제 실행·확인

- `051-input.json` 6개 SHA-256 대조: 모두 일치
- `tests/app/test_env_update_result.py`: **19 passed in 1.10s**
- `SettingsModal.save-isolation.test.tsx`: **4 passed**, test file 1 passed
- Python stdlib AST: 변경 backend·test 구문 통과
- `git diff --check`: 통과
- 정적 검색: `dangerouslySetInnerHTML`, `innerHTML`, eval 계열 없음. Task 4가 추가한 JSON·저장 오류 분기에는 rejected 값이나 raw 예외 로깅 없음
- 제공된 관련 backend 대상 검사: **147 passed**, exit 0
- 제공된 SettingsModal UI 검사: **10 passed**, exit 0
- 제공된 전체 pytest: **2220 passed / 3 skipped**, exit 0
- 제공된 전체 Vitest: **374 passed**, typecheck exit 0, lint error 0

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다. stdlib AST·typecheck·실제 회귀는 대체 근거이며 LSP PASS로 기록하지 않습니다.
- 전체 pytest/Vitest/typecheck/lint는 이 독립 리뷰에서 반복하지 않고 제공된 종료 코드와 개수를 확인했습니다.
- 실제 `.env`, `data`, `logs`, 원본·격리 HTTP 서버, 3500/5501, live URL, LLM·외부 발송·설정 쓰기·삭제는 실행하지 않았습니다.
- Task 5의 저장 실패 후 알림 발송 차단은 후속 FE-041 범위이며 현재 Task 4의 미완성으로 판정하지 않았습니다.

## Recommendation

**APPROVE.** 승인된 INFRA-051 Task 4 범위에서 비문자열 우회, rejected 값 저장, 시크릿 응답·로그 노출, 관리자 우회, rejected 키의 React XSS를 발견하지 못했습니다.
