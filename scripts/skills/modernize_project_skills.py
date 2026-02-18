#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.skills.apply_skill_template import apply_skill_template
from scripts.skills.skill_inventory import load_target_skills


def read_frontmatter(markdown: str) -> Dict[str, str]:
    if not markdown.startswith("---"):
        return {}
    match = re.match(r"^---\n(.*?)\n---\n", markdown, flags=re.DOTALL)
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1)) or {}
    if not isinstance(payload, dict):
        return {}
    return {str(k): str(v) for k, v in payload.items()}


def extract_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def extract_commands(text: str) -> List[str]:
    candidates = re.findall(r"`([^`]+)`", text)
    commands: List[str] = []
    for item in candidates:
        token = item.strip()
        if token.startswith(("./", "python", "bash", "npm", "uv ")):
            commands.append(token)
    deduped: List[str] = []
    for command in commands:
        if command not in deduped:
            deduped.append(command)
    return deduped


def extract_outputs(text: str) -> List[str]:
    outputs: List[str] = []
    for line in text.splitlines():
        if "`" not in line:
            continue
        tokens = re.findall(r"`([^`]+)`", line)
        for token in tokens:
            if "/" in token or token.endswith((".md", ".json", ".wav", ".srt", ".mp4", ".png")):
                outputs.append(token)
    deduped: List[str] = []
    for item in outputs:
        if item not in deduped:
            deduped.append(item)
    return deduped


def normalize_description(raw: str, skill_name: str) -> str:
    desc = raw.strip().rstrip(".")
    if not desc:
        return f"Use when operating or validating the {skill_name} workflow in this project."
    if desc.lower().startswith("use when"):
        return desc
    return f"Use when {desc[0].lower()}{desc[1:]}"


def build_skill_markdown(
    skill_name: str,
    frontmatter: Dict[str, str],
    mission: str,
    commands: List[str],
    outputs: List[str],
) -> str:
    description = normalize_description(frontmatter.get("description", ""), skill_name)
    allowed_tools = frontmatter.get("allowed-tools", "Read, Write, Edit, Bash, Grep, Glob")
    mission_text = mission or f"Operate and verify the {skill_name} workflow with deterministic outputs."

    if not commands:
        commands = [f"./scripts/pipeline/run_stage.sh validate # placeholder for {skill_name}"]

    verification_lines = [
        f"- `python3 scripts/skills/validate_skill_structure.py --skills {skill_name}`",
    ]
    if outputs:
        verification_lines.extend([f"- Confirm artifact exists: `{item}`" for item in outputs[:3]])

    outputs_block = "\n".join([f"- `{item}`" for item in outputs]) if outputs else "- Document expected artifact paths for this skill."
    commands_block = "\n".join([f"- `{cmd}`" for cmd in commands])
    verification_block = "\n".join(verification_lines)

    return f"""---
name: {skill_name}
description: {description}
allowed-tools: {allowed_tools}
---

# {skill_name}

## Mission
{mission_text}

## Use this skill when
- You need this skill's workflow in the video production pipeline.
- You want deterministic outputs with explicit verification evidence.

## Do not use this skill when
- The task is unrelated to this skill's domain.
- You need a different specialized skill with stricter scope.

## Inputs
- Project sources and pipeline scripts
- Runtime environment variables required by the referenced commands

## Outputs
{outputs_block}

## Quick Commands
{commands_block}

## Verification
{verification_block}

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
"""


def write_command_docs(skill_dir: Path, commands: List[str]) -> None:
    commands_dir = skill_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    primary = commands[0] if commands else "./scripts/pipeline/run_stage.sh validate"
    (commands_dir / "run.md").write_text(
        f"# Run\n\n```bash\n{primary}\n```\n",
        encoding="utf-8",
    )
    (commands_dir / "validate.md").write_text(
        "# Validate\n\n```bash\n./scripts/pipeline/run_stage.sh validate\n```\n",
        encoding="utf-8",
    )
    (commands_dir / "recover.md").write_text(
        "# Recover\n\n```bash\n./scripts/pipeline/rerun_failed.sh\n```\n",
        encoding="utf-8",
    )


def modernize_skill(skill_name: str, skill_path: Path) -> None:
    apply_skill_template(skill_path)

    skill_md = skill_path / "SKILL.md"
    original = skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""

    frontmatter = read_frontmatter(original)
    mission = extract_section(original, "Mission")
    outputs = extract_outputs(extract_section(original, "Output") + "\n" + extract_section(original, "Outputs"))
    commands = extract_commands(original)

    updated = build_skill_markdown(
        skill_name=skill_name,
        frontmatter=frontmatter,
        mission=mission,
        commands=commands,
        outputs=outputs,
    )
    skill_md.write_text(updated, encoding="utf-8")

    write_command_docs(skill_path, commands)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Modernize project skill structure")
    parser.add_argument(
        "--targets",
        default="scripts/skills/target_skills.yaml",
        help="Target skill YAML",
    )
    parser.add_argument(
        "--skills",
        default="",
        help="Comma-separated skill names",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = {item.strip() for item in args.skills.split(",") if item.strip()}
    skills = load_target_skills(args.targets)

    for item in skills:
        name = item["name"]
        if selected and name not in selected:
            continue
        modernize_skill(name, ROOT_DIR / item["path"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
