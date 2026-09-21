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
execution_venv = Path(json.loads((evidence / "review-input.json").read_text()).get("execution_venv", str(scratch / "venv")))
execution_python = execution_venv / "bin/python"
commands = {
 "cookie-red": ([str(execution_python),str(scratch/"docs/dev-cycle/evidence/numpy-cookie-fix-20260921/red_naver_probe.py")],scratch,60),
 "sdk": ([str(execution_python),str(scratch/"docs/dev-cycle/evidence/numpy-cookie-fix-20260921/sdk_probe.py")],scratch,60),
 "pipcheck": ([str(execution_python), "-m", "pip", "check"],scratch,60),
 "versions": ([str(execution_python), "-c", "import sys,numpy,importlib.metadata as m,json;print(json.dumps(dict(prefix=sys.prefix,numpy=numpy.__version__,pykrx=m.version('pykrx'))))"],scratch,60),
 "sessionprobe": ([str(execution_python), str(scratch/"docs/dev-cycle/evidence/numpy-upgrade-20260921/session_probe.py")],scratch,60),
 "bench": ([str(execution_python), str(scratch/"docs/dev-cycle/evidence/numpy-upgrade-20260921/performance_probe.py")],scratch,240),
 "snapshotprobe": ([str(execution_python),str(scratch/"docs/dev-cycle/evidence/numpy-upgrade-20260921/snapshot_process_probe.py")],scratch,110),
 "fixture": ([str(execution_python),str(scratch/"docs/dev-cycle/evidence/numpy-upgrade-20260921/fixture_probe.py")],scratch,60),
 "pytarget": ([str(execution_python),"-m","pytest","-q", *sys.argv[2:]],scratch,120),
 "pytest": ([str(execution_python),"-m","pytest","-q","-ra"],scratch,300),
 "vitest": (["npx","vitest","run"],scratch/"frontend",300),
 "target": (["npx","vitest","run", *sys.argv[2:]],scratch/"frontend",120),
 "lint": (["npm","run","lint"],scratch/"frontend",120),
 "typecheck": (["npm","run","type-check"],scratch/"frontend",90),
 "build": (["npm","run","test:build"],scratch/"frontend",240),
}

command, cwd, timeout = commands[stage.split(":")[0]]
environment = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "TMPDIR", "LANG") if key in os.environ}
environment["PATH"] = str(execution_venv / "bin") + os.pathsep + environment["PATH"]
environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(scratch), CI="true", PYTHON_DOTENV_DISABLED="1", MPLCONFIGDIR=str(scratch / "tmp/mpl"), TMPDIR=str(scratch / "tmp"))
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
