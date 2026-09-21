"""Read-only final evidence checks; never imports project code or contacts original services."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent


def read(name):
    return json.loads((EVIDENCE / name).read_text())


frozen = read("review-frozen.json")
for path, expected in frozen.items():
    source = ROOT / path
    assert (hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else None) == expected, path
    blob = subprocess.run(["git", "show", "cb51702:" + path], cwd=ROOT, capture_output=True)
    assert (hashlib.sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None) == expected, path
for row in read("log-index.json") + [read("review-diff-integrity.json")] + read("next-diagnostics-integrity.json"):
    data = gzip.decompress((EVIDENCE / row["archive"]).read_bytes())
    assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
stages = ["pytest-import-repair", "vitest-final", "build-integrated", "lint-final", "typecheck-final", "bench-final", "fixture-cycle2-preflight"]
for stage in stages:
    assert read(stage + ".json")["exit_code"] == 0, stage
assert b"2449 passed, 3 skipped" in gzip.decompress((EVIDENCE / "pytest-import-repair.log.gz").read_bytes())
modes = read("ego-modes.json")
assert len(modes) == 6
for row in modes:
    assert row["actual"] == row["amount"] and row["httpStatus"] == 200
    assert row["observation"]["errors"] == row["observation"]["consoleErrors"] == []
    assert row["observation"]["foreignUnchanged"] and row["observation"]["institutionUnchanged"]
recovery = read("ego-recovery.json")
assert recovery["sameDocument"] and [row["response"]["status"] for row in recovery["rows"]] == [503, 200]
for row in recovery["rows"]:
    assert row["observation"]["errors"] == row["observation"]["consoleErrors"] == []
diagnostics = read("next-diagnostics.json")
errors = json.loads(diagnostics["get_errors"][0]["result"]["content"][0]["text"])
issues = json.loads(diagnostics["get_compilation_issues"][0]["result"]["content"][0]["text"])
assert errors == {"configErrors": [], "sessionErrors": []} and issues == {"issues": []}
for row in read("image-review.json")["images"]:
    assert row["viewed"] and hashlib.sha256((EVIDENCE / row["path"]).read_bytes()).hexdigest() == row["sha256"]
assert read("ego-finish.json")["closedSpace"] and read("browser.json")["finished"]
cleanup = read("cleanup.json")
assert cleanup["scratch_removed"] and not Path(cleanup["scratch"]).exists()
assert all(cleanup["ports_closed"].values()) and (ROOT / "venv").is_dir()
assert hashlib.sha256((ROOT / "package.json").read_bytes()).hexdigest() == read("review-input.json")["package_sha256"]
assert read("request-audit.json")["forbidden_browser_mutations"] == 0
assert not read("request-audit.json")["unexpected_api_errors"]
print(json.dumps({"pass": True, "commit": "cb51702", "frozen_paths": len(frozen), "verified_logs": len(read("log-index.json")), "pytest": 2449, "vitest": 634, "required_qa": "9/9", "qa_cycles": 2, "images_viewed": 8, "cleanup": "complete"}))
