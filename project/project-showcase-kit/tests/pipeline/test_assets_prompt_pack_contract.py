#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
RUN_STAGE = KIT_ROOT / "scripts" / "pipeline" / "run_stage.sh"


REQUIRED_PROMPT_FILES = [
    "thumbnail_prompt_nanobanana_pro.md",
    "youtube_description_prompt.md",
    "project_overview_doc_prompt.md",
    "ppt_slide_prompt_gemini.md",
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_assets_stage_generates_required_prompt_pack_markdown(tmp_path: Path) -> None:
    out_dir = tmp_path / "assets"

    result = _run(
        [
            str(RUN_STAGE),
            "assets",
            "--thumbnail-mode",
            "manual",
            "--title",
            "Smart Money Bot KR Showcase",
            "--subtitle",
            "Scene Gate + Sync Precision",
            "--language",
            "ko+en",
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    assets_dir = WORKSPACE_ROOT / "project" / "video" / "assets"
    for name in REQUIRED_PROMPT_FILES:
        path = assets_dir / name
        assert path.exists(), f"missing prompt file: {path}"
        text = path.read_text(encoding="utf-8")
        assert "System Prompt" in text
        assert "Output Format" in text
