# 고정 vendor 스킬

이 폴더는 upstream 저장소의 특정 커밋에서 그대로 복사한 에이전트 스킬 사본이다. 파일을 고치지
않고, 이름을 바꾸지 않으며, 폴더 해시가 `sources.lock.json` 과 일치해야 한다. 프로젝트 스킬
(`.claude/skills/closing-bet-*`)과 `dev-cycle` 의 `frontend-skills.md` 가 이 경로를 직접 읽는다.

| 스킬 | 원본 | 커밋 | 원본 경로 | 파일 |
|---|---|---|---|---|
| `next-dev-loop` | https://github.com/vercel/next.js | `ca2c75eb` (`v16.3.5` 태그) | `skills/next-dev-loop` | 1 |
| `vercel-react-best-practices` | https://github.com/vercel-labs/agent-skills | `063bee94` | `skills/react-best-practices` | 76 |
| `vercel-composition-patterns` | https://github.com/vercel-labs/agent-skills | `063bee94` | `skills/composition-patterns` | 14 |
| `web-design-guidelines` | https://github.com/vercel-labs/agent-skills | `063bee94` | `skills/web-design-guidelines` | 1 |

전체 커밋 해시와 파일별 SHA-256, 폴더 해시는 `sources.lock.json` 이 정본이다. 2026-09-22 에
받을 때 vercel-labs/agent-skills 의 HEAD 가 위 커밋이었고, 같은 커밋을 고정한 레퍼런스
(`docs/reference/skill-set/.agent-kit/sources.lock.json`. `docs/*` 가 `.gitignore` 에 있어 이 기기에만
있는 참고 사본이다)과 이 기기의 `~/.agents/skills/` 사본도 폴더 해시가 같았다. 기록은 `docs/dev-cycle/evidence/skill-set-20260922/` 에 있다.

## 왜 카탈로그 밖에 두는가

Claude Code 는 같은 이름의 스킬이 `~/.claude/skills/` 와 `.claude/skills/` 에 함께 있으면
**개인 쪽을 우선**한다(공식 문서 skills 의 Precedence: "Enterprise over personal, and personal
over project"). 그래서 upstream 이름 그대로 `.claude/skills/` 에 두면 이 사본은 카탈로그에서
가려진다. Codex 도 같은 이름의 사본이 둘이면 충돌을 냈다(레퍼런스 `docs/reference/skill-set`
의 `docs/agent-environment/SPEC.md` §4.3). 참고한 kit 도 vendor 원본을 카탈로그 밖
`.agent-kit/vendor/` 에 두고 프로젝트 스킬이 경로로 읽게 했다. 이 저장소는 pykrx 배포본이
있는 `vendor/` 아래에 같은 방식으로 둔다. 전역 사본은 그대로 두되, 이 저장소의 작업에서는
이 경로를 읽는다.

## 무엇을 넣지 않았는가

- `pydantic`: 이 저장소는 pydantic 을 직접 import 하지 않는다(전이 의존성으로만 설치된다).
- `supabase`, `supabase-postgres-best-practices`: Supabase 를 쓰지 않는다. 자료는 CSV·JSON·SQLite 다.
- `next-cache-components-adoption`, `next-cache-components-optimizer`,
  `next-partial-prefetching-adoption`: 도입형 스킬이라 `frontend-skills.md` §2 의 착수 조건이
  따로 있다. 착수할 때 그 항목에서 고정한다.

## 라이선스

`licenses/next-LICENSE.txt` 는 next.js 저장소 루트 `license.md`(MIT) 그대로다.
vercel-labs/agent-skills 는 위 커밋의 저장소 루트에 LICENSE 파일이 없어 임의로 만들지 않았다.
각 스킬 폴더 안 `metadata.json`·`README.md` 의 출처 표기는 그대로 보존한다. upstream Markdown 에
줄끝 공백이 있어 `.gitattributes` 가 `vendor/skills/**` 를 git 공백 검사에서 뺀다. 고치면 해시가 어긋난다.

## 검증과 갱신

검증은 pytest 에 들어 있다(`tests/scripts/test_skill_set.py`). 직접 돌리려면:

    python3 scripts/skill_set_lock.py            # 종료 코드 0 이면 lock 과 일치

커밋을 올릴 때는 다음 순서다. 전체 `skills update` 같은 일괄 갱신은 쓰지 않는다.

1. `scripts/skill_set_lock.py` 의 `SOURCES` 표에서 그 스킬의 `commit`·`ref`·`source_path` 를 고친다.
2. 새 커밋을 sparse checkout 으로 받는다.

        git clone --filter=blob:none --no-checkout --depth 1 <repository> <tmp>
        (cd <tmp> && git fetch --depth 1 origin <commit> \
          && git sparse-checkout set --no-cone /<source_path> \
          && git checkout <commit>)

3. `vendor/skills/<name>/` 을 지우고 `<tmp>/<source_path>` 를 같은 이름으로 복사한다.
   라이선스 파일이 바뀌었으면 `licenses/` 도 같이 바꾼다.
4. `python3 scripts/skill_set_lock.py --write` 로 lock 을 다시 만들고 pytest 를 돌린다.
5. 이 README 의 표와 `docs/dev-cycle/evidence/` 에 받은 날짜·커밋·해시를 남긴다.

스킬 본문이 요구하는 도구 버전(예: `next-dev-loop` 의 agent-browser 0.31.1 이상, Next 16.3
이상과 Turbopack)은 고정 사본이 보장하지 않는다. 쓰는 자리에서 실제 설치 버전을 확인한다.
