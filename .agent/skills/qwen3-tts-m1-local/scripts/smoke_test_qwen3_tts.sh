#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

echo "[qwen3-m1-legacy] redirecting to qwen3-tts-universal smoke test"
exec "${PROJECT_ROOT}/.agent/skills/qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh" "$@"
