# 프론트엔드 스킬 매핑

`frontend/` 아래를 건드리는 항목에서만 읽는다. 파이썬만 바꾸는 항목은 이 파일과 무관하다.

## 1. 현재 전제

2026-09-01 실측 결과이며, Next.js 행은 `[FE-002]` 가 끝난 2026-09-02 에 갱신했다.

| 항목 | 값 |
|---|---|
| Next.js | 16.3.4 (2026-09-02 기준 최신) |
| React | 19.2.4 |
| 라우터 | App Router, 루트는 `frontend/src/app` |
| 라우트 | 페이지 6개, API 라우트 1개 |
| 클라이언트 컴포넌트 | 49개 중 26개가 `'use client'` |
| Cache Components | 미적용. `next.config.js` 에 `cacheComponents` 키가 없다 |
| agent-browser | 0.31.1 |

**16.3 문턱은 2026-09-02 에 열렸다.** 아래 표에서 문턱이 붙은 네 스킬은 16.3 미만에서
실행을 거부하도록 만들어져 있었고, `[FE-002]` 가 16.1.6 을 16.3.4 로 올려 그 조건을
해소했다. `/_next/mcp` 가 `tools/list` 에 200 으로 응답하는 것까지 확인했으므로 문턱은
버전 문자열이 아니라 실제 동작으로 열려 있다.

## 2. 언제 무엇을 쓰는가

| 상황 | 스킬 | 문턱 |
|---|---|---|
| `src/app` 아래 코드를 새로 쓰거나 고칠 때 | `next-best-practices` | 없음 |
| 컴포넌트 구조를 손볼 때. 불리언 프롭이 늘어나거나 재사용 경계를 다시 그을 때 | `vercel-composition-patterns` | 없음 |
| 렌더링·번들·데이터 페칭 성능을 손볼 때 | `vercel-react-best-practices` | 없음 |
| Next.js 나 React 버전을 올릴 때 | `next-upgrade` | 없음 |
| 화면 동작을 실측할 때 | `next-dev-loop` | 16.3 이상이고 `next dev` 가 떠 있어야 한다 |
| Cache Components 를 도입할 때 | `next-cache-components-adoption` | 16.3 이상 |
| 특정 라우트의 진입 속도를 끌어올릴 때 | `next-cache-components-optimizer` | 16.3 이상이고 `cacheComponents: true` |
| 링크 프리페치를 개선할 때 | `next-partial-prefetching-adoption` | 위 도입이 끝나 있어야 한다 |

`next-cache-components` 는 절차 스킬이 아니라 문법 참고 문서다. `use cache`, `cacheLife`,
`cacheTag` 의 표기가 필요할 때만 연다.

아래 세 줄은 도입형 스킬을 언제 꺼내는지에 대한 기준이다.

- 도입형 세 스킬(`-adoption`, `-optimizer`, `-partial-prefetching-`)은 실제로 느린 화면이
  관찰되었을 때 시작한다. 문턱이 열렸다는 이유만으로 착수하지 않는다.
- 착수하기로 했다면 `TODO.md` 에 항목을 먼저 만든다. 다른 항목을 진행하다 곁다리로
  도입하지 않는다.
- 세 스킬은 모두 여러 PR 에 걸치는 분량이므로 `T3` 으로 판정한다.

## 3. 검증 단계에서의 자리

`tier-rules.md` §1 의 검증 열은 세 티어 모두에 `/qa-only` 를 요구하고, 화면이 바뀌는
`T2` 와 `T3` 에서는 agent-browser 로 값을 대조하도록 한다. `frontend/` 를 건드리는
항목에서는 다음 규칙이 그 위에 얹힌다.

- Next.js 가 16.3 이상이면 `next-dev-loop` 으로 실측한다. 이 스킬은 agent-browser 로 보는
  브라우저 쪽 관점과 `/_next/mcp` 로 보는 프레임워크 쪽 관점을 함께 대조하므로,
  agent-browser 단독 실측을 대체한다.
- 16.3 미만이면 종전대로 agent-browser 를 직접 쓴다. 프레임워크 쪽 관점은 얻지 못하므로,
  라우트 렌더링과 관련된 변경이라면 `npm run build` 결과를 함께 확인한다.
- `next-dev-loop` 이 대체하는 것은 agent-browser 쪽 실측이며 `/qa-only` 는 그대로 돌린다.
  두 스킬이 보는 것이 다르기 때문이다. 앞의 것은 개발자가 지목한 화면을 프레임워크와 함께
  들여다보고, 뒤의 것은 사용자의 눈으로 앱을 훑어 무엇이 깨졌는지 리포트를 낸다.

## 4. 설치 상태

전역 스킬 디렉터리 `~/.claude/skills/` 에 설치되어 있다. 이 저장소에는 스킬 본문을 두지
않는다. 출처는 다음과 같다.

| 스킬 | 출처 |
|---|---|
| `next-best-practices`, `next-cache-components`, `next-upgrade` | `vercel-labs/next-skills` |
| `next-dev-loop`, `next-cache-components-adoption`, `next-cache-components-optimizer`, `next-partial-prefetching-adoption` | `vercel/next.js` canary 브랜치의 `skills/` |
| `vercel-composition-patterns`, `vercel-react-best-practices`, `vercel-optimize` 등 | `vercel-labs/skills` |
