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


### [INFRA-076] 운영 유닛의 환경 주입과 프로덕션 서빙 방식 정리
- 카테고리: 인프라 | 티어: T2 | 근거: `[INFRA-075]` 에서 이월. 상세는 `deploy/systemd/README.md` 의 「남아 있는 판단 사항」
- 선행 조건: 운영 서버에서 systemd 를 실제로 돌려 확인할 수 있을 때 착수한다. 로컬에서는 검증할 수 없다. 2026-09-22 에 운영자가 유닛을 내리고 `restart_all.sh` 로 운영하기로 했으므로, 아래 U6 은 그대로 유효하고(`restart_all.sh` 도 `run-next.js dev` 로 띄운다) 나머지 세 항목은 유닛을 다시 쓸 때만 해당한다.
- [ ] U6: 프로덕션이 Next dev 서버로 서빙 중이다. `npm run build` 를 배포 절차에 넣고 `npm run start` 로 바꾼다. 빌드 실패 시의 처리를 함께 정한다.
- [ ] 두 유닛이 `set -a; . ./.env` 로 `.env` 를 셸로 읽는다. 실제로 쓰는 값은 `FLASK_PORT` 와 `FRONTEND_PORT` 하나씩뿐이고, Flask 는 `load_dotenv()`, Next 는 `@next/env` 로 각자 읽으므로 나머지는 중복이다(`scripts/env_value.sh` 주석). `EnvironmentFile=` 은 인라인 주석을 떼지 않아 대안이 아니다. `scripts/env_value.sh` 를 쓰거나 포트만 주입한다. `/bin/bash -lc` 도 함께 걷어낸다. 그 로그인 셸 때문에 frontend 유닛의 `Environment=PATH=` 는 `/etc/profile` 에 덮여 듣지 않을 가능성이 크다(리뷰 N6, `systemd-run --user --wait --pipe -p 'Environment=PATH=/tmp' /bin/bash -lc 'echo $PATH'` 로 확인).
- [ ] frontend 유닛의 `/home/ms/n/bin/npm` 절대 경로를 `%h/n/bin/npm` 으로 바꾼다.
- [ ] 두 유닛의 `After=`·`Wants=network-online.target` 이 사용자 매니저에 없는 유닛을 가리킨다. 지우거나 사용자 매니저에서 쓸 수 있는 대상으로 바꾼다.


## P1 — 이번 주기

## P2 — 대기
