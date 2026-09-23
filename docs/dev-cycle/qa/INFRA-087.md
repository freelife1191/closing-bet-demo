# [INFRA-087] 기동 스크립트와 문서에서 systemd 관련 부분 제거 — QA 시나리오

- 대상: 격리 사본의 `./stop_all.sh` 가 기존 backend 점유자를 입양해 종료하는 CLI 흐름과, 종료 직후 되살아나는 점유자에 대한 반응
- 구성 근거: `[INFRA-087]` 설계 승인(2026-09-24 00:55, systemd 입양 거부 장치·테스트·문서 절 제거, 운영 문서는 `deploy/README.md` 로 이동) + 심층 리뷰(critic) 보류 1(재점유 감지는 관측 창 안에서만 성립)
- 구성 2026-09-24 01:03 | 실행 (미실행)
- 검증 기준 커밋: (첫 커밋 뒤 기록)
- QA 엔진(engine): Claude Code. 화면 없이 셸 스크립트만 바뀌었고 사용자 진입 흐름은 터미널 명령이다. browser_applicability: not-applicable, browser_driver: none. 하네스:
  첫 커밋 **뒤에** `git archive HEAD` 로 scratchpad 에 사본을 만들고 추적 파일 때문에 생긴 `data/` 를 지운 뒤 빈 `data/` 를 새로 만든다. 사본의 `secrets/` 는 만들자마자 지운다. `venv` 는 `cp -c -R` 로 APFS clone 한다. 사본 `.env` 에는 비밀 없이 `FLASK_PORT=58151`, `FRONTEND_PORT=58152` 두 줄만 둔다(값이 없으면 스크립트가 3500·5501 을 쓰므로 반드시 둔다).
  backend 점유자는 사본 cwd 에서 `env -i` 로 `SCHEDULER_ENABLED=false` 와 더미 `INTERNAL_IDENTITY_SECRET`·`ADMIN_EMAILS` 만 주고 `<사본>/venv/bin/gunicorn flask_app:app --bind 127.0.0.1:58151 --workers 2 --threads 8 --timeout 120 --keep-alive 0` 으로 띄운다. PID 파일은 만들지 않는다(입양 대상).
  `restart_all.sh` 는 의존성 동기화(pip·npm)를 돌리므로 실행하지 않는다. restart 의 거부 전파는 pytest(`test_entrypoints_refuse_unmanaged_listener_without_claiming_success[restart_all.sh]`)가 맡는다.
  원본 `data/`·`logs/`·3500·5501·운영 주소는 건드리지 않고 LLM·발송·저장 조작은 하지 않는다
- 기대값 출처: 설계 승인 범위, `scripts/service_lifecycle.sh` 의 입양 문구(「관리 대상으로 전환했습니다」)와 재점유 문구(「다시 점유했습니다」), `stop_all.sh` 의 성공 문구(「종료되었습니다」)
- 단계(phase): 시나리오 구성 완료 | 실행 대기
- 반복(iteration): 0
- 필수 여부(required): 예
- 결과: (미실행)
- 증거: (미실행)
- 정리(cleanup): (미실행)

## 시나리오

### S-1. PID 기록 없는 기존 backend 를 입양해 종료한다 (회귀)
- 조작: 사본에서 위 gunicorn 을 띄우고 58151 이 열릴 때까지 기다린 뒤 사본에서 `./stop_all.sh` 를 실행한다.
- 기대: exit 0, stderr 에 「관리 대상으로 전환했습니다」, stdout 에 「종료되었습니다」, 실행 뒤 58151 리스너 0, 출력에 `cgroup`·`systemd` 없음.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-2. 비어 있는 포트에서 종료는 성공한다 (경계)
- 조작: S-1 뒤 같은 사본에서 `./stop_all.sh` 를 한 번 더 실행한다.
- 기대: exit 0, 「종료되었습니다」, 두 포트 리스너 0.
- 필수 여부(required): 예
- 실제:
- 결과:

### S-3. 종료 직후 되살리는 관리자에 대한 반응 (관측)
- 조작: 사본 cwd 에서 gunicorn 이 끝나면 곧바로 다시 띄우는 `while` 루프를 백그라운드로 돌리고, 58151 이 열리면 `./stop_all.sh` 를 실행한다. 끝나면 루프와 gunicorn 을 내린다.
- 기대: 판정 대상이 아닌 관측이다. 되살림이 종료 대기 창 안이면 「다시 점유했습니다」와 비영점, 창 밖이면 성공 문구 뒤 포트가 다시 열린다. 어느 쪽이든 결과를 그대로 기록한다. 심층 리뷰 보류 1 과 `deploy/README.md` 의 「다른 실행 관리자와 병행하지 않습니다」가 이 한계를 운영 규칙으로 다룬다.
- 필수 여부(required): 아니오
- 실제:
- 결과:

## 실행 결과

- (미실행)
