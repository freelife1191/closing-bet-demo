# smoke-nextjs — 읽기 전용 smoke 원문 (2026-09-22)

- 도구 호출: {'Read': 1, 'Bash': 22, 'ToolSearch': 1, 'SendMessage': 1}
- Read 로 연 파일: .claude/skills/closing-bet-nextjs/SKILL.md
- Bash 명령 (원문, 전부 로컬 읽기 전용이었고 HTTP 요청은 없었다):

    cat .claude/skills/dev-cycle/references/frontend-skills.md

    cat frontend/src/app/dashboard/kr/vcp/page.tsx

    grep -n "Refresh VCP\|refreshVcp\|handleRefresh\|updateVcpSignal\|vcp.*refresh\|Refresh" frontend/src/app/dashboard/kr/vcp/page.tsx -i | head -60

    sed -n '1470,1540p' frontend/src/app/dashboard/kr/vcp/page.tsx

    sed -n '1400,1470p' frontend/src/app/dashboard/kr/vcp/page.tsx

    echo "--- useAdmin hook ---" && cat frontend/src/hooks/useAdmin.ts 2>/dev/null; echo "--- grep isAdmin in page.tsx ---" && grep -n "isAdmin\b" frontend/src/app/dashboard/kr/vcp/page.tsx | head -20

    grep -n "runVCPScreener\|getVCPStatus\b" frontend/src/lib/api.ts

    sed -n '1,80p' frontend/src/lib/api.ts

    sed -n '220,270p' frontend/src/lib/api.ts

    cat frontend/src/proxy.ts

    find frontend/src -iname "*vcp*test*" -o -iname "*VCP*.test.*" | sort

    grep -l "runVCPScreener\|Refresh VCP\|screenerRunning\|permissionModal" frontend/src/app/dashboard/kr/vcp/page.regression-vcp-*.test.tsx frontend/src/app/dashboard/kr/page.regression-vcp-026.test.tsx 2>/dev/null

    sed -n '1,60p' frontend/src/app/dashboard/kr/vcp/page.regression-vcp-002.test.tsx

    grep -n "하지 않을 것\|되돌릴 수 없는\|Refresh\|되돌릴" AGENTS.md | head -30

    grep -n "checkRunningStatus\|useEffect" frontend/src/app/dashboard/kr/vcp/page.tsx | head -40

    sed -n '150,215p' AGENTS.md

    sed -n '640,720p' frontend/src/app/dashboard/kr/vcp/page.tsx

    find frontend/src/app/api -name "route.ts" | sort
    echo "---"
    ls vendor/skills/
    echo "---"
    cat vendor/skills/sources.lock.json 2>/dev/null | head -40
    echo "---next.config.js rewrite check---"
    grep -n "rewrite\|cacheComponents" frontend/next.config.js

    grep -n "cacheComponents" frontend/next.config.js
    node -e "console.log(require('./frontend/node_modules/next/package.json').version)" 2>/dev/null
    node -e "console.log(require('./frontend/node_modules/react/package.json').version)" 2>/dev/null

    grep -rn "signals/run\b" app/routes/*.py 2>/dev/null; grep -rln "def.*signals.*run\|/signals/run" app/ engine/ services/ 2>/dev/null | head

    sed -n '195,235p' app/routes/kr_market_data_signals_routes.py

    which agent-browser 2>/dev/null && agent-browser --version 2>/dev/null; npm ls -g agent-browser 2>/dev/null; npx --no-install agent-browser --version 2>/dev/null; echo "exit:$?"

## 에이전트가 돌려준 보고 원문

closing-bet-nextjs 스킬의 smoke 검증을 마쳤습니다. 파일을 만들거나 고치지 않았고, 어떤 서버에도 요청을 보내지 않았으며, data/ 와 .env 계열 파일은 열지 않았습니다.

(a) 이번 과제에서 읽어야 할 문서

frontend/src/app/dashboard/kr/vcp/page.tsx 는 파일 첫 줄이 'use client' 이고, 버튼 흐름 전체가 useState·setInterval 기반 폴링과 fetch 호출로만 이루어져 있습니다. 서버 컴포넌트를 프롭으로 넘기는 구조나 캐시·재검증, 라우트 파일 배치, error.tsx, app/api/ 라우트 핸들러 가운데 어느 것도 이 흐름에 실제로 걸리지 않았습니다. frontend-skills.md §2 표의 여섯 항목 중 정확히 들어맞는 줄이 없었다는 뜻입니다. 그래서 저는 가장 근접한 근거로 checkRunningStatus 를 부르는 마운트 시점 useEffect(frontend/src/app/dashboard/kr/vcp/page.tsx:656-659)와 그 안의 데이터 재조회(loadSignals, loadMarketGate)를 「데이터 조회와 fetch」 줄에 걸어 06-fetching-data.md 를 판정 근거로 삼았습니다. 다만 이 판정은 표의 취지(서버 컴포넌트의 fetch·서버 액션)를 다소 넓힌 것이라, 스스로도 확신이 높지는 않습니다. 이 점은 아래 (3)에서 모호함으로 다시 짚었습니다.

vendor/skills/ 경로 중에서는 vercel-react-best-practices/AGENTS.md 와 해당 rules/ 를 읽어야 합니다. 판정 근거는 버튼 onClick 안에서 setInterval 로 스크리너 상태를 폴링하는 코드(page.tsx:1431-1503)와, 마운트 시 같은 폴링을 복구하는 useEffect(page.tsx:649-696) 두 곳으로, 스킬이 명시한 「폴링·타이머」 조건에 그대로 해당합니다. vercel-composition-patterns 는 해당 코드가 없어 읽지 않아도 됩니다. 이 흐름에서 프롭 여덟 개를 넘거나 불리언 프롭 셋을 넘는 컴포넌트를 새로 만들거나 고치는 지점이 없었기 때문입니다. web-design-guidelines 는 접근성 검토를 별도로 요청받지 않았으므로 대상이 아닙니다.

(b) 관련 파일과 적용되는 구현 경계

- frontend/src/app/dashboard/kr/vcp/page.tsx:1428-1433 (버튼 onClick) — 「신원은 서명된 헤더 하나다」 항목의 클라이언트 쪽 절반이 적용됩니다. isAdmin 이 거짓이면 권한 모달만 띄우고 곧바로 return 하는 구조입니다.
- frontend/src/hooks/useAdmin.ts — 같은 항목의 근거 훅입니다. `/api/admin/check` 응답만으로 isAdmin 을 정하고, 이메일 값 자체를 요청에 싣지 않는다는 주석(15-16행)이 스킬의 「클라이언트가 가진 값으로 신원이나 권한을 판정하지 않는다」와 정확히 맞습니다.
- frontend/src/lib/api.ts:229-259 (runVCPScreener, getVCPStatus) — 「호출은 fetchAPI 를 재사용한다」가 적용됩니다. 둘 다 fetchAPI 를 감싸고, runVCPScreener 는 409 응답만 한국어 문구로 바꿔 던지는 사유 추출 재사용 패턴을 그대로 따릅니다.
- frontend/src/proxy.ts — 「신원은 서명된 헤더 하나다」의 서버 쪽 절반입니다. 브라우저가 보낸 x-user-email·x-auth-identity 를 지우고, NextAuth 세션 이메일만 v2. 헤더로 서명해 넘깁니다.
- app/routes/kr_market_data_signals_routes.py:207-208 (`@require_admin` 데코레이터가 붙은 `/signals/run`) — Python 코드라 이 스킬의 직접 대상은 아니지만, 「클릭 핸들러가 막고 서버가 403 으로 거부하는 이중 구조」라는 SKILL.md 51행의 주장을 검증하려고 확인했고, 실제로 그렇게 되어 있었습니다.
- frontend/src/app/dashboard/kr/vcp/page.regression-vcp-002.test.tsx — 스크리너 폴링과 관련된 유일한 기존 테스트입니다. 언마운트 뒤에도 폴링 setInterval 이 계속 도는 문제를 다루고 있어, 이번 버튼 흐름을 고치면 회귀 검사 이름 관례(page.regression-<항목>.test.tsx)를 그대로 따라야 합니다.

(c) 검증 명령과 두 관점 확인

정적 검사 세 가지를 frontend 서브셸로 돌립니다.

    (cd frontend && npx vitest run)
    (cd frontend && npm run type-check)
    (cd frontend && npm run lint)

동작 확인은 closing-bet-verify 스킬이 정한 격리 환경에서, 브라우저 관점(agent-browser 로 실제로 그려지는 화면)과 프레임워크 관점(`/_next/mcp` 의 get_compilation_issues·get_errors)을 각각 확인합니다. 이 기기의 agent-browser 버전을 직접 확인했더니 0.31.1 로, SKILL.md 84-85행이 말하는 하한과 정확히 일치해서 next-dev-loop 절차를 그대로 쓸 조건을 충족합니다.

(3) 스킬 본문에서 어긋나거나 모호한 문장

1. .claude/skills/closing-bet-nextjs/SKILL.md:19-22 — 「frontend/src/app 아래 파일을 하나라도 고치면 예외 없이 읽는다」는 절대 규정과, frontend-skills.md §2 표가 여섯 가지 구체 항목으로만 문서를 고르게 한 구조가 서로 어긋날 수 있습니다. 이번처럼 순수 클라이언트 상태·폴링·핸들러만 바뀌는 흐름은 여섯 줄 가운데 어디에도 깔끔하게 들어맞지 않아서, 「예외 없이 읽는다」를 지키려면 가장 가까운 줄을 억지로 골라야 했습니다. 표에 「위 여섯 항목에 해당하지 않으면 판단 근거를 직접 밝히고 생략할 수 있다」같은 예외 조항이 없다는 점이 모호합니다.

나머지 항목은 실제 코드와 대조한 결과 전부 일치했습니다. route 핸들러가 auth 와 system/env 둘뿐이라는 주장(39-40행), Next 16.3.5·React 19.2.8·Cache Components 미적용이라는 수치(8-10행), vendor 잠금 파일과 해시 존재(23-26행), 이중 게이트 주장(51행), agent-browser 0.31.1 하한(84-85행)을 모두 직접 실행이나 파일 대조로 확인했고 어긋난 곳이 없어 2번과 3번 지적은 「없음」입니다.

실제로 읽은 파일: .claude/skills/closing-bet-nextjs/SKILL.md, .claude/skills/dev-cycle/references/frontend-skills.md, frontend/src/app/dashboard/kr/vcp/page.tsx(여러 구간), frontend/src/hooks/useAdmin.ts, frontend/src/lib/api.ts(여러 구간), frontend/src/proxy.ts, frontend/src/app/dashboard/kr/vcp/page.regression-vcp-002.test.tsx, AGENTS.md(150-215행), CLAUDE.md(프로젝트 루트, 시스템 안내로 이미 전달됨), vendor/skills/sources.lock.json(일부), app/routes/kr_market_data_signals_routes.py(195-231행), frontend/next.config.js(grep 으로 rewrite·cacheComponents 줄만 확인). 그 외 frontend/next/package.json·react/package.json 버전과 agent-browser 버전은 명령 실행으로 직접 확인했습니다.
