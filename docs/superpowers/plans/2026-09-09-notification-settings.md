# Notification Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 설정 저장과 알림 발송의 실패를 숨기지 않고, 발송 자격 증명을 로그에 남기지 않는다.

**Architecture:** 기존 SettingsModal → Next env proxy → Flask env service → notification route → Messenger → sender 흐름을 유지한다. 작은 계약 변경을 다섯 라운드로 구분한다. 정상 설정의 부분 반영은 유지하되 거부를 HTTP 400으로 명시하고, 테스트 발송은 저장 성공 뒤에만 수행한다.

**Tech Stack:** Python/Flask/python-dotenv/requests, Next.js 16.3.4/React/Vitest, pytest, agent-browser.

**Spec:** 2026-09-09 실제 대화의 다섯 라운드 설계 표와 이어진 사용자 「승인」. 새 하위 시스템 없는 bounded 변경이다. 시크릿 경계에 대한 보수적 T3 검토를 적용하기 위해 이 실행 계획을 남긴다.

## Global Constraints

- 원본 작업 트리의 untracked package.json, 실제 .env/data/logs와 운영 3500/5501/live는 접근·변경하지 않는다.
- 격리 clone의 develop에서만 작업한다. 신규 의존성, 배포, 외부 알림, LLM 호출 없음.
- 구현 순서 INFRA-043 → INFRA-057 → INFRA-058 → INFRA-051 → FE-041. 각 ID의 변경·QA·아카이브를 구분한다.
- 각 독립 리뷰 상한 20분, QA 90분, 전체 묶음 6시간. 초과는 미완료이며 PASS로 바꾸지 않는다.
- QA는 ultraqa App 대응이며 hook 소유 .omx 상태는 조작하지 않는다. 기존 실제 UI를 agent-browser로 검사하고 HTTP/SMTP 외부 경계만 대역한다.
- 각 ID의 필수 QA가 통과하기 전 TODO 제거·완료 아카이브 금지. 소유한 프로세스·fixture만 정리한다.
- 동일 실패 3회/UltraQA 5회 중단 한도와 실패 원문을 보존한다.

### Task 1: INFRA-043 발송 결과와 비밀 경계

**Files:** engine/messenger_senders.py, engine/messenger.py, services/notifier_channels.py, services/notifier.py, app/routes/common_notification_routes.py; tests/engine/test_notification_failure_contract.py, tests/engine/test_messenger_compatibility.py, tests/app/test_common_routes_refactor.py, tests/app/test_notification_admin_gate.py.

**Interfaces:** 기존 send(data)->bool을 facade `_send_*(payload)->bool`까지 전달한다. None에 의존하는 호출자는 없는지 검색한다. API는 실제 성공200, disabled503, sender False502, 예상치 못한 예외500+고정 오류문을 반환한다.

- [ ] RED: transport를 대역하고 실제 Messenger와 Flask route에서 아래 계약을 확인한다.

```python
assert messenger._send_discord({"title": "QA"}) is False  # 비활성/전송 예외
assert response.status_code == 503  # NOTIFICATION_ENABLED=false
assert transport.call_count == 0
assert "FAKE_PRIVATE_NOTIFICATION_CANARY" not in caplog.text
```

- [ ] GREEN: 세 기본 sender와 직접 호출 가능한 custom sender에 config.disabled guard를 둔다. facade는 sender 결과를 반환하고 sender 부재면 False. API는 bool을 검사한다. 기존 성공용 dummy는 실제 bool 계약과 맞게 True를 반환하도록 고치고 실제 sender 통합 검사로 보강한다.
- [ ] 예외 로그는 `type(error).__name__`, 상대 실패 응답은 HTTP status만 기록한다. engine custom 및 notifier channels/outer catch에도 같은 비밀 비노출 기준을 적용한다. notification API 예외 원문은 응답하지 않는다. 기존 관리자 게이트 유지.
- [ ] 대상 pytest RED/GREEN → ponytail → code/architecture → deep/security 리뷰 → 전체 pytest/vitest → QA 행렬 커밋. 실제 브라우저 성공·disabled·전송 실패와 transport 수를 검증하고 ID별 완료 기록을 남긴다.

### Task 2: INFRA-057 설정 제어문자 거부

**Files:** services/common_env_service.py, tests/app/test_env_control_characters.py.

**Interfaces:** update_env_file의 기존 부분반영/마스킹 정책 유지. 거부 정규식에 NUL과 리터럴 backslash+n/r/t를 추가한다. 실제 CR/LF/변수확장 거부도 유지한다.

- [ ] RED: 기존/신규 키에 `a\x00b`, 큰따옴표 안의 리터럴 `\\n`, `\\r`, `\\t`를 전달하고 파일·environ 불변을 검사한다. `pass!word$`, `has$!bang`, 공백 포함 정상 비밀번호는 저장 후 dotenv_values로 재적재해 원문과 대조한다.
- [ ] GREEN: `UNSAFE_ENV_VALUE = re.compile(r"[\x00\r\n]|\\[nrt]|\$[{(\w]")`로 두 유입 경로를 공통 검사한다.
- [ ] 대상 회귀와 기존 INFRA-044/050 검사를 수행한다. 최종 QA에서 실제 설정 화면의 정상 저장과 API 적대 입력의 파일/환경 불변을 대조한다.

### Task 3: INFRA-058 명시적 삭제

**Files:** services/common_env_service.py, tests/app/test_env_absent_key_deletion.py.

**Interfaces:** 빈 문자열은 삭제 의사다. 디스크에 키가 없는 경우에도 삭제 목록에 포함하되 atomic_write_text 성공 후에만 environ.pop을 수행한다. 마스킹 입력은 기존 값 유지.

- [ ] RED: 파일 존재/부재 각각에 environ만 가진 SMTP_USER를 빈 문자열로 저장해 키가 사라지는지 검사한다. atomic_write_text 실패 시 파일/environ 불변도 검사한다.
- [ ] GREEN: 새 키 루프에서 `if "*" in value: continue`, `if not value: removed.append(key); continue`를 분리한다. 기존 잠금/원자 교체/메모리 적용 순서를 유지한다.
- [ ] 전체 회귀와 실제 화면의 SMTP_USER 비우기·재조회 및 backend presence 증거를 검사한다.

### Task 4: INFRA-051 설정 저장 결과

**Files:** services/common_env_service.py, app/routes/common_update_routes.py, tests/app/test_env_update_result.py, frontend/src/app/components/SettingsModal.tsx와 저장 검사.

**Interfaces:** `update_env_file(...)->dict`는 `applied`, `removed`, `preserved`, `rejected`를 반환한다. 앞 세 필드는 키 목록, rejected는 키→고정 사유. 사유는 unsupported_key/unsafe_value/invalid_type. 값은 절대 포함하지 않는다. 거부가 있으면 HTTP400/status error, 없으면200/status ok. 정상값 부분반영은 유지한다.

- [ ] RED: 위험키와 정상키 혼합 요청은 정상값만 반영되고400/rejected를 받는지 검사한다. 전부거부·마스킹만·빈요청·잘못된 JSON 타입·파일쓰기예외도 검사한다.
- [ ] GREEN: 키 필터에서 거부 사유를 모으고 기존 잠금 안에서 applied/removed/preserved를 모은다. 실패 시 반환값으로 성공을 주장하지 않는다. route는 dict 입력과 반환 결과를 검사하고 거부가 있으면400. 사용자 UI는 실패 상태와 거부된 허용 필드명을 표시하되 값은 출력하지 않는다.
- [ ] 계약 검증 예시:

```python
assert response.status_code == 400
assert response.json["rejected"]["SMTP_USER"] == "unsafe_value"
assert response.json["applied"] == ["SMTP_PORT"]
assert environ["SMTP_PORT"] == "587"
```

- [ ] 관련 pytest/Vitest·typecheck/lint와 실제 일반 저장 오류 화면을 검사한다. 정상키 일부 반영을 전체 롤백처럼 설명하지 않는다.

### Task 5: FE-041 저장 뒤 발송

**Files:** frontend/src/app/components/SettingsModal.tsx, frontend/src/app/api/system/env/route.ts 및 각각의 테스트.

**Interfaces:** handleTestNotification은 저장 HTTP 성공 및 body.status=ok를 확인한 뒤에만 notification/send를 호출한다. 전송도 HTTP 성공 및 status=success를 확인해야 성공이다. 저장 실패는 '설정 저장 실패', 전송 실패는 '발송 실패'로 구분한다. Next upstream fetch/response.text 예외는 고정 JSON502+no-store.

- [ ] RED: 실제 SettingsModal에 저장400/403/502, 네트워크 거부, 잘못된 성공본문을 공급하고 notification/send 요청0회 및 저장 실패 표시를 검사한다. 정상 저장/성공 전송과 실패 전송을 구분한다.
- [ ] GREEN: 저장 요청/본문 확인을 별도 try 경계로 두고 실패면 return한다. finally는 isTesting을 해제한다. Next proxy는 fetch와 text 읽기를 함께 catch하며 자격 증명/예외문을 출력하지 않는다. 인증 판정은 그대로 유지한다.
- [ ] Next 번들 문서 15-route-handlers, 07-mutating-data와 frontend 매핑을 적용한다. typecheck/lint/full Vitest·pytest, next-dev-loop MCP, 실제 브라우저 정상/실패/권한을 검증한다.

## 공유 검증과 마감

- [ ] baseline: pytest2077 passed/3 skipped, Vitest373 passed/57 files(2026-09-09 격리 실행); 후속 변경마다 영향 검사를 갱신한다.
- [ ] 정확한 파일 SHA와 diff로 ponytail, code-reviewer/architect 병렬, deep review, security-review를 수행한다. 신규 agent 생성한도면 기존 독립 reviewer를 재사용하고 역할 대체 여부를 기록한다. 자기 검토를 독립 리뷰로 주장하지 않는다.
- [ ] docs/dev-cycle/qa/<ID>.md의 필수 행을 실제 UI·요청·응답·transport·파일/환경 증거에 연결한다. 공유 실행을 재사용할 때 각 ID의 검증 대상과 기준 SHA를 명시한다.
- [ ] 기본 성공/실패와 스크린샷을 실제로 열어 확인한다. 합성 비밀의 로그·API·프론트 번들 노출0 및 .env 추적 없음 검사. 외부 CDN 차단은 기능 검증과 분리한다.
- [ ] 구현/QA 증거 커밋과 ID별 아카이브를 남긴 뒤 원본 develop에 fast-forward 통합한다. 원본 package.json SHA 불변 및 소유 PID/포트/fixture 정리를 확인한다. 원본 서비스 재기동/배포는 수행하지 않는다.
