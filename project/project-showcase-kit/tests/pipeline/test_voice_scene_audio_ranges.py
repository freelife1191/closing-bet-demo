#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
GEN_VOICE = KIT_ROOT / "scripts" / "video" / "gen_voice.py"


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
            {"id": "scene-01", "durationSec": 4, "narration": "첫 번째 씬 설명입니다."},
            {"id": "scene-02", "durationSec": 6, "narration": "두 번째 씬 설명입니다."},
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_voice_metadata_contains_scene_audio_ranges(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    out_wav = WORKSPACE_ROOT / "project" / "video" / "audio" / "narration.scene-range-test.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    _write_manifest(manifest)

    result = _run(
        [
            "python3",
            str(GEN_VOICE),
            "--manifest",
            str(manifest),
            "--out",
            str(out_wav),
            "--engine",
            "qwen-local-cmd",
            "--language",
            "ko",
            "--allow-silence-fallback",
            "--silence-seconds",
            "6",
            "--qwen-local-timeout-sec",
            "1",
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    meta_path = out_wav.with_suffix(".json")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    tracks = payload.get("tracks") or []
    assert tracks

    first_track = tracks[0]
    ranges = first_track.get("sceneAudioRanges")
    assert isinstance(ranges, list) and ranges
    assert ranges[0].get("sceneId") == "scene-01"
    assert "startSec" in ranges[0] and "endSec" in ranges[0]
