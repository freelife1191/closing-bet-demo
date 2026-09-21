#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run actual pykrx contracts apart from suite-wide module doubles and credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_real_pykrx_public_apis_preserve_numpy_dataframe_contracts():
    probe = Path(__file__).resolve().parents[1] / "fixtures" / "pykrx_contract_probe.py"
    env = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "LANG", "TMPDIR") if key in os.environ}
    env.update(PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, str(probe)], cwd=probe.parent, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["cases"] == ["ohlcv", "fundamentals", "net_purchases", "index", "business_day", "daily_flow"]
    assert payload["external_requests"] == 0
