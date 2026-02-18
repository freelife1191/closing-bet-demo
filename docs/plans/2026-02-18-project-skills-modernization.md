# Project Skills Modernization (Video Pipeline) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize all project-created video pipeline skills into a structured, testable format with 100% legacy command compatibility and per-skill detailed verification reports.

**Architecture:** Build a small skill-tooling layer (`scripts/skills/*`) first, then apply templates family-by-family (`scene-*`, `video-*`, `pipeline-*`, `promo-*`, `logo-*`, `qwen3-*`). Enforce static + runtime + compatibility verification gates before marking each skill complete.

**Tech Stack:** Python 3.11, Bash, pytest, existing pipeline shell scripts, markdown docs.

---

### Task 1: Build Target Skill Inventory (RED first)

**Files:**
- Create: `scripts/skills/skill_inventory.py`
- Create: `scripts/skills/target_skills.yaml`
- Create: `tests/skills/test_skill_inventory.py`

**Step 1: Write the failing test**

```python
# tests/skills/test_skill_inventory.py
from scripts.skills.skill_inventory import load_target_skills

def test_target_skills_count_and_names():
    skills = load_target_skills("scripts/skills/target_skills.yaml")
    names = {s["name"] for s in skills}
    assert len(skills) == 18
    assert "video-orchestration-manager" in names
    assert "qwen3-tts-universal" in names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_skill_inventory.py -v`
Expected: FAIL (`ModuleNotFoundError` or missing file)

**Step 3: Write minimal implementation**

```python
# scripts/skills/skill_inventory.py
import yaml

def load_target_skills(path: str):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["skills"]
```

Add `scripts/skills/target_skills.yaml` with 18 approved skill names.

**Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_skill_inventory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/skills/skill_inventory.py scripts/skills/target_skills.yaml tests/skills/test_skill_inventory.py
git commit -m "test: add target skill inventory baseline"
```

---

### Task 2: Add Skill Structure Validator

**Files:**
- Create: `scripts/skills/validate_skill_structure.py`
- Create: `tests/skills/test_validate_skill_structure.py`

**Step 1: Write the failing test**

```python
def test_validator_flags_missing_required_sections(tmp_path):
    # create fake skill with incomplete SKILL.md
    ...
    assert result["status"] == "fail"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_validate_skill_structure.py -v`
Expected: FAIL (validator missing)

**Step 3: Write minimal implementation**

Implement checks for:
- required directories: `commands/`, `scripts/`, `config/`, `samples/`, `references/`
- required SKILL sections: Mission, Use this skill when, Quick Commands, Verification, Failure & Recovery
- trigger format in frontmatter `description: Use when ...`

**Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_validate_skill_structure.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/skills/validate_skill_structure.py tests/skills/test_validate_skill_structure.py
git commit -m "test: add skill structure validator"
```

---

### Task 3: Add Skill Template Applier

**Files:**
- Create: `scripts/skills/apply_skill_template.py`
- Create: `scripts/skills/templates/skill_skeleton/*`
- Create: `tests/skills/test_apply_skill_template.py`

**Step 1: Write the failing test**

```python
def test_template_applier_creates_missing_directories_and_stub_files():
    ...
    assert (skill_dir / "commands").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_apply_skill_template.py -v`
Expected: FAIL (applier missing)

**Step 3: Write minimal implementation**

Implement applier with non-destructive rules:
- create missing dirs/files only
- preserve existing files
- add compatibility note stubs for wrappers

**Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_apply_skill_template.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/skills/apply_skill_template.py scripts/skills/templates tests/skills/test_apply_skill_template.py
git commit -m "feat: add skill template applier"
```

---

### Task 4: Modernize `logo/promo/pipeline` Skills

**Files:**
- Modify: `.agent/skills/logo-thumbnail-prompt-designer/SKILL.md`
- Modify/Create: `.agent/skills/logo-thumbnail-prompt-designer/commands/*`
- Modify/Create: `.agent/skills/promo-asset-studio/SKILL.md`
- Modify/Create: `.agent/skills/promo-asset-studio/commands/*`
- Modify/Create: `.agent/skills/pipeline-output-validator/SKILL.md`
- Modify/Create: `.agent/skills/pipeline-output-validator/commands/*`

**Step 1: Write failing validator assertion**

Add to `tests/skills/test_validate_skill_structure.py` checks for these 3 skills.

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_validate_skill_structure.py -v`
Expected: FAIL for missing sections/dirs

**Step 3: Implement minimal modernization**

- apply template
- rewrite `description` to `Use when ...`
- add `commands/setup.md`, `commands/run.md`, `commands/validate.md`
- keep old command strings documented and callable

**Step 4: Run tests and smoke**

Run:
- `pytest tests/skills/test_validate_skill_structure.py -v`
- `python3 scripts/skills/validate_skill_structure.py --skills logo-thumbnail-prompt-designer,promo-asset-studio,pipeline-output-validator`

Expected: PASS

**Step 5: Commit**

```bash
git add .agent/skills/logo-thumbnail-prompt-designer .agent/skills/promo-asset-studio .agent/skills/pipeline-output-validator tests/skills/test_validate_skill_structure.py
git commit -m "refactor: standardize logo promo pipeline validator skills"
```

---

### Task 5: Modernize `scene-*` Skills

**Files:**
- Modify/Create: `.agent/skills/scene-script-architect/**`
- Modify/Create: `.agent/skills/scene-record-and-capture/**`
- Modify/Create: `.agent/skills/scene-subtitle-builder/**`
- Modify/Create: `.agent/skills/scene-tts-qwen/**`

**Step 1: Add failing assertions for all `scene-*` skills**

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_validate_skill_structure.py -k scene -v`
Expected: FAIL

**Step 3: Implement modernization + compatibility wrappers**

- add command docs (`manifest`, `record`, `rerun`, `captions`, `voice`)
- add `scripts/smoke_*.sh` wrappers calling existing pipeline commands
- preserve existing CLI examples

**Step 4: Run tests and smoke**

Run:
- `pytest tests/skills/test_validate_skill_structure.py -k scene -v`
- `bash .agent/skills/scene-script-architect/scripts/smoke_manifest.sh`
- `bash .agent/skills/scene-tts-qwen/scripts/smoke_voice.sh`

Expected: PASS

**Step 5: Commit**

```bash
git add .agent/skills/scene-script-architect .agent/skills/scene-record-and-capture .agent/skills/scene-subtitle-builder .agent/skills/scene-tts-qwen tests/skills/test_validate_skill_structure.py
git commit -m "refactor: standardize scene skill family"
```

---

### Task 6: Modernize `video-*` Skills (Orchestration/QC/Render)

**Files:**
- Modify/Create: `.agent/skills/video-manifest-planner/**`
- Modify/Create: `.agent/skills/video-mastering-editor/**`
- Modify/Create: `.agent/skills/video-orchestration-manager/**`
- Modify/Create: `.agent/skills/video-pipeline-orchestrator/**`
- Modify/Create: `.agent/skills/video-postproduction-remotion/**`
- Modify/Create: `.agent/skills/video-qc-gatekeeper/**`
- Modify/Create: `.agent/skills/video-quality-researcher/**`
- Modify/Create: `.agent/skills/video-copywriter-docs/**`
- Modify/Create: `.agent/skills/video-tts-local-free/**`

**Step 1: Add failing assertions for all `video-*` skills**

**Step 2: Run tests to verify failure**

Run: `pytest tests/skills/test_validate_skill_structure.py -k video -v`
Expected: FAIL

**Step 3: Implement modernization**

- structured commands per skill (`run`, `rerun`, `verify`, `report`)
- add compatibility notes and wrappers for legacy paths
- align verification sections with evidence artifact paths

**Step 4: Run validator + representative runtime checks**

Run:
- `pytest tests/skills/test_validate_skill_structure.py -k video -v`
- `./scripts/pipeline/run_stage.sh validate`
- `./scripts/pipeline/run_stage.sh manager-report`

Expected: PASS

**Step 5: Commit**

```bash
git add .agent/skills/video-manifest-planner .agent/skills/video-mastering-editor .agent/skills/video-orchestration-manager .agent/skills/video-pipeline-orchestrator .agent/skills/video-postproduction-remotion .agent/skills/video-qc-gatekeeper .agent/skills/video-quality-researcher .agent/skills/video-copywriter-docs .agent/skills/video-tts-local-free tests/skills/test_validate_skill_structure.py
git commit -m "refactor: standardize video skill family"
```

---

### Task 7: Harden `qwen3-*` Skills and Compatibility

**Files:**
- Modify: `.agent/skills/qwen3-tts-universal/SKILL.md`
- Modify/Create: `.agent/skills/qwen3-tts-universal/commands/*`
- Modify: `.agent/skills/qwen3-tts-m1-local/SKILL.md`
- Modify: `.agent/skills/qwen3-tts-m1-local/scripts/*.sh`

**Step 1: Add failing tests for compatibility assertions**

```python
def test_qwen3_m1_legacy_wrappers_redirect_to_universal():
    ...
```

**Step 2: Run test to verify failure**

Run: `pytest tests/skills -k qwen3 -v`
Expected: FAIL

**Step 3: Implement minimal fixes**

- ensure legacy wrappers redirect correctly
- ensure universal commands include `setup/init/custom/design/clone/script`
- ensure smoke test covers all modes

**Step 4: Run tests/smoke**

Run:
- `pytest tests/skills -k qwen3 -v`
- `bash .agent/skills/qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh --mode all`

Expected: PASS

**Step 5: Commit**

```bash
git add .agent/skills/qwen3-tts-universal .agent/skills/qwen3-tts-m1-local tests/skills
git commit -m "refactor: harden qwen3 skill compatibility and coverage"
```

---

### Task 8: Add Per-Skill Detailed Reporting Pipeline

**Files:**
- Create: `scripts/skills/generate_skill_modernization_report.py`
- Create: `docs/plans/reports/.gitkeep`
- Create: `tests/skills/test_generate_skill_reports.py`

**Step 1: Write failing report test**

```python
def test_report_contains_before_after_and_verification_sections():
    ...
```

**Step 2: Run to verify it fails**

Run: `pytest tests/skills/test_generate_skill_reports.py -v`
Expected: FAIL

**Step 3: Implement report generator**

Generate one report per skill:
- `docs/plans/reports/<skill>.md`

Required sections:
- baseline gaps
- applied changes
- compatibility status
- static/runtime verification logs
- residual risks

**Step 4: Run test + report generation**

Run:
- `pytest tests/skills/test_generate_skill_reports.py -v`
- `python3 scripts/skills/generate_skill_modernization_report.py --targets scripts/skills/target_skills.yaml`

Expected: PASS + report files generated

**Step 5: Commit**

```bash
git add scripts/skills/generate_skill_modernization_report.py docs/plans/reports tests/skills/test_generate_skill_reports.py
git commit -m "feat: add per-skill modernization reporting"
```

---

### Task 9: Update Master Guides and Run Final Verification Gate

**Files:**
- Modify: `.agent/skills/SKILLS_GUIDE.md`
- Modify: `project/jobs/QUICK_START.md`
- Modify: `docs/plans/2026-02-18-project-skills-modernization.md` (execution notes)

**Step 1: Add failing doc-consistency tests**

Create/extend: `tests/skills/test_skill_docs_consistency.py`

**Step 2: Run tests to verify failure**

Run: `pytest tests/skills/test_skill_docs_consistency.py -v`
Expected: FAIL

**Step 3: Implement documentation updates**

- ensure every modernized skill is listed with command entrypoints
- ensure QUICK_START references canonical skills and smoke commands
- add compatibility note for legacy aliases

**Step 4: Final verification sweep**

Run:
- `pytest tests/skills -v`
- `python3 scripts/skills/validate_skill_structure.py --targets scripts/skills/target_skills.yaml`
- `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`

Expected: all PASS

**Step 5: Commit**

```bash
git add .agent/skills/SKILLS_GUIDE.md project/jobs/QUICK_START.md tests/skills scripts/skills
git commit -m "docs: finalize skill modernization guide and verification"
```

---

### Task 10: Final Review Before Completion

**Files:**
- Modify/Create: `docs/plans/reports/summary.md`

**Step 1: Build failing completion checklist test**

Checklist must fail if any target skill lacks:
- required structure
- smoke evidence
- compatibility proof
- detailed report

**Step 2: Run to verify failure**

Run: `python3 scripts/skills/validate_skill_structure.py --strict --targets scripts/skills/target_skills.yaml`
Expected: FAIL until all items complete

**Step 3: Produce summary report**

Write:
- total skills modernized
- per-skill status matrix
- remaining risks and follow-ups

**Step 4: Run final gates**

Run:
- `pytest tests/skills -v`
- `python3 scripts/skills/generate_skill_modernization_report.py --targets scripts/skills/target_skills.yaml --summary docs/plans/reports/summary.md`

Expected: PASS and summary generated

**Step 5: Commit**

```bash
git add docs/plans/reports

git commit -m "docs: add final skill modernization summary"
```

---

## Execution Notes
- Apply @superpowers:test-driven-development discipline for each task.
- Use @superpowers:verification-before-completion before claiming done.
- For execution mode 1, use @superpowers:subagent-driven-development.
- For execution mode 2, execute in separate session with @superpowers:executing-plans.
