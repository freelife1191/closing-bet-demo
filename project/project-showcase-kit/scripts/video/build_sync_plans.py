#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build TTS and caption sync plans from scenario markdown files."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple


MIN_TTS_RATE = 4.4
MAX_TTS_RATE = 4.8
DEFAULT_TTS_RATE = 4.6
MAX_COMPRESSION_RATIO = 0.08


@dataclass
class ScenarioRow:
    scene_id: str
    start_sec: float
    end_sec: float
    target_sec: float
    narration: str
    tts_rate_hint: float
    subtitle_cue: str


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="Build sync plans")
    parser.add_argument("--scenario-dir", default="project/video/scenarios")
    parser.add_argument("--out-dir", default="project/video/scenarios")
    return parser.parse_args()


def _parse_hms(raw: str) -> float:
    parts = raw.strip().split(":")
    if len(parts) != 2:
        return 0.0
    minutes = int(parts[0])
    seconds = int(parts[1])
    return float(minutes * 60 + seconds)


def _parse_time_range(raw: str) -> Tuple[float, float]:
    value = raw.strip()
    if "-" not in value:
        return 0.0, 0.0
    start_raw, end_raw = [part.strip() for part in value.split("-", 1)]
    start_sec = _parse_hms(start_raw)
    end_sec = _parse_hms(end_raw)
    if end_sec < start_sec:
        end_sec = start_sec
    return start_sec, end_sec


def _safe_float(raw: str, default: float) -> float:
    try:
        return float(raw)
    except Exception:
        return default


def _clean_chars(text: str) -> int:
    cleaned = re.sub(r"\s+", "", text)
    return len(cleaned)


def _slug_from_filename(path: Path) -> str:
    stem = path.stem
    if stem.startswith("scenario_"):
        return stem.replace("scenario_", "", 1)
    return stem


def _target_duration_from_header(text: str) -> int:
    match = re.search(r"targetDurationSec:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return 0


def _parse_scenario_rows(path: Path) -> Tuple[int, List[ScenarioRow]]:
    text = path.read_text(encoding="utf-8")
    header_target = _target_duration_from_header(text)

    rows: List[ScenarioRow] = []
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

        scene_id = cells[0]
        start_sec, end_sec = _parse_time_range(cells[1])
        target_sec = max(0.5, end_sec - start_sec)
        narration = cells[4]
        tts_rate_hint = _safe_float(cells[5], DEFAULT_TTS_RATE)
        subtitle_cue = cells[6]

        rows.append(
            ScenarioRow(
                scene_id=scene_id,
                start_sec=start_sec,
                end_sec=end_sec,
                target_sec=target_sec,
                narration=narration,
                tts_rate_hint=tts_rate_hint,
                subtitle_cue=subtitle_cue,
            )
        )

    return header_target, rows


def _plan_scene(row: ScenarioRow) -> Dict[str, float | str]:
    chars = _clean_chars(row.narration)
    if chars == 0:
        return {
            "scene_id": row.scene_id,
            "target_sec": round(row.target_sec, 3),
            "speech_est_sec": 0.0,
            "speech_final_sec": 0.0,
            "tts_rate": row.tts_rate_hint,
            "overflow_sec": 0.0,
            "compression_ratio": 0.0,
            "adjustment_step": "none",
            "cue_start": round(row.start_sec, 3),
            "cue_end": round(row.end_sec, 3),
        }

    base_rate = min(MAX_TTS_RATE, max(MIN_TTS_RATE, row.tts_rate_hint))
    speech_est_sec = chars / base_rate

    adjustment_step = "none"
    applied_rate = base_rate
    compression_ratio = 0.0
    speech_final_sec = speech_est_sec

    if speech_est_sec > row.target_sec:
        needed_rate = chars / row.target_sec
        applied_rate = min(MAX_TTS_RATE, max(MIN_TTS_RATE, needed_rate))
        speech_after_speed = chars / applied_rate

        if speech_after_speed <= row.target_sec:
            adjustment_step = "speed"
            speech_final_sec = speech_after_speed
        else:
            adjustment_step = "speed+compression"
            compressed_chars = int(round(chars * (1.0 - MAX_COMPRESSION_RATIO)))
            compressed_chars = max(1, compressed_chars)
            compression_ratio = (chars - compressed_chars) / chars
            speech_after_compression = compressed_chars / applied_rate

            if speech_after_compression <= row.target_sec:
                speech_final_sec = speech_after_compression
            else:
                adjustment_step = "speed+compression+scene_extend"
                speech_final_sec = speech_after_compression

    overflow_sec = max(0.0, speech_final_sec - row.target_sec)
    cue_end = row.end_sec + overflow_sec
    fill_ratio = 0.0
    if row.target_sec > 0:
        fill_ratio = speech_final_sec / row.target_sec

    return {
        "scene_id": row.scene_id,
        "target_sec": round(row.target_sec, 3),
        "speech_est_sec": round(speech_est_sec, 3),
        "speech_final_sec": round(speech_final_sec, 3),
        "fill_ratio": round(fill_ratio, 4),
        "tts_rate": round(applied_rate, 3),
        "overflow_sec": round(overflow_sec, 3),
        "compression_ratio": round(compression_ratio, 4),
        "adjustment_step": adjustment_step,
        "cue_start": round(row.start_sec, 3),
        "cue_end": round(cue_end, 3),
    }


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    scenario_dir = Path(args.scenario_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario_files = sorted(scenario_dir.glob("scenario_*.md"))
    if not scenario_files:
        print(f"[sync-plan] no scenario files found: {scenario_dir}")
        return 1

    for scenario_path in scenario_files:
        version = _slug_from_filename(scenario_path)
        header_target, rows = _parse_scenario_rows(scenario_path)
        scene_plans = [_plan_scene(row) for row in rows]

        target_duration = header_target
        if target_duration <= 0:
            target_duration = int(round(sum(float(item["target_sec"]) for item in scene_plans)))

        tts_payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "sourceScenario": str(scenario_path),
            "targetDurationSec": target_duration,
            "policy": {
                "minTtsRate": MIN_TTS_RATE,
                "maxTtsRate": MAX_TTS_RATE,
                "defaultTtsRate": DEFAULT_TTS_RATE,
                "maxCompressionRatio": MAX_COMPRESSION_RATIO,
                "order": ["speed", "compression", "scene_extend"],
            },
            "scenes": scene_plans,
        }

        caption_payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "sourceScenario": str(scenario_path),
            "targetDurationSec": target_duration,
            "scenes": [
                {
                    "scene_id": item["scene_id"],
                    "target_sec": item["target_sec"],
                    "speech_est_sec": item["speech_est_sec"],
                    "fill_ratio": item["fill_ratio"],
                    "tts_rate": item["tts_rate"],
                    "cue_start": item["cue_start"],
                    "cue_end": item["cue_end"],
                    "overflow_sec": item["overflow_sec"],
                    "adjustment_step": item["adjustment_step"],
                }
                for item in scene_plans
            ],
        }

        tts_out = out_dir / f"tts_plan_{version}.json"
        caption_out = out_dir / f"caption_plan_{version}.json"
        _write_json(tts_out, tts_payload)
        _write_json(caption_out, caption_payload)

        print(f"sync plan generated: {tts_out}")
        print(f"sync plan generated: {caption_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
