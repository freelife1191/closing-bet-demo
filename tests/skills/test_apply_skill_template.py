#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path

from scripts.skills.apply_skill_template import apply_skill_template


def test_template_applier_creates_missing_directories_and_stub_files(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo-skill\ndescription: Use when demo\n---\n", encoding="utf-8")

    result = apply_skill_template(skill_dir)

    assert result["changed"] is True
    assert (skill_dir / "commands").is_dir()
    assert (skill_dir / "scripts").is_dir()
    assert (skill_dir / "config").is_dir()
    assert (skill_dir / "samples").is_dir()
    assert (skill_dir / "references").is_dir()
    assert (skill_dir / "commands" / "run.md").is_file()
    assert (skill_dir / "scripts" / "smoke.sh").is_file()
