#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정리 명령의 argv만 실행한다. 실제 재시작/프로세스 조작은 금지한다."""
import json
from pathlib import Path
import subprocess
import sys


def test_restart_cleanup_passes_each_pattern_separately(tmp_path):
    root = Path(__file__).resolve().parents[1]
    lines = [line for line in (root / 'restart_all.sh').read_text().splitlines()
             if line.startswith('pkill -f ')]
    fake = tmp_path / 'pkill'
    fake.write_text(f'#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    fake.chmod(0o700)
    result = subprocess.run(['/bin/bash', '-c', '\n'.join(lines)],
                            env={'PATH': str(tmp_path)}, capture_output=True, text=True,
                            timeout=5, check=True)
    arguments = [json.loads(line) for line in result.stdout.splitlines()]
    assert arguments == [['-f', pattern] for pattern in ('flask_app.py', 'next dev', 'npm.*dev')]
    stop_text = (root / 'stop_all.sh').read_text()
    for _, pattern in arguments:
        assert f'pkill -f "{pattern}"' in stop_text
