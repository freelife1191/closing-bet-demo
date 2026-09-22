# smoke-reviewer — 읽기 전용 smoke 원문 (2026-09-22)

- 도구 호출: {'Read': 1, 'ToolSearch': 1, 'SendMessage': 1}
- Read 로 연 파일: .claude/agents/closing-bet-reviewer.md
- Bash 명령 (원문, 전부 로컬 읽기 전용이었고 HTTP 요청은 없었다):

## 에이전트가 돌려준 보고 원문

`.claude/agents/closing-bet-reviewer.md` 의 「하지 않을 일」 목록을 그대로 돌려드립니다. 검토는 시작하지 않았고, 파일 수정이나 서버 요청도 하지 않았습니다.

## 하지 않을 일

- 코드·문서·상태를 수정하지 않는다. `Edit`·`Write` 를 쓰지 않는다.
- 돌고 있는 서버(3500·5501·live)에 어떤 HTTP 요청도 보내지 않는다. GET 도 보내지 않는다. `AGENTS.md` 「되돌릴 수 없는 조작」이 이유다.
- `data/` 아래 파일을 열지 않고 `.env` 계열의 값을 옮겨 적지 않는다.
- 서브에이전트를 띄우지 않는다. 검토는 이 역할 하나가 끝낸다.
- 범위 밖 전체 감사를 하지 않는다. 범위 밖 문제는 한 줄로 적고 넘어간다.
