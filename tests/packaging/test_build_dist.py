#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_build_dist_generates_all_installers() -> None:
    script = Path("project/project-showcase-kit-src/scripts/build_dist.py")
    subprocess.run([sys.executable, str(script), "--repo-root", "."], check=True)

    for tool in ["codex", "claudecode", "gemini", "antigravity"]:
        installer = Path("project/project-showcase-kit-dist/install") / tool / "install.sh"
        assert installer.is_file()
