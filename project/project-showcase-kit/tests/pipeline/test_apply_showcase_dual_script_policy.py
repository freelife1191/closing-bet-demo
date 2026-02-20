#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
APPLY_SCRIPT = KIT_ROOT / "scripts" / "video" / "apply_showcase_scenario.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_scenario(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# 보통(2분) 시나리오",
                "",
                "- targetDurationSec: 120",
                "",
                "| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| S1 | 00:00-00:12 | `/dashboard/kr` | 요약 영역 강조 | Smart Money Bot 데모를 시작합니다. | 4.6 | 오프닝 |",
                "| S2 | 00:12-00:24 | `/dashboard/kr/closing-bet` | 점수 패널 하이라이트 | Market Gate 결과를 빠르게 확인합니다. | 4.6 | 핵심 시그널 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_dual_script(path: Path, lang: str, rows: list[tuple[str, str]]) -> None:
    lines = [
        f"# showcase normal script ({lang})",
        "",
        "| Scene | Time | Screen | Narration |",
        "| --- | --- | --- | --- |",
    ]
    for scene_id, narration in rows:
        lines.append(f"| {scene_id} | 00:00-00:12 | `/dashboard/kr` | {narration} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_apply_showcase_fails_when_english_script_missing(tmp_path: Path) -> None:
    scenario = tmp_path / "scenario_normal.md"
    script_dir = tmp_path / "scripts"
    manifest = tmp_path / "manifest.json"
    script_out = tmp_path / "script.md"

    script_dir.mkdir(parents=True, exist_ok=True)
    _write_scenario(scenario)
    _write_dual_script(
        script_dir / "script_normal.ko.md",
        "ko",
        [("S1", "스마트머니봇 소개"), ("S2", "마켓 게이트 확인")],
    )

    result = _run(
        [
            "python3",
            str(APPLY_SCRIPT),
            "--scenario-file",
            str(scenario),
            "--scenario-version",
            "normal",
            "--script-dir",
            str(script_dir),
            "--manifest",
            str(manifest),
            "--script-out",
            str(script_out),
            "--language",
            "ko+en",
        ]
    )

    assert result.returncode != 0
    assert "english script missing" in (result.stderr + result.stdout).lower()


def test_apply_showcase_fails_when_english_script_is_korean(tmp_path: Path) -> None:
    scenario = tmp_path / "scenario_normal.md"
    script_dir = tmp_path / "scripts"
    manifest = tmp_path / "manifest.json"
    script_out = tmp_path / "script.md"

    script_dir.mkdir(parents=True, exist_ok=True)
    _write_scenario(scenario)
    _write_dual_script(
        script_dir / "script_normal.ko.md",
        "ko",
        [("S1", "스마트머니봇 소개"), ("S2", "마켓 게이트 확인")],
    )
    _write_dual_script(
        script_dir / "script_normal.en.md",
        "en",
        [("S1", "스마트머니봇 소개"), ("S2", "마켓 게이트 확인")],
    )

    result = _run(
        [
            "python3",
            str(APPLY_SCRIPT),
            "--scenario-file",
            str(scenario),
            "--scenario-version",
            "normal",
            "--script-dir",
            str(script_dir),
            "--manifest",
            str(manifest),
            "--script-out",
            str(script_out),
            "--language",
            "ko+en",
        ]
    )

    assert result.returncode != 0
    assert "english script contamination" in (result.stderr + result.stdout).lower()
