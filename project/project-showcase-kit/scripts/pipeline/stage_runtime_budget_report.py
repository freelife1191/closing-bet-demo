#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate runtime budget report for showcase pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="runtime budget report stage")
    parser.add_argument("--elapsed-seconds", type=float, default=0.0)
    parser.add_argument("--budget-minutes", type=float, default=120.0)
    parser.add_argument("--out-json", default="project/video/evidence/runtime_budget_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/runtime_budget_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()

    elapsed_seconds = max(0.0, float(args.elapsed_seconds or 0.0))
    budget_minutes = max(1.0, float(args.budget_minutes or 120.0))
    elapsed_minutes = elapsed_seconds / 60.0
    within_budget = elapsed_minutes <= budget_minutes

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if within_budget else "fail",
        "elapsedSeconds": round(elapsed_seconds, 3),
        "elapsedMinutes": round(elapsed_minutes, 3),
        "budgetMinutes": round(budget_minutes, 3),
        "withinBudget": within_budget,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Runtime Budget Report",
        "",
        f"- status: {payload['status']}",
        f"- elapsedSeconds: {payload['elapsedSeconds']}",
        f"- elapsedMinutes: {payload['elapsedMinutes']}",
        f"- budgetMinutes: {payload['budgetMinutes']}",
        f"- withinBudget: {payload['withinBudget']}",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"runtime budget report: {out_json}")
    print(f"runtime budget report: {out_md}")
    return 0 if within_budget else 1


if __name__ == "__main__":
    raise SystemExit(main())
