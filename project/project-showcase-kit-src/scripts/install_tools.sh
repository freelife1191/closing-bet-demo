#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
python3 "${REPO_ROOT}/project/project-showcase-kit-src/scripts/build_dist.py" --repo-root "${REPO_ROOT}"
