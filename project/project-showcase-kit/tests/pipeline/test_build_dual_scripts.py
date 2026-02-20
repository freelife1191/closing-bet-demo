#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
BUILD_SCENARIO = KIT_ROOT / "scripts" / "video" / "build_showcase_scenarios.py"
BUILD_DUAL = KIT_ROOT / "scripts" / "video" / "build_dual_scripts.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _hangul_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha() or ("\uac00" <= ch <= "\ud7a3")]
    if not letters:
        return 0.0
    hangul = sum(1 for ch in letters if "\uac00" <= ch <= "\ud7a3")
    return hangul / float(len(letters))


def test_dual_scripts_are_generated_and_english_has_low_hangul_ratio(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "scenarios"

    scenario_result = _run(
        [
            "python3",
            str(BUILD_SCENARIO),
            "--out-dir",
            str(scenario_dir),
        ]
    )
    assert scenario_result.returncode == 0, scenario_result.stderr or scenario_result.stdout

    dual_result = _run(
        [
            "python3",
            str(BUILD_DUAL),
            "--scenario-dir",
            str(scenario_dir),
            "--out-dir",
            str(scenario_dir),
        ]
    )
    assert dual_result.returncode == 0, dual_result.stderr or dual_result.stdout

    ko_script = scenario_dir / "script_short.ko.md"
    en_script = scenario_dir / "script_short.en.md"
    assert ko_script.exists(), f"missing ko script: {ko_script}"
    assert en_script.exists(), f"missing en script: {en_script}"

    ko_text = ko_script.read_text(encoding="utf-8")
    en_text = en_script.read_text(encoding="utf-8")

    assert "| Scene |" in ko_text
    assert "| Scene |" in en_text
    assert "Smart Money Bot" in en_text

    en_narrations = []
    for line in en_text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if re.match(r"^\|\s*Scene\s*\|", stripped):
            continue
        if set(stripped) <= {"|", "-", " ", ":"}:
            continue
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        if len(cells) >= 2:
            en_narrations.append(cells[-1])

    assert en_narrations, "english script must include narration rows"
    assert _hangul_ratio("\n".join(en_narrations)) <= 0.05
