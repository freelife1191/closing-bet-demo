#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project init audit for project-showcase-kit")
    parser.add_argument("--project-root", default=".", help="Path to target project root")
    parser.add_argument("--overwrite", default="true", choices=["true", "false"])
    return parser.parse_args()


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_ports(env_text: str) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for key in ["FRONTEND_PORT", "FLASK_PORT", "PORT"]:
        match = re.search(rf"^{key}=(.+)$", env_text, flags=re.MULTILINE)
        if match:
            payload[key] = match.group(1).strip()
    return payload


def _discover_start_stop(root: Path) -> Dict[str, List[str]]:
    starts: List[str] = []
    stops: List[str] = []

    for candidate in ["restart_all.sh", "scripts/init_all.sh", "flask_app.py", "run.py"]:
        path = root / candidate
        if path.exists():
            if candidate.endswith(".sh"):
                starts.append(f"./{candidate}")
            elif candidate == "flask_app.py":
                starts.append("python3 flask_app.py")
            elif candidate == "run.py":
                starts.append("python3 run.py")

    for candidate in ["stop_all.sh"]:
        path = root / candidate
        if path.exists():
            stops.append(f"./{candidate}")

    package_json = root / "frontend" / "package.json"
    if package_json.exists():
        starts.append("cd frontend && npm run dev")

    return {"start": starts, "stop": stops}


def _build_runbook(audit: Dict) -> str:
    lines = [
        "# Project Runbook",
        "",
        "## Discovered Start Commands",
    ]
    starts = audit["runtime"]["commands"]["start"]
    if starts:
        lines.extend([f"- `{item}`" for item in starts])
    else:
        lines.append("- unresolved")

    lines.extend(["", "## Discovered Stop Commands"])
    stops = audit["runtime"]["commands"]["stop"]
    if stops:
        lines.extend([f"- `{item}`" for item in stops])
    else:
        lines.append("- unresolved")

    lines.extend(["", "## Discovered Ports"])
    ports = audit["runtime"]["ports"]
    if ports:
        for key, value in ports.items():
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- unresolved")
    return "\n".join(lines) + "\n"


def _build_flows() -> str:
    return (
        "# Project Flows\n\n"
        "1. Init audit (documents + scripts)\n"
        "2. Preflight runtime verification\n"
        "3. Scene/script planning\n"
        "4. Record/voice/captions/render\n"
        "5. Validate and signoff\n"
    )


def main() -> int:
    args = parse_args()
    root = Path(args.project_root).resolve()
    evidence_dir = root / "project" / "video" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    env_text = _read_if_exists(root / ".env")
    commands = _discover_start_stop(root)
    ports = _extract_ports(env_text)

    audit = {
        "project_root": str(root),
        "documents": {
            "README.md": (root / "README.md").exists(),
            "AGENTS.md": (root / "AGENTS.md").exists(),
            "CLAUDE.md": (root / "CLAUDE.md").exists(),
            "GEMINI.md": (root / "GEMINI.md").exists(),
        },
        "runtime": {
            "commands": commands,
            "ports": ports,
            "unresolved": [],
        },
    }

    if not commands["start"]:
        audit["runtime"]["unresolved"].append("start_command")
    if not commands["stop"]:
        audit["runtime"]["unresolved"].append("stop_command")
    if not ports:
        audit["runtime"]["unresolved"].append("ports")

    overwrite = args.overwrite == "true"
    outputs = {
        "project_audit.json": json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        "project_runbook.md": _build_runbook(audit),
        "project_flows.md": _build_flows(),
    }
    for filename, content in outputs.items():
        path = evidence_dir / filename
        if path.exists() and not overwrite:
            continue
        path.write_text(content, encoding="utf-8")

    print(json.dumps({"status": "ok", "evidence_dir": str(evidence_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

