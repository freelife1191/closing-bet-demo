#!/usr/bin/env bash
set -euo pipefail

python3 .agent/skills/psk-project-init-audit/scripts/run_init_audit.py --project-root .
test -f project/video/evidence/project_audit.json
