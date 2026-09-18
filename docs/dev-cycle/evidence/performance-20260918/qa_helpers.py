"""Small parent-owned UI helpers; selectors always come from a fresh snapshot."""
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

P = Path(__file__).resolve().parent


def ab(stage, *args):
    result = subprocess.run([sys.executable, str(P/'browser.py'), stage, *args], text=True, capture_output=True, timeout=50)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def snap(stage):
    return ab(stage, 'snapshot', '-i')


def ref(stage, role, pattern='.*'):
    observed = snap(stage)
    matches = []
    for line in observed.splitlines():
        if re.match(r'\s*- ' + role + r'(?:\s|$)', line):
            name = re.search(r'"([^"]*)"', line)
            if re.search(pattern, name.group(1) if name else ''):
                match = re.search(r'ref=(e\d+)', line)
                if match:
                    matches.append('@' + match.group(1))
    assert len(matches) == 1, (role, pattern, matches, observed)
    return matches[0]


def control(**fields):
    req = urllib.request.Request('http://127.0.0.1:57612/__qa/control', data=json.dumps(fields).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        assert response.status == 200
        return json.load(response)


def read(stage, expression):
    return json.loads(ab(stage, 'eval', expression))
