#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal output validator for restored project-showcase-kit pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from language_voice_policy import default_language_selection, resolve_target_languages
from path_policy import is_within_project_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate restored-full-stage outputs")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--out-json", default="project/video/evidence/validation_report.json")
    parser.add_argument("--out-md", default="project/video/evidence/validation_report.md")
    parser.add_argument("--require-showcase", action="store_true")
    parser.add_argument("--scenario-dir", default="project/video/scenarios")
    parser.add_argument("--term-audit", default="project/video/evidence/term_audit_report.json")
    return parser.parse_args()


def make_check(name: str, ok: bool, detail: str) -> Dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if ok else "fail",
        "detail": detail,
    }


def safe_load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _safe_scene_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    scenes = payload.get("scenes")
    if isinstance(scenes, list):
        return [row for row in scenes if isinstance(row, dict)]
    return []


def _collect_paths(value: Any) -> List[Path]:
    paths: List[Path] = []
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        looks_like_path = ("/" in raw) or ("\\" in raw) or raw.startswith(".") or raw.startswith("~")
        if looks_like_path:
            paths.append(Path(raw).expanduser().resolve())
        return paths
    if isinstance(value, list):
        for item in value:
            paths.extend(_collect_paths(item))
        return paths
    if isinstance(value, dict):
        for item in value.values():
            paths.extend(_collect_paths(item))
        return paths
    return paths


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    project_root = Path(__file__).resolve().parents[2].parent.resolve()

    checks: List[Dict[str, Any]] = [make_check("manifest_exists", manifest_path.exists(), str(manifest_path))]
    manifest_payload = safe_load_json(manifest_path)

    voice_path = Path("project/video/audio/narration.wav").resolve()
    checks.append(make_check("voice_exists", voice_path.exists(), str(voice_path)))
    captions_path = Path("project/video/captions/subtitles.srt").resolve()
    render_path = Path("project/out/final_showcase.mp4").resolve()
    checks.append(make_check("captions_exists", captions_path.exists(), str(captions_path)))
    checks.append(make_check("render_exists", render_path.exists(), str(render_path)))

    voice_meta = safe_load_json(Path("project/video/audio/narration.json").resolve())
    captions_meta = safe_load_json(Path("project/video/captions/subtitles.json").resolve())
    render_meta = safe_load_json(Path("project/video/evidence/render_meta.json").resolve())

    voice_duration = safe_float(voice_meta.get("durationSeconds"))
    render_duration = safe_float(render_meta.get("durationSec"))
    captions_end = 0.0
    captions = captions_meta.get("captions", [])
    if isinstance(captions, list):
        for row in captions:
            if isinstance(row, dict):
                captions_end = max(captions_end, safe_float(row.get("endSec")))

    if voice_duration > 0:
        checks.append(
            make_check(
                "caption_covers_voice",
                captions_end + 0.2 >= voice_duration,
                f"caption_end={captions_end:.3f}, voice_duration={voice_duration:.3f}",
            )
        )
        checks.append(
            make_check(
                "render_covers_voice",
                render_duration + 0.2 >= voice_duration,
                f"render_duration={render_duration:.3f}, voice_duration={voice_duration:.3f}",
            )
        )

    requested_language = str(voice_meta.get("requestedLanguage") or manifest_payload.get("language", "")).strip()
    if not requested_language:
        requested_language = default_language_selection()
    language_codes = resolve_target_languages(requested_language)
    for code in language_codes:
        extra_audio = Path(f"project/out/audio/narration.{code}.wav").resolve()
        extra_srt = Path(f"project/out/captions/subtitles.{code}.srt").resolve()
        checks.append(make_check(f"extra_audio_{code}_exists", extra_audio.exists(), str(extra_audio)))
        checks.append(make_check(f"extra_srt_{code}_exists", extra_srt.exists(), str(extra_srt)))

    all_output_paths: List[Path] = [
        voice_path,
        captions_path,
        render_path,
    ]
    all_output_paths.extend(_collect_paths(voice_meta.get("output")))
    all_output_paths.extend(_collect_paths(voice_meta.get("audioExports")))
    all_output_paths.extend(_collect_paths(voice_meta.get("metadataExports")))
    all_output_paths.extend(_collect_paths(captions_meta.get("exports")))
    all_output_paths.extend(_collect_paths(render_meta.get("output")))
    all_output_paths.extend(_collect_paths(render_meta.get("tracks")))

    outside = sorted({str(path) for path in all_output_paths if not is_within_project_root(project_root, path)})
    checks.append(
        make_check(
            "output_within_project_root",
            len(outside) == 0,
            "ok" if not outside else "; ".join(outside),
        )
    )

    if args.require_showcase:
        scenario_dir = Path(args.scenario_dir).resolve()
        term_audit_path = Path(args.term_audit).resolve()
        required_files = {
            "showcase_scenario_short_exists": scenario_dir / "scenario_short.md",
            "showcase_scenario_normal_exists": scenario_dir / "scenario_normal.md",
            "showcase_scenario_detail_exists": scenario_dir / "scenario_detail.md",
            "showcase_tts_plan_short_exists": scenario_dir / "tts_plan_short.json",
            "showcase_tts_plan_normal_exists": scenario_dir / "tts_plan_normal.json",
            "showcase_tts_plan_detail_exists": scenario_dir / "tts_plan_detail.json",
            "showcase_caption_plan_short_exists": scenario_dir / "caption_plan_short.json",
            "showcase_caption_plan_normal_exists": scenario_dir / "caption_plan_normal.json",
            "showcase_caption_plan_detail_exists": scenario_dir / "caption_plan_detail.json",
        }
        for name, path in required_files.items():
            checks.append(make_check(name, path.exists(), str(path)))

        tts_plan_status: List[str] = []
        min_fill_ratio = 1.0
        no_cut_ok = True
        fill_ok = True
        for version in ("short", "normal", "detail"):
            tts_plan_path = scenario_dir / f"tts_plan_{version}.json"
            tts_payload = safe_load_json(tts_plan_path)
            scenes = _safe_scene_list(tts_payload)
            if not scenes:
                no_cut_ok = False
                fill_ok = False
                tts_plan_status.append(f"{version}:invalid")
                continue

            max_overflow = max(safe_float(row.get("overflow_sec")) for row in scenes)
            local_fill = min(
                (
                    safe_float(row.get("fill_ratio"))
                    if safe_float(row.get("fill_ratio")) > 0
                    else (
                        safe_float(row.get("speech_final_sec")) / max(0.001, safe_float(row.get("target_sec")))
                        if safe_float(row.get("target_sec")) > 0
                        else 0.0
                    )
                )
                for row in scenes
            )
            min_fill_ratio = min(min_fill_ratio, local_fill)
            if max_overflow > 0.001:
                no_cut_ok = False
            if local_fill < 0.90:
                fill_ok = False

            tts_plan_status.append(f"{version}:overflow={max_overflow:.3f},min_fill={local_fill:.3f}")

        checks.append(
            make_check(
                "showcase_tts_no_cut",
                no_cut_ok,
                "; ".join(tts_plan_status) if tts_plan_status else "no plans",
            )
        )
        checks.append(
            make_check(
                "showcase_tts_fill_ratio",
                fill_ok,
                f"min_fill_ratio={min_fill_ratio:.3f}",
            )
        )

        term_audit = safe_load_json(term_audit_path)
        term_status = str(term_audit.get("status", "missing")).strip().lower()
        checks.append(
            make_check(
                "showcase_term_audit_pass",
                term_status == "pass",
                f"{term_audit_path} status={term_status}",
            )
        )

    errors = [row for row in checks if row["status"] == "fail"]
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "status": "fail" if errors else "pass",
        "checks": checks,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Validation Report",
        "",
        f"- status: {payload['status']}",
        f"- manifest: {manifest_path}",
        "",
        "## Checks",
        "",
    ]
    for row in checks:
        lines.append(f"- {row['name']}: {row['status']} ({row['detail']})")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"validation report: {out_json}")
    print(f"validation report: {out_md}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
