---
name: closing-bet-verify
description: 이 저장소에서 「됐다」「통과했다」「고쳤다」를 말하기 전에 읽는다. 어떤 검사가 어떤 주장의 증거가 되는지, 원본 3500/5501 을 건드리지 않는 격리 QA 환경을 어떻게 세우는지, 브라우저·프레임워크 두 관점을 어떻게 읽는지, 결과를 docs/dev-cycle/qa/<ID>.md 에 어떻게 남기는지를 담는다. 구현자·리뷰어·QA 서브에이전트가 모두 읽으며, dev-cycle [3] 검증과 tier-rules.md §1-1 을 대체하지 않고 이 저장소에서 실제로 겪은 요령을 더한다. 검증, QA, 실측, 증거, 격리 환경, 하네스라는 말이 나오면 이 스킬이다.
---

# 검증 증거 (closing-bet-demo)

절차의 정본은 `dev-cycle` 의 [3] 검증, `references/tier-rules.md` §1-1(QA 2단계),
`references/archive-format.md` §8(QA 문서 형식), `references/browser-notes.md`(브라우저 조작),
`references/ultraqa.md`(Codex)다. 이 스킬은 그 문서들이 정한 것을 다시 적지 않고, 실행할 때
매번 다시 알아내던 것을 적어 둔다.

## 증거의 등급

주장마다 가장 작은 직접 증거를 고른다. 등급이 다른 증거를 같은 것으로 부르지 않는다.

| 등급 | 무엇 | 무엇의 증거가 되는가 |
|---|---|---|
| 정적 | `pytest`, `(cd frontend && npx vitest run)`, `(cd frontend && npm run type-check)`, lint | 코드가 검사가 정한 계약을 지킨다 |
| 하네스 | 격리 사본에서 가짜 클라이언트·스텁 진입점으로 실제 호출 경로를 태움 | 실패 경로·비용이 드는 경로의 실제 동작. 사용자 진입 흐름이 화면이면 보강 증거일 뿐이며 브라우저 등급을 대신하지 못한다 |
| 프레임워크 | `/_next/mcp` 의 `get_compilation_issues`·`get_errors` | Next 가 컴파일·런타임에서 본 오류 |
| 브라우저 | 격리 Next 의 실제 화면을 조작해 읽은 값·요청·스크린샷 | 사용자가 보는 것 |

실행하지 않은 검사를 통과로 적지 않는다. `skip` 만 있는 로그, 성공 문구 하나, 마지막 명령의
exit 0 으로 앞선 실패를 덮지 않는다. mock 이 통과한 것은 live 증거가 아니고, 화면이 그려진
것은 권한이나 외부 효과의 증거가 아니다. 기존 경고와 새 경고를 구분해 적는다. vitest 를 다른
무거운 명령과 동시에 돌리면 시간 초과로 무더기 실패가 나므로 단독으로 다시 돌려 판정한다.

## 격리 환경

원본 3500/5501, live 주소, 원본 `data/`, 원본 `.env` 를 QA 에 쓰지 않는다. 되돌릴 수 없는
조작 목록은 `AGENTS.md` 에 있고, 격리 사본에서도 비용이 드는 바깥 경계(LLM, 발송)는 대역으로
바꾼다.

- **사본**: scratchpad 에 저장소 전체를 복사한다. `frontend/node_modules` 는 APFS clone
  (`cp -c -R`)으로 두면 빠르다. `data/` 는 사본을 두고 `.env` 는 두지 않는다. 필요한 값만
  더미로 환경 변수에 준다. `NEXTAUTH_SECRET=qa-nextauth-secret`,
  `INTERNAL_IDENTITY_SECRET=qa-identity-secret`, `ADMIN_EMAILS=qa-admin@example.com`,
  `NEXTAUTH_URL=http://localhost:<Next 포트>`, 챗봇 쿼터 가드용
  `GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=qa-stub`. 실제 비밀은 어디에도 적지 않는다.
- **Flask**: 사본 루트에서 `SCHEDULER_ENABLED=false gunicorn <진입점>:app --bind 127.0.0.1:<포트>
  --workers 1 --threads 4`. 진입점은 `flask_app` 이거나, 외부 호출을 바꿔치기한 QA 전용 파일
  (`from flask_app import app` 앞에서 `engine.genai_client.build_genai_client` 나
  `scripts.init_data` 의 단계를 가짜로 바꾼 것)이다. 이 파일은 사본에만 두고 저장소에 넣지 않는다.
- **Next**: 사본 `frontend/` 에서 `PORT=<포트> API_URL=http://127.0.0.1:<Flask 포트> TZ=Asia/Seoul
  npm run dev`. 브라우저는 반드시 `http://localhost:<포트>` 로 연다. 더미 비밀은 `run-next.js`
  허용 목록에 있어 그대로 전달된다.
- **관리자 세션**: 사본 `frontend/` 안에서 `next-auth/jwt` 의 `encode` 로 더미
  `NEXTAUTH_SECRET` 과 같은 값의 토큰을 만들어 쿠키 `next-auth.session-token` 에 넣는다. 그러면
  proxy 가 신원을 서명하고 Flask 의 `require_admin` 이 `ADMIN_EMAILS` 로 통과시킨다. 스크립트를
  `frontend/` 밖에 두면 `next-auth` 가 resolve 되지 않는다.
- **정리**: 띄운 gunicorn·Next·브라우저를 끝내고 토큰 파일을 지운다. 저장소 루트에서 `npx vitest`
  를 돌려 생긴 `node_modules/.vite` 가 있으면 지운다. 저장소에는 그 항목의 파일만 남긴다.

## 두 관점

`frontend/` 를 건드렸거나 기존 화면이 이번에 바꾼 API·인증·자료를 쓰면 두 관점을 모두 읽는다.
어느 도구로 읽었는지가 아니라 두 관점을 다 확인했는지가 기준이다.

브라우저 관점은 Claude Code 에서 gstack `browse`(`goto`, `wait --networkidle`, `snapshot -i`,
`js`, `fill @eN`, `cookie name=value`, `console --clear`, `console --errors`, `network`, `screenshot`,
`stop`), Codex 에서 agent-browser 다. 콘솔 오류를 판정하기 전에 `console --clear` 로 비우고
`goto` 로 다시 연다. 비우지 않으면 HMR 중간 상태의 오류가 현재 코드의 오류처럼 보인다. 조작 전후 snapshot, 기대·실제 화면 값, 관련 요청의 URL·메서드·
상태, 스크린샷 경로, 콘솔 오류 판정을 남기고 스크린샷은 열어서 본다. `snapshot -i` 가 버튼의
ref 를 못 찾으면 `js` 로 문구를 찾아 누른다. 챗봇 화면은 LLM 대역 없이는 아무 버튼도 누르지 않는다.

프레임워크 관점은 격리 Next 에 아래를 보내 `data:` 줄을 읽는다. `get_errors` 는 브라우저가
그 화면을 한 번 이상 열어야 값이 찬다.

    curl -sN -X POST "http://localhost:<포트>/_next/mcp" \
      -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_compilation_issues","arguments":{}}}' \
      | sed -n 's/^data: //p'

두 관점에서 읽은 값이 QA 문서 시나리오의 「기대」 줄이 된다. 같은 값을 두 번 조사하지 않는다.

## 기록

- QA 문서 `docs/dev-cycle/qa/<ID>.md` 의 형식은 `archive-format.md` §8 이다. 메타 열한 가지
  (대상 화면, 구성 근거, 구성·실행 시각, QA 엔진, 단계, 반복, baseline 상태, 필수 여부, 결과,
  증거, 정리)와 시나리오별 조작·기대·실제·결과·증거·정리를 모두 적는다. 기대는 눈으로 대조할 값이지 「정상 동작한다」가 아니다.
- 실행한 정확한 명령, 종료 코드, 검증 기준 커밋, 환경, 경고, 실행하지 못한 검사와 이유를 적는다.
- 어느 정본을 읽었는지 경로로 적는다. 고정 vendor 스킬은 `vendor/skills/<이름>/`, 프로젝트
  스킬은 `.claude/skills/closing-bet-*/`. 이름만 적으면 전역 사본과 구분되지 않는다.
- 서브에이전트는 `Agent` 도구에 `name` 을 주어 띄우고 결과를 기다린다. 회신이 유실되면
  `ListAgents` 로 idle 을 확인한 뒤 `SendMessage` 로 다시 요청하고, 그래도 없으면 세션의
  `subagents/agent-a<name>-*.jsonl` 에서 마지막 assistant 텍스트를 읽는다. 같은 리뷰를 다시
  띄우지 않는다.
- 필수 시나리오가 실패·차단·미실행이거나 정리가 끝나지 않았으면 완료로 적지 않는다. 범위 밖
  발견은 TODO 로 이월하고 현재 필수 시나리오를 범위 밖으로 다시 이름 붙이지 않는다.
