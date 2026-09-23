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


## P1 — 이번 주기

## P2 — 대기

### [CHAT-035] HistoryManager 의 책임 분리
- 카테고리: 챗봇 | 티어: T3 | 근거: AUDIT-CHAT(2차) §4.1. `chatbot/storage.py:39-493` 의 한 클래스가 SQLite 적재·저장, 레거시 JSON 스냅샷, 파일 서명 재적재 판정, 메시지·세션 LRU 캐시 둘, 델타 장부, 세션 CRUD, 메시지 CRUD 여덟 책임을 진다. `[CHAT-033]` 의 결함은 델타 장부·저장·재적재가 서로의 상태를 잠금 없이 건드리는 자리에서 나왔다. 선행 조건: `[CHAT-033]` 완료(2026-09-23 충족, 커밋 `bd5adf1`). 같은 자리를 두 항목이 동시에 건드리면 충돌한다.
- 범위: 레거시 스냅샷 동기화, LRU 캐시와 파일 서명 판정, 델타 장부를 각각 분리. 기존 공개 메서드 시그니처와 기존 테스트 16건 통과 유지.
- QA: 대화 생성·메시지 송수신·삭제 후 새로고침 → 목록과 본문이 조작한 대로 남는다.
- [ ] 설계 승인 - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` → `/review` - [ ] QA

### [VCP-030] `signals_log.csv` 쓰기를 원자적으로 바꾸고 0바이트 파일에서 회복한다
- 카테고리: VCP 시그널 | 티어: T3 (`scripts/init_data.py` 위험 경로) | 근거: `[VCP-029]` 계획 검토(oh-my-claudecode:critic, 2026-09-22) R4. `create_signals_log` 의 `to_csv` 세 곳은 파일을 자르고 쓰므로 중간에 죽으면 잘린 파일이나 0바이트 파일이 남는다. `[VCP-029]` 뒤에는 0바이트 파일에서 `pd.read_csv` 가 `EmptyDataError` 를 내어 이후 모든 실행이 「보존 + False」 갈래로 빠진다. 스케줄러 ERROR 로그는 남지만 운영자가 손보기 전까지 오늘 자 시그널이 저장되지 않는다. 종전 코드는 덮어쓰기로 스스로 회복하던 자리였다. `[JONGGA-040]` 의 형제 항목이다.
- 함께(`[VCP-029]` 심층 리뷰 M2·m4): 손상은 0바이트만이 아니다. 열 수가 다른 행이 든 파일은 쓰는 쪽(`scripts/init_data.py:1580`, 전체 열 읽기)만 `ParserError` 로 막히고, 화면 쪽(`services/kr_market_vcp_payload_service.py:169-173`, `app/routes/kr_market_data_signals_routes.py:65-71`, `usecols` 읽기)은 예외 없이 보존된 행을 계속 보이므로 막힌 상태가 화면에 드러나지 않고 그날 자 옛 행이 남아 있으면 최신 대체가 그것을 오늘 자로 계속 노출한다. 0바이트일 때는 `_extract_csv_data_date` 가 `None` 을 돌려주고 `services/common_data_status_service.py:71` 이 `vcp_signals_latest.json`(세 실패 갈래가 모두 `date=오늘` 로 씀)으로 대체해 데이터 상태 화면이 「오늘」로 보인다.
- 범위: CSV 를 임시 파일에 쓴 뒤 교체하는 방식으로 바꾸고(`services/kr_market_data_cache_service.py` 의 `atomic_write_text` 재사용 가능 여부를 설계에서 본다), 파싱에 실패한 파일의 회복 경로를 정한다(0바이트·헤더뿐인 파일은 「기존 로그 없음」으로, 열 수가 어긋난 파일은 원본을 `.corrupt-<시각>` 으로 옮겨 보존한 뒤 새로 시작하는 안을 설계에서 본다). 쓰는 쪽과 읽는 쪽의 관용도 차이를 설계에 적는다. 회귀 테스트 세 건.
- 설계 승인: 승인 일자 2026-09-23 | 승인 확인 시각 2026-09-23 14:19 | 범위: `create_signals_log` 의 `to_csv` 다섯 곳을 기존 `services/kr_market_vcp_reanalysis_service.write_vcp_signals_csv_atomic`(BOM 포함 원자적 교체) 호출로 바꾸고, 기존 로그를 읽는 두 곳에서 `EmptyDataError`(0바이트·BOM 만 든 파일)를 「기존 로그 없음」으로 이어간다. 열 수가 어긋난 파일(`ParserError`)은 `[VCP-029]` 대로 보존 + False 를 유지하고 `.corrupt-<시각>` 격리는 하지 않는다. 쓰는 쪽과 읽는 쪽의 관용도 차이는 계획 문서에 기록만 한다. 회귀 테스트 세 건, 격리 사본 QA(가짜 스크리너 하네스 + 브라우저 확인) | 근거: 대화에서 bounded 설계를 제시하고 사용자가 「응 진행해」로 승인
- [x] 설계 승인(bounded)
- [x] 계획 검토: 계획 `docs/superpowers/plans/2026-09-23-vcp-030-signals-log-atomic-write.md`, oh-my-claudecode:critic ACCEPT-WITH-RESERVATIONS. R1(당일 정리 갈래의 원자성을 잡는 테스트 없음 → 쓰기 실패 테스트를 병합·정리 두 경우로 parametrize, 변이 목록 추가), R2(캐시 무효화의 DELETE 는 `dirname(csv)/runtime_cache.db` 로 가므로 테스트는 원본에 닿지 않음 → 문장 정정), R3(파일 권한 0644→0600 → 수용한 차이에 기록) 반영. m1(ENOSPC·파일 없음에서 False 대신 OSError, 호출자 둘 모두 실패 처리)은 기록만 함. m2 는 확인 사항
- [x] 구현·RED→GREEN: 신규 테스트 3건(마지막은 병합·정리 parametrize) 구현 전 4건 실패 확인 뒤 구현. 관련 6모듈 60 통과. 변이 3종(`EmptyDataError` except 제거, 병합 쓰기 `to_csv` 복원, 정리 쓰기 `to_csv` 복원)이 각각 해당 테스트를 실패시킴. 격리 사본 전체 pytest 2685 passed 1 failed 3 skipped, 실패 1건은 사본이 git 저장소가 아니라서 실패하는 `test_gitignore_hides_macos_appledouble_and_ds_store_files` 이며 원본 트리에서 통과
- [x] `/ponytail-review` → `/code-review` → `/review`: ponytail-review Lean already. closing-bet-reviewer APPROVE(범위 안 결함 없음). 지적 1(`SignalTracker` 쓰기 세 곳이 여전히 비원자) → `[VCP-034]` 등록, 원자성 주장을 `create_signals_log` 로 한정. 지적 2(예외 갈래 빈 파일 쓰기가 ENOSPC 로 실패하면 최신 JSON 도 건너뜀) → 계획에 기록. 지적 3(병합 실패 시에도 최신 JSON 은 먼저 쓰임)은 `[VCP-029]` 부터의 기존 동작이라 기록만 함. 심층 리뷰(oh-my-claudecode:critic, review 스킬 절차) APPROVE. Minor 1(`[VCP-034]` 근거가 「막힘」으로 적혔으나 실측은 「손상 행이 조용히 굳음」) → 근거 정정. 참고: 재분석 경로와의 동시 쓰기 경합은 기존 문제, 운영 `data/signals_log.csv` 가 symlink 이면 `os.replace` 가 일반 파일로 바꾼다(미확인, 계획에 기록), 0600 을 다른 계정으로 읽는 저장소 밖 소비자는 확인 불가
- [ ] QA

### [VCP-034] `SignalTracker` 의 `signals_log.csv` 쓰기 세 곳도 원자적으로 바꾼다
- 카테고리: VCP 시그널 | 티어: T2 (`engine/signal_tracker_analysis_mixin.py` 는 `tier-rules.md` §2 목록에 없음, 설계에서 건드릴 파일로 재판정) | 근거: `[VCP-030]` 코드 리뷰(closing-bet-reviewer, 2026-09-23) 지적 1. `engine/signal_tracker_analysis_mixin.py:339`(새 파일), `:387`(추가 병합), `:423`(청산 갱신)이 같은 `data/signals_log.csv` 를 `to_csv` 로 자르고 쓴다. `services/common_update_pipeline_steps.py:220-226` 이 `create_signals_log` 직후 `SignalTracker().update_open_signals()` 를 부르므로 매 실행에서 이어서 돈다. 도중에 죽으면 0바이트 파일은 `[VCP-030]` 의 회복이 받아 준다. 그러나 행 중간에서 잘린 파일(`...\n005930,2026-02-1`)은 예외 없이 읽혀 `signal_date=2026-02-1`·`score=NaN` 같은 손상된 행이 되고, 다음 `create_signals_log` 가 그 행을 옛 날짜로 병합해 원자적으로 다시 쓰면서 True 를 돌려준다. 즉 실행이 막히기보다 손상이 조용히 굳는다. `ParserError`(보존 + False)는 따옴표 필드 안에서 잘린 경우에만 났다(`[VCP-030]` 심층 리뷰 실측, pandas 2.3.3). 헤더 중간에서 잘린 파일(`ticker,sig`)은 당일 정리 갈래가 `signal_date` 열이 없다며 필터를 건너뛰고 그대로 다시 쓴다.
- 범위: 세 곳을 `services/kr_market_vcp_reanalysis_service.write_vcp_signals_csv_atomic` 으로 바꾸고 각 뒤의 `_refresh_signals_log_source_cache` 와의 관계(무효화 순서)를 설계에서 본다. 회귀 테스트는 쓰기 실패 시 원본 바이트 유지.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] 리뷰 - [ ] QA

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1 | 근거: `[FE-045]` 계획 검토(2026-09-22). `services/usage_tracker.py`(`usage_log`)와 `engine/services/usage_tracker.py`(`api_usage`)는 이메일을 기본 키로 쓰지만 어떤 운영 코드도 import 하지 않는 유물이다. 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한다. 행이 있으면 그 이메일 행을 지우는 절차(또는 파일 제거)와 두 모듈·테스트의 삭제를 설계한다. 행이 없으면 두 모듈과 테스트 여섯 파일의 삭제만 남는다. 원격 서버 접속은 운영자가 한다.
- [ ] 운영 서버 행 수 확인(운영자) - [ ] 설계 승인(bounded) - [ ] 구현·검증

### [CHAT-037] 프록시가 끊은 뒤 완료된 챗봇 스트림도 무료 사용량을 차감한다
- 카테고리: 챗봇 | 티어: T2 | 근거: `[CHAT-036]` QA S-3(`docs/dev-cycle/qa/CHAT-036.md` 이월한 발견). Next 프록시가 120초 무활동으로 upstream 을 끊어 사용자는 「서버 응답을 받지 못했습니다 (HTTP 500)」 를 봤는데, Flask 는 침묵을 마친 뒤 닫힌 소켓에 스트림을 끝까지 쓰고 `services/kr_market_chatbot_stream_helpers.py` 의 `on_finalize` 가 `stream_has_error=False` 로 `maybe_increment_chatbot_usage` 를 불러 무료 횟수를 1 차감했다(격리 Flask 로그 「[QUOTA] … stream_has_error=False」 → 「사용량 차감 완료 … -> 4회」, 화면의 「N회 남음」 도 줄었다). 답을 받지 못한 요청에 횟수가 쓰인다.
- 범위: 클라이언트 연결이 끊긴 뒤의 완료를 구분하는 방법 결정(닫힌 소켓 쓰기 실패 감지, `stream_with_context` 생성기의 `GeneratorExit`, 또는 `done` 이벤트가 실제로 쓰였을 때만 차감), 그 경우 차감을 건너뛰는 규칙과 테스트. 정상 도착 경로의 차감은 바꾸지 않는다.
- QA: 격리 /chatbot 에서 첫 토큰이 130초 늦는 가짜 클라이언트로 전송 → 오류 문구가 뜬 뒤 「N회 남음」 이 줄지 않는다. 브라우저 실측 required.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [INFRA-080] Next rewrite 프록시가 gunicorn 요청을 ECONNRESET 으로 잃고 500 을 낸다
- 카테고리: 인프라 | 티어: T2 | 근거: `[FLOW-019]` QA S-5 1회차(2026-09-23). 격리 환경(gunicorn `--workers 1 --threads 4`, Next dev)에서 종가베팅 화면 첫 로드 때 차트 요청 여러 개 가운데 `GET /api/kr/stock-chart/003160?period=1m&end=2026-09-21` 하나가 18ms 만에 500 이 되었고, Next 로그에 `Failed to proxy … Error: read ECONNRESET` 이 남았다. 같은 요청을 Flask 에 직접 보내면 200 이며, 이어진 다섯 번 로드에서는 재현되지 않았다. 원인은 미규명이다. gunicorn 의 keep-alive 기본값(2초)이 끝나 닫힌 연결을 프록시가 재사용하는 경합이 가설이며, 그렇다면 같은 구성인 운영에서도 드물게 차트나 API 요청 하나가 실패할 수 있다.
- 범위: 먼저 재현 조건을 확정한다(유휴 시간 뒤 동시 요청, keep-alive 값 변화). 가설이 맞으면 `restart_all.sh` 의 gunicorn `--keep-alive` 를 Next 프록시의 유휴 연결 유지 시간보다 길게 두는 안과 재시도 안을 비교한다. 재현 스크립트나 회귀 테스트를 남긴다.
- QA: 격리 환경에서 유휴 뒤 종가베팅 화면을 여러 번 열어도 5xx 와 ECONNRESET 이 없다. 브라우저 실측 required.
- [ ] 재현·원인 확정 - [ ] 설계 승인(bounded) - [ ] 구현·검증 - [ ] QA

### [CHAT-038] 독립 단어로 쓰인 짧은 종목명이 종목 질의로 잡힌다
- 카테고리: 챗봇 | 티어: T2 | 근거: `[CHAT-032]` 코드 리뷰. `[CHAT-032]` 가 종목 질의 문맥을 전체 종목 맵(1,997종목, 두 글자 이하 147개)에 연결하고 두 글자 이하 이름은 단어 경계에서만 잡도록 했다. 그래도 「VCP 분석 대상 종목 알려줘」→대상, 「전방 산업」→전방, 「러셀 지수」→러셀, 「요즘 한창 뜨는 섹터」→한창, 심층 리뷰의 「남성 소비」→남성·「동양 철학」→동양·「목표가 TP 얼마」→TP·「DB 오류」→DB처럼 종목명이 일반 단어로 쓰이면 그 종목의 `[종목 조회 컨텍스트]` 가 프롬프트에 붙는다. LLM 호출 수·저장·권한은 바뀌지 않지만 답변이 묻지 않은 종목의 수치를 끌어올 수 있다.
- 함께(심층 리뷰 낮음): 6자리 숫자 경계가 `(?<!\d)\d{6}(?!\d)` 로 바뀌어 「150000원」처럼 조사·단위가 붙은 6자리 숫자도 그 값이 티커면 잡힌다. 가격을 적은 질문이 드문 티커와 겹치는지 함께 본다. 티커 갈래가 이름 갈래보다 먼저 돌아서, 「삼성전자 298000원 가면 팔까?」처럼 종목명이 있어도 가격이 티커와 같으면 다른 종목의 문맥이 실린다(천 원 단위 10만~99만9천 원 가운데 9개 값이 티커와 겹침, 만 원 단위는 0개). 또 두 글자 이하 이름 뒤에는 조사 한 글자만 허용해 「기아랑 비교」·「기아에서 신차」는 잡히지 않는다(문맥이 빠지는 안전한 쪽).
- 범위: 일반 단어와 겹치는 짧은 종목명의 처리 방향 결정(흔한 단어 제외 목록, 「종목·주가·어때」 같은 종목 질의 신호와 함께 나올 때만 매칭, 또는 티커·긴 이름만 허용) 과 회귀 테스트.
- QA: 격리 /chatbot 에서 「VCP 분석 대상 종목 알려줘」를 보내고 조립된 프롬프트에 `[종목 조회 컨텍스트]` 가 없음을 확인한다. 「대상 주가 어때?」는 여전히 대상의 문맥을 싣는다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [INFRA-081] 활동 로그 밖의 로그 세 개가 0644 로 남는다
- 카테고리: 인프라 | 티어: T2 | 근거: `[FE-046]` 계획 검토 R4. `[FE-046]` 은 활동 로그·SQLite DB·챗봇 JSON 만 0600 으로 좁혔다. `logs/backend.log`·`logs/frontend.log`(`restart_all.sh:113` 의 셸 리다이렉트, gunicorn 의 요청 로그와 예외 메시지), `logs/critical_errors.log`(`app/__init__.py:276`, 예외 메시지), gunicorn access 로그(IP)는 여전히 0644 로 만들어진다. 그래서 개인정보처리방침 10항은 권한 제한 범위를 「활동 로그와 데이터베이스 파일」로 좁혀 적었다.
- 범위: 세 로그가 어떤 개인정보를 담는지 실측하고, 담는다면 생성 지점(셸 `umask`, `open` 의 모드)에서 0600 으로 만드는 방안과 회귀 테스트. 방침 10항 문안을 넓힐지 함께 정한다.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` → `/code-review` - [ ] QA

### [INFRA-082] 캐시가 아닌 `data/` 절대 경로 여섯 곳이 격리 실행에서도 원본을 가리킨다
- 카테고리: 인프라 | 티어: T2 이상(종가베팅 실행·업데이트 파이프라인 경로를 건드리므로 설계 때 재판정) | 근거: `[INFRA-078]` 조사(2026-09-23). 데이터 파일은 cwd 기준 `data/` 를 읽지만 다음 여섯 곳은 모듈 위치 기준 절대 경로다. `app/routes/common.py:44`(`update_status.json`, `common_update_routes.py:119` 가 그 디렉터리를 스케줄러 상태 파일 위치로도 씀), `app/routes/kr_market.py:191`(`vcp_status.json`), `services/common_update_pipeline_steps.py:30`, `services/kr_market_jongga_runtime_service.py:40`, `services/common_update_ai_analysis_service.py:176`(인자가 없을 때), `services/usage_tracker.py:39`·`engine/services/usage_tracker.py:16`. `services/kr_market_realtime_price_cache.py:125` 의 대체 경로도 같은 방식이다. `scripts/init_data.py` 도 `BASE_DIR/data` 를 쓴다(61행 `BASE_DIR`). 그 가운데 `send_jongga_notification`(1701행)은 `jongga_v2_latest.json` 을 이 절대 경로로 읽는데, `[JONGGA-040]` 이 같은 파일을 절대 경로로 다시 쓰던 코드를 지웠으므로 cwd 가 루트가 아닌 실행에서는 옛 파일을 읽을 수 있다(계획 검토 R1, 2026-09-23). 같은 함수를 부르는 CLI 두 곳(`scripts/run_full_update.py:36`, `scripts/verify_collection_logic.py:31`)을 루트가 아닌 곳에서 실행하면 최신 파일이 `<cwd>/data` 에만 생긴다(`[JONGGA-040]` 코드 리뷰). `[INFRA-078]` 은 사용자 결정으로 캐시 다섯 곳만 고쳤다.
- 범위: 각 경로가 캐시·상태·파이프라인 출력 가운데 무엇인지 분류하고, cwd 기준으로 옮겨도 운영(`restart_all.sh` 가 루트로 `cd`)과 스케줄러·CLI(`run.py`, `scripts/`) 동작이 같은지 확인한 뒤 통일할지 정한다.
- [ ] 설계 승인 - [ ] 구현·RED→GREEN - [ ] 리뷰 - [ ] QA

### [INFRA-083] 전체 pytest 가 원본 `data/runtime_cache.db` 에 캐시 행을 쓴다
- 카테고리: 인프라 | 티어: T1 | 근거: `[INFRA-078]` 정적 검증(2026-09-23). 저장소 루트에서 `pytest -q` 를 돌리면 원본 `data/runtime_cache.db` 의 수정 시각이 바뀐다. 테스트마다 수정 시각을 비교하는 임시 플러그인으로 11개 파일의 34개 테스트를 찾았다(`tests/services/test_kr_market_realtime_service.py` 6, `tests/services/test_kr_market_analytics_service_refactor.py` 5, `tests/app/test_common_data_status_service.py` 5, `tests/services/test_file_row_count_cache.py` 4, `tests/services/test_common_update_status_service.py` 4, `tests/services/test_kr_market_backtest_summary_cache.py` 3, `tests/services/test_kr_market_cumulative_cache.py` 2, `tests/app/test_kr_market_file_cache.py` 2, `tests/test_chatbot_feature.py`·`tests/app/test_kr_market_data_ai_routes_refactor.py`·`tests/app/test_common_routes_refactor.py` 각 1). 캐시 경로를 monkeypatch 하지 않고 cwd 가 저장소 루트라서다. `[INFRA-078]` 전에는 절대 경로로 같은 파일에 썼으므로 새로 생긴 문제는 아니다. `closing-bet-python` 스킬의 「원본 `data/` 를 쓰는 테스트를 만들지 않는다」와 어긋나고, `[FE-046]` 의 0600 권한 변경처럼 테스트가 원본 파일 상태를 바꾸는 통로가 된다.
- 추가 관찰(`[VCP-027]` 정적 검증, 2026-09-23 11:55): 원본 작업 트리의 전체 pytest 한 번이 `runtime_cache.db` 말고도 `data/vcp_status.json`·`v2_screener_status.json`·`scheduler_runtime_status.json`(모두 대기 상태 값으로 다시 씀), `paper_trading.db-wal`·`-shm`, `data/.krx_collector_cache/`·`.market_schedule_cache/` 아래 캐시 DB, `logs/user_activity.log`(테스트 클라이언트 요청 기록 추가)를 바꿨다. 범위를 `data/` 전체와 `logs/` 로 넓혀 판단한다.
- 범위: `tests/conftest.py` 에 autouse 로 cwd 를 `tmp_path` 로 옮기거나 캐시 경로 상수를 `tmp_path` 로 돌리는 방안 가운데 하나를 고르고, 전체 실행 전후 원본 `data/` 수정 시각이 같음을 확인하는 검사.
- [ ] 설계 승인(bounded) - [ ] 구현·RED→GREEN - [ ] `/ponytail-review` - [ ] 정적 검증

### [INFRA-084] `closing-bet-reviewer` 에 일반 Python 보안 검토 항목을 더한다
- 카테고리: 인프라 | 티어: 문서(`tier-rules.md` §5, 설계 때 재판정) | 근거: 2026-09-23 대화에서 `docs/reference/skill-trend/05_python_agent_skills_research_review.md` 의 추천 스킬을 대조했다. Pydantic Skills 는 저장소가 Pydantic 을 직접 쓰지 않아(import 0건, 구조체는 `@dataclass`) 제외했다. ECC(`affaan-m/everything-claude-code`, MIT) 의 `python-testing`·`python-patterns`·`python-reviewer` 전체는 `CLAUDE.md` 의 테스트 규칙(`test_*_refactor.py`, 새 fixture 계층 금지)·`engine/constants` 우선 규칙과 충돌하거나 일반 관용구라 제외했다. 차용할 가치가 있는 것은 `agents/python-reviewer.md` 의 CRITICAL 보안 항목뿐이다. 현재 `closing-bet-reviewer` 는 결측·신원·비용·비밀·문서 계약을 보지만 명령 주입(셸 문자열 `subprocess`), 경로 조작(`..`), 안전하지 않은 역직렬화(`pickle`·`yaml.load`), 잠금 없는 공유 상태(gunicorn 스레드·스케줄러)는 명시하지 않는다. 빈 `except` 는 `closing-bet-python` 이 이미 금지한다.
- 범위: `.claude/agents/closing-bet-reviewer.md` 와 `.codex/agents/closing-bet-reviewer.toml` 의 검토 기준에 위 네 항목을 이 저장소의 사례와 함께 더하고 출처(ECC, MIT)를 적는다. ECC 를 설치하거나 다른 파일을 가져오지 않는다. `tests/scripts/test_skill_set.py` 의 대조가 계속 통과하는지 확인한다.
- [ ] 설계 승인(bounded) - [ ] 문서 수정 - [ ] §5 검토 - [ ] `test_skill_set.py`
