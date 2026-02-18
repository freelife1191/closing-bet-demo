#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import subprocess

from scripts.skills.validate_skill_structure import validate_skill_dir


def test_validator_flags_missing_required_sections(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        """---\nname: bad-skill\ndescription: This skill does something\n---\n\n# Bad Skill\n\n## Random\ntext\n""",
        encoding="utf-8",
    )

    result = validate_skill_dir(skill_dir)

    assert result["status"] == "fail"
    assert "commands" in result["missingDirectories"]
    assert "Mission" in result["missingSections"]
    assert result["descriptionStartsWithUseWhen"] is False


def test_validator_cli_runs_for_selected_skill() -> None:
    completed = subprocess.run(
        [
            "python",
            "scripts/skills/validate_skill_structure.py",
            "--skills",
            "qwen3-tts-universal",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert '"skill": "qwen3-tts-universal"' in completed.stdout
