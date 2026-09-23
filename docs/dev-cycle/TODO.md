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

## P1 — 이번 주기

## P2 — 대기

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T3(등록 때 T1, 설계 때 위험 경로 「저장소 스키마」로 재판정) | 근거: `[FE-045]` 계획 검토(2026-09-22). `services/usage_tracker.py`(`usage_log`)와 `engine/services/usage_tracker.py`(`api_usage`)는 이메일을 기본 키로 쓰지만 어떤 운영 코드도 import 하지 않는 유물이다. 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한다. 행이 있으면 그 이메일 행을 지우는 절차(또는 파일 제거)와 두 모듈·테스트의 삭제를 설계한다. 행이 없으면 두 모듈과 테스트의 삭제만 남는다(등록 때 적은 「테스트 여섯 파일」은 설계 전 추정이며, 실제로는 전용 테스트 둘 삭제와 한 파일 수정이다). 원격 서버 접속은 운영자가 한다.
- 설계 승인: 2026-09-24 00:36 사용자 「진행해」(bounded 설계를 대화에서 제시). 범위를 코드 삭제로 나눈다(사용자 「코드 삭제만 먼저 진행해」). 운영 서버 행 확인과 `data/usage.db` 파일 정리는 운영자 몫으로 이 항목에 남는다.
- 티어: T3. 두 모듈이 `tier-rules.md` §2 「저장소 스키마」의 `CREATE TABLE` 모듈이라 삭제도 위험 경로다.
- 코드 삭제 범위: `services/usage_tracker.py`·`engine/services/usage_tracker.py` 와 전용 테스트 둘 삭제, `tests/app/test_kr_market_route_integration.py` 의 폐기 라우트 테스트를 실제 사용량 저장소(`user_quota.json`) 확인으로 교체, `README.md` 트리 한 줄, `tier-rules.md` 목록 두 줄과 개수(스물한 → 열아홉). 과거 증거·아카이브와 `data/usage.db` 는 건드리지 않는다.
- QA 초안: 격리 사본(`data/` 에 `usage.db` 없음)에서 gunicorn 기동, 대시보드 API 200, 폐기 라우트 `POST /api/kr/reanalyze/gemini` 410, 사본 `data/usage.db` 미생성.
- [x] ponytail 리뷰(oh-my-claudecode:code-reviewer 레인): diff 안에서는 지울 것 없음(-880/+11). 잔존 참조 `docs/vibe/ARCHITECTURE.md` 두 줄(트리 항목, 「사용량 추적」)을 지적 → 삭제 반영(트리 기호 정리). 테스트의 `execute_user_gemini_reanalysis_request`·`run_user_gemini_reanalysis` 가짜 키를 죽은 의존성으로 본 관찰은 미반영: 폐기 라우트가 옛 의존성을 부르지 않음을 검사하는 가드(`test_retired_gemini_does_not_call_former_dependency` 등)에 쓰인다. `evidence/infra-boundaries-20260920/fixture_probe.py` 는 `tests/` 밖이라 수집되지 않는 과거 증거로 보존.
- [x] 코드 삭제·정적 검증: `git grep` 잔존 참조는 `tests/app/test_kr_market_system_http_routes_refactor.py:53` 의 람다 인자 이름 하나(모듈 참조 아님). 전체 `venv/bin/python -m pytest -q -p no:cacheprovider` exit 0, 2707 passed 2 skipped(직전 2728 에서 삭제한 전용 테스트 21건 감소). 원본 `data/usage.db` 무변경.
- [x] 코드 리뷰(closing-bet-reviewer) APPROVE, max low. L-1(머리 줄 티어 T1·「테스트 여섯 파일」 불일치) → 정정, L-2(람다 인자 이름) → 범위 밖·가드 테스트가 쓰는 키라 미반영, L-3(운영 파일은 삭제 경로·권한 좁히기가 닿지 않음) → 운영자 단계에 chmod 600 과 파일 제거 추가. 리뷰어가 뮤테이션 대조로 교체 테스트가 쿼터 소비 퇴행을 잡음을 확인.
- [x] 심층 리뷰(oh-my-claudecode:critic, review 절차) ACCEPT-WITH-RESERVATIONS: 코드 결함 없음. 유보는 모두 QA 계획. medium 1(S-2 의 쿼터 해시 검사는 서명 신원 없이 실패할 수 없음) → S-2 기대를 410·코드로 낮추고 쿼터 불소비는 단위 테스트가 보장한다고 명시, low 2(원본 `data/` 전후 대조 없음) → `ls`·`stat` 대조와 `cp -c -R`·inode 확인 추가, low 3(원본 `data/` 복제로 개인정보 확산) → 사본 `data/` 를 비워 두고 정리 절차 명시, low 4(커밋 전 사본이면 무의미) → S-1 앞에 사본의 모듈 부재 확인, info 5(`engine/services/__pycache__` 의 고아 pyc) → 두 곳의 `usage_tracker` pyc 와 빈 `engine/services/` 디렉터리 삭제(추적 대상 아님).
- [x] 설계 승인(bounded) - [x] 심층 리뷰(critic) - [ ] QA - [ ] 운영 서버 행 수 확인과 파일 정리(운영자). 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로, 행을 확인한 뒤 파일을 제거하고 제거 전까지는 `chmod 600 data/usage.db` 로 둔다

### [INFRA-084] `closing-bet-reviewer` 에 일반 Python 보안 검토 항목을 더한다
- 카테고리: 인프라 | 티어: 문서(`tier-rules.md` §5, 설계 때 재판정) | 근거: 2026-09-23 대화에서 `docs/reference/skill-trend/05_python_agent_skills_research_review.md` 의 추천 스킬을 대조했다. Pydantic Skills 는 저장소가 Pydantic 을 직접 쓰지 않아(import 0건, 구조체는 `@dataclass`) 제외했다. ECC(`affaan-m/everything-claude-code`, MIT) 의 `python-testing`·`python-patterns`·`python-reviewer` 전체는 `CLAUDE.md` 의 테스트 규칙(`test_*_refactor.py`, 새 fixture 계층 금지)·`engine/constants` 우선 규칙과 충돌하거나 일반 관용구라 제외했다. 차용할 가치가 있는 것은 `agents/python-reviewer.md` 의 CRITICAL 보안 항목뿐이다. 현재 `closing-bet-reviewer` 는 결측·신원·비용·비밀·문서 계약을 보지만 명령 주입(셸 문자열 `subprocess`), 경로 조작(`..`), 안전하지 않은 역직렬화(`pickle`·`yaml.load`), 잠금 없는 공유 상태(gunicorn 스레드·스케줄러)는 명시하지 않는다. 빈 `except` 는 `closing-bet-python` 이 이미 금지한다.
- 범위: `.claude/agents/closing-bet-reviewer.md` 와 `.codex/agents/closing-bet-reviewer.toml` 의 검토 기준에 위 네 항목을 이 저장소의 사례와 함께 더하고 출처(ECC, MIT)를 적는다. ECC 를 설치하거나 다른 파일을 가져오지 않는다. `tests/scripts/test_skill_set.py` 의 대조가 계속 통과하는지 확인한다.
- [ ] 설계 승인(bounded) - [ ] 문서 수정 - [ ] §5 검토 - [ ] `test_skill_set.py`
