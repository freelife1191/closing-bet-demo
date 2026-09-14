#!/usr/bin/env python3
"""Run bounded layout QA commands in this task's isolated browser namespace."""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path


EVIDENCE_DIR = Path(__file__).resolve().parent
PARENT_EVIDENCE_DIR = EVIDENCE_DIR.parent
STAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: browser.py <stage> <agent-browser command...>", file=sys.stderr)
        return 2

    stage, *args = sys.argv[1:]
    if not STAGE_PATTERN.fullmatch(stage):
        print("invalid evidence stage", file=sys.stderr)
        return 2

    scratch = Path(json.loads((PARENT_EVIDENCE_DIR / "review-input.json").read_text())["scratch"])
    env = {key: os.environ[key] for key in ("PATH", "HOME", "USER", "TMPDIR", "LANG") if key in os.environ}
    command = [
        "agent-browser",
        "--namespace", "chat-layout-20260914",
        "--session", "qa",
        "--profile", str(scratch / "layout-profile"),
        "--allowed-domains", "127.0.0.1",
        "--proxy", "http://127.0.0.1:9",
        "--proxy-bypass", "127.0.0.1",
        "--args", "--disable-background-networking",
        *args,
    ]
    process = subprocess.Popen(
        command,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=30)
        code = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        output, _ = process.communicate()
        output += "browser command timed out\n"
        code = 124

    (EVIDENCE_DIR / f"{stage}.txt").write_text(output)
    print(output, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
