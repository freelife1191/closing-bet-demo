#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Dict, List

ROOT_SENTINEL = "project-showcase-kit-src"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build project-showcase-kit dist artifacts")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_yaml(path: Path) -> Dict:
    import yaml

    payload = yaml.safe_load(_read_text(path)) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML payload in {path}")
    return payload


def _load_tools(repo_root: Path) -> List[Dict[str, str]]:
    tool_map = repo_root / "project" / "project-showcase-kit-src" / "manifest" / "tool-map.yaml"
    payload = _load_yaml(tool_map)
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("tool-map.yaml must contain a tools list")
    return [item for item in tools if isinstance(item, dict)]


def _load_skills(repo_root: Path) -> List[Dict[str, str]]:
    skills_map = repo_root / "project" / "project-showcase-kit-src" / "manifest" / "skills-map.yaml"
    payload = _load_yaml(skills_map)
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        raise ValueError("skills-map.yaml must contain a skills list")
    return [item for item in skills if isinstance(item, dict)]


def _copy_skill_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _render_common_readme(repo_root: Path, dist_root: Path) -> None:
    template_path = repo_root / "project" / "project-showcase-kit-src" / "templates" / "common" / "README.template.md"
    content = _read_text(template_path).replace("{{PROJECT_ROOT}}", str(repo_root))
    _write_text(dist_root / "README.md", content)


def _render_installers(repo_root: Path, dist_root: Path, tools: List[Dict[str, str]]) -> None:
    for tool in tools:
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        template = repo_root / "project" / "project-showcase-kit-src" / "templates" / name / "install.template.sh"
        output = dist_root / "install" / name / "install.sh"
        _write_text(output, _read_text(template))
        os.chmod(output, 0o755)


def _populate_canonical_skills(repo_root: Path, dist_root: Path, skills: List[Dict[str, str]]) -> None:
    source_root = repo_root / ".agent" / "skills"
    canonical_root = dist_root / "skills" / "canonical"
    canonical_root.mkdir(parents=True, exist_ok=True)

    for item in skills:
        source_name = str(item.get("source", "")).strip()
        target_name = str(item.get("target", "")).strip()
        if not source_name or not target_name:
            continue
        preferred_source = source_root / target_name
        fallback_source = source_root / source_name
        source_dir = preferred_source if preferred_source.exists() else fallback_source
        if not source_dir.exists():
            continue
        target_dir = canonical_root / target_name
        _copy_skill_tree(source_dir, target_dir)


def build_dist(repo_root: Path) -> Path:
    dist_root = repo_root / "project" / "project-showcase-kit-dist"
    dist_root.mkdir(parents=True, exist_ok=True)
    tools = _load_tools(repo_root)
    skills = _load_skills(repo_root)
    _populate_canonical_skills(repo_root, dist_root, skills)
    _render_installers(repo_root, dist_root, tools)
    _render_common_readme(repo_root, dist_root)
    return dist_root


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    dist_root = build_dist(repo_root)
    print(dist_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

