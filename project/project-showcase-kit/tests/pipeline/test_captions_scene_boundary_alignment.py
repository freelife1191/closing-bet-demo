#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
STAGE_CAPTIONS = KIT_ROOT / "scripts" / "pipeline" / "stage_captions.py"


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
        "language": "ko",
        "scenes": [
            {"id": "scene-01", "durationSec": 5, "narration": "씬 하나 설명"},
            {"id": "scene-02", "durationSec": 5, "narration": "씬 둘 설명"},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_voice_meta(path: Path) -> None:
    payload = {
        "durationSeconds": 10.0,
        "requestedLanguage": "ko",
        "tracks": [
            {
                "languageCode": "ko",
                "sceneAudioRanges": [
                    {"sceneId": "scene-01", "startSec": 0.0, "endSec": 5.0},
                    {"sceneId": "scene-02", "startSec": 5.0, "endSec": 10.0},
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_captions_respects_scene_boundaries_with_strict_threshold(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    voice_meta = tmp_path / "voice_meta.json"
    out_srt = tmp_path / "subtitles.srt"
    out_json = tmp_path / "subtitles.json"

    _write_manifest(manifest)
    _write_voice_meta(voice_meta)

    result = _run(
        [
            "python3",
            str(STAGE_CAPTIONS),
            "--manifest",
            str(manifest),
            "--language",
            "ko",
            "--voice-meta",
            str(voice_meta),
            "--out-srt",
            str(out_srt),
            "--out-json",
            str(out_json),
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert float(payload.get("sceneBoundaryMaxDeltaSec", 999)) <= 0.15
    assert int(payload.get("sceneBoundaryViolationCount", 999)) == 0
