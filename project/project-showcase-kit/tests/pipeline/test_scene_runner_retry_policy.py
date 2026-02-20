#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
RUN_STAGE = KIT_ROOT / "scripts" / "pipeline" / "run_stage.sh"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_manifest(path: Path) -> None:
    payload = {
        "language": "ko+en",
        "scenes": [
            {"id": "scene-01", "durationSec": 8, "narration": "씬 1"},
            {"id": "scene-02", "durationSec": 8, "narration": "씬 2"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_scene_runner_retries_failed_scene_up_to_three_times(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    failure_plan = tmp_path / "failure_plan.json"
    report_json = tmp_path / "scene_runner_report.json"
    report_md = tmp_path / "scene_runner_report.md"

    _write_manifest(manifest)
    failure_plan.write_text(
        json.dumps(
            {
                "scene-01": ["fail", "fail", "pass"],
                "scene-02": ["pass"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run(
        [
            str(RUN_STAGE),
            "scene-runner",
            "--manifest",
            str(manifest),
            "--scene-failure-plan",
            str(failure_plan),
            "--scene-runner-out-json",
            str(report_json),
            "--scene-runner-out-md",
            str(report_md),
        ]
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    scenes = {row["scene_id"]: row for row in payload.get("scenes", [])}

    assert scenes["scene-01"]["attempt_count"] == 3
    assert scenes["scene-02"]["attempt_count"] == 1
    assert payload.get("status") == "pass"
