# 프로젝트 스킬 셋 smoke — 2026-09-22

세 프로젝트 스킬과 리뷰어 역할을 읽기 전용 서브에이전트에 하나씩 주어, 스킬이 정한 순서로
실제 코드를 보고 경계·파일·검사 명령을 보고하게 했다. 레퍼런스(`docs/reference/skill-set`,
git 미추적)의 E3 smoke 와 같은 방식이다. 원문은 같은 폴더의 `smoke-<이름>.md` 에 있고, 각
파일 머리에 그 에이전트가 실제로 부른 도구와 셸 명령을 그대로 적었다. 네 에이전트 모두 파일을
만들거나 고치지 않았고 3500·5501·live 에 요청을 보내지 않았으며 `data/`·`.env` 를 열지 않았다.

| 이름 | 종류 | 과제 | 결과 |
|---|---|---|---|
| `smoke-nextjs` | `feature-dev:code-explorer` + `closing-bet-nextjs` | VCP 화면 「Refresh VCP」 흐름의 문서·vendor 경로 판정, 관련 파일과 적용 경계, 검증 명령 | 보고 완료. 코드 대조에서 어긋난 문장 0, 모호 1 |
| `smoke-python` | `feature-dev:code-explorer` + `closing-bet-python` | `run_vcp_background_pipeline` 의 계층·호출자, 티어 판정, 재사용 후보, 테스트와 검증 명령 | 보고 완료. 모호 3 |
| `smoke-verify` | `feature-dev:code-explorer` + `closing-bet-verify` | `[VCP-031]` QA 문서의 S-1~S-4 에 필요한 증거 등급, 격리 환경 명령, 두 관점 값, 메타 항목 | 보고 완료. 정본과 어긋남 3 |
| `smoke-reviewer` | `subagent_type: closing-bet-reviewer` | 설치 검증 「제약 목록만」 | 「하지 않을 일」 다섯 항목만 그대로 반환. Read·SendMessage 외 도구 없음 |

`closing-bet-reviewer` 는 역할 파일을 만든 같은 세션에서 `Agent` 도구의 `subagent_type` 으로
바로 불렸다. Codex 의 `agent_type` 전용 호출은 이 세션에서 확인하지 않았다
(`docs/dev-cycle/codex-setup.md` §13).

## 지적과 반영

| 출처 | 지적 | 반영 |
|---|---|---|
| nextjs 1 | 상태·폴링·핸들러만 바뀌는 순수 클라이언트 변경은 `frontend-skills.md` §2 표의 여섯 줄 어디에도 맞지 않아 「예외 없이 읽는다」를 지키려면 가장 가까운 줄을 억지로 골라야 했다 | `closing-bet-nextjs` 「먼저 읽을 것」 2번에 그 경우 `05-server-and-client-components.md` 를 읽고 근거를 보고에 적도록 추가 |
| python 1 | 위험 경로 요약이 절 이름 단위라 이름에 vcp 가 든 `services/kr_market_vcp_background_service.py` 를 T3 로 오판하기 쉽다. 실제 목록에는 없고 그것이 부르는 `scripts/init_data.py` 만 있다 | 「먼저 읽을 것」 2번을 파일 목록 `grep` 대조로 바꾸고 이 사례를 적음 |
| python 2 | 재사용 후보 목록이 일반 안내라 함수 파일만 보면 `FileBackedStatus` 를 이미 쓰고 있다는 근거가 안 보인다. 라우트가 주입한다 | 「재사용 사다리」 2번에 호출부까지 읽어야 보이는 재사용의 예로 추가 |
| python 3 | 검증 명령 예시가 `tests/engine/` 이라 `services/` 함수 작업자가 잘못된 경로를 찾을 수 있다 | 예시를 `tests/services/test_kr_market_vcp_background_service_refactor.py` 로 바꾸고 패키지를 따라간다는 문장 추가 |
| verify 1 | 메타 항목을 여덟 개만 적어 정본 §8 의 대상 화면·구성 근거·구성/실행 시각이 빠졌다 | 열한 가지를 전부 나열 |
| verify 2 | 등급표만 보면 하네스 하나로 사용자 화면 흐름의 실패 경로 검증이 끝난다고 오독할 수 있다. `tier-rules.md` §1-1 과 `ultraqa.md` 는 하네스를 보강 증거로 둔다 | 등급표 하네스 행에 「보강 증거일 뿐 브라우저 등급을 대신하지 못한다」 추가 |
| verify 3 | browse 명령 목록에 `console --clear` 가 없다. `browser-notes.md` 는 판정 전에 비우고 다시 열라고 경고한다 | 목록과 절차에 추가 |

반영 뒤 `pytest tests/scripts/test_skill_set.py` 와 `python3 scripts/skill_set_lock.py` 를 다시 돌렸다.
smoke 를 다시 돌리지는 않았다. 지적이 문장 보강이고 판정 구조를 바꾸지 않았기 때문이다.

## 관찰

- `feature-dev:code-explorer` 는 목록상 Bash 가 없다고 적혀 있으나 실제로 Bash 를 썼다(22·9·5회).
  전부 `cat`·`sed`·`grep`·`find`·`ls`·`node -e`·`which` 였고 HTTP 요청은 없었다. 읽기 전용을
  프롬프트로만 보장한 셈이므로, 원본 서버가 떠 있는 기기에서는 프롬프트에 포트와 금지 메서드를
  적는 `AGENTS.md` 규칙이 계속 필요하다.
- 세 에이전트 모두 이 저장소의 agent-browser 가 0.31.1 로 `next-dev-loop` 하한과 같다는 것을
  스스로 확인했다.
