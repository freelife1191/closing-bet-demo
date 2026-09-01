---
name: dev-cycle
description: Use when working through this project's backlog — runs one TODO item from planning to archive with exactly two approval gates, choosing review depth and verification scope by tier. Triggers on "/dev-cycle", "다음 작업 진행", "todo 진행", "백로그 진행".
---

# dev-cycle

`docs/dev-cycle/TODO.md` 의 항목 하나를 계획부터 아카이브 기록까지 완주시킨다.
승인 게이트는 두 곳뿐이다.

## 호출

| 형식 | 동작 |
|---|---|
| `/dev-cycle next` | 백로그에서 다음 항목을 골라 시작한다 |
| `/dev-cycle <ID>` | 지정한 항목을 시작한다. 예: `/dev-cycle INFRA-001` |
| `/dev-cycle status` | 백로그 현황만 보고하고 끝낸다 |

## 참조

- 티어 판정과 위험 경로: `references/tier-rules.md`
- TODO 및 아카이브 형식: `references/archive-format.md`
- 프론트엔드 스킬 매핑: `references/frontend-skills.md` (`frontend/` 를 건드릴 때만)

세 파일의 내용을 이 문서에 복제하지 않는다. 판정이나 기록이 필요한 시점에 해당 파일을 읽는다.

## 절차

### [0] 준비

1. `git status --short` 로 작업 트리가 깨끗한지 확인한다. 커밋되지 않은 변경이 있으면
   멈추고 사용자에게 알린다.
2. 현재 브랜치를 확인한다. `develop` 이 아니면 멈추고 사용자에게 알린다.
3. `docs/dev-cycle/TODO.md` 를 읽는다.
4. `next` 이면 `P0` → `P1` → `P2` 순으로, 같은 우선순위 안에서는 위에 있는 항목을 고른다.
   ID 가 주어졌으면 그 항목을 찾는다. 없으면 멈추고 알린다.
5. 백로그가 비어 있으면 그 사실을 알리고 종료한다.

### [1] 계획

1. `autoplan` 스킬로 실행 계획을 세운다.
2. 계획에서 건드릴 파일 목록을 뽑는다.
3. `references/tier-rules.md` 의 §3 절차로 티어를 판정한다.
4. 사용자에게 다음을 제시한다.
   - 항목 ID 와 제목
   - 실행 계획
   - 판정한 티어와 그 근거. 위험 경로에 닿았다면 어느 파일인지 명시한다
   - 그 티어에서 돌릴 리뷰 목록과 검증 범위
5. **게이트 1** — 승인을 기다린다. 승인 없이 구현을 시작하지 않는다.

### [2] 구현

1. 계획대로 구현한다. 건드릴 파일이 `frontend/` 아래에 있으면
   `references/frontend-skills.md` §2 를 먼저 읽고 해당 상황에 배정된 스킬을 적용한다.
2. `git diff --stat` 으로 실제 변경 규모를 확인하고 티어를 재판정한다. 상위 티어에
   해당하면 올린다. 낮게 나와도 내리지 않는다.
3. 티어에 해당하는 리뷰를 `references/tier-rules.md` §1 의 순서대로 실행한다.
   순서를 바꾸지 않는다.
4. 각 리뷰의 지적 사항을 반영한다. 반영하지 않기로 한 지적은 그 이유를 남겨 두었다가
   게이트 2 에서 함께 보고한다.

### [3] 검증

1. 티어에 해당하는 검증을 실행한다. `frontend/` 를 건드렸다면 브라우저 실측 방식은
   `references/frontend-skills.md` §3 이 정하는 대로 고른다.
2. 실패하면 고치고 다시 실행한다. 실패를 남긴 채 다음 단계로 넘어가지 않는다.

### [4] 마감

1. 커밋 메시지 초안을 작성한다.
2. `references/archive-format.md` 의 §5 와 §6 형식으로 기록할 내용을 작성한다.
3. 사용자에게 다음을 제시한다.
   - 커밋 메시지
   - 변경 파일 목록과 증감
   - 리뷰 결과 요약. 반영하지 않은 지적이 있으면 그 이유를 함께 적는다
   - 검증 결과
   - 아카이브에 남길 기록
4. **게이트 2** — 승인을 기다린다.
5. 승인되면 한 커밋에 다음을 모두 담는다.
   - 구현 변경
   - `docs/dev-cycle/TODO.md` 에서 해당 항목 제거
   - `docs/dev-cycle/archive/daily/YYYY-MM-DD.md` 에 상세 추가
   - `docs/dev-cycle/archive/YYYY-MM.md` 에 요약 한 줄 추가와 통계 갱신
   - 위험 경로에 해당하는 파일이 새로 생겼으면 `references/tier-rules.md` §2 갱신

## 규칙

- TODO 에 없는 작업을 즉흥으로 시작하지 않는다. 진행 중에 발견한 개선점은 `TODO.md` 에
  새 항목으로 추가하고, 지금 항목을 마저 끝낸다.
- 게이트를 건너뛰지 않는다. 사소해 보이는 항목도 두 게이트를 모두 거친다.
- 티어를 낮추지 않는다.
- 리뷰 순서를 바꾸지 않는다.
- 검증 실패를 남긴 채 커밋하지 않는다.

## 중단

어느 단계에서든 중단되면 작업 트리를 그대로 두고 상황을 보고한다. `TODO.md` 의 항목은
제거하지 않는다. 다음 호출에서 같은 항목을 이어서 진행할 수 있다.
