#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공개 수집기와 하위 모듈이 한 구현을 사용한다."""


def test_public_and_submodule_share_krx_class():
    from engine.collectors import KRXCollector
    from engine.collectors.krx import KRXCollector as SubmoduleKRX

    assert KRXCollector is SubmoduleKRX


def test_service_first_import_does_not_create_a_collector_cycle():
    import subprocess
    from pathlib import Path
    import sys
    result = subprocess.run([sys.executable, "-c", "import services.investor_trend_5day_service; from engine import KRXCollector; from engine.collectors.krx import KRXCollector as direct; assert KRXCollector is direct"], capture_output=True, text=True, timeout=15, cwd=Path(__file__).resolve().parents[2])
    assert result.returncode == 0, result.stderr
