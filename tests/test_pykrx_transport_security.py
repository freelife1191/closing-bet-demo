#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patched pykrx wheel의 cookie transport contract를 격리 subprocess에서 검사한다."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_pykrx_cookie_transport_stays_on_strict_krx_https_origin(tmp_path):
    root = Path(__file__).resolve().parents[1]
    probe = root / "tests" / "fixtures" / "pykrx_transport_probe.py"
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
        "cases": ["trusted", "public", "hostile", "single-read", "redirect", "naver_ohlcv", "direct_auth"],
        "external_requests": 0,
    }
