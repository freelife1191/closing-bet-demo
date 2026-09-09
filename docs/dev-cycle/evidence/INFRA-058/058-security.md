# INFRA-058 독립 보안 리뷰

## 최종 판정

**APPROVE**

- 기준 커밋: `80e2498`
- 입력 manifest: `058-input.json`
- manifest SHA-256: `af62bf0cf5e2c1eff87559e05a795cb2af758e88065cbd52c1b54cfa04ba9615`
- 파일 SHA-256: manifest 3개와 현재 checkout **3/3 일치**
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## 보안 판정 근거

### 원자성·실패 경계 — OWASP A04/A05

- `services/common_env_service.py:262`–`services/common_env_service.py:270`은 디스크에 없는 editable 키의 빈 값을 `removed`에 기록만 합니다.
- 실제 `environ.pop`은 `services/common_env_service.py:298`의 `atomic_write_text`가 성공한 뒤, 같은 lock 안의 `services/common_env_service.py:305`–`services/common_env_service.py:307`에서만 실행됩니다.
- 원자 쓰기가 예외를 내면 제어가 메모리 삭제에 도달하지 않으므로 파일과 워커 환경이 함께 이전 상태를 유지합니다. 실패를 성공으로 바꾸는 fallback이나 선행 메모리 mutation은 없습니다.
- 디스크에 키가 이미 있는 삭제 경로도 같은 `removed` 목록과 성공 후 적용 순서를 사용합니다.

### allowlist·시크릿 경계 — OWASP A01/A02

- `EDITABLE_ENV_KEYS` allowlist가 빈 값 처리보다 먼저 적용됩니다. `ADMIN_EMAILS`, `ADMIN_API_TOKEN` 등 비편집 키를 빈 값으로 보내도 `data`에서 제거되어 워커 환경을 삭제할 수 없습니다.
- INFRA-057의 unsafe-value 필터도 같은 선행 단계에 유지됩니다. 이번 diff는 parser나 검증 집합을 변경하지 않았습니다.
- 값에 `*`가 포함된 마스킹 응답은 기존 값 보존 분기에서 먼저 빠지므로 삭제 의사로 오해되지 않습니다.
- 삭제된 값이나 기존 시크릿을 로그·응답·예외에 추가로 포함하는 코드가 없습니다.

### 파일·잠금 경계

- `O_NOFOLLOW` 읽기, 별도 `flock`, `atomic_write_text` 교체, 성공 후 `environ` 반영 순서는 변경되지 않았습니다.
- 다른 정상 키가 함께 온 부분 반영 계약도 유지되며, 이 Task는 삭제 결과를 HTTP 400/구조화 body로 노출하는 후속 INFRA-051을 앞당기지 않습니다.

## 실제 실행·확인

- `058-input.json` 3개 SHA-256 대조: 모두 일치
- `tests/app/test_env_absent_key_deletion.py`: **3 passed in 0.40s**
  - 기존 `.env` 파일에서 디스크에 없는 `SMTP_USER` 삭제
  - `.env` 자체가 없을 때 environ-only `SMTP_USER` 삭제
  - synthetic atomic write 실패 시 파일·`environ` 불변
- 제공된 관련 대상 검사: **31 passed**, exit 0
- 제공된 전체 pytest: **2201 passed / 3 skipped**, exit 0
- 제공된 frontend 불변 Vitest: **373 passed**, exit 0
- Python stdlib AST: 제품·테스트 구문 통과
- `git diff --check`: 통과
- 저장 호출부 검색: 제품 경로는 관리자 설정 route 한 곳이며, 새 우회 호출부 없음
- 추적 `.env*`는 `.env.example`만 확인, 지정 파일에 실제 시크릿 패턴 없음

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다. stdlib AST와 실제 회귀는 대체 근거이며 LSP PASS로 기록하지 않습니다.
- 전체 pytest/Vitest는 이 독립 리뷰에서 반복하지 않고 제공된 종료 코드와 개수를 확인했습니다.
- 실제 `.env`, `data`, `logs`, 원본·격리 HTTP 서버, 3500/5501, live URL, LLM·외부 발송·설정 쓰기·삭제는 실행하지 않았습니다.
- 실제 UI에서의 삭제·재조회와 backend presence 확인은 후속 격리 QA의 별도 완료 조건입니다.

## Recommendation

**APPROVE.** 승인된 INFRA-058 범위에서 비편집 키 삭제, 마스킹 값 삭제, 원자 쓰기 실패 후 메모리 선행 삭제, 시크릿 노출 회귀를 발견하지 못했습니다.
