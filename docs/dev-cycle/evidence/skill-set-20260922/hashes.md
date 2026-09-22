# 고정 vendor 스킬 해시 대조 — 2026-09-22

`docs/reference/skill-set`(git 미추적. 이 기기에만 있는 Shopping Pilot agent-kit 참고 사본)을 본떠
`vendor/skills/` 에 넣은 네 사본의 출처와 해시 대조 기록이다.
세션은 Claude Code(Fable 5.1)였고, 받은 시각은 2026-09-22 21:00 KST 무렵이다.

## 받은 방법

blob 없는 얕은 clone 에 sparse checkout 으로 원본 경로만 받았다. 두 저장소 모두 GitHub 가
커밋 SHA 로의 fetch 를 허용했다.

    git clone --filter=blob:none --no-checkout --depth 1 https://github.com/vercel-labs/agent-skills.git
    git fetch --depth 1 origin 063bee94c3f4df8453406c830b0a7df0f2860278
    git sparse-checkout set --no-cone /skills/react-best-practices /skills/composition-patterns /skills/web-design-guidelines
    git checkout 063bee94c3f4df8453406c830b0a7df0f2860278

    git clone --filter=blob:none --no-checkout --depth 1 --branch v16.3.5 https://github.com/vercel/next.js.git
    git sparse-checkout set --no-cone /skills/next-dev-loop /license.md
    git checkout ca2c75eb7f8d9dd012a8bb83c06132149fe221f9

받을 때 `git ls-remote` 로 확인한 upstream 상태: vercel-labs/agent-skills 의 `HEAD` 는
`063bee94c3f4df8453406c830b0a7df0f2860278`, vercel/next.js 의 `refs/tags/v16.3.5` 는
`ca2c75eb7f8d9dd012a8bb83c06132149fe221f9`. 레퍼런스가 고정한 커밋과 같다.

## 폴더 해시 (sha256-canonical-path-sha256-casefold-v1)

같은 규칙으로 네 곳을 계산했다. 네 스킬 모두 네 곳의 값이 같았다.

| 스킬 | 파일 수 | 폴더 해시 | 받은 사본 | 레퍼런스 `.agent-kit/vendor` | 레퍼런스 `sources.lock.json` | 이 기기 `~/.agents/skills` |
|---|---|---|---|---|---|---|
| `next-dev-loop` | 1 | `c333583e01d337e77009cdf16034b9069558120f6f73bbed4d921847e8e253b7` | 일치 | 일치 | 일치 | 일치 |
| `vercel-react-best-practices` | 76 | `517a7572ff793b82737e517b27a8ccb9525feaf22e4544f6f8349815c8730665` | 일치 | 일치 | 일치 | 일치 |
| `vercel-composition-patterns` | 14 | `f16328ec47ffd149810df1d0d0199175ed710b93e3d0a27794998170cb5e74e6` | 일치 | 일치 | 일치 | 일치 |
| `web-design-guidelines` | 1 | `5d9fd9ff8863be3d775f717f6ad52a3909cd7abd8fb67a7376fe2e317b309fa3` | 일치 | 일치 | 일치 | 일치 |

next.js `license.md` 의 SHA-256 은 `ee765244e2d59f5234d474f62e0766fa0c8b99af967fdd4c0cb8dcb0c76ea224` 로
레퍼런스 lock 의 `next-LICENSE.txt` 와 같다. vercel-labs/agent-skills 는 그 커밋의 루트에
LICENSE 파일이 없었다(`README.md` 와 `skills/` 만 있음).

## 검증

- `python3 scripts/skill_set_lock.py` → `vendor/skills matches sources.lock.json`, 종료 코드 0
- `pytest tests/scripts/test_skill_set.py -q -p no:cacheprovider` → 5 passed
- `git diff --check` → 처음에는 upstream Markdown 의 줄끝 공백 153줄 때문에 `vendor/skills` 에서
  종료 코드 2 였다. 바이트를 보존해야 하므로 고치지 않고 `.gitattributes` 에
  `vendor/skills/** -whitespace` 를 두어 그 경로만 공백 검사에서 뺐다. 그 뒤 전체 트리에서 종료
  코드 0 이다. 레퍼런스는 같은 상황을 종료 코드 2 로 두고 기록만 남겼다.

## 넣지 않은 것과 이유

- `pydantic`(pydantic/skills @ `238d9710`): 저장소에 `import pydantic` 이 없다. 전이 의존성으로만 설치된다.
- `supabase`, `supabase-postgres-best-practices`(supabase/agent-skills @ `8331f910`): Supabase 를 쓰지 않는다.
- 도입형 세 스킬(`next-cache-components-adoption`, `-optimizer`, `next-partial-prefetching-adoption`):
  `frontend-skills.md` §2 의 착수 조건 전에는 고정하지 않는다.

## 카탈로그 배치 근거

Claude Code 공식 문서(https://code.claude.com/docs/en/skills.md, Precedence): "Enterprise over
personal, and personal over project. With `deploy` in both `~/.claude/skills/` and the project's
`.claude/skills/`, `/deploy` runs the personal one". 같은 문서는 `.claude/skills/<name>` 이
심볼릭 링크여도 되고 같은 대상은 한 번만 싣는다고 적는다. 이 조회는 `claude-code-guide`
서브에이전트(`skill-precedence-guide`)로 했다.
