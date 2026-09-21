#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""의존성 승격의 최소 런타임 계약을 격리 subprocess에서 확인한다."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_yfinance_history_uses_synthetic_yahoo_transport_only():
    root = Path(__file__).resolve().parents[1]
    probe = root / "tests" / "fixtures" / "dependency_contract_probe.py"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
    }
    result = subprocess.run(
        [sys.executable, str(probe)],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ticker": "005930.KS",
        "date": "2026-09-01",
        "close": 71_000,
        "external_requests": 0,
    }
