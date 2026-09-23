# UltraQA Report

engine=ultraqa, lifecycle=app-adapted, phase=complete, iteration=3, screenshot_failure_count=3(iteration 2). 재시도(iteration 3, 2026-09-23)에서 B1·C1 통과, 아래 「재시도」 절.
기준 구현: `6569c60`. 최종 코드 SHA: `evidence/INFRA-074/frozen.json`.

## 목표와 범위

재시작/중지의 거짓 성공과 중복 기동을 막고, 정상 의존성 출력을 축약하며 KRX 로그인 비정상 응답을 안전하게 처리한다. 원격 Linux에는 접속하지 않았다. 실제 서버관리자/네트워크 차단 원인을 확정하거나 원격 복구 완료로 보고하지 않는다.
실제 비용·AI·발송·거래·사용자 설정 저장은 실행하지 않는다. 격리 서비스는58120/58121, 원본3500/5501은 보존한다.

## 필수 시나리오와 결과

| ID | 의도/모델 | setup·실행 | 기대 | 실제·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| L1 | 정상 운영자/구버전 | scratch 실제 Gunicorn/Next 시작→중지→재시작, 기록 없는 legacy 중지 | 실제 프로세스·포트·응답 확인 후 성공 | 시작/중지0, stop2.6초/restart6.9초; legacy 인수·중지 및 cleanup도exit0 | own 서비스 종료 확인 | 예 |
| L2 | 다른 사용자·PID 재사용·관리자 재점유 | ss/ps 대역 및 자체 tmp 자식 | 무관 프로세스 보존, 비정상 종료 | 동적17개 PASS: 다중/숨은PID, 재점유, 잘못된 명령, PID 재사용 | tmp 자식 종료 | 예 |
| L3 | 정체·중복·부분 실패 | 실제 flock 경쟁, fake child, 실제 app 부팅 | 잠금 회수, 자체 자식만 정리, 거짓Ready 없음 | 동적17개 PASS, 최종 dual readiness·PID 기록 실패·Done job·뒤늦은 backend 사망 | tmp 자식 종료 | 예 |
| D1 | 정상 의존성·공백 경로 | 실제 fresh 설치/같은 환경 반복 | 잡음 제거, npm ci 생략 | 최초9.6초/반복1.3초, 실제 재시작에서도 변경 없음 | scratch 삭제 완료 | 예 |
| D2 | 설치 불량·실패 | lock 변경/실행 파일 누락, pip/npm 실패 | 필요한 갱신과 오류 원문, 기동 차단 | 관련 회귀 PASS, 설치 실패 시 down 상태 명시 | tmp fixture | 예 |
| K1 | HTML/HTTP/schema/network/redirect | 실제 cookie.2의 합성 transport 및 Gunicorn import 강제 | 예외/자격정보 누출 없이 인증 실패 | 로그인14 시나리오 PASS; 앱 주입 증거 app-krx-fault.json | 외부 접속0/실제 자격정보 없음 | 예 |
| K2 | 정상·CD011·갱신 실패 | 실제 requests와 합성 세션/응답 | 정상 로그인 유지, 실패 쿠키 제거 | 로그인14 + 기존 transport7그룹 PASS, wheel 재빌드2회 SHA일치 | 구현자 tmp 삭제 | 예 |
| B1 | 앱 사용자 | ego-browser space1, /dashboard/kr | 화면·JSON·오류 및 screenshot 확인 | DOM 정상/JSON200, Next MCP오류0. 캡처2회timeout+대체CDP실패: **BLOCKED** | space1 finish 완료 | 예 · 재시도 통과 |
| C1 | 원본/다른 작업 보존 | 해시·소유권 대조 | 원본 전체불변 | 하위 검수의 원본 전체pytest 실행으로 **미통과**. 아래 사건 기록 | 원본을 임의 rollback하지 않음 | 예 · 재시도 통과 |

## 실행 근거

- 최종 snapshot fresh venv 전체 pytest: **2527 passed,2 skipped**,81.19초,exit0. macOS sandbox가 ps 실행을 막아 lifecycle adversarial 파일만 별도 실행.
- 같은 snapshot의 동적 lifecycle adversarial: **17 passed**,5.30초,exit0. 실제 원본 환경이 아닌 scratch cwd와 합성 env, 자체 tmp 자식만 사용. 합계 Python2544통과.
- 관련 스크립트·Next launcher 회귀:81통과. 프론트엔드 Vitest641/84파일 통과.
- bash 문법·git diff check 통과. 원본 비추적package.json 보존.
- 실제 서비스 시작/중지/재시작 exit0. KRX HTML을 주입한 실제 import/기동 결과는 app-krx-fault.json에 별도로 기록한다. 최초 UI 방문에서는 pykrx가 lazy import여서 로그인 분기를 실행하지 않았음을 구분한다.
- code APPROVE, architect CLEAR, deep ACCEPT, security APPROVE. 과잉설계2건 반영. 초기 리뷰 해시는 이력으로 보존하며 final frozen.json/deep 리뷰가 최종 기준이다.
- UI는 일반 대시보드의 실제 DOM을 관찰했다. 스크린샷 파일이 없으므로 시각 검증 성공으로 세지 않는다. raw CDP 쿠키/헤더는 보존하지 않고 event method만 남겼다.

## 실패→수정

1. 기존 KRX 비JSON 예외 RED→로그인 guard GREEN. 보안 검토에서 로그인307 재전송을 재현해 모든 로그인 요청의 redirect 차단 및 명시적2xx검사 추가.
2. 이전 bootstrap fixture가 신규helper를 복사하지 않던 실패 수정. 기존 symlink 권한보존 기대값 유지.
3. OS sandbox의 ps 차단은 제품 결함과 분리하고 해당 격리 프로세스 회귀만 clean-env scratch에서 실행.
4. 실제 app smoke에서 Next의 ps 출력 공백으로 오인→문자열 정규화 회귀 추가. Bash pipeline에서 job table이 사라져 정리 시wait가 걸림→command substitution으로 고치고 실제 자식 회귀 통과.
5. PID 파일 기록 실패, 포트가 먼저 닫히는 종료, 의존성 설치 중 재점유, 먼저 준비된 backend의 사망 모두 검증에 포함.

## 검수 경계 위반

하위 agent `/root/lifecycle_adversarial`이 지정 범위를 벗어나 원본 cwd에서 상속 환경으로 `venv/bin/python -m pytest -q`를 한 번 실행했다. 종료(exit1) 뒤 추가 원본 테스트를 금지했다. 기존cookie.1이 계정 ID를 도구stdout에 출력했으며 그 값은 문서/증거에 복사하지 않았다. 이 전체 실행은 검증 증거에서 제외했다.

원본.env 계열·root package.json·종가/VCP 결과 파일은 초기 해시와 같다. Market Gate를 포함한 runtime/cache/status8개 변경, WAL/SHM 변동은 preservation-check.json에 기록했다. 원본 서비스도 자동 갱신 중이므로 모든 변화가 그 테스트 하나 때문이라고 단정하지 않는다. baseline은 해시만 보유하므로 이전 캐시 내용을 정확히 복구할 수 없다. 사용자 파일이나 정상 갱신을 임의로 되돌리지 않는다.

이 사건을 새 baseline으로 덮거나 원본 전체불변 PASS로 바꾸지 않는다. 코드의 기능 검증과 별개로 C1은 미통과다.

## 남은 한계와 판정

원격 서버 미적용. 외부 systemd/Supervisor를 추측해서 중지하지 않으며 진단 후 관리자의 절차로 정리해야 한다. launcher 강제 종료로 분리된 자식은 안전한 소유권 증명이 없으면 종료하지 않고 PID 기록·실패를 남긴다. 정상 설치 hook의 daemon화는 지원하지 않는다.

**ULTRAQA BLOCKED: B1 screenshot unavailable after3 attempts; C1 original-environment preservation violated.**
기능 수정은 구현·검증했지만 전체 검수 완료/완료 아카이브를 만들지 않고 TODO를 유지한다.

정리 완료(2026-09-22): own launchers 종료 및58120/58121해제, scratch삭제, browser space1 finish1회. 민감설정/root package 해시 및 frozen15파일 일치. 원본3500/5501은 기존 master77981/Next78031로 실행 중이다. 마지막 실행은 KRX실패 import를 강제로 검증했고 QA_KRX_IMPORT_OK/invalid_json을 확인했으며 JSONDecodeError/worker bootfailure는 없었다.

## 재시도 (iteration 3, 2026-09-23)

- 대상: `git archive 727b2e0` 사본(scratchpad `infra074/app`)에 원본 `data/` 와 `frontend/node_modules` 를 APFS clone 으로 두고 `.env` 는 두지 않았다. 사본 venv 는 `restart_all.sh` 가 새로 만들었다. 포트 58120(Next dev)·58121(Gunicorn), `SCHEDULER_ENABLED=false`, 더미 비밀(`closing-bet-verify` 의 값)만 `env -i` 로 넘겼다
- 검증 기준 커밋: `727b2e0`. iteration 2 의 frozen 이후 범위 파일(`restart_all.sh`, `stop_all.sh`, `scripts/service_lifecycle.sh`, `scripts/sync_dependencies.sh`)은 `[INFRA-075]`·`[INFRA-076]`·`[INFRA-077]` 등에서 바뀌었으므로 현재 HEAD 로 실행했다
- QA 엔진: Claude Code, gstack `browse`(`~/.claude/skills/gstack/browse/dist/browse`). 원본 3500/5501 은 실행 전후 모두 리스너 0 이었고 쓰지 않았다
- 금지 조작: 설정 저장·갱신·재분석·챗봇 전송·모의 매수·삭제 계열. 화면을 열고 읽기만 했다
- 실행 21:17(기준 기록)~21:21(정리)
- 읽은 정본: `.claude/skills/closing-bet-verify/SKILL.md`, `.claude/skills/dev-cycle/references/browser-notes.md`

### B1 재시도: 격리 기동 뒤 대시보드 화면 (필수)
- 조작: 사본에서 `./restart_all.sh` → `browse console --clear` → `goto http://localhost:58120/dashboard/kr` → `wait --networkidle` → `screenshot`
- 기대: 기동 exit 0 과 `🎉 Ready!`, 화면의 Market Gate 점수가 `GET /api/kr/market-gate` 의 `score`·`label` 과 같음, `/api/` 요청 5xx 0, 콘솔 오류 0, `get_errors`·`get_compilation_issues` 비어 있음, 스크린샷 파일이 열림
- 실제: 기동 exit 0, 48초(새 venv 생성 포함). 스크린샷(`evidence/INFRA-074/retry-20260923/b1-dashboard.png`)을 열어 확인: KR Market Gate 55 Neutral, KOSPI 200 섹터 11칸, 지수·원자재·암호화폐 카드 값 표시. API `score=55 label=Neutral`, Next 경유 200. 브라우저 `/api/` 요청 13건 전부 200(`market-gate`·`signals`·`status`·`backtest-summary`·`config/interval`·`auth/session`·`user/quota`). 콘솔 오류 없음, `configErrors`·`sessionErrors`·`issues` 모두 빈 배열
- 결과: 통과

### L1 보강: 떠 있는 상태의 재시작과 중지 (보강)
- 조작: 서비스가 떠 있는 채로 `./restart_all.sh`, 이어서 `./stop_all.sh`
- 기대: 재시작이 기존 PID 둘을 정상 종료한 뒤 새로 기동, 중지 뒤 58120/58121 리스너·`logs/*.pid`·사본 경로 프로세스 0
- 실제: 재시작 exit 0 9초(frontend 17189·backend 16159 정상 종료 → 21427·21550 기동, `/` 200), 중지 exit 0 3초, 리스너 0, PID 파일 0, `pgrep -f` 0
- 결과: 통과

### 사본 회귀 (보강)
- 사본 venv 로 `pytest -q -p no:cacheprovider tests/scripts tests/test_pykrx_login_guard.py`: 159 passed, 1 skipped, 1 failed. 실패는 `test_gitignore_hides_macos_appledouble_and_ds_store_files` 이며 `git archive` 사본에 `.git` 이 없어 `git check-ignore` 가 128 을 낸 환경 차이다. 같은 테스트는 원본 트리의 직전 전체 실행(2720 passed, CHAT-041)에서 통과했다

### C1 재시도: 원본 불변 (필수)
- 조작: 실행 전 원본의 민감 파일 9개(`.env` 계열 8개, 루트 `package.json`)와 `data/`·`logs/` 의 모든 파일을 `shasum -a 256` 으로 기록하고 시각 표지를 남김 → QA → 같은 목록을 다시 해시해 `diff`, 표지보다 새로운 파일을 `find -newer` 로 셈(`.omc`·`.git` 제외 후 `.git` 은 따로 확인)
- 기대: 해시 차이 0줄, 새 파일은 QA 도구 자신의 무시된 로그뿐, `git status --short` 0줄. 하위 에이전트를 쓰지 않고 원본 트리에서 pytest·서버를 실행하지 않는다
- 실제: 27,572개 파일 해시 차이 0줄. 표지 이후 수정은 `.gstack/` 의 browse 상태 파일 다섯(`browse-console.log`·`browse-network.log`·`browse-daemon.log`·`browse-audit.jsonl`·`.gitignore`, 디렉터리는 05-22 부터 존재, `.gitignore:104` 로 무시)과 `.git` 디렉터리 자체의 mtime(내부 항목 변경 없음)뿐. `git status --short` 0줄. 원본 3500/5501 리스너 0
- 결과: 통과. iteration 2 의 위반 사건 기록은 그대로 두며, 이 판정은 새 실행의 결과다

### 정리
- `browse stop`, 사본 `infra074/app`·`tmp` 삭제, 사본 경로 프로세스 0, 58120/58121 리스너 0. 증거는 `docs/dev-cycle/evidence/INFRA-074/retry-20260923/`(스크린샷, 기동·재시작·중지 로그, 보존 검사 결과). 로그에 비밀 문자열 0건(grep 확인)

**재시도 판정: 필수 9/9 통과(L1~K2 는 iteration 2, B1·C1 은 iteration 3).**
