#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
SCENE_GATE = KIT_ROOT / "scripts" / "pipeline" / "stage_scene_gate.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_metrics(path: Path, boundary_delta: float) -> None:
    payload = {
        "scenes": [
            {
                "scene_id": "scene-01",
                "scene_av_boundary_delta_sec": boundary_delta,
                "scene_caption_voice_end_delta_sec": 0.06,
                "action_execution_rate": 0.97,
                "static_frame_ratio": 0.30,
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_scene_gate_fails_when_boundary_delta_exceeds_threshold(tmp_path: Path) -> None:
    metrics = tmp_path / "scene_metrics.json"
    out_json = tmp_path / "scene_gate_report.json"
    out_md = tmp_path / "scene_gate_report.md"
    _write_metrics(metrics, boundary_delta=0.20)

    result = _run(
        [
            "python3",
            str(SCENE_GATE),
            "--input-json",
            str(metrics),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert result.returncode == 1
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload.get("status") == "fail"
    first = (payload.get("scenes") or [])[0]
    assert first.get("checks", {}).get("scene_av_boundary_delta_sec") == "fail"


def test_scene_gate_passes_when_all_metrics_within_threshold(tmp_path: Path) -> None:
    metrics = tmp_path / "scene_metrics.json"
    out_json = tmp_path / "scene_gate_report.json"
    out_md = tmp_path / "scene_gate_report.md"
    _write_metrics(metrics, boundary_delta=0.08)

    result = _run(
        [
            "python3",
            str(SCENE_GATE),
            "--input-json",
            str(metrics),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    assert result.returncode == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload.get("status") == "pass"
