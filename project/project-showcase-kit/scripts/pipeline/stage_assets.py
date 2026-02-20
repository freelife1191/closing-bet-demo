#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate promotion prompt-pack assets for showcase outputs."""

from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path


ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y3Wf2QAAAAASUVORK5CYII="
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="assets stage")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--language", default="ko+en")
    parser.add_argument("--thumbnail-mode", default="manual")
    parser.add_argument("--title", default="오늘 장마감 핵심 시그널")
    parser.add_argument("--subtitle", default="AI가 뽑은 KR 시장 인사이트")
    parser.add_argument("--out-dir", default="project/video/assets")
    return parser.parse_args()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _thumbnail_prompt(title: str, subtitle: str, language: str, mode: str) -> str:
    return "\n".join(
        [
            "# NanoBanana Pro Thumbnail Prompt",
            "",
            "## System Prompt",
            "You are a senior YouTube thumbnail strategist for fintech product launches.",
            "Produce text-safe, high-contrast concepts optimized for KR/EN bilingual audiences.",
            "",
            "## User Prompt",
            f"- Title: {title}",
            f"- Subtitle: {subtitle}",
            f"- Language: {language}",
            f"- Mode: {mode}",
            "- Must emphasize: Market Gate, VCP, Closing Bet, AI workflow",
            "",
            "## Output Format",
            "1. Concept Name",
            "2. Visual Composition (foreground/background/focal point)",
            "3. Typography Layout (safe area and font hierarchy)",
            "4. Color Palette (hex)",
            "5. Negative Prompt",
            "",
            "## Quality Checklist",
            "- No text clipping in 16:9",
            "- Readable at small-size feed preview",
            "- Finance/analytics tone without clickbait distortion",
        ]
    ) + "\n"


def _youtube_description_prompt(title: str, subtitle: str, language: str) -> str:
    return "\n".join(
        [
            "# YouTube Description Prompt",
            "",
            "## System Prompt",
            "You are a launch copywriter for B2B/B2C trading analytics software.",
            "Write concise, trust-first copy with clear feature-value mapping.",
            "",
            "## User Prompt",
            f"- Video Title: {title}",
            f"- Core Message: {subtitle}",
            f"- Language Target: {language}",
            "- Include feature blocks: Market Gate, VCP, Closing Bet, AI Chat, Data Status",
            "",
            "## Output Format",
            "1. Hook sentence",
            "2. Feature summary bullets (5)",
            "3. Credibility/ops section",
            "4. CTA",
            "5. Hashtags",
            "",
            "## Quality Checklist",
            "- Avoid exaggerated profit claims",
            "- Keep compliance-safe wording",
            "- Mention ko+en deliverable context naturally",
        ]
    ) + "\n"


def _project_overview_doc_prompt(title: str, subtitle: str, language: str) -> str:
    return "\n".join(
        [
            "# Project Overview Document Prompt",
            "",
            "## System Prompt",
            "You are a technical product marketer writing executive-ready docs.",
            "Blend architecture facts with practical user workflow narrative.",
            "",
            "## User Prompt",
            f"- Project: {title}",
            f"- Positioning: {subtitle}",
            f"- Language: {language}",
            "- Required sections: Problem, Solution, Architecture, Feature Walkthrough, Reliability, Roadmap",
            "",
            "## Output Format",
            "- Markdown document with H2 section headers",
            "- Per section: Summary + Evidence bullets",
            "- One final 'Why this matters now' section",
            "",
            "## Quality Checklist",
            "- Use consistent terminology (Market Gate, VCP, Closing Bet)",
            "- Avoid ambiguous buzzwords",
            "- Ensure each claim maps to observable feature/output",
        ]
    ) + "\n"


def _ppt_prompt(title: str, subtitle: str, language: str) -> str:
    return "\n".join(
        [
            "# Gemini PPT Slide Prompt",
            "",
            "## System Prompt",
            "You are a presentation architect for product demo decks.",
            "Design narrative-first slide structures that stay visually clean and defensible.",
            "",
            "## User Prompt",
            f"- Deck Title: {title}",
            f"- Deck Theme: {subtitle}",
            f"- Delivery Language: {language}",
            "- Target: 10 slides",
            "- Mandatory flow: Market context -> Product architecture -> Feature demo -> Quality gate evidence -> CTA",
            "",
            "## Output Format",
            "1. Slide-by-slide outline (title + key bullets)",
            "2. Visual instruction per slide",
            "3. Speaker note summary per slide",
            "",
            "## Quality Checklist",
            "- One message per slide",
            "- Avoid overcrowded bullets",
            "- Include measurable evidence on quality/sync gates",
        ]
    ) + "\n"


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_prompt_new = out_dir / "thumbnail_prompt_nanobanana_pro.md"
    youtube_desc_prompt = out_dir / "youtube_description_prompt.md"
    overview_doc_prompt = out_dir / "project_overview_doc_prompt.md"
    ppt_prompt = out_dir / "ppt_slide_prompt_gemini.md"

    # Backward-compatible artifacts
    thumbnail_prompt_legacy = out_dir / "thumbnail_prompt.md"
    copy_md = out_dir / "copy.md"
    release_notes = out_dir / "release_notes.md"
    promo_brief = out_dir / "promo_brief.md"

    promo_deck = out_dir / "promo_deck.pptx"
    thumbnail_png = out_dir / "thumbnail_preview.png"
    index_json = out_dir / "assets_index.json"

    _write(thumbnail_prompt_new, _thumbnail_prompt(args.title, args.subtitle, args.language, args.thumbnail_mode))
    _write(youtube_desc_prompt, _youtube_description_prompt(args.title, args.subtitle, args.language))
    _write(overview_doc_prompt, _project_overview_doc_prompt(args.title, args.subtitle, args.language))
    _write(ppt_prompt, _ppt_prompt(args.title, args.subtitle, args.language))

    # Legacy files keep existing contracts stable.
    _write(thumbnail_prompt_legacy, thumbnail_prompt_new.read_text(encoding="utf-8"))
    _write(copy_md, f"# Promo Copy\n\n{args.title}\n\n{args.subtitle}\n")
    _write(release_notes, "# Release Notes\n\n- prompt-pack assets generated\n")
    _write(promo_brief, "# Promo Brief\n\n- Audience: KR market users\n- Goal: explain showcase flow\n")

    promo_deck.write_bytes(b"PSK_PROMO_DECK_PLACEHOLDER\n")
    thumbnail_png.write_bytes(base64.b64decode(ONE_PIXEL_PNG_BASE64))

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "title": args.title,
        "subtitle": args.subtitle,
        "language": args.language,
        "thumbnailMode": args.thumbnail_mode,
        "files": {
            "thumbnailPromptNanoBananaPro": str(thumbnail_prompt_new),
            "youtubeDescriptionPrompt": str(youtube_desc_prompt),
            "projectOverviewDocPrompt": str(overview_doc_prompt),
            "pptSlidePromptGemini": str(ppt_prompt),
            "thumbnailPromptLegacy": str(thumbnail_prompt_legacy),
            "copy": str(copy_md),
            "releaseNotes": str(release_notes),
            "promoBrief": str(promo_brief),
            "promoDeck": str(promo_deck),
            "thumbnailPreview": str(thumbnail_png),
        },
    }
    index_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"assets dir: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
