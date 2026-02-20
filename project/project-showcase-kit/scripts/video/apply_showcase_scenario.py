#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply showcase scenario markdown (short/normal/detail) to manifest/script."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from kr_text_policy import normalize_kr_manifest_payload, validate_kr_manifest_payload
from language_voice_policy import (
    fallback_english_narration,
    hangul_ratio,
    resolve_target_languages,
    translate_legacy_scene_text,
)


SUPPORTED_VERSIONS = {"short", "normal", "detail"}
DEFAULT_BASE_URL = "http://127.0.0.1:3500"
DEFAULT_FALLBACK_PATH = "/dashboard/kr/closing-bet"
EN_MAX_HANGUL_RATIO = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply showcase scenario to manifest/script")
    parser.add_argument("--scenario-dir", default="project/video/scenarios")
    parser.add_argument("--scenario-version", default="normal", choices=sorted(SUPPORTED_VERSIONS))
    parser.add_argument("--scenario-file", default="")
    parser.add_argument("--script-dir", default="")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--script-out", default="project/video/script.md")
    parser.add_argument("--language", default="ko+en")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--title", default="")
    parser.add_argument("--reuse-existing", default="true")
    return parser.parse_args()


def _parse_hms(raw: str) -> float:
    match = re.match(r"^\s*(\d+):(\d+)\s*$", raw.strip())
    if not match:
        return 0.0
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    return float(minutes * 60 + seconds)


def _parse_time_range(raw: str) -> Tuple[float, float]:
    value = raw.strip()
    if "-" not in value:
        return 0.0, 0.0
    start_raw, end_raw = [part.strip() for part in value.split("-", 1)]
    start = _parse_hms(start_raw)
    end = _parse_hms(end_raw)
    if end < start:
        end = start
    return start, end


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _strip_inline_code(value: str) -> str:
    text = value.strip()
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        return text[1:-1].strip()
    return text


def _extract_target_duration(text: str) -> int:
    match = re.search(r"targetDurationSec:\s*(\d+)", text)
    if not match:
        return 0
    return _safe_int(match.group(1), default=0)


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _scenario_rows(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        if set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 7:
            continue
        if cells[0].lower() == "scene":
            continue
        rows.append(
            {
                "scene": cells[0],
                "time": cells[1],
                "screen": cells[2],
                "action": cells[3],
                "narration": cells[4],
                "ttsRate": cells[5],
                "subtitleCue": cells[6],
            }
        )
    return rows


def _resolve_scene_url(screen: str, base_url: str) -> str:
    normalized = _strip_inline_code(screen)
    if not normalized:
        return f"{base_url.rstrip('/')}{DEFAULT_FALLBACK_PATH}"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    if normalized.startswith("/"):
        return f"{base_url.rstrip('/')}{normalized}"
    return f"{base_url.rstrip('/')}{DEFAULT_FALLBACK_PATH}"


def _build_actions(action_text: str, scene_no: int, duration_sec: int) -> List[Dict[str, Any]]:
    action = action_text.strip()
    wait_primary = max(700, min(2200, int(duration_sec * 1000 * 0.38)))
    wait_secondary = max(500, min(1800, int(duration_sec * 1000 * 0.20)))
    scroll_y = 320 + (scene_no * 36)
    actions: List[Dict[str, Any]] = [{"type": "wait", "ms": wait_primary}]

    if any(token in action for token in ("스크롤", "목록", "테이블", "히스토리", "로그")):
        actions.append({"type": "scroll", "x": 0, "y": scroll_y + 120})
    elif any(token in action for token in ("탭", "전환", "하이라이트", "강조", "포커스")):
        actions.append({"type": "scroll", "x": 0, "y": scroll_y})
    else:
        actions.append({"type": "wait", "ms": 550})

    actions.append({"type": "wait", "ms": wait_secondary})
    return actions


def _parse_script_rows(path: Path) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        if set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "scene":
            continue
        scene_key = cells[0].strip()
        narration = cells[-1].strip()
        if scene_key and narration:
            rows[scene_key] = narration
    return rows


def _load_dual_scripts(
    script_dir: Path,
    scenario_version: str,
    language_codes: List[str],
) -> Dict[str, Dict[str, str]]:
    script_files = {
        "ko": script_dir / f"script_{scenario_version}.ko.md",
        "en": script_dir / f"script_{scenario_version}.en.md",
    }
    exists = {code: path.exists() for code, path in script_files.items()}
    has_any = any(exists.values())
    if not has_any:
        return {}

    short_codes = {code.strip().lower().split("-", 1)[0] for code in language_codes}
    if "en" in short_codes and not exists["en"]:
        raise ValueError(f"english script missing: {script_files['en']}")
    if "ko" in short_codes and not exists["ko"]:
        raise ValueError(f"korean script missing: {script_files['ko']}")

    payload: Dict[str, Dict[str, str]] = {}
    for code, path in script_files.items():
        if not exists[code]:
            continue
        rows = _parse_script_rows(path)
        if not rows:
            raise ValueError(f"{code} script has no scene rows: {path}")
        payload[code] = rows

    en_rows = payload.get("en", {})
    if en_rows:
        ratio = hangul_ratio("\n".join(en_rows.values()))
        if ratio > EN_MAX_HANGUL_RATIO:
            raise ValueError(
                f"english script contamination: hangul_ratio={ratio:.4f} > {EN_MAX_HANGUL_RATIO:.2f}"
            )

    return payload


def _build_narration_by_lang(
    narration: str,
    language_codes: List[str],
    scene_key: str,
    screen: str,
    subtitle_cue: str,
    dual_scripts: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for code in language_codes:
        short = code.strip().lower().split("-", 1)[0]
        script_rows = (dual_scripts or {}).get(short, {})
        script_text = str(script_rows.get(scene_key, "")).strip()
        if script_text:
            payload[short] = script_text
            continue

        if short == "ko":
            payload["ko"] = narration
            continue
        if short == "en":
            payload["en"] = fallback_english_narration(
                source_text=narration,
                scene_id=scene_key,
                screen=screen,
                subtitle_cue=subtitle_cue,
            )
            continue

        translated = translate_legacy_scene_text(narration, short)
        payload[short] = translated if translated else narration

    if "ko" not in payload:
        payload["ko"] = narration

    if any(code.strip().lower().split("-", 1)[0] == "en" for code in language_codes):
        en_text = payload.get("en", "").strip()
        if not en_text:
            raise ValueError(f"english script missing for scene: {scene_key}")
        ratio = hangul_ratio(en_text)
        if ratio > EN_MAX_HANGUL_RATIO:
            raise ValueError(
                f"english script contamination for {scene_key}: hangul_ratio={ratio:.4f} > {EN_MAX_HANGUL_RATIO:.2f}"
            )
    return payload


def _default_title(version: str) -> str:
    labels = {
        "short": "간소화",
        "normal": "보통",
        "detail": "디테일",
    }
    label = labels.get(version, version)
    return f"Smart Money Bot 표준 프로젝트 쇼케이스 ({label})"


def _build_script_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = [
        f"# {payload.get('title', 'Smart Money Bot 표준 프로젝트 쇼케이스')}",
        "",
        f"- language: {payload.get('language', 'ko+en')}",
        f"- durationSec: {payload.get('durationSec', 0)}",
        f"- showcaseScenarioVersion: {payload.get('showcaseScenarioVersion', 'normal')}",
        "",
        "## Scenes",
        "",
    ]
    scenes = payload.get("scenes", [])
    for scene in scenes if isinstance(scenes, list) else []:
        row = scene if isinstance(scene, dict) else {}
        lines.append(f"### {row.get('id', 'scene')}")
        lines.append(f"- title: {row.get('title', '')}")
        lines.append(f"- durationSec: {row.get('durationSec', '')}")
        lines.append(f"- narration: {row.get('narration', '')}")
        lines.append(f"- url: {row.get('url', '')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _resolve_scenario_path(args: argparse.Namespace) -> Path:
    if args.scenario_file.strip():
        return Path(args.scenario_file).resolve()
    scenario_dir = Path(args.scenario_dir).resolve()
    return (scenario_dir / f"scenario_{args.scenario_version}.md").resolve()


def _is_reusable(
    manifest_path: Path,
    script_path: Path,
    scenario_path: Path,
    scenario_version: str,
) -> bool:
    if not manifest_path.exists() or not script_path.exists():
        return False
    if script_path.stat().st_size <= 10:
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return False
    if str(manifest.get("showcaseScenarioVersion", "")).strip() != scenario_version:
        return False
    if str(manifest.get("showcaseScenarioPath", "")).strip() != str(scenario_path):
        return False
    return True


def _build_manifest_payload(
    scenario_text: str,
    scenario_path: Path,
    scenario_version: str,
    language_expr: str,
    base_url: str,
    title: str,
    dual_scripts: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    rows = _scenario_rows(scenario_text)
    if not rows:
        raise ValueError(f"scenario table rows not found: {scenario_path}")

    language_codes = resolve_target_languages(language_expr)
    primary_lang = language_codes[0] if language_codes else "ko"
    scenes: List[Dict[str, Any]] = []
    total_duration = 0
    for idx, row in enumerate(rows, start=1):
        start_sec, end_sec = _parse_time_range(row["time"])
        duration_sec = max(1, int(round(end_sec - start_sec)))
        total_duration += duration_sec

        narration = row["narration"].strip()
        scenario_scene_id = row["scene"].strip() or f"S{idx}"
        narration_by_lang = _build_narration_by_lang(
            narration=narration,
            language_codes=language_codes,
            scene_key=scenario_scene_id,
            screen=_strip_inline_code(row["screen"]),
            subtitle_cue=row["subtitleCue"],
            dual_scripts=dual_scripts,
        )
        scene_id = f"scene-{idx:02d}"
        scene_title = row["subtitleCue"].strip() or f"씬 {idx}"
        scene = {
            "id": scene_id,
            "title": scene_title,
            "narration": narration_by_lang.get(primary_lang, narration),
            "narrationByLang": narration_by_lang,
            "durationSec": duration_sec,
            "url": _resolve_scene_url(row["screen"], base_url=base_url),
            "actions": _build_actions(row["action"], scene_no=idx, duration_sec=duration_sec),
            "scenario": {
                "scene": scenario_scene_id,
                "time": row["time"],
                "screen": _strip_inline_code(row["screen"]),
                "action": row["action"],
                "subtitleCue": row["subtitleCue"],
                "ttsRate": row["ttsRate"],
            },
        }
        scenes.append(scene)

    target_duration = _extract_target_duration(scenario_text)
    if target_duration <= 0:
        target_duration = total_duration
    scenario_title = _extract_title(scenario_text)
    payload = {
        "title": title or scenario_title or _default_title(scenario_version),
        "language": language_expr,
        "durationSec": target_duration,
        "showcaseScenarioVersion": scenario_version,
        "showcaseScenarioPath": str(scenario_path),
        "showcaseScenarioTargetDurationSec": target_duration,
        "scenes": scenes,
    }
    return normalize_kr_manifest_payload(payload)


def main() -> int:
    args = parse_args()
    scenario_path = _resolve_scenario_path(args)
    if not scenario_path.exists():
        print(f"[scenario-apply] scenario file not found: {scenario_path}")
        return 1

    manifest_path = Path(args.manifest).resolve()
    script_path = Path(args.script_out).resolve()
    reuse_existing = args.reuse_existing.strip().lower() == "true"
    if reuse_existing and _is_reusable(
        manifest_path=manifest_path,
        script_path=script_path,
        scenario_path=scenario_path,
        scenario_version=args.scenario_version,
    ):
        print("[scenario-apply] reuse-existing=true (skip apply)")
        print(f"[scenario-apply] manifest: {manifest_path}")
        print(f"[scenario-apply] script: {script_path}")
        return 0

    scenario_text = scenario_path.read_text(encoding="utf-8")
    script_dir_raw = args.script_dir.strip()
    script_dir = Path(script_dir_raw).resolve() if script_dir_raw else scenario_path.parent
    language_codes = resolve_target_languages(args.language)
    try:
        dual_scripts = _load_dual_scripts(
            script_dir=script_dir,
            scenario_version=args.scenario_version,
            language_codes=language_codes,
        )
    except ValueError as exc:
        print(f"[scenario-apply] {exc}")
        return 1

    try:
        payload = _build_manifest_payload(
            scenario_text=scenario_text,
            scenario_path=scenario_path,
            scenario_version=args.scenario_version,
            language_expr=args.language,
            base_url=args.base_url,
            title=args.title.strip(),
            dual_scripts=dual_scripts,
        )
    except ValueError as exc:
        print(f"[scenario-apply] {exc}")
        return 1
    issues = validate_kr_manifest_payload(payload)
    if issues:
        for issue in issues:
            print(f"[scenario-apply] terminology issue: {issue}")
        return 1

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    script_path.write_text(_build_script_markdown(payload), encoding="utf-8")

    print(f"[scenario-apply] version: {args.scenario_version}")
    print(f"[scenario-apply] scenario: {scenario_path}")
    print(f"[scenario-apply] manifest: {manifest_path}")
    print(f"[scenario-apply] script: {script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
