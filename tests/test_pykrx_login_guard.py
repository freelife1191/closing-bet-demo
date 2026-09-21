#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression contract for non-fatal KRX authentication failures."""

import json
import os
from pathlib import Path
import subprocess
import sys


def test_pykrx_login_failures_do_not_crash_or_expose_credentials(tmp_path):
    root = Path(__file__).resolve().parents[1]
    probe = root / "tests" / "fixtures" / "pykrx_login_guard_probe.py"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "MPLCONFIGDIR": str(tmp_path / "mpl"),
    }
    result = subprocess.run(
        [sys.executable, str(probe)], cwd=root, env=environment,
        capture_output=True, text=True, timeout=30, check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {
        "cases": [
            "non_json", "http_error", "wrong_schema", "missing_error_code", "network_error", "warmup_redirect",
            "post_network_error", "post_redirect",
            "duplicate_non_json", "duplicate_http_error", "duplicate_wrong_schema", "duplicate_network_error",
            "success", "duplicate_success",
        ],
    }
