# 운영 서버의 실행 관리

운영 서버(`close.highvalue.kr`)는 2026-09-22 부터 `systemd --user` 유닛 없이 `./restart_all.sh` 와
`./stop_all.sh` 로만 두 서비스를 관리합니다. 앞단의 Caddy 가 `localhost:3500` 으로 리버스 프록시합니다.
macOS 개발 머신과 같은 경로이며, 스크립트에는 플랫폼을 가르는 분기가 없습니다.

## 유닛을 없앤 이유

서버에는 `closing-bet-backend.service`·`closing-bet-frontend.service` 두 유닛이 `Restart=always`,
`StartLimitIntervalSec=0` 으로 같은 스택을 관리하고 있었습니다. 그 유닛은 저장소가 추적하지 않아
`[INFRA-055]`(Next 실행 환경 분리) 이후의 코드와 어긋난 채 방치되었고, `restart_all.sh` 가 포트를
뺏자 systemd 가 5초마다 되찾으려 들어 backend 433회·frontend 823회를 재시작했습니다(`[INFRA-075]`).
두 경로가 같은 포트를 두고 경쟁하므로 하나만 남겨야 했고, 운영자가 스크립트를 남기는 쪽을 골라
유닛을 서버에서 완전히 제거했습니다.

유닛 파일은 커밋 `0125358` 부터 `13952d9` 까지 이 디렉터리에 있었고 `13952d9` 가 서버에 마지막으로
적용됐던 내용입니다. 적용 절차와 확인 명령, U4 의 상세 근거가 담긴 당시 README 도 같은 이력에
있습니다(`git show 13952d9:deploy/systemd/README.md`). 다시 필요해지면 거기서 꺼내되, 아래 「유닛을
다시 만든다면」을 먼저 읽습니다.

## 스크립트로 운영할 때의 대가

`restart_all.sh` 가 띄운 프로세스는 `lifecycle_exec_detached` 가 새 세션으로 분리하므로 ssh
로그아웃에는 살아남습니다. 단, 이것은 logind 의 `KillUserProcesses=no` 를 전제합니다. Ubuntu 의
기본값이 그렇습니다(상류 systemd 는 v230 부터 `yes` 이고 Debian·Ubuntu 가 `no` 로 되돌려 배포합니다).
서버의 실제 유효값은 `busctl get-property org.freedesktop.login1 /org/freedesktop/login1
org.freedesktop.login1.Manager KillUserProcesses` 로 봅니다. `systemd-analyze cat-config
systemd/logind.conf | grep -i KillUserProcesses` 는 override 를 찾는 용도이며, `#KillUserProcesses=no`
주석 줄 하나만 나오면 기본값 그대로라는 뜻입니다.

**재부팅 뒤에는 아무것도 자동으로 뜨지 않고, 프로세스가 죽어도 되살리는 것이 없습니다.** 재부팅 뒤에는
손으로 `./restart_all.sh` 를 실행합니다. 부팅 시 `restart_all.sh` 를 돌리던 `closing-bet-demo-restart.service`
는 유닛 둘과 포트를 다투던 시절에 탐색 경로 밖으로 빼 두었고 내용은 저장소에 없습니다. 자동 기동이
다시 필요해지면 `restart_all.sh` 를 부르는 `Type=oneshot` 유닛에 `RemainAfterExit=yes` 를 함께 두어
만듭니다. 그 줄이 없으면 스크립트가 끝나는 순간 유닛이 비활성이 되고 기본 `KillMode=control-group`
이 같은 cgroup 에 남은 서비스를 정리합니다. setsid 는 cgroup 을 바꾸지 않으므로 분리해 띄워도
여기에 걸립니다. 그런 유닛은 서비스 자체를 관리하는 유닛과 함께 켜지 않습니다.

## 입양 검사

`[INFRA-075]` 부터 `scripts/service_lifecycle.sh` 는 포트 점유자를 관리 대상으로 전환하기 전에
`/proc/<pid>/cgroup` 을 읽어 실행 관리자가 있는지 확인합니다. cgroup 경로가 `*.service` 안이면
유닛 이름과 함께 거부하고 비영점으로 끝납니다. 유닛 이름은 스크립트에 없고 cgroup 에서 읽습니다.

```
❌ PID 3217802 는 systemd 유닛 closing-bet-backend.service 가 관리합니다. 이 스크립트로 교체하지 않습니다.
   다음 명령을 사용하세요: systemctl --user restart closing-bet-backend.service
```

유닛이 없는 지금은 점유자가 로그인 세션 스코프(`session-*.scope`)라 이 검사가 그냥 통과하며,
`/proc` 이 없는 macOS 도 같습니다. 호출자가 점유자와 같은 유닛 안에 있는 경우도 통과합니다.
데스크톱 터미널에서 손으로 띄운 서비스가 그렇고, 그 점유자는 종료해도 되살아나지 않습니다.
Linux 에서 점유자의 cgroup 만 읽지 못하면 허용이 아니라 「알 수 없음」으로 거부합니다. 검사는 지금
포트를 쥔 프로세스만 보므로, 유닛이 `RestartSec` 대기 중이라 포트가 잠시 빈 순간에는 막지 못합니다.
유닛과 스크립트를 함께 쓰지 않는 것이 유일한 해법입니다.

## 유닛을 다시 만든다면

서버에서 실제로 겪은 것들입니다. 하나라도 어기면 같은 사고가 납니다.

- **`restart_all.sh` 와 병행하지 않습니다.** 유닛이 있는 동안 스크립트는 거부만 하고, 없는 동안만
  기동합니다.
- **새 장비에서는 `loginctl enable-linger "$USER"` 를 먼저 켭니다.** 켜져 있지 않으면 `systemd --user`
  유닛이 ssh 세션이 끝날 때 함께 내려갑니다.
- **frontend 유닛에 `After=closing-bet-backend.service` 를 두지 않습니다.** 지난 편입본이 넣었다가 뺀
  것입니다. Next 는 요청이 올 때 Flask 로 프록시하므로 기동 순서가 필요 없습니다.
- **node 는 이 서버에서 `~/n/bin` 에 있습니다.** 마지막 유닛은 `Environment=PATH=/home/ms/n/bin:...`
  와 `ExecStart` 의 `/home/ms/n/bin/npm` 절대 경로로 그것을 찾았습니다. 다시 만들 때는 `%h/n/bin/npm`
  처럼 경로를 명시합니다. 아래 `/bin/bash -lc` 를 버리면 로그인 프로파일이 PATH 에 넣어 주던 것으로
  보이는 그 경로도 사라지므로, 명시하지 않은 유닛은 node 를 찾지 못합니다.
- **`ExecStartPre` 로 `services/scheduler.lock` 을 지우지 않습니다.** `services/scheduler.py` 가 flock
  으로 리더를 뽑는데, 살아 있는 워커가 쥔 inode 를 unlink 하면 새 워커가 다른 inode 에 잠금을 따로
  얻어 리더가 둘이 됩니다.
- **`--bind` 는 `127.0.0.1` 로 박고 `.env` 의 `FLASK_HOST` 를 읽지 않습니다.** `0.0.0.0` 이면 LAN 에서
  Flask 에 직접 닿아 NextAuth 를 우회합니다(`.env.example` 의 `FLASK_HOST` 주석).
- **`frontend/.env -> ../.env` 심링크를 만들지 않습니다.** `frontend/scripts/run-next.js` 가 기동 전에
  그 심링크를 제거하므로 매 기동마다 만들고 지우는 싸움이 됩니다.
- **`StartLimitIntervalSec` 와 `StartLimitBurst` 를 둘 다 0 이 아닌 값으로 `[Unit]` 에 둡니다.** 어느
  한쪽이 0 이면 상한이 없고, `0s`·`0min` 도 0 입니다. 마지막 값은 300 과 5 였습니다. 옛 이름
  `StartLimitInterval=`·`StartLimitBurst=` 는 `[Service]` 에서도 호환용으로 읽히지만, 새 이름
  `StartLimitIntervalSec=` 를 `[Service]` 에 두면 「Unknown key name」 경고와 함께 무시됩니다. 상한에
  걸리면 `systemctl --user start` 가 「start request repeated too quickly」로 거부하므로, 원인을 고친 뒤
  `systemctl --user reset-failed <유닛>` 으로 기록을 지우고 다시 시작합니다.
- **로그는 `logs/backend.log`·`logs/frontend.log` 에 `append:` 합니다.** journal 로 옮기면 그 경로를
  로그 위치로 적은 `CLAUDE.md`·`AGENTS.md`·`README.md`·`restart_all.sh` 를 두 갈래로 갈라야 합니다.
  대신 스크립트와 유닛을 번갈아 쓰면 같은 파일에 두 출처가 섞이므로, 그것도 병행 금지의 이유입니다.
- **`.env` 를 셸로 `source` 하지 않습니다.** 이 저장소가 시작 스크립트에서 그 방식을 금지한 이유
  (`scripts/env_value.sh` 주석, `[INFRA-049]`)가 유닛에도 그대로 적용됩니다. 유닛이 실제로 쓰는 값은
  포트 하나뿐입니다. `EnvironmentFile=` 은 인라인 주석을 떼지 않아 대안이 아닙니다.
- **`/bin/bash -lc` 를 쓰지 않습니다.** 로그인 프로파일에 기대는 환경 드리프트를 만들고, Ubuntu 의
  `/etc/profile` 이 PATH 를 다시 쓰므로 `Environment=PATH=` 가 듣지 않을 가능성이 큽니다. 서버에서
  실측하지는 않았으며, 확인은 `systemd-run --user --wait --pipe -p 'Environment=PATH=/tmp' /bin/bash -lc
  'echo $PATH'` 한 줄입니다.
- **`After=`·`Wants=network-online.target` 은 사용자 매니저에 없는 대상입니다.** 두지 않습니다.

## 환경 드리프트

운영 서버의 `.env` 는 2026-09-22 에 `FLASK_HOST=127.0.0.1` 로 바꾸어 저장소의 `.env.example` 과
같아졌습니다. `.env` 는 git 이 추적하지 않으므로 코드로 강제하지 않으며, 스크립트로 운영하는 지금은
이 값이 loopback 계약의 방어선입니다. `0.0.0.0` 이 실제로 무엇을 여는지는 `.env.example` 의
`FLASK_HOST` 주석에 있습니다.

운영 `.env` 에는 `CLOSING_SCHEDULE_TIME`, `SLACK_WEBHOOK_URL`, `VCP_GPT_FALLBACK_MODEL`,
`VCP_PERPLEXITY_API_TIMEOUT`, `VCP_ZAI_API_TIMEOUT` 이 없지만 조치할 것이 없습니다. 다섯 키
모두 코드에 기본값이 있습니다. `services/scheduler.py` 의 `_resolve_daily_schedule_time` 호출이
17:00 을, `services/notifier.py` 의 `__init__` 이 빈 웹훅 주소를, `engine/config.py` 의 같은
이름 프로퍼티 셋이 나머지를 채웁니다. 두 타임아웃은 `ANALYSIS_LLM_API_TIMEOUT` 을 먼저 보고
그것도 없으면 각각 120초·180초입니다(2026-09-22 서버 감사, 실제 로그로 확인). 다음 사람이
다시 조사하지 않도록 적어 둡니다.

## 남아 있는 판단 사항

**프로덕션이 Next dev 서버로 서빙 중입니다.** `restart_all.sh` 가 `run-next.js dev` 로 띄웁니다.
`next dev` 는 요청이 올 때 컴파일하므로 첫 응답이 느리고, 프로덕션 최적화가 꺼져 있으며, 파일 감시
때문에 메모리를 계속 쓰고, HMR 클라이언트 번들이 외부로 나갑니다. `npm run build` 를 배포 절차에
넣고 `npm run start` 로 바꾸어야 하지만, 빌드 실패 시의 처리와 QA 없이 전환하면 라이브가 깨질 수
있어 `[INFRA-076]` 으로 다룹니다. 전환 전 확인할 것은 `next start` 에서 `next.config.js` 의 rewrites
와 NextAuth 콜백 주소, `run-next.js` 의 production 환경 필터가 dev 와 같은 값을 내는지, 그리고 Caddy
뒤에서 로그인 흐름이 실제로 도는지입니다. 되돌리기는 기동 명령을 `dev` 로 돌리고 재기동하는 것이며,
`.next` 는 dev 가 덮어씁니다.
