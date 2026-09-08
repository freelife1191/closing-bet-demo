# INFRA-043 Task 1 독립 보안 리뷰

## 최종 판정

**APPROVE**

- 기준 커밋: `e4c4fd6c1997`
- 입력 manifest: `043-input-v3.json`
- manifest SHA-256: `945ce9d38b436d741277357f8bdda4aaedfe1f65cf1629fe2dd5c862870c99dc`
- 파일 SHA-256: manifest 9개와 현재 checkout **9/9 일치**
- 검토 파일: 제품 코드 5개, 회귀 테스트 3개, 승인 계획 1개
- 미해결 이슈: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0

## 보안 판정 근거

### 관리자·요청 경계 — OWASP A01/A07

- `app/routes/common_notification_routes.py:137`에서 서명 검증을 거친 `g.user_email`을 `ADMIN_EMAILS`와 대조하며, payload 파싱과 `Messenger` 생성보다 먼저 403으로 차단합니다.
- 익명, 위조 신원, 비관리자, 구형 사용자 헤더, 관리자 목록·신원 비밀 누락, 다른 메서드·경로에서 재사용한 서명은 모두 발송 호출 0건으로 고정되어 있습니다.
- `request.get_json()`을 유지해 simple form POST가 415로 차단됩니다. 알 수 없는 플랫폼도 `Messenger`가 환경 자격 증명을 읽기 전에 400으로 끝납니다.

### disabled·불리언 결과 경계 — OWASP A04/A05

- `engine/messenger.py:87`–`engine/messenger.py:121`의 facade와 `engine/messenger_senders.py:43`–`engine/messenger_senders.py:142`의 직접 sender 모두 `config.disabled`를 transport 이전에 검사합니다. 우회 가능한 직접 sender 경로에서도 False와 호출 0건이 확인됩니다.
- custom Telegram/Discord 경로도 `engine/messenger.py:179`–`engine/messenger.py:232`에서 disabled, 원격 HTTP 실패, 예외를 False로 보존합니다.
- API는 disabled 503, sender False 502, 예상치 못한 예외 500과 고정 문구, 실제 성공만 200으로 구분합니다. broad catch가 성공으로 바꾸거나 조용한 기본 성공을 반환하는 masking fallback은 없습니다.
- `NOTIFICATION_ENABLED` 해석은 실제 `MessengerConfig`에서 대소문자를 제외하고 정확한 `true`만 활성화하고, `false` 및 다른 문자열은 비활성 처리합니다. 이번 Task 1은 기존 설정 생명주기·워커 재기동 계약을 바꾸지 않습니다.

### 시크릿·로그·오류 경계 — OWASP A02/A05/A09

- sender, custom sender, notifier channel, notifier outer catch, screener builder outer catch, route outer catch는 예외 객체·`str(error)` 대신 예외 타입명만 기록합니다.
- HTTP 상대 실패는 status code만 기록하고 원격 response body를 로그에 넣지 않습니다. route의 예외 응답은 `Notification request failed`, 발송 실패는 `Notification delivery failed`로 고정되어 자격 증명이나 provider 오류 원문을 반환하지 않습니다.
- 합성 canary가 webhook URL, Telegram token, SMTP password, transport 예외 메시지와 원격 body에 들어간 회귀에서 API body와 `caplog` 모두 canary 0건입니다.
- 지정 파일 정적 시크릿 패턴에서 실제 키·토큰·private key를 찾지 못했습니다. 테스트 값은 명시적인 fake canary입니다. `git ls-files`에서 추적되는 `.env*`는 `.env.example`뿐입니다.

### 주입·SSRF 범위 — OWASP A03/A10

- 셸 실행, SQL, 파일 경로 조작은 추가되지 않았습니다. transport 주소와 수신자는 서버 환경 설정에서만 오며 요청 body는 allowlist된 platform 선택에만 사용됩니다.
- 외부 HTTP/SMTP 실패의 원문을 로그나 응답으로 반사하지 않습니다. 실제 외부 주소 안전성·전달은 후속 격리 QA가 검증할 동적 경계입니다.

## 실제 실행·확인한 검사

- `043-input-v3.json`의 9개 SHA-256과 현재 파일 대조: 모두 일치
- 대상 pytest 5개 파일: **72 passed in 1.46s**
- Python stdlib AST parse: 제품·테스트 8개 파일 모두 성공
- stdlib AST logger argument 점검: 변경 범위의 error/warning 호출을 열거해 예외 원문·response body·자격 증명 인자 사용 없음 확인
- `git diff --check`: 통과
- 지정 9개 파일의 key/private-key 정적 패턴 검색: 실제 시크릿 없음
- 제공된 v3 전체 검증 증거: pytest **2115 passed / 3 skipped**, exit 0
- 제공된 frontend 불변 검증 증거: Vitest **373 passed**, exit 0
- 독립 architecture v3: CLEAR, 독립 code-review v3: APPROVE

## 실행하지 않은 검사

- MCP LSP·ast-grep: 환경의 `Transport closed`가 확정되어 반복 호출하지 않았습니다. stdlib AST와 실제 테스트는 대체 근거이며 LSP PASS로 기록하지 않습니다.
- `npm audit`·외부 CVE 조회: dependency/version 변경이 없어 실행하지 않았고 의존성 취약점 PASS를 주장하지 않습니다.
- 실제 `.env`, `.env.production`, `.env.vertex`, `data/`, 실제 `logs/`: 접근하지 않았습니다.
- 원본·격리 서버 HTTP, 3500/5501, live URL, 실제 LLM·알림·설정 저장·삭제: 실행하지 않았습니다.
- 실제 bundle/log canary와 브라우저 발송 결과: 후속 UltraQA가 검증할 별도 완료 조건이며 이 정적 코드 리뷰를 대체하지 않습니다.

## 남은 동적 확인

후속 격리 QA에서 fake 자격 증명만 사용해 성공·disabled·transport 실패의 실제 HTTP 상태와 transport 호출 수를 확인하고, 실제 캡처 로그·응답·번들에서 canary 0건을 검증해야 합니다. 이 단계는 아직 미실행이므로 배포·완료 증거로 확대하지 않습니다.

## Recommendation

**APPROVE.** 승인된 Task 1 범위에서 관리자 우회, disabled 우회, 성공 오판, 시크릿 로그·오류 응답 노출, 사용자 입력 기반 transport 주소 선택을 발견하지 못했습니다.
