# Codex 개발 사이클 연결 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 사이클과 감사 역할을 정본 복제 없이 Codex에 연결하고 설정 검증을 마친다.

**Architecture:** 저장소의 상대 심볼릭 링크와 TOML 포인터를 추가한다. 호출 안내를
일치시키고, 파일 준비와 현재 App의 실제 호출 성공을 구분한다.

**Tech Stack:** Git, Markdown, 심볼릭 링크, TOML, Python 표준 라이브러리.

**Spec:** `docs/superpowers/specs/2026-09-06-codex-setup-design.md`

## Global Constraints

- 정본은 `.claude/skills/dev-cycle/` 과 `.claude/agents/dev-workflow.md` 에 유지한다.
- 홈 디렉터리의 기존 스킬·에이전트·설정을 변경하지 않는다. 새 의존성은 추가하지 않는다.
- 애플리케이션 서버·LLM·데이터 갱신 API를 호출하지 않는다.
- `.env` 와 `data/` 는 접근하지 않는다. `~/.claude/` 는 읽지 않고
  `~/.agents/skills` 는 디렉터리 목록만 확인한다.
- 설정 절차의 지시에 따라 현재 `develop` 에서 수행하고 모든 변경을 한 커밋으로 남긴다.
- 승인은 대화에서 완료했다. 이 계획의 구현과 검증을 현재 세션에서 이어 간다.

## Task 1: 연결과 호출 안내

**Files:**
- Create: `.agents/skills/dev-cycle`, `.codex/agents/dev-workflow.toml`
- Modify: `AGENTS.md`, `.claude/skills/dev-cycle/SKILL.md`,
  `.claude/agents/dev-workflow.md`,
  `.claude/skills/dev-cycle/references/tier-rules.md`,
  `.claude/skills/dev-cycle/references/frontend-skills.md`,
  `docs/dev-cycle/codex-setup.md`

**Interfaces:**
- Consumes: `name: dev-cycle` 인 원본 스킬, 감사 역할 본문과 「하지 않을 일」.
- Produces: `$dev-cycle` 탐색 경로와 `agent_type: "dev-workflow"` 역할 정의.

- [x] 시작 상태와 누락 경로를 확인한다. `develop`, 깨끗한 트리, 두 연결 경로 부재를 확인했다.
- [x] 상대 링크와 원본을 참조하는 TOML 정의를 만든다.

```bash
mkdir -p .agents/skills .codex/agents
ln -s ../../.claude/skills/dev-cycle .agents/skills/dev-cycle
```

TOML은 설정 문서 §2의 필드만 사용한다. 설치 검증 요청은 카테고리 감사보다 먼저
판정하며, 역할의 제약만 반환하도록 지시한다.

- [x] 사이클 실행 환경 표를 `$qa-only`, `$qa`, `$review`, `$code-review`,
  `superpowers:writing-plans` 및 역할 포인터 방식으로 맞춘다. 과잉설계 리뷰는
  원본의 ponytail 기준을 읽는 `code-reviewer` 를 사용하고 직접 검토를 대체 수단으로 둔다.
- [x] 진입 문서·역할 호출 문단·티어 문단·프론트엔드 설치 문단을 같은 안내로 맞춘다.
  티어 판정 규칙은 변경하지 않으므로 백로그 99건의 티어도 변경하지 않는다.

## Task 2: 검증과 기록

**Files:**
- Modify: `docs/dev-cycle/codex-setup.md`, 이 계획의 체크박스.

**Interfaces:**
- Consumes: Task 1의 링크·역할 정의·호출 안내.
- Produces: 확인 사실과 미검증 항목이 분리된 설정 기록, 한 개의 Git 커밋.

- [x] Python 표준 라이브러리로 링크 도달·frontmatter 이름·TOML 키·원본 경로를 확인한다.

```python
from pathlib import Path
import tomllib

root = Path.cwd()
link = root / '.agents/skills/dev-cycle'
assert link.is_symlink()
assert link.resolve() == (root / '.claude/skills/dev-cycle').resolve()
assert 'name: dev-cycle' in (link / 'SKILL.md').read_text()
agent = tomllib.loads((root / '.codex/agents/dev-workflow.toml').read_text())
assert agent['name'] == 'dev-workflow'
assert agent['sandbox_mode'] == 'read-only'
assert '.claude/agents/dev-workflow.md' in agent['developer_instructions']
assert (root / '.claude/agents/dev-workflow.md').is_file()
```

- [x] 설치된 스킬·browse·agent-browser·Next.js 문서의 존재를 확인한다. 실제 목록에 없는
  호출은 성공으로 간주하지 않는다. 홈 설정 복구를 유발하는 진단은 실행하지 않는다.
- [x] 새 역할로 제약 목록만 반환하는 호출을 시도한다. 불가능하면 일반 읽기 전용
  서브에이전트로 원본 참조만 검증하고 두 결과를 구분해 기록한다.
- [x] 연결된 스킬의 `[S] status` 로 최근 완료 3건·우선순위별 수·첫 항목·미완료 QA와
  작업 트리 상태를 확인한다. 다음 사이클을 실행하지 않는다.
- [x] 독립 읽기 전용 검토로 문서 간 모순과 경로 오류를 확인하고 지적을 반영한다.
- [x] `git diff --check` 와 변경 파일 목록을 확인하고 설정 문서에 실측 결과를 남긴다.
- [x] 지정 파일만 스테이징하고 `docs(dev-cycle): codex 에서 같은 이름으로 사이클과 감사를 부르게 한다`
  제목으로 커밋한다. 커밋 후 깨끗한 작업 트리를 확인한다.
