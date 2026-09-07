# [INFRA-044] 인가 근거가 된 `ADMIN_EMAILS` 의 보호 — QA 시나리오

- 대상: `services/common_env_service.py` 의 `update_env_file` 과 `read_masked_env_vars`,
  그리고 그것을 부르는 `POST /api/system/env` (`app/routes/common_update_routes.py:219-252`)
- 구성 근거: `oh-my-claudecode:security-reviewer`(`infra044-security`)가 찾은 값 개행 주입
  결함 [F1] 과 이번 사이클의 변경 두 파일
- 구성 2026-09-08 00:05 | 실행 2026-09-08 00:08
- QA 엔진(engine): 안전한 파이썬 하네스 + Flask 테스트 클라이언트
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회
- baseline 상태: 기준값 수집 완료 (결함 재현으로 확인)
- 필수 여부(required): 예
- 결과: 통과
- 증거: 아래 각 시나리오
- 정리(cleanup): 임시 디렉터리만 사용하며 실행 후 자동 삭제된다

## 화면 대신 하네스를 쓰는 이유

이 경로의 화면은 설정 모달(`SettingsModal.tsx`)의 「저장」 버튼이다. 그 버튼을 누르면
**운영 `.env` 가 실제로 다시 쓰인다.** 이 사이클의 안전 제약이 그 조작을 금지하므로,
`tier-rules.md` §1-1 이 정한 「화면이 없는 경로는 해당 CLI·안전한 하네스를 검사 대상으로
삼는다」에 따라 `update_env_file` 을 임시 디렉터리에 대해 직접 부른다. 운영 `.env` 는 이
사이클에서 한 번도 쓰기 대상이 되지 않았다.

HTTP 계층은 `.env` 를 건드리지 않는 거부 경로(S-11)만 실제로 친다.

## 시나리오

### S-1. 개행 주입이 기존 줄 갱신 경로에서 막힌다 (회귀)
- 조작: `.env` 에 `ADMIN_EMAILS=owner@example.com` 과 `SMTP_HOST=old` 를 두고
  `update_env_file` 에 `{"SMTP_HOST": "smtp.example.com\nADMIN_EMAILS=attacker@example.com"}` 을 준다.
- 기대: `.env` 에 `ADMIN_EMAILS=attacker@example.com` 줄이 생기지 않는다. 원래의
  `ADMIN_EMAILS=owner@example.com` 이 그대로 남고, `SMTP_HOST` 도 `old` 그대로다.
  `environ` 에 `SMTP_HOST` 가 들어가지 않는다.
- 필수 여부(required): 예
- 실제: `.env` 가 `ADMIN_EMAILS=owner@example.com\nSMTP_HOST=old\n` 그대로였다. `attacker@example.com` 줄이 생기지 않았고 `environ` 도 비어 있었다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-2. 개행 주입이 새 키 추가 경로에서 막힌다 (회귀)
- 조작: `.env` 에 `SMTP_HOST=old` 만 두고
  `{"EMAIL_RECIPIENTS": "a@b.c\nADMIN_API_TOKEN=forged"}` 를 준다. `EMAIL_RECIPIENTS` 는
  파일에 없으므로 `update_env_file` 의 140-149행 덧붙이기 경로를 지난다.
- 기대: `.env` 마지막에 `ADMIN_API_TOKEN=forged` 가 붙지 않는다. `EMAIL_RECIPIENTS` 줄
  자체도 생기지 않는다.
- 필수 여부(required): 예
- 실제: `.env` 가 `SMTP_HOST=old\n` 그대로였다. `ADMIN_API_TOKEN` 도 `EMAIL_RECIPIENTS` 도 붙지 않았다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-3. 캐리지리턴 주입도 막힌다 (회귀)
- 조작: `{"SMTP_USER": "u@example.com\rADMIN_EMAILS=attacker@example.com"}` 을 준다.
- 기대: `ADMIN_EMAILS` 줄이 생기지 않는다. `\n` 만 막고 `\r` 를 놓치면 `.env` 를 읽는
  파서에 따라 같은 주입이 성립한다.
- 필수 여부(required): 예
- 실제: `.env` 가 `ADMIN_EMAILS=owner@example.com\n` 그대로였고 `SMTP_USER` 줄이 생기지 않았다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-4. 인가 키를 직접 지정해도 쓰이지 않는다 (회귀)
- 조작: `{"ADMIN_EMAILS": "attacker@example.com", "ADMIN_API_TOKEN": "forged"}` 를 준다.
- 기대: `.env` 의 `ADMIN_EMAILS` 가 그대로이고 `ADMIN_API_TOKEN` 줄이 생기지 않는다.
  `environ` 에도 둘 다 들어가지 않는다. `[INFRA-025]` 가 세운 보장의 회귀 검사다.
- 필수 여부(required): 예
- 실제: `.env` 의 `ADMIN_EMAILS` 가 `owner@example.com` 그대로였고 `ADMIN_API_TOKEN` 줄은 없었다. `environ` 은 빈 딕셔너리였다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-5. 읽기 응답에 인가 키가 실리지 않는다 (회귀)
- 조작: `.env` 에 `ADMIN_EMAILS`·`ADMIN_API_TOKEN`·`SMTP_PORT=587` 을 두고
  `read_masked_env_vars` 를 부른다.
- 기대: 결과 딕셔너리에 `ADMIN_EMAILS` 와 `ADMIN_API_TOKEN` 이 없고 `SMTP_PORT` 는
  `587` 로 들어 있다. 뒤의 것을 함께 재지 않으면 「전부 거르는 코드」도 통과한다.
- 필수 여부(required): 예
- 실제: 결과가 `{'SMTP_PORT': '587'}` 하나뿐이었다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-6. 정상 값이 기존 줄 갱신 경로로 반영된다 (인접)
- 조작: `.env` 에 `SMTP_HOST=old` 를 두고 `{"SMTP_HOST": "smtp.gmail.com"}` 을 준다.
- 기대: `.env` 가 `SMTP_HOST=smtp.gmail.com` 이 되고 `environ["SMTP_HOST"]` 도 같은 값이다.
  개행 검사를 넣으면서 정상 저장까지 막지 않았는지 재는 자리다.
- 필수 여부(required): 예
- 실제: `.env` 가 `SMTP_HOST=smtp.gmail.com` 이 되었고 `environ['SMTP_HOST']` 도 같았다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-7. 정상 값이 새 키 추가 경로로 반영된다 (인접)
- 조작: 파일에 없는 `{"TELEGRAM_CHAT_ID": "123456"}` 을 준다.
- 기대: `.env` 마지막에 `TELEGRAM_CHAT_ID=123456` 이 붙고 `environ` 에도 들어간다.
- 필수 여부(required): 예
- 실제: `.env` 마지막에 `TELEGRAM_CHAT_ID=123456` 이 붙었고 `environ` 에도 들어갔다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-8. 마스킹 값은 기존 값을 유지한다 (인접)
- 조작: `.env` 에 `OPENAI_API_KEY=secret-value` 를 두고 `{"OPENAI_API_KEY": "****"}` 를 준다.
- 기대: `.env` 의 값이 `secret-value` 그대로다. 조회 응답을 그대로 되보내는 화면 동작이
  실제 키를 별표로 덮어쓰지 않게 하는 장치다.
- 필수 여부(required): 예
- 실제: `.env` 의 `OPENAI_API_KEY` 가 `secret-value` 그대로였다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-9. 빈 값은 키를 지운다 (인접)
- 조작: `.env` 에 `SMTP_USER=someone` 을 두고 `{"SMTP_USER": ""}` 를 준다.
- 기대: `.env` 에서 `SMTP_USER` 줄이 사라지고 `environ` 에서도 빠진다.
- 필수 여부(required): 예
- 실제: `.env` 에서 `SMTP_USER` 줄이 사라졌고 `environ` 에서도 빠졌다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-10. 주석과 목록 밖 키가 보존된다 (인접)
- 조작: `.env` 에 `# 주석`, `GOOGLE_API_KEY=keep-me`(허용 목록 밖), `SMTP_PORT=25` 를
  두고 `{"SMTP_PORT": "587"}` 을 준다.
- 기대: 주석 줄과 `GOOGLE_API_KEY=keep-me` 가 그대로 남고 `SMTP_PORT` 만 `587` 이 된다.
  필터가 목록 밖 키를 지우는 방식으로 동작하지 않는 것을 확인한다.
- 필수 여부(required): 예
- 실제: `# 주석` 과 `GOOGLE_API_KEY=keep-me` 가 남았고 `SMTP_PORT` 만 `587` 이 되었다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044.py` 실행 출력
- 정리(cleanup): 임시 디렉터리

### S-11. 토큰 없는 요청은 `.env` 에 닿지 못한다 (인접)
- 조작: Flask 테스트 클라이언트로 `X-Admin-Token` 없이
  `POST /api/system/env` 에 `{"SMTP_HOST": "x\nADMIN_EMAILS=attacker@example.com"}` 를 보낸다.
- 기대: 403 이 돌아오고 본문은 `{"error": "Forbidden"}` 이다. 게이트가 앞에 서므로
  파일 쓰기 함수까지 가지 않는다.
- 필수 여부(required): 예
- 실제: 403 과 `{'error': 'Forbidden'}` 이 돌아왔다. 게이트가 앞에 서므로 파일 쓰기 함수까지 가지 않았다.
- 결과: 통과
- 증거: `scratchpad/qa_infra044_s11.py` 실행 출력
- 정리(cleanup): 실제 `.env` 를 건드리지 않는 거부 경로만 친다

## 이월한 발견

보안 리뷰가 이번 변경의 범위 밖에서 찾은 것 둘을 백로그로 올렸다.

- [F2] `POST /api/kr/config/interval`(`app/routes/kr_market.py:155`)에 관리자 게이트가 없고
  `services/kr_market_interval_service.py:22` 가 `.env` 전체를 다시 쓴다 → `[INFRA-042]`.
  값은 `int()` 변환과 1..1440 범위 검사를 거치므로 내용 주입은 되지 않으나, 인증 없는
  요청이 서버 설정 파일을 다시 쓰고 스케줄러 주기를 바꾸는 것 자체가 남는다. 게이트
  표준화 항목이 이미 있으므로 그 목록에 넣었다.
- [F3] `.env` 쓰기의 원자성 부재 → `[INFRA-050]`. `update_env_file` 은
  `open(env_path, "w")` 로 직접 덮어쓰는데 [F2] 의 경로는 `atomic_write_text` 를 쓴다.
  둘이 겹치면 서로의 갱신을 잃고 부분 기록된 `.env` 가 남을 수 있다. 침해가 아니라
  가용성 문제이고 창이 좁아 별도 항목으로 두었다.

## 실행 결과

- 필수 시나리오: 통과 11 / 전체 11
- 미통과 필수: 없음
- 재개 판정: 완료 가능
- 시나리오 밖에서 새로 발견: 코드 리뷰가 같은 파일에서 더 넓은 결함을 찾았다. `.env` 를
  bash 가 `source` 하므로 허용된 키의 값에 `$(...)` 를 넣으면 **개행 없이도** 다음 기동에서
  임의 명령이 실행된다. 임시 디렉터리에서 재현해 확인했다(`SMTP_HOST=x$(touch ...)` 한 줄로
  파일이 생성되었다). 이번 변경이 만든 결함이 아니고 근본 수정이 쓰기 인용과 기동 스크립트
  양쪽에 걸치므로 `[INFRA-049]`(P0) 로 이월했다. 이번 사이클의 개행 필터는 그것과 별개로
  유효하며, 새 `KEY=VALUE` 줄을 끼워 넣는 경로는 닫혔다.
- 정리(cleanup): 하네스 두 개는 스크래치패드에만 두었고 임시 `.env` 는 전부
  `TemporaryDirectory` 안에서만 만들어져 자동 삭제되었다. 운영 `.env` 는 이 사이클에서
  한 번도 쓰기 대상이 되지 않았다. S-11 은 `SCHEDULER_ENABLED=false` 로 앱을 세워
  스케줄러가 뜨지 않았다.
