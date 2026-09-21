# 운영 systemd 유닛

운영 서버(`close.highvalue.kr`)에서 이 스택을 관리하는 `systemd --user` 유닛 두 개입니다.
앞단의 Caddy 가 `localhost:3500` 으로 리버스 프록시합니다.

이 파일들은 원래 서버의 `~/.config/systemd/user/` 에만 있었고 저장소가 추적하지 않았습니다.
그래서 `[INFRA-055]`(Next 실행 환경 분리) 이후의 코드와 어긋난 채 방치되었고, 그 어긋남이
`[INFRA-075]` 의 재시작 루프로 드러났습니다. 앞으로는 여기를 고친 뒤 서버에 반영합니다.

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

## 적용 절차

순서를 지키지 않으면 `stop_all.sh` 가 마지막 포트 확인에서 실패합니다. systemd 가 5초 뒤
프로세스를 되살려 포트를 다시 점유하기 때문입니다.

새 장비에 처음 적용한다면 lingering 을 먼저 켭니다. 켜져 있지 않으면 `systemd --user` 유닛이
ssh 세션이 끝날 때 함께 내려갑니다. 이미 켜져 있으면 아무 일도 일어나지 않습니다.

```bash
loginctl enable-linger "$USER"
```

```bash
# ① systemd 재시작 루프를 먼저 멈춥니다. 여기까지는 다운타임이 없습니다.
systemctl --user stop closing-bet-backend closing-bet-frontend

# ② 스크립트로 띄워 둔 프로세스가 남아 있으면 정리합니다.
cd ~/app/closing-bet-demo && ./stop_all.sh

# ③ 새 유닛을 반영하고 기동합니다. 여기부터 약 20초의 다운타임이 있습니다.
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start closing-bet-backend closing-bet-frontend
```

## 적용 후 확인

```bash
# 활성 상태이고 재시작 누적이 0 이어야 합니다.
systemctl --user show closing-bet-backend closing-bet-frontend -p ActiveState -p NRestarts

# 유닛의 cgroup 아래에 있어야 합니다. session-*.scope 로 나오면 유닛이 아니라 셸이 띄운 것입니다.
cat /proc/$(pgrep -f 'gunicorn flask_app:app' | head -1)/cgroup

# loopback 으로 바인딩되어야 합니다. 0.0.0.0 이면 .env 의 FLASK_HOST 가 남아 있는 것입니다.
ss -ltn | grep 5501

# 재시작 루프의 흔적이 없어야 합니다.
journalctl --user -u closing-bet-backend -u closing-bet-frontend --since "-2min" | grep -i "restart counter"

# 서비스가 응답해야 합니다.
curl -s -o /dev/null -w '%{http_code}\n' https://close.highvalue.kr/dashboard/kr

# 이번 수정의 핵심 검증입니다. 거부 메시지가 유닛 이름과 함께 나오고 종료 코드가 0 이 아니어야 합니다.
./restart_all.sh; echo "exit=$?"
```

## 환경 드리프트

운영 서버의 `.env` 는 `FLASK_HOST=0.0.0.0`, 저장소의 `.env.example` 은 `127.0.0.1` 입니다.
`.env` 는 git 이 추적하지 않으므로 코드로 강제하지 않습니다. 대신 backend 유닛의
`--bind` 가 `.env` 의 `FLASK_HOST` 를 읽지 않고 `127.0.0.1` 로 고정합니다. 서버의 `.env`
값도 `127.0.0.1` 로 맞추어 두면 `python flask_app.py` 로 직접 띄울 때에도 같아집니다.
`0.0.0.0` 이 실제로 무엇을 여는지는 `.env.example` 의 `FLASK_HOST` 주석에 있습니다.

운영 `.env` 에는 `CLOSING_SCHEDULE_TIME`, `SLACK_WEBHOOK_URL`, `VCP_GPT_FALLBACK_MODEL`,
`VCP_PERPLEXITY_API_TIMEOUT`, `VCP_ZAI_API_TIMEOUT` 이 없지만 조치할 것이 없습니다. 다섯 키
모두 코드에 기본값이 있습니다. `services/scheduler.py` 의 `_resolve_daily_schedule_time` 호출이
17:00 을, `services/notifier.py` 의 `__init__` 이 빈 웹훅 주소를, `engine/config.py` 의 같은
이름 프로퍼티 셋이 나머지를 채웁니다. 두 타임아웃은 `ANALYSIS_LLM_API_TIMEOUT` 을 먼저 보고
그것도 없으면 각각 120초·180초입니다(2026-09-22 서버 감사, 실제 로그로 확인). 다음 사람이
다시 조사하지 않도록 적어 둡니다.

## 남아 있는 판단 사항

이번 라운드에서 고치지 않고 기록만 남긴 것들입니다.

- **프로덕션이 Next dev 서버로 서빙 중입니다.** `ExecStart` 가 `npm run dev` 입니다.
  `next dev` 는 요청이 올 때 컴파일하므로 첫 응답이 느리고, 프로덕션 최적화가 꺼져 있으며,
  파일 감시 때문에 메모리를 계속 씁니다. `npm run build` 를 배포 절차에 넣고 `npm run start`
  로 바꾸어야 하지만, 빌드 실패 시의 처리까지 정해야 하므로 별도 항목으로 다룹니다.
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
  셈입니다.

  이번 라운드에서 바꾸지 않은 것은 systemd 를 실제로 돌려 확인할 수 없기 때문입니다. 서버에서
  검증할 수 있을 때 별도 항목으로 전환하며, 그때 `/bin/bash -lc` 도 함께 걷어내면 로그인
  프로파일에 기대는 환경 드리프트까지 정리됩니다.
- **frontend 유닛의 `/home/ms/n/bin/npm` 은 장비에 묶인 절대 경로입니다.** 운영 서버의 값을
  그대로 옮겼습니다. `%h/n/bin/npm` 으로 바꾸면 같은 사용자 유닛에서 동일하게 해석됩니다.
- **두 유닛의 `After=`·`Wants=network-online.target` 은 사용자 매니저에 없는 유닛을
  가리킵니다.** 약한 의존이라 기동을 막지는 않지만 의도한 효과가 없고 로그에 경고가 남습니다.
  운영 서버의 값을 그대로 옮겼으며, 정리하려면 사용자 매니저에서 쓸 수 있는 대상으로
  바꾸거나 지워야 합니다.

## 이 guard 가 막지 못하는 경우

`scripts/service_lifecycle.sh` 의 검사는 **지금 포트를 쥐고 있는 프로세스**를 봅니다. 유닛이
`RestartSec` 대기 중이라 포트가 잠시 비어 있는 순간에 `restart_all.sh` 를 실행하면 검사할
대상이 없으므로 그대로 기동하고, 곧 유닛과 경쟁하게 됩니다. 이래서 적용 절차의 1번 단계가
「유닛을 먼저 정지한다」입니다. 다만 이제는 `StartLimitBurst=5` 때문에 예전처럼 수백 회
반복되지 않고 다섯 번 만에 멈춥니다.
