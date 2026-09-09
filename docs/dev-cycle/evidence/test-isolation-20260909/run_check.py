#!/usr/bin/env python3
"""Bounded check runner for this round's isolated, recorded checkout."""
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

evidence = Path(__file__).resolve().parent
scratch = Path(json.loads((evidence / "review-input.json").read_text())["scratch"])
stage = sys.argv[1]
commands = {
    "pytest": ([str(scratch / "venv/bin/python"), "-m", "pytest", "-q"], scratch, 180),
    "vitest": (["npx", "vitest", "run"], scratch / "frontend", 300),
    "lint": (["npm", "run", "lint"], scratch / "frontend", 60),
    "baseline": (["npx", "vitest", "run", "tests/smoke/upgrade-smoke.test.ts", "-t", "should successfully build the application"], scratch / "frontend", 240),
    "baseline-build": (["npm", "run", "build"], scratch / "frontend", 240),
    "build": (["npm", "run", "test:build"], scratch / "frontend", 240),
    "typecheck": (["npm", "run", "type-check"], scratch / "frontend", 90),
    "target": ([str(scratch / "venv/bin/python"), "-m", "pytest", "tests/services/test_paper_trading_service.py", "-q"], scratch, 120),
    "probe": ([str(scratch / "venv/bin/python"), str(scratch / "qa_probe.py"), str(scratch)], scratch, 30),
}
command, cwd, timeout = commands[stage.split(":")[0]]
environment = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "TMPDIR", "LANG") if key in os.environ}
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(scratch), CI="true", PYTHON_DOTENV_DISABLED="1", TMPDIR=str(scratch / "tmp"))
started = time.monotonic()
started_at = datetime.now(timezone.utc).isoformat()
with (evidence / (stage + ".log")).open("w") as output:
    process = subprocess.Popen(["sandbox-exec", "-f", str(scratch / ("qa-target.sb" if stage == "target" else "qa.sb")), *command], cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    timed_out = False
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        code = 124
result = {"stage": stage, "started_at": started_at, "ended_at": datetime.now(timezone.utc).isoformat(), "pid": process.pid, "command": command, "cwd": str(cwd), "timeout_seconds": timeout, "timed_out": timed_out, "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2)}
(evidence / (stage + ".json")).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
sys.exit(code)
