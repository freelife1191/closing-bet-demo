# INFRA-057 v2 — ponytail delta review

**기준:** `20fbbdd`

**입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/057-input-v2.json`

**입력 무결성:** 제품 코드, 회귀 테스트, Task 2 계획의 SHA-256 3개가 현재 checkout과 모두 일치했다.

## 판정

**APPROVE — 과잉설계 이슈 0건**

## Delta 근거

- `services/common_env_service.py:161-163`의 기존 공통 정규식 한 곳만 `C0 0x00-0x1f`, `DEL 0x7f`, python-dotenv escape `abfnrtv`로 넓혔다. 보안 v1의 LOW finding을 새 validator나 parser wrapper 없이 가장 작은 위치에서 닫았다.
- 실제 제어문자 33개는 `range(32)`와 `127`, 리터럴 escape 7개는 문자열 생성식 하나로 정의한다. `tests/app/test_env_control_characters.py:13-20`은 40개 입력을 기존/신규 키 두 상태에 재사용하므로 80개 테스트 본문을 복제하지 않는다.
- 정상 비밀번호 3개의 저장·재적재 회귀는 기존 그대로다. 위험 범위를 넓히면서 허용 경계도 함께 유지하므로 불필요한 테스트 scaffolding이 아니다.
- 변경은 정규식·근거 주석·테스트 데이터·Task 2 명세에만 있다. 파일 쓰기, 잠금, 부분 반영, 마스킹, 삭제, 반환 계약에는 새 구조가 없다.

## Validation

- 보안 v1 RED: **68 failed / 15 passed**. v2 대상 회귀: **111 passed**.
- frontend는 변경되지 않아 기존 Vitest **373 passed** 증거가 유지된다. 전체 pytest v2는 진행 중이므로 이 delta에서 반복하지 않았다.
- MCP 진단은 확정된 `Transport closed` 상태라 재시도하지 않았다.
- 제품 코드·테스트를 수정하지 않았고 실제 `.env`, `data`, `logs`, HTTP, 외부 발송, 운영 서비스에 접근하지 않았다.

## Recommendation

**APPROVE**

v1 보안 누락을 기존 공통 검사 한 줄에서 닫았으며 제거하거나 합칠 새 구조가 없다.
