# 개발 라운드와 UltraQA Implementation Plan

> **For agentic workers:** Use the approved design and execute the bounded tasks below. Record verification evidence before completion.

**Goal:** 새 라운드의 brainstorming과 Codex UltraQA를 연결하고 실제 업무 흐름을 검증한다.

**Architecture:** 기존 Markdown 스킬과 역할 정의를 수정한다. 상태·기록 계약은 기존
references에 유지하고, App 대응 QA만 별도 참조 문서로 분리한다.

**Tech Stack:** Markdown, TOML, Python 표준 라이브러리, Git, Codex app-server JSON-RPC.

**Spec:** `docs/superpowers/specs/2026-09-06-dev-cycle-brainstorming-ultraqa-design.md`

## Constraints

- 승인된 동일 설계를 다시 승인받지 않는다.
- 기존 QA·아카이브와 다른 작업의 변경을 보존한다.
- 운영 앱·시크릿·데이터와 기존 OMX 상태에 쓰지 않는다.
- 전용 역할은 실제 런타임 메타데이터로 확인한다.

## Task 1: 실행 계약

- [x] `SKILL.md`에 상태 분류·brainstorming·승인 후 자동 진행·필수 실패 차단을 반영한다.
- [x] `references/ultraqa.md`에 Codex 행렬·실행·재시도·App 상태 대응을 정리한다.
- [x] `CLAUDE.md`, `AGENTS.md`, `dev-workflow.md`, 설정 안내를 동일 계약에 맞춘다.
- [x] 독립 담당자가 tier-rules/archive-format/frontend-skills/browser-notes 참조를 맞춘다.

## Task 2: 검증과 마감

- [x] 격리 하네스에서 정상과 적대적 시나리오를 실제 실행했다 (6/9 통과, 전체 완료 아님). 결과 판정은 Git·파일·종료
  코드·런타임 메타데이터로 하고, 에이전트의 성공 문구만으로 통과시키지 않는다.
- [x] 스킬 형식, 경로·절 참조, 원본 연결과 `git diff --check`를 확인했다.
- [x] 독립 문서 리뷰 지적 7건을 반영했고 제한된 재실행 후 동일 실패 3회에서 중단했다.
- [x] UltraQA Report에 행렬·실행 코드·수정·정리·잔여 위험을 기록했다.
- [x] 검증된 변경을 커밋하고 INFRA-033을 완료 아카이브에 반영한다.

초기 검증은 `ULTRAQA STOPPED: Same failure detected 3 times`였다. 구현 커밋은 4eaba62이며
당시 필수 미통과로 완료 아카이브를 작성하지 않았다. 이 실패 기록은 보존한다.

## 후속 수리와 재검수

- [x] 직전 체크포인트·리뷰 hash 재사용, 설계 전 위험 티어 판정을 보완했다.
- [x] 신뢰된 worktree의 전용 역할, Git metadata 쓰기 사전검사, App/native lifecycle 경계를 검증했다.
- [x] 신규 파일 staged 검사 실패 시 커밋 차단과 원문 JSON 보존 후 재개를 실제 actor로 확인했다.
- [x] Codex App 필수 시나리오 8/8, T3 fixture QA 6/6·unittest 3/3·전체 아카이브·clean을 확인했다.
- [x] 독립 최종 증거 검수 APPROVE와 소유 app-server 19개·worktree/fixture 정리를 확인했다.

최종 App 대응 결과는 `ULTRAQA COMPLETE: Goal met after 5 cycles`이며
`docs/dev-cycle/qa/INFRA-033-recheck.md`에 남긴다. 별도 native CLI lifecycle 진단 중단은
App 필수 통과에 합산하지 않는다. 원본의 미추적 package.json은 보존했다.
