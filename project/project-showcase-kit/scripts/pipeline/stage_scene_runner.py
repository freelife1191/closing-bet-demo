#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scene-by-scene runner with bounded retry policy."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="scene runner stage")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--failure-plan", default="")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--out-json", default="project/video/evidence/scene_runner_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/scene_runner_report.md")
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Scene Runner Report",
        "",
        f"- status: {payload.get('status', 'fail')}",
        f"- maxRetries: {payload.get('maxRetries', 3)}",
        "",
        "## Scenes",
        "",
    ]

    for row in payload.get("scenes", []):
        lines.append(
            f"- {row.get('scene_id')}: {row.get('status')} "
            f"(attempts={row.get('attempt_count')}, history={','.join(row.get('attempt_history', []))})"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _resolve_scene_ids(manifest_path: Path) -> List[str]:
    payload = _load_json(manifest_path)
    scenes_raw = payload.get("scenes") if isinstance(payload, dict) else []
    scene_ids: List[str] = []
    if isinstance(scenes_raw, list):
        for idx, row in enumerate(scenes_raw, start=1):
            scene = row if isinstance(row, dict) else {}
            scene_id = str(scene.get("id") or f"scene-{idx:02d}").strip()
            if scene_id:
                scene_ids.append(scene_id)
    return scene_ids


def _simulate_scene(scene_id: str, plan: Dict[str, Any], max_retries: int) -> Dict[str, Any]:
    planned = plan.get(scene_id)
    if not isinstance(planned, list) or not planned:
        planned = ["pass"]

    attempt_history: List[str] = []
    attempts = max(1, max_retries)
    for idx in range(attempts):
        current = str(planned[idx] if idx < len(planned) else planned[-1]).strip().lower()
        status = "pass" if current == "pass" else "fail"
        attempt_history.append(status)
        if status == "pass":
            break

    final_status = attempt_history[-1] if attempt_history else "fail"
    return {
        "scene_id": scene_id,
        "status": final_status,
        "attempt_count": len(attempt_history),
        "attempt_history": attempt_history,
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    failure_plan_path = Path(args.failure_plan).resolve() if args.failure_plan.strip() else None

    scene_ids = _resolve_scene_ids(manifest_path)
    if not scene_ids:
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "manifest": str(manifest_path),
            "status": "fail",
            "maxRetries": max(1, args.max_retries),
            "scenes": [],
            "error": "scenes is empty",
        }
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _write_md(out_md, payload)
        return 1

    failure_plan = _load_json(failure_plan_path) if failure_plan_path else {}
    rows = [_simulate_scene(scene_id, failure_plan, max(1, args.max_retries)) for scene_id in scene_ids]
    failed = [row["scene_id"] for row in rows if row.get("status") != "pass"]

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "status": "pass" if not failed else "fail",
        "maxRetries": max(1, args.max_retries),
        "scenes": rows,
        "failedSceneIds": failed,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_md(out_md, payload)

    print(f"scene runner report: {out_json}")
    print(f"scene runner report: {out_md}")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
