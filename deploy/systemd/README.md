# 운영 systemd 유닛

운영 서버(`close.highvalue.kr`)에서 이 스택을 관리하던 `systemd --user` 유닛 두 개입니다.
앞단의 Caddy 가 `localhost:3500` 으로 리버스 프록시합니다.

이 파일들은 원래 서버의 `~/.config/systemd/user/` 에만 있었고 저장소가 추적하지 않았습니다.
그래서 `[INFRA-055]`(Next 실행 환경 분리) 이후의 코드와 어긋난 채 방치되었고, 그 어긋남이
`[INFRA-075]` 의 재시작 루프로 드러났습니다. 편입본은 2026-09-22 에 서버에 마지막으로 적용된
내용과 같습니다. 다른 것은 주석 두 곳뿐입니다. `[U4 미채택]` 줄(근거는 아래 「U4」 절)과, backend
유닛의 StartLimit 배치 주석(서버본의 「[Service] 에 두면 조용히 무시한다」는 사실과 달라 고쳤습니다.
옛 이름은 `[Service]` 에서도 호환용으로 읽힙니다). frontend 유닛에는 `After=closing-bet-backend.service`
같은 순서 의존을 두지 않습니다. 서버본에 없었고, Next 는 요청이 올 때 Flask 로 프록시하므로 기동
순서가 필요 없습니다.

**운영자는 2026-09-22 에 이 유닛을 서버에서 완전히 내리고 `restart_all.sh` 로 운영합니다.** 두 경로가
같은 포트를 두고 경쟁하므로 하나만 남겨야 하고, 스크립트를 남기는 쪽을 골랐습니다. 절차는 아래
「유닛을 내리고 스크립트로 운영하기」에 있으며 ①은 이미 수행했으므로 ②부터 확인만 합니다. 파일은
지우지 않고 둡니다. 유닛을 다시 쓰게 되면 여기서 시작해야 같은 드리프트를 반복하지 않습니다.

## 실행 관리자와 `restart_all.sh` 의 관계

**이 유닛들이 활성화되어 있는 동안에는 `./restart_all.sh` 로 서비스를 교체하지 않습니다.**
두 경로가 같은 포트를 두고 경쟁하기 때문입니다. `restart_all.sh` 가 포트를 뺏으면 systemd 가
`RestartSec=5` 마다 되찾으려 시도합니다.

`[INFRA-075]` 부터 `scripts/service_lifecycle.sh` 가 점유자의 `/proc/<pid>/cgroup` 을 읽어
실행 관리자가 있는지 확인합니다. 유닛이 관리하는 프로세스는 관리 대상으로 전환하지 않고
유닛 이름과 함께 거부하며 비영점으로 끝납니다. 따라서 이 상황에서 `restart_all.sh` 를
실행하면 서비스를 건드리지 않고 다음과 같이 안내만 합니다.

```
❌ PID 3217802 는 systemd 유닛 closing-bet-backend.service 가 관리합니다. 이 스크립트로 교체하지 않습니다.
   다음 명령을 사용하세요: systemctl --user restart closing-bet-backend.service
```

이 검사는 플랫폼을 따로 가리지 않습니다. `/proc` 이 없는 macOS 에서는 systemd 계층 자체가
없으므로 종전 입양 동작을 그대로 두고, Linux 에서 점유자의 cgroup 만 읽지 못하면 허용이 아니라
「알 수 없음」으로 거부합니다. 스크립트가 유닛으로 위임하는 갈래는 두지 않았습니다. 유닛을
내리기로 했으므로 필요가 없습니다.

## 유닛을 내리고 스크립트로 운영하기

```bash
# ① 유닛을 멈추고 부팅 시 기동에서도 뺍니다. 여기부터 다운타임입니다.
#    유닛 파일을 이미 지웠다면 이 명령은 "does not exist" 로 실패하므로 건너뛰고 ②부터 봅니다.
systemctl --user disable --now closing-bet-backend closing-bet-frontend

# ② 두 포트가 비어 있어야 합니다. 무언가 남아 있으면 유닛이 아닌 다른 것이 쥔 것입니다.
ss -ltn | grep -E ':(5501|3500) '

# ③ 스크립트로 띄웁니다. 유닛이 없으므로 guard 가 거부할 대상이 없고 그대로 기동합니다.
cd ~/app/closing-bet-demo && ./restart_all.sh; echo "exit=$?"
```

확인은 다음과 같습니다.

```bash
# 유닛 파일이 남아 있지 않아야 합니다. (list-units 는 내려간 유닛을 잠시 더 보여 줄 수 있어 파일 목록으로 봅니다.)
systemctl --user list-unit-files 'closing-bet-*'

# 유닛 cgroup 이 아니라 로그인 세션 스코프(session-*.scope) 아래에 있어야 합니다.
cat /proc/$(pgrep -f 'gunicorn flask_app:app' | head -1)/cgroup

# loopback 으로 바인딩되어야 합니다.
ss -ltn | grep 5501

# 서비스가 응답해야 합니다.
curl -s -o /dev/null -w '%{http_code}\n' https://close.highvalue.kr/dashboard/kr
```

이 선택의 대가를 적어 둡니다. `restart_all.sh` 가 띄운 프로세스는 `lifecycle_exec_detached` 가
새 세션으로 분리하고 Ubuntu 의 logind 기본값이 `KillUserProcesses=no` 이므로 ssh 로그아웃에는
살아남습니다. 그러나 **재부팅 뒤에는 아무것도 자동으로 뜨지 않고, 프로세스가 죽어도 되살리는
것이 없습니다.** 부팅 시 `restart_all.sh` 를 돌리던 `closing-bet-demo-restart.service` 는 유닛
둘과 포트를 다투는 3중 충돌이라 탐색 경로 밖으로 빼 두었고, 그 내용은 저장소에 없습니다. 유닛
둘이 없는 지금은 그 충돌도 없으므로, 재부팅 자동 기동이 필요해지면 `restart_all.sh` 를 부르는
`Type=oneshot` 유닛에 `RemainAfterExit=yes` 를 함께 두어 다시 만들되 `closing-bet-*` 유닛과 함께
켜지 않습니다. `RemainAfterExit=` 가 없으면 스크립트가 끝나는 순간 유닛이 비활성이 되고 기본
`KillMode=control-group` 이 같은 cgroup 에 남은 서비스를 정리합니다. setsid 는 cgroup 을 바꾸지
않으므로 `lifecycle_exec_detached` 로 분리해도 여기에 걸립니다. 그 전까지는 재부팅
뒤 손으로 `./restart_all.sh` 를 실행합니다.

## 유닛을 쓰는 경우의 적용 절차

유닛으로 되돌릴 때의 절차입니다. 순서를 지키지 않으면 `stop_all.sh` 가 마지막 포트 확인에서
실패합니다. systemd 가 5초 뒤 프로세스를 되살려 포트를 다시 점유하기 때문입니다.

새 장비에 처음 적용한다면 lingering 을 먼저 켭니다. 켜져 있지 않으면 `systemd --user` 유닛이
ssh 세션이 끝날 때 함께 내려갑니다. 이미 켜져 있으면 아무 일도 일어나지 않습니다.

```bash
loginctl enable-linger "$USER"
```

```bash
# ⓪ 편입본이 서버본과 같은지 봅니다. 서버에 유닛이 남아 있다면 [U4 미채택] 주석 줄만 달라야 합니다.
diff deploy/systemd/closing-bet-backend.service  ~/.config/systemd/user/closing-bet-backend.service
diff deploy/systemd/closing-bet-frontend.service ~/.config/systemd/user/closing-bet-frontend.service

# ① 스크립트로 띄워 둔 프로세스를 먼저 내립니다. 유닛이 먼저 뜨면 포트를 두고 경쟁합니다.
cd ~/app/closing-bet-demo && ./stop_all.sh

# ② 유닛을 반영하고 기동합니다. 여기부터 약 20초의 다운타임이 있습니다.
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now closing-bet-backend closing-bet-frontend
```

시작 상한(`StartLimitBurst=5`)에 걸린 유닛은 `systemctl --user start` 가 「start request repeated
too quickly」로 거부합니다. 원인을 고친 뒤 `systemctl --user reset-failed closing-bet-backend
closing-bet-frontend` 로 상한 기록을 지우고 다시 시작합니다.

### 적용 후 확인

```bash
# 활성 상태이고 재시작 누적이 0 이어야 합니다.
systemctl --user show closing-bet-backend closing-bet-frontend -p ActiveState -p NRestarts

# 유닛의 cgroup 아래에 있어야 합니다. session-*.scope 로 나오면 유닛이 아니라 셸이 띄운 것입니다.
cat /proc/$(pgrep -f 'gunicorn flask_app:app' | head -1)/cgroup

# loopback 으로 바인딩되어야 합니다. 0.0.0.0 이면 유닛이 아닌 다른 것이 띄운 것입니다.
ss -ltn | grep 5501

# 재시작 루프의 흔적이 없어야 합니다.
journalctl --user -u closing-bet-backend -u closing-bet-frontend --since "-2min" | grep -i "restart counter"

# 서비스가 응답해야 합니다.
curl -s -o /dev/null -w '%{http_code}\n' https://close.highvalue.kr/dashboard/kr

# guard 확인입니다. 거부 메시지가 유닛 이름과 함께 나오고 종료 코드가 0 이 아니어야 합니다.
./restart_all.sh; echo "exit=$?"
```

## U4: 로그를 journal 로 옮기지 않았습니다

`StandardOutput=append:` 를 `journal` 로 바꾸면 유닛으로 돌 때 `logs/backend.log` 와
`logs/frontend.log` 가 동결됩니다. 그 경로를 로그 위치로 적은 곳이 `CLAUDE.md`, `AGENTS.md`,
`README.md`, `restart_all.sh` 네 파일이라 전부 「스크립트는 `logs/*.log`, 유닛은
`journalctl`」 두 갈래로 갈라야 합니다. 로그 폭주 자체는 U5 의 `StartLimitBurst=5` 가 이미 다섯
번에서 멈춥니다.

journal 로 옮기면 얻는 것이 하나 있습니다. 스크립트 운영과 유닛 운영을 오가면 같은
`logs/backend.log` 에 두 출처의 기록이 구분자 없이 시간순으로 섞여, 어느 줄이 지금 돌고 있는
프로세스의 것인지 파일만 보고는 알 수 없습니다. 지난 편입본이 journal 을 고른 이유가 이것이었습니다.
그러나 유닛을 내린 지금은 출처가 스크립트 하나뿐이라 이 비용이 생기지 않고, 유닛으로 되돌리더라도
스크립트와 번갈아 쓰지 않는 한 같습니다. 그 값어치가 네 파일을 두 갈래로 만드는 비용에 미치지
못해 채택하지 않았습니다. 유닛 파일의 `[U4 미채택]` 주석이 같은 결론을 담고 있습니다.

## 환경 드리프트

운영 서버의 `.env` 는 2026-09-22 에 `FLASK_HOST=127.0.0.1` 로 바꾸어 저장소의 `.env.example` 과
같아졌습니다. `.env` 는 git 이 추적하지 않으므로 코드로 강제하지 않습니다. 유닛을 쓸 때는
backend 유닛의 `--bind` 가 `.env` 의 `FLASK_HOST` 를 읽지 않고 `127.0.0.1` 로 고정하므로 `.env`
값과 무관하게 막히고, `restart_all.sh` 로 운영할 때는 `.env` 의 이 값이 방어선입니다.
`0.0.0.0` 이 실제로 무엇을 여는지는 `.env.example` 의 `FLASK_HOST` 주석에 있습니다.

운영 `.env` 에는 `CLOSING_SCHEDULE_TIME`, `SLACK_WEBHOOK_URL`, `VCP_GPT_FALLBACK_MODEL`,
`VCP_PERPLEXITY_API_TIMEOUT`, `VCP_ZAI_API_TIMEOUT` 이 없지만 조치할 것이 없습니다. 다섯 키
모두 코드에 기본값이 있습니다. `services/scheduler.py` 의 `_resolve_daily_schedule_time` 호출이
17:00 을, `services/notifier.py` 의 `__init__` 이 빈 웹훅 주소를, `engine/config.py` 의 같은
이름 프로퍼티 셋이 나머지를 채웁니다. 두 타임아웃은 `ANALYSIS_LLM_API_TIMEOUT` 을 먼저 보고
그것도 없으면 각각 120초·180초입니다(2026-09-22 서버 감사, 실제 로그로 확인). 다음 사람이
다시 조사하지 않도록 적어 둡니다.

## 남아 있는 판단 사항

이번 라운드에서 고치지 않고 기록만 남긴 것들입니다. 첫 항목은 유닛과 무관하게 유효하고,
나머지 셋은 유닛을 다시 쓸 때만 해당합니다.

- **프로덕션이 Next dev 서버로 서빙 중입니다.** 유닛의 `ExecStart` 도, `restart_all.sh` 도
  `run-next.js dev` 로 띄웁니다. `next dev` 는 요청이 올 때 컴파일하므로 첫 응답이 느리고,
  프로덕션 최적화가 꺼져 있으며, 파일 감시 때문에 메모리를 계속 쓰고, HMR 클라이언트 번들이
  외부로 나갑니다. `npm run build` 를 배포 절차에 넣고 `npm run start` 로 바꾸어야 하지만,
  빌드 실패 시의 처리와 QA 없이 전환하면 라이브가 깨질 수 있어 `[INFRA-076]` 으로 다룹니다.
  전환 전 확인할 것은 `next start` 에서 `next.config.js` 의 rewrites 와 NextAuth 콜백 주소,
  `run-next.js` 의 production 환경 필터가 dev 와 같은 값을 내는지, 그리고 Caddy 뒤에서 로그인
  흐름이 실제로 도는지입니다. 되돌리기는 기동 명령을 `dev` 로 돌리고 재기동하는 것이며, `.next`
  는 dev 가 덮어씁니다.
- **두 유닛이 `set -a; . ./.env` 로 `.env` 를 셸로 읽습니다.** 이 저장소는 같은 이유로 시작
  스크립트에서 그 방식을 금지하고 `scripts/env_value.sh` 를 쓰며,
  `tests/scripts/test_env_value_sh.py` 의 `test_startup_scripts_do_not_source_env` 가 그것을
  고정하고 있습니다. `.env` 에 `$(...)` 나 백틱이 들어가면 gunicorn 의 권한으로 실행됩니다.

  **systemd 의 `EnvironmentFile=` 은 대안이 되지 못합니다.** `systemd.exec(5)` 는 `#` 이나
  `;` 으로 **시작하는 줄**만 무시한다고 규정하며 값 뒤에 붙은 인라인 주석은 떼지 않습니다.
  운영 서버의 `.env` 에는 그런 줄이 21개 있습니다(`LLM_CONCURRENCY=8 # [Z.ai 전용] ...`
  형태). bash 의 `.` 에서는 `8` 이 되지만 `EnvironmentFile=` 에서는 주석까지 포함한 문자열이
  되므로, 그대로 바꾸면 워커가 잘못된 값으로 기동합니다.

  **더 나은 해법은 `.env` 전체를 읽지 않는 것입니다.** 두 유닛이 실제로 쓰는 값은 backend 의
  `FLASK_PORT` 와 frontend 의 `FRONTEND_PORT` 각각 하나뿐입니다. 나머지 50여 개는 읽을
  이유가 없습니다. `scripts/env_value.sh` 의 주석이 그 근거를 이미 적어 두었습니다. Flask 는
  `config.py` 의 `load_dotenv()` 로, Next 는 `@next/env` 로 각자 `.env` 를 읽으므로 셸이 미리
  내보내던 값은 처음부터 중복이었습니다. 즉 포트 하나 때문에 `.env` 를 셸로 실행하고 있는
  셈입니다. 바꿀 때 `/bin/bash -lc` 도 함께 걷어내면 로그인 프로파일에 기대는 환경 드리프트까지
  정리됩니다.
- **frontend 유닛의 `/home/ms/n/bin` 은 이 서버의 node 위치입니다.** `Environment=PATH=` 와
  `ExecStart` 의 npm 경로 둘 다 서버 전용 값이며 그대로 옮겼습니다. `%h` 로 바꾸면 편입본과
  서버본이 어긋나므로 바꾸지 않습니다. 그리고 `Environment=PATH=` 는 실제로는 듣지 않을
  가능성이 큽니다. `ExecStart` 가 `/bin/bash -lc` 로그인 셸이라 Ubuntu 의 `/etc/profile` 이 PATH 를
  다시 쓰므로, node 를 찾아 주는 것은 이 줄이 아니라 `~/.profile` 의 설정입니다. 확인은
  `systemd-run --user --wait --pipe -p 'Environment=PATH=/tmp' /bin/bash -lc 'echo $PATH'` 한 줄이며,
  위 `.env` 항목과 함께 `/bin/bash -lc` 를 걷어낼 때 같이 정리합니다(`[INFRA-076]`).
- **두 유닛의 `After=`·`Wants=network-online.target` 은 사용자 매니저에 없는 유닛을
  가리킵니다.** 약한 의존이라 기동을 막지는 않지만 의도한 효과가 없고 로그에 경고가 남습니다.
  운영 서버의 값을 그대로 옮겼으며, 정리하려면 사용자 매니저에서 쓸 수 있는 대상으로
  바꾸거나 지워야 합니다.

## 이 guard 가 막지 못하는 경우

`scripts/service_lifecycle.sh` 의 검사는 **지금 포트를 쥐고 있는 프로세스**를 봅니다. 유닛이
`RestartSec` 대기 중이라 포트가 잠시 비어 있는 순간에 `restart_all.sh` 를 실행하면 검사할
대상이 없으므로 그대로 기동하고, 곧 유닛과 경쟁하게 됩니다. 이래서 유닛을 쓰는 절차의 첫
단계가 「스크립트 프로세스를 먼저 내린다」이고, 유닛을 내리는 절차의 첫 단계가 「유닛을 먼저
내린다」입니다. 다만 이제는 `StartLimitBurst=5` 때문에 예전처럼 수백 회 반복되지 않고 다섯 번
만에 멈춥니다.
