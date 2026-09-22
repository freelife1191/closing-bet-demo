# codex 작업 환경 구성 프롬프트

이 파일은 codex 에 넘기는 프롬프트다. 저장소 루트에서 codex 를 열고 「`docs/dev-cycle/codex-setup.md`
를 읽고 그대로 수행해」라고 하거나 아래 본문을 그대로 붙여 넣는다. 기기마다 한 번 실행하면
되고, 저장소에 남는 결과물은 커밋되므로 두 번째 기기부터는 홈 디렉터리 쪽만 채우면 된다.

초안은 2026-09-06 에 codex-cli 0.153.0 과 oh-my-codex 0.20.3 을 기준으로 작성했다.
같은 날 Codex App 세션에서 PATH의 CLI 0.153.4·OMX 0.21.3 설치를 확인해 절차를 보완했다.
설치 파일이 존재하는 것과 현재 세션에서 호출되는 것은 별도로 확인한다. 실제와 다른 것을
만나면 그 자리에서 이 문서를 고쳐 같은 커밋에 담는다. 초기 실측은 §7에 있고,
이후 전용 호출 성공과 검증 절차 보완은 §8에 있다.

---

## 목표

이 저장소를 codex 로 열었을 때 Claude Code 에서 쓰던 것과 같은 이름으로 개발 사이클과
카테고리 감사를 부를 수 있게 한다. 구체적으로 다음 넷이다.

1. `$dev-cycle` 로 `.claude/skills/dev-cycle/SKILL.md` 의 절차가 돈다.
2. 저장소의 `dev-workflow` 에이전트 정의가 `.claude/agents/dev-workflow.md` 를
   참조한다. 현재 호스트가 이 역할을 제공하면 `spawn_agent` 의
   `agent_type: "dev-workflow"` 로 호출한다. 제공하지 않으면 §4의 대체 수단과
   미검증 범위를 기록한다.
3. 사이클이 부르는 내부 스킬이 전부 이 기기의 codex 에 있다. codex 에 없는 Claude Code
   전용 스킬은 oh-my-codex(omx) 의 것으로 대체한다.
4. 문서가 실측한 결과와 같다.

절차와 역할 정의의 원본은 `.claude/skills/dev-cycle/` 과 `.claude/agents/dev-workflow.md`
하나뿐이다. **복제하지 않는다.** codex 쪽에는 원본을 가리키는 링크와 정의 파일만 둔다.
같은 내용이 두 곳에 있으면 반드시 어긋난다.

## 제약

- `.env` 로 시작하는 파일을 열어야 하면 변수 이름과 값의 유무만 확인하고 값은 어디에도
  옮겨 적지 않는다.
- `data/` 아래는 읽기 전용으로만 연다.
- 앱 서버에 요청을 보내지 않는다. 네트워크는 스킬 설치 명령(`npm`, `npx`, `git clone`)에만
  쓴다.
- `~/.claude/` 아래는 `~/.claude/skills/gstack/setup` 을 실행하는 것 외에 읽거나 실행하지
  않는다. `~/.agents/skills` 는 디렉터리 목록만 본다.
- 홈 디렉터리의 기존 스킬과 에이전트 정의를 지우거나 덮어쓰지 않는다. 이미 있으면 그대로
  쓴다.
- 이 설정 작업에서는 개발 사이클을 시작하지 않는다. 상태만 확인하며 다음 사이클은
  사용자가 `$dev-cycle next` 로 시작한다.
- 마지막 보고에 무엇을 확인했고 무엇을 새로 설치했는지 적는다. 확인하지 못한 것은
  했다고 적지 않는다.

## 0. 환경 확인

```bash
printenv CODEX_HOME                  # 미설정이면 기본값은 ~/.codex
codex --version
omx list                            # 설치 패키지의 카탈로그. 현재 App의 도구 목록과는 다르다
git status --short                    # 비어 있어야 한다
```

확인할 스킬 위치는 `$CODEX_HOME/skills`, `~/.agents/skills`, 설치된 플러그인,
**저장소의 `.agents/skills`** 다. 에이전트 정의는 `$CODEX_HOME/agents/*.toml` 과
**저장소의 `.codex/agents/*.toml`** 을 확인한다. 저장소에 둔 연결은 커밋되므로
기기마다 복제할 필요가 없다. 단, 파일 생성만으로 현재 App의 목록이 갱신되었다고
판정하지 않는다. 현재 세션의 스킬 목록과 사용 가능한 `agent_type` 이 호출 여부의 근거다.

OMX 0.21.3의 `omx doctor` 는 시작할 때 네이티브 훅 claim journal 복구를 수행한다.
홈 설정을 보존하는 이번 점검에서는 실행하지 않고 카탈로그·파일 존재·현재 도구 목록으로
필요한 설치 상태를 확인한다. 이 결과를 `omx doctor` 전체 통과로 보고하지 않는다.

omx 가 없으면 CLI 패키지를 설치한다. 홈 초기화는 별도 단계다.

```bash
npm install -g oh-my-codex
```

`omx setup --scope user` 는 홈 설정과 스킬·에이전트 정의를 만든다. 기존 사용자 설정이나
정의가 있으면 이번 절차에서 일괄 초기화를 실행하지 않는다. 필요한 스킬·역할 중 부족한
것과 홈 초기화를 생략한 이유를 보고한다. 기존 설정·정의가 없는 새 환경에서만 홈 초기화를
수행한다. 이 기기는 이미 필요한 설치가 갖추어져 있으므로 두 단계 모두 실행하지 않았다.

## 1. dev-cycle 스킬 (저장소에 커밋)

```bash
mkdir -p .agents/skills
ln -s ../../.claude/skills/dev-cycle .agents/skills/dev-cycle
test -f .agents/skills/dev-cycle/SKILL.md && echo ok
```

위 생성 명령은 경로가 없을 때만 실행한다. 이미 있다면 `readlink .agents/skills/dev-cycle`
로 대상을 확인한다. 다른 경로를 가리키거나 일반 파일·디렉터리이면 그대로 보존하고
충돌을 보고한다. `ln -sf` 로 덮어쓰지 않는다.

호출 이름은 디렉터리가 아니라 `SKILL.md` frontmatter 의 `name: dev-cycle` 이 정한다. 링크라서
원본을 고치면 그대로 반영된다. 자동 탐색은 현재 세션의 스킬 목록에 `dev-cycle` 이
저장소 출처로 보이는 것으로 확인한다. `/skills` 를 제공하는 환경이면 그 목록을 쓴다.
목록을 새로 읽을 수 없는 App에서는 링크 검증과 자동 탐색 확인을 구분해 기록한다.

## 2. dev-workflow 에이전트 (저장소에 커밋)

`.codex/agents/dev-workflow.toml` 이 없으면 아래 내용으로 만든다. 이미 있으면
원본을 참조하는지 확인하며, 다른 사용자 정의를 덮어쓰지 않는다.

```toml
# 역할 정의의 정본은 .claude/agents/dev-workflow.md 이다.
name = "dev-workflow"
description = "이 저장소의 한 기능 카테고리를 읽기 전용으로 감사해 개선 항목 초안을 산출한다. 카테고리 이름(챗봇, 종가베팅, VCP, 수급·백테스트, 프론트엔드, 인프라) 하나를 입력받는다."
sandbox_mode = "read-only"
developer_instructions = """
작업 디렉터리의 `.claude/agents/dev-workflow.md` 를 먼저 읽고 그 본문을 역할 정의로 따른다.
그 파일의 「하지 않을 일」이 이 에이전트의 제약이다. 어떤 파일이나 상태도 바꾸지 않는다.
설치 검증으로 제약 목록만 요청받으면 그 목록만 반환하고 감사를 시작하지 않는다.
감사를 요청받으면 프롬프트의 카테고리 이름 하나에 해당하는 범위만 감사한다.
"""
```

모델과 추론 수준은 이 정의에 고정하지 않고 호스트의 서브에이전트 기본 설정을 따른다.
이 기기의 `$CODEX_HOME/config.toml` 에는 `[agents].default_subagent_model` 과
`default_subagent_reasoning_effort` 가 있다. 다른 호스트에서도 같은 값이 적용된다고
가정하지 않는다. 역할 연결 확인 방법은 §4를 따른다.

## 3. 내부 스킬 (기기마다 확인)

사이클과 감사가 부르는 것의 전체 목록이다. 「확인」 열의 방법으로 하나씩 보고, 없는 것만
「없을 때」 열대로 설치한다.

| 사이클이 부르는 것 | Claude Code | codex 에서 부를 이름 | 확인 | 없을 때 |
|---|---|---|---|---|
| 새 라운드 설계 | `superpowers:brainstorming` | `$superpowers:brainstorming` | 현재 스킬 목록과 설계 승인 단계 | 아래 superpowers 설치 |
| 시나리오 구성 | `/qa-only` | `$ultraqa`의 행렬 계획 | 현재 스킬 목록에 `ultraqa` | omx 설치 (0번) |
| 시나리오 실행·진단·정리 | `/qa` | `$ultraqa` | 스킬과 `references/ultraqa.md`의 native/App 대응 확인 | omx 설치 (0번) |
| 심층 리뷰 (T3) | `/review` | `$review` | `/skills` 에 `review` | gstack 설치 |
| browse 바이너리 | `/qa` 와 `/qa-only` 가 내부에서 쓴다 | 같다 | `test -x "${CODEX_HOME:-$HOME/.codex}/skills/gstack/browse/dist/browse"` | gstack 설치가 함께 빌드한다 |
| 브라우저 실측 | agent-browser | 같다. 셸 명령이다 | `which agent-browser` | `npm install -g agent-browser`. 검증마다 고유 namespace/session과 가짜 계정·fixture를 준비하며 기존 로그인 세션을 요구하거나 자동 재사용하지 않는다 |
| 코드 리뷰 | `closing-bet-reviewer` 역할(`.claude/agents/`, 2026-09-22 부터. 없으면 `feature-dev:code-reviewer`) | omx `$code-review` 스킬. §13 의 전용 호출이 확인되면 `agent_type: "closing-bet-reviewer"` | `/skills` 에 `code-review`, `$CODEX_HOME/agents/code-reviewer.toml` | omx 설치 (0번) |
| 과잉설계 리뷰 | `/ponytail-review` | omx `code-reviewer` 에이전트를 `spawn_agent` 로 띄운다. 프롬프트는 아래 「과잉설계 리뷰 프롬프트」 | `$CODEX_HOME/agents/code-reviewer.toml` | omx 설치 |
| 계획 문서 (T3) | `superpowers:writing-plans` | `$superpowers:writing-plans` | 현재 스킬 목록에 `superpowers:writing-plans` | 아래 superpowers 설치. 그래도 없으면 omx `$plan` 으로 대신하고 그 사실을 문서에 적는다 |
| 계획 검토 (architectural·T3) | `oh-my-claudecode:critic` 에이전트 | omx `critic` 역할을 `spawn_agent` 의 `agent_type: "critic"` 으로 띄운다 | `$CODEX_HOME/agents/critic.toml` | omx 설치 (0번) |
| 보안 리뷰 보강 (인증·시크릿) | `oh-my-claudecode:security-reviewer` 에이전트 | `$security-review` → 보안 범위의 `code-reviewer` | 스킬 목록과 실제 위임 대상 확인 | 스킬이 없으면 설치를 확인한다. 독립 역할을 사용할 수 없으면 미완료로 기록하며 시크릿 검사 세 가지로 대체하지 않는다 |
| 프론트엔드 스킬 | `vercel-react-best-practices`, `vercel-composition-patterns` | 같다 | 현재 스킬 목록에 두 이름 | `npx skills add vercel-labs/agent-skills` 뒤 `~/.agents/skills` 에 두 디렉터리가 생겼는지 본다. 이름이 다르면 `npx skills find react --owner vercel-labs` 로 찾는다 |
| 프론트엔드 실행 검증 | `next-dev-loop` | `$next-dev-loop` | 현재 스킬 목록 | `skill-installer` 로 `vercel/next.js`의 `canary`, `skills/next-dev-loop` 설치 |
| Cache Components 도입·최적화 | `next-cache-components-adoption`, `next-cache-components-optimizer` | 같은 이름의 `$` 호출 | 현재 스킬 목록에 두 이름 | 같은 저장소·브랜치의 `skills/<스킬 이름>` 설치 |
| Partial Prefetching 도입 | `next-partial-prefetching-adoption` | `$next-partial-prefetching-adoption` | 현재 스킬 목록 또는 새로 읽은 Codex 스킬 메타데이터 | 같은 저장소·브랜치의 `skills/next-partial-prefetching-adoption` 설치 |
| Next.js 버전 변경 | `next-upgrade` 사본 | `$vercel:next-upgrade` | 활성 Vercel 플러그인과 현재 스킬 목록 | 설치된 플러그인의 제공 여부 확인. 없으면 번들 업그레이드 문서와 `@next/codemod`를 대체 수단으로 사용 |
| Next.js 번들 문서 | 파일 | 같다 | `ls frontend/node_modules/next/dist/docs/01-app` | `(cd frontend && npm install)` |
| 카테고리 감사 | `dev-workflow` 에이전트 | 역할이 제공되면 `spawn_agent` 에 `agent_type: "dev-workflow"` | 2번과 4번 | 2번. 현재 App의 역할 미노출은 재설치 근거가 아니다 |

**gstack 설치.** 설치 대상은 `${CODEX_HOME:-~/.codex}/skills` 이고 browse 바이너리를 함께
빌드한다.

```bash
~/.claude/skills/gstack/setup --host codex
# Claude Code 쪽에도 gstack 이 없으면
git clone https://github.com/garrytan/gstack.git ~/gstack && ~/gstack/setup --host codex
```

**superpowers 설치.** 현재 기기에서는 아래 링크와 `superpowers:writing-plans` 목록 항목이
확인되어 재설치하지 않는다. 다른 기기에서는 두 경로가 없을 때만 생성하고 현재 스킬
목록에서 호출 이름을 확인한다. 모든 스킬의 이름에 같은 접두사 규칙을 가정하지 않는다.

```bash
git clone https://github.com/obra/superpowers.git ~/.codex/superpowers
mkdir -p ~/.agents/skills && ln -s ~/.codex/superpowers/skills ~/.agents/skills/superpowers
```

**과잉설계 리뷰 프롬프트.** `/ponytail-review` 는 Claude Code 플러그인이라 codex 에 없다.
그 리뷰의 판정 기준 전문은 `CLAUDE.md` 의 `## Code Philosophy — ponytail` 절에 있으므로,
omx 의 `code-reviewer` 에이전트(읽기 전용)에 그 절과 출력 형식을 주어 같은 리뷰를 받는다.
`ai-slop-cleaner` 스킬은 목적이 같지만 코드를 직접 고치고 회귀 테스트를 먼저 쓰므로,
리포트를 다음 단계의 입력으로 쓰는 사이클의 리뷰 자리에는 맞지 않아 쓰지 않는다.

```
`git diff` 의 변경만 본다. 판정 기준은 `CLAUDE.md` 의 `## Code Philosophy — ponytail`
절이며 그 절을 먼저 읽는다. 과잉설계와 불필요한 복잡도만 다루고 정확성과 보안과 성능은
다루지 않는다. 결과는 발견 하나에 한 줄로 적는다.
`<파일>:L<줄>: <delete|stdlib|native|yagni|shrink>: <무엇을>. <무엇으로 대신할지>.`
마지막 줄은 `net: -<N> lines possible.` 이고, 덜어낼 것이 없으면 `Lean already. Ship.`
한 줄만 적는다. 코드를 고치지 않는다. `.env` 로 시작하는 파일의 값을 옮겨 적지 않는다.
```

## 4. 검증

1. 현재 세션의 스킬 목록에 다음이 있는지 확인한다. `dev-cycle`(저장소), `ultraqa`, `review`,
   `code-review`, `superpowers:brainstorming`, `superpowers:writing-plans`, `vercel-react-best-practices`,
   `vercel-composition-patterns`. 조건부 프론트엔드 작업도 포함해 `next-dev-loop`,
   `next-cache-components-adoption`, `next-cache-components-optimizer`,
   `next-partial-prefetching-adoption`, `vercel:next-upgrade` 를 확인한다.
   로컬 `skills/list` 가 플러그인 스킬을 반환하지 않으면 현재 App의 플러그인 스킬 목록과
   활성 설정을 별도로 확인한다. 한 목록에 없다는 이유만으로 재설치하지 않는다.
2. `$dev-cycle status` 를 부른다. 현재 목록에 없으면 연결된
   `.agents/skills/dev-cycle/SKILL.md` 를 직접 읽어 `[S] status` 를 수행한다.
   최근 완료 3건·우선순위별 수와 첫 항목·진행 중 사이클·미완료 QA·`git status` 를 보고한다.
   직접 수행했으면 자동 탐색까지 확인한 것으로 보고하지 않는다. 사이클을 시작하지 않는다.
3. `spawn_agent` 로 `agent_type: "dev-workflow"` 를 띄우되 프롬프트는 「정의 파일을 읽고
   「하지 않을 일」 목록만 돌려줘. 감사는 시작하지 마」로 한다. 이 호출에 목록이 돌아오면
   역할 등록과 원본 참조를 확인한 것이다. 역할을 제공하지 않거나 `unknown agent_type`
   오류가 나면 재설치하지 않는다. 사용 가능한 읽기 전용 서브에이전트에 TOML과 원본의
   경로를 주어 같은 제약 목록만 요청하고, **원본 참조만 확인했으며 전용 역할 호출은
   확인하지 못했다**고 기록한다. 전용 호출까지 검증하는 작업에서는 여기서 끝내지 않고
   §8의 새 실행 문맥 검증을 수행한다. 같은 작업에서 턴이나 자식만 추가하는 것으로
   역할 목록이 새로 로드된다고 가정하지 않는다.
4. 연결 설치만 확인하는 호출에서는 `$ultraqa`와 `$review`를 실제 업무에 실행하지 않는다.
   사용자가 동적 검증을 명시하면 격리된 표면에서 해당 흐름을 검증하고 실행 범위를 기록한다.

## 5. 문서 갱신

실측한 결과대로만 고친다. 확인하지 못한 것은 적지 않는다.

- `.claude/skills/dev-cycle/SKILL.md` 의 `## 실행 환경`
  - 표의 codex 열을 3번 표의 「codex 에서 부를 이름」 열과 같게 한다. `$` 표기를 쓴다.
  - 저장소의 `.agents/skills/dev-cycle` 링크와 `$dev-cycle` 호출, 확인할 스킬 위치 네 곳을
    안내한다. 현재 App에 스킬이 노출되지 않을 때 파일을 직접 읽는 대체 수단도 적는다.
  - 「**과잉설계 리뷰에 대응하는 스킬이 codex 에 없다.**」 문단을 위의 에이전트 방식으로
    바꾼다. 에이전트를 띄울 수 없을 때 직접 검토한다는 내용은 대체 수단으로 남긴다.
  - 「**codex 는 `CLAUDE.md` 를 자동으로 읽지 않는다.**」 문단은 그대로 둔다.
- `.claude/agents/dev-workflow.md` 의 「이 정의를 부르는 방법」: TOML의 원본 참조,
  역할이 제공될 때의 `agent_type: "dev-workflow"` 호출, 미노출 시 파일 경로를 주는
  대체 수단을 적는다. 본문을 프롬프트로 복사하지 않는다.
- `AGENTS.md`: `$dev-cycle` 연결과 목록 미노출 시 이 문서로 점검하는 절차를 안내한다.
- `.claude/skills/dev-cycle/references/tier-rules.md` 의 §1 아래와 `Agent` 도구 문단 앞에
  있는 codex 문단, `references/frontend-skills.md` §4 의 codex 문단을 새 이름에 맞춘다.
  `vercel-composition-patterns` 가 codex 에도 보이므로 「대응하는 것은 없다」를 고친다.
- 연결 설치만 할 때는 `CLAUDE.md`를 고치지 않는다. 개발 라운드 규약을 바꾸는 작업은 공통 요약도 함께 갱신한다.

## 6. 커밋과 보고

커밋은 하나다. `.agents/skills/dev-cycle` 링크, `.codex/agents/dev-workflow.toml`, 고친
문서, 그리고 이 문서를 고쳤다면 그것까지 담는다. 제목은
`docs(dev-cycle): codex 에서 같은 이름으로 사이클과 감사를 부르게 한다` 로 하고, 본문에
무엇을 실측했고 무엇을 새로 설치했는지 적는다. 커밋을 묻지 않는다.

보고는 네 가지다. 확인한 것, 새로 설치한 것, 설치하지 못한 것과 그 이유,
`$dev-cycle status` 의 브리핑. 그다음 멈춘다. 다음 사이클은 사용자가 `$dev-cycle next` 로
시작한다.

## 7. 2026-09-06 Codex App 실측 기록

실행 환경은 tmux 밖의 Codex App이며, 시작 브랜치는 `develop`, 시작 작업 트리는 깨끗했다.
아래는 이 설정 작업에서 확인한 범위다. 다른 기기의 설치·로그인·호출 가능 여부까지
보장하는 기록은 아니다.

| 대상 | 결과 | 근거 |
|---|---|---|
| PATH의 Codex CLI / OMX / agent-browser | 0.153.4 / 0.21.3 / 0.31.1 | `codex --version`, 설치 패키지의 `package.json` |
| OMX 카탈로그 | 스킬 33개 중 활성 23개, 에이전트 프롬프트 30개 중 활성 16개 | `omx list --json`. 현재 App의 역할 목록과 별개 |
| 기존 내부 스킬 | `qa`, `qa-only`, `review`, `code-review`, `plan`, `superpowers:writing-plans`, 두 프론트엔드 스킬 확인 | 현재 세션 스킬 목록과 허용된 설치 경로의 존재 확인 |
| browse / agent-browser / Next.js 문서 | 실행 파일 두 개와 번들 문서 디렉터리 확인 | 파일 존재·실행 권한·명령 경로 확인 |
| 브라우저 세션 | 활성 세션 없음 | `agent-browser session list`: `No active sessions`. `adguard-cft-extension` 로그인 상태는 확인하지 못함 |
| `dev-cycle` 링크 | 정본과 네 참조 파일에 도달 | 상대 경로·frontmatter 이름 검사 통과 |
| `dev-workflow` 정의 | TOML 구문·읽기 전용 선언·원본 경로·설치 검증 분기 확인 | Python `tomllib` 검사. 이 문서 §2의 예시와 실제 정의도 일치 |
| 전용 역할 호출 | 현재 App에서 실패 | `agent_type: "dev-workflow"` → `unknown agent_type 'dev-workflow'` |
| 역할 원본 참조 | 대체 수단으로 확인 | 기존 `code-reviewer` 에 TOML과 원본 경로를 주어 「하지 않을 일」 세 항목을 반환받음. 전용 역할 등록 성공으로 간주하지 않음 |
| 상태 브리핑 | 연결 파일을 직접 읽어 수행 | `.agents/skills/dev-cycle/SKILL.md` 의 `[S] status`. `$dev-cycle` 자동 탐색은 현재 세션에서 미검증 |

새로 추가한 것은 저장소의 상대 링크와 TOML 정의다. 홈 디렉터리에 새로 설치하거나
변경한 것은 없다. 당시 확인한 기본 목록의 도구는 있었고, 이후 발견한 조건부 스킬 누락은
§9에서 보완했다. 전용 역할 호출과 새 스킬의 자동 탐색은 위 표처럼 별도로 남겼다.
앱 서버·LLM·데이터 갱신 요청과 실제 QA·감사는
실행하지 않았다. `omx doctor` 는 §0의 이유로 실행하지 않았다.

`[S] status` 결과는 다음과 같다.

- 최근 완료: 09-05 `CHAT-017` 공용 메모리의 사용자 분리 (`1b1e4bb`),
  09-06 `CHAT-021` 프로필 API 소유자 판정 (`40b37a2`),
  09-06 `CHAT-026` 대시보드 프로필 저장 경로 통일 (`b7f790c`).
- P0: 0건. P1: 27건, 첫 항목은 `CHAT-022` 메모리 전체 동기화의 다른 워커 행 삭제.
  P2: 72건, 첫 항목은 `CHAT-027` 프로필과 메모리 영역의 어긋남.
- 진행 중 사이클이나 아카이브되지 않은 QA 문서는 없다. `FE-030`·`FE-038`의 완료
  체크는 다른 사이클에서 수행한 내용이다.
- 브리핑 시점 작업 트리에는 이번 설정 변경만 있다. 커밋 후 상태는 최종 보고에서 확인한다.

티어 조건과 제품 동작을 변경하지 않아 백로그 99건의 판정 변경은 없다. 링크·TOML·문서
참조 검사를 실행하며, 커밋 전에는 `git diff --check` 와 변경 파일 범위를 다시 확인한다.
독립 문서 검토에서 지적한 역할 호출의 제공 조건과 기존 홈 설정이 있을 때의 OMX 초기화
제한을 각각 실행 환경 표와 §0에 반영했다.
애플리케이션 코드를 변경하지 않았으므로 pytest·vitest·타입 검사는 이번 설정 작업에서
실행하지 않는다.

## 8. 전용 호출 재검증과 원인 확인

2026-09-06 후속 검토에서 `$dev-cycle` 은 저장소 출처의 현재 스킬 목록에 노출되는 것을
확인했다. §7의 자동 탐색 미검증은 이 확인으로 해소했다.

`dev-workflow` 는 설치 정의를 변경하지 않고도 **새로 초기화한 App 내장 CLI에서
전용 호출과 자식 응답이 성공**했다. 따라서 이번 실패를 TOML 오류나 플러그인 설치
누락으로 처리하지 않는다. 기존 작업과 자식에서는 실패하고 새로 초기화한 실행에서는
성공했다. 이 대조 결과로 역할 목록이 실행 문맥 초기화 시 고정되는 것으로 판단했다.
내부 캐시 구현을 직접 관측한 것은 아니다. 다음 대조 결과가 근거다.

| 검증 조건 | 결과 |
|---|---|
| 기존 App 작업의 새 턴에서 전용 호출 | `unknown agent_type 'dev-workflow'` |
| 그 작업에서 새로 띄운 일반 자식이 전용 역할 호출 | 동일 오류 |
| 사용자 홈에 같은 정의의 임시 링크를 둔 뒤 기존 작업에서 호출 | 동일 오류. 검증 직후 이번에 만든 링크만 제거 |
| `omx agents list --scope project` | `dev-workflow` 정의를 정상 표시. 실행 성공을 뜻하는 검사는 아님 |
| App 내장 CLI의 새 임시 실행에서 전용 호출 | `/root/dedicated_smoke` 생성과 응답 완료, 종료 코드 0 |
| 같은 바이너리의 독립 임시 app-server에서 런타임 메타데이터 확인 | 실제 자식 `agentRole: "dev-workflow"`, 부모 연결 일치, 제약 세 항목 반환 |

### 실제 실행 파일로 검증한다

이 기기에서 `PATH`의 `codex` 는 0.153.4지만, 실행 중인 App은
`/Applications/ChatGPT.app/Contents/Resources/codex` 0.153.3을 사용했다. 성공 검증도
App 내장 0.153.3으로 수행했으므로 버전 업그레이드로 고친 사례가 아니다. 다른 기기는
실행 중인 App의 실제 바이너리 경로와 버전을 먼저 확인한다.

다음 명령은 이 기기에서 확인한 바이너리를 사용한다. `--ephemeral` 은 세션 파일을
저장하지 않는 옵션이며, 새 사용자 작업을 만들지 않고 독립 검증을 수행하기 위해 쓴다.
이 검증은 Codex 모델과 네이티브 서브에이전트를 사용한다. 「제약」 절의 네트워크 제한은
주식 분석 앱·외부 데이터 서비스 요청을 계속 금지하며, 사용자가 요청한 이 Codex 전용
호출 검증은 허용 범위에 포함한다. 실제 카테고리 감사는 실행하지 않는다.

```bash
/Applications/ChatGPT.app/Contents/Resources/codex exec \
  --ephemeral --json --color never --sandbox read-only --cd "$PWD" - <<'PROMPT'
전용 역할 등록 검증만 수행한다. 첫 동작으로 네이티브 collaboration.spawn_agent를
agent_type="dev-workflow", task_name="dedicated_smoke", fork_turns="none"으로 호출하라.
다른 agent_type으로 대체하지 마라. 자식에게 다음을 전달하라.
"전용 역할 설치 검증이다. 설정이 가리키는 역할 원본을 읽고 하지 않을 일 세 항목만
한국어로 반환하라. 감사, 파일 수정, 네트워크, 검증 명령, 추가 에이전트 생성은 금지한다."
호출에 성공하면 그 자식의 완료를 기다리고 실제 유형, 자식 식별자, 반환된 제약을 보고하라.
실패하면 오류 그대로 보고하고 종료하라. 파일 변경, 설치, 앱 서버 요청, .env/data/홈
파일 읽기, 별도의 영구 사용자 작업 생성은 금지한다. 검증은 사용자가 승인했다.
PROMPT
```

### 성공 판정과 증거

종료 코드 0만으로 통과시키지 않는다. 요청한 전용 유형을 대체하지 않았는지, 실제 자식의
완료 대기가 끝났는지, 반환값에 원본의 세 제약이 있는지 확인한다. 이번 실행은
`dev-workflow`, `/root/dedicated_smoke` 와 다음 응답을 반환했다.

- 코드 파일을 수정하지 않는다.
- 사이클·리뷰 스킬·검증 명령을 실행하지 않는다.
- 담당 경로 밖을 감사하지 않는다.

첫 실행의 원시 출력은 `docs/dev-cycle/evidence/2026-09-06-dev-workflow-smoke.jsonl`
에 보관한다. 이 CLI의 JSONL은 완료된 네이티브 `wait` 를 출력하지만 V2 `spawn`의
인자와 자식 식별자를 별도 구조화 이벤트로 출력하지 않았다. 따라서 완료 문구와 별도로
런타임 메타데이터를 확인하는 두 번째 검증을 수행했다.

App 내장 바이너리를 `app-server --stdio` 로 독립 실행해 로컬 JSON-RPC로 확인했다.
`thread/start` 에 `ephemeral: true`, `sandbox: "read-only"` 를 주고 위와 같은 전용
호출 요청을 `turn/start` 로 전달했다. 완료 후 `thread/loaded/list` 와
`thread/read`(`includeTurns: false`)로 그 프로세스 안의 부모와 자식 메타데이터를 읽었다.
`item/completed` 이벤트에서 실제 자식의 응답도 확인한 뒤 검증 프로세스를 종료했다.
사용자 App의 실행 중인 작업이나 서비스를 재시작한 것은 아니다.

수집기는 `thread/loaded/list`의 `data`에 들어 있는 **문자열 ID 배열**을 처리해야 한다.
thread 객체 배열이라고 가정하면 실제 자식이 있어도 전용 호출을 미검증으로 판정한다.
현재 소유한 독립 app-server에서 얻은 ID만 `thread/read`하고, 정확한 부모와 연결된 자식의
`agentRole`, `source.subAgent.thread_spawn.agent_role`, 부모 ID 두 필드와 `ephemeral`을
함께 확인한다. `source`는 문자열일 수도 있으므로 객체 여부를 먼저 판정한다.
자식의 완료 turn·최종 응답을 같은 child ID에 결속한다. `thread/list`의 저장된 작업 목록이나
리더의 성공 문구는 전용 호출 증거가 아니다. 재검수에서도 명시적 `agent_type`을 사용한다.

임의의 새 Git fixture는 원본 저장소의 신뢰 설정을 자동으로 공유하지 않는다. 0.153.3
재검수에서는 프로세스/turn의 trust override만으로 새 fixture의 프로젝트 계층이 활성화되지
않았다. `config/read`의 project layer `disabledReason`을 먼저 확인한다. 이 저장소에서 만든
격리 worktree는 같은 설정 검사에서 계층이 활성화됐다. 검수는 그 worktree에서 수행하고
홈의 신뢰 설정을 일괄 변경하지 않는다. 필수 필드가 정상인데도 역할을 찾지 못할 때는
이 환경 오류와 실제 역할 정의 결함을 구분한다.

전체 라운드 검수는 모델 실행 전에 같은 sandbox로 Git 메타데이터 쓰기도 검사한다.
`workspace-write`는 일반 소스 쓰기를 허용하면서 `.git`을 보호할 수 있다. 이 경우 승인된
소유 fixture의 `.git`만 추가 writable root로 지정하고, 그 안의 임시 파일 생성·삭제가
통과하는지 확인한다. 파일 시스템 전체 권한을 열거나 실제 저장소 권한을 바꾸지 않는다.
검수용 workspace·역할 trust·Git 쓰기·QA lifecycle을 먼저 갖춘 뒤 스킬 동작을 판정한다.

`docs/dev-cycle/evidence/2026-09-06-dev-workflow-runtime.json` 은 이 결과를 담는다.
실제 자식의 `agentRole` 과 `source.subAgent.thread_spawn.agent_role` 이 모두
`dev-workflow` 이며, `parentThreadId` 는 검증 부모의 ID와 일치한다. 자식 경로는
`/root/dedicated_runtime_smoke` 이다. 부모와 자식 모두 `ephemeral: true` 이고,
완료한 자식의 메시지가 원본의 세 제약을 반환했다. 이 값들을 검사해 통과했으므로
일반 에이전트의 자기 보고를 전용 역할 실행의 근거로 대체하지 않았다.

`plugin-creator` 의 스키마와 검증기도 함께 검토했다. 플러그인 manifest 검증과 스킬의
`agents/openai.yaml` 메타데이터 검증은 네이티브 `agent_type` 호출 검증을 대신하지 않는다.
이번에는 기존 정의의 전용 호출이 성공했으므로 플러그인·마켓플레이스를 추가하지 않았다.

기존 작업의 오래된 역할 목록을 제자리에서 갱신한 것으로 보고하지 않는다. 새 역할을
일상적으로 사용할 때도 그 정의가 존재하는 상태에서 시작한 실행 문맥을 사용한다.

## 9. 조건부 내부 스킬까지 대조한 설치 보완

2026-09-06 후속 전체 대조에서 §3의 초기 목록이 프론트엔드 참조 문서의 조건부 스킬을
빠뜨린 것을 확인했다. `next-partial-prefetching-adoption` 은 Codex 설치 경로와 현재
목록에 없었다. `skill-installer` 로 공식 `vercel/next.js` 저장소의 `canary` 브랜치에서
`skills/next-partial-prefetching-adoption` 을 설치했다. 설치 위치는
`$CODEX_HOME/skills/next-partial-prefetching-adoption` 이며 기존 스킬은 덮어쓰지 않았다.

설치 후 스킬 형식 검사가 통과했고, App 내장 CLI의 로컬 `skills/list` 를
`forceReload: true` 로 실행해 새 스킬을 `enabled: true` 로 확인했다. 새로 설치한 스킬은
다음 대화 턴에서 사용할 수 있다. 기본 스킬과 조건부 로컬 스킬 13개는 같은 스캐너에서
활성 상태를 확인했다. `next-upgrade` 는 이 로컬 응답에 포함되지 않으므로, 현재 App의
`vercel:next-upgrade` 항목과 Vercel 플러그인 활성 설정·실제 파일을 별도로 확인했다.

이로써 §3의 기본·조건부 스킬 설치 목록을 모두 대조했다. Claude Code 전용
`ponytail-review` 는 기존처럼 `code-reviewer` 와 정본의 ponytail 기준으로 대체한다.
QA·리뷰·업그레이드·캐시 도입을 전부 실행했다는 뜻은 아니다. 특히 새로 설치한 Partial
Prefetching 스킬은 Cache Components 도입과 통과한 빌드를 먼저 요구하며, 이번 작업에서
그 기능을 켜지 않았다. 프로젝트의 설치 버전은 Next.js 16.3.4·React 19.2.4로 확인했다.


## 10. 개발 라운드 설계와 UltraQA

2026-09-06 승인된 후속 변경부터 새 TODO 라운드는 `superpowers:brainstorming` 설계와
해당 경로의 승인을 거친다. 이미 승인된 동일 범위의 재개와 QA 재시도는 새 라운드가 아니다.
상태 조회와 `dev-workflow` 감사는 읽기 전용이다. 과거 §7~§9의 설치 기록은 당시 증거이며
현재 실행 도구 선택은 §3과 사이클 스킬의 실행 환경 표를 따른다.

Codex QA는 시나리오 계획부터 실행·진단·수정·정리까지 `$ultraqa`를 사용한다.
`.claude/skills/dev-cycle/references/ultraqa.md`가 현재 입력·행렬·한도·보고·App 대응을
정한다. Claude Code의 기존 도구 매핑과 이미 저장한 QA 이력은 보존한다.

현재 App의 writable scope 사전 확인은 `session.json is present but unusable`을
반환했다. 원본 session.json과 hook 상태를 생성·수정·교체·삭제·이동·권한 변경하거나 다른 세션 ID를
지정하지 않고 App 대응 모드로 QA 문서에
진행 상태를 기록한다. 이는 네이티브 OMX 상태 관리 성공을 주장하는 방식이 아니다.
정상 OMX 문맥에서는 스킬의 CLI 수명주기를 사용한다.

필수 실패·차단·미실행·정리 미완료는 완료가 아니다. 구현 커밋에서도 TODO를 유지하고,
필수 검증과 정리의 통과를 확인한 최종 아카이브 커밋에서만 항목을 제거한다. 이전 기록의
`실패 → 이월`은 소급 수정하지 않는다.

초기 중단 기록은 `docs/dev-cycle/qa/INFRA-033.md`, 원인 수리와 재검수는
`docs/dev-cycle/qa/INFRA-033-recheck.md`에 남긴다. 설치 목록 확인이나
성공 문구만으로 업무 처리 성공을 주장하지 않고, 격리 fixture의 명령 종료 코드·파일 변경·
TODO·아카이브·런타임 역할 메타데이터를 검사한다. 새 플러그인 패키지를 만들지 않았으므로
검증 대상은 실제 등록된 프로젝트 스킬과 전용 네이티브 역할이다.

## 11. 2026-09-08 보안 리뷰 내부 호출 수리

사용자의 설치 점검·조치 요청으로 기본·조건부 스킬과 실제 역할을 대조했다. 스킬 파일과
현재 목록은 갖춰졌지만, 별도로 남아 있던 `~/.agents/skills/security-review/SKILL.md`가
호출하는 `security-reviewer` 역할은 없었다. 설치된 OMX의
`templates/catalog-manifest.json`은 이 역할을 `deprecated`, `code-reviewer`를 `active`로
분류하며, native 설치기는 active/internal 역할만 설치한다. 단순 설치 누락으로 보았던
초기 설명을 정정한다. 홈에 예전 역할 프롬프트가 남아 있는 것은 native 역할 등록이 아니다.

로컬 보안 스킬을 백업하고 위임 대상을 `code-reviewer`로 수정했다. OWASP·시크릿·입력·인증·
의존성·심각도 판정 기준은 유지한다. 리더가 보안 범위의 독립 reviewer를 호출하고,
이미 지정된 reviewer는 재위임하지 않는다. 사용할 수 없는 역할을 통과로 대체하지 않으며,
폐지된 Swarm·Ralph 실행 안내와 존재를 가정한 외부 도구 호출도 제거했다. 이 변경은
사용자 승인으로 보완한 로컬 스킬이며 OMX 상류 패키지를 수정한 것은 아니다.

- 백업: `~/.codex/backups/security-review-20260908/SKILL.md.before`
- 수정 위치: `~/.agents/skills/security-review/SKILL.md`
- 재현용 차이와 해시: [검증 기록](evidence/security-review-20260908/verification.json),
  [스킬 변경](evidence/security-review-20260908/skill.patch.gz)
- 스킬 형식 검사 통과. 실제 `agent_type: "code-reviewer"` 호출
  `/root/security_review_verified`의 완료 결과에서 의도적으로 넣은 계정 소유권 검증 누락을
  발견하고 검사하지 않은 영역을 구분했다. [결과](evidence/security-review-20260908/reviewer.md)
- 첫 검증용 executor는 leaf 제한 때문에 하위 위임을 거부했다. 이를 호출 성공으로 세지 않고,
  리더가 직접 독립 reviewer를 호출해 검증했다. 폐지된 역할을 새로 설치하거나 호출한 것이 아니다.
- 검증용 코드는 실행하지 않았고 운영 HTTP·외부 네트워크·실제 자격 증명을 사용하지 않았다.
  임시 fixture는 제거했으며, 기존 루트 `package.json`은 해시가 동일하다.

이번 검증은 스킬의 실제 역할 위임과 보안 결과 반환을 확인한 것이다. 애플리케이션 전체 QA나
UltraQA 실행을 대신하지 않는다. 티어 판정·설계 승인·UltraQA 완료 조건은 바뀌지 않았고,
TODO의 81개 항목(P1 29, P2 52)은 그대로 유지한다. INFRA-063은 아직 설계 승인 대기다.
이 기기 외의 설치 또는 이후 스킬 업데이트 때에는 위임 대상과 현재 역할 목록을 다시 대조한다.

## 12. 브라우저 실측 누락 보완

2026-09-08 사용자 요청으로 Codex QA 연결을 다시 검토했다. 기존 tier-rules는 화면 코드가
바뀌는 경우를 중심으로 브라우저를 요구했고, browser-notes는 Codex UltraQA에 browse를
연결했다. 그 결과 INFRA-062/063은 기존 화면과 연결된 API 변경인데도 “UI 수정 없음”을
근거로 HTTP 하네스만 실행했다. 당시 보고서는 브라우저 실측을 하지 않았다고 명시했으며
그 기록을 소급해 브라우저 통과로 바꾸지 않는다.

현재 정본은 ultraqa.md §1-1이다. dev-workflow는 UI 호출부와 실측 시나리오를 초안에 적고,
dev-cycle의 UltraQA가 agent-browser로 실제 웹 행을 실행한다. backend-only도 기존 화면과
연결되면 필수다. UI 없는 CLI/배치만 근거 있는 제외를 허용하며, 도구/안전 표면이 없으면
필수 실측은 BLOCKED다. 설치된 agent-browser의 사용법은 `agent-browser skills get core`로
읽는다. 전용 세션·격리 URL을 사용하고 기존 로그인 세션이나 원본 서비스로 자동 접속하지 않는다.

이번 보완의 실제 검증 결과는 `docs/dev-cycle/qa/browser-measurement-workflow-2026-09-08.md`에
남긴다. 스킬 파일 설치 여부나 HTTP 성공만으로 브라우저 검증이 끝났다고 보고하지 않는다.

## 13. 2026-09-22 프로젝트 스킬 셋과 고정 vendor 스킬

`docs/reference/skill-set`(Shopping Pilot 에 적용한 agent-kit 기록. `docs/*` 가 `.gitignore` 에 있어
이 기기에만 있는 참고 사본이다)을 본떠 이 저장소에 맞는 스킬 셋을 두었다. 설계 근거와 파일 목록은 `vendor/skills/README.md` 와 `CLAUDE.md` 의
「개발 사이클」 문서 목록에 있다.

| 종류 | 위치 | codex 에서 |
|---|---|---|
| 프로젝트 스킬 3개 | `.claude/skills/closing-bet-{nextjs,python,verify}/` (정본) | `.agents/skills/closing-bet-*` 링크로 발견되어 `$closing-bet-nextjs` 처럼 부른다 |
| 고정 vendor 스킬 4개 | `vendor/skills/{next-dev-loop,vercel-react-best-practices,vercel-composition-patterns,web-design-guidelines}/` | 카탈로그에 넣지 않는다. 프로젝트 스킬이 이 경로를 직접 읽는다 |
| 읽기 전용 리뷰 역할 | `.claude/agents/closing-bet-reviewer.md` (정본), `.codex/agents/closing-bet-reviewer.toml` | §2 의 `dev-workflow` 와 같은 방식. `agent_type: "closing-bet-reviewer"` |

vendor 사본을 카탈로그 밖에 두는 이유는 두 호스트 모두 같은 이름의 사본이 둘이면 문제가 나기
때문이다. Claude Code 는 개인 스킬을 프로젝트 스킬보다 우선하고, Codex 는 레퍼런스 기록
(`docs/reference/skill-set/docs/agent-environment/SPEC.md` §4.3·§4.4)에서 같은 이름의 추가
사본을 거부했으며 프로젝트 `config.toml` 의 `skills.config` 비활성 규칙도 적용하지 않았다.
그래서 이 저장소는 전역 `~/.agents/skills/` 사본을 그대로 두고 비활성 규칙도 만들지 않는다.
전역 카탈로그의 `$vercel-react-best-practices` 등은 §4 의 대조 기록대로 계속 보이지만, 이
저장소의 작업에서는 프로젝트 스킬이 지시하는 `vendor/skills/` 경로를 읽는다.

기기마다 확인할 것은 셋이다.

1. `/skills` 목록에 `closing-bet-nextjs`·`closing-bet-python`·`closing-bet-verify` 가 보인다.
   보이지 않으면 `.agents/skills/` 의 링크 셋이 `../../.claude/skills/<이름>` 을 가리키는지
   `ls -la .agents/skills` 로 본다. 링크는 커밋되어 있으므로 clone 이 정상이면 있다.
2. `python3 scripts/skill_set_lock.py` 가 종료 코드 0 이다. pytest 전체에도 들어 있다.
3. `closing-bet-reviewer` 전용 호출은 §8 과 같은 방식으로 새 실행 문맥에서 확인한다.
   설치 검증으로 「제약 목록만」을 요청하면 그 역할은 「하지 않을 일」 목록만 돌려준다.

같은 날 Claude Code 의 코드 리뷰 자리(T2 이상)를 `feature-dev:code-reviewer` 에서 이 역할로
바꿨다(`SKILL.md` `## 실행 환경`, `tier-rules.md` §1). 플러그인 설치와 무관하게 어느 기기에서든
같은 검토 기준이 적용되게 하려는 것이다. Codex 열은 전용 호출이 확인될 때까지 `$code-review`
그대로이며, 확인되면 표의 Codex 열을 `agent_type: "closing-bet-reviewer"` 로 바꾼다.

이 절을 적은 세션은 Claude Code 였다. 세 스킬이 Claude Code 카탈로그에 뜨는 것과 pytest 통과,
읽기 전용 smoke 는 확인했고(`docs/dev-cycle/evidence/skill-set-20260922/`), Codex 의 실제
발견·전용 호출은 이 세션에서 확인하지 않았다. 다음 Codex 세션에서 위 셋을 확인하고 결과를
이 절에 덧붙인다.
