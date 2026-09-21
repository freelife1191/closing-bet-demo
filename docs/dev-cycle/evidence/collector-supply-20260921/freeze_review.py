"""Freeze all changed product/test files, including untracked additions and deletions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[4]
evidence = Path(__file__).resolve().parent
paths = subprocess.check_output(["git", "diff", "--name-only", "63b1db0"], cwd=root, text=True).splitlines()
paths += subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True).splitlines()
paths = sorted({path for path in paths if path.startswith(("engine/", "services/", "tests/", "frontend/src/"))})
records = {path: hashlib.sha256((root/path).read_bytes()).hexdigest() if (root/path).exists() else None for path in paths}
for path in ["docs/superpowers/specs/2026-09-21-collector-supply-design.md", "docs/superpowers/plans/2026-09-21-collector-supply.md"]:
    records[path] = hashlib.sha256((root/path).read_bytes()).hexdigest()
if len(sys.argv) > 1:
    (evidence/f"review-frozen-{sys.argv[1]}.json").write_bytes((evidence/"review-frozen.json").read_bytes())
(evidence/"review-frozen.json").write_text(json.dumps(records, indent=2)+"\n")
diff = subprocess.check_output(["git", "diff", "63b1db0", "--", *paths], cwd=root, text=True)
for path in paths:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=root, capture_output=True)
    if tracked.returncode and (root/path).exists():
        diff += subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", path], cwd=root, capture_output=True, text=True).stdout
(evidence/"review-diff.txt").write_text(diff)
print(json.dumps({"paths": len(records), "sha256": hashlib.sha256((evidence/"review-frozen.json").read_bytes()).hexdigest()}))
