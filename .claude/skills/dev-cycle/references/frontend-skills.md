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

`frontend/src/app` 아래 파일을 하나라도 고치면 예외 없이 `next-best-practices` 를 읽는다.
조건을 따로 판정하지 않는다. 이 스킬은 App Router 의 파일 규약과 서버·클라이언트 경계,
비동기 API, 데이터 페칭 패턴을 다루는데 이 저장소의 화면 코드는 전부 그 규약 위에 있다.

「항상 해당한다」는 사실이 오히려 이 줄을 건너뛰게 만든다. 판정할 것이 없으면 자문할
계기도 없기 때문이다. 그래서 `SKILL.md` [1] 계획의 4번이 고른 스킬 이름을 사용자에게
보고하도록 정해 두었다. 프론트엔드를 건드리는 사이클의 보고에 이 이름이 없으면 건너뛴
것이고, 보고가 곧 점검이 된다.

### 건드리는 파일의 내용으로 고르는 것

| 이런 코드를 고치면 | 스킬 |
|---|---|
| 프롭이 여덟 개를 넘거나 불리언 프롭이 셋을 넘는 컴포넌트. 또는 같은 UI 를 두 곳 이상에서 쓰려고 경계를 다시 그을 때 | `vercel-composition-patterns` |
| `useEffect` 나 `useMemo` 로 렌더링을 제어하는 코드, 폴링·구독·타이머, `dynamic()` 이나 번들 분할 | `vercel-react-best-practices` |
| `frontend/package.json` 의 `next` 또는 `react` 버전 | `next-upgrade` |

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

`next-cache-components` 는 절차 스킬이 아니라 문법 참고 문서다. `use cache`, `cacheLife`,
`cacheTag` 의 표기가 필요할 때만 연다.

## 3. 검증 단계에서의 자리

`tier-rules.md` §1 의 검증 열은 세 티어 모두에 QA 2단계(`/qa-only` 로 시나리오를 구성하고
`/qa` 로 실행)를 요구하고, 화면이 바뀌는 `T2` 와 `T3` 에서는 브라우저로 값을 대조하도록
한다. `frontend/` 를 건드리는 항목에서는 그 대조를 두 관점으로 나눈다.

1. **브라우저 관점** — 화면이 실제로 무엇을 그리는지 읽는다. `next-dev-loop` 이 이 관점을
   agent-browser 로 다루며, agent-browser 를 직접 써도 같은 것을 본다.
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

전역 스킬 디렉터리 `~/.claude/skills/` 에 설치되어 있다. 이 저장소에는 스킬 본문을 두지
않는다. 출처는 다음과 같다.

| 스킬 | 출처 |
|---|---|
| `next-best-practices`, `next-cache-components`, `next-upgrade` | `vercel-labs/next-skills` |
| `next-dev-loop`, `next-cache-components-adoption`, `next-cache-components-optimizer`, `next-partial-prefetching-adoption` | `vercel/next.js` canary 브랜치의 `skills/` |
| `vercel-composition-patterns`, `vercel-react-best-practices`, `vercel-optimize` 등 | `vercel-labs/skills` |
