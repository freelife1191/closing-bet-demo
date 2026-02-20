#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate quality report using voice/captions/validation metadata."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="quality report stage")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--voice-meta", default="project/video/audio/narration.json")
    parser.add_argument("--captions-meta", default="project/video/captions/subtitles.json")
    parser.add_argument("--validation", default="project/video/evidence/validation_report.json")
    parser.add_argument("--scene-gate", default="project/video/evidence/scene_gate_report.json")
    parser.add_argument("--version-gate", default="project/video/evidence/version_gate_report.json")
    parser.add_argument("--runtime-budget", default="project/video/evidence/runtime_budget_report.json")
    parser.add_argument("--out-json", default="project/video/evidence/quality_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/quality_research.md")
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

    voice_meta = _load_json(Path(args.voice_meta).resolve())
    captions_meta = _load_json(Path(args.captions_meta).resolve())
    validation = _load_json(Path(args.validation).resolve())
    scene_gate = _load_json(Path(args.scene_gate).resolve())
    version_gate = _load_json(Path(args.version_gate).resolve())
    runtime_budget = _load_json(Path(args.runtime_budget).resolve())

    duration = voice_meta.get("durationSeconds")
    caption_count = len(captions_meta.get("captions", [])) if isinstance(captions_meta.get("captions"), list) else 0
    validation_status = validation.get("status", "missing")
    scene_gate_status = scene_gate.get("status", "missing")
    version_gate_status = version_gate.get("status", "missing")
    runtime_within_budget = runtime_budget.get("withinBudget")
    if runtime_within_budget is None:
        runtime_within_budget = str(runtime_budget.get("status", "missing")).strip().lower() in {"pass", "missing", ""}

    status = "pass" if (
        validation_status == "pass"
        and str(scene_gate_status).strip().lower() in {"pass", "missing", ""}
        and str(version_gate_status).strip().lower() in {"pass", "missing", ""}
        and bool(runtime_within_budget)
    ) else "needs_action"

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "voiceDurationSeconds": duration,
        "captionCount": caption_count,
        "validationStatus": validation_status,
        "sceneGateStatus": scene_gate_status,
        "versionGateStatus": version_gate_status,
        "runtimeWithinBudget": bool(runtime_within_budget),
        "notes": [
            "validation/scene gate/version gate/runtime budget 지표를 함께 반영함",
            "caption count와 voice duration은 참고 지표",
        ],
    }

    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Quality Research",
        "",
        f"- status: {status}",
        f"- validation: {validation_status}",
        f"- sceneGate: {scene_gate_status}",
        f"- versionGate: {version_gate_status}",
        f"- runtimeWithinBudget: {bool(runtime_within_budget)}",
        f"- voiceDurationSeconds: {duration}",
        f"- captionCount: {caption_count}",
        "",
        "## Notes",
        "",
        "- validation 상태가 pass인지 우선 확인",
        "- 음성 길이와 자막 개수 일관성 확인",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"quality report: {out_json}")
    print(f"quality report: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
