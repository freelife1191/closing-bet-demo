# smoke-verify — 읽기 전용 smoke 원문 (2026-09-22)

- 도구 호출: {'Read': 5, 'Bash': 5, 'ToolSearch': 1, 'SendMessage': 1}
- Read 로 연 파일: .claude/skills/closing-bet-verify/SKILL.md, .claude/skills/dev-cycle/references/archive-format.md, .claude/skills/dev-cycle/references/tier-rules.md, docs/dev-cycle/qa/VCP-031.md, .claude/skills/dev-cycle/references/browser-notes.md
- Bash 명령 (원문, 전부 로컬 읽기 전용이었고 HTTP 요청은 없었다):

    sed -n '1,400p' .claude/skills/dev-cycle/references/archive-format.md | grep -n "^## \|^### "

    grep -n "^## \|^### " .claude/skills/dev-cycle/references/tier-rules.md

    test -f docs/dev-cycle/qa/VCP-031.md && wc -l docs/dev-cycle/qa/VCP-031.md || echo "NOT FOUND directly, searching archive"; find docs/dev-cycle -iname "*VCP-031*"

    grep -n "되돌릴 수 없는" AGENTS.md .claude/skills/dev-cycle/SKILL.md .claude/skills/dev-cycle/references/*.md 2>/dev/null; echo "---검증 기준 커밋---"; grep -rn "검증 기준 커밋" .claude/skills docs/dev-cycle 2>/dev/null; echo "---하네스 등급 사용례---"; grep -rn "하네스" .claude/skills/closing-bet-verify/SKILL.md .claude/skills/dev-cycle/references/tier-rules.md

    grep -n "하네스" .claude/skills/dev-cycle/references/tier-rules.md .claude/skills/dev-cycle/references/ultraqa.md .claude/skills/dev-cycle/references/browser-notes.md 2>/dev/null

## 에이전트가 돌려준 보고 원문

closing-bet-verify 스킬 읽기 전용 스모크 검증 결과를 보고합니다. 어떤 파일도 만들거나 고치지 않았고, 서버나 요청도 일으키지 않았습니다.

## (a) S-1~S-4 별 필요 등급과 근거

- **S-1(저장 실패가 화면에 오류로 보인다)**: 하네스 + 브라우저 두 등급이 함께 필요합니다. 등급표 정의상 하네스는 "실패 경로·비용이 드는 경로의 실제 동작"의 증거이고, 이 시나리오는 `create_signals_log` False 를 스텁으로 강제한 실패 경로이므로 하네스가 필요합니다. 동시에 사용자 진입 흐름이 관리자 화면 조작이므로 "사용자가 보는 것"의 증거인 브라우저 등급도 필요합니다. `tier-rules.md` §1-1 하위 "agent-browser 와의 관계"(166행)가 "API 하네스만으로 사용자 조작·화면 결과를 검증한 것으로 세지 않는다"고 못박아, 하네스 단독으로는 부족합니다.
- **S-2(저장 성공은 시그널 수를 말한다)**: S-1과 동일한 이유로 하네스(`QA_VCP_MODE=ok` 스텁 경로) + 브라우저(화면 문구·표 행수) 둘 다 필요합니다.
- **S-3(True 인데 0건이면 종전 문구다)**: 정적 등급으로 충분합니다. pytest 단위 테스트가 "코드가 검사가 정한 계약을 지킨다"는 것만 증명하면 되는 순수 로직 분기이고, 인접(필수 아님) 시나리오라 비용이 큰 등급을 요구하지 않습니다.
- **S-4(비관리자는 실행되지 않고 라우트는 거부한다)**: 브라우저(권한 모달이 보이는지, 요청이 실제로 나가지 않는지)가 핵심이며, 라우트 403 자체는 curl 로 실제 호출 경로를 태우는 것이라 하네스 성격도 겹칩니다. `tier-rules.md` §2 "신원 확정"이 이런 인증 경로를 위험 경로로 분류하므로, 두 등급을 함께 쓰는 편이 정본 취지에 맞습니다.

## (b) 「격리 환경」이 정한 세우기 명령 목록 (적기만, 미실행)

1. scratchpad 에 저장소 전체 사본 생성, `frontend/node_modules` 는 `cp -c -R` (APFS clone)
2. `SCHEDULER_ENABLED=false gunicorn <진입점>:app --bind 127.0.0.1:<포트> --workers 1 --threads 4`
3. `PORT=<포트> API_URL=http://127.0.0.1:<Flask 포트> TZ=Asia/Seoul npm run dev` (사본 `frontend/` 안에서)
4. 사본 `frontend/` 안에서 `next-auth/jwt` 의 `encode` 로 더미 `NEXTAUTH_SECRET` 과 같은 값의 세션 토큰을 만들어 쿠키 `next-auth.session-token` 에 주입
5. 정리: gunicorn·Next·브라우저 종료, 토큰 파일 삭제, `npx vitest` 가 남긴 `node_modules/.vite` 삭제

## (c) 「두 관점」 가운데 이 항목에서 실제로 읽어야 할 값 세 개

VCP-031 은 `services/kr_market_vcp_background_service.py` 만 고쳤지만 기존 화면(`/dashboard/kr/vcp`)이 이번에 바뀐 API(상태 판정)를 그대로 쓰므로, SKILL.md "두 관점" 절의 조건("frontend/ 를 건드렸거나 기존 화면이 이번에 바꾼 API·인증·자료를 쓰면")에 해당해 두 관점 모두 필요합니다.

1. 브라우저 관점: 「Refresh VCP」 클릭 뒤 화면에 실제로 보이는 상태 문구(성공/오류 텍스트)와 표 행수
2. 브라우저 관점: `POST /api/kr/signals/run`·`GET /api/kr/signals/status` 요청의 URL·메서드·응답 상태/바디
3. 프레임워크 관점: 격리 Next 의 `/_next/mcp` `get_compilation_issues`·`get_errors` 가 돌려주는 `data:` 줄(콘솔 오류 판정의 보강 근거, 브라우저가 그 화면을 먼저 열어야 값이 참)

## (d) QA 문서 메타에 적어야 할 항목 이름 전부

`archive-format.md` §8 형식 기준 11개: 대상 화면, 구성 근거, 구성/실행 시각, QA 엔진(engine), 단계(phase), 반복(iteration), baseline 상태, 필수 여부(required), 결과, 증거, 정리(cleanup).

## 정본과 어긋나거나 모호한 문장 (최대 3개)

1. **SKILL.md:78** — "메타(엔진, 단계, 반복, baseline, 필수 여부, 결과, 증거, 정리)"라고 8개만 나열해, 정본인 `archive-format.md` §8 예시(172-234행)가 실제로 갖춘 「대상 화면」·「구성 근거」·「구성/실행 시각」 3개 항목이 빠졌습니다. 이 요약만 보고 QA 문서를 쓰면 대상·근거·시각을 누락할 위험이 있습니다.
2. **SKILL.md:20**(등급표의 하네스 행) — "격리 사본에서 가짜 클라이언트·스텁 진입점으로 실제 호출 경로를 태움"이 "실패 경로·비용이 드는 경로의 실제 동작"의 증거라고만 적혀, `tier-rules.md:166`과 `ultraqa.md:42,56`이 명시하는 "API/HTTP 하네스는 보강 증거일 뿐 사용자 조작·화면 결과의 브라우저 검증을 대신하지 못한다"는 종속 관계가 등급표 자체에는 드러나지 않습니다. 등급표만 보면 하네스 하나로 S-1·S-2 같은 사용자 화면 흐름의 실패 경로 검증이 끝난다고 오독할 수 있습니다.
3. **SKILL.md:61-62**(browse 명령 목록) — `console --errors` 만 나열하고 `console --clear` 를 넣지 않았습니다. `browser-notes.md:65`는 "판정 전에 `console --clear` 로 비우고 `goto` 로 다시 로드한다. 이것을 빠뜨리면 Next.js HMR 중간 상태에서 났던 오류가 현재 코드의 오류처럼 보인다"고 명시적으로 경고하는데, SKILL.md의 명령 목록만 보고 따라 하면 이 단계를 빠뜨리기 쉽습니다.

## 실제로 읽은 파일 경로

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.claude/skills/closing-bet-verify/SKILL.md` (전체)
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.claude/skills/dev-cycle/references/archive-format.md` (172-236행, §8)
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.claude/skills/dev-cycle/references/tier-rules.md` (116-175행, §1-1 및 §2 도입부; 헤더 목록은 전체 grep)
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.claude/skills/dev-cycle/references/browser-notes.md` (전체)
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/qa/VCP-031.md` (전체)
- `AGENTS.md`, `.claude/skills/dev-cycle/SKILL.md`(181행 부근) — grep 으로 "되돌릴 수 없는 조작"·"검증 기준 커밋" 존재만 확인, 전체 읽지 않음
