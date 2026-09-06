# codex 작업 환경 구성 프롬프트

이 파일은 codex 에 넘기는 프롬프트다. 저장소 루트에서 codex 를 열고 「`docs/dev-cycle/codex-setup.md`
를 읽고 그대로 수행해」라고 하거나 아래 본문을 그대로 붙여 넣는다. 기기마다 한 번 실행하면
되고, 저장소에 남는 결과물은 커밋되므로 두 번째 기기부터는 홈 디렉터리 쪽만 채우면 된다.

여기 적힌 경로와 명령은 2026-09-06 에 codex-cli 0.153.0 과 oh-my-codex 0.20.3 으로 실측한
것이다. 실제와 다른 것을 만나면 그 자리에서 이 문서를 고쳐 같은 커밋에 담는다.

---

## 목표

이 저장소를 codex 로 열었을 때 Claude Code 에서 쓰던 것과 같은 이름으로 개발 사이클과
카테고리 감사를 부를 수 있게 한다. 구체적으로 다음 넷이다.

1. `$dev-cycle` 로 `.claude/skills/dev-cycle/SKILL.md` 의 절차가 돈다.
2. `spawn_agent` 의 `agent_type` 에 `dev-workflow` 가 있고, 그것이
   `.claude/agents/dev-workflow.md` 의 역할 정의를 따른다.
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
- 설치가 끝나기 전에 사이클을 시작하지 않는다. 사이클은 사용자가 `$dev-cycle next` 로
  시작한다.
- 마지막 보고에 무엇을 확인했고 무엇을 새로 설치했는지 적는다. 확인하지 못한 것은
  했다고 적지 않는다.

## 0. 환경 확인

```bash
echo "${CODEX_HOME:-$HOME/.codex}"   # 스킬 홈. orca 가 관리하는 계정이면 ~/.codex 가 아니다
omx doctor && omx list | head -3      # oh-my-codex
git status --short                    # 비어 있어야 한다
```

codex 는 스킬을 네 곳에서 읽는다. `$CODEX_HOME/skills`, `~/.agents/skills`, 설치된
플러그인, 그리고 **저장소의 `.agents/skills`** 다. 에이전트 정의는
`$CODEX_HOME/agents/*.toml` 과 **저장소의 `.codex/agents/*.toml`** 에서 읽는다. 저장소 안에
둔 것은 커밋되므로 기기마다 설치할 필요가 없다. 이 두 사실은 2026-09-06 에 저장소 안에
링크와 정의를 두고 codex 에 목록을 물어 확인했다.

omx 가 없으면 설치한다. 사용자 홈에 `code-review`, `plan`, `ai-slop-cleaner` 등의 스킬과
`code-reviewer`, `architect`, `critic` 등의 에이전트가 생긴다.

```bash
npm install -g oh-my-codex && omx setup --scope user
```

## 1. dev-cycle 스킬 (저장소에 커밋)

```bash
mkdir -p .agents/skills
ln -s ../../.claude/skills/dev-cycle .agents/skills/dev-cycle
test -f .agents/skills/dev-cycle/SKILL.md && echo ok
```

호출 이름은 디렉터리가 아니라 `SKILL.md` frontmatter 의 `name: dev-cycle` 이 정한다. 링크라서
원본을 고치면 그대로 반영된다. 확인은 `/skills` 목록에 `dev-cycle` 이 저장소 출처로 보이는
것으로 한다.

## 2. dev-workflow 에이전트 (저장소에 커밋)

`.codex/agents/dev-workflow.toml` 을 아래 내용 그대로 만든다.

```toml
# codex 용 dev-workflow 에이전트. 역할 정의의 원본은 .claude/agents/dev-workflow.md 이며
# 여기에는 그것을 가리키는 지시만 둔다.
name = "dev-workflow"
description = "이 저장소의 한 기능 카테고리를 감사해 개선 항목 초안을 산출한다. 코드를 수정하지 않고 읽기만 한다. 카테고리 이름(챗봇, 종가베팅, VCP, 수급·백테스트, 프론트엔드, 인프라) 하나를 입력받는다."
sandbox_mode = "read-only"
developer_instructions = """
작업 디렉터리의 `.claude/agents/dev-workflow.md` 를 먼저 읽고 그 본문을 역할 정의로 따른다.
그 파일의 「하지 않을 일」이 이 에이전트의 제약이다. 코드를 고치지 않는다.
받은 프롬프트에서 카테고리 이름 하나를 찾아 그 카테고리만 감사한다.
"""
```

`model` 을 적지 않으면 `$CODEX_HOME/config.toml` 의 `[agents]` 절에 있는
`default_subagent_model` 을 쓴다. 필요해지면 그때 더한다. 확인은 `spawn_agent` 도구의
`agent_type` 목록에 `dev-workflow` 가 있는 것으로 한다.

## 3. 내부 스킬 (기기마다 확인)

사이클과 감사가 부르는 것의 전체 목록이다. 「확인」 열의 방법으로 하나씩 보고, 없는 것만
「없을 때」 열대로 설치한다.

| 사이클이 부르는 것 | Claude Code | codex 에서 부를 이름 | 확인 | 없을 때 |
|---|---|---|---|---|
| 시나리오 구성 | `/qa-only` | `$qa-only` | `/skills` 에 `qa-only`. 디렉터리는 `gstack-qa-only` 지만 `name` 이 `qa-only` 다 | gstack 설치 (아래) |
| 시나리오 실행 | `/qa` | `$qa` | `/skills` 에 `qa` | gstack 설치 |
| 심층 리뷰 (T3) | `/review` | `$review` | `/skills` 에 `review` | gstack 설치 |
| browse 바이너리 | `/qa` 와 `/qa-only` 가 내부에서 쓴다 | 같다 | `test -x "${CODEX_HOME:-$HOME/.codex}/skills/gstack/browse/dist/browse"` | gstack 설치가 함께 빌드한다 |
| 브라우저 실측 | agent-browser | 같다. 셸 명령이다 | `which agent-browser` | `npm install -g agent-browser`. 로그인 세션은 기기별이므로 `--session adguard-cft-extension` 이 없으면 사용자에게 알린다 |
| 코드 리뷰 | `feature-dev:code-reviewer` 에이전트 | omx `$code-review` 스킬 | `/skills` 에 `code-review`, `$CODEX_HOME/agents/code-reviewer.toml` | omx 설치 (0번) |
| 과잉설계 리뷰 | `/ponytail-review` | omx `code-reviewer` 에이전트를 `spawn_agent` 로 띄운다. 프롬프트는 아래 「과잉설계 리뷰 프롬프트」 | `$CODEX_HOME/agents/code-reviewer.toml` | omx 설치 |
| 계획 문서 (T3) | `superpowers:writing-plans` | 같다. `~/.agents/skills/superpowers` 로 codex 에도 보인다 | `/skills` 에 `superpowers:writing-plans` | 아래 superpowers 설치. 그래도 없으면 omx `$plan` 으로 대신하고 그 사실을 문서에 적는다 |
| 프론트엔드 스킬 | `vercel-react-best-practices`, `vercel-composition-patterns` | 같다 | `/skills` 에 두 이름 | `npx skills add vercel-labs/agent-skills` 뒤 `~/.agents/skills` 에 두 디렉터리가 생겼는지 본다. 이름이 다르면 `npx skills find react --owner vercel-labs` 로 찾는다 |
| Next.js 번들 문서 | 파일 | 같다 | `ls frontend/node_modules/next/dist/docs/01-app` | `(cd frontend && npm install)` |
| 카테고리 감사 | `dev-workflow` 에이전트 | `spawn_agent` 에 `agent_type: "dev-workflow"` | 2번 | 2번 |

**gstack 설치.** 설치 대상은 `${CODEX_HOME:-~/.codex}/skills` 이고 browse 바이너리를 함께
빌드한다.

```bash
~/.claude/skills/gstack/setup --host codex
# Claude Code 쪽에도 gstack 이 없으면
git clone https://github.com/garrytan/gstack.git ~/gstack && ~/gstack/setup --host codex
```

**superpowers 설치.** codex 는 `~/.agents/skills` 아래 디렉터리를 `<디렉터리>:<스킬>` 이름으로
읽으므로 링크 하나면 `superpowers:writing-plans` 가 보인다.

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

1. `/skills` 목록에 다음이 전부 있다. `dev-cycle`(저장소), `qa`, `qa-only`, `review`,
   `code-review`, `superpowers:writing-plans`, `vercel-react-best-practices`,
   `vercel-composition-patterns`.
2. `$dev-cycle status` 를 부른다. `[S] status` 의 브리핑, 즉 최근 완료 3건과 우선순위별 항목
   수와 진행 중 사이클 여부와 `git status` 가 나오면 된다. 사이클을 시작하지 않는다.
3. `spawn_agent` 로 `agent_type: "dev-workflow"` 를 띄우되 프롬프트는 「정의 파일을 읽고
   「하지 않을 일」 목록만 돌려줘. 감사는 시작하지 마」로 한다. 목록이 돌아오면 정의 파일의
   포인터가 동작하는 것이다.
4. `$qa-only`, `$qa`, `$review` 는 실행하지 않는다. 앱이 떠 있어야 하고 비용이 든다. 존재만
   확인한다.

## 5. 문서 갱신

실측한 결과대로만 고친다. 확인하지 못한 것은 적지 않는다.

- `.claude/skills/dev-cycle/SKILL.md` 의 `## 실행 환경`
  - 표의 codex 열을 3번 표의 「codex 에서 부를 이름」 열과 같게 한다. `$` 표기를 쓴다.
  - 「**codex 에서는 `/dev-cycle` 로 부를 수 없다.**」 문단을 지우고, 저장소의
    `.agents/skills/dev-cycle` 링크로 `$dev-cycle` 로 부른다는 문단으로 바꾼다. codex 가
    스킬을 읽는 네 곳을 적는다.
  - 「**과잉설계 리뷰에 대응하는 스킬이 codex 에 없다.**」 문단을 위의 에이전트 방식으로
    바꾼다. 에이전트를 띄울 수 없을 때 직접 검토한다는 내용은 대체 수단으로 남긴다.
  - 「**codex 는 `CLAUDE.md` 를 자동으로 읽지 않는다.**」 문단은 그대로 둔다.
- `.claude/agents/dev-workflow.md` 의 「이 정의를 부르는 방법」: codex 에서는
  `.codex/agents/dev-workflow.toml` 이 이 파일을 가리키므로 `spawn_agent` 에
  `agent_type: "dev-workflow"` 와 카테고리 이름을 준다고 적는다. 본문을 프롬프트로 복사해
  넘기는 방법은 지운다.
- `AGENTS.md`: 「codex 에서는 `/dev-cycle` 슬래시 호출이 되지 않는다」 문단을 `$dev-cycle`
  로 부른다는 문단으로 바꾸고, `/skills` 에 그 이름이 없으면 이 문서를 수행하라는 한 줄을
  더한다.
- `.claude/skills/dev-cycle/references/tier-rules.md` 의 §1 아래와 `Agent` 도구 문단 앞에
  있는 codex 문단, `references/frontend-skills.md` §4 의 codex 문단을 새 이름에 맞춘다.
  `vercel-composition-patterns` 가 codex 에도 보이므로 「대응하는 것은 없다」를 고친다.
- `CLAUDE.md` 는 고치지 않는다. 「부르는 리뷰·QA 도구의 이름만 다릅니다」가 여전히 맞다.

## 6. 커밋과 보고

커밋은 하나다. `.agents/skills/dev-cycle` 링크, `.codex/agents/dev-workflow.toml`, 고친
문서, 그리고 이 문서를 고쳤다면 그것까지 담는다. 제목은
`docs(dev-cycle): codex 에서 같은 이름으로 사이클과 감사를 부르게 한다` 로 하고, 본문에
무엇을 실측했고 무엇을 새로 설치했는지 적는다. 커밋을 묻지 않는다.

보고는 네 가지다. 확인한 것, 새로 설치한 것, 설치하지 못한 것과 그 이유,
`$dev-cycle status` 의 브리핑. 그다음 멈춘다. 다음 사이클은 사용자가 `$dev-cycle next` 로
시작한다.
