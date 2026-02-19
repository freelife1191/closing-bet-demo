#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import subprocess
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = KIT_ROOT.parents[1]
SCRIPT_PATH = KIT_ROOT / "scripts" / "video" / "build_sync_plans.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_sync_plan_enforces_no_cut_policy(tmp_path: Path) -> None:
    scenario_dir = tmp_path / "scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # 의도적으로 4초 구간에 과도하게 긴 문장을 넣어 scene_extend 단계 유도
    scenario_path = scenario_dir / "scenario_short.md"
    scenario_path.write_text(
        "\n".join(
            [
                "# 간소화(1분 이내) 시나리오",
                "",
                "| Scene | Time | Screen | Action | Narration | TTSRate | SubtitleCue |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| S1 | 00:00-00:04 | `/dashboard/kr` | 테스트 | "
                + ("아주 긴 설명 문장을 반복하여 오버런을 유도합니다. " * 25)
                + "| 4.6 | 테스트 |",
            ]
        ),
        encoding="utf-8",
    )

    result = _run(
        [
            "python3",
            str(SCRIPT_PATH),
            "--scenario-dir",
            str(scenario_dir),
            "--out-dir",
            str(scenario_dir),
        ]
    )
    assert result.returncode == 0, result.stderr or result.stdout

    tts_plan_path = scenario_dir / "tts_plan_short.json"
    caption_plan_path = scenario_dir / "caption_plan_short.json"
    assert tts_plan_path.exists()
    assert caption_plan_path.exists()

    tts_payload = json.loads(tts_plan_path.read_text(encoding="utf-8"))
    scene = (tts_payload.get("scenes") or [])[0]

    assert scene.get("adjustment_step") in {
        "speed",
        "speed+compression",
        "speed+compression+scene_extend",
    }
    assert scene.get("overflow_sec", 0) >= 0
    assert float(scene.get("fill_ratio", 0)) >= 0
