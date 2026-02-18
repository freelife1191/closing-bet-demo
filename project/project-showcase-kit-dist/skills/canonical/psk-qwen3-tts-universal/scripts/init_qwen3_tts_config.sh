#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SKILL_DIR}/../../../.." && pwd)"

PROJECT_ROOT="${PROJECT_ROOT_DEFAULT}"
CONFIG_PATH=""
VENV_PATH=""
DEFAULT_MODE="custom_voice"
MODEL_SIZE="0.6b"
LANGUAGE="Auto"
SPEAKER="Vivian"
STYLE_INSTRUCT=""
DEVICE="auto"
DTYPE="auto"
OUTPUT_DIR=""
REFERENCE_AUDIO=""
REFERENCE_TEXT=""
OVERWRITE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"; shift 2 ;;
    --config-path)
      CONFIG_PATH="$2"; shift 2 ;;
    --venv-path)
      VENV_PATH="$2"; shift 2 ;;
    --default-mode)
      DEFAULT_MODE="$2"; shift 2 ;;
    --model-size)
      MODEL_SIZE="$2"; shift 2 ;;
    --language)
      LANGUAGE="$2"; shift 2 ;;
    --speaker)
      SPEAKER="$2"; shift 2 ;;
    --style-instruct)
      STYLE_INSTRUCT="$2"; shift 2 ;;
    --device)
      DEVICE="$2"; shift 2 ;;
    --dtype)
      DTYPE="$2"; shift 2 ;;
    --output-dir)
      OUTPUT_DIR="$2"; shift 2 ;;
    --reference-audio)
      REFERENCE_AUDIO="$2"; shift 2 ;;
    --reference-text)
      REFERENCE_TEXT="$2"; shift 2 ;;
    --overwrite)
      OVERWRITE="$2"; shift 2 ;;
    *)
      echo "[qwen3-init] unknown option: $1" >&2
      exit 1 ;;
  esac
done

PROJECT_ROOT="$(cd "${PROJECT_ROOT}" && pwd)"
if [[ -z "${CONFIG_PATH}" ]]; then
  CONFIG_PATH="${PROJECT_ROOT}/project/video/config/qwen3_tts.yaml"
fi
if [[ -z "${VENV_PATH}" ]]; then
  VENV_PATH="${PROJECT_ROOT}/.venv-qwen3-tts"
fi
if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="${PROJECT_ROOT}/project/video/audio"
fi

CONFIG_PATH="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "${CONFIG_PATH}")"
OUTPUT_DIR="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "${OUTPUT_DIR}")"

if [[ -f "${CONFIG_PATH}" && "${OVERWRITE}" != "true" ]]; then
  echo "[qwen3-init] config exists (skip): ${CONFIG_PATH}"
  exit 0
fi

mkdir -p "$(dirname "${CONFIG_PATH}")"
mkdir -p "${OUTPUT_DIR}"

cat > "${CONFIG_PATH}" <<EOF
# psk-qwen3-tts-universal runtime config
runtime:
  project_root: "${PROJECT_ROOT}"
  venv_path: "${VENV_PATH}"
  runner: "${PROJECT_ROOT}/.agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py"

defaults:
  mode: "${DEFAULT_MODE}"
  model_size: "${MODEL_SIZE}"
  language: "${LANGUAGE}"
  speaker: "${SPEAKER}"
  style_instruct: "${STYLE_INSTRUCT}"
  device: "${DEVICE}"
  dtype: "${DTYPE}"

generation:
  max_new_tokens: 2048
  pause_sec: 0.65
  split_max_chars: 280

paths:
  output_dir: "${OUTPUT_DIR}"
  reference_audio: "${REFERENCE_AUDIO}"
  reference_text: "${REFERENCE_TEXT}"
EOF

echo "[qwen3-init] wrote config: ${CONFIG_PATH}"
