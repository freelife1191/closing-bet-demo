#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate showcase script terminology against project source-of-truth terms."""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_REQUIRED_BRAND = "Smart Money Bot"
DEFAULT_REQUIRED_TERMS = [
    "Market Gate",
    "VCP",
    "종가베팅",
    "Jongga V2",
    "AI 상담",
    "Data Status",
    "Telegram",
    "Discord",
    "Slack",
    "Email",
    "Toss Securities API",
    "Phase1~4",
    "project-showcase-kit",
]
DEFAULT_FORBIDDEN_PHRASES = [
    "마켓 게이",
    "AI 상당",
    "KR 마켓팩",
    "Market Gate트",
    "KOSDAG",
]
DEFAULT_UI_ALIAS_MAP = {
    "마켓 게이트": "Market Gate",
    "마켓게이트": "Market Gate",
    "마켓 게이": "Market Gate",
    "오버뷰": "Overview",
    "종가 베팅": "종가베팅",
    "데이터 스테이터스": "Data Status",
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Validate script terminology")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--scenario-glob", default="project/video/scenarios/scenario_*.md")
    parser.add_argument("--report-json", default="project/video/evidence/term_audit_report.json")
    parser.add_argument("--report-md", default="project/video/evidence/term_audit_report.md")
    parser.add_argument("--required-brand", default=DEFAULT_REQUIRED_BRAND)
    parser.add_argument(
        "--required-terms",
        default=",".join(DEFAULT_REQUIRED_TERMS),
        help="Comma-separated required terms for feature coverage checks",
    )
    return parser.parse_args()


def _safe_load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _append_fragment(fragments: List[Dict[str, str]], source: str, scene_id: str, field: str, text: str) -> None:
    value = str(text).strip()
    if not value:
        return
    fragments.append(
        {
            "source": source,
            "scene_id": scene_id,
            "field": field,
            "text": value,
        }
    )


def _load_manifest_fragments(manifest_path: Path) -> List[Dict[str, str]]:
    fragments: List[Dict[str, str]] = []
    payload = _safe_load_json(manifest_path)
    if not payload:
        return fragments

    _append_fragment(fragments, str(manifest_path), "GLOBAL", "title", str(payload.get("title", "")))

    scenes = payload.get("scenes")
    if not isinstance(scenes, list):
        return fragments

    for idx, scene in enumerate(scenes, start=1):
        row = scene if isinstance(scene, dict) else {}
        scene_id = str(row.get("id") or f"scene-{idx:02d}")
        _append_fragment(fragments, str(manifest_path), scene_id, "title", str(row.get("title", "")))
        _append_fragment(fragments, str(manifest_path), scene_id, "narration", str(row.get("narration", "")))

        by_lang = row.get("narrationByLang")
        if isinstance(by_lang, dict):
            for code, text in by_lang.items():
                _append_fragment(
                    fragments,
                    str(manifest_path),
                    scene_id,
                    f"narrationByLang.{code}",
                    str(text),
                )

        must_show_ui = row.get("must_show_ui")
        if isinstance(must_show_ui, list):
            for item in must_show_ui:
                _append_fragment(fragments, str(manifest_path), scene_id, "must_show_ui", str(item))

    return fragments


def _load_markdown_fragments(path: Path) -> List[Dict[str, str]]:
    fragments: List[Dict[str, str]] = []
    if not path.exists():
        return fragments

    current_scene = "GLOBAL"
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            current_scene = line.replace("###", "", 1).strip()
            continue
        if line.startswith("|") and line.endswith("|"):
            # Markdown table row
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            for idx, cell in enumerate(cells, start=1):
                _append_fragment(fragments, str(path), current_scene, f"table_col_{idx}", cell)
            continue
        if set(line) <= {"-", "|", ":"}:
            continue
        _append_fragment(fragments, str(path), current_scene, "markdown", line)

    return fragments


def validate_fragments(
    fragments: List[Dict[str, str]],
    required_brand: str,
    forbidden_phrases: List[str],
    ui_alias_map: Dict[str, str],
    required_terms: List[str] | None = None,
) -> List[Dict[str, str]]:
    """Validate collected fragments and return findings."""
    findings: List[Dict[str, str]] = []
    full_text = "\n".join(str(item.get("text", "")) for item in fragments)
    normalized_required_terms = [term.strip() for term in (required_terms or []) if str(term).strip()]

    if required_brand and required_brand not in full_text:
        findings.append(
            {
                "severity": "ERROR",
                "rule_id": "brand_name_exact",
                "scene_id": "GLOBAL",
                "field": "global",
                "offending_text": "(missing brand)",
                "expected": required_brand,
                "suggestion": f"브랜드명을 `{required_brand}`로 명시하세요.",
            }
        )

    for term in normalized_required_terms:
        if term not in full_text:
            findings.append(
                {
                    "severity": "ERROR",
                    "rule_id": "required_term_exact",
                    "scene_id": "GLOBAL",
                    "field": "global",
                    "offending_text": f"(missing term: {term})",
                    "expected": term,
                    "suggestion": f"핵심 기능 용어 `{term}`를 시나리오/대본에 명시하세요.",
                }
            )

    for fragment in fragments:
        text = str(fragment.get("text", ""))
        scene_id = str(fragment.get("scene_id", "GLOBAL"))
        field = str(fragment.get("field", "text"))

        for phrase in forbidden_phrases:
            if phrase and phrase in text:
                findings.append(
                    {
                        "severity": "ERROR",
                        "rule_id": "forbidden_phrase",
                        "scene_id": scene_id,
                        "field": field,
                        "offending_text": phrase,
                        "expected": "금지어 미포함",
                        "suggestion": "프로젝트 표준 용어로 교체하세요.",
                    }
                )

        for alias, canonical in ui_alias_map.items():
            if alias and alias in text:
                findings.append(
                    {
                        "severity": "ERROR",
                        "rule_id": "ui_term_exact",
                        "scene_id": scene_id,
                        "field": field,
                        "offending_text": alias,
                        "expected": canonical,
                        "suggestion": f"UI 용어는 `{canonical}` 원문으로 표기하세요.",
                    }
                )

    return findings


def write_report(report_json: Path, report_md: Path, findings: List[Dict[str, str]]) -> None:
    """Write JSON/Markdown reports from findings."""
    error_count = len([item for item in findings if item.get("severity") == "ERROR"])
    warning_count = len([item for item in findings if item.get("severity") == "WARN"])

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "fail" if error_count > 0 else "pass",
        "summary": {
            "errorCount": error_count,
            "warningCount": warning_count,
            "total": len(findings),
        },
        "findings": findings,
    }

    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Terminology Audit Report",
        "",
        f"- status: {payload['status']}",
        f"- errorCount: {error_count}",
        f"- warningCount: {warning_count}",
        "",
        "## Findings",
        "",
    ]

    if findings:
        for item in findings:
            lines.append(
                "- [{severity}] {rule_id} | scene={scene_id} | field={field} | offending={offending_text} | expected={expected}".format(
                    severity=item.get("severity", "INFO"),
                    rule_id=item.get("rule_id", ""),
                    scene_id=item.get("scene_id", "GLOBAL"),
                    field=item.get("field", "text"),
                    offending_text=item.get("offending_text", ""),
                    expected=item.get("expected", ""),
                )
            )
    else:
        lines.append("- no findings")

    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    report_json = Path(args.report_json).resolve()
    report_md = Path(args.report_md).resolve()

    scenario_paths = [Path(path).resolve() for path in sorted(glob.glob(args.scenario_glob))]

    fragments: List[Dict[str, str]] = []
    fragments.extend(_load_manifest_fragments(manifest_path))
    for scenario_path in scenario_paths:
        fragments.extend(_load_markdown_fragments(scenario_path))

    findings = validate_fragments(
        fragments=fragments,
        required_brand=str(args.required_brand).strip(),
        forbidden_phrases=DEFAULT_FORBIDDEN_PHRASES,
        ui_alias_map=DEFAULT_UI_ALIAS_MAP,
        required_terms=[term.strip() for term in str(args.required_terms).split(",") if term.strip()],
    )
    write_report(report_json, report_md, findings)

    status = "fail" if any(item.get("severity") == "ERROR" for item in findings) else "pass"
    print(f"term audit status: {status}")
    print(f"term audit json: {report_json}")
    print(f"term audit md: {report_md}")
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
