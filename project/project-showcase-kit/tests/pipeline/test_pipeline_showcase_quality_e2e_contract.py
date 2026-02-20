#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
RUN_ALL = KIT_ROOT / "scripts" / "pipeline" / "run_all.sh"


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


def test_run_all_generates_gate_reports_and_multilang_outputs(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    script_out = tmp_path / "script.md"

    scene_path = WORKSPACE_ROOT / "project" / "video" / "scenes" / "scene-01.mp4"
    summary_path = WORKSPACE_ROOT / "project" / "video" / "evidence" / "record_summary.json"
    summary_md = WORKSPACE_ROOT / "project" / "video" / "evidence" / "record_summary.md"

    _write_json(
        manifest,
        {
            "language": "ko+en",
            "scenes": [
                {
                    "id": "scene-01",
                    "title": "씬 1",
                    "durationSec": 3,
                    "narration": "테스트 씬",
                    "narrationByLang": {"ko": "테스트 씬", "en": "Test scene"},
                    "url": "http://127.0.0.1:3500/dashboard/kr",
                    "actions": [{"type": "wait", "ms": 200}],
                }
            ],
        },
    )
    script_out.write_text("# script\n", encoding="utf-8")

    scene_path.parent.mkdir(parents=True, exist_ok=True)
    scene_path.write_bytes(b"\x00")

    _write_json(
        summary_path,
        {
            "manifest": str(manifest.resolve()),
            "status": "pass",
            "scenes": [
                {
                    "id": "scene-01",
                    "status": "pass",
                    "output": str(scene_path.resolve()),
                    "durationSec": 3.0,
                    "sceneUrl": "http://127.0.0.1:3500/dashboard/kr",
                }
            ],
        },
    )
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text("# Record Summary\n\n- status: pass\n", encoding="utf-8")

    result = _run(
        [
            str(RUN_ALL),
            "--manifest",
            str(manifest),
            "--script-out",
            str(script_out),
            "--showcase-scenario",
            "false",
            "--manifest-from-scenario",
            "false",
            "--language",
            "ko+en",
            "--tts-engine",
            "auto-local",
            "--qwen-local-timeout-sec",
            "1",
            "--strict-tts",
            "false",
            "--skip-health",
            "--auto-start-services",
            "false",
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    expected = [
        WORKSPACE_ROOT / "project" / "out" / "final_showcase.ko.mp4",
        WORKSPACE_ROOT / "project" / "out" / "final_showcase.en.mp4",
        WORKSPACE_ROOT / "project" / "video" / "evidence" / "scene_gate_report.json",
        WORKSPACE_ROOT / "project" / "video" / "evidence" / "version_gate_report.json",
        WORKSPACE_ROOT / "project" / "video" / "evidence" / "runtime_budget_report.json",
    ]
    for path in expected:
        assert path.exists(), f"missing expected artifact: {path}"
