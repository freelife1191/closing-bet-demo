# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 최종 필수 QA가 통과한 완료 항목만 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.
>
> 2026-09-01 여섯 카테고리 감사(`[INFRA-004]`)로 30개 항목이 들어왔습니다. 각 항목의
> 근거에 적힌 `AUDIT-*` 문서는 `docs/dev-cycle/audits/` 에 있으며, 항목마다 위치를
> 절 번호까지 적어 두었으므로 사이클을 시작할 때 그 절을 먼저 읽습니다.
> 2026-09-07 `[INFRA-036]` 으로 백로그를 현행화했습니다. 해소된 항목 9건을 제거하고 같은 원인의
> 항목 26건을 병합했으며, 목록과 사유는 `archive/2026-09.md` 의 「백로그 정리」 절에 있습니다.

> 2026-09-09 비상용 검토 정정: 긴급성이 낮다는 이유로 제외했던 19건을 복구했습니다(검토 시점 68건). 이후 완료 건은 아카이브에 따라 제거합니다.
> 구조 통합·입력 보강·업그레이드·화면 개선도 유효한 작업입니다. 필요성과 실행 순서를 구분하고,
> 관련 코드와 검증을 공유하는 항목은 묶어서 진행합니다. 기존 체크리스트와 설계 선택지는 보존합니다.
> 판단 정정 기록: [백로그 검토](reviews/backlog-noncommercial-2026-09-09.md).

## P0 — 즉시

### [INFRA-074] 재시작 충돌·로그인 실패·반복 설치 로그 보완
- 카테고리: 인프라 | 티어: T3 | 근거: 사용자 Linux 로그(2026-09-21 23:07), 시작·중지 실패 은폐, KRX 인증 경계
- 설계 승인: 사용자의 「확인 된 부분들 모두 보완하고 … 의존성 … 로그 … 보완해줘」 및 기존 자율 진행 위임. 기존 시작/중지·의존성·KRX 실패 경계의 bounded 수정.
- 범위: restart_all.sh, stop_all.sh, scripts의 관련 helper, pykrx vendor wheel/핀, 회귀 및 문서. 원격 운영 서버의 실행 관리자/계정 설정은 변경하지 않음.
- QA 시나리오: 포트 충돌/재점유/기동 실패에서 성공 문구 없이 종료, 정상 시작/중지, 의존성 정상 재실행 로그 축약과 실패 표시, KRX HTML/HTTP/schema 오류와 정상 로그인.
- [x] 구현과 RED→GREEN 회귀
- [x] 과잉설계 2건 반영 → code APPROVE / architect CLEAR / deep ACCEPT / security APPROVE
- [x] 기능 검증: 격리 pytest2527 통과2skip + 수명주기17 통과, 관련81 통과, Vitest641 통과. 실제 시작·중지·재시작/legacy 인수0, KRX HTML import+JSON200, DOM/Next오류0. 임시 서비스·scratch·browser 정리 완료.
- [ ] B1 화면 캡처 미통과: ego-browser 캡처3회 실패, DOM/API는 확인. driver 복구 뒤 별도 캡처 검증 필요.
- [ ] C1 원본 전체불변 검수 계약 미통과: 하위 agent의 원본 전체pytest 실행 경계 위반. 민감 설정·종가/VCP 결과 보존 확인, runtime cache/status 변경 기록. 전체 COMPLETE/완료 아카이브 금지; QA 문서 참조.


### [INFRA-075] systemd 소유 포트 입양 차단과 운영 유닛 파일 편입
- 카테고리: 인프라 | 티어: T3 | 근거: 운영 서버(close.highvalue.kr) EADDRINUSE 무한 반복, 누적 재시작 backend 433회·frontend 823회, `/proc/<pid>/cgroup` 소유권 증거
- 설계 승인: 사용자 작업 의뢰서(2026-09-22). `superpowers:brainstorming` 설계 후 승인을 받고 구현한다.
- 범위: `scripts/service_lifecycle.sh` 의 `lifecycle_legacy_master_pid` 입양 경로에 감독자 감지 guard 추가, 운영 systemd 유닛 파일을 저장소에 편입(U1~U5), `.env.example` 주석과 운영 적용 절차 문서화, 회귀 테스트. 원격 운영 서버에 직접 접속해 실험하지 않는다.
- 범위에 추가(부록 B, 2026-09-22 서버 감사): `deploy/caddy/Caddyfile` 편입(B1), `.gitignore` AppleDouble 규칙(B2), `CLAUDE.md` 의 `.env.production` 서술 정정(B3), `.env.example` FLASK_HOST 주석 보강(B4). B5(누락 env 키 다섯 개)는 전부 코드 기본값이 있어 조치 불필요이며 기록만 남긴다. 운영 서버에서 이미 처리한 Caddy reload·`ADMIN_API_TOKEN` 추가·`.env` 권한 변경은 다시 하지 않는다.
- 범위 정정(v2 의뢰서, 2026-09-22): 의뢰서 §5 의 플랫폼 분기와 `systemctl --user` 위임은 사용자 결정으로 제외한다. 운영자가 유닛을 내리고 `restart_all.sh` 로 운영하기로 했으므로 스크립트에 유닛 갈래를 두지 않는다. `service_lifecycle.sh` 와 두 진입점은 이번 라운드에서 바꾸지 않는다. 남는 것은 유닛 편입본을 서버본과 일치시키는 것(U4 미채택), 유닛을 내리는 운영 절차 문서, Caddy README 의 다른 사이트 블록 안내, `.gitignore` 계약 테스트, macOS 실기동 검증, U6 판단 보고다.
- 문제: `lifecycle_legacy_master_pid` 가 소유자·작업 경로·실행 명령 세 가지만 확인하고 「누가 이 프로세스의 수명주기를 관리하는가」를 보지 않아, systemd --user 유닛이 소유한 프로세스를 관리 대상으로 입양해 종료한다. systemd 가 5초 뒤 되살리므로 경쟁 상태가 된다.
- 종료 로직(종료 순서, flock, PID 토큰 검증, `lifecycle_exec_detached` 의 setsid)은 결함이 아니므로 수정 대상이 아니다. `[INFRA-074]` 가 세운 계약을 유지한다.
- U6(운영이 Next dev 서버로 서빙 중인 문제)은 판단만 보고하고 이 항목에서 변경하지 않는다.
- QA 시나리오: cgroup 이 `.service` 로 끝나는 점유자를 입양하지 않고 유닛 이름을 포함해 거부·비영점 종료, `session-*.scope` 점유자의 기존 입양 경로 회귀 없음, cgroup 을 읽을 수 없을 때 조용히 통과하지 않음, `restart_all.sh`·`stop_all.sh` 두 진입점이 성공 문구 없이 거부를 전파, 유닛 파일 계약 검사. 부록 B 추가분: Caddy 설정 계약 테스트(압축·보안 헤더·`:80` 비노출·`reverse_proxy` 대상), `git status` 에 `._*` 가 뜨지 않음.
- [x] 설계와 승인: bounded 설계를 대화에서 제시하고 사용자 승인 확보. cgroup 미존재 플랫폼의 판정을 「감독자 없음」으로 확정.
- [x] 구현과 RED→GREEN 회귀: guard 도입 전 신규 4건 실패·회귀 방지 2건 통과를 확인한 뒤 구현. `scripts/service_lifecycle.sh` 에 `lifecycle_cgroup_path`·`lifecycle_cgroup_unit`·`lifecycle_pid_supervisor`·`lifecycle_assert_pid_is_unsupervised` 추가, `deploy/systemd/` 유닛 2개와 README 편입, `.env.example` 주석 보강.
- [x] 리뷰와 보안 검토: code-reviewer 3라운드 → CHANGES REQUESTED(M1/M2) 후 APPROVE. M1(데스크톱 터미널 거짓 양성과 위험한 안내 명령), L1(Delegate 하위 cgroup 우회), L2(권위 없는 cgroup 줄·빈 파일), L3(제어 문자 출력), L4(사용자 세션 관리자 재기동 안내), L5(계약 테스트 단언 기준), L6(lingering 누락) 반영. M2 는 근거를 갖춰 이월. 무력화 실험으로 판정 3갈래가 각각 테스트에 고정됨을 확인.
- [ ] 기능 검증과 운영 적용 절차 문서화: 정적 검증 완료(tests/scripts 126 통과, 전체 pytest 2555 통과 2skip, Vitest 641 통과, type-check 통과, 실제 기동·종료 사이클과 적대적 시나리오 통과). 운영 서버 적용과 확인은 미실시.
- [ ] 미규명 1건: 전체 회귀 첫 실행에서 `test_supervisor_detection_ignores_a_unit_the_caller_itself_runs_inside` 가 1회 실패(종료 코드 0, stderr 비어 있음, stdout 에 유닛 경로). 이후 단독 전체 회귀 3회, 동일 동시 부하 전체 회귀 1회, 단독 반복 30회에서 재현되지 않음. 리뷰어의 fork EAGAIN 가설은 종료 코드 2 와 stderr 의 fork 오류를 예측하므로 관측과 맞지 않아 배제. 기전 미규명이므로 해결로 기록하지 않으며, 단언에 두 cgroup 파일의 실제 내용을 남기도록 보강함. 재현되면 `lifecycle_cgroup_path` 를 셸 내장 `read` 루프로 바꾸는 안을 검토한다.
- [x] 부록 B 설계와 승인: bounded 설계를 대화에서 제시하고 사용자 승인 확보(2026-09-22).
- [x] 부록 B 구현: `deploy/caddy/Caddyfile`·README 편입, `.gitignore` `._*`(`.DS_Store` 는 기존), `CLAUDE.md`·`AGENTS.md` 의 `.env.production` 서술 정정과 회전 절차 2단계화, `.env.example` FLASK_HOST 주석에 LAN 우회 근거, `deploy/systemd/README.md` 에 B5 기록. Caddy 계약 테스트는 RED→GREEN 으로 추가.
- [x] 부록 B 리뷰와 검증: code-reviewer 2라운드 → CHANGES REQUESTED(M1~M4) 후 APPROVE. M2(두 번째 `reverse_proxy` 미검출), M3(백업 없이 덮어쓰기), M4(`AGENTS.md` 드리프트), N1·N3·N4 반영, N2·N5 는 근거를 갖춰 미반영. 변이 실험 9종 실패·원본 통과. `pytest tests/scripts/` 128 통과, 전체 pytest 2559 통과 2 skip. `git check-ignore -v` 로 `._*` 가 56행 규칙에 걸림을 확인. 로컬에 caddy 가 없어 Caddyfile 문법은 미검증. frontend 파일 변경 없음이라 type-check·Vitest 생략.
- [x] v2 잔여분 구현(2026-09-22): 유닛 두 개를 서버본 그대로 교체. 지난 편입본은 세 군데 어긋나 있었다(U4 journal 선채택, frontend `After=closing-bet-backend.service` 추가, `Environment=PATH=` 누락). U4 는 미채택으로 확정하고 근거를 유닛 주석과 README 에 기록. 계약 테스트에서 journal 단언 제거. `.gitignore` 계약 테스트(`git check-ignore`) 추가. `deploy/caddy/README.md` 의 적용 절차가 서버 Caddyfile 전체를 덮어써 다른 사이트 블록을 지우는 결함을 발견해 블록 단위 반영으로 정정. `deploy/systemd/README.md` 에 「유닛을 내리고 스크립트로 운영하기」 절차와 그 대가(재부팅·크래시 시 자동 기동 없음) 기록.
- [x] macOS 실기동(2026-09-22 08:26, Darwin 25.5, bash 5.3): 떠 있던 서비스(PID 52504·52719)를 `./restart_all.sh` 가 정상 종료 → 의존성 확인(변경 없음) → 재기동해 9초 만에 `🎉 Ready!` exit 0. backend `/api/kr/market-gate` 200, frontend `/` 200, 두 프로세스 모두 자기 프로세스 그룹 리더(setsid 분리 확인). `./stop_all.sh` 3초 만에 exit 0, 두 포트 비고 PID 파일 삭제, 작업 트리 변화 없음. `sync_dependencies.sh` 의 macOS 구문 문제 없음.
- [x] v2 잔여분 리뷰: 별도 레인 둘(feature-dev:code-reviewer APPROVE + 낮은 확신도 3건, oh-my-claudecode:code-reviewer CHANGES REQUESTED M1~M4·N1~N9). 두 레인 모두 회신이 유실되어 subagents 기록에서 결과를 읽음. M1(`StartLimitBurst=0` 통과)·M2(`0s`·`0sec`·`0min` 통과)는 단언 보강, M3(backend 유닛의 StartLimit 주석이 systemd 동작과 다름)은 주석 정정 후 README 에 의도한 차이로 기록, M4(Caddy 절차의 대조 단계 부재)는 블록 단위 diff 스니펫 추가(가짜 다중 사이트 파일로 동작 확인). N1(`check-ignore -q` 가 전역 excludes 도 통과)은 `-v` 와 `.gitignore:` 접두 단언으로, N2·N3·N5·N7·N8·N9 반영, N4 는 해당 유닛 내용이 저장소에 없어 재작성 지침만 기록, N6 은 `[INFRA-076]` 에 이관. 첫 리뷰어의 `list-units` GC 시점 관찰은 `list-unit-files` 로, Caddyfile 헤더 주석의 「사본」 표현은 「기준본」으로 정정. 변이 8종(StartLimit 7 + 전역 excludes 1) 실패·원본 통과. 재판정 APPROVE. 후속 권고 F1(대조 스니펫 후행 공백)·F2(블록 순서 안내)·F3(oneshot 유닛에 `RemainAfterExit=yes` 필요)·F4(줄 수 표기)·F5(서버 파일 읽기에 sudo) 모두 반영. 최종 `pytest -q` 2560 통과 2 skip, `tests/scripts/` 129 통과.
- [x] 유닛 파일 삭제(2026-09-22, 사용자 지시 「지워」): 서버에서 유닛을 완전히 제거했으므로 `deploy/systemd/*.service` 두 개와 유닛 계약 테스트를 지움. 마지막 판은 커밋 `13952d9`. `deploy/systemd/README.md` 는 입양 검사 설명, 스크립트 운영의 대가, 「유닛을 다시 만든다면」 규칙(U1~U5 와 리뷰 N6 의 교훈), B5 기록, U6 판단만 남김. `.env.example` 의 FLASK_HOST 주석과 `deploy/caddy/README.md` 의 유닛 참조를 정리. 리뷰(oh-my-claudecode:code-reviewer) CHANGES REQUESTED → D1(node 위치·`%h/n/bin/npm`)·D2(`After=` 금지)·D3(lingering)·B2(로그인 셸 PATH 는 미실측 가설로 되돌리고 확인 명령 복원) 반영, C1(`restart_all.sh` 의 `--bind` 기본값 loopback 을 텍스트 단언으로 고정, 변이 2종 실패)·C2(미사용 `import re`)·B1(`busctl` 유효값 확인)·B3(StartLimit 옛 이름 호환)·D4(`reset-failed`) 반영. 재판정 APPROVE, E1~E3(수치·줄 폭·표현) 반영. 유닛 계약 테스트 하나를 빼고 loopback 단언 하나를 더해 전체 pytest 는 2560 통과 2 skip 그대로.


### [INFRA-076] 운영 Next 실행 모드 전환 (dev → prod)
- 카테고리: 인프라 | 티어: T3 (계획 T2, diff 320줄로 상향) | 근거: 2026-09-22 운영 실측, Next 16 dev 서버의 외부 Origin HMR 차단으로 대시보드 데이터 미표시. 위험 경로 파일 없음
- 이력: `[INFRA-075]` 에서 U6(프로덕션이 Next dev 서버로 서빙 중)로 이월된 항목을 2026-09-22 작업 의뢰서 내용으로 교체했다. 의뢰서는 `[INFRA-075]` 로 적었으나 그 번호는 이미 쓰이고 있어 같은 주제인 이 번호를 유지한다.
- 문제: 운영 서버(Ubuntu)가 `./restart_all.sh` 로 `node scripts/run-next.js dev` 를 띄운다. Next 16 은 Origin 이 `localhost` 가 아닌 `/_next/hmr` 웹소켓을 403 으로 막고(`allowedDevOrigins`), 그 연결이 없으면 클라이언트가 API 호출을 시작하지 않는다. 실측: 대시보드가 틀만 그려지고 값이 전부 `--`, 브라우저 콘솔 `wss://<운영 도메인>/_next/hmr` 502, `logs/frontend.log` 에 `Blocked cross-origin request to Next.js dev resource /_next/hmr`. 서버 안의 `http://localhost:3500` 은 정상. 지금은 Caddy 가 `/_next/hmr` 의 `Origin` 을 `http://localhost:3500` 으로 바꿔 넘기는 땜질로 살려 두었고, 이 작업이 끝나면 그 블록을 지운다.
- 설계 승인: 2026-09-22 사용자 승인(bounded 설계, 대화에서 제시). 다운타임은 중지 → 동기화 → 빌드 → 기동 순서로 받아들인다. `next build` 가 실행 중인 서버가 읽는 `frontend/.next` 에 쓰고, 빌드 전 의존성 동기화는 서비스를 내린 뒤에만 하도록 계약되어 있어 빌드 후 교체는 distDir 분리가 더 필요하기 때문이다.
- 범위: `restart_all.sh` 의 `NEXT_MODE=dev|prod` 분기(기본 `dev`, `.env` → 환경 변수 → 기본값 순으로 읽고 잠금·종료 전에 검증, `prod` 면 의존성 동기화 직후 `run-next.js build` 후 `start`), `scripts/service_lifecycle.sh` 의 frontend 명령 서명 한 줄에 `run-next.js start`·`next start` 변형 추가(승인된 유일한 예외. 기록 PID 가 `run-next.js start` 래퍼라 서명이 없으면 준비 판정과 종료가 모두 거부된다), `.env.example`, README 운영 절, `deploy/systemd/README.md` 의 운영 적용·되돌리기 절차, `tests/scripts/` 회귀. `service_lifecycle.sh` 의 종료·잠금·PID 검증 로직과 도메인 리터럴은 금지. 공개 URL 출처는 `.env` 의 `NEXTAUTH_URL` 하나다.
- QA: dev 기본 경로 회귀 없음, prod 경로 build→start 순서·실패 시 미기동·잘못된 값 거부, macOS 실기동(dev), 로컬 prod 사이클(환경 변수로 `NEXT_MODE=prod`, `.env` 무변경), 운영 적용 후 HMR 오류 없음·API 호출·데이터 표시
- [x] 구현·RED→GREEN: 신규 11건 가운데 구현 전 5건 실패(prod 가 dev 를 호출, 잘못된 값과 빌드 실패가 exit 0, `start` 서명 거부)·6건 통과(dev 기본 경로 회귀 방지, 서명 dev·next-server 인정과 build 거부, 도메인 없음)를 확인한 뒤 구현. 변이 1종(빌드 블록을 백엔드 기동 뒤로 이동)에서 「아무것도 시작하지 않는다」 단언이 실패함을 확인. `env_value` 의 dotenv 대조 테스트에 `NEXT_MODE` 추가. 픽스처 초판은 준비 판정을 즉시 통과시켜 가짜 자식이 첫 줄을 실행하기 전에 스크립트가 끝나는 경합이 있었고, 적대적 테스트처럼 PID 표식을 기다리도록 고침.
- [x] macOS 실기동 첨부(2026-09-22 11:01, Darwin 25.5, Node 24.19, Next 16.3.5). dev: 떠 있던 서비스(PID 15865·15962)를 `./restart_all.sh` 가 종료 → 의존성 변경 없음 → 9초 만에 `🎉 Ready!`, `/`·`/api/kr/market-gate`(직접·rewrite 경유) 200, 기록 PID 는 `node scripts/run-next.js dev` 그룹 리더 → `./stop_all.sh` 3초 exit 0, 포트 비고 PID 파일 삭제. prod(`.env` 무변경, 환경 변수 `NEXT_MODE=prod`): `./restart_all.sh` exit 0 17초(「Compiled successfully in 3.9s」 포함), 기록 PID `node scripts/run-next.js start`(그룹 리더), 포트 3500 소유자는 그 자식 `next-server (v16.3.5)`, `/`·`/dashboard/kr`·`/api/kr/market-gate` 200, `logs/frontend.log` 에 `_next/hmr`·`Blocked cross-origin` 0건. 여섯 prod 사이클 가운데 첫 번째의 `./stop_all.sh` 만 「frontend PID 3266 의 종료를 확인하지 못했습니다」 exit 1(다른 helper 메시지 없음, 직후 포트 3500 은 비어 있었고 1분 뒤 두 프로세스 모두 없음, backend 는 종료 순서상 남았음). 이후 다섯 번(0.25초 샘플링 2회, `bash -x` 추적 3회)은 모두 3초 이내 exit 0, 두 프로세스가 1초 안에 사라짐. 심층 리뷰가 메커니즘을 특정: `lifecycle_pid_alive` 가 `kill -0` 성공·`ps -o stat=` 공백을 「살아 있음」으로 읽고 이어지는 `lifecycle_record_matches_process` 가 `ps -o lstart=` 공백에 메시지 없이 실패하는 경합(주입으로 결정적 재현, 같은 출력). TERM 대기 중의 같은 경합은 다음 `lifecycle_pid_alive` 에서 자가 치유되거나 다른 메시지를 남기므로, ❌ 만 남는 경로는 TERM 8초가 만료되어 KILL 로 넘어간 뒤뿐이다. 즉 첫 사이클의 프론트엔드는 SIGTERM 뒤 8초 넘게 살아 있었고 그 이유는 미규명(리뷰어 실측 그룹 소멸 0.03~0.04초). 동결 구역이라 `[INFRA-077]` 로 이관. 종료 로직은 이번 라운드의 변경 대상이 아니다. 실기동을 마친 뒤 로컬 서비스는 내려 둔 상태.
- [x] `/ponytail-review` → `/code-review` → `/review`(T3): ponytail-review(oh-my-claudecode:code-reviewer 레인) 9건 가운데 8건 반영(`*)` 갈래 한 줄, 테스트의 가짜 자식 정리 루프·`import signal` 삭제, `deploy/systemd/README.md` 중복 문장 4곳, `.env.example`·README 축약, 총 -17줄), `allowedDevOrigins` 대안 스니펫은 의뢰서가 요구한 되돌리기 대안이라 유지. 코드 리뷰(feature-dev:code-reviewer) APPROVE, 확신도 80 이상 지적 없음. 낮은 확신도 관찰: 가짜 자식이 `time.sleep(30)` 으로 최대 30초 잔류(20, 포트를 쥐지 않아 무해), 도메인 검사가 `CLAUDE.md` 의 Live Demo 줄에 의존(15, 줄이 사라지면 조용히 통과하지 않고 실패). 첫 종료 실패의 가설(70): Next 의 production `cleanup()` 은 `isDev` 일 때만 `server.closeAllConnections()` 를 불러 prod 에서는 `server.close()` 의 drain 을 기다린다(`start-server.js` 330-343행). 반대 근거: 브라우저 없이 curl·`urlopen` 만 썼고 Node 24 의 `server.close()` 는 유휴 keep-alive 를 끊으며, TERM 8초를 넘겨도 KILL 뒤 zombie 를 종료로 보아 성공해야 하는 구조라 ❌ 만 남기는 경로를 설명하지 못한다. 가설로만 기록했으나 심층 리뷰 실측(keep-alive 1개 보유 상태에서도 0.04초 소멸)으로 기각. 심층 리뷰(oh-my-claudecode:critic, review 스킬 절차, 재현 실험 포함) ACCEPT: MAJOR 1(종료 실패 메커니즘 특정, README 의 drain 문장이 인과처럼 읽힘) → README·TODO 정정과 `[INFRA-077]` 등록, MINOR 1(빌드 서브셸이 잠금 FD 9 를 물려줌, 빌드 중단 시 잠금 잔류 가능) → `9>&-` 추가, 같은 구멍이 있던 `sync_dependencies.sh` 호출에도 추가, MINOR 2(빈 `NEXT_MODE=` 는 조용히 dev, 주석이 반대로 단언) → `.env.example`·런북에 명시, MINOR 3(빌드 출력 무기록) → `logs/frontend.log` 에 이어 쓰고 실패 시 `lifecycle_tail_service_log` 로 마지막 15줄 출력, MINOR 4(런북 2단계에 실패 시 행동 없음) → 한 줄 추가, MINOR 5(도달하지 않는 서명 변형 넷) → 주석에 보험 취지 기록. 평가 불가 4건(운영 서버 실측, 8초 초과 원인, prod 준비 판정의 자동 회귀, 브라우저 실측). 반영 뒤 `tests/scripts/` 두 모듈 30 통과, 실제 prod 사이클 1회 추가(10초 Ready, 빌드 출력 38줄이 `logs/frontend.log` 에 기록, 종료 3초, 잠금 파일 보유자 없음). 최종 전체 `pytest -q`: 2571 passed, 2 skipped in 97.22s (0:01:37). type-check·vitest 641 은 frontend 변경이 없어 앞선 결과 유지.
- [x] 운영 적용 절차 문서화: `deploy/systemd/README.md` 「Next 를 production 으로 돌리기」(왜 dev 가 문제였는지, 기동 순서와 다운타임, 적용 5단계, 브라우저 확인 4항목, Caddy `@hmr` 제거, 되돌리기, 종료 확인 실패 시 대처), README 운영 절 한 단락, `.env.example` 키와 주석, `deploy/caddy/README.md` 의 `@hmr` 안내, `CLAUDE.md` Quick Start 한 줄. 운영 서버 적용은 미실시.


### [JONGGA-039] 저장분이 비어 있으면 「최신」 이 과거 리포트로 내려가지 않고, 배너가 표시 중인 사실을 감춘다
- 카테고리: 종가베팅 | 티어: T1 | 근거: 로컬 재현과 코드(2026-09-22). 정상 stale 갈래(어제 파일에 시그널 있음)는 `[JONGGA-009]` 대로 시그널 8건을 표식과 함께 내려주는 것을 확인했다. 남은 문제는 둘이다. ① `services/kr_market_jongga_payload_latest.py:221-241` 의 stale 갈래는 `jongga_v2_latest.json` 의 시그널이 비어 있으면 `find_recent_valid_jongga_payload` 를 부르지 않고 빈 응답에 「최신 저장 데이터는 어제입니다」 표식만 붙인다. 전날 실행이 0건으로 끝나면 `save_result_to_json` 이 빈 파일을 덮어쓰므로(`services/kr_market_jongga_runtime_service.py:128`, 0건 보호 없음) 다음 개장일 17시 전까지 화면은 배너와 「분석된 종목이 없습니다」 를 함께 보인다. `test_build_jongga_latest_payload_stale_without_signals_stays_empty` 가 이 동작을 고정하고 있다. ② `frontend/src/app/dashboard/kr/closing-bet/page.tsx:1255-1265` 배너가 굵은 제목 「오늘 종가베팅 데이터가 아직 없습니다.」 아래 `stale_warning` 을 우선 표시해, 백엔드가 함께 보내는 `message`(「가장 최근 저장분을 그대로 보여주고 있습니다」)는 어디에도 표시되지 않는다. 목록이 있어도 두 줄 모두 「없다」 고 읽힌다.
- 범위: ① stale 갈래에서 저장분 시그널이 비어 있으면 `find_recent_valid_jongga_payload` 로 내려가 표식을 붙인다. 그 함수가 `message` 를 「주말/휴일로 인해 …」 로 덮어쓰므로 표식이 나중에 적용되게 순서를 둔다. 유효한 파일이 하나도 없을 때만 빈 응답을 낸다. ② 배너 제목을 「오늘 분석은 아직 없습니다. 최신 저장분(X)을 표시합니다」 형태로 바꾸고 `message` 줄을 함께 보인다. 0건 실행이 `jongga_v2_latest.json` 을 덮어쓰는 것 자체는 손대지 않는다(`jongga_v2_results_YYYYMMDD.json` 이력에는 0건도 기록이 맞다).
- 운영 판별: 서버의 `data/jongga_v2_latest.json` 에서 `date` 와 `signals` 길이를 보면 어느 갈래인지 갈린다. 접속은 운영자가 한다.
- 설계 승인: 2026-09-22 사용자의 「백로그도 설계해서 진행해」 뒤 네 항목 일괄 설계(bounded, 대화 제시) → AskUserQuestion 「최근 유효 리포트로 대체」 선택. stale 갈래에서 저장분 시그널이 비면 `find_recent_valid_jongga_payload` 로 내려가고 그 리포트 날짜로 stale 표식을 나중에 덮는다. 유효 파일이 없을 때만 빈 응답. 오늘 자 0건과 비개장일은 종전대로. 배너는 시그널이 있으면 「오늘(날짜) 분석은 아직 없습니다. 최신 저장분(날짜)을 표시합니다.」 제목과 `message` 줄, 없으면 종전 제목.
- 파일: `services/kr_market_jongga_payload_latest.py`, `frontend/src/app/dashboard/kr/closing-bet/page.tsx`, `tests/services/test_kr_market_jongga_payload_service_refactor.py`, 새 vitest. 위험 경로 없음 → T1(구현 50줄 이하 예상). 프론트엔드: Next 번들 문서 `05-server-and-client-components.md`·`06-fetching-data.md`, 스킬 `vercel-react-best-practices`.
- [x] 설계 승인(bounded)
- [x] 구현·RED→GREEN: pytest 고정 테스트 1건을 새 계약(대체 + 표식)으로 바꾸고 「유효 파일 없음 → 빈 응답 유지」 1건 추가(구현 전 1 실패·3 통과 확인), vitest `page.regression-jongga-039.test.tsx` 2건(구현 전 1 실패). 구현 뒤 pytest 파일 9 통과, closing-bet vitest 15파일 95 통과, `npm run type-check` exit 0. 구현 diff 38줄(위험 경로 없음) → T1 유지
- [x] `/ponytail-review`(인라인): 배너의 두 갈래가 감싸는 `<div>` 를 중복해 삼항식 두 개로 줄임(-6줄). 백엔드 갈래는 더 줄일 것 없음
- [ ] QA(브라우저 실측): `docs/dev-cycle/qa/JONGGA-039.md`

### [CHAT-031] 프롬프트가 싣는 시장·시그널 값과 기준일 바로잡기
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT(2차) §1.1, §1.2, §1.3, §2.2. 실제 `data/*.json` 으로 프롬프트를 생성해 확인. ① `collect_market_context`(`chatbot/payload_service.py:24-28`)가 섹터 변동률(퍼센트)을 `sector_scores` 에 넣고 `build_system_prompt`(`chatbot/prompts.py:136-147`)가 0~100 점수로 가정해 40 미만이면 🔴 와 「점」을 붙이므로 모든 섹터가 빨간색이 된다(반도체 +2.93% 가 「2.93점, 매우 약함」). 같은 요청에서 `build_market_gate_context` 는 올바른 퍼센트 표기를 만들어 한 프롬프트에 서로 다른 단위가 두 번 실린다. 지수는 소수 아홉 자리 원값. ② `build_vcp_buy_recommendations_text` 가 `action == "BUY"` 만 담아, 분석 4건이 전부 HOLD 면 빈 문자열이 되고 `build_vcp_intent_context` 가 「현재 분석된 VCP 시그널이 없습니다」로 바꾼다. VCP 화면은 같은 파일로 표를 그리므로 사용자는 표를 보면서 옆 상담 패널에서 「없다」는 답을 받는다. ③ 시그널·뉴스 문맥에 기준일이 없어 `kr_ai_analysis.json`(2026-05-05)이 「오늘의 시장 현황」 제목 아래 실린다. 기존 테스트 두 건(`test_payload_service.py:79-86`, `test_intent_context.py:24-28`)이 이 동작을 사양으로 고정하고 있다.
- 범위: 섹터 절을 퍼센트 표기 하나로 모으고 점수 렌더 제거, 지수 자리수 포맷, 「분석 없음」과 「매수 추천 없음」 문구 분리, 시그널·뉴스·AI 분석 문맥에 기준일과 경과일 명시, 최종 시스템 프롬프트 문자열을 고정 입력으로 대조하는 회귀 테스트. `[VCP-026]` 과 무관한 별개 경로다.
- QA: 격리 /chatbot 에서 「오늘 섹터 어때?」「VCP 매수 추천 알려줘」 전송 → 첫 답변이 반도체를 상승률 2.93% 로 말하고, 둘째가 「시그널 없음」 대신 「분석 4건, 매수 추천 0건, 기준일 2026-05-05」를 말한다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

## P1 — 이번 주기

### [FE-045] 서버에 저장한 개인정보를 사용자가 실제로 지울 수 있게 한다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: `[FE-044]` 조사에서 발견. 설정 모달의 「계정 삭제」 버튼(`frontend/src/app/components/SettingsModal.tsx:630`)은 `localStorage` 와 `sessionStorage` 만 비우고 로그아웃할 뿐 서버 데이터를 지우지 않는다. 서버 DELETE 라우트는 `[INFRA-025]` 에서 제거되었고 주석만 남아 있다(`:125-142`). 실패 시 문구는 「계정 삭제 처리에 실패했습니다」라 사용자는 삭제되었다고 믿는다.
- 문제: `chatbot_storage.db` 의 대화·메모리, `paper_trading.db` 의 계좌 네 테이블, `usage.db` 의 `usage_log` 에는 기간 기반 자동 삭제가 전혀 없다. 개별 수단(대화 세션 삭제, `/clear all`, 모의 계좌 초기화)은 있으나 세 데이터베이스를 한 번에 지우는 길이 없다. `chatbot/storage_memory_manager.py:231-243` 의 `clear` 는 `user_profile` 까지 지우지만 `clear_general` 은 남기므로 어느 경로를 타느냐로 결과가 갈린다. `services/paper_trading_trade_account_mixin.py:321` 의 `reset_account` 는 `portfolio`·`trade_log`·`asset_history` 만 지우고 `owner_id` 가 이메일인 `balance` 행을 남긴다.
- 범위: 소유자 검증을 거쳐 한 이메일의 세 데이터베이스 행을 모두 지우는 경로와 화면 문구 정정. 활동 로그 파일은 30일 자동 삭제가 있으므로 이번 범위에서 제외하고 그 사실을 화면에 적는다.
- QA 시나리오: 로그인 후 대화와 모의 매수를 남긴 계정으로 삭제를 실행하면 세 데이터베이스에서 해당 행이 사라지고, 다시 로그인해도 이전 기록이 복원되지 않는다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [INFRA-077] 종료 판정의 거짓 음성 제거(`lifecycle_pid_alive` 경합)
- 카테고리: 인프라 | 티어: T2 | 근거: `[INFRA-076]` 심층 리뷰(2026-09-22). `lifecycle_pid_alive` 가 `kill -0` 성공·`ps -o stat=` 공백을 「살아 있음」으로 판정하고, 이어지는 `lifecycle_record_matches_process` 가 `ps -o lstart=` 공백에 메시지 없이 실패해 `stop_managed_service` 가 「종료를 확인하지 못했습니다」 만 남긴다. 주입으로 결정적 재현. 실제로는 프로세스가 내려간 뒤라 거짓 음성이며, 그 실패로 `stop_all.sh`·`restart_all.sh` 가 중단되어 backend 가 남는다. macOS prod 사이클에서 1/6 관측.
- 범위: `lifecycle_pid_alive` 에서 `ps` 공백을 죽음으로 판정(`[ -n "$state" ] || return 1`), `lifecycle_terminate_recorded_process` 의 TERM→KILL 승격을 stderr 에 한 줄 기록(`stop_managed_service` 의 ⚠️ 와 같은 형식. 이 기록이 있었으면 `[INFRA-076]` 의 8초 초과가 로그에 남았다), `ps` 공백을 주입하는 회귀 테스트. `[INFRA-074]`·`[INFRA-075]` 가 세운 종료 계약(종료 순서, flock, PID 토큰 검증, setsid)은 유지한다.
- 미규명 승계: prod 첫 사이클에서 프론트엔드가 SIGTERM 뒤 8초 넘게 살아 있었던 이유. 리뷰어 실측은 연결 없이·keep-alive 1개 보유 모두 0.04초 이내 소멸. 브라우저의 장기 keep-alive·RSC 스트리밍이 남은 후보이며 승격 로그가 생기면 다음 발생 때 판별한다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review`


### [FLOW-016] 누적성과 표의 순번을 전체 기준으로 매긴다
- 카테고리: 수급·백테스트 | 티어: T1 | 근거: AUDIT-FLOW(2차) §1.1, §5.1. `CumulativeClientPage.tsx:836` 이 순번을 `trades.length - idx` 로 계산하는데 그 `trades` 는 현재 페이지분에 필터까지 적용한 배열이라, 1페이지와 2페이지가 모두 50번부터 1번까지 매겨지고 서로 다른 거래에 같은 번호가 붙는다. 서버가 보내는 `pagination.total`·`page` 를 쓰지 않는다. 실측 재현.
- 범위: `TradeTable` 에 `pagination` 을 넘겨 `total - (page - 1) * limit - idx` 로 계산. 필터가 켜진 동안의 순번 표기 방식(비우기 또는 「필터 결과 내 순번」 표시)을 정해 반영. 2페이지 첫 행 번호를 고정하는 vitest 회귀 테스트.
- QA: `/dashboard/kr/cumulative` 진입 → 표 첫 행 번호를 읽고 다음 페이지로 이동 → 1페이지가 234 로 시작하고 2페이지가 184 로 이어진다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [FLOW-017] 결과·등급 필터를 전체 기간에 건다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW(2차) §1.2, §5.1. `/api/kr/closing-bet/cumulative` 가 `page`·`limit` 만 받아 잘라낸 뒤 화면(`CumulativeClientPage.tsx:990-994`)이 그 50건을 다시 거른다. 「성공」을 누르면 전체 86건이 아니라 현재 페이지 안의 성공만 보이고 페이지 수는 그대로다. 1144줄 주석이 명시한 의도적 단순화이므로 결함이 아니라 개선 항목이다. 「현재 페이지 내」 안내가 결과 필터에만 있고 등급 「전체」 버튼에는 건수가 없다.
- 범위: 라우트에 `outcome`·`grade` 쿼리 파라미터 추가(잘못된 값은 400), `paginate_items` 앞에서 거르고 캐시된 `trades` 와의 관계 확인, 화면의 클라이언트 필터 제거와 버튼 건수의 서버 집계 교체, 등급 「전체」 건수 추가와 안내 정리, 라우트 pytest 와 화면 vitest 회귀 테스트.
- QA: 「성공」 필터 클릭 → 버튼 건수가 86 이고 표의 전체 행수와 페이지 수가 그 86건에 맞게 바뀐다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [FLOW-019] 세 화면의 모집단 규칙을 맞추고 화면에 적는다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW(2차) §2.2, §5.2. 누적성과 KPI(`kpi_helpers.py:31, 74`)는 D 등급을 포함하고(`[FLOW-013]` 의 의도적 결정), 종가베팅 화면(`closing-bet/page.tsx:899, 1033`)은 D 를 제외하며, 백테스트 요약(`kr_market_analytics_service.py:329, 366`)은 결과 파일을 최근 30개로 자르는데 누적성과는 전부 읽는다. 현행 판정기(`engine/grade_decider.py:55-67`)는 S·A·B 만 내므로 D 는 2월 자료 7건에만 있는 과거 등급이다. 파일이 30개를 넘으면 두 화면의 승률이 벌어진다(지금 18개). `Grade` 열거형의 C 가 저장 자료에 섞이면 누적 추천수에만 잡히고 어느 등급 카드에도 나타나지 않는다.
- 범위: 누적성과의 D 포함과 종가베팅 화면의 D 제외 가운데 기준을 정하고 한 자리에 기록, 30개 상한을 요약 화면에 기준 기간으로 표시, 등급 집합 밖의 값이 들어오면 카드 합과 누적 추천수의 불일치가 드러나게 처리, 그 일치를 고정하는 pytest 회귀 테스트.
- QA: `/dashboard/kr/cumulative` 와 `/dashboard/kr/closing-bet` 을 차례로 열어 추천 건수와 승률을 읽는다 → 두 화면의 기준이 문구로 설명되고 D 취급이 일치한다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [CHAT-032] 종목 질의 문맥이 언제나 비는 경로 복구
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT(2차) §3.1. `get_chatbot()` 이 `data_fetcher` 없이 인스턴스를 만들고 운영 코드 어디서도 넘기지 않아 `get_cached_data` 가 항상 `fetch_mock_data()`(`vcp_stocks: []`)로 떨어진다. 그래서 `[종목 조회 컨텍스트]` 절, `## VCP 상위 종목` 절, 웰컴 메시지 Top 3, 관심종목 요약이 모두 죽어 있고, 웰컴 메시지가 예시로 드는 「삼성전자 어때?」도 페르소나만 남는다. VCP 상담 모드가 `[종목명(티커)]` 접두를 붙여 보내도 서버는 그 종목 자료를 싣지 않는다. 실제 종목 맵과 CSV 로 최근 5일 주가·수급·시그널 이력을 붙이는 `detect_stock_query_from_stock_map` 은 테스트만 부른다. `[CHAT-005]` 가 그 private 래퍼를 미사용으로 지웠으나 살아 있는 경로가 늘 빈 목록을 본다는 사실은 그때 다루지 않았다.
- 범위: `_detect_stock_query` 를 `detect_stock_query_from_stock_map` 으로 연결, VCP 상담 모드의 선택 종목 문맥 확인(없으면 접두 파싱), `fetch_mock_data`·`detect_stock_query_from_vcp_data` 처리 방향 결정, 웰컴 Top 3 를 살릴지 문구에서 뺄지 결정, 종목명·티커 두 갈래의 문맥 주입 회귀 테스트.
- QA: 격리 /chatbot 에서 「삼성전자 어때?」 전송 → 답변이 최근 5일 종가와 외국인·기관 순매수 수치를 인용한다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [CHAT-033] 챗봇 저장소의 스레드 동시성 확보
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT(2차) §1.4, §1.5, §5.1. 프로세스당 챗봇 인스턴스 하나를 워커의 스레드 여덟 개가 공유하는데 `MemoryManager` 와 `HistoryManager` 에 잠금이 없다. ① `add()` 가 `_reload()` 로 `self.memories` 를 통째로 교체한 뒤 `_save_single_entry` 가 그 사전을 다시 읽으므로, 그 사이 다른 스레드의 `view()`(모든 채팅 요청이 부름)가 사전을 또 교체하면 `KeyError`, `update()` 는 옛 값 저장. ② `HistoryManager._save()` 가 변경 표시가 비었거나 델타 저장이 실패하면 `save_history_sessions_to_sqlite` 로 떨어지고, 그 끝의 `_delete_stale_sessions_cursor` 가 이 워커 메모리에 없는 세션(다른 워커가 만든 것 포함)을 지우며 메시지는 CASCADE 로 함께 사라진다. 메모리 쪽은 `[CHAT-022]` 가 upsert 전용으로 고쳤으나 히스토리에는 같은 수정이 없다. 동시성 테스트가 없어 고쳐도 재발을 막을 장치가 없다.
- 범위: `MemoryManager` 의 재적재·쓰기를 인스턴스 잠금으로 직렬화, `_save_single_entry` 에 레코드를 인자로 전달, `_save()` 전체 동기화 폴백의 삭제 절 제거, 델타 장부와 세션 사전 접근 잠금, 두 스레드 동시 쓰기에서 유실·`KeyError` 가 없음을 확인하는 테스트. 테이블을 정의하는 `storage_sqlite_common.py` 는 건드리지 않는다. diff 가 300줄을 넘으면 T3 로 올린다.
- QA: 격리 /chatbot 두 탭에서 같은 계정으로 각각 대화를 만들고 동시에 메시지를 보낸 뒤 새로고침 → 두 대화가 모두 남고 메시지가 유실되지 않는다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [FE-046] 활동 로그의 보관 기간을 날짜 기준으로 만들고 데이터 파일 권한을 좁힌다
- 카테고리: 프론트엔드 공통 | 티어: T2 | 근거: `[FE-044]` 리뷰. `services/activity_logger.py:24` 의 `TimedRotatingFileHandler(when='midnight', backupCount=30)` 는 날짜가 아니라 파일 개수를 세며, 기록이 없는 날에는 회전 자체가 일어나지 않는다. 실측 결과 `logs/` 에 `user_activity.log.2026-02-22` 부터 20개 파일이 남아 보관 범위가 7개월이다. 그 파일에는 IP 주소와 챗봇 질문·답변이 각각 앞 2000자까지 들어 있다.
- 함께: `data/paper_trading.db`, `data/usage.db`, `data/runtime_cache.db`, `logs/user_activity.log` 의 권한이 모두 0644 이며 이를 좁히는 코드가 저장소에 없다.
- 문제: `[FE-044]` 의 개인정보처리방침은 이 실제 동작을 사실대로 적었으므로 지금은 거짓이 아니다. 다만 「최근 30일분의 파일」이라는 서술은 이용자가 기대하는 보관 기간보다 길게 남을 수 있다는 뜻이며, 날짜 기준 삭제를 넣으면 방침을 더 짧고 분명하게 고칠 수 있다.
- 범위: 날짜를 기준으로 오래된 활동 로그 파일을 지우는 갈래 추가, 개인정보가 담긴 파일의 권한을 0600 으로 좁히는 갈래 추가, 두 가지를 고정하는 회귀 테스트, 그리고 `frontend/src/app/(legal)/privacy/page.tsx` 3항 문안의 갱신.
- QA 시나리오: 오래된 날짜의 활동 로그 파일을 만들어 두고 기동하면 기준 기간이 지난 파일이 사라지며, 새로 만들어진 데이터베이스 파일의 권한이 0600 이다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

## P2 — 대기

### [FE-047] 루트 레이아웃의 `lang` 을 한국어로 바로잡는다
- 카테고리: 프론트엔드 공통 | 티어: T1 | 근거: `[FE-044]` 리뷰. `frontend/src/app/layout.tsx:18` 이 `<html lang="en">` 인데 화면의 문구가 전부 한국어다. 화면 낭독기가 영어 발음 규칙으로 읽고 브라우저의 번역 제안도 어긋난다. 새로 만든 법적 고지 두 화면에서 특히 두드러진다.
- 범위: `frontend/src/app/layout.tsx` 의 한 낱말과 이를 고정하는 계약 테스트. 다른 화면의 문구는 건드리지 않는다.
- QA 시나리오: 아무 화면에서나 문서의 `lang` 속성이 `ko` 로 읽힌다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` - [ ] QA

### [INFRA-078] 격리 실행이 원본 `runtime_cache.db` 에 쓰는 절대 경로 세 곳
- 카테고리: 인프라 | 티어: T1 | 근거: `[VCP-026]` QA(2026-09-22). scratchpad 사본을 cwd 로 삼은 임시 백엔드가 원본 `data/runtime_cache.db` 에 행을 남겼다. `services/file_row_count_cache.py:50`, `services/common_update_status_service.py:49`, `services/kr_market_data_cache_jongga.py:48` 이 `_BASE_DIR/data/runtime_cache.db` 를 절대 경로로 잡고, `services/common_update_status_service.py`·`services/scheduler_runtime_status_service.py` 가 같은 방식으로 `v2_screener_status.json`·`scheduler_runtime_status.json` 을 원본 `data/` 에 쓴다(기동 시 초기화 플래그라 내용은 무해). 다른 캐시 모듈은 `data_dir` 인자나 원본 파일의 디렉터리에서 경로를 만든다. `browser-notes.md` 「공통」 절이 이 종류의 구멍을 일반론으로만 경고한다.
- 범위: 세 모듈이 다른 캐시와 같은 방식(`data_dir` 인자 또는 대상 파일의 디렉터리)으로 경로를 정하게 하고, 격리 실행 뒤 원본 `data/` 가 바뀌지 않음을 확인하는 회귀 테스트. 운영 동작은 바뀌지 않는다(같은 파일).
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` - [ ] QA

### [VCP-027] 실패 AI 재분석의 대상 날짜를 화면과 같은 판정으로 정한다
- 카테고리: VCP 시그널 | 티어: T1 | 근거: `[VCP-026]` 심층 리뷰 MINOR 2(2026-09-22, 재현됨). 화면의 날짜 목록과 「최신」 대체는 `_is_vcp_signal_row` 를 통과한 날짜의 최댓값을 쓰지만, `services/kr_market_vcp_reanalysis_service.py:61-63` 의 `prepare_vcp_signals_scope` 는 판정 없이 `signal_date` 전체의 최댓값을 쓴다. 2026-09-10 에 유효 행이 있고 2026-09-15 행이 전부 CLOSED 면 화면은 09-10 을 보이는데 재분석 스코프는 09-15 다. `[VCP-026]` 전에는 최신 탭이 비어 관리자가 그 단추를 누를 일이 없었으나 이제 도달할 수 있다.
- 범위: `prepare_vcp_signals_scope` 의 날짜 없는 갈래에 같은 판정을 걸지, 판정 탈락 행(CLOSED)의 실패 AI 도 재분석 대상으로 둘지 먼저 정한다. 결정에 따라 스코프 함수와 회귀 테스트.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` - [ ] QA

### [FLOW-018] 겹치는 재추천을 어떻게 셀지 정하고 화면에 드러낸다
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: AUDIT-FLOW(2차) §2.1. 거래 식별자가 `f"{ticker}-{stats_date}"`(`kr_market_backtest_trade_helpers.py:298`)라 청산 전에 다시 추천된 종목이 독립한 두 거래로 집계된다. 실측 234건 중 13건. 005935 삼성전자우는 09-04 진입분이 09-08 익절(+5.0%)되기 전인 09-07 에 재추천되어 그 건이 손절(-3.0%)로 잡혔다. 승률·손익비는 독립 시행을 가정하는 지표인데 같은 가격 움직임이 두 번 반영되고, 화면에 그 가정이 적혀 있지 않다.
- 범위: 설계 판단이 먼저다. 현행 유지 + 툴팁에 「추천 단위 집계, 재추천 미합산」 명시 / 겹치는 재추천 제외 / 겹침 건수를 별도 지표로 표시 가운데 하나를 정하고 근거를 남긴 뒤 `aggregate_cumulative_kpis` 또는 툴팁을 수정, 겹침 사례를 담은 고정 자료로 회귀 테스트.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA(승률 카드 툴팁·값 확인)

### [FLOW-020] 「최고가」 열이 값을 숨기지 않게 한다
- 카테고리: 수급·백테스트 | 티어: T1 | 근거: AUDIT-FLOW(2차) §1.3. `CumulativeClientPage.tsx:874` 가 `maxHigh > 0` 이 아니면 `-` 를 그려, 실측에서 032830 삼성생명(진입가 307,000, 청산일까지 최고가 302,500, 최대상승률 -1.5%)이 하이픈으로 보인다. 값이 없는 것인지 한 번도 오르지 않은 것인지 구분되지 않고, 양수도 부호 없이 적어 같은 화면의 `formatSignedPercent` 표기와 다르다.
- 범위: 음수를 부호와 함께 표시하고 자료가 없을 때만 하이픈, 양수 표기를 `formatSignedPercent` 와 통일, 음수·0·양수 세 경우의 vitest 회귀 테스트.
- QA: 2026-09-01 삼성생명 행의 최고가 열에 `-1.5%` 가 보인다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [CHAT-034] SQLite 누락 테이블 복구 래퍼 통합
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT(2차) §2.1. `storage_sqlite_history.py` 여섯 곳과 `storage_sqlite_memory.py` 여덟 곳, 열네 함수가 「스키마 확인 → `run_sqlite_with_retry` → `_is_missing_table_error` 면 `force_recheck` 뒤 `_retried=True` 로 재호출」 골격을 복제하고 있다. 재시도·복구 조건을 바꾸면 열네 곳을 함께 고쳐야 하고, 한 곳을 빠뜨려도 평소에는 증상이 없다. 공용 래퍼를 `services/sqlite_utils.py`(공통 접속 계층, 위험 경로)에 두면 T3.
- 범위: 공통 골격을 데코레이터 또는 헬퍼 하나로 추출, 테이블 이름만 주입, 양쪽 공개 함수 시그니처 유지, 열네 경로 모두의 복구 동작 테스트.
- QA: `data/chatbot_storage.db` 를 지운 상태에서 질문을 보내고 사이드바 확인 → 오류 없이 답변이 오고 새 대화가 목록에 나타난다.
- [ ] 설계 승인 - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` → `/review` - [ ] QA

### [CHAT-035] HistoryManager 의 책임 분리
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT(2차) §4.1. `chatbot/storage.py:39-493` 의 한 클래스가 SQLite 적재·저장, 레거시 JSON 스냅샷, 파일 서명 재적재 판정, 메시지·세션 LRU 캐시 둘, 델타 장부, 세션 CRUD, 메시지 CRUD 여덟 책임을 진다. `[CHAT-033]` 의 결함은 델타 장부·저장·재적재가 서로의 상태를 잠금 없이 건드리는 자리에서 나왔다. 선행 조건: `[CHAT-033]` 완료. 같은 자리를 두 항목이 동시에 건드리면 충돌한다.
- 범위: 레거시 스냅샷 동기화, LRU 캐시와 파일 서명 판정, 델타 장부를 각각 분리. 기존 공개 메서드 시그니처와 기존 테스트 16건 통과 유지.
- QA: 대화 생성·메시지 송수신·삭제 후 새로고침 → 목록과 본문이 조작한 대로 남는다.
- [ ] 설계 승인 - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` → `/review` - [ ] QA

### [JONGGA-040] 종가베팅 결과를 저장한 뒤 `jongga_v2_latest.json` 을 비원자적으로 한 번 더 쓴다
- 카테고리: 종가베팅 | 티어: T1 | 근거: 2026-09-22 저장 경로 재점검. `engine/generator.py:170` 의 `run_screener` 가 `save_result_to_json` 으로 일자 파일과 최신 파일을 `atomic_write_text` 로 이미 쓰는데, 스케줄러 진입 함수 `scripts/init_data.py:1685-1687` 의 `create_jongga_v2_latest` 가 같은 내용을 `open(..., 'w')` 로 최신 파일에 다시 쓴다. `services/kr_market_route_service.py:103` 과 `services/kr_market_jongga_runtime_service.py:128` 도 `run_screener` 뒤에 `save_result_to_json` 을 한 번 더 부른다. 두 번째 쓰기 도중 프로세스가 죽으면 최신 파일만 잘린 채 남고, `kr_market_data_cache_core.py:229` 의 `json.load` 가 예외를 내므로 「최신」 조회가 다음 저장 때까지 실패한다. 일자 파일은 온전해 이력은 잃지 않는다.
- 범위: 중복 쓰기 세 곳을 지운다. `create_jongga_v2_latest` 가 파일을 직접 열지 않는 것을 고정하는 회귀 테스트 한 건.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` - [ ] QA

### [VCP-030] `signals_log.csv` 쓰기를 원자적으로 바꾸고 0바이트 파일에서 회복한다
- 카테고리: VCP 시그널 | 티어: T3 (`scripts/init_data.py` 위험 경로) | 근거: `[VCP-029]` 계획 검토(oh-my-claudecode:critic, 2026-09-22) R4. `create_signals_log` 의 `to_csv` 세 곳은 파일을 자르고 쓰므로 중간에 죽으면 잘린 파일이나 0바이트 파일이 남는다. `[VCP-029]` 뒤에는 0바이트 파일에서 `pd.read_csv` 가 `EmptyDataError` 를 내어 이후 모든 실행이 「보존 + False」 갈래로 빠진다. 스케줄러 ERROR 로그는 남지만 운영자가 손보기 전까지 오늘 자 시그널이 저장되지 않는다. 종전 코드는 덮어쓰기로 스스로 회복하던 자리였다. `[JONGGA-040]` 의 형제 항목이다.
- 함께(`[VCP-029]` 심층 리뷰 M2·m4): 손상은 0바이트만이 아니다. 열 수가 다른 행이 든 파일은 쓰는 쪽(`scripts/init_data.py:1580`, 전체 열 읽기)만 `ParserError` 로 막히고, 화면 쪽(`services/kr_market_vcp_payload_service.py:169-173`, `app/routes/kr_market_data_signals_routes.py:65-71`, `usecols` 읽기)은 예외 없이 보존된 행을 계속 보이므로 막힌 상태가 화면에 드러나지 않고 그날 자 옛 행이 남아 있으면 최신 대체가 그것을 오늘 자로 계속 노출한다. 0바이트일 때는 `_extract_csv_data_date` 가 `None` 을 돌려주고 `services/common_data_status_service.py:71` 이 `vcp_signals_latest.json`(세 실패 갈래가 모두 `date=오늘` 로 씀)으로 대체해 데이터 상태 화면이 「오늘」로 보인다.
- 범위: CSV 를 임시 파일에 쓴 뒤 교체하는 방식으로 바꾸고(`services/kr_market_data_cache_service.py` 의 `atomic_write_text` 재사용 가능 여부를 설계에서 본다), 파싱에 실패한 파일의 회복 경로를 정한다(0바이트·헤더뿐인 파일은 「기존 로그 없음」으로, 열 수가 어긋난 파일은 원본을 `.corrupt-<시각>` 으로 옮겨 보존한 뒤 새로 시작하는 안을 설계에서 본다). 쓰는 쪽과 읽는 쪽의 관용도 차이를 설계에 적는다. 회귀 테스트 세 건.
- [ ] 설계 승인(bounded) - [ ] 계획 검토 - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` → `/review` - [ ] QA

### [VCP-033] AI 규칙 기반 폴백이 낮은 합산 점수의 VCP 시그널을 일괄 SELL 로 판정한다
- 카테고리: VCP 시그널 | 티어: T3 (`engine/vcp_ai_analyzer_helpers.py` 위험 경로) | 근거: `[VCP-032]` 코드 리뷰(feature-dev:code-reviewer, 2026-09-22, 확신도 중간). `build_vcp_rule_based_recommendation` 은 LLM 응답의 JSON 파싱이 실패했을 때 합산 점수 `score <= 62` 면 SELL, `>= 78` 이면 BUY 로 판정한다. 종전에는 저장 게이트가 60 이상을 보장했지만 `[VCP-032]` 뒤에는 12~59점 시그널이 정상 저장되므로, 폴백을 타는 시그널은 거의 예외 없이 SELL 이 된다. 「약한 수급은 보수적으로 SELL」 이 의도인지, 옛 게이트 전제가 남은 것인지 정해야 한다.
- 범위: 폴백 기준을 새 점수 분포(패턴 통과 종목의 합산 27~53)에 맞추거나 VCP 원점수·수축비 같은 패턴 지표로 바꾼다. 폴백은 실패 경로라 실측은 파싱 실패를 주입한 하네스로 한다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` → `/review` - [ ] QA

### [VCP-031] 「Refresh VCP」가 시그널 저장 실패를 「완료: 조건 충족 종목 없음」 성공으로 보인다
- 카테고리: VCP 시그널 | 티어: T2 | 근거: `[VCP-029]` 심층 리뷰(oh-my-claudecode:critic, 2026-09-22) M1. `services/kr_market_vcp_background_service.py:78-86` 은 `create_signals_log` 의 반환값이 `False` 면 `elif result_df:` 를 통과하지 못하고 else 로 떨어져 `status="success"` 와 「완료: 조건 충족 종목 없음」을 세운다. `[VCP-028]`·`[VCP-029]` 뒤에는 스크리너 예외, 병합 실패, 정리 실패가 전부 `False` 이므로 시그널이 실제로 있었는데 저장만 실패한 경우까지 관리자는 성공 상태를 본다. 유일한 흔적은 `logs/backend.log` 의 WARNING 한 줄이다. `:78` 의 `isinstance(result_df, pd.DataFrame)` 은 죽은 분기다(`create_signals_log` 는 DataFrame 을 돌려주는 갈래가 없다). 같은 파일 `:82` 의 `elif result_df:` 갈래도 함께 본다.
- 범위: `False` 를 `status="error"` 와 실패 문구로 옮기고 죽은 분기를 지운다. 종전처럼 「조건 충족 종목 없음」은 `True` 이면서 최신 payload 의 시그널이 0건일 때만 보인다. 회귀 테스트 두 건(False → error, True + 0건 → 종전 문구).
- QA 시나리오: 손상 사본을 둔 격리 백엔드에서 「Refresh VCP」 를 누르면 상태창이 error 와 실패 문구를 보인다. 원본 `data/` 에서는 실행하지 않는다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA
