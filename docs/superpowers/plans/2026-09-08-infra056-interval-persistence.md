# INFRA-056 Interval Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Native children perform bounded tests/reviews; leader owns integration and QA.

**Goal:** 관리자 주기 변경을 공통 루트 .env에 안전하게 저장하고 다음 기동에서도 유지한다.
**Architecture:** 공통 resolve_env_path, _env_file_lock, _read_env_lines, 기존 atomic_write_text를 재사용한다. 잠금은 한 번만 잡고 읽기·교체·성공 후 런타임 적용까지 덮는다. HTTP 검증은 단일 설정 콜백으로 위임한다.
**Tech Stack:** 기존 Python/Flask, pytest, Next/vitest, agent-browser. 새 의존성 없음.
**Spec:** 현재 대화 INFRA-056 bounded/T3 설계 제안에 사용자가 「진행해」로 승인. 경로·잠금·링크 보호·저장 후 적용·테스트/설명·격리 재시작/UI 검증·리뷰/커밋.

## Global Constraints

- T3. 독립 develop clone 사용. 원본 /Users/freelife/vibe/lecture/hodu/closing-bet-demo/package.json (사용자 소유 untracked, clone에 없음) SHA 4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8 보존.
- 원본 .env/.env.production/.env.vertex/data 읽기·변경 금지. 원본3500/5501/close.highvalue.kr 접근 금지.
- 실제 LLM·수집·발송·거래·삭제·설정저장·운영재시작/배포 금지. 테스트는 임시 가짜 파일/계정과 소유 서버만.
- 공통 잠금 재진입 금지, update_env_file을 잠금 안에서 호출하지 않는다.
- 기존 스케줄러 소유 워커 정책은 유지한다. 다른 워커 메모리에 즉시 전파하는 설계는 범위 밖이다.
- 파일 없음은 공통 _read_env_lines([])와 atomic writer로 주기 키만 가진0600 파일 생성. 읽기/교체 실패는 성공 처리·runtime 적용 없이 오류 반환.
- env 키 기존표기(공백/export/따옴표/중복/잘못된 값)는 대상 키를 정규화하고 다른 키/주석은 보존한다. 유효 요청1..1440, 기존 int변환 계약 유지.
- 외부네트워크 차단, Python 전체검증480초/브라우저검증명령120초. 리뷰 각10분. QA 최대5회/동일실패3회.

## Task 1: 경로·저장·적용 경계

Files: services/common_env_service.py(_read_env_lines의 newline=""만), services/kr_market_interval_service.py, services/kr_market_interval_http_service.py, app/routes/kr_market.py;
tests/services/test_kr_market_interval_persistence.py(신규), tests/services/test_kr_market_interval_http_service.py, tests/app/test_kr_market_route_integration.py.

Interfaces: persist_market_gate_interval_to_env(*, interval:int, env_path:str, atomic_write_text:Callable, apply_interval_fn:Callable[[int],None])->None.
HTTP handle_interval_config_request의 apply_interval_fn/persist_interval_fn 인자를 set_interval_fn:Callable[[int],None]으로 통합한다. GET은 콜백 미호출. route의 기존 _persist helper가 실제 저장+적용을 연결한다.

- [ ] RED: tmp_path의 가짜 .env 저장 시 주기15로 바뀌고 다른키 보존/모드0600, 중복키1개, missing 파일생성, 링크ELOOP, replace실패원본보존/runtime0을 검사한다.
```python
applied=[]
persist_market_gate_interval_to_env(interval=15,env_path=str(env),atomic_write_text=atomic_write_text,apply_interval_fn=applied.append)
assert dotenv_values(env)['MARKET_GATE_UPDATE_INTERVAL_MINUTES']=='15'
assert applied==[15]
```
- [ ] 기존 경로 별칭은 common_env_service.resolve_env_path를 사용한다. project_env_path(base_file) 및 import를 삭제한다.
```python
_project_env_path = resolve_env_path
```
- [ ] 저장 함수에 공통 단일 잠금, _read_env_lines 링크보호, 대상키 정규화, atomic_write_text 적용. 교체 성공 뒤 같은잠금 안에서 apply_interval_fn(interval).
```python
with _env_file_lock(env_path):
    lines = _read_env_lines(env_path)
    parts = []
    found = False
    for binding in parse_stream(StringIO("".join(lines))):
        if binding.error:
            raise ValueError("Invalid environment file syntax")
        if binding.key == "MARKET_GATE_UPDATE_INTERVAL_MINUTES":
            if not found:
                parts.append(f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}\n")
                found = True
        else:
            parts.append(binding.original.string)
    if not found:
        if parts and not parts[-1].endswith(("\n", "\r")):
            parts.append("\n")
        parts.append(f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}\n")
    atomic_write_text(env_path, "".join(parts))
    apply_interval_fn(interval)
```
- [ ] HTTP 서비스는 유효값에 set_interval_fn(new_interval) 한 번 호출. route callback 연결과 오래된 .env 미저장 docstring 수정.
- [ ] 동시 .env 일반설정 저장과 주기저장 상호 배타/갱신보존 검사, runtime apply 전 다른 같은프로세스 요청이 진행하지 않는지 events+bounded joins로 검증한다. 두 경로 resolver 같은 절대경로임을 코드와 테스트로 검증.
- [ ] 관련 pytest RED→GREEN, 전체 pytest/vitest·typecheck/lint. frontend 제품변경은 예정 없음. 생성물·원본 보존 확인.

## Task 2: 리뷰·동적 검증·마감

Files: CLAUDE.md, docs/dev-cycle/TODO.md, docs/dev-cycle/qa/INFRA-056.md, docs/dev-cycle/reviews/INFRA-056.md, docs/dev-cycle/evidence/INFRA-056/, docs/dev-cycle/archive/2026-09.md, docs/dev-cycle/archive/daily/2026-09-08.md.

- [ ] CLAUDE에 주기영속화/재시작반영과 워커정책 경계를 적는다.
- [ ] ponytail → code-reviewer+architect 병렬 → security 전용 code-reviewer → T3 review 심층. 실제입력SHA/원문/미반영사유 기록.
- [ ] 시크릿3검사: 추적 .env 파일목록(.env.example만 허용), 가짜 sentinel 로그/API 비반사, frontend private키 번들 미노출. 새 키 없음. 실제 시크릿 읽지 않는다.
- [ ] 정적PASS+QA행렬 첫커밋. UltraQA App 대응으로 아래행렬 실행:
  - 실제 관리자 /dashboard/kr에서30→15 변경, 실제 Next→Flask POST200, 임시.env 값15, 새 Flask 프로세스의 GET15 및 화면15.
  - 비관리자/권한철회403 및 파일/runtime 불변, UI권한안내/값복원.
  - 빈 파일/없는키/중복키·quoted/export/Unicode 다른값 보존, 입력범위400.
  - 파일/잠금심볼릭링크, 읽기/교체실패: 외부대상·기존파일/runtime 불변, 실패화면복원.
  - multiprocessing 두 writer 경합, 잠금보유프로세스 종료후 복구, timeout/자식종료 확인.
- [ ] agent-browser 실제 snapshot/ref조작/network/status/스크린샷 열기/console·errors. interval API·저장로직 mock 금지; 외부 MarketGate와 scheduler actual work만 대역. 보조UI GET fixtures 명시.
- [ ] 검증 소스SHA일치 확인후 ff 통합, 소유서버/브라우저/clone/가짜.env정리, 최종아카이브커밋에서만 TODO제거.

## 계획 검토 보완 (2026-09-08)

첫 critic REJECT의4개를 같은 승인범위 안에서 반영한다.

1. 설치된 python-dotenv1.2.1 parser API를 사용한다: `from dotenv.parser import parse_stream`, `from io import StringIO`. binding.key 대상만 정규화, 비대상 binding.original.string 유지. binding.error는 generic ValueError로 파일/runtime 변경 전에 거부한다(잘못된 따옴표 등). _read_env_lines의 os.fdopen에 newline=""를 지정해CRLF/LF도 보존하며 비대상멀티라인·CRLF·주석 exact-byte 테스트를 둔다. 대상 malformed numeric값은 정상 binding이면 정규화한다.
2. 보장하는 실패는 읽기/파싱/교체 이전 실패의 파일/runtime 불변이다. 교체 후 callback 실패는 파일이 새 값인 채 예외가전파되고HTTP500이다. 디스크 롤백은 없으며 임의 callback의 메모리 복구를 약속하지 않는다. 실제 scheduler update는 이미 예외를 로깅해 삼키는 best-effort이다. 기존 워커별 적용정책을 유지하고 로그/문서로 한계를 명시한다. callback가 raise하는 별도검사에서 파일새값·예외·잠금해제 후 재시도 성공을 확인한다.
3. UI fixture는 clone루트.env만 사용, 부모/Flask재시작child의 MARKET_GATE_UPDATE_INTERVAL_MINUTES를unset하고 새프로세스가 dotenv에서 다시읽는다. ready는소유port/PID/cwd/HEAD/sourceSHA/API_URL과시작·종료정보를 기록한다. synthetic NEXTAUTH_SECRET/INTERNAL_IDENTITY_SECRET/ADMIN_EMAILS와전용관리자세션을 사용한다. 생성불가면필수UI BLOCKED. 보조GET fixtures는 admin/check(실제권한함수), quota, signals, status, backtest-summary, market-gate, signals/status, signals/dates, ai-analysis, system/data-status/update-status로명시한다. intervalAPI/실제writer는대역금지.
4. QA/리뷰/증거/아카이브 경로를 모두실제 docs/dev-cycle 경로로고쳤다.
