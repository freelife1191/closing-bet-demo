# INFRA-074 Code Review

## 판정

**APPROVE** — 요구사항과 root-cause 경계를 충족하며 CRITICAL/HIGH 차단점은 없다.

- Files reviewed: 8
- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 1
- Scope: `restart_all.sh`, `stop_all.sh`, `scripts/service_lifecycle.sh`,
  `scripts/sync_dependencies.sh`, 관련 `tests/scripts` 4개
- 제외: KRX vendor wheel/transport 변경은 별도 security lane 소관이다.

## Stage 1 — 요구사항 적합성

통과했다.

- stop/restart가 같은 FD 9 `fcntl.flock`을 사용하고 서비스 자식은 FD 9를 닫는다.
- 포트 점유 PID를 확인할 수 없으면 실패하며, 같은 사용자·정확한 서비스 cwd·예상 argv와
  시작 식별자가 일치하는 프로세스만 legacy 관리 대상으로 전환한다.
- TERM 뒤 실제 master 종료를 확인하고, KILL 직전 PID 시작 식별자와 서비스 identity를
  다시 검사한다. 새 PID로 재점유되면 systemd/supervisor 진단과 함께 중단한다.
- 의존성 동기화가 끝난 뒤 두 포트를 다시 확인하고 각 spawn 직전에도 필요한 포트를
  확인하므로, 동기화 중 supervisor가 재점유한 포트에 Gunicorn/Next를 중복 기동하지 않는다.
- 준비 판정은 launcher 생존·기록된 시작 식별자·listener 자손 관계·HTTP 응답을 함께
  검사한다. 프론트 준비 중 백엔드가 죽는 경우도 최종 양쪽 재검사에서 `Ready!`를 거부한다.
- 실패 정리는 이번 셸의 active child와 identity만 대상으로 하며 외부 listener를 종료하지
  않는다. 로그는 append하고 `services/scheduler.lock`은 삭제하지 않는다.
- pip 정상 반복 출력과 npm 정상 설치 소음은 축약하지만 pip/npm 실패 원문과 비정상 종료
  상태는 보존한다. 실패를 성공이나 빈 기본값으로 바꾸는 masking fallback은 없다.

초기 리뷰에서 발견한 실행 비트 손실, 동기화 중 포트 재점유 경합, 광범위한 argv/cwd 매칭,
master 미종료 성공 판정, 완료된 shell job PID 오인 가능성은 최종 코드에서 모두 제거됐다.

## Stage 2 — 품질·보안

### [LOW] 완료 job 회귀 테스트가 실제 unreaped job 상태를 만들지 않는다

- File: `tests/scripts/test_lifecycle_adversarial.py:355`
- Issue: 테스트가 `wait`로 job을 먼저 회수한 뒤 inactive 경로를 검사하므로, 구현이 다시
  `jobs -p`로 바뀌어 완료됐지만 아직 회수되지 않은 job까지 active로 보는 회귀를 직접
  검출하지는 못한다.
- Risk: 현재 구현은 `jobs -pr`와 `jobs -ps`만 수집해 안전하고 별도 실측도 통과했으므로
  런타임 결함은 아니다. 다만 이후 유지보수에서 같은 PID 오인 문제가 재발할 수 있다.
- Fix: 짧은 background child가 끝날 때까지 기다리되 `wait`로 회수하지 않은 상태에서
  `jobs -p`에는 남고 `lifecycle_active_job`에는 없음을 검사한다.

그 밖의 security/root-cause blocker는 없다. 하드코딩 시크릿, 빈 예외, 실패 삼키기,
외부 PID broad kill, 성공으로 내리는 호환 fallback은 발견하지 못했다.

## 검증

- `bash -n restart_all.sh stop_all.sh scripts/service_lifecycle.sh scripts/sync_dependencies.sh`: PASS
- 격리 pytest: **81 passed in 17.70s**
  - `tests/scripts/test_service_lifecycle.py`
  - `tests/scripts/test_lifecycle_adversarial.py`
  - `tests/scripts/test_sync_dependencies.py`
  - `tests/scripts/test_next_environment.py`
- 마지막 cleanup 보완 뒤 lifecycle 재검증: **22 passed in 4.33s**
- 완료됐지만 unreaped 상태의 실제 Bash job이 `jobs -p`에는 남고
  `lifecycle_active_job`에는 포함되지 않으며 TERM marker가 생성되지 않는 reviewer 실측: PASS
- ShellCheck: error/warning 없음. SC2015/SC2086/SC2181 정보·스타일 진단만 존재하며,
  두 SC2086 위치의 값은 앞 단계에서 숫자로 검증한 PID 목록의 의도적 분리다.
- basedpyright: 새 lifecycle 테스트 파일에는 type error 없음. 기존
  `test_next_environment.py`의 넓은 JSON `object` 타입 관련 진단은 변경 줄 밖의 baseline이며,
  이번 한 줄 helper 복사 변경에서 새 type error는 없다.
- `git diff --check`: PASS

원본 3500/5501 서비스, `.env`, `data`, 원본 `venv/node_modules`는 이 리뷰에서 실행하거나
변경하지 않았다. 원격 Linux에서 supervisor unit 이름과 실제 재시작 정책은 이 저장소만으로
확정할 수 없지만, 재점유 시 중복 기동하지 않고 운영자에게 해당 관리자를 확인하도록
실패하는 계약은 검증했다.

## Freeze hashes

```text
0c5a27f5f4fe68d1cbb9a56da4f392c98a3645d272c2ff16dcded4e63ae1ed11  restart_all.sh
51d75910fa62c5476c4c54a02b9e29b71b470528b4e5c739347308164fe5b38c  stop_all.sh
028f929c5abbaf5a57202dda77976f856a512250ef186648a57b5a334e7d6d0a  scripts/service_lifecycle.sh
ecd34f67ab25b8f83cf9945579cd3d42be56d6647f6c080b391dd177bf090e70  scripts/sync_dependencies.sh
958db7fbf304543f816f41597b4e58caf71c67c166d72da4eb21e35e9d04fa1b  tests/scripts/test_service_lifecycle.py
d04bbf3986fd86a917c7c6df7e9902a39041d5aae78183e622b7b62ff6c867ee  tests/scripts/test_lifecycle_adversarial.py
59c1139c65469bc8f3f6b45edbdc72c69a5a9cd04ed44ba66d29111899cbca26  tests/scripts/test_sync_dependencies.py
e8a9040bff6febd7260437b9ec5189d6adf4cc607e94977bc4e1c1136bfabfea  tests/scripts/test_next_environment.py
```
