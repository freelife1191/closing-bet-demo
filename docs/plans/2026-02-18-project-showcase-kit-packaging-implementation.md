# Project Showcase Kit Packaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `project-showcase-kit` as a reusable packaging system with canonical `psk-*` skills, dynamic project init auditing, and generated installers for Codex/ClaudeCode/Gemini/Antigravity.

**Architecture:** Keep a single canonical skill set in root `/.agent/skills/psk-*`, manage conversion rules in `project/project-showcase-kit-src`, and generate tool-specific artifacts into `project/project-showcase-kit-dist` through a tested Python builder. Apply TDD for all new mapping/build logic and only then migrate skills/references.

**Tech Stack:** Python 3.11+, pytest, shell scripts, YAML, markdown docs, existing `scripts/skills` utilities.

---

**Execution skills to use while implementing:** `@test-driven-development`, `@verification-before-completion`, `@systematic-debugging`

### Task 1: Add packaging manifest contract and schema validation

**Files:**
- Create: `project/project-showcase-kit-src/manifest/skills-map.yaml`
- Create: `project/project-showcase-kit-src/manifest/tool-map.yaml`
- Create: `scripts/packaging/manifest_loader.py`
- Test: `tests/packaging/test_manifest_loader.py`

**Step 1: Write the failing test**

```python
from scripts.packaging.manifest_loader import load_skills_map

def test_load_skills_map_requires_psk_prefix(tmp_path):
    manifest = tmp_path / "skills-map.yaml"
    manifest.write_text(
        "skills:\n  - source: video-manifest-planner\n    target: psk-video-manifest-planner\n",
        encoding="utf-8",
    )
    payload = load_skills_map(manifest)
    assert payload["skills"][0]["target"].startswith("psk-")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_manifest_loader.py::test_load_skills_map_requires_psk_prefix -v`  
Expected: FAIL with `ModuleNotFoundError` for `scripts.packaging.manifest_loader`.

**Step 3: Write minimal implementation**

```python
from pathlib import Path
import yaml

def load_skills_map(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for item in data.get("skills", []):
        if not item["target"].startswith("psk-"):
            raise ValueError("target must start with psk-")
    return data
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_manifest_loader.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-src/manifest/skills-map.yaml \
  project/project-showcase-kit-src/manifest/tool-map.yaml \
  scripts/packaging/manifest_loader.py \
  tests/packaging/test_manifest_loader.py
git commit -m "feat: add project-showcase-kit manifest contracts"
```

### Task 2: Implement deterministic skill rename planner

**Files:**
- Create: `scripts/packaging/skill_rename_plan.py`
- Test: `tests/packaging/test_skill_rename_plan.py`

**Step 1: Write the failing test**

```python
from scripts.packaging.skill_rename_plan import build_rename_plan

def test_build_rename_plan_includes_qwen_and_video_families():
    plan = build_rename_plan()
    targets = {item["target"] for item in plan}
    assert "psk-video-manifest-planner" in targets
    assert "psk-qwen3-tts-universal" in targets
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_skill_rename_plan.py::test_build_rename_plan_includes_qwen_and_video_families -v`  
Expected: FAIL with missing module/function.

**Step 3: Write minimal implementation**

```python
def build_rename_plan() -> list[dict]:
    sources = [
        "video-manifest-planner",
        "playwright-scene-recorder",
        "qwen3-tts-universal",
    ]
    return [{"source": name, "target": f"psk-{name}"} for name in sources]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_skill_rename_plan.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/packaging/skill_rename_plan.py tests/packaging/test_skill_rename_plan.py
git commit -m "feat: add deterministic psk skill rename planner"
```

### Task 3: Create safe rename executor for root `/.agent/skills`

**Files:**
- Create: `scripts/packaging/rename_skills.py`
- Test: `tests/packaging/test_rename_skills.py`

**Step 1: Write the failing test**

```python
from pathlib import Path
from scripts.packaging.rename_skills import rename_skill_dir

def test_rename_skill_dir_moves_folder(tmp_path: Path):
    src = tmp_path / "video-manifest-planner"
    src.mkdir()
    (src / "SKILL.md").write_text("name: video-manifest-planner", encoding="utf-8")
    dst = tmp_path / "psk-video-manifest-planner"
    rename_skill_dir(src, dst)
    assert dst.exists()
    assert not src.exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_rename_skills.py::test_rename_skill_dir_moves_folder -v`  
Expected: FAIL with import error.

**Step 3: Write minimal implementation**

```python
from pathlib import Path

def rename_skill_dir(source: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(target)
    source.rename(target)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_rename_skills.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/packaging/rename_skills.py tests/packaging/test_rename_skills.py
git commit -m "feat: add safe skill rename executor"
```

### Task 4: Rewrite repository references from legacy names to `psk-*`

**Files:**
- Create: `scripts/packaging/rewrite_skill_references.py`
- Test: `tests/packaging/test_rewrite_skill_references.py`

**Step 1: Write the failing test**

```python
from scripts.packaging.rewrite_skill_references import rewrite_text

def test_rewrite_text_replaces_legacy_skill_names():
    text = ".agent/skills/video-manifest-planner/SKILL.md"
    mapping = {"video-manifest-planner": "psk-video-manifest-planner"}
    assert rewrite_text(text, mapping) == ".agent/skills/psk-video-manifest-planner/SKILL.md"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_rewrite_skill_references.py::test_rewrite_text_replaces_legacy_skill_names -v`  
Expected: FAIL due missing module/function.

**Step 3: Write minimal implementation**

```python
def rewrite_text(text: str, mapping: dict[str, str]) -> str:
    result = text
    for source, target in mapping.items():
        result = result.replace(f"/{source}/", f"/{target}/")
        result = result.replace(source, target)
    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_rewrite_skill_references.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/packaging/rewrite_skill_references.py tests/packaging/test_rewrite_skill_references.py
git commit -m "feat: add psk skill reference rewriting helper"
```

### Task 5: Add canonical `psk-project-init-audit` skill

**Files:**
- Create: `.agent/skills/psk-project-init-audit/SKILL.md`
- Create: `.agent/skills/psk-project-init-audit/commands/run.md`
- Create: `.agent/skills/psk-project-init-audit/commands/validate.md`
- Create: `.agent/skills/psk-project-init-audit/scripts/run_init_audit.py`
- Create: `.agent/skills/psk-project-init-audit/config/defaults.template.yaml`
- Create: `.agent/skills/psk-project-init-audit/references/README.md`
- Test: `tests/skills/test_psk_project_init_audit_structure.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_psk_project_init_audit_has_required_dirs():
    root = Path(".agent/skills/psk-project-init-audit")
    for name in ["commands", "scripts", "config", "samples", "references"]:
        assert (root / name).exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_psk_project_init_audit_structure.py -v`  
Expected: FAIL because directory does not exist yet.

**Step 3: Write minimal implementation**

```python
# scripts/run_init_audit.py
from pathlib import Path
import json

def main(project_root: Path) -> None:
    output = {
        "project_root": str(project_root),
        "run": {"discovered": []},
        "stop": {"discovered": []},
    }
    evidence = project_root / "project/video/evidence/project_audit.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_psk_project_init_audit_structure.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add .agent/skills/psk-project-init-audit tests/skills/test_psk_project_init_audit_structure.py
git commit -m "feat: add psk project init audit canonical skill"
```

### Task 6: Build `project-showcase-kit-src` templates for four tools

**Files:**
- Create: `project/project-showcase-kit-src/templates/common/README.template.md`
- Create: `project/project-showcase-kit-src/templates/codex/install.template.sh`
- Create: `project/project-showcase-kit-src/templates/claudecode/install.template.sh`
- Create: `project/project-showcase-kit-src/templates/gemini/install.template.sh`
- Create: `project/project-showcase-kit-src/templates/antigravity/install.template.sh`
- Test: `tests/packaging/test_tool_templates.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_all_tool_templates_exist():
    root = Path("project/project-showcase-kit-src/templates")
    for tool in ["codex", "claudecode", "gemini", "antigravity"]:
        assert (root / tool / "install.template.sh").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_tool_templates.py::test_all_tool_templates_exist -v`  
Expected: FAIL due missing files.

**Step 3: Write minimal implementation**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$ROOT_DIR/.agent/skills"
cp -R "$ROOT_DIR/project/project-showcase-kit-dist/skills/canonical/psk-"* "$ROOT_DIR/.agent/skills/"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_tool_templates.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-src/templates tests/packaging/test_tool_templates.py
git commit -m "feat: add project-showcase-kit per-tool install templates"
```

### Task 7: Implement dist builder (`src -> dist`) with idempotency

**Files:**
- Create: `project/project-showcase-kit-src/scripts/build_dist.py`
- Test: `tests/packaging/test_build_dist.py`

**Step 1: Write the failing test**

```python
import subprocess
import sys
from pathlib import Path

def test_build_dist_generates_all_installers(tmp_path: Path):
    script = Path("project/project-showcase-kit-src/scripts/build_dist.py")
    subprocess.run([sys.executable, str(script), "--repo-root", str(tmp_path)], check=True)
    for tool in ["codex", "claudecode", "gemini", "antigravity"]:
        assert (tmp_path / "project/project-showcase-kit-dist/install" / tool / "install.sh").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_build_dist.py::test_build_dist_generates_all_installers -v`  
Expected: FAIL with missing module.

**Step 3: Write minimal implementation**

```python
from pathlib import Path

def build_dist(repo_root: Path) -> None:
    tools = ["codex", "claudecode", "gemini", "antigravity"]
    for tool in tools:
        dst = repo_root / "project/project-showcase-kit-dist/install" / tool / "install.sh"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_build_dist.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-src/scripts/build_dist.py tests/packaging/test_build_dist.py
git commit -m "feat: add src-to-dist packaging builder"
```

### Task 8: Add unified installer entrypoint for users

**Files:**
- Create: `project/project-showcase-kit-dist/install/install_all.sh`
- Create: `project/project-showcase-kit-dist/install/README.md`
- Test: `tests/packaging/test_install_scripts_contract.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_install_all_mentions_supported_tools():
    script = Path("project/project-showcase-kit-dist/install/install_all.sh").read_text(encoding="utf-8")
    assert "codex" in script
    assert "claudecode" in script
    assert "gemini" in script
    assert "antigravity" in script
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_install_scripts_contract.py::test_install_all_mentions_supported_tools -v`  
Expected: FAIL due missing file.

**Step 3: Write minimal implementation**

```bash
#!/usr/bin/env bash
set -euo pipefail
TOOL="${1:-}"
case "$TOOL" in
  codex|claudecode|gemini|antigravity) ;;
  *) echo "usage: install_all.sh <codex|claudecode|gemini|antigravity>"; exit 1 ;;
esac
bash "$(dirname "$0")/$TOOL/install.sh"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_install_scripts_contract.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-dist/install tests/packaging/test_install_scripts_contract.py
git commit -m "feat: add unified installer entrypoint"
```

### Task 9: Migrate existing skill references in scripts/docs to `psk-*`

**Files:**
- Modify: `scripts/skills/target_skills.yaml`
- Modify: `project/jobs/QUICK_START.md`
- Modify: `project/jobs/STEP4.md`
- Modify: `scripts/video/gen_voice.py`
- Modify: `scripts/pipeline/preflight_check.sh`
- Test: `tests/skills/test_psk_reference_consistency.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_target_skills_uses_psk_prefix():
    text = Path("scripts/skills/target_skills.yaml").read_text(encoding="utf-8")
    assert ".agent/skills/psk-" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/skills/test_psk_reference_consistency.py::test_target_skills_uses_psk_prefix -v`  
Expected: FAIL while legacy names are still present.

**Step 3: Write minimal implementation**

```yaml
skills:
  - name: psk-video-manifest-planner
    path: .agent/skills/psk-video-manifest-planner
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/skills/test_psk_reference_consistency.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/skills/target_skills.yaml \
  project/jobs/QUICK_START.md \
  project/jobs/STEP4.md \
  scripts/video/gen_voice.py \
  scripts/pipeline/preflight_check.sh \
  tests/skills/test_psk_reference_consistency.py
git commit -m "refactor: migrate skill references to psk namespace"
```

### Task 10: Create required-only packaging checklist

**Files:**
- Create: `project/project-showcase-kit-dist/checklists/required.md`
- Modify: `project/jobs/STEP_INDEX.md`
- Test: `tests/packaging/test_required_checklist.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_required_checklist_contains_gate_a_to_d():
    text = Path("project/project-showcase-kit-dist/checklists/required.md").read_text(encoding="utf-8")
    for gate in ["Gate A", "Gate B", "Gate C", "Gate D"]:
        assert gate in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_required_checklist.py::test_required_checklist_contains_gate_a_to_d -v`  
Expected: FAIL due missing file.

**Step 3: Write minimal implementation**

```markdown
# Required Packaging Checklist
- [ ] Init audit complete
- [ ] Preflight pass
- [ ] Gate A approved
- [ ] Gate B approved
- [ ] Gate C approved
- [ ] Gate D approved
- [ ] validation_report / manager_report / signoff present
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_required_checklist.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-dist/checklists/required.md \
  project/jobs/STEP_INDEX.md \
  tests/packaging/test_required_checklist.py
git commit -m "docs: add required-only packaging checklist"
```

### Task 11: Add package-focused `.gitignore` rules for dist hygiene

**Files:**
- Modify: `.gitignore`
- Test: `tests/packaging/test_gitignore_packaging_rules.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_gitignore_excludes_generated_video_artifacts():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "project/video/scenes/" in text
    assert "project/video/audio/" in text
    assert "project/video/evidence/*.zip" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_gitignore_packaging_rules.py::test_gitignore_excludes_generated_video_artifacts -v`  
Expected: FAIL because rules are incomplete.

**Step 3: Write minimal implementation**

```gitignore
# Project showcase generated artifacts
project/video/scenes/
project/video/audio/
project/video/evidence/*.zip
project/video/evidence/tmp_videos/
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_gitignore_packaging_rules.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add .gitignore tests/packaging/test_gitignore_packaging_rules.py
git commit -m "chore: add packaging artifact ignore rules"
```

### Task 12: Verification sweep and release-ready report

**Files:**
- Create: `project/project-showcase-kit-dist/README.md`
- Create: `docs/plans/reports/project-showcase-kit-packaging-summary.md`

**Step 1: Write the failing test**

```python
from pathlib import Path

def test_dist_readme_lists_install_targets():
    text = Path("project/project-showcase-kit-dist/README.md").read_text(encoding="utf-8")
    assert "Codex" in text
    assert "ClaudeCode" in text
    assert "Gemini" in text
    assert "Antigravity" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/packaging/test_dist_readme.py::test_dist_readme_lists_install_targets -v`  
Expected: FAIL due missing file.

**Step 3: Write minimal implementation**

```markdown
# project-showcase-kit-dist
Supported installs:
- Codex
- ClaudeCode
- Gemini
- Antigravity
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/packaging/test_dist_readme.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add project/project-showcase-kit-dist/README.md \
  docs/plans/reports/project-showcase-kit-packaging-summary.md \
  tests/packaging/test_dist_readme.py
git commit -m "docs: add project-showcase-kit dist usage summary"
```

## Final verification commands (must run before completion claim)

```bash
pytest tests/packaging -v
pytest tests/skills/test_psk_project_init_audit_structure.py -v
pytest tests/skills/test_psk_reference_consistency.py -v
python scripts/skills/validate_skill_structure.py --strict
```

Expected:
- All tests PASS.
- Skill structure validation PASS with `psk-*` paths.
- Dist installers exist for all four tools.
