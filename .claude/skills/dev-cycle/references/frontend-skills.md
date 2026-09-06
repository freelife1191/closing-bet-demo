# 프론트엔드 스킬 매핑

`frontend/` 아래를 건드리는 항목에서만 읽는다. 파이썬만 바꾸는 항목은 이 파일과 무관하다.

## 1. 현재 전제

스킬을 고르는 문턱을 판정하는 값만 적는다. 파일 개수처럼 사이클마다 달라지는 값은 적지
않는다. 손으로 갱신하는 수치는 반드시 낡고, 낡은 표는 판정을 어긋나게 만든다.
`[INFRA-010]` 이 2026-09-02 에 갱신한 파일 개수가 이틀 만에 어긋나 있던 것이 근거다.

| 항목 | 값 | 다시 확인하는 방법 |
|---|---|---|
| Next.js | 16.3.4 | `node -e "console.log(require('next/package.json').version)"` |
| React | 19.2.4 | `node -e "console.log(require('react/package.json').version)"` |
| 라우터 | App Router, 루트는 `frontend/src/app` | — |
| Cache Components | 미적용 | `grep cacheComponents frontend/next.config.js` |

**16.3 문턱은 2026-09-02 에 열렸다.** §2 의 도입형 세 스킬과 §3 의 `next-dev-loop` 은
16.3 미만에서 실행을 거부하도록 만들어져 있었고, `[FE-002]` 가 16.1.6 을 16.3.4 로 올려
그 조건을 해소했다. `/_next/mcp` 가 `tools/list` 에 200 으로 응답하는 것까지 확인했으므로
문턱은 버전 문자열이 아니라 실제 동작으로 열려 있다.

## 2. 언제 무엇을 쓰는가

고르는 자리는 `SKILL.md` [1] 계획의 1번이다. 건드릴 파일 목록을 뽑는 자리이므로 아래
판정에 필요한 것을 그 자리에서 이미 보고 있다.

### 기본으로 읽는 것

`frontend/src/app` 아래 파일을 하나라도 고치면 예외 없이
`frontend/node_modules/next/dist/docs/01-app/` 아래에서 이번에 건드리는 주제의 문서를
읽는다. 조건을 따로 판정하지 않는다. App Router 의 파일 규약과 서버·클라이언트 경계,
비동기 API, 데이터 페칭 패턴이 여기에 있고 이 저장소의 화면 코드는 전부 그 규약 위에
있기 때문이다.

**이 자리에 종전에는 `next-best-practices` 스킬을 적어 두었으나 그 스킬은 폐지되었다.**
Vercel 이 2026 년에 `vercel-labs/next-skills` 를 접으면서 참고 지식에 해당하는 세 스킬을
없앴고, 그 내용을 Next.js 패키지에 번들되는 문서로 옮겼다. 그쪽 README 의 문구는
「`next-best-practices` is no longer a skill … No separate install」이다. 설치할 대상이
없으므로 대체 경로를 규정에 직접 적는다. 판정 근거는 §4 에 있다.

번들 문서는 설치된 Next.js 와 버전이 함께 움직인다는 점에서 스킬보다 낫다. 별도 저장소에
있던 시절에는 프레임워크가 올라가도 스킬이 그대로 남아 어긋났다. `next dev` 가 만들어 두는
`frontend/AGENTS.md` 도 같은 경로를 가리킨다.

어느 파일을 열지는 이번에 건드리는 것으로 고른다. 전부 읽지 않는다.

| 이번 사이클에서 건드리는 것 | 읽을 문서 (`01-app/01-getting-started/` 기준) |
|---|---|
| `'use client'` 경계, 서버 컴포넌트를 프롭으로 넘기는 구조 | `05-server-and-client-components.md` |
| 데이터 조회와 `fetch`, 서버 액션 | `06-fetching-data.md`, `07-mutating-data.md` |
| 캐시와 재검증 | `08-caching.md`, `09-revalidating.md` |
| 라우트 파일 배치, `layout` 과 `page` | `02-project-structure.md`, `03-layouts-and-pages.md` |
| 오류 경계와 `error.tsx` | `10-error-handling.md` |
| 라우트 핸들러 (`app/api/`) | `15-route-handlers.md` |

「항상 해당한다」는 사실이 오히려 이 줄을 건너뛰게 만든다. 판정할 것이 없으면 자문할
계기도 없기 때문이다. 그래서 `SKILL.md` [1] 계획의 4번이 이번에 읽은 것을 사용자에게
보고하도록 정해 두었다. 프론트엔드를 건드리는 사이클의 보고에 문서 이름이 없으면 건너뛴
것이고, 보고가 곧 점검이 된다.

### 건드리는 파일의 내용으로 고르는 것

| 이런 코드를 고치면 | 스킬 |
|---|---|
| 프롭이 여덟 개를 넘거나 불리언 프롭이 셋을 넘는 컴포넌트. 또는 같은 UI 를 두 곳 이상에서 쓰려고 경계를 다시 그을 때 | `vercel-composition-patterns` |
| `useEffect` 나 `useMemo` 로 렌더링을 제어하는 코드, 폴링·구독·타이머, `dynamic()` 이나 번들 분할 | `vercel-react-best-practices` |
| `frontend/package.json` 의 `next` 또는 `react` 버전 | `next-upgrade` (아래 각주) |

Claude Code의 `next-upgrade` 는 상류에서 폐지되었으나 2026-09-01 에 받아 둔 사본이
`~/.claude/skills/next-upgrade/` 에 남아 있어 지금도 동작하므로 그대로 쓴다. 갱신되지
않는다는 것만 알아 둔다. 상류가 대신 권하는 것은 `npx @next/codemod@latest upgrade` 이고,
마이그레이션 안내는 번들 문서의 `01-app/01-getting-started/18-upgrading.md` 에 있다.
Codex에서는 현재 활성 Vercel 플러그인이 제공하는 `$vercel:next-upgrade` 를 쓴다.

앞의 두 줄을 「구조를 손볼 때」나 「성능을 손볼 때」처럼 의도로 적지 않은 이유가 있다.
의도는 사이클 도중에 판정할 계기가 없어서 매번 지나친다. 반면 파일에 무엇이 들어 있는지는
계획에서 파일 목록을 뽑을 때 이미 보게 되므로 같은 자리에서 판정된다.


### 도입형 세 스킬

`next-cache-components-adoption`, `next-cache-components-optimizer`,
`next-partial-prefetching-adoption` 은 위 표와 성격이 다르다. 사이클에 끼워 넣는 것이
아니라 그 자체가 여러 사이클에 걸치는 작업이다. 다음 세 조건을 모두 갖췄을 때만 꺼낸다.

1. 실제로 느린 화면이 관찰되었다. 문턱이 열렸다는 이유만으로 착수하지 않는다
2. `TODO.md` 에 항목을 먼저 만들었다. 다른 항목을 진행하다 곁다리로 도입하지 않는다
3. 그 항목의 티어를 `T3` 으로 판정했다. 셋 모두 여러 PR 에 걸치는 분량이다

`use cache` 와 `cacheLife` 와 `cacheTag` 의 표기가 필요하면 번들 문서의
`01-app/01-getting-started/08-caching.md` 와 `09-revalidating.md` 를 연다. 종전에 이 자리에
적혀 있던 `next-cache-components` 스킬은 위 세 스킬로 쪼개지면서 없어졌다.

## 3. 검증 단계에서의 자리

`tier-rules.md` §1 의 검증 열은 세 티어 모두에 QA 2단계(`/qa-only` 로 시나리오를 구성하고
`/qa` 로 실행)를 요구하고, 화면이 바뀌는 `T2` 와 `T3` 에서는 브라우저로 값을 대조하도록
한다. `frontend/` 를 건드리는 항목에서는 그 대조를 두 관점으로 나눈다.

1. **브라우저 관점** — 화면이 실제로 무엇을 그리는지 읽는다. `next-dev-loop` 이 이 관점을
   agent-browser 로 다루며, agent-browser 를 직접 써도 같은 것을 본다. 직접 쓸 때의
   요령은 `browser-notes.md` 에 있다.
2. **프레임워크 관점** — Next.js 가 컴파일과 런타임에서 무엇을 보고 있는지 읽는다.
   `next-dev-loop` 이 `/_next/mcp` 로 다룬다. 스킬을 부르지 않고 직접 확인하려면 아래
   두 가지를 호출한다. 응답이 SSE 이므로 `data:` 줄만 뽑아 읽는다.

        curl -sN -X POST http://localhost:3500/_next/mcp \
          -H 'Content-Type: application/json' \
          -H 'Accept: application/json, text/event-stream' \
          -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_compilation_issues","arguments":{}}}' \
          | sed -n 's/^data: //p'

   `get_compilation_issues` 는 Turbopack 의 컴파일 오류를 돌려주고, 이름만 `get_errors`
   로 바꾸면 런타임 오류를 돌려준다. 뒤의 것은 브라우저가 그 화면을 한 번 이상 열어야
   값이 찬다.

**두 관점을 모두 확인했으면 어느 방법으로 했든 이 절을 만족한다.** 기준은 스킬 이름이
아니라 확인한 내용이다. 종전에는 「`next-dev-loop` 으로 실측한다」고만 적었는데 47개
사이클 가운데 그 스킬이 기록된 것은 한 건뿐이었고, 나머지는 프레임워크 관점을 통째로
빠뜨린 채 넘어갔다.

- 두 관점에서 읽은 값이 곧 시나리오의 기대값이 된다. 건수와 비율과 배지 문구를 그대로
  `docs/dev-cycle/qa/<ID>.md` 의 `기대` 줄에 옮겨 적으면 같은 값을 두 번 조사하지 않는다.
- QA 2단계는 이것과 별개로 그대로 돌린다. 보는 것이 다르기 때문이다. 이 절은 개발자가
  지목한 화면을 들여다보고, QA 2단계는 사용자의 눈으로 확정한 시나리오를 실행한다.

## 4. 설치 상태

**아래 표의 판정은 Claude Code 환경의 것이다.** 2026-09-06 Codex App 세션에서는
`vercel-react-best-practices` 와 `vercel-composition-patterns` 가 둘 다 같은 이름으로
노출되는 것을 확인했다. codex 에서는 각각 `$vercel-react-best-practices` 와
`$vercel-composition-patterns` 로 부른다. 별도로 보이는 `vercel:react-best-practices` 는
이름이 비슷한 다른 스킬이므로 같은 것으로 간주하지 않는다. 기기별로 현재 스킬 목록을
확인하며 누락 시 `docs/dev-cycle/codex-setup.md` 를 따른다.

Next.js 번들 문서(`frontend/node_modules/next/dist/docs/01-app/`)는 파일이므로 어느
환경에서든 그대로 읽는다. §2 의 「기본으로 읽는 것」이 그 문서를 가리키고 있으므로,
스킬이 없는 환경에서도 판정 근거가 사라지지는 않는다.

Codex의 조건부 스킬도 2026-09-06에 따로 대조했다. `next-dev-loop`,
`next-cache-components-adoption`, `next-cache-components-optimizer` 는 이미 설치되어
있었고, 누락된 `next-partial-prefetching-adoption` 은 공식 `vercel/next.js`의 `canary`
브랜치에서 설치했다. 네 이름 모두 Codex 스캐너가 활성 상태로 인식했다. 설치 경로와
검증 범위는 `docs/dev-cycle/codex-setup.md` §9에 있다. 도입형 스킬의 설치는 §2의
착수 조건이나 각 스킬의 기능 선행 조건을 충족했다는 뜻이 아니다.

Claude Code 쪽 스킬은 `~/.claude/skills/` 에 설치되어 있다. 이 저장소에는 스킬 본문을 두지
않는다. 다음 표는 Claude Code 쪽의 2026-09-05 기록이다. 당시 상류 저장소를 직접
조회해 다음을 확인했다.

| 스킬 | 상태 | 출처 |
|---|---|---|
| `next-dev-loop`, `next-cache-components-adoption`, `next-cache-components-optimizer`, `next-partial-prefetching-adoption` | 설치됨 | `vercel/next.js` canary 의 `skills/` |
| `vercel-composition-patterns`, `vercel-react-best-practices`, `vercel-optimize` 등 | 설치됨 | `vercel-labs/skills` |
| `next-upgrade` | 사본만 남음 | 상류 폐지. 2026-09-01 사본이 동작한다 |
| `next-best-practices`, `next-cache-components` | 폐지 | 설치 대상이 존재하지 않는다 |

**폐지된 셋은 설치할 수 없다.** `vercel-labs/next-skills` 는 스킬 본문 없이 안내문만 남은
저장소가 되었고, 그 README 가 세 스킬을 각각 어디로 보냈는지 적어 두었다.
`next-best-practices` 의 지식은 번들 문서와 `next dev` 가 만드는 `AGENTS.md` 로,
`next-cache-components` 는 `-adoption` 과 `-optimizer` 두 절차 스킬로,
`next-upgrade` 는 번들 문서와 `@next/codemod` 로 갔다. 새 거처인 `vercel/next.js` canary 의
`skills/` 에 있는 것은 위 표 첫 줄의 넷뿐이며 그 넷은 모두 설치되어 있다. 빠진 것이 없다.

이 판정을 다시 확인하려면 다음 두 가지를 본다. 앞의 것은 상류 목록이고 뒤의 것은 여기의
설치 상태다.

    curl -s "https://api.github.com/repos/vercel/next.js/contents/skills?ref=canary" \
      | python3 -c "import json,sys; [print(x['name']) for x in json.load(sys.stdin)]"
    ls ~/.claude/skills/ | grep -E '^(next|vercel)-'

`next-best-practices` 가 되살아나기를 기다릴 필요는 없다. 번들 문서는 설치된 Next.js 와
버전이 함께 움직이므로 별도 저장소에 있던 스킬보다 오히려 어긋나지 않는다. §2 의
「기본으로 읽는 것」이 어느 문서를 열지까지 정해 두었다.
