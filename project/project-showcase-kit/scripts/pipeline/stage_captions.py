#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate subtitles from manifest narration."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from kr_text_policy import normalize_kr_text
from language_voice_policy import default_language_selection, resolve_target_languages
from language_voice_policy import translate_legacy_scene_text

CAPTION_WRAP_THRESHOLD = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="captions stage")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--language", default="ko+en")
    parser.add_argument("--voice-meta", default="project/video/audio/narration.json")
    parser.add_argument("--out-srt", default="project/video/captions/subtitles.srt")
    parser.add_argument("--out-json", default="project/video/captions/subtitles.json")
    return parser.parse_args()


def _safe_duration(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        return 6.0
    return max(1.0, v)


def _fmt_srt(ts: float) -> str:
    millis = int(round(ts * 1000))
    hours = millis // 3_600_000
    millis -= hours * 3_600_000
    minutes = millis // 60_000
    millis -= minutes * 60_000
    seconds = millis // 1_000
    millis -= seconds * 1_000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _char_display_width(char: str) -> int:
    if not char:
        return 0
    if char.isspace():
        return 1
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


def _text_display_width(text: str) -> int:
    return sum(_char_display_width(char) for char in text)


def _balanced_split_index(text: str) -> int:
    target = _text_display_width(text) / 2.0
    running = 0.0
    best_index = -1
    best_gap = float("inf")
    for index, char in enumerate(text):
        running += _char_display_width(char)
        if char == " ":
            gap = abs(running - target)
            if gap < best_gap:
                best_gap = gap
                best_index = index

    if best_index >= 0:
        return best_index

    running = 0.0
    for index, char in enumerate(text):
        running += _char_display_width(char)
        if running >= target:
            return index
    return max(1, len(text) // 2)


def _wrap_caption_text(text: str) -> str:
    normalized = " ".join(text.replace("\n", " ").split())
    if not normalized:
        return ""
    if _text_display_width(normalized) <= CAPTION_WRAP_THRESHOLD:
        return normalized

    split_index = _balanced_split_index(normalized)
    if split_index <= 0 or split_index >= len(normalized) - 1:
        return normalized

    if normalized[split_index] == " ":
        first = normalized[:split_index].strip()
        second = normalized[split_index + 1 :].strip()
    else:
        first = normalized[:split_index].strip()
        second = normalized[split_index:].strip()

    if not first or not second:
        return normalized
    return f"{first}\n{second}"


def _copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    shutil.copy2(src, dst)


def _load_voice_meta(voice_meta_path: Path) -> Dict[str, Any]:
    if not voice_meta_path.exists():
        return {}
    try:
        return json.loads(voice_meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_voice_duration(voice_payload: Dict[str, Any]) -> float:
    try:
        duration = float(voice_payload.get("durationSeconds") or 0.0)
    except Exception:
        return 0.0
    return max(0.0, duration)


def _extract_scene_audio_ranges(
    voice_payload: Dict[str, Any],
    language_code: str,
) -> List[Dict[str, Any]]:
    code = language_code.strip().lower()
    ranges: List[Dict[str, Any]] = []

    tracks = voice_payload.get("tracks")
    if isinstance(tracks, list):
        for row in tracks:
            item = row if isinstance(row, dict) else {}
            if str(item.get("languageCode", "")).strip().lower() != code:
                continue
            scene_ranges = item.get("sceneAudioRanges")
            if isinstance(scene_ranges, list):
                ranges = [entry for entry in scene_ranges if isinstance(entry, dict)]
                break

    if not ranges:
        top_level = voice_payload.get("sceneAudioRanges")
        if isinstance(top_level, list):
            ranges = [entry for entry in top_level if isinstance(entry, dict)]

    return ranges


def _scaled_scene_durations(scenes: List[Dict[str, Any]], target_duration: float) -> tuple[List[float], float]:
    base = [_safe_duration(scene.get("durationSec", 6)) for scene in scenes]
    source_total = sum(base)
    if target_duration <= 0.0 or source_total <= 0.0:
        return base, source_total

    scale = target_duration / source_total
    scaled = [max(duration * scale, 0.25) for duration in base]
    scaled_total = sum(scaled)
    if scaled_total <= 0.0:
        return base, source_total

    # Preserve total length exactly to avoid drift in the last caption.
    normalized = [duration * target_duration / scaled_total for duration in scaled]
    return normalized, source_total


def _resolve_scene_text(scene: Dict[str, Any], language_code: str, scene_index: int) -> str:
    by_lang = scene.get("narrationByLang")
    text = ""
    used_explicit = False
    if isinstance(by_lang, dict):
        text = str(by_lang.get(language_code, "")).strip()
        used_explicit = bool(text)
        if not text and language_code != "ko":
            text = str(by_lang.get("en", "")).strip()
        if not text:
            text = str(by_lang.get("ko", "")).strip()
    if not text:
        text = str(scene.get("narration", "")).strip()
    if text and not used_explicit:
        text = translate_legacy_scene_text(text, language_code)
    normalized = normalize_kr_text(text)
    return normalized if normalized else f"scene {scene_index}"


def _build_captions_for_language(
    scenes: List[Dict[str, Any]],
    durations: List[float],
    effective_target: float,
    language_code: str,
) -> List[Dict[str, Any]]:
    captions: List[Dict[str, Any]] = []
    current = 0.0
    for idx, scene in enumerate(scenes, start=1):
        duration = durations[idx - 1] if idx - 1 < len(durations) else _safe_duration(scene.get("durationSec", 6))
        text = _resolve_scene_text(scene, language_code, idx)
        start = current
        end = current + duration
        if idx == len(scenes) and effective_target > 0:
            end = max(end, effective_target)
        captions.append(
            {
                "index": idx,
                "sceneId": str(scene.get("id") or f"scene-{idx:02d}"),
                "startSec": round(start, 3),
                "endSec": round(end, 3),
                "text": text,
            }
        )
        current = end
    return captions


def _build_captions_with_scene_ranges(
    scenes: List[Dict[str, Any]],
    scene_ranges: List[Dict[str, Any]],
    language_code: str,
    effective_target: float,
) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in scene_ranges:
        item = row if isinstance(row, dict) else {}
        scene_id = str(item.get("sceneId", "")).strip()
        if scene_id:
            by_id[scene_id] = item

    captions: List[Dict[str, Any]] = []
    cursor = 0.0
    for idx, scene in enumerate(scenes, start=1):
        scene_id = str(scene.get("id") or f"scene-{idx:02d}")
        item = by_id.get(scene_id, {})
        start = float(item.get("startSec")) if item.get("startSec") is not None else cursor
        end = float(item.get("endSec")) if item.get("endSec") is not None else (start + _safe_duration(scene.get("durationSec", 6)))
        if end < start:
            end = start
        text = _resolve_scene_text(scene, language_code, idx)
        captions.append(
            {
                "index": idx,
                "sceneId": scene_id,
                "startSec": round(start, 3),
                "endSec": round(end, 3),
                "text": text,
            }
        )
        cursor = end

    if captions and effective_target > 0:
        captions[-1]["endSec"] = round(max(float(captions[-1]["endSec"]), effective_target), 3)
    return captions


def _compute_scene_boundary_metrics(
    captions: List[Dict[str, Any]],
    scene_ranges: List[Dict[str, Any]],
    tolerance_sec: float = 0.15,
) -> tuple[float, int]:
    by_scene_end: Dict[str, float] = {}
    for row in scene_ranges:
        item = row if isinstance(row, dict) else {}
        scene_id = str(item.get("sceneId", "")).strip()
        if not scene_id:
            continue
        try:
            by_scene_end[scene_id] = float(item.get("endSec") or 0.0)
        except Exception:
            continue

    max_delta = 0.0
    violation_count = 0
    for row in captions:
        scene_id = str(row.get("sceneId", "")).strip()
        if scene_id not in by_scene_end:
            continue
        try:
            caption_end = float(row.get("endSec") or 0.0)
        except Exception:
            caption_end = 0.0
        delta = abs(caption_end - by_scene_end[scene_id])
        max_delta = max(max_delta, delta)
        if delta > tolerance_sec:
            violation_count += 1

    return round(max_delta, 3), violation_count


def _write_srt(path: Path, captions: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    srt_lines: List[str] = []
    for row in captions:
        wrapped_text = _wrap_caption_text(str(row["text"]))
        srt_lines.extend(
            [
                str(row["index"]),
                f"{_fmt_srt(float(row['startSec']))} --> {_fmt_srt(float(row['endSec']))}",
                wrapped_text,
                "",
            ]
        )
    path.write_text("\n".join(srt_lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    voice_meta_path = Path(args.voice_meta).resolve()
    out_srt = Path(args.out_srt).resolve()
    out_json = Path(args.out_json).resolve()

    if not manifest_path.exists():
        print(f"[captions] manifest not found: {manifest_path}")
        return 1

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if not isinstance(scenes, list) or not scenes:
        print(f"[captions] scenes is empty: {manifest_path}")
        return 1

    requested_language = args.language.strip() if args.language.strip() else str(data.get("language", default_language_selection()))
    language_codes = resolve_target_languages(requested_language)
    voice_payload = _load_voice_meta(voice_meta_path)
    target_duration = _load_voice_duration(voice_payload)
    durations, source_duration = _scaled_scene_durations(scenes, target_duration)
    effective_target = target_duration if target_duration > 0 else sum(durations)
    speed_factor = (effective_target / source_duration) if source_duration > 0 else 1.0

    primary_language = language_codes[0] if language_codes else "ko"
    primary_scene_ranges = _extract_scene_audio_ranges(voice_payload, primary_language)
    if primary_scene_ranges:
        captions = _build_captions_with_scene_ranges(scenes, primary_scene_ranges, primary_language, effective_target)
    else:
        captions = _build_captions_for_language(scenes, durations, effective_target, primary_language)
    _write_srt(out_srt, captions)
    scene_boundary_max_delta, scene_boundary_violation_count = _compute_scene_boundary_metrics(
        captions=captions,
        scene_ranges=primary_scene_ranges,
        tolerance_sec=0.15,
    )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "language": requested_language,
        "languageCodes": language_codes,
        "voiceMeta": str(voice_meta_path),
        "sourceDurationSec": round(source_duration, 3),
        "targetDurationSec": round(effective_target, 3),
        "speedFactor": round(speed_factor, 4),
        "sceneBoundaryMaxDeltaSec": scene_boundary_max_delta,
        "sceneBoundaryViolationCount": scene_boundary_violation_count,
        "captions": captions,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    project_root = Path(__file__).resolve().parents[2].parent
    out_captions_dir = project_root / "out" / "captions"
    out_captions_dir.mkdir(parents=True, exist_ok=True)

    unique_srt: List[Path] = [out_captions_dir / "subtitles.srt"]
    unique_json: List[Path] = [out_captions_dir / "subtitles.json"]
    language_payloads: Dict[str, Dict[str, Any]] = {}
    for code in language_codes:
        scene_ranges = _extract_scene_audio_ranges(voice_payload, code)
        if scene_ranges:
            lang_captions = _build_captions_with_scene_ranges(scenes, scene_ranges, code, effective_target)
        else:
            lang_captions = _build_captions_for_language(scenes, durations, effective_target, code)
        lang_srt = out_captions_dir / f"subtitles.{code}.srt"
        lang_json = out_captions_dir / f"subtitles.{code}.json"
        _write_srt(lang_srt, lang_captions)
        lang_scene_delta, lang_violation_count = _compute_scene_boundary_metrics(
            captions=lang_captions,
            scene_ranges=scene_ranges,
            tolerance_sec=0.15,
        )
        lang_payload = {
            **payload,
            "languageCode": code,
            "sceneBoundaryMaxDeltaSec": lang_scene_delta,
            "sceneBoundaryViolationCount": lang_violation_count,
            "captions": lang_captions,
        }
        lang_json.write_text(json.dumps(lang_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        language_payloads[code] = lang_payload
        unique_srt.append(lang_srt)
        unique_json.append(lang_json)

    # Keep primary files synced for compatibility.
    _copy_if_needed((out_captions_dir / f"subtitles.{primary_language}.srt"), out_captions_dir / "subtitles.srt")
    _copy_if_needed((out_captions_dir / f"subtitles.{primary_language}.json"), out_captions_dir / "subtitles.json")

    payload["exports"] = {
        "srt": [str(path) for path in unique_srt],
        "json": [str(path) for path in unique_json],
    }
    payload["languagePayloads"] = {code: {"json": str((out_captions_dir / f"subtitles.{code}.json"))} for code in language_payloads}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"captions srt: {out_srt}")
    print(f"captions json: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
