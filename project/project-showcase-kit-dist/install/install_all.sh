#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TOOL="${1:-}"

case "${TOOL}" in
  codex|claudecode|gemini|antigravity)
    ;;
  *)
    echo "usage: install_all.sh <codex|claudecode|gemini|antigravity>"
    exit 1
    ;;
esac

INSTALLER="${ROOT_DIR}/project/project-showcase-kit-dist/install/${TOOL}/install.sh"
if [[ ! -f "${INSTALLER}" ]]; then
  python3 "${ROOT_DIR}/project/project-showcase-kit-src/scripts/build_dist.py" --repo-root "${ROOT_DIR}"
fi

bash "${INSTALLER}" "${ROOT_DIR}"
