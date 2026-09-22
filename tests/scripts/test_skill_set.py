#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""프로젝트 스킬 셋의 고정 사본·정본 경로·호스트 링크가 문서와 같은지 확인한다.

vendor/skills 는 sources.lock.json 과 바이트 단위로 일치해야 하고, 프로젝트 스킬은
.claude/skills/ 가 정본이며 .agents/skills/ 의 같은 이름은 그 정본을 가리키는 링크다.
"""

import re
from pathlib import Path

from scripts import skill_set_lock

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_SKILLS = ("closing-bet-nextjs", "closing-bet-python", "closing-bet-verify")
LINKED_SKILLS = PROJECT_SKILLS + ("dev-cycle",)


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"frontmatter 가 없다: {path}"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip():
            fields[key.strip()] = value.strip()
    return fields


def test_vendor_skills_match_lock():
    assert skill_set_lock.verify() == []


def test_vendor_lock_pins_every_source_to_a_commit():
    lock = skill_set_lock.build_lock()
    assert {entry["name"] for entry in lock["sources"]} == {
        source["name"] for source in skill_set_lock.SOURCES
    }
    for entry in lock["sources"]:
        assert re.fullmatch(r"[0-9a-f]{40}", entry["commit"]), entry["name"]
        assert entry["files"], entry["name"]
        skill_md = REPO_ROOT / entry["destination"] / "SKILL.md"
        assert _frontmatter(skill_md)["name"] == entry["name"]


def test_project_skill_names_match_their_directories():
    for name in PROJECT_SKILLS:
        skill_md = REPO_ROOT / ".claude" / "skills" / name / "SKILL.md"
        fields = _frontmatter(skill_md)
        assert fields["name"] == name
        assert len(fields.get("description", "")) > 40, name


def test_agents_skill_links_point_at_the_claude_canonical_copy():
    for name in LINKED_SKILLS:
        link = REPO_ROOT / ".agents" / "skills" / name
        assert link.is_symlink(), name
        assert Path(link.readlink()).as_posix() == f"../../.claude/skills/{name}", name
        assert (link / "SKILL.md").is_file(), name


def test_cycle_documents_wire_the_skill_set_in():
    """정의만 있고 부르는 자리가 없는 상태로 되돌아가지 않게 한다."""
    cycle = (REPO_ROOT / ".claude" / "skills" / "dev-cycle" / "SKILL.md").read_text(encoding="utf-8")
    assert "| 코드 리뷰 | `closing-bet-reviewer`" in cycle
    for name in PROJECT_SKILLS:
        assert f"`{name}`" in cycle, name
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    for name in PROJECT_SKILLS + ("closing-bet-reviewer",):
        assert f"`{name}`" in claude_md, name


def test_reviewer_role_is_defined_for_both_hosts():
    claude_role = REPO_ROOT / ".claude" / "agents" / "closing-bet-reviewer.md"
    assert _frontmatter(claude_role)["name"] == "closing-bet-reviewer"
    codex_role = (REPO_ROOT / ".codex" / "agents" / "closing-bet-reviewer.toml").read_text(
        encoding="utf-8"
    )
    assert 'name = "closing-bet-reviewer"' in codex_role
    assert 'sandbox_mode = "read-only"' in codex_role
    assert ".claude/agents/closing-bet-reviewer.md" in codex_role
