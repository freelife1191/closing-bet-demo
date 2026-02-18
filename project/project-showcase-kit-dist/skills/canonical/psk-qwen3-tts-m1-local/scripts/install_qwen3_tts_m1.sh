#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

echo "[qwen3-m1-legacy] redirecting to psk-qwen3-tts-universal installer"
exec "${PROJECT_ROOT}/.agent/skills/psk-qwen3-tts-universal/scripts/install_qwen3_tts.sh" "$@"
