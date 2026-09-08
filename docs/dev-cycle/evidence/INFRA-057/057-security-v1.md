# INFRA-057 독립 보안 리뷰 — 최초 판정

## 판정

**REQUEST CHANGES**

- 기준 커밋: `20fbbdd`
- 입력 manifest: `057-input.json`
- manifest SHA-256: `90663dc6cdad0f08a2212f5ade5b2f1404f7b51edbe22c81ddbe78ccb1873990`
- 파일 SHA-256: manifest 3개와 현재 checkout **3/3 일치**
- 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 1

## 발견 사항

### [LOW, 높은 신뢰도] python-dotenv가 복원하는 C0 제어 이스케이프 일부가 필터를 우회함

- 위치: `services/common_env_service.py:161`–`services/common_env_service.py:163`
- OWASP: A03 Injection, A05 Security Misconfiguration, A09 Security Logging and Monitoring Failures
- 현상: `UNSAFE_ENV_VALUE`는 실제 NUL/CR/LF와 리터럴 `\n`, `\r`, `\t`만 막습니다. 그러나 같은 저장 파일을 읽는 `python-dotenv`는 큰따옴표 안의 리터럴 `\a`, `\b`, `\f`, `\v`도 각각 BEL, BS, FF, VT 제어문자로 복원합니다. 실제 TAB·ESC 등 다른 C0와 DEL도 현재 정규식에 걸리지 않습니다.
- 영향: 관리자 전용 설정 경로라 권한 상승이나 비관리자 주입은 아닙니다. 다만 editable 자격 증명·주소·수신자에 제어문자가 저장·메모리 반영되어 전송 가용성을 깨거나, 해당 값이 다른 로그/표시 경로에 쓰일 때 출력 교란을 일으킬 수 있습니다. “설정 제어문자 거부” 경계가 parser의 실제 의미와 일치하지 않습니다.
- 수정: 실제 C0와 DEL을 `\x00-\x1f`, `\x7f` 범위로 거부하고, python-dotenv가 큰따옴표에서 복원하는 리터럴 escape를 `\\[abfnrtv]`로 모두 막으십시오. 기존 allowlist·부분 반영·마스킹·잠금·원자 쓰기 순서는 바꾸지 마십시오.
- 회귀: 위험값을 existing/new key 양쪽에 넣고 파일 bytes와 `environ`이 불변이며 `dotenv_values` 재적재 결과에도 대상 키가 생기거나 바뀌지 않는지 확인하십시오. 기존 정상 `pass!word$`, `has$!bang`, 공백 포함 비밀번호 3개는 계속 왕복되어야 합니다.

## 합성 probe 원문

실제 `.env`가 아닌 `StringIO`에 fake 값만 넣어 현재 설치된 `python-dotenv`의 해석을 확인했습니다.

```text
[('a\\ab', "'a\\x07b'"),
 ('a\\bb', "'a\\x08b'"),
 ('a\\fb', "'a\\x0cb'"),
 ('a\\vb', "'a\\x0bb'"),
 ('a\\x00b', "'a\\\\x00b'"),
 ('a\\u000ab', "'a\\\\u000ab'")]
```

판정: `\a`, `\b`, `\f`, `\v`는 실제 C0로 복원됩니다. `\x00`, `\u000a` 표기는 이 parser에서 literal로 남으므로 이번 finding의 우회가 아닙니다.

## 통과한 경계

- `$` 뒤 `{`, `(`, ASCII/Unicode word 문자를 막아 `${VAR}`, `$VAR`, `$()` 및 중첩·escaped 보간 시작은 차단합니다.
- 실제 NUL/CR/LF와 리터럴 `\n`, `\r`, `\t`는 existing/new key에서 저장 전에 제거됩니다.
- unsafe 데이터만 있으면 잠금·파일 쓰기·`environ` 변경 전에 반환하고, mixed 요청에서는 기존 정상값 부분 반영 정책을 유지합니다.
- `EDITABLE_ENV_KEYS`, 마스킹, `O_NOFOLLOW` 읽기, 별도 lock, atomic replace, 성공 후 `environ` 반영 순서는 변경되지 않았습니다.

## 실제 실행·확인

- `057-input.json` 3개 SHA-256 대조: 모두 일치
- stdlib AST로 제품·테스트 구문 확인
- fake `StringIO` + `dotenv_values` parser probe 실행: exit 0, 위 원문 확인
- 변경 정규식과 15개 회귀 사례 정적 대조
- `git diff --check`: 통과
- 실제 `.env`, `data`, `logs`, HTTP, 서버, LLM, 발송, 설정 쓰기·삭제는 실행하지 않음

## 실행하지 않은 검사

- MCP LSP·ast-grep: `Transport closed`가 확정되어 재시도하지 않았습니다. stdlib AST는 대체 근거이며 LSP PASS가 아닙니다.
- 전체 pytest/Vitest: 제공된 pytest 2130 passed / 3 skipped, Vitest 373 passed 증거를 확인했으며 이 독립 최초 리뷰에서 반복하지 않았습니다.
- HTTP 400 표면: INFRA-051 후속 범위이므로 현재는 비저장·`environ` 불변만 판정했습니다.

## Recommendation

**REQUEST CHANGES.** parser가 실제로 복원하는 제어문자 집합과 저장 전 검증 집합을 일치시킨 뒤 같은 범위를 재검토해야 합니다.
