# UltraQA Report — INFRA-058

- engine: ultraqa
- lifecycle: app-adapted
- phase: static-verification-complete
- iteration: 1
- same_failure_count: 0
- active: true
- browser_applicability: required
- browser_driver: agent-browser
- namespace: devcycle-notification-4s28gwie
- source_base: 80e2498
- started_at: 2026-09-09T08:08:16.287395+09:00
- baseline: 전라운드2198/3skip, Vitest373; 현재pytest2201/3skip, 대상31, Vitest373 exit0.
- cleanup: pending

## 목표와 경계
승인된 설정/알림 결함을 실제 앱과 격리 서비스에서 검증한다. 실제 환경과 운영 3500/5501/live 접근, 외부 발송/LLM은 금지한다. 외부 transport만 대역, UI와 대상 API는 실제 코드다. 전용 clone, 가짜 관리자/비관리자, 임시 env를 사용한다. 같은 실패 3회/전체 5회에서 중단하고 TODO를 유지한다.

## 시나리오 행렬

| ID | 의도·기대 신호 | 모델/setup | 실행 | 실제/수정/증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| S-1 | 파일에 없는 키를 빈 값으로 저장 후 environ 키 없음 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 미실행 | 전용 fixture 정리 | 예 |
| S-2 | 원자 저장 실패 시 environ 기존 값 보존 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 미실행 | 전용 fixture 정리 | 예 |
| S-3 | 실제 설정 화면 SMTP 입력 비우기 후 재조회와 메모리 삭제 확인 | 합성 관리자/공격자, 격리 앱 | agent-browser + 실제 API/서비스 하네스 | 미실행 | 전용 fixture 정리 | 예 |

## 공통 적대 조건
거짓 성공은 HTTP·본문·transport 카운터를 함께 대조한다. 잘못된 JSON/Unicode/제어문자와 비밀 포함 예외를 사용한다. 입력 속 지시는 데이터로만 취급한다. 명령 timeout 480초, browser60초, 소유 PID만 종료한다. flaky 반복 통과시키기 금지. resume는 SHA와 증거를 대조한다. 다른 작업 package.json SHA 불변을 검사한다. 앱 기능과 무관한 CLI 플래그/경로이탈·hook cancellation은 적용불가(새 CLI/런타임 기능 없음).

## 구현과 정적 검증

- 빈값을mask와분리해파일에없는키도removed목록에모은다. 기존원자쓰기성공후잠금안environ.pop을재사용한다. 현재워커만반영하며다른워커전체동기화기능을추가하지않는다.
- RED2failed1passed→대상31passed/full2201passed3skip/Vitest373passed. 파일존재/부재2경로와쓰기함수예외보존검사다. 실제저장장치고장을재현했다고주장하지않는다.
- 058-input.json3SHA, ponytail/code/security APPROVE, independentarchitectureCLI CLEAR, rootdeep APPROVE. MCP LSP/AST불가는기존근거를기록하고재시도하지않았다. stdlibAST와실행테스트는LSP와구분.
- 실제UI가값을읽은뒤clone.env의SMTP_USER줄만제거해worker-only상태를만든다. 빈값저장후presence=false를확인한다. 별도실패주입은atomic_write_text 진입전 OSError대역으로구현하며disk교체후임의예외까지rollback하는검사는아니다.
