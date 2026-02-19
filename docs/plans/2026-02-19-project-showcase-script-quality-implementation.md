# Project Showcase Script Quality Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `Smart Money Bot` 본체 기능을 정확한 용어로 소개하는 3종(간소화/보통/디테일) 시나리오/대본/TTS/자막 동기화 산출물을 자동 생성하고, 품질 게이트로 잘림/오역을 사전에 차단한다.

**Architecture:** 기존 `project-showcase-kit` 파이프라인을 유지한 채, 설계 전용 레이어(시나리오 생성/동기화 계획/용어 감사)를 추가한다. 핵심은 `scenario generator -> sync planner -> terminology guardian`의 선행 검증 체인을 만든 뒤, 기존 `voice/captions/render/validate`로 연결하는 방식이다.

**Tech Stack:** Python 3.11, Bash, pytest, JSON/Markdown, 기존 `project/project-showcase-kit/scripts/pipeline/*`

---

사전 적용 스킬: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`

### Task 1: 용어 감사기(terminology guardian) 구현

**Files:**
- Create: `project/project-showcase-kit/scripts/video/validate_script_terminology.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_script_terminology_validator.py`
- Modify: `project/project-showcase-kit/scripts/lib/kr_text_policy.py`

**Step 1: Write the failing test**

```python
def test_validator_fails_on_mismatched_terms(tmp_path: Path):
    # scenario text에 의도적으로 비표준 용어 삽입
    # expected: status == fail, findings에 rule_id 포함
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_script_terminology_validator.py::test_validator_fails_on_mismatched_terms`
Expected: FAIL (`validate_script_terminology.py` 미존재 또는 main/validator 함수 없음)

**Step 3: Write minimal implementation**

```python
# validate_script_terminology.py
# - 입력: scenario md/json, manifest json
# - 규칙: 브랜드명/금지어/UI 명칭 정합성
# - 출력: term_audit_report.json|md
# - 에러 발견 시 exit 1
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_script_terminology_validator.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/validate_script_terminology.py \
  project/project-showcase-kit/tests/pipeline/test_script_terminology_validator.py \
  project/project-showcase-kit/scripts/lib/kr_text_policy.py
git commit -m "feat: add script terminology guardian validator"
```

### Task 2: 3버전 시나리오 생성기 구현

**Files:**
- Create: `project/project-showcase-kit/scripts/video/build_showcase_scenarios.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_build_showcase_scenarios.py`
- Create: `project/video/scenarios/scenario_short.md`
- Create: `project/video/scenarios/scenario_normal.md`
- Create: `project/video/scenarios/scenario_detail.md`

**Step 1: Write the failing test**

```python
def test_build_scenarios_writes_three_versions_with_scene_table(tmp_path: Path):
    # expected files: short/normal/detail
    # expected columns: Scene, Time, Screen, Action, Narration, TTSRate, SubtitleCue
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_showcase_scenarios.py::test_build_scenarios_writes_three_versions_with_scene_table`
Expected: FAIL (생성 스크립트 없음)

**Step 3: Write minimal implementation**

```python
# build_showcase_scenarios.py
# - 입력: 길이 목표(60/120/180~240), 기능 커버리지 정의
# - 출력: scenario_short.md / scenario_normal.md / scenario_detail.md
# - 디테일 버전은 설명량에 따라 180~240초 가변 생성
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_showcase_scenarios.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/build_showcase_scenarios.py \
  project/project-showcase-kit/tests/pipeline/test_build_showcase_scenarios.py \
  project/video/scenarios/scenario_short.md \
  project/video/scenarios/scenario_normal.md \
  project/video/scenarios/scenario_detail.md
git commit -m "feat: generate 3-version showcase scenario docs"
```

### Task 3: TTS/자막 동기화 계획기(sync planner) 구현

**Files:**
- Create: `project/project-showcase-kit/scripts/video/build_sync_plans.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py`
- Create: `project/video/scenarios/tts_plan_short.json`
- Create: `project/video/scenarios/tts_plan_normal.json`
- Create: `project/video/scenarios/tts_plan_detail.json`
- Create: `project/video/scenarios/caption_plan_short.json`
- Create: `project/video/scenarios/caption_plan_normal.json`
- Create: `project/video/scenarios/caption_plan_detail.json`

**Step 1: Write the failing test**

```python
def test_sync_plan_enforces_no_cut_policy(tmp_path: Path):
    # scene별 speech_est_sec와 target_sec 비교
    # expected: overflow 발생 시 adjustment_step 기록
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py::test_sync_plan_enforces_no_cut_policy`
Expected: FAIL (sync planner 미구현)

**Step 3: Write minimal implementation**

```python
# build_sync_plans.py
# - 기준 속도: 4.6 syll/sec
# - 허용 범위: 4.4~4.8
# - 보정 순서: speed -> compression -> scene_extend
# - 출력: tts_plan_*.json, caption_plan_*.json
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/build_sync_plans.py \
  project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py \
  project/video/scenarios/tts_plan_short.json \
  project/video/scenarios/tts_plan_normal.json \
  project/video/scenarios/tts_plan_detail.json \
  project/video/scenarios/caption_plan_short.json \
  project/video/scenarios/caption_plan_normal.json \
  project/video/scenarios/caption_plan_detail.json
git commit -m "feat: add tts-caption sync planning artifacts"
```

### Task 4: 신규 스킬 `psk-kr-script-terminology-guardian` 추가

**Files:**
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/SKILL.md`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/commands/run.md`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/commands/validate.md`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/commands/recover.md`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/scripts/smoke.sh`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/config/defaults.template.yaml`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/references/README.md`
- Create: `project/project-showcase-kit/skills/psk-kr-script-terminology-guardian/samples/README.md`
- Modify: `project/project-showcase-kit/docs/SKILLS_GUIDE.md`

**Step 1: Write the failing test**

```python
def test_skill_structure_terminology_guardian_exists():
    # validate_skill_structure.py로 신규 스킬 구조 검증
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-kr-script-terminology-guardian`
Expected: FAIL (스킬 디렉토리/필수 파일 누락)

**Step 3: Write minimal implementation**

```text
- SKILL.md에 mission/inputs/outputs/verification/failure-recovery 정의
- run.md에서 validate_script_terminology.py 실행 계약 명시
```

**Step 4: Run test to verify it passes**

Run: `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-kr-script-terminology-guardian`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/skills/psk-kr-script-terminology-guardian \
  project/project-showcase-kit/docs/SKILLS_GUIDE.md
git commit -m "feat: add psk terminology guardian skill"
```

### Task 5: 신규 스킬 `psk-showcase-scenario-orchestrator` 추가

**Files:**
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/SKILL.md`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/commands/run.md`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/commands/validate.md`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/commands/recover.md`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/scripts/smoke.sh`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/config/defaults.template.yaml`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/references/README.md`
- Create: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/samples/README.md`
- Modify: `project/project-showcase-kit/docs/SKILLS_GUIDE.md`

**Step 1: Write the failing test**

```python
def test_skill_structure_scenario_orchestrator_exists():
    ...
```

**Step 2: Run test to verify it fails**

Run: `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-showcase-scenario-orchestrator`
Expected: FAIL

**Step 3: Write minimal implementation**

```text
- run.md에 build_showcase_scenarios.py + build_sync_plans.py + terminology validator 순차 실행 명시
- validate.md에 Gate T1~T4 체크리스트 명시
```

**Step 4: Run test to verify it passes**

Run: `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-showcase-scenario-orchestrator`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator \
  project/project-showcase-kit/docs/SKILLS_GUIDE.md
git commit -m "feat: add showcase scenario orchestration skill"
```

### Task 6: 파이프라인 연동용 진입점 추가

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/run_stage.sh`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_all.sh`
- Create: `project/project-showcase-kit/tests/pipeline/test_showcase_scenario_stage_contract.py`

**Step 1: Write the failing test**

```python
def test_run_stage_supports_showcase_scenario_generation():
    # run_stage.sh showcase-scenario 호출 시 0 반환 기대
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_showcase_scenario_stage_contract.py::test_run_stage_supports_showcase_scenario_generation`
Expected: FAIL (unsupported stage)

**Step 3: Write minimal implementation**

```bash
# run_stage.sh case 추가
# showcase-scenario)
#   python .../build_showcase_scenarios.py
#   python .../build_sync_plans.py
#   python .../validate_script_terminology.py
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_showcase_scenario_stage_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/run_stage.sh \
  project/project-showcase-kit/scripts/pipeline/run_all.sh \
  project/project-showcase-kit/tests/pipeline/test_showcase_scenario_stage_contract.py
git commit -m "feat: add showcase scenario planning stage"
```

### Task 7: 최종 산출물 품질 계약 테스트 추가

**Files:**
- Create: `project/project-showcase-kit/tests/pipeline/test_showcase_outputs_contract.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/validate_outputs.py`

**Step 1: Write the failing test**

```python
def test_showcase_contract_requires_all_three_version_outputs():
    # scenario_short/normal/detail + tts/caption plans 존재 검증
    ...


def test_showcase_contract_requires_no_term_errors():
    # term_audit_report.json status == pass
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_showcase_outputs_contract.py`
Expected: FAIL (validate_outputs 확장 전)

**Step 3: Write minimal implementation**

```python
# validate_outputs.py에 showcase artifact check 추가
# - scenario_*.md
# - tts_plan_*.json
# - caption_plan_*.json
# - term_audit_report.json status
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_showcase_outputs_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/tests/pipeline/test_showcase_outputs_contract.py \
  project/project-showcase-kit/scripts/pipeline/validate_outputs.py
git commit -m "test: enforce showcase scenario output contract"
```

### Task 8: 통합 검증 및 문서 반영

**Files:**
- Modify: `project/jobs/QUICK_START.md`
- Modify: `project/jobs/STEP_INDEX.md`
- Modify: `project/project-showcase-kit/docs/SKILLS_GUIDE.md`
- Create: `project/video/scenarios/README.md`

**Step 1: Write the failing test/check**

```text
- QUICK_START에 showcase-scenario 실행 커맨드와 pass 기준이 없다면 실패
- SKILLS_GUIDE에 신규 2개 스킬 항목이 없으면 실패
```

**Step 2: Run check to verify it fails**

Run: `rg -n "showcase-scenario|psk-kr-script-terminology-guardian|psk-showcase-scenario-orchestrator" project/jobs/QUICK_START.md project/project-showcase-kit/docs/SKILLS_GUIDE.md`
Expected: 누락 구간 확인

**Step 3: Write minimal implementation**

```markdown
# QUICK_START에 추가
./scripts/pipeline/run_stage.sh showcase-scenario --language ko+en
# 검증 기준: term_audit_report.status=pass, scenario 3종 파일 존재
```

**Step 4: Run verification suite to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline`
Expected: PASS

**Step 5: Commit**

```bash
git add project/jobs/QUICK_START.md project/jobs/STEP_INDEX.md \
  project/project-showcase-kit/docs/SKILLS_GUIDE.md project/video/scenarios/README.md
git commit -m "docs: add showcase scenario workflow and validation guide"
```

### Task 9: 최종 E2E 검증(요구사항 기준)

**Files:**
- Validate only (코드 수정 없음 가능)

**Step 1: Run full stage chain with new planning stage**

Run:

```bash
./scripts/pipeline/run_stage.sh showcase-scenario --language ko+en
./scripts/pipeline/run_all.sh --language ko+en --tts-engine qwen-local-cmd --strict-tts false --skip-health --auto-start-services false
```

Expected: `project/video/scenarios/*`, `project/video/evidence/validation_report.json` 생성

**Step 2: Verify sync and terminology evidence**

Run:

```bash
cat project/video/evidence/term_audit_report.json
cat project/video/evidence/validation_report.json
```

Expected:
- `term_audit_report.json.status == pass`
- `validation_report.json.status == pass`
- TTS/자막/렌더 커버리지 pass

**Step 3: Final commit (if needed)**

```bash
git add project/video/evidence/term_audit_report.json project/video/scenarios
git commit -m "chore: capture showcase scenario quality validation evidence"
```

