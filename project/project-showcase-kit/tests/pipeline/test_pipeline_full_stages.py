#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
RUN_STAGE = KIT_ROOT / "scripts/pipeline/run_stage.sh"
RUN_ALL = KIT_ROOT / "scripts/pipeline/run_all.sh"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_manifest(path: Path, scene_count: int = 2) -> None:
    scenes = []
    for idx in range(scene_count):
        scene_no = idx + 1
        scenes.append(
            {
                "id": f"scene-{scene_no:02d}",
                "title": f"씬 {scene_no}",
                "narration": f"KR 마켓 패키지 stage 테스트 문장 {scene_no}",
                "durationSec": 6,
            }
        )

    path.write_text(
        json.dumps({"language": "ko+en", "scenes": scenes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_record_stage_creates_scene_outputs(tmp_path: Path) -> None:
    manifest = tmp_path / "record_manifest.json"
    _write_manifest(manifest, scene_count=2)

    result = _run([str(RUN_STAGE), "record", "--manifest", str(manifest), "--headless", "false"])

    assert result.returncode == 0, result.stderr or result.stdout
    scene_file = WORKSPACE_ROOT / "project/video/scenes/scene-01.mp4"
    summary_file = WORKSPACE_ROOT / "project/video/evidence/record_summary.json"
    assert scene_file.exists()
    assert summary_file.exists()


def test_captions_stage_creates_srt_and_json(tmp_path: Path) -> None:
    manifest = tmp_path / "captions_manifest.json"
    _write_manifest(manifest, scene_count=2)

    # voice is required before captions in full flow
    voice_result = _run([str(RUN_STAGE), "voice", "--manifest", str(manifest), "--language", "ko+en", "--tts-engine", "qwen-local-cmd"])
    assert voice_result.returncode == 0, voice_result.stderr or voice_result.stdout

    result = _run([str(RUN_STAGE), "captions", "--manifest", str(manifest), "--language", "ko+en"])

    assert result.returncode == 0, result.stderr or result.stdout
    srt_path = WORKSPACE_ROOT / "project/video/captions/subtitles.srt"
    json_path = WORKSPACE_ROOT / "project/video/captions/subtitles.json"
    assert srt_path.exists()
    assert json_path.exists()


def test_render_assets_qc_and_reports_generate_outputs(tmp_path: Path) -> None:
    manifest = tmp_path / "post_manifest.json"
    _write_manifest(manifest, scene_count=2)

    assert _run([str(RUN_STAGE), "record", "--manifest", str(manifest)]).returncode == 0
    assert _run([str(RUN_STAGE), "voice", "--manifest", str(manifest), "--language", "ko+en", "--tts-engine", "qwen-local-cmd"]).returncode == 0
    assert _run([str(RUN_STAGE), "captions", "--manifest", str(manifest), "--language", "ko+en"]).returncode == 0

    render = _run([str(RUN_STAGE), "render", "--manifest", str(manifest)])
    assets = _run([
        str(RUN_STAGE),
        "assets",
        "--manifest",
        str(manifest),
        "--language",
        "ko+en",
        "--thumbnail-mode",
        "manual",
        "--title",
        "KR 마켓 패키지 데모",
        "--subtitle",
        "단위 검증",
    ])
    qc = _run([
        str(RUN_STAGE),
        "qc",
        "--manifest",
        str(manifest),
        "--gate-a",
        "approved",
        "--gate-b",
        "approved",
        "--gate-c",
        "approved",
        "--gate-d",
        "approved",
    ])
    manager = _run([str(RUN_STAGE), "manager-report", "--manifest", str(manifest)])
    quality = _run([str(RUN_STAGE), "quality-report", "--manifest", str(manifest)])

    assert render.returncode == 0, render.stderr or render.stdout
    assert assets.returncode == 0, assets.stderr or assets.stdout
    assert qc.returncode == 0, qc.stderr or qc.stdout
    assert manager.returncode == 0, manager.stderr or manager.stdout
    assert quality.returncode == 0, quality.stderr or quality.stdout

    assert (WORKSPACE_ROOT / "project/out/final_showcase.mp4").exists()
    assert (WORKSPACE_ROOT / "project/out/final_showcase.ko.mp4").exists()
    assert (WORKSPACE_ROOT / "project/out/final_showcase.en.mp4").exists()
    assert (WORKSPACE_ROOT / "project/video/assets/thumbnail_prompt.md").exists()
    assert (WORKSPACE_ROOT / "project/video/assets/thumbnail_prompt_nanobanana_pro.md").exists()
    assert (WORKSPACE_ROOT / "project/video/assets/youtube_description_prompt.md").exists()
    assert (WORKSPACE_ROOT / "project/video/assets/project_overview_doc_prompt.md").exists()
    assert (WORKSPACE_ROOT / "project/video/assets/ppt_slide_prompt_gemini.md").exists()
    assert (WORKSPACE_ROOT / "project/video/evidence/signoff.json").exists()
    assert (WORKSPACE_ROOT / "project/video/evidence/manager_report.json").exists()
    assert (WORKSPACE_ROOT / "project/video/evidence/quality_report.json").exists()


def test_run_all_full_pipeline_generates_all_core_artifacts(tmp_path: Path) -> None:
    manifest = tmp_path / "full_manifest.json"
    _write_manifest(manifest, scene_count=2)

    result = _run(
        [
            str(RUN_ALL),
            "--manifest",
            str(manifest),
            "--language",
            "ko+en",
            "--tts-engine",
            "qwen-local-cmd",
            "--strict-tts",
            "false",
            "--skip-health",
            "--auto-start-services",
            "false",
            "--yes",
        ]
    )

    assert result.returncode == 0, result.stderr or result.stdout

    expected = [
        WORKSPACE_ROOT / "project/video/evidence/record_summary.json",
        WORKSPACE_ROOT / "project/video/captions/subtitles.srt",
        WORKSPACE_ROOT / "project/out/final_showcase.mp4",
        WORKSPACE_ROOT / "project/out/final_showcase.ko.mp4",
        WORKSPACE_ROOT / "project/out/final_showcase.en.mp4",
        WORKSPACE_ROOT / "project/video/assets/thumbnail_prompt.md",
        WORKSPACE_ROOT / "project/video/assets/thumbnail_prompt_nanobanana_pro.md",
        WORKSPACE_ROOT / "project/video/assets/youtube_description_prompt.md",
        WORKSPACE_ROOT / "project/video/assets/project_overview_doc_prompt.md",
        WORKSPACE_ROOT / "project/video/assets/ppt_slide_prompt_gemini.md",
        WORKSPACE_ROOT / "project/video/evidence/signoff.json",
        WORKSPACE_ROOT / "project/video/evidence/manager_report.json",
        WORKSPACE_ROOT / "project/video/evidence/quality_report.json",
        WORKSPACE_ROOT / "project/video/evidence/validation_report.json",
    ]
    for path in expected:
        assert path.exists(), f"missing expected artifact: {path}"
