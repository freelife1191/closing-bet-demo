# [INFRA-087] 기동 스크립트와 문서에서 systemd 관련 부분 제거 — QA 시나리오

- 대상: 격리 사본의 `./stop_all.sh` 가 기존 backend 점유자를 입양해 종료하는 CLI 흐름과, 종료 직후 되살아나는 점유자에 대한 반응
- 구성 근거: `[INFRA-087]` 설계 승인(2026-09-24 00:55, systemd 입양 거부 장치·테스트·문서 절 제거, 운영 문서는 `deploy/README.md` 로 이동) + 심층 리뷰(critic) 보류 1(재점유 감지는 관측 창 안에서만 성립)
- 구성 2026-09-24 01:03 | 실행 2026-09-24 01:06 (1회차)
- 검증 기준 커밋: `33cf316` (첫 커밋, 01:06). 사본은 이 커밋의 `git archive HEAD` 이며 사본의 `service_lifecycle.sh` 에 `cgroup` 0건임을 확인했다. 실행 중 범위 파일은 바뀌지 않았다
- QA 엔진(engine): Claude Code. 화면 없이 셸 스크립트만 바뀌었고 사용자 진입 흐름은 터미널 명령이다. browser_applicability: not-applicable, browser_driver: none. 하네스:
  첫 커밋 **뒤에** `git archive HEAD` 로 scratchpad 에 사본을 만들고 추적 파일 때문에 생긴 `data/` 를 지운 뒤 빈 `data/` 를 새로 만든다. 사본의 `secrets/` 는 만들자마자 지운다. `venv` 는 `cp -c -R` 로 APFS clone 한다. 사본 `.env` 에는 비밀 없이 `FLASK_PORT=58151`, `FRONTEND_PORT=58152` 두 줄만 둔다(값이 없으면 스크립트가 3500·5501 을 쓰므로 반드시 둔다).
  backend 점유자는 사본 cwd 에서 `env -i` 로 `SCHEDULER_ENABLED=false` 와 더미 `INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 만 주고 `<사본>/venv/bin/gunicorn flask_app:app --bind 127.0.0.1:58151 --workers 2 --threads 8 --timeout 120 --keep-alive 0` 으로 띄운다. PID 파일은 만들지 않는다(입양 대상).
  `restart_all.sh` 는 의존성 동기화(pip·npm)를 돌리므로 실행하지 않는다. restart 의 거부 전파는 pytest(`test_entrypoints_refuse_unmanaged_listener_without_claiming_success[restart_all.sh]`)가 맡는다.
  원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고 LLM·발송·저장 조작은 하지 않는다
- 기대값 출처: 설계 승인 범위, `scripts/service_lifecycle.sh` 의 입양 문구(「관리 대상으로 전환했습니다」)와 재점유 문구(「다시 점유했습니다」), `stop_all.sh` 의 성공 문구(「종료되었습니다」)
- 단계(phase): 시나리오 구성 완료 | 실행 완료
- 반복(iteration): 1회. 하네스 실수 없음. 계보 출력의 `└` 가 화면에서 깨져 보였으나 함수 출력 바이트는 변경 전후·C/UTF-8 로캘 모두 `e2 94 94` 로 정상이었다(표시 과정의 문제, 결함 아님)
- 필수 여부(required): 예
- 결과: 통과 (필수 2/2, 관측 1건)
- 증거: 아래 각 시나리오의 「실제」 줄(명령 출력 원문). 원문 파일은 scratchpad `s1.*`·`s2.*`·`s3.*`(세션 임시). 기준 상태 58151·58152·3500·5501 리스너 0, 사본 `data/` 비어 있음, `secrets/` 없음, venv inode 원본 407795279 / 사본 906410847. CLI 만 바뀌어 스크린샷은 없다
- 정리(cleanup): 되살림 루프를 중지 파일로 멈추고 그 자식 gunicorn 마스터(PID 78848)를 TERM 으로 내렸다. `pgrep -fl infra087` 0건, 58151·58152·3500·5501 리스너 0, 사본·루프 스크립트 삭제 뒤 `ls` 로 없음 확인. 원본 `data/`·`logs/`·3500·5501 은 건드리지 않았고 작업 트리 변경 없음

## 시나리오

### S-1. PID 기록 없는 기존 backend 를 입양해 종료한다 (회귀)
- 조작: 사본에서 위 gunicorn 을 띄우고 58151 이 열릴 때까지 기다린 뒤 사본에서 `./stop_all.sh` 를 실행한다.
- 기대: exit 0, stderr 에 「관리 대상으로 전환했습니다」, stdout 에 「종료되었습니다」, 실행 뒤 58151 리스너 0, 출력에 `cgroup`·`systemd` 없음.
- 필수 여부(required): 예
- 실제: 01:06:49 사본에서 띄운 gunicorn 이 58151 을 점유(PID 76845·77094·77095, `logs/` 없음). `./stop_all.sh` exit 0(01:06:52). stderr 「ℹ️  기존 backend PID 76845 를 같은 사용자·프로젝트·명령으로 확인해 관리 대상으로 전환했습니다.」, stdout 「🛑 backend PID 76845 를 정상 종료합니다...」「✅ 이 프로젝트가 관리하던 서비스가 종료되었습니다.」. 실행 뒤 58151 리스너 0, 출력의 `cgroup|systemd` 0건
- 결과: 통과

### S-2. 비어 있는 포트에서 종료는 성공한다 (경계)
- 조작: S-1 뒤 같은 사본에서 `./stop_all.sh` 를 한 번 더 실행한다.
- 기대: exit 0, 「종료되었습니다」, 두 포트 리스너 0.
- 필수 여부(required): 예
- 실제: 01:07:02 exit 0, 「✅ 이 프로젝트가 관리하던 서비스가 종료되었습니다.」, 58151·58152 리스너 0
- 결과: 통과

### S-3. 종료 직후 되살리는 관리자에 대한 반응 (관측)
- 조작: 사본 cwd 에서 gunicorn 이 끝나면 곧바로 다시 띄우는 `while` 루프를 백그라운드로 돌리고, 58151 이 열리면 `./stop_all.sh` 를 실행한다. 끝나면 루프와 gunicorn 을 내린다.
- 기대: 판정 대상이 아닌 관측이다. 되살림이 종료 대기 창 안이면 「다시 점유했습니다」와 비영점, 창 밖이면 성공 문구 뒤 포트가 다시 열린다. 어느 쪽이든 결과를 그대로 기록한다. 심층 리뷰 보류 1 과 `deploy/README.md` 의 「다른 실행 관리자와 병행하지 않습니다」가 이 한계를 운영 규칙으로 다룬다.
- 필수 여부(required): 아니오
- 실제: 01:07:03 루프가 띄운 PID 78407 이 58151 점유. `./stop_all.sh` exit 1(01:07:14). 78407 을 입양해 TERM 한 뒤 루프가 01:07:05 에 띄운 새 PID 78848 을 대기 창 안에서 잡아 「❌ backend 종료 뒤 새 PID 78848 가 포트 58151 를 다시 점유했습니다.」와 계보(78848 → 루프 bash 78401 → launchd)를 출력했고 성공 문구는 없었다. 3초 뒤에도 78848 이 포트를 쥐고 있었다. 이번 관측은 되살림 지연이 약 2초로 창 안이었다. 창보다 긴 지연은 잡지 못하며 그 한계는 `deploy/README.md` 의 병행 금지 문단이 다룬다
- 결과: 관측 기록(판정 대상 아님)

## 실행 결과

- 1회차(2026-09-24 01:06, 기준 `33cf316`): 필수 2/2 통과, 관측 1건 기록
- 이월한 발견: 없음
