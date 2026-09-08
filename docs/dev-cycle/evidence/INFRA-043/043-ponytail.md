# INFRA-043 Task 1 — ponytail review

**검토 기준:** `e4c4fd6c19973dc4c877e9c90763d076c5bb3926`

**최종 입력:** `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/043-input-v2.json`

**입력 무결성:** Task 1 소스·테스트·계획 9개 SHA-256을 현재 checkout과 대조했으며 모두 일치했다. 이 판정은 v1이 아니라 custom sender 반환 계약까지 반영한 v2에 대한 것이다.

## 판정

**APPROVE — 과잉설계 이슈 0건**

## 근거

- `engine/messenger_senders.py:43-142`는 기존 세 sender의 실제 전송 경계에 disabled guard와 bool 반환, 고정 오류 로그만 추가했다. 새 sender 계층, 정책 객체, 예외 래퍼나 설정값을 만들지 않았다.
- `engine/messenger.py:87-121`의 facade guard와 각 sender guard는 단순 중복처럼 보이지만 제거 대상이 아니다. route는 facade를 사용하고, `send_screener_result`는 `engine/messenger.py:139-145`에서 sender를 직접 호출하므로 두 진입점 모두 독립적으로 비활성 상태를 지켜야 한다. 공통 template/helper로 세 채널을 묶으면 현재보다 간접 호출과 분기만 늘어난다.
- custom 경로는 `engine/messenger.py:179-232`의 기존 두 메서드 안에서 disabled, HTTP status, 예외를 각각 `False`로 보존하고 성공만 `True`로 반환한다. Telegram과 Discord의 payload·주소·설정 조건이 다르므로 두 메서드를 새 범용 전송기로 합치지 않은 것이 작은 변경이다.
- `services/notifier_channels.py:23-132`와 `services/notifier.py:65-95`는 이미 존재하던 별도 알림 흐름이다. 이번 변경은 기존 catch의 예외 원문을 예외 타입으로 바꾸는 데 그쳤다. 이 라운드에서 engine sender와 notifier channel을 통합하면 승인 범위를 벗어난 리팩터링과 회귀 위험이 커진다.
- route는 기존 `_NotificationPlatformSpec`, `_build_error_response`, `_execute_notification_route`, `_send_platform_test_notification` 구조를 그대로 사용한다. `app/routes/common_notification_routes.py:98-115,162-168`에서 bool을 HTTP 502로 올리고 disabled를 503으로 구분하는 최소 계약 변경이며 fallback이나 병렬 실행 경로가 없다.
- 새 테스트는 별도 프레임워크나 fixture 계층 없이 로컬 `messenger`·`transport` fixture와 매개변수화로 반복을 줄였다. `tests/engine/test_notification_failure_contract.py:46-142`가 facade/direct sender/custom/notifier/route의 서로 다른 실제 분기를 고정하므로 단순 구현 복제 테스트가 아니다.
- `send_custom_message`의 aggregate 결과 반환, sender 공통 template method, 전역 redaction 유틸리티, 채널 registry 확장은 현재 요구에 필요하지 않아 추가하지 않았다. ponytail ladder의 YAGNI와 최소 변경 원칙에 맞는다.

## 확인 범위

- `git diff --check e4c4fd6`는 깨끗했다.
- 제품 코드·테스트는 수정하지 않았다.
- 상위 검증 결과는 대상 pytest **69 passed**, 전체 pytest **2112 passed / 3 skipped**다. frontend SHA는 바뀌지 않았고 기존 Vitest **373 passed** 증거가 유지된다. 이 레인에서는 중복 실행하지 않았다.
- `/var/folders/99/kpfx0mdj3fvbczqpbncjl0bm0000gn/T/closing-bet-notification-rounds-4s28gwie/043-static-analysis.json`의 stdlib AST 검사에서 unsafe logger argument 0건을 확인했다. MCP LSP/AST 도구는 transport 종료로 실행되지 않았으므로 성공으로 기록하지 않는다.
- 본 문서는 구조와 불필요 코드에 대한 ponytail 판정이며 이후 code-review·보안·QA 게이트를 대체하지 않는다.
- 실제 `.env`, `data/`, `logs/`와 원본 서비스·live URL에 접근하지 않았고 HTTP/네트워크·외부 발송을 실행하지 않았다.
