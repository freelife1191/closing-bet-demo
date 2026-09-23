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
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)

### [INFRA-084] `closing-bet-reviewer` 에 일반 Python 보안 검토 항목을 더한다
- 카테고리: 인프라 | 티어: 문서(`tier-rules.md` §5, 설계 때 재판정) | 근거: 2026-09-23 대화에서 `docs/reference/skill-trend/05_python_agent_skills_research_review.md` 의 추천 스킬을 대조했다. Pydantic Skills 는 저장소가 Pydantic 을 직접 쓰지 않아(import 0건, 구조체는 `@dataclass`) 제외했다. ECC(`affaan-m/everything-claude-code`, MIT) 의 `python-testing`·`python-patterns`·`python-reviewer` 전체는 `CLAUDE.md` 의 테스트 규칙(`test_*_refactor.py`, 새 fixture 계층 금지)·`engine/constants` 우선 규칙과 충돌하거나 일반 관용구라 제외했다. 차용할 가치가 있는 것은 `agents/python-reviewer.md` 의 CRITICAL 보안 항목뿐이다. 현재 `closing-bet-reviewer` 는 결측·신원·비용·비밀·문서 계약을 보지만 명령 주입(셸 문자열 `subprocess`), 경로 조작(`..`), 안전하지 않은 역직렬화(`pickle`·`yaml.load`), 잠금 없는 공유 상태(gunicorn 스레드·스케줄러)는 명시하지 않는다. 빈 `except` 는 `closing-bet-python` 이 이미 금지한다.
- 범위: `.claude/agents/closing-bet-reviewer.md` 와 `.codex/agents/closing-bet-reviewer.toml` 의 검토 기준에 위 네 항목을 이 저장소의 사례와 함께 더하고 출처(ECC, MIT)를 적는다. ECC 를 설치하거나 다른 파일을 가져오지 않는다. `tests/scripts/test_skill_set.py` 의 대조가 계속 통과하는지 확인한다.
- [ ] 설계 승인(bounded) - [ ] 문서 수정 - [ ] §5 검토 - [ ] `test_skill_set.py`
