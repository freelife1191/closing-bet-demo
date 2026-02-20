#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
BUILD_SCENARIO = KIT_ROOT / "scripts" / "video" / "build_showcase_scenarios.py"
BUILD_SYNC = KIT_ROOT / "scripts" / "video" / "build_sync_plans.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_showcase_generates_scene_plan_and_sync_bundle(tmp_path: Path) -> None:
    out_dir = tmp_path / "scenarios"

    scenario_result = _run(
        [
            "python3",
            str(BUILD_SCENARIO),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert scenario_result.returncode == 0, scenario_result.stderr or scenario_result.stdout

    sync_result = _run(
        [
            "python3",
            str(BUILD_SYNC),
            "--scenario-dir",
            str(out_dir),
            "--out-dir",
            str(out_dir),
        ]
    )
    assert sync_result.returncode == 0, sync_result.stderr or sync_result.stdout

    scene_plan_path = out_dir / "scene_plan_short.json"
    sync_bundle_path = out_dir / "sync_bundle_short.json"

    assert scene_plan_path.exists(), f"missing scene plan: {scene_plan_path}"
    assert sync_bundle_path.exists(), f"missing sync bundle: {sync_bundle_path}"

    scene_plan = json.loads(scene_plan_path.read_text(encoding="utf-8"))
    sync_bundle = json.loads(sync_bundle_path.read_text(encoding="utf-8"))

    scene_rows = scene_plan.get("scenes")
    assert isinstance(scene_rows, list) and scene_rows
    first_scene = scene_rows[0]
    assert "scene_id" in first_scene
    assert "target_sec" in first_scene
    assert "narration_ko" in first_scene
    assert "subtitle_cue" in first_scene

    sync_rows = sync_bundle.get("scenes")
    assert isinstance(sync_rows, list) and sync_rows
    first_sync = sync_rows[0]
    assert "scene_id" in first_sync
    assert "target_sec" in first_sync
    assert "tts_rate" in first_sync
    assert "caption_cues" in first_sync
    assert "scene_extend_budget_sec" in first_sync
