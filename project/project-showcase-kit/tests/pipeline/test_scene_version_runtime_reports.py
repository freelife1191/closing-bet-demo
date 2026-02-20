#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
VALIDATE_SCRIPT = KIT_ROOT / "scripts" / "pipeline" / "validate_outputs.py"
RUNTIME_REPORT_SCRIPT = KIT_ROOT / "scripts" / "pipeline" / "stage_runtime_budget_report.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_validate_outputs_includes_scene_and_runtime_budget_checks(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    out_json = tmp_path / "validation_report.json"
    out_md = tmp_path / "validation_report.md"

    _write_json(
        manifest,
        {
            "language": "ko+en",
            "scenes": [{"id": "scene-01", "durationSec": 3, "narration": "테스트"}],
        },
    )

    # baseline required artifacts for validator
    (WORKSPACE_ROOT / "project" / "video" / "audio").mkdir(parents=True, exist_ok=True)
    (WORKSPACE_ROOT / "project" / "video" / "captions").mkdir(parents=True, exist_ok=True)
    (WORKSPACE_ROOT / "project" / "out").mkdir(parents=True, exist_ok=True)
    (WORKSPACE_ROOT / "project" / "video" / "evidence").mkdir(parents=True, exist_ok=True)

    (WORKSPACE_ROOT / "project" / "video" / "audio" / "narration.wav").write_bytes(b"RIFF")
    (WORKSPACE_ROOT / "project" / "video" / "captions" / "subtitles.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\n테스트\n", encoding="utf-8")
    (WORKSPACE_ROOT / "project" / "out" / "final_showcase.mp4").write_bytes(b"\x00")

    _write_json(
        WORKSPACE_ROOT / "project" / "video" / "audio" / "narration.json",
        {"durationSeconds": 1.0, "requestedLanguage": "ko+en", "tracks": []},
    )
    _write_json(
        WORKSPACE_ROOT / "project" / "video" / "captions" / "subtitles.json",
        {"captions": [{"endSec": 1.0}]},
    )
    _write_json(
        WORKSPACE_ROOT / "project" / "video" / "evidence" / "render_meta.json",
        {"durationSec": 1.1, "output": str((WORKSPACE_ROOT / "project" / "out" / "final_showcase.mp4").resolve())},
    )

    _write_json(WORKSPACE_ROOT / "project" / "video" / "evidence" / "scene_gate_report.json", {"status": "pass"})
    _write_json(WORKSPACE_ROOT / "project" / "video" / "evidence" / "version_gate_report.json", {"status": "pass"})

    runtime_report = tmp_path / "runtime_budget_report.json"
    runtime_md = tmp_path / "runtime_budget_report.md"
    runtime_result = _run(
        [
            "python3",
            str(RUNTIME_REPORT_SCRIPT),
            "--elapsed-seconds",
            "2400",
            "--budget-minutes",
            "120",
            "--out-json",
            str(runtime_report),
            "--out-md",
            str(runtime_md),
        ]
    )
    assert runtime_result.returncode == 0, runtime_result.stderr or runtime_result.stdout

    _write_json(WORKSPACE_ROOT / "project" / "video" / "evidence" / "runtime_budget_report.json", json.loads(runtime_report.read_text(encoding="utf-8")))

    result = _run(
        [
            str(VALIDATE_SCRIPT),
            "--manifest",
            str(manifest),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    checks = {row.get("name"): row.get("status") for row in payload.get("checks", [])}

    assert checks.get("scene_gate_pass") == "pass"
    assert checks.get("version_gate_pass") == "pass"
    assert checks.get("runtime_budget_within_120min") == "pass"
