#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
SCRIPT_PATH = KIT_ROOT / "scripts" / "video" / "build_showcase_scenarios.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_build_scenarios_writes_three_versions_with_scene_table(tmp_path: Path) -> None:
    out_dir = tmp_path / "scenarios"

    result = _run(
        [
            "python3",
            str(SCRIPT_PATH),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    for name in ("scenario_short.md", "scenario_normal.md", "scenario_detail.md"):
        path = out_dir / name
        assert path.exists(), f"missing scenario file: {path}"
        text = path.read_text(encoding="utf-8")
        assert "| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |" in text
        assert "Smart Money Bot" in text
        assert "| S" in text

    short_text = (out_dir / "scenario_short.md").read_text(encoding="utf-8")
    normal_text = (out_dir / "scenario_normal.md").read_text(encoding="utf-8")
    detail_text = (out_dir / "scenario_detail.md").read_text(encoding="utf-8")

    assert "targetDurationSec: 60" in short_text
    assert "Jongga V2" in normal_text
    assert "project-showcase-kit" in detail_text
