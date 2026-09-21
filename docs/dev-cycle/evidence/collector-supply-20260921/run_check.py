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
 "bench": ([str(scratch/"venv/bin/python"), str(scratch/"docs/dev-cycle/evidence/collector-supply-20260921/performance_probe.py")],scratch,240),
 "snapshotprobe": ([str(scratch/"venv/bin/python"),str(scratch/"docs/dev-cycle/evidence/collector-supply-20260921/snapshot_process_probe.py")],scratch,110),
 "fixture": ([str(scratch/"venv/bin/python"),str(scratch/"docs/dev-cycle/evidence/collector-supply-20260921/fixture_probe.py")],scratch,60),
 "pytarget": ([str(scratch/"venv/bin/python"),"-m","pytest","-q", *sys.argv[2:]],scratch,120),
 "pytest": ([str(scratch/"venv/bin/python"),"-m","pytest","-q","-ra"],scratch,180),
 "vitest": (["npx","vitest","run"],scratch/"frontend",300),
 "target": (["npx","vitest","run", *sys.argv[2:]],scratch/"frontend",120),
 "lint": (["npm","run","lint"],scratch/"frontend",120),
 "typecheck": (["npm","run","type-check"],scratch/"frontend",90),
 "build": (["npm","run","test:build"],scratch/"frontend",240),
}

command, cwd, timeout = commands[stage.split(":")[0]]
environment = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "TMPDIR", "LANG") if key in os.environ}
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(scratch), CI="true", PYTHON_DOTENV_DISABLED="1", TMPDIR=str(scratch / "tmp"))
if stage == "build:security":
    environment.update(NEXTAUTH_SECRET="qa-auth-nonsecret-sentinel-20260920", INTERNAL_IDENTITY_SECRET="qa-identity-nonsecret-sentinel-20260920", ADMIN_API_TOKEN="qa-admin-nonsecret-sentinel-20260920")
started = time.monotonic()
started_at = datetime.now(timezone.utc).isoformat()
with (evidence / (stage.replace(":", "-") + ".log")).open("w") as output:
    process = subprocess.Popen(["sandbox-exec", "-f", str(scratch / "qa.sb"), *command], cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    timed_out = False
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        code = 124
result = {"stage": stage, "started_at": started_at, "ended_at": datetime.now(timezone.utc).isoformat(), "pid": process.pid, "command": command, "cwd": str(cwd), "timeout_seconds": timeout, "timed_out": timed_out, "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2)}
(evidence / (stage.replace(":", "-") + ".json")).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
sys.exit(code)
