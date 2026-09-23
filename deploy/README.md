# 운영 서버의 실행 관리

운영 서버(`close.highvalue.kr`)는 `./restart_all.sh` 와 `./stop_all.sh` 로만 두 서비스를 관리합니다.
앞단의 Caddy 가 `localhost:3500` 으로 리버스 프록시합니다. macOS 개발 머신과 같은 경로이며,
스크립트에는 플랫폼을 가르는 분기가 없습니다. 갈리는 것은 `.env` 의 `NEXT_MODE` 하나입니다(아래
「Next 를 production 으로 돌리기」).

`restart_all.sh` 가 띄운 프로세스는 `lifecycle_exec_detached` 가 새 세션으로 분리하므로 ssh
로그아웃에는 살아남습니다. 단, 이것은 로그아웃할 때 그 사용자의 프로세스를 모두 정리하지 않는
호스트를 전제합니다. Ubuntu 의 기본 로그인 설정이 그렇고, 그 설정을 바꾼 호스트에서는 로그아웃과
함께 서비스가 내려갑니다. **재부팅 뒤에는 아무것도 자동으로 뜨지 않고, 프로세스가 죽어도 되살리는
것이 없습니다.** 재부팅 뒤에는 손으로 `./restart_all.sh` 를 실행합니다.

**다른 실행 관리자와 병행하지 않습니다.** 스크립트는 종료 대기 중이거나 종료 직후에 포트를 다시
잡은 프로세스만 잡아내고 비영점으로 끝납니다. 되살리는 지연이 그보다 긴 관리자는 잡지 못하므로,
같은 서비스를 되살리는 관리자가 있으면 두 경로가 포트를 두고 번갈아 재시작합니다.

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

## Next 를 production 으로 돌리기

`[INFRA-076]` 이전에는 운영도 `run-next.js dev` 로 떠 있었습니다. Next 16 의 dev 서버는 Origin 이
`localhost` 가 아닌 `/_next/hmr` 웹소켓을 403 으로 막고(`allowedDevOrigins`), 그 연결이 없으면
클라이언트가 API 호출을 시작하지 않습니다. 그래서 대시보드가 틀만 그려지고 값이 전부 `--` 였고,
서버 안의 `http://localhost:3500` 만 정상이었습니다. 그 사이 Caddy 에 `/_next/hmr` 요청의 `Origin` 을
`http://localhost:3500` 으로 바꿔 넘기는 `@hmr` 블록을 두어 화면을 살려 두었습니다.

`.env` 에 `NEXT_MODE=prod` 를 두면 같은 `./restart_all.sh` 가 다음 순서로 돕니다. 중지 → 의존성 동기화 →
`node scripts/run-next.js build`(전경, 출력은 `logs/frontend.log` 에 이어 쓰고 실패하면 마지막 15줄을 화면에
보여 줍니다) → gunicorn → `node scripts/run-next.js start`.
빌드가 실패하면 비영점으로 끝나며 아무 서비스도 시작하지 않습니다. 그 시점에는 이전 서비스가 이미
내려가 있으므로, **다운타임은 빌드 시간과 기동 시간의 합입니다.** 빌드가 실행 중인 서버가 읽는
`frontend/.next` 에 쓰고, 빌드에 필요한 의존성 동기화가 서비스를 내린 뒤에만 돌도록 계약되어 있어
빌드 후 교체 방식은 채택하지 않았습니다. `next.config.js` 의 rewrites 대상(`API_URL`)은 빌드 때
고정되므로 `.env` 를 바꾸면 반드시 `./restart_all.sh` 로 다시 빌드합니다. 빌드는 타입 검사를 포함합니다.

### 적용 절차 (Ubuntu)

```bash
# 1. 모드 지정. 따옴표 없이 적는다. 이미 줄이 있으면 그 줄을 고친다. 값을 비워 두면 dev 로 뜬다.
grep -q '^NEXT_MODE=' .env && sed -i 's/^NEXT_MODE=.*/NEXT_MODE=prod/' .env || printf 'NEXT_MODE=prod\n' >> .env

# 2. 재기동. 「🔨 Frontend production build...」 뒤 빌드가 logs/frontend.log 에 기록되고 끝에 「🎉 Ready!」가 나와야 한다.
#    비영점으로 끝나면(빌드 실패 포함) 서비스는 내려간 상태다. 원인은 그 로그에 있고, 바로 아래 「되돌리기」로 간다.
./restart_all.sh

# 3. 프로세스 확인. 기록 PID 는 run-next.js start 래퍼이고 포트는 next-server 가 쥔다.
ps -o pid,pgid,command -p "$(cut -d'|' -f1 logs/frontend.pid)"
ss -ltnp 'sport = :3500'
```

`./restart_all.sh` 나 `./stop_all.sh` 가 「frontend PID … 의 종료를 확인하지 못했습니다」로 끝나면
`ss -ltnp 'sport = :3500'` 으로 포트를 봅니다. 비어 있으면 종료는 된 것이고 보고만 거짓 음성입니다.
`[INFRA-077]` 전에는 `lifecycle_pid_alive` 가 `ps` 가 빈 값을 주는 순간을 「살아 있음」으로 읽고 이어지는
시작 시각 대조가 메시지 없이 실패하는 경합이 있었고, 그 경로는 SIGTERM 뒤 8초 안에 내려가지 않아 KILL 로
넘어간 뒤에만 닿았습니다. 지금은 그 순간을 종료로 판정하고, KILL 로 올릴 때 `⚠️ … KILL 로 올립니다` 한 줄을
stderr 에 남깁니다. `ps -o stat=` 과 바로 다음 `ps -o lstart=` 사이에 프로세스가 사라지는 더 좁은 창은 남아
있으며, 그때도 같은 ❌ 한 줄로 끝납니다. macOS 의 prod 사이클 여섯 번 가운데 첫 번째가 그렇게 끝났고, 8초를
넘긴 이유는 재현되지 않았습니다(연결 없이, 그리고 keep-alive 1개를 쥔 채 잰 그룹 소멸은 0.04초 이내). 다음에
같은 일이 생기면 ⚠️ 줄의 유무로 8초 초과 여부를 가릴 수 있습니다. 포트가 비었으면 `./restart_all.sh` 를 다시
실행하면 됩니다.

브라우저에서 `NEXTAUTH_URL` 의 호스트로 `/dashboard/kr` 을 엽니다. 확인할 것은 넷입니다. 콘솔에
`/_next/hmr` 오류가 없어야 하고, 네트워크 탭에 `/api/kr/*` 호출이 생겨야 하며, 대시보드에 값이
표시되어야 하고, Google 로그인이 `NEXTAUTH_URL` 로 돌아와야 합니다. 마지막 항목은 `next start` 가
`run-next.js` 의 production 환경 필터로 같은 키를 받는지를 실제로 확인하는 것입니다.

```bash
# 4. Caddy 의 땜질 제거. @hmr 블록만 지운다. 저장소의 deploy/caddy/Caddyfile 에는 원래 없다.
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak
sudoedit /etc/caddy/Caddyfile
sudo -u caddy caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy

# 5. 재확인. 강력 새로고침 뒤 3 의 브라우저 확인을 반복한다.
```

### 되돌리기

```bash
sed -i 's/^NEXT_MODE=.*/NEXT_MODE=dev/' .env   # 줄을 지워도 같다. 기본값이 dev 다
./restart_all.sh
```

dev 로 돌아간 뒤에는 4 에서 지운 `@hmr` 블록이 없으므로 대시보드가 다시 비어 보입니다. 백업에서
블록을 되살리거나, dev 서버를 운영에 계속 쓰기로 결정한 경우에만 `next.config.js` 에
`allowedDevOrigins: process.env.NEXTAUTH_URL ? [new URL(process.env.NEXTAUTH_URL).hostname] : []`
를 둡니다. 도메인 리터럴은 어느 쪽에도 넣지 않습니다. 공개 URL 의 출처는 `.env` 의 `NEXTAUTH_URL`
하나입니다.

dev 는 `.next/dev` 아래에 쓰므로 prod 빌드 산출물과 섞이지 않습니다.
