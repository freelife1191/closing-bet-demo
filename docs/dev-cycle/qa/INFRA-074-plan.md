# 재시작 실패 경계 보완 Implementation Plan

Goal: 사용자가 stop/restart 후 실제 결과를 신뢰하고, 정상 의존성 출력은 간결하며 KRX 장애로 import가 실패하지 않는다.
Architecture: 기존 Bash 진입점과 공유 lifecycle helper, 기존 pip/npm 검증, 기존 pykrx 재현 가능 wheel patch를 사용한다. 새 supervisor/서비스 관리자를 도입하지 않는다.
Tech Stack: Bash, Python stdlib, requests, npm.
Spec: 사용자 확인된 오류 전부 보완 요청 및 같은 턴 bounded 설계.

## Constraints
- 사용자 root package.json, 원본 env/data/venv/node_modules 및 3500/5501 보존.
- 모든 real 동작은 임시 루트/포트. 비용·발송·AI 없음. 원격 Linux 서버 복구는 직접 검증하지 못했음을 명시.
- 원격 systemd/Supervisor unit을 추측하거나 임의 종료하지 않는다. 충돌 진단 후 관리 경로 안내.

## Tasks
- [ ] lifecycle: stop/restart 공유 소유권·포트 확인, 종료 실패/재점유에서 차단, 기동 HTTP 확인, 로그 append, scheduler lock 삭제 제거. RED→GREEN.
- [ ] dependencies: Python quiet 검증, npm 최초/변경/설치불량 사유 구분, 정상 로그 축약 및 오류 보존. 최초/반복/lock변경/실패 회귀.
- [ ] KRX: HTTP/비JSON/잘못된 응답/network 실패를 인증 실패로 반환, 비밀 출력 제거, 새 local version wheel 재빌드. 정상 및 hostile transport 회귀.
- [ ] 통합: 기존 shell contract 조정이 필요한 경우 바뀐 사용자 계약 근거로 수정. 회귀 기대를 실패 숨김으로 완화하지 않는다.
- [ ] 리뷰/전체 테스트/UltraQA 실행·정리·커밋/아카이브.

## Review focus
포트 PID가 숨겨진 권한환경, supervisor 재생성, PID 재사용/동시 호출, 정상 frontend stamp 없는 최초 기동, HTML200와 HTTP403 및 duplicate login 실패.

## Lifecycle 상세 계약 (critic 반영)
- 새 실행은 실제 launcher PID/시작 식별자/역할/root를 기록하고 signal 전 재검증한다. frontend grep 파이프라인을 없애 launcher를 직접 추적한다.
- 최초 이전 실행 인수는 같은 UID, 정확한 프로젝트 cwd, 예상 gunicorn/Next argv가 모두 맞을 때만 허용한다. 다른 사용자·경로·확인 불가 PID는 건드리지 않고 실패한다.
- restart/stop은 동일 파일의 커널 flock을 공유한다(Python stdlib fcntl, 셸 FD9). 중복 획득은 거부하며 비정상 종료 시 커널이 자동 해제한다. 서비스 자식은 FD9를 닫아 잠금을 상속하지 않는다. PID 기록은 서비스 identity 확인에만 사용한다.
- TERM 후 유한 대기, 필요 시 같은 identity 재검증 후 KILL. 포트 해제가 되지 않거나 supervisor가 재점유하면 중복 실행하지 않는다. 관리자 unit을 추측해서 stop하지 않는다.
- backend GET /api/kr/market-gate 200 JSON, frontend GET / 200 또는 앱의 실제 정상 redirect를 유한 시간 내 확인한다. 실행 child가 살아 있고 listening PID가 그 child/자손인 경우만 인정한다. 타 PID HTTP200은 실패다.
- 부분 기동 실패면 이번에 시작한 child만 종료하고 새 PID 기록/owned lifecycle lock을 정리한다. 이전 로그는 append 보존한다. scheduler.lock 삭제 금지.
- 순서 확정: 공유 lifecycle lock → 양쪽 포트·소유권 진단 → 해당 프로젝트 서비스 정상 중지·포트 해제 확인 → 의존성 동기화 → 성공 시 기동. 활성 venv/node_modules를 교체하지 않는다. 설치 실패는 서비스를 내린 상태로 사실대로 출력하며 atomic 배포/rollback은 추가하지 않는다.

## KRX 상세 계약
최초/CD011 POST 모두 HTTP 오류, 비JSON, 비dict/missing code를 False로 처리한다. 실패 refresh는 이전 인증 플래그 및 쿠키를 남기지 않는다. 로그는 유형/상태만 기록하고 ID/암호/본문/서버 error_message는 출력하지 않는다. 새 wheel local version, requirements pin, builder, SHA, README 일치와 재현 빌드를 검증한다.

잠금 FD는 동기 의존성 설치 자식에도 유지한다. 부모가 중단돼도 설치가 진행 중이면 다음 재시작과 패키지 변경이 겹치지 않게 하기 위함이다. 정상 장기 실행 서비스는 FD를 닫는다. 설치 hook이 별도 daemon을 남기는 배포는 지원하지 않는다.
