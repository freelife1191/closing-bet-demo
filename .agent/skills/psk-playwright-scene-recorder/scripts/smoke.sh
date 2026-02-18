#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/skills/validate_skill_structure.py --skills psk-playwright-scene-recorder --strict
echo "[skill-smoke] psk-playwright-scene-recorder structure verified"
