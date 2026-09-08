# INFRA-057 독립 보안 재검토 — v2

## 최종 판정

**APPROVE**

- 기준 커밋: `20fbbdd`
- 입력 manifest: `057-input-v2.json`
- manifest SHA-256: `356ba41fd6b833e1690e8a253e198f3322eac0602d2433650703ba7c7b28218a`
- 파일 SHA-256: manifest 3개와 현재 checkout **3/3 일치**
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## 최초 finding 해소

최초 리뷰의 LOW finding은 `services/common_env_service.py:161`–`services/common_env_service.py:163`에서 해소됐습니다.

- 실제 C0 전체 `\x00-\x1f`와 DEL `\x7f`를 저장 전에 거부합니다.
- 현재 `python-dotenv`가 큰따옴표 안에서 제어문자로 복원하는 리터럴 `\\a`, `\\b`, `\\f`, `\\n`, `\\r`, `\\t`, `\\v`를 모두 거부합니다.
- 기존 `${VAR}`, `$VAR`, `$()` 차단 규칙은 그대로 유지됩니다.
- 검증은 기존 `data` 필터 한 곳에 남아 있어 기존 키 갱신과 새 키 추가 경로가 같은 판정을 사용합니다. 별도 우회·fallback 경로가 생기지 않았습니다.

## 보안 경계 판정

### OWASP A03/A05 — 입력·설정 주입

- actual C0/DEL은 `.env` 파일·즉시 반영되는 `environ`에 들어가기 전에 제거됩니다.
- dotenv가 나중에 제어문자로 되살릴 수 있는 literal escape도 저장 전에 제거됩니다.
- `$` 뒤 `{`, `(`, word 문자를 막는 기존 보간 방어가 유지되어 editable 값으로 비편집 시크릿을 참조하거나 셸 모양 표현을 심는 경로를 다시 열지 않습니다.
- `$`로 끝나는 값, `$!`, 공백을 포함한 정상 비밀번호는 계속 저장·재적재됩니다.

### OWASP A01/A02/A09 — allowlist·시크릿·로그 무결성

- `EDITABLE_ENV_KEYS` allowlist, 값 마스킹, plain key 목록은 변경되지 않았습니다. `ADMIN_EMAILS`, `ADMIN_API_TOKEN` 등 비편집 키를 추가로 노출·저장하지 않습니다.
- 제어문자나 dotenv escape가 거부될 때 unsafe 값 자체를 로그·오류로 새로 출력하는 코드가 추가되지 않았습니다.
- 실제 C0/DEL과 parser-generated control을 차단해 editable 수신자·주소가 이후 로그나 전송 표면에서 표시를 교란하는 경로를 닫았습니다.

### 파일·메모리 원자성

- unsafe 항목만 있으면 lock·파일 읽기·쓰기 전 반환합니다. 파일 bytes와 `environ`이 모두 불변입니다.
- mixed 요청의 기존 부분 반영 정책은 유지됩니다. 이 라운드는 거부 결과를 HTTP 400으로 노출하지 않으며, 그 계약은 후속 INFRA-051 범위입니다.
- `O_NOFOLLOW` 읽기, 별도 `flock`, atomic replace, 성공 후 `environ` 갱신 순서는 변경되지 않았습니다.

## 실제 실행·확인

- `057-input-v2.json` 3개 SHA-256 대조: 모두 일치
- `tests/app/test_env_control_characters.py`: **83 passed in 0.48s**
  - actual C0 32개 + DEL + literal `abfnrtv` 7개 = 위험값 40개
  - existing/new key 각각 검사 = 80개
  - 기존 정상값 왕복 3개
- 제공된 관련 대상 검사: **111 passed**, exit 0
- Python stdlib AST: 제품·테스트 구문 통과
- `git diff --check`: 통과
- v1 fake `dotenv_values` probe에서 확인했던 `\a/\b/\f/\v` 복원 동작과 v2 차단 집합을 직접 대조

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다. stdlib AST와 실제 회귀는 대체 근거이며 LSP PASS로 기록하지 않습니다.
- v2 전체 pytest는 이 독립 재검토에서 반복하지 않았습니다. v1의 전체 pytest 2130 passed / 3 skipped는 수정 전 스냅샷이므로 v2 전체 PASS로 확대하지 않습니다.
- Vitest 373 passed는 frontend 불변 근거일 뿐 이 Python 입력 검증의 독립 증명으로 사용하지 않습니다.
- 실제 `.env`, `data`, `logs`, 원본·격리 HTTP 서버, live URL, LLM·외부 발송·설정 쓰기·삭제는 실행하지 않았습니다.
- 실제 UI/API 값 불변 검사는 후속 격리 QA가 수행할 별도 완료 조건입니다.

## Recommendation

**APPROVE.** 승인된 INFRA-057 범위에서 제어문자·dotenv escape·변수 보간 우회, 비편집 시크릿 노출, 거부 항목의 파일·메모리 반영 회귀를 발견하지 못했습니다.
