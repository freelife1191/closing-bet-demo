#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evaluate per-scene quality gates with strict sync thresholds."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="scene quality gate stage")
    parser.add_argument("--input-json", default="project/video/evidence/scene_metrics.json")
    parser.add_argument("--out-json", default="project/video/evidence/scene_gate_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/scene_gate_report.md")
    parser.add_argument("--max-boundary-delta-sec", type=float, default=0.15)
    parser.add_argument("--max-caption-voice-delta-sec", type=float, default=0.10)
    parser.add_argument("--min-action-rate", type=float, default=0.95)
    parser.add_argument("--max-static-frame-ratio", type=float, default=0.35)
    return parser.parse_args()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _check_status(ok: bool) -> str:
    return "pass" if ok else "fail"


def _evaluate_scene(scene: Dict[str, Any], args: argparse.Namespace, scene_index: int) -> Dict[str, Any]:
    scene_id = str(scene.get("scene_id") or scene.get("id") or f"scene-{scene_index:02d}")

    boundary_delta = _safe_float(scene.get("scene_av_boundary_delta_sec"))
    caption_voice_delta = _safe_float(scene.get("scene_caption_voice_end_delta_sec"))
    action_rate = _safe_float(scene.get("action_execution_rate"), default=1.0)
    static_ratio = _safe_float(scene.get("static_frame_ratio"), default=0.0)

    checks = {
        "scene_av_boundary_delta_sec": _check_status(boundary_delta <= args.max_boundary_delta_sec),
        "scene_caption_voice_end_delta_sec": _check_status(caption_voice_delta <= args.max_caption_voice_delta_sec),
        "action_execution_rate": _check_status(action_rate >= args.min_action_rate),
        "static_frame_ratio": _check_status(static_ratio <= args.max_static_frame_ratio),
    }
    status = "pass" if all(value == "pass" for value in checks.values()) else "fail"

    return {
        "scene_id": scene_id,
        "status": status,
        "metrics": {
            "scene_av_boundary_delta_sec": boundary_delta,
            "scene_caption_voice_end_delta_sec": caption_voice_delta,
            "action_execution_rate": action_rate,
            "static_frame_ratio": static_ratio,
        },
        "checks": checks,
    }


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Scene Gate Report",
        "",
        f"- status: {payload.get('status', 'fail')}",
        f"- source: {payload.get('source', '')}",
        "",
        "## Scenes",
        "",
    ]

    for scene in payload.get("scenes", []):
        scene_id = scene.get("scene_id", "scene")
        status = scene.get("status", "fail")
        checks = scene.get("checks", {})
        lines.append(
            f"- {scene_id}: {status} "
            f"(boundary={checks.get('scene_av_boundary_delta_sec')}, "
            f"caption_voice={checks.get('scene_caption_voice_end_delta_sec')}, "
            f"action={checks.get('action_execution_rate')}, "
            f"static={checks.get('static_frame_ratio')})"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_json).resolve()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()

    source = _load_json(input_path)
    scenes_raw = source.get("scenes") if isinstance(source, dict) else []
    scenes: List[Dict[str, Any]] = []
    if isinstance(scenes_raw, list):
        scenes = [row for row in scenes_raw if isinstance(row, dict)]

    evaluated = [_evaluate_scene(scene, args, idx + 1) for idx, scene in enumerate(scenes)]
    status = "pass" if evaluated and all(row.get("status") == "pass" for row in evaluated) else "fail"
    if not evaluated:
        status = "fail"

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": str(input_path),
        "status": status,
        "thresholds": {
            "maxBoundaryDeltaSec": args.max_boundary_delta_sec,
            "maxCaptionVoiceDeltaSec": args.max_caption_voice_delta_sec,
            "minActionRate": args.min_action_rate,
            "maxStaticFrameRatio": args.max_static_frame_ratio,
        },
        "scenes": evaluated,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_md(out_md, payload)

    print(f"scene gate report: {out_json}")
    print(f"scene gate report: {out_md}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
