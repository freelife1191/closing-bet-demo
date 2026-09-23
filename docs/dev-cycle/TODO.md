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

### [INFRA-087] 기동 스크립트와 문서에서 systemd 관련 부분을 제거한다
- 카테고리: 인프라 | 티어: T3 예상(삭제 300줄 초과 가능, 위험 경로 아님, 구현 후 `git diff --stat` 으로 확정) | 근거: 2026-09-24 대화. 운영 서버가 2026-09-22 부터 systemd 유닛 없이 `restart_all.sh`·`stop_all.sh` 로만 돌아 `[INFRA-075]` 의 systemd 입양 거부 장치가 불필요해졌다고 사용자가 판단했다. 두 스크립트에 OS 이름 분기(`uname`·`OSTYPE`)는 이미 없다.
- 범위: `scripts/service_lifecycle.sh` 의 cgroup·systemd 판정 함수 넷(`lifecycle_cgroup_path`·`lifecycle_cgroup_unit`·`lifecycle_pid_supervisor`·`lifecycle_assert_pid_is_unsupervised`)과 호출, 계보 출력의 cgroup 줄, `LIFECYCLE_PROC_DIR`, 관련 주석·오류 문구를 지운다. `/proc` cwd 조회와 `lsof`/`ss` 대체는 남긴다. 해당 테스트(`test_lifecycle_adversarial.py` 의 cgroup 테스트, `test_service_lifecycle.py` 의 거부 전파 테스트)를 지운다. `deploy/systemd/README.md` 는 systemd 절을 빼고 운영 절차만 `deploy/README.md` 로 옮기며 `README.md`·`.env.example`·`deploy/caddy/README.md` 의 참조와 언급을 고친다. 과거 아카이브·QA·증거 기록은 고치지 않는다.
- 설계 승인: 승인 일자 2026-09-24 | 승인 확인 시각 2026-09-24 00:55 | bounded, 사용자 「systemd 관련된거도 모두 제거해야돼 불필요해졌어」 뒤 설계 제시, 문서 처리 선택 「deploy/README.md 로 이동 (Recommended)」
- [x] 설계 승인(bounded) - [x] 스크립트 삭제(`service_lifecycle.sh` 함수 넷·호출·cgroup 계보 줄·`LIFECYCLE_PROC_DIR`) - [x] 테스트 삭제(cgroup 테스트 12·진입점 거부 전파 1 삭제, 입양 성공 1 재작성, 입양 거부 테스트를 두 진입점으로 매개변수화) - [x] 문서 이동·정리(`deploy/README.md`) - [x] 티어 확정 T3(실행 코드 스크립트 88줄·테스트 254줄 삭제로 300줄 초과) - [x] 과잉설계 리뷰 「Lean already. Ship.」 - [x] `closing-bet-reviewer` APPROVE(low): 로그아웃 생존 전제 문장 복구·줄바꿈 반영, 옛 유닛 이력 포인터와 부팅 유닛 경고는 승인 범위(systemd 절 제거)라 미반영 - [x] 심층 리뷰(critic) ACCEPT-WITH-RESERVATIONS: 보류 1(재점유 감지는 관측 창 안에서만 성립)은 `deploy/README.md` 에 병행 금지 문단을 두고 기록 문구를 한정해 반영, 보류 2(restart 진입점 거부 전파 공백)는 매개변수화로 반영, 사소 2건 반영 - [x] pytest 전체 2696 passed, 2 skipped(exit 0, 리뷰 반영 뒤) - [ ] QA(격리 사본 CLI 하네스)

### [INFRA-079] 유물 사용량 저장소 `data/usage.db` 의 이메일 행 확인과 정리
- 카테고리: 인프라 | 티어: T1(남은 단계는 운영자 확인과 파일 정리) | 근거: `[FE-045]` 계획 검토(2026-09-22). 이메일을 기본 키로 쓰던 유물 모듈 `services/usage_tracker.py`(`usage_log`)·`engine/services/usage_tracker.py`(`api_usage`)는 코드 삭제분으로 제거했다(2026-09-24, 커밋 `6efcb93`, 아카이브 2026-09-24). 개발 기기의 `data/usage.db` 는 두 테이블 모두 행 0 이나 운영 서버의 파일은 이 기기에서 확인할 수 없다.
- 남은 범위: 운영자가 운영 서버에서 `sqlite3 data/usage.db 'select count(*) from usage_log; select count(*) from api_usage'` 로 행 수를 읽어 기록한 뒤 파일을 제거한다. 코드가 사라져 계정 삭제(`[FE-045]`)와 0600 좁히기(`[FE-046]`)가 이 파일에 닿지 않으므로 제거 전까지는 `chmod 600 data/usage.db` 로 둔다. 원격 서버 접속은 운영자가 한다.
- [x] 코드 삭제(T3, 설계 승인 2026-09-24 00:36, QA 필수 3/3) - [ ] 운영 서버 행 수 확인과 파일 제거(운영자)
