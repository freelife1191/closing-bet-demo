#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build dual-language (ko/en) scripts from showcase scenario markdown files."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ScenarioRow:
    scene_id: str
    time_range: str
    screen: str
    action: str
    narration_ko: str
    subtitle_cue: str


_PHRASE_REPLACEMENTS: list[tuple[str, str]] = [
    ("Smart Money Bot은", "Smart Money Bot"),
    ("Smart Money Bot은", "Smart Money Bot"),
    ("한국 주식", "Korean stock"),
    ("종가베팅", "closing bet"),
    ("누적 성과", "cumulative performance"),
    ("모의투자", "paper trading"),
    ("재분석", "re-analysis"),
    ("점수", "score"),
    ("등급", "grade"),
    ("시장", "market"),
    ("데이터", "data"),
    ("상태", "status"),
    ("알림", "alerts"),
    ("검증", "verification"),
    ("분석", "analysis"),
    ("플랫폼", "platform"),
    ("통합", "integrated"),
    ("시스템", "system"),
    ("운영", "operations"),
    ("자동", "automated"),
    ("화면", "screen"),
    ("강조", "highlight"),
    ("확인", "review"),
    ("보여주고", "shows"),
    ("제공해", "provides"),
    ("제공합니다", "provides"),
    ("점검", "check"),
    ("마무리", "finalize"),
    ("흐름", "workflow"),
    ("전략", "strategy"),
    ("리스크", "risk"),
    ("성능", "performance"),
    ("실행", "execution"),
    ("장마감", "market close"),
    ("코스피", "KOSPI"),
    ("코스닥", "KOSDAQ"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dual ko/en scripts")
    parser.add_argument("--scenario-dir", default="project/video/scenarios")
    parser.add_argument("--out-dir", default="project/video/scenarios")
    return parser.parse_args()


def _slug_from_filename(path: Path) -> str:
    stem = path.stem
    if stem.startswith("scenario_"):
        return stem.replace("scenario_", "", 1)
    return stem


def _strip_inline_code(text: str) -> str:
    value = text.strip()
    if value.startswith("`") and value.endswith("`") and len(value) > 1:
        return value[1:-1].strip()
    return value


def _parse_rows(path: Path) -> List[ScenarioRow]:
    rows: List[ScenarioRow] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
            ScenarioRow(
                scene_id=cells[0],
                time_range=cells[1],
                screen=_strip_inline_code(cells[2]),
                action=cells[3],
                narration_ko=cells[4],
                subtitle_cue=cells[6],
            )
        )

    return rows


def _to_english_text(text: str, scene_id: str, screen: str, subtitle_cue: str) -> str:
    updated = text
    for source, target in _PHRASE_REPLACEMENTS:
        updated = updated.replace(source, target)

    # Remove residual Hangul to enforce English-only script generation.
    updated = re.sub(r"[가-힣]+", " ", updated)
    updated = re.sub(r"[ ]{2,}", " ", updated).strip()

    if not updated:
        cue = re.sub(r"[^A-Za-z0-9 .,+\-/]", " ", subtitle_cue)
        cue = re.sub(r"\s+", " ", cue).strip()
        screen_hint = screen if screen else "the dashboard"
        if cue:
            updated = f"{scene_id} highlights {cue} on {screen_hint}."
        else:
            updated = f"{scene_id} highlights Smart Money Bot workflows on {screen_hint}."

    if "Smart Money Bot" not in updated:
        updated = f"Smart Money Bot: {updated}"

    if updated[-1] not in {".", "!", "?"}:
        updated = f"{updated}."
    return updated


def _hangul_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha() or ("\uac00" <= ch <= "\ud7a3")]
    if not letters:
        return 0.0
    hangul = sum(1 for ch in letters if "\uac00" <= ch <= "\ud7a3")
    return hangul / float(len(letters))


def _render_script(version: str, language: str, rows: List[ScenarioRow]) -> str:
    is_english = language == "en"
    lines = [
        f"# showcase {version} script ({language})",
        "",
        "- project: Smart Money Bot",
        f"- version: {version}",
        f"- language: {language}",
        "",
        "| Scene | Time | Screen | Narration |",
        "| --- | --- | --- | --- |",
    ]

    narrations: List[str] = []
    for row in rows:
        narration = row.narration_ko
        if is_english:
            narration = _to_english_text(
                text=row.narration_ko,
                scene_id=row.scene_id,
                screen=row.screen,
                subtitle_cue=row.subtitle_cue,
            )
        narrations.append(narration)
        lines.append(f"| {row.scene_id} | {row.time_range} | `{row.screen}` | {narration} |")

    if is_english:
        ratio = _hangul_ratio("\n".join(narrations))
        lines.extend(["", f"- englishHangulRatio: {ratio:.4f}"])

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    scenario_dir = Path(args.scenario_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario_files = sorted(scenario_dir.glob("scenario_*.md"))
    if not scenario_files:
        print(f"[dual-scripts] no scenario files found: {scenario_dir}")
        return 1

    for scenario_path in scenario_files:
        version = _slug_from_filename(scenario_path)
        rows = _parse_rows(scenario_path)
        if not rows:
            print(f"[dual-scripts] no scene rows: {scenario_path}")
            return 1

        ko_script = out_dir / f"script_{version}.ko.md"
        en_script = out_dir / f"script_{version}.en.md"

        ko_script.write_text(_render_script(version, "ko", rows), encoding="utf-8")
        en_script.write_text(_render_script(version, "en", rows), encoding="utf-8")

        print(f"dual script generated: {ko_script}")
        print(f"dual script generated: {en_script}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
