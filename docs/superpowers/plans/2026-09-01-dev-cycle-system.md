# dev-cycle 개발 사이클 운영 체계 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TODO 항목 하나를 계획부터 아카이브 기록까지 완주시키는 dev-cycle 규약을 구축하고, 흩어진 백로그를 한 곳으로 통합한다.

**Architecture:** 새 실행 코드를 만들지 않는다. 이미 설치된 스킬(`autoplan`, `/ponytail-review`, `/simplify`, `/code-review`, `/review`, `/security-review`, `qa`, `agent-browser`)을 정해진 순서로 엮는 프로젝트 로컬 스킬 정의와 레퍼런스 문서, 그리고 기록 파일만으로 구성한다. 검증은 단위 테스트 대신 파일 존재·경로 실재·중복 부재를 확인하는 셸 명령으로 수행한다.

**Tech Stack:** Markdown (스킬·에이전트 정의, 레퍼런스, 기록), git, 셸 검증 명령

**Spec:** `docs/superpowers/specs/2026-09-01-dev-cycle-system-design.md`

## Global Constraints

- 새로 추가되는 실행 코드는 없다. 산출물은 Markdown 파일과 `.gitignore` 수정뿐이다.
- 프로젝트 로컬 자산은 `.claude/skills/dev-cycle/` 과 `.claude/agents/` 아래에만 둔다. 전역 스킬 디렉터리(`~/.claude/skills/`)를 건드리지 않는다.
- 기록 파일은 `docs/dev-cycle/` 아래에 둔다. 이 경로는 커밋 `30645f0` 에서 `.gitignore` 예외로 이미 등록되었다.
- 항목 ID 는 `CHAT` `JONGGA` `VCP` `FLOW` `FE` `INFRA` 여섯 카테고리 약어와 세 자리 일련번호를 하이픈으로 잇는다. 예: `INFRA-001`.
- 우선순위는 `P0`(즉시) `P1`(이번 주기) `P2`(대기) 세 단계뿐이다.
- 티어는 `T1` `T2` `T3` 세 단계뿐이며, 구현 후 상향만 허용하고 하향은 금지한다.
- 위험 경로 목록은 2026-09-01 기준 실측값이다. 목록에 적는 모든 경로는 실재해야 한다.
- 작업 브랜치는 `develop` 이다. `main` 에서 시작하지 않는다.
- 커밋 메시지는 한국어 본문을 쓰고 `Co-Authored-By` 와 `Claude-Session` 트레일러를 붙인다.

---

## 파일 구조

| 경로 | 책임 | 태스크 |
|---|---|---|
| `.claude/skills/dev-cycle/references/tier-rules.md` | 티어 판정 규칙과 위험 경로 목록. 판정 근거의 단일 출처 | 1 |
| `.claude/skills/dev-cycle/references/archive-format.md` | TODO 및 아카이브 기록 형식. 형식의 단일 출처 | 2 |
| `.claude/skills/dev-cycle/SKILL.md` | 사이클 절차와 게이트. 두 레퍼런스를 참조만 하고 내용을 복제하지 않는다 | 3 |
| `.claude/agents/dev-workflow.md` | 감사 전담 서브에이전트. 사이클을 실행하지 않는다 | 4 |
| `docs/dev-cycle/TODO.md` | 백로그 단일 관리 지점 | 5 |
| `docs/dev-cycle/archive/2026-09.md` | 월별 요약 (헤더만 둔 상태로 시작) | 5 |
| `CLAUDE.md` | dev-cycle 섹션 추가, 기존 백로그 섹션 이관, 잘못된 스케줄러 경로 정정 | 5 |
| `docs/plans/TO_DO_LIST.md` | 삭제 (내용은 TODO.md 로 이관) | 5 |

레퍼런스 두 개를 `SKILL.md` 와 분리하는 이유는 갱신 주기가 다르기 때문이다. 위험 경로 목록은 파일이 추가될 때마다 바뀌지만 사이클 절차는 거의 바뀌지 않는다. 같은 파일에 두면 절차를 읽을 때마다 긴 경로 목록을 지나쳐야 한다.

---

## Task 1: 티어 판정 레퍼런스

**Files:**
- Create: `.claude/skills/dev-cycle/references/tier-rules.md`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces: 티어 이름 `T1` `T2` `T3`, 위험 경로 목록의 정본. Task 3 의 `SKILL.md` 가 이 파일을 경로로 참조하고, Task 4 의 에이전트가 감사 결과에 티어를 매길 때 이 규칙을 따른다.

- [ ] **Step 1: 디렉터리를 만든다**

```bash
mkdir -p .claude/skills/dev-cycle/references
```

- [ ] **Step 2: `tier-rules.md` 를 작성한다**

파일 전문은 다음과 같다.

````markdown
# 티어 판정 규칙

dev-cycle 의 리뷰와 검증 강도를 정하는 규칙이다. 판정은 계획 단계에서 하고, 구현 후
실제 diff 가 상위 티어에 해당하면 상향한다. 하향은 어떤 경우에도 하지 않는다.

## 1. 티어별 절차

| 티어 | 조건 | 리뷰 | 검증 |
|---|---|---|---|
| T1 | 변경 50줄 이하이고 위험 경로에 닿지 않는다 | `/simplify` | 변경 범위의 pytest 또는 vitest |
| T2 | 변경 300줄 이하이고 위험 경로에 닿지 않는다 | `/ponytail-review` → `/simplify` → `/code-review` | pytest·vitest 전체 + agent-browser 로 변경 화면 실측 |
| T3 | 변경 300줄을 초과하거나 위험 경로에 닿는다 | T2 전체 + `/review` | pytest·vitest 전체 + qa 스킬 전체 시나리오 |

`/ponytail-review` 를 `/simplify` 앞에 두는 순서를 지킨다. 지울 코드를 먼저 걷어내야
곧 사라질 코드를 다듬는 낭비가 생기지 않는다.

인증이나 시크릿에 닿으면 티어와 무관하게 `/security-review` 를 추가한다.

줄 수는 `git diff --stat` 의 추가와 삭제 합계를 쓴다. 테스트 파일과 의존성 잠금 파일
(`package-lock.json`, `requirements.txt` 의 버전 핀 갱신)은 합계에서 제외한다.

## 2. 위험 경로

한 줄이라도 닿으면 T3 이다. 2026-09-01 기준 실측 결과이며 47개 파일, 약 16,197줄이다.

### 신호와 등급 결정
- `engine/grade_classifier.py`
- `engine/grade_decider.py`
- `engine/grade_filter_validator.py`
- `engine/generator.py`
- `engine/generator_helpers.py`
- `engine/generator_result_storage.py`
- `engine/generator_runtime_helpers.py`
- `engine/generator_runtime_mixin.py`
- `engine/phases.py` (파사드)
- `engine/phases_analysis.py`
- `engine/phases_base.py`
- `engine/phases_news_llm.py`
- `engine/phases_phase1_helpers.py`
- `engine/phases_phase4_helpers.py`
- `engine/phases_pipeline.py`

### 시장 진입 판정
- `engine/market_gate.py`
- `engine/market_gate_analysis.py`
- `engine/market_gate_fetchers_external.py`
- `engine/market_gate_fetchers_local.py`
- `engine/market_gate_logic.py`
- `engine/market_gate_logic_fetchers.py`
- `engine/market_gate_logic_scoring.py`
- `engine/market_gate_logic_utils.py`

### VCP 판정
- `engine/vcp_ai_analyzer.py`
- `engine/vcp_ai_analyzer_helpers.py`

### 모의투자 계좌와 거래
- `services/paper_trading.py`
- `services/paper_trading_constants.py`
- `services/paper_trading_db_setup.py`
- `services/paper_trading_history_mixin.py`
- `services/paper_trading_price_fetchers.py`
- `services/paper_trading_sync_service.py`
- `services/paper_trading_trade_account_mixin.py`
- `services/paper_trading_valuation_helpers.py`
- `services/paper_trading_valuation_service.py`

### 수급 집계
- `services/investor_trend_5day_service.py`
- `services/kr_market_flow_service.py`

### 스케줄러와 데이터 적재
- `services/scheduler.py`
- `services/scheduler_jobs.py`
- `services/scheduler_loop.py`
- `services/scheduler_runtime_status_service.py`
- `scripts/init_data.py`

### 저장소 스키마
파일명에 `sqlite` 를 포함하는 모든 모듈이 해당한다.
- `chatbot/storage_sqlite_common.py`
- `chatbot/storage_sqlite_helpers.py`
- `chatbot/storage_sqlite_history.py`
- `chatbot/storage_sqlite_memory.py`
- `services/kr_market_data_cache_sqlite_payload.py`
- `services/sqlite_utils.py`

### 시크릿과 인증

이 절은 파일 목록이 아니라 접촉 패턴이다. 아래 패턴에 해당하는 파일을 건드리면 그 파일이
지금 존재하는지와 무관하게 T3 이며 `/security-review` 를 추가한다.

- `.env` 로 시작하는 모든 파일 (`.env`, `.env.production`, `.env.example` 등)
- `secrets/` 아래 전부

## 3. 판정 절차

1. 계획에서 건드릴 파일 목록을 뽑는다.
2. 그 목록이 §2 와 하나라도 겹치면 T3 이다. 줄 수는 보지 않는다.
3. 겹치지 않으면 예상 변경 줄 수로 T1 과 T2 를 가른다.
4. 구현 후 `git diff --stat` 으로 재확인한다. 상위 티어에 해당하면 올리고, 낮게 나와도
   내리지 않는다.

## 4. 목록 갱신

위험 경로에 해당하는 파일이 새로 생기거나 이동하면, 그 파일을 만든 사이클의 게이트 2 에서
이 목록을 함께 갱신한다. 목록에 적힌 경로는 모두 실재해야 한다.
````

- [ ] **Step 3: 목록의 모든 경로가 실재하는지 검증한다**

```bash
RULES=.claude/skills/dev-cycle/references/tier-rules.md
missing=0
for f in $(grep -oE '`[^`]+\.py`' "$RULES" | tr -d '`' | sort -u); do
  [ -e "$f" ] || { echo "MISSING: $f"; missing=1; }
done
[ $missing -eq 0 ] && echo "OK: 목록의 파이썬 경로가 모두 실재합니다"
echo "검사한 경로 수: $(grep -oE '`[^`]+\.py`' "$RULES" | tr -d '`' | sort -u | wc -l | tr -d ' ')"
```

기대 결과:
```
OK: 목록의 파이썬 경로가 모두 실재합니다
검사한 경로 수: 47
```

백틱 안의 경로만 뽑으므로 `` `engine/phases.py` (파사드) `` 처럼 뒤에 주석이 붙은 줄도
정확히 처리한다. §2 의 시크릿 절은 파일 목록이 아니라 패턴 규칙이므로 이 검사에 포함되지
않는다.

`MISSING` 이 하나라도 출력되면 그 경로를 실측으로 확인해 목록을 고친 뒤 이 단계를 다시
실행한다.

- [ ] **Step 4: 위험 경로 파일 수를 확인한다**

```bash
ls engine/grade_*.py engine/generator*.py engine/phases*.py engine/market_gate*.py \
   engine/vcp_ai_analyzer*.py services/paper_trading*.py services/investor_trend*.py \
   services/kr_market_flow_service.py services/scheduler*.py scripts/init_data.py \
   chatbot/storage_sqlite_*.py services/kr_market_data_cache_sqlite_payload.py \
   services/sqlite_utils.py 2>/dev/null | wc -l
```

기대 결과: `47`

값이 다르면 파일이 추가되거나 이동한 것이므로, 실측 결과에 맞추어 §2 목록을 갱신한 뒤
Step 3 부터 다시 실행한다.

- [ ] **Step 5: 커밋한다**

```bash
git add .claude/skills/dev-cycle/references/tier-rules.md
git commit -m "$(cat <<'MSG'
feat(dev-cycle): 티어 판정 규칙과 위험 경로 목록 추가

변경 규모와 위험 경로 접촉 여부로 T1/T2/T3 를 가른다.
위험 경로는 2026-09-01 실측 기준 47개 파일이며, 한 줄이라도 닿으면
줄 수와 무관하게 T3 로 판정한다. 구현 후 상향만 허용한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## Task 2: 기록 형식 레퍼런스

**Files:**
- Create: `.claude/skills/dev-cycle/references/archive-format.md`

**Interfaces:**
- Consumes: Task 1 의 티어 이름 `T1` `T2` `T3`
- Produces: 항목 ID 규칙(`CHAT` `JONGGA` `VCP` `FLOW` `FE` `INFRA` + 세 자리 번호), 우선순위 값 `P0` `P1` `P2`, TODO·일별·월별 세 형식의 정본. Task 3 의 `SKILL.md` 가 기록 단계에서 이 파일을 참조하고, Task 5 가 이 형식으로 `TODO.md` 를 만든다.

- [ ] **Step 1: `archive-format.md` 를 작성한다**

파일 전문은 다음과 같다.

````markdown
# TODO 및 아카이브 기록 형식

dev-cycle 이 백로그와 완료 기록을 남기는 형식이다. 형식을 바꾸려면 이 파일만 고친다.

## 1. 파일 위치

```
docs/dev-cycle/
  TODO.md                    백로그. 대기 중이거나 진행 중인 항목만 담는다
  archive/
    2026-09.md               월별 요약. 완료 항목을 한 줄씩 적는다
    daily/
      2026-09-01.md          일별 상세. 완료 항목의 전체 기록
```

백로그는 `TODO.md` 한 곳에만 둔다. CLAUDE.md 를 비롯한 다른 문서에 할 일 목록을 중복해서
적지 않는다. 중복된 백로그는 반드시 어긋난다.

## 2. 항목 ID

`<카테고리 약어>-<세 자리 일련번호>` 형식을 쓴다.

| 약어 | 카테고리 | 주요 경로 |
|---|---|---|
| `CHAT` | 챗봇 | `chatbot/`, `app/routes/kr_market_chatbot_*`, `frontend/src/app/chatbot/` |
| `JONGGA` | 종가베팅 | `app/routes/kr_market_jongga_*`, `frontend/src/app/dashboard/kr/closing-bet/` |
| `VCP` | VCP 시그널 | `engine/vcp_ai_analyzer*`, `app/routes/kr_market_vcp_*`, `frontend/src/app/dashboard/kr/vcp/` |
| `FLOW` | 수급·백테스트 | `services/investor_trend*`, `services/kr_market_backtest_*`, `services/kr_market_flow_service.py` |
| `FE` | 프론트엔드 공통 | `frontend/src/app/components/`, `frontend/src/lib/` |
| `INFRA` | 인프라·패키지 | `requirements.txt`, `frontend/package.json`, `services/scheduler*`, `scripts/init_data.py` |

일련번호는 카테고리별로 독립 증가하며 완료 후에도 재사용하지 않는다. 다음 번호는
`TODO.md` 와 `archive/` 전체에서 해당 약어의 최대 번호에 1을 더해 정한다.

```bash
# CHAT 카테고리의 다음 번호를 구한다
grep -rhoE 'CHAT-[0-9]{3}' docs/dev-cycle/ | sort -u | tail -1
```

## 3. 우선순위

| 값 | 뜻 |
|---|---|
| `P0` | 즉시 처리한다. 동작이 깨져 있거나 다른 작업을 막고 있다 |
| `P1` | 이번 주기에 처리한다 |
| `P2` | 대기한다. 순서가 오면 처리한다 |

## 4. TODO.md 형식

```markdown
# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 완료된 항목은 아카이브로 옮기고 이 파일에서 제거합니다.

## P0 — 즉시

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1
- [ ] requirements.txt 에 버전 핀 적용
- [ ] google-genai 2.x 호환성 확인
- [ ] 회귀 테스트 확인

## P1 — 이번 주기

### [VCP-001] ...

## P2 — 대기

### [FE-001] ...
```

각 항목은 제목 줄, 메타 줄 하나, 체크박스 목록으로 이루어진다. 메타 줄에는 카테고리와
티어를 반드시 적고, 감사에서 나온 항목이면 근거를 함께 적는다. 근거는 감사 리포트의
절 번호를 가리킨다.

체크박스는 실행 단위를 적는다. 세 개에서 여섯 개 사이가 적당하며, 열 개를 넘으면 항목을
둘로 쪼갠다.

## 5. 일별 상세 형식

`docs/dev-cycle/archive/daily/YYYY-MM-DD.md` 에 완료 순서대로 덧붙인다. 파일이 없으면
그날 첫 완료 시점에 다음 헤더로 새로 만든다.

```markdown
# 2026-09-01

## [INFRA-001] 파이썬 의존성 버전 고정
- 완료 2026-09-01 14:32 | 티어 T3 | 커밋 abc1234, def5678
- 변경: requirements.txt, engine/genai_client.py (+42 -18)
- 리뷰: ponytail-review(net -12) · simplify(3건 적용) · code-review(0건) · review(1건 반영)
- 검증: pytest 1515 통과 · vitest 160 통과 · qa 헬스 99
- 메모: google-genai 2.x 에서 GenerateContentConfig 시그니처가 바뀌어 대응했다
```

- **완료** 줄에는 시각, 티어, 커밋 해시를 적는다. 커밋이 여럿이면 쉼표로 잇는다.
- **변경** 줄에는 건드린 파일과 `git diff --stat` 의 증감을 적는다. 파일이 다섯 개를
  넘으면 대표 파일 세 개와 `외 N개` 로 줄인다.
- **리뷰** 줄에는 실제로 돌린 자산만 적는다. 티어가 T1 이면 `simplify` 하나만 적힌다.
  각 자산 뒤 괄호 안에 결과를 요약한다.
- **검증** 줄에는 실행한 테스트와 그 결과를 적는다.
- **메모** 줄은 다음에 같은 자리를 건드릴 사람이 알아야 할 사실이 있을 때만 적는다.
  없으면 줄 자체를 뺀다.

## 6. 월별 요약 형식

`docs/dev-cycle/archive/YYYY-MM.md` 의 표에 한 줄을 덧붙이고 통계를 갱신한다. 파일이
없으면 그달 첫 완료 시점에 새로 만든다.

```markdown
# 2026-09 요약

| 완료일 | ID | 제목 | 카테고리 | 티어 | 커밋 |
|---|---|---|---|---|---|
| 09-01 | INFRA-001 | 파이썬 의존성 버전 고정 | 인프라 | T3 | abc1234 |

## 통계
- 완료 1건 (P0 1 · P1 0 · P2 0)
- 순 코드 증감 +24줄
```

통계는 항목을 추가할 때마다 다시 계산해서 덮어쓴다. 순 코드 증감은 그달 각 항목의
`변경` 줄에 적힌 증감을 합한 값이다.

## 7. 기록 시점

게이트 2 를 통과한 직후에 일별 상세와 월별 요약을 함께 기록하고, 같은 커밋에서
`TODO.md` 의 해당 항목을 제거한다. 월말에 몰아서 집계하는 배치 작업은 두지 않는다.
````

- [ ] **Step 2: 형식대로 샘플을 만들어 구조를 검증한다**

임시 디렉터리에 샘플을 만들어 형식이 파싱 가능한지 확인한다. 검증이 끝나면 지운다.

```bash
TMP=$(mktemp -d)
cat > "$TMP/TODO.md" <<'SAMPLE'
# TODO

## P0 — 즉시

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: AUDIT-INFRA §1
- [ ] requirements.txt 에 버전 핀 적용
SAMPLE
echo "항목 수: $(grep -cE '^### \[[A-Z]+-[0-9]{3}\]' "$TMP/TODO.md")"
echo "메타 줄 수: $(grep -cE '^- 카테고리: .+ \| 티어: T[123]' "$TMP/TODO.md")"
rm -rf "$TMP"
```

기대 결과:
```
항목 수: 1
메타 줄 수: 1
```

두 값이 모두 1 이면 형식이 정규식으로 식별 가능하다는 뜻이다. 0 이 나오면 `archive-format.md`
의 형식 예시와 이 검증 명령의 정규식이 어긋난 것이므로 예시를 고친다.

- [ ] **Step 3: 커밋한다**

```bash
git add .claude/skills/dev-cycle/references/archive-format.md
git commit -m "$(cat <<'MSG'
feat(dev-cycle): TODO 및 아카이브 기록 형식 추가

백로그를 docs/dev-cycle/TODO.md 한 곳으로 모으고, 완료 항목을
일별 상세와 월별 요약 두 층위로 남기는 형식을 정의한다.

항목 ID 는 여섯 카테고리 약어와 세 자리 일련번호로 이루어지며
번호는 재사용하지 않는다. 기록은 게이트 2 통과 직후에 남긴다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## Task 3: dev-cycle 스킬 정의

**Files:**
- Create: `.claude/skills/dev-cycle/SKILL.md`

**Interfaces:**
- Consumes: Task 1 의 `references/tier-rules.md`, Task 2 의 `references/archive-format.md`. 두 파일을 경로로 참조하며 내용을 복제하지 않는다.
- Produces: 호출 형식 `/dev-cycle next`, `/dev-cycle <ID>`, `/dev-cycle status`. Task 5 의 CLAUDE.md 섹션이 이 호출 형식을 안내하고, Task 6 이 이 절차를 드라이런으로 검증한다.

- [ ] **Step 1: `SKILL.md` 를 작성한다**

파일 전문은 다음과 같다.

````markdown
---
name: dev-cycle
description: Use when working through this project's backlog — runs one TODO item from planning to archive with exactly two approval gates, choosing review depth and verification scope by tier. Triggers on "/dev-cycle", "다음 작업 진행", "todo 진행", "백로그 진행".
---

# dev-cycle

`docs/dev-cycle/TODO.md` 의 항목 하나를 계획부터 아카이브 기록까지 완주시킨다.
승인 게이트는 두 곳뿐이다.

## 호출

| 형식 | 동작 |
|---|---|
| `/dev-cycle next` | 백로그에서 다음 항목을 골라 시작한다 |
| `/dev-cycle <ID>` | 지정한 항목을 시작한다. 예: `/dev-cycle INFRA-001` |
| `/dev-cycle status` | 백로그 현황만 보고하고 끝낸다 |

## 참조

- 티어 판정과 위험 경로: `references/tier-rules.md`
- TODO 및 아카이브 형식: `references/archive-format.md`

두 파일의 내용을 이 문서에 복제하지 않는다. 판정이나 기록이 필요한 시점에 해당 파일을 읽는다.

## 절차

### [0] 준비

1. `git status --short` 로 작업 트리가 깨끗한지 확인한다. 커밋되지 않은 변경이 있으면
   멈추고 사용자에게 알린다.
2. 현재 브랜치를 확인한다. `develop` 이 아니면 멈추고 사용자에게 알린다.
3. `docs/dev-cycle/TODO.md` 를 읽는다.
4. `next` 이면 `P0` → `P1` → `P2` 순으로, 같은 우선순위 안에서는 위에 있는 항목을 고른다.
   ID 가 주어졌으면 그 항목을 찾는다. 없으면 멈추고 알린다.
5. 백로그가 비어 있으면 그 사실을 알리고 종료한다.

### [1] 계획

1. `autoplan` 스킬로 실행 계획을 세운다.
2. 계획에서 건드릴 파일 목록을 뽑는다.
3. `references/tier-rules.md` 의 §3 절차로 티어를 판정한다.
4. 사용자에게 다음을 제시한다.
   - 항목 ID 와 제목
   - 실행 계획
   - 판정한 티어와 그 근거. 위험 경로에 닿았다면 어느 파일인지 명시한다
   - 그 티어에서 돌릴 리뷰 목록과 검증 범위
5. **게이트 1** — 승인을 기다린다. 승인 없이 구현을 시작하지 않는다.

### [2] 구현

1. 계획대로 구현한다.
2. `git diff --stat` 으로 실제 변경 규모를 확인하고 티어를 재판정한다. 상위 티어에
   해당하면 올린다. 낮게 나와도 내리지 않는다.
3. 티어에 해당하는 리뷰를 `references/tier-rules.md` §1 의 순서대로 실행한다.
   순서를 바꾸지 않는다.
4. 각 리뷰의 지적 사항을 반영한다. 반영하지 않기로 한 지적은 그 이유를 남겨 두었다가
   게이트 2 에서 함께 보고한다.

### [3] 검증

1. 티어에 해당하는 검증을 실행한다.
2. 실패하면 고치고 다시 실행한다. 실패를 남긴 채 다음 단계로 넘어가지 않는다.

### [4] 마감

1. 커밋 메시지 초안을 작성한다.
2. `references/archive-format.md` 의 §5 와 §6 형식으로 기록할 내용을 작성한다.
3. 사용자에게 다음을 제시한다.
   - 커밋 메시지
   - 변경 파일 목록과 증감
   - 리뷰 결과 요약. 반영하지 않은 지적이 있으면 그 이유를 함께 적는다
   - 검증 결과
   - 아카이브에 남길 기록
4. **게이트 2** — 승인을 기다린다.
5. 승인되면 한 커밋에 다음을 모두 담는다.
   - 구현 변경
   - `docs/dev-cycle/TODO.md` 에서 해당 항목 제거
   - `docs/dev-cycle/archive/daily/YYYY-MM-DD.md` 에 상세 추가
   - `docs/dev-cycle/archive/YYYY-MM.md` 에 요약 한 줄 추가와 통계 갱신
   - 위험 경로에 해당하는 파일이 새로 생겼으면 `references/tier-rules.md` §2 갱신

## 규칙

- TODO 에 없는 작업을 즉흥으로 시작하지 않는다. 진행 중에 발견한 개선점은 `TODO.md` 에
  새 항목으로 추가하고, 지금 항목을 마저 끝낸다.
- 게이트를 건너뛰지 않는다. 사소해 보이는 항목도 두 게이트를 모두 거친다.
- 티어를 낮추지 않는다.
- 리뷰 순서를 바꾸지 않는다.
- 검증 실패를 남긴 채 커밋하지 않는다.

## 중단

어느 단계에서든 중단되면 작업 트리를 그대로 두고 상황을 보고한다. `TODO.md` 의 항목은
제거하지 않는다. 다음 호출에서 같은 항목을 이어서 진행할 수 있다.
````

- [ ] **Step 2: frontmatter 가 유효한지 확인한다**

```bash
python3 - <<'PY'
from pathlib import Path
t = Path('.claude/skills/dev-cycle/SKILL.md').read_text()
assert t.startswith('---\n'), 'frontmatter 가 첫 줄에서 시작하지 않습니다'
fm = t.split('---\n')[1]
assert 'name: dev-cycle' in fm, 'name 필드가 없거나 값이 다릅니다'
assert 'description:' in fm, 'description 필드가 없습니다'
print('OK: frontmatter 유효')
PY
```

기대 결과: `OK: frontmatter 유효`

- [ ] **Step 3: 참조하는 레퍼런스 파일이 실재하는지 확인한다**

```bash
for f in tier-rules archive-format; do
  p=".claude/skills/dev-cycle/references/$f.md"
  [ -f "$p" ] && echo "OK: $p" || echo "MISSING: $p"
done
```

기대 결과:
```
OK: .claude/skills/dev-cycle/references/tier-rules.md
OK: .claude/skills/dev-cycle/references/archive-format.md
```

- [ ] **Step 4: 레퍼런스 내용이 복제되지 않았는지 확인한다**

`SKILL.md` 는 두 레퍼런스를 경로로 참조만 해야 한다. 위험 경로 목록이나 기록 형식 예시가
`SKILL.md` 안에 들어가면 두 곳이 어긋나기 시작한다.

```bash
if grep -qE 'engine/(grade|generator|vcp)_|services/paper_trading' .claude/skills/dev-cycle/SKILL.md; then
  echo "FAIL: 위험 경로 목록이 SKILL.md 에 복제되었습니다"
else
  echo "OK: 레퍼런스 내용 복제 없음"
fi
```

기대 결과: `OK: 레퍼런스 내용 복제 없음`

- [ ] **Step 5: 커밋한다**

```bash
git add .claude/skills/dev-cycle/SKILL.md
git commit -m "$(cat <<'MSG'
feat(dev-cycle): 사이클 오케스트레이터 스킬 추가

TODO 항목 하나를 준비·계획·구현·검증·마감 다섯 단계로 완주시킨다.
승인 게이트는 계획 확정과 저장소 반영 두 지점에만 둔다.

티어 판정과 기록 형식은 references/ 아래 두 파일을 참조하며
내용을 복제하지 않는다. 갱신 주기가 다르기 때문이다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## Task 4: dev-workflow 감사 에이전트

**Files:**
- Create: `.claude/agents/dev-workflow.md`

**Interfaces:**
- Consumes: Task 2 의 `archive-format.md` §2 카테고리 약어와 §4 TODO 항목 형식, Task 1 의 티어 판정 규칙
- Produces: 카테고리 이름 하나를 입력받아 감사 리포트와 `TODO.md` 형식의 항목 초안을 돌려주는 서브에이전트. 하위 프로젝트 B 가 이 에이전트를 카테고리마다 한 번씩 호출한다.

- [ ] **Step 1: 디렉터리를 만든다**

```bash
mkdir -p .claude/agents
```

- [ ] **Step 2: `dev-workflow.md` 를 작성한다**

파일 전문은 다음과 같다.

````markdown
---
name: dev-workflow
description: 이 저장소의 한 기능 카테고리를 감사해 개선 항목 초안을 산출한다. 코드를 수정하지 않고 읽기만 한다. 카테고리 이름(챗봇, 종가베팅, VCP, 수급·백테스트, 프론트엔드, 인프라) 하나를 입력받는다.
model: opus
---

너는 이 저장소의 한 기능 카테고리를 감사하는 역할을 맡는다. 코드를 고치지 않는다.
읽고, 문제를 찾고, 개선 항목의 초안을 만들어 돌려주는 것이 전부다.

## 입력

카테고리 이름 하나를 받는다. 각 카테고리의 담당 경로는
`.claude/skills/dev-cycle/references/archive-format.md` §2 표에 있다. 그 표를 먼저 읽고
담당 경로를 확정한 뒤에 감사를 시작한다.

## 하지 않을 일

- 코드를 수정하지 않는다. `Edit` 과 `Write` 를 코드 파일에 쓰지 않는다.
- 사이클을 실행하지 않는다. 리뷰 스킬이나 검증 명령을 돌리지 않는다.
- 담당 경로 밖을 감사하지 않는다. 다른 카테고리에서 문제를 발견하면 그 사실만 한 줄로
  적고 넘어간다.

## 감사 관점

담당 경로의 코드를 읽고 다음 다섯 가지를 본다. 각 관점마다 근거가 되는 파일과 줄 번호를
반드시 함께 적는다. 근거를 댈 수 없는 지적은 적지 않는다.

1. **깨진 동작** — 실제로 잘못된 결과를 내는 지점. 대소문자 불일치, 상태 구분 누락,
   경계 조건 처리 누락 따위가 해당한다.
2. **중복** — 같은 로직이 여러 곳에 흩어져 한쪽만 고쳐질 위험이 있는 지점.
3. **과잉 설계** — 구현체가 하나뿐인 추상화, 아무도 바꾸지 않는 설정값, 호출자가 하나뿐인
   계층.
4. **비대한 파일** — 한 파일이 여러 책임을 지고 있어 한 번에 파악하기 어려운 지점.
   줄 수만으로 판단하지 않고 책임의 개수로 판단한다.
5. **검증 공백** — 분기나 점수 계산 로직인데 대응하는 테스트가 없는 지점.

## 출력

두 부분으로 이루어진 보고서를 돌려준다.

### 1부: 감사 리포트

```markdown
# AUDIT-<카테고리 약어> — <카테고리 이름> 감사

**감사 범위**: <읽은 경로 목록>
**읽은 파일 수**: N개 / 총 M줄

## 1. 깨진 동작
### 1.1 <제목>
- 위치: `path/to/file.py:123`
- 증상: <관찰된 잘못된 동작>
- 원인: <코드상의 근거>
- 영향: <사용자나 다른 모듈이 받는 영향>

## 2. 중복
## 3. 과잉 설계
## 4. 비대한 파일
## 5. 검증 공백

## 요약
| 관점 | 발견 | 그중 P0 | P1 | P2 |
|---|---|---|---|---|
| 깨진 동작 | 3 | 2 | 1 | 0 |
```

발견이 없는 절은 `없음` 한 줄만 적고 넘어간다. 억지로 채우지 않는다.

### 2부: TODO 항목 초안

`.claude/skills/dev-cycle/references/archive-format.md` §4 형식을 그대로 따른다.
일련번호는 `docs/dev-cycle/` 전체에서 해당 약어의 최대 번호를 확인한 뒤 그다음부터 매긴다.

```markdown
### [CHAT-003] 챗봇 스트리밍 폴백 정리
- 카테고리: 챗봇 | 티어: T2 | 근거: AUDIT-CHAT §2.1
- [ ] response_flow_fallback 의 중복 경로 통합
- [ ] 모델 체인 실패 시 UI 표기 추가
- [ ] 회귀 테스트 추가
```

티어는 `.claude/skills/dev-cycle/references/tier-rules.md` §3 절차로 판정한다. 건드릴
파일이 위험 경로에 닿으면 줄 수와 무관하게 `T3` 이다.

우선순위는 다음 기준으로 매긴다.
- `P0`: 사용자에게 잘못된 값이 보이거나 동작이 깨져 있다
- `P1`: 지금은 동작하지만 곧 문제가 될 구조다
- `P2`: 고치면 나아지지만 급하지 않다

## 분량

리포트는 한 카테고리당 발견 사항 열 건 이내로 추린다. 사소한 지적을 늘리기보다 실제로
고칠 가치가 있는 것만 남긴다. 항목 초안도 같은 기준으로 다섯 개 이내가 적당하다.
````

- [ ] **Step 3: frontmatter 를 검증한다**

```bash
python3 - <<'PY'
from pathlib import Path
t = Path('.claude/agents/dev-workflow.md').read_text()
assert t.startswith('---\n'), 'frontmatter 가 첫 줄에서 시작하지 않습니다'
fm = t.split('---\n')[1]
for field in ('name: dev-workflow', 'description:', 'model:'):
    assert field in fm, f'{field} 가 없습니다'
print('OK: 에이전트 frontmatter 유효')
PY
```

기대 결과: `OK: 에이전트 frontmatter 유효`

- [ ] **Step 4: 커밋한다**

```bash
git add .claude/agents/dev-workflow.md
git commit -m "$(cat <<'MSG'
feat(dev-cycle): 감사 전담 dev-workflow 서브에이전트 추가

카테고리 하나를 읽기 전용으로 감사해 리포트와 TODO 항목 초안을
돌려준다. 사이클은 실행하지 않는다.

감사는 수십 개 파일을 읽어야 하므로 메인 세션과 컨텍스트를 분리한다.
카테고리 약어와 항목 형식, 티어 판정은 references/ 를 참조한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## Task 5: 백로그 단일화

**Files:**
- Create: `docs/dev-cycle/TODO.md`
- Create: `docs/dev-cycle/archive/2026-09.md`
- Modify: `CLAUDE.md` (Important Notes 4번 경로 정정, Remaining Refactoring Tasks 섹션 교체)
- Delete: `docs/plans/TO_DO_LIST.md`

**Interfaces:**
- Consumes: Task 2 의 `archive-format.md` §2 ID 규칙, §3 우선순위, §4 TODO 형식, §6 월별 요약 형식. Task 3 의 호출 형식 `/dev-cycle next`
- Produces: 백로그의 단일 관리 지점 `docs/dev-cycle/TODO.md` 와 그 안의 항목 `JONGGA-001` `FLOW-001` `FLOW-002` `INFRA-001` `INFRA-002`. Task 6 이 이 파일을 대상으로 드라이런을 수행한다.

**이관 대상 조사 결과 (2026-09-01 실측)**

| 출처 | 원 항목 | 판정 |
|---|---|---|
| CLAUDE.md | `market_gate.py` 리팩토링 — 400줄 `_get_global_data()` 추출 | **폐기.** 이미 완료되었다. `engine/market_gate.py` 는 216줄이고 8개 모듈로 분리되어 있으며, `_get_global_data()` 의 docstring 에 `(Refactored)` 가 명시되어 있다. 400줄짜리 함수는 존재하지 않는다 |
| CLAUDE.md | `generator.py` 리팩토링 — 인라인 페이즈 로직을 `phases.py` 클래스로 교체 | **유효.** `engine/generator.py` 의 import 목록에 `engine.phases` 가 없다. `JONGGA-001` 로 이관한다 |
| CLAUDE.md | 타입 힌트 보강 | **유효.** `INFRA-002` 로 이관한다 |
| `docs/plans/TO_DO_LIST.md` | KIS API 장중 실시간 수급 연동 | **유효.** 외부 계좌 개설이 선행되어야 하므로 P2 다. `FLOW-001` 로 이관한다 |
| `docs/plans/TO_DO_LIST.md` | (보류) 섹터별 수급 등 분석 고도화 | **유효.** `FLOW-002` 로 이관한다 |
| 신규 | 파이썬 의존성 버전 고정 | `requirements.txt` 에 버전 핀이 하나도 없고 `google-genai` 는 1.62 대 2.21 로 메이저 격차가 있다. 하위 프로젝트 D 의 진입점이며 `INFRA-001`, P0 다 |

- [ ] **Step 1: 디렉터리를 만든다**

```bash
mkdir -p docs/dev-cycle/archive/daily
```

`daily/` 는 첫 완료 기록이 생길 때까지 비어 있다. git 은 빈 디렉터리를 추적하지 않으므로
`.gitkeep` 을 두지 않는다. 형식 문서에 "파일이 없으면 그날 첫 완료 시점에 새로 만든다"고
명시되어 있다.

- [ ] **Step 2: `docs/dev-cycle/TODO.md` 를 작성한다**

파일 전문은 다음과 같다.

````markdown
# TODO

> 백로그의 단일 관리 지점입니다. 형식은
> `.claude/skills/dev-cycle/references/archive-format.md` 를 따릅니다.
> 완료된 항목은 아카이브로 옮기고 이 파일에서 제거합니다.
> 진행은 `/dev-cycle next` 로 시작합니다.

## P0 — 즉시

### [INFRA-001] 파이썬 의존성 버전 고정
- 카테고리: 인프라 | 티어: T3 | 근거: 2026-09-01 실측
- [ ] `requirements.txt` 의 14개 패키지에 버전 핀 적용
- [ ] `google-genai` 1.62 → 2.x 호환성 확인 (`engine/genai_client.py` 호출부)
- [ ] `requirements.updated.txt` 와의 관계 정리 또는 폐기
- [ ] pytest 전체 통과 확인

## P1 — 이번 주기

### [JONGGA-001] generator.py 의 인라인 페이즈 로직을 phases 모듈로 교체
- 카테고리: 종가베팅 | 티어: T3 | 근거: CLAUDE.md 이관
- [ ] `engine/generator.py` 의 인라인 페이즈 로직 범위 확정
- [ ] `engine/phases_*.py` 의 기존 클래스로 대체
- [ ] 신호 생성 결과가 교체 전후로 동일한지 확인
- [ ] 회귀 테스트 추가

## P2 — 대기

### [FLOW-001] 장중 실시간 수급 데이터 KIS API 연동
- 카테고리: 수급·백테스트 | 티어: T3 | 근거: docs/plans/TO_DO_LIST.md 이관
- 선행 조건: 한국투자증권 계좌 개설과 Open API 키 발급이 끝나야 착수할 수 있습니다
- [ ] `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO` 를 `.env.example` 에 추가
- [ ] `engine/kis_collector.py` 연동 활성화
- [ ] 장중 수급 점수가 0 으로 고정되던 동작 해소 확인
- [ ] 참고 문서: `docs/KIS_API_GUIDE.md`

### [FLOW-002] 수급 데이터 분석 고도화
- 카테고리: 수급·백테스트 | 티어: T2 | 근거: docs/plans/TO_DO_LIST.md 이관
- [ ] 섹터별 수급 집계 설계
- [ ] 기존 `services/investor_trend_5day_service.py` 와의 경계 정리

### [INFRA-002] 타입 힌트 보강
- 카테고리: 인프라 | 티어: T2 | 근거: CLAUDE.md 이관
- [ ] 타입 힌트가 없는 공개 함수 범위 확정
- [ ] 우선순위가 높은 모듈부터 보강
- [ ] 한 번에 300줄을 넘기지 않도록 여러 항목으로 나누어 진행
````

- [ ] **Step 3: `docs/dev-cycle/archive/2026-09.md` 를 작성한다**

아직 완료 항목이 없으므로 헤더와 빈 표만 둔다.

````markdown
# 2026-09 요약

| 완료일 | ID | 제목 | 카테고리 | 티어 | 커밋 |
|---|---|---|---|---|---|

## 통계
- 완료 0건 (P0 0 · P1 0 · P2 0)
- 순 코드 증감 0줄
````

- [ ] **Step 4: CLAUDE.md 의 잘못된 스케줄러 경로를 정정한다**

`app/services/scheduler.py` 는 실재하지 않는다. 실제 경로는 `services/scheduler.py` 이며
관련 모듈이 네 개다.

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('CLAUDE.md')
s = p.read_text()
old = "4. **Scheduler**: `app/services/scheduler.py` (15:20, 15:40 KST)"
new = "4. **Scheduler**: `services/scheduler.py` (15:20, 15:40 KST). 관련 모듈: `scheduler_jobs.py`, `scheduler_loop.py`, `scheduler_runtime_status_service.py`"
assert s.count(old) == 1, "정정 대상 줄을 찾지 못했습니다"
p.write_text(s.replace(old, new))
print("OK: 스케줄러 경로 정정")
PY
```

기대 결과: `OK: 스케줄러 경로 정정`

- [ ] **Step 5: CLAUDE.md 의 Remaining Refactoring Tasks 섹션을 교체한다**

```bash
python3 - <<'PY'
from pathlib import Path
p = Path('CLAUDE.md')
s = p.read_text()
old = """## Remaining Refactoring Tasks

1. **Refactor market_gate.py** (HIGH): Extract 400-line `_get_global_data()` using `DataSourceStrategy`
2. **Refactor generator.py** (HIGH): Replace inline phase logic with `phases.py` classes
3. **Add type hints** (MEDIUM): Missing in many functions
"""
new = """## 개발 사이클 — dev-cycle

작업은 `docs/dev-cycle/TODO.md` 의 항목 단위로 진행합니다.
`/dev-cycle next` 로 시작하며, 절차와 티어 규칙은 스킬 정의를 따릅니다.

- 백로그: `docs/dev-cycle/TODO.md` (단일 관리 지점)
- 완료 기록: `docs/dev-cycle/archive/` (월별 요약 + 일별 상세)
- 사이클 절차: `.claude/skills/dev-cycle/SKILL.md`
- 티어와 위험 경로: `.claude/skills/dev-cycle/references/tier-rules.md`
- 기록 형식: `.claude/skills/dev-cycle/references/archive-format.md`
- 카테고리 감사: `dev-workflow` 에이전트

승인 게이트는 두 곳입니다. 계획이 확정되는 시점과 결과가 저장소에 반영되는 시점입니다.

TODO 에 없는 작업을 즉흥으로 시작하지 않습니다. 새로 발견한 개선점은
`TODO.md` 에 항목으로 추가한 뒤 순서에 따라 처리합니다. 이 파일에 할 일 목록을
따로 적지 않습니다. 백로그가 두 곳에 존재하면 반드시 어긋납니다.
"""
assert s.count(old) == 1, "Remaining Refactoring Tasks 섹션을 찾지 못했습니다"
p.write_text(s.replace(old, new))
print("OK: 백로그 섹션 교체")
PY
```

기대 결과: `OK: 백로그 섹션 교체`

- [ ] **Step 6: `docs/plans/TO_DO_LIST.md` 를 삭제한다**

내용은 `FLOW-001` 과 `FLOW-002` 로 모두 이관되었다.

```bash
git rm docs/plans/TO_DO_LIST.md
```

- [ ] **Step 7: 백로그가 한 곳에만 있는지 검증한다**

```bash
echo "--- TODO.md 항목 수 ---"
grep -cE '^### \[[A-Z]+-[0-9]{3}\]' docs/dev-cycle/TODO.md
echo "--- CLAUDE.md 에 남은 할 일 목록 ---"
if grep -qE 'Remaining Refactoring Tasks|^[0-9]+\. \*\*Refactor ' CLAUDE.md; then
  echo "FAIL: CLAUDE.md 에 백로그가 남아 있습니다"
else
  echo "OK: CLAUDE.md 에 백로그 없음"
fi
echo "--- 삭제 확인 ---"
[ -e docs/plans/TO_DO_LIST.md ] && echo "FAIL: TO_DO_LIST.md 가 남아 있습니다" || echo "OK: TO_DO_LIST.md 삭제됨"
echo "--- 잘못된 경로 잔존 확인 ---"
grep -q 'app/services/scheduler.py' CLAUDE.md && echo "FAIL: 잘못된 경로가 남아 있습니다" || echo "OK: 경로 정정됨"
```

기대 결과:
```
--- TODO.md 항목 수 ---
5
--- CLAUDE.md 에 남은 할 일 목록 ---
OK: CLAUDE.md 에 백로그 없음
--- 삭제 확인 ---
OK: TO_DO_LIST.md 삭제됨
--- 잘못된 경로 잔존 확인 ---
OK: 경로 정정됨
```

- [ ] **Step 8: 기록 파일이 git 추적 대상인지 검증한다**

커밋 `30645f0` 에서 `.gitignore` 예외를 등록했으므로 추적되어야 한다.

```bash
git check-ignore -v docs/dev-cycle/TODO.md docs/dev-cycle/archive/2026-09.md 2>&1 \
  && echo "FAIL: 기록 파일이 무시되고 있습니다" \
  || echo "OK: 기록 파일이 추적 대상입니다"
```

기대 결과: `OK: 기록 파일이 추적 대상입니다`

- [ ] **Step 9: 커밋한다**

```bash
git add docs/dev-cycle CLAUDE.md
git commit -m "$(cat <<'MSG'
refactor(dev-cycle): 백로그를 docs/dev-cycle/TODO.md 한 곳으로 통합

CLAUDE.md 의 Remaining Refactoring Tasks 와 docs/plans/TO_DO_LIST.md 에
나뉘어 있던 백로그를 TODO.md 로 모으고, CLAUDE.md 에는 dev-cycle 섹션과
포인터만 남긴다.

market_gate.py 리팩토링 항목은 이관하지 않고 폐기한다. 해당 파일은 이미
216줄 8개 모듈로 분리되어 있고 400줄짜리 _get_global_data() 는 존재하지
않는다. 완료된 작업이 백로그에 남아 있던 것이다.

아울러 실재하지 않는 경로 app/services/scheduler.py 를 services/scheduler.py
로 정정한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## Task 6: 통합 검증

**Files:**
- Modify: 없음 (검증만 수행한다. 실패가 나오면 해당 태스크로 돌아가 고친다)

**Interfaces:**
- Consumes: Task 1~5 의 모든 산출물
- Produces: 스펙 §11 성공 기준 다섯 항목의 충족 여부 판정

- [ ] **Step 1: 산출물이 모두 존재하는지 확인한다**

```bash
for f in \
  .claude/skills/dev-cycle/SKILL.md \
  .claude/skills/dev-cycle/references/tier-rules.md \
  .claude/skills/dev-cycle/references/archive-format.md \
  .claude/agents/dev-workflow.md \
  docs/dev-cycle/TODO.md \
  docs/dev-cycle/archive/2026-09.md ; do
  [ -f "$f" ] && echo "OK   $f" || echo "MISS $f"
done
```

기대 결과: 여섯 줄 모두 `OK` 로 시작한다.

- [ ] **Step 2: 실행 코드가 추가되지 않았는지 확인한다 (성공 기준 5)**

```bash
git diff --stat 30645f0..HEAD -- '*.py' '*.ts' '*.tsx' '*.js' | tail -1
```

기대 결과: 출력이 없다. 파이썬이나 TypeScript 파일이 한 줄도 변경되지 않아야 한다.

출력이 있으면 어떤 태스크가 코드를 건드린 것이므로, 해당 변경을 되돌리고 그 태스크를
다시 수행한다.

- [ ] **Step 3: 백로그가 한 곳에만 있는지 확인한다 (성공 기준 4)**

```bash
echo "TODO.md 항목: $(grep -cE '^### \[[A-Z]+-[0-9]{3}\]' docs/dev-cycle/TODO.md)"
echo "다른 곳의 백로그:"
grep -rlE '^[0-9]+\. \*\*Refactor |Remaining Refactoring Tasks' CLAUDE.md AGENTS.md docs/*.md 2>/dev/null || echo "  (없음)"
```

기대 결과:
```
TODO.md 항목: 5
다른 곳의 백로그:
  (없음)
```

`AGENTS.md` 나 다른 문서에서 백로그가 발견되면, 그 내용이 `TODO.md` 에 이미 있는지
확인하고 중복이면 원본에서 제거한다.

- [ ] **Step 4: 위험 경로 목록이 실재하는 파일만 담고 있는지 다시 확인한다**

```bash
RULES=.claude/skills/dev-cycle/references/tier-rules.md
missing=0
for f in $(grep -oE '`[^`]+\.py`' "$RULES" | tr -d '`' | sort -u); do
  [ -e "$f" ] || { echo "MISSING: $f"; missing=1; }
done
[ $missing -eq 0 ] && echo "OK: 위험 경로 파이썬 파일 47개가 모두 실재합니다"
```

기대 결과: `OK: 위험 경로 파이썬 파일 47개가 모두 실재합니다`

- [ ] **Step 5: `/dev-cycle status` 드라이런을 수행한다 (성공 기준 1, 2)**

세션에서 `/dev-cycle status` 를 호출한다.

기대 동작:
1. `docs/dev-cycle/TODO.md` 를 읽는다
2. 항목 다섯 개를 우선순위별로 보고한다 (P0 1건, P1 1건, P2 3건)
3. 다음에 진행할 항목으로 `INFRA-001` 을 지목한다
4. 아무것도 구현하지 않고 끝낸다

기대와 다르게 동작하면 `SKILL.md` 의 [0] 준비 절차를 고친다. 특히 우선순위 정렬 규칙
(`P0` → `P1` → `P2`, 같은 우선순위에서는 위쪽 우선)이 제대로 읽히는지 확인한다.

- [ ] **Step 6: 티어 판정 드라이런을 수행한다 (성공 기준 2)**

`INFRA-001` 의 티어가 실제로 `T3` 으로 판정되는지 확인한다. 이 항목은 `requirements.txt` 와
`engine/genai_client.py` 를 건드리는데, `genai_client.py` 는 위험 경로 목록에 없다.
따라서 판정 근거는 위험 경로 접촉이 아니라 변경 규모여야 한다.

```bash
echo "genai_client.py 가 위험 경로에 있는가:"
grep -q 'engine/genai_client.py' .claude/skills/dev-cycle/references/tier-rules.md \
  && echo "  있음 → 위험 경로 접촉으로 T3" \
  || echo "  없음 → 변경 규모로 판정해야 함"
```

기대 결과: `없음 → 변경 규모로 판정해야 함`

`TODO.md` 의 `INFRA-001` 메타 줄에는 `티어: T3` 이 적혀 있다. 이 판정의 근거는
의존성 14개의 버전 핀과 SDK 메이저 업그레이드가 300줄을 넘길 가능성이 크다는 예상이다.
계획 단계에서 실제 변경 범위를 확정한 뒤 게이트 1 에서 이 판정을 사용자에게 다시 제시한다.

- [ ] **Step 7: 검증 결과를 보고한다**

스펙 §11 성공 기준 다섯 항목에 대해 충족 여부를 표로 보고한다.

| # | 성공 기준 | 검증 방법 | 결과 |
|---|---|---|---|
| 1 | 항목 하나가 계획부터 아카이브까지 완주하며 게이트가 정확히 두 곳이다 | Step 5 드라이런 | |
| 2 | 티어에 따라 리뷰와 검증 범위가 달라진다 | Step 6 판정 확인 | |
| 3 | 완료 항목이 TODO 에서 사라지고 두 아카이브에 남는다 | 하위 프로젝트 D 의 첫 완주에서 확인 | 보류 |
| 4 | 백로그가 한 곳에만 존재한다 | Step 3 | |
| 5 | 새로 추가된 실행 코드가 없다 | Step 2 | |

3번은 실제로 항목을 하나 완주시켜야 확인할 수 있다. 하위 프로젝트 D(`INFRA-001`)를
이 체계의 첫 실전 사례로 삼아 그때 검증한다.

- [ ] **Step 8: 검증 결과를 커밋한다**

검증 과정에서 고친 내용이 있을 때만 커밋한다. 고칠 것이 없었으면 이 단계를 건너뛴다.

```bash
git add -A .claude docs/dev-cycle
git commit -m "$(cat <<'MSG'
fix(dev-cycle): 통합 검증에서 발견한 문제 수정

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh
MSG
)"
```

---

## 완료 후

이 계획을 모두 마치면 하위 프로젝트 A 가 끝난다. 다음은 D(패키지 업데이트)이며,
`/dev-cycle INFRA-001` 로 시작한다. 이것이 체계의 첫 실전 검증 사례이자 성공 기준 3번의
확인 수단이다.

이어서 B(카테고리별 감사)를 `dev-workflow` 에이전트로 여섯 번 수행하고, 그 산출물을
`TODO.md` 에 적재한 뒤 C(개선 실행)로 넘어간다.
