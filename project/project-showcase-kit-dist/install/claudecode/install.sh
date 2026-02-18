#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$(pwd)}"
TARGET_DIR="${ROOT_DIR}/.agent/skills"
SOURCE_DIR="${ROOT_DIR}/project/project-showcase-kit-dist/skills/canonical"

mkdir -p "${TARGET_DIR}"
cp -R "${SOURCE_DIR}"/psk-* "${TARGET_DIR}/"
echo "[project-showcase-kit] claudecode install complete -> ${TARGET_DIR}"
