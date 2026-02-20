#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate version gate report from scene gate evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="version gate report stage")
    parser.add_argument("--scene-gate-json", default="project/video/evidence/scene_gate_report.json")
    parser.add_argument("--out-json", default="project/video/evidence/version_gate_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/version_gate_report.md")
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    args = parse_args()
    scene_gate_path = Path(args.scene_gate_json).resolve()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()

    scene_gate = _load_json(scene_gate_path)
    scene_status = str(scene_gate.get("status", "missing")).strip().lower()
    status = "pass" if scene_status in {"pass", "missing", ""} else "fail"

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sceneGate": str(scene_gate_path),
        "sceneGateStatus": scene_status or "missing",
        "status": status,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Version Gate Report",
        "",
        f"- status: {status}",
        f"- sceneGate: {scene_gate_path}",
        f"- sceneGateStatus: {scene_status or 'missing'}",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"version gate report: {out_json}")
    print(f"version gate report: {out_md}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
