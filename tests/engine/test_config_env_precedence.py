#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
환경변수 우선순위 회귀 테스트
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_process_env_overrides_dotenv_for_scheduler_enabled(tmp_path: Path):
    """프로세스 환경변수는 .env 값보다 우선해야 한다."""
    (tmp_path / ".env").write_text("SCHEDULER_ENABLED=true\n", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    env["SCHEDULER_ENABLED"] = "false"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from engine.config import app_config; print(app_config.SCHEDULER_ENABLED)",
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
