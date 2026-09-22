---
name: closing-bet-nextjs
description: 이 저장소의 Next.js 대시보드(frontend/)를 고치거나 검토할 때 먼저 읽는다. frontend/src/app 의 화면·컴포넌트·훅, lib/api.ts, proxy.ts, next.config.js, scripts/run-next.js, vitest 테스트를 하나라도 건드리면 파일 수와 무관하게 해당한다. 「화면 고쳐줘」「배지 문구 바꿔」「버튼 추가」「모달 손봐」처럼 frontend 나 Next.js 라는 말이 없어도 결과가 브라우저에 보이면 이 스킬이다. App Router 경계, 서명된 신원 헤더, 환경 변수 허용 목록, 고정 vendor 스킬을 경로로 읽는 규칙, 검증 명령을 담는다.
---

# Next.js 경계 (closing-bet-demo)

이 저장소의 화면은 `frontend/src/app` 아래 App Router 위에 있다. Next 16.3.5, React 19.2.8,
Tailwind 3, vitest 4 이며 `next dev`·`build`·`start` 는 `frontend/scripts/run-next.js` 를 거친다.
Cache Components 는 켜져 있지 않다. 값을 다시 확인하는 명령은 `dev-cycle` 의
`references/frontend-skills.md` §1 에 있다.

이 스킬은 `dev-cycle` 을 대체하지 않는다. 작업의 시작·티어·리뷰·QA·마감은 그 절차가 정하고,
이 문서는 화면 코드를 만질 때 지켜야 할 경계와 읽을 자료만 정한다.

## 먼저 읽을 것

1. `CLAUDE.md` 와 `AGENTS.md` 의 「TypeScript / React」「하지 않을 것」「되돌릴 수 없는 조작」.
2. `frontend/node_modules/next/dist/docs/01-app/` 아래에서 이번에 건드리는 주제의 문서.
   `frontend/src/app` 아래 파일을 하나라도 고치면 예외 없이 읽는다. 어느 파일을 열지는
   `frontend-skills.md` §2 의 표가 정한다. 번들 문서는 설치된 Next 와 버전이 함께 움직여서
   별도 저장소의 스킬보다 어긋나지 않는다. 상태·폴링·클릭 핸들러만 바뀌어 표의 여섯 줄
   어디에도 맞지 않는 순수 클라이언트 변경이면 `05-server-and-client-components.md` 를 읽고
   그렇게 판정한 근거를 계획 보고에 적는다. 이 저장소의 화면은 전부 `'use client'` 경계 위에
   있어서 그 문서가 가장 가까운 규약이다. 가장 비슷한 줄을 억지로 고르지 않는다.
3. 고정 vendor 스킬. **전역 카탈로그의 같은 이름을 부르지 말고 아래 경로를 직접 읽는다.**
   Claude Code 는 같은 이름이면 개인 스킬을 프로젝트 스킬보다 우선하므로, 이름으로 부르면
   어느 사본이 읽혔는지 알 수 없다. 이 경로는 커밋에 고정되어 있고 해시는
   `vendor/skills/sources.lock.json` 에 있다.

   | 건드리는 코드 | 읽을 경로 |
   |---|---|
   | `useEffect`·`useMemo` 로 렌더링을 제어하는 코드, 폴링·구독·타이머, `dynamic()`·번들 분할 | `vendor/skills/vercel-react-best-practices/AGENTS.md` 와 해당 `rules/` |
   | 프롭이 여덟 개를 넘거나 불리언 프롭이 셋을 넘는 컴포넌트, 같은 UI 를 두 곳 이상에서 쓰려고 경계를 다시 긋는 일 | `vendor/skills/vercel-composition-patterns/AGENTS.md` 와 해당 `rules/` |
   | 접근성·UI 규칙 검토를 요청받았을 때 | `vendor/skills/web-design-guidelines/SKILL.md`. 규칙 본문을 URL 에서 받아오므로 조회 시각과 원문 해시를 기록하고, 네트워크가 없으면 그 검토를 미실행으로 남긴다 |

   해당 코드가 없으면 읽지 않는다. 판정 근거는 의도가 아니라 파일에 무엇이 들어 있는가다.
   계획에서 파일 목록을 뽑는 자리에서 이미 보고 있기 때문이다.

## 구현 경계

- **API 는 Flask 가 맡는다.** `/api/*` 요청은 `next.config.js` 의 rewrite 가 Flask(5501)로
  중계한다. 라우트 핸들러는 `api/auth/[...nextauth]` 와 `api/system/env` 둘뿐이며, 각각 NextAuth
  와 관리자 설정 저장을 위해 세션을 확인해야 해서 있다. 일반 API 를 라우트 핸들러로 옮기거나
  Flask 의 업무 로직을 Next 로 가져오지 않는다.
- **호출은 `frontend/src/lib/api.ts` 의 `fetchAPI` 를 재사용한다.** 시간 제한과 백엔드 오류 문구
  추출(`message`·`error`)이 거기 한 곳에 있다. 화면마다 사유를 꺼내는 코드를 다시 쓰지 않는다.
  남아 있는 맨 `fetch(` 호출은 기존 코드이며 새 코드에서 늘리지 않는다.
- **신원은 서명된 헤더 하나다.** `frontend/src/proxy.ts` 가 브라우저가 보낸 `x-user-email` 과
  `x-auth-identity` 를 지우고, NextAuth 세션의 이메일을 `INTERNAL_IDENTITY_SECRET` 으로 서명한
  `v2.` 헤더만 Flask 로 넘긴다. 익명 사용자는 `lib/session.ts` 의 `X-Session-Id` 로 센다.
  관리자 여부는 `hooks/useAdmin.ts` 가 `/api/admin/check` 로 묻는다. 클라이언트가 가진 값으로
  신원이나 권한을 판정하는 코드를 만들지 않는다. 「Refresh VCP」처럼 모두에게 보이는 버튼은
  클릭 핸들러가 비관리자를 권한 모달로 막고 서버가 403 으로 거부하는 이중 구조다.
- **환경 변수는 허용 목록을 통과해야 자식 프로세스에 닿는다.** `frontend/scripts/run-next.js` 의
  `APPLICATION_KEYS`·`RUNTIME_KEYS`·`PUBLIC_APPLICATION_KEYS` 밖의 키는 Next 에 전달되지 않는다.
  새 키는 그 목록과 루트 `.env.example` 을 함께 고친다. `NEXT_PUBLIC_` 접두사는 브라우저 번들에
  실리므로 비밀을 그 이름으로 만들지 않는다. `.env` 값은 어디에도 옮겨 적지 않는다.
- **상태를 구분해 그린다.** 로딩, 데이터 없음, 오류, 비관리자를 서로 다른 화면으로 둔다. 결측을
  0 으로 표시하지 않고, 「오늘 데이터가 없음」과 「최신 저장분을 대신 표시함」을 같은 배너로
  합치지 않는다(`[JONGGA-039]`).
- **코드 규칙은 `AGENTS.md` 가 정본이다.** 클라이언트 컴포넌트는 첫 줄 `'use client';`, 임포트는
  React·Next → 외부 → 로컬, 모든 데이터 구조에 인터페이스, Tailwind 유틸리티. `as any`·
  `@ts-ignore`·`@ts-expect-error` 를 쓰지 않는다.
- `frontend/AGENTS.md` 와 `frontend/CLAUDE.md` 는 `next dev` 가 매번 다시 만드는 파일이다.
  지우지 않는다.
- 되돌릴 수 없는 조작 버튼(설정 저장, AI 재분석, Refresh, 챗봇 전송, 모의투자, 삭제)의 목록은
  `AGENTS.md` 에 있다. 원본 3500/5501 이나 live 주소에서 누르지 않는다.

## 검증

정적 검사 세 가지를 서브셸로 돌린다. 감싸지 않으면 셸의 작업 디렉터리가 `frontend/` 에 남아
뒤따르는 명령이 엉뚱한 곳에서 돌고, 저장소 루트에서 `npx vitest` 를 돌리면 루트에
`node_modules/.vite` 가 생긴다.

    (cd frontend && npx vitest run)          # 전체. 변경 범위만은 경로를 붙인다
    (cd frontend && npm run type-check)      # tsc --noEmit. vitest 는 타입 오류를 잡지 못한다
    (cd frontend && npm run lint)            # 기존 경고와 새 경고를 구분해 기록한다

테스트는 대상 파일 옆에 `*.test.tsx` 로 두고, 회귀 검사는 `page.regression-<항목>.test.tsx`
처럼 항목 ID 를 이름에 남긴다. 분기·조건부 렌더링·문구 판정에는 검사 하나를 남기고, 문구
한 줄 변경에는 만들지 않는다.

화면 동작은 격리 환경에서 브라우저 관점과 프레임워크 관점(`/_next/mcp`) 두 가지로 읽는다.
환경을 세우는 요령과 증거 기록은 `closing-bet-verify` 스킬에 있다.
`vendor/skills/next-dev-loop/SKILL.md` 는 그 두 관점을 묶은 upstream 절차인데 Next 16.3 이상과
Turbopack, agent-browser 0.31.1 이상을 요구한다. 이 기기의 agent-browser 는 0.31.1 로 하한만
충족한다. 조건을 같은 세션에서 확인했을 때만 그 절차를 쓰고, 아니면 `browser-notes.md` 의
직접 조작으로 같은 두 관점을 확인한다. 어느 쪽이든 확인한 내용이 기준이지 스킬 이름이 아니다.
