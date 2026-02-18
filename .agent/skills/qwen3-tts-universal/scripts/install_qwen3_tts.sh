#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SKILL_DIR}/../../../.." && pwd)"

PROJECT_ROOT="${PROJECT_ROOT_DEFAULT}"
VENV_PATH=""
PYTHON_BIN=""
FROM_SOURCE="auto"
WRITE_DOTENV="true"
WRITE_CONFIG="true"
CONFIG_PATH=""
INSTALL_SYSTEM_TOOLS="auto"
DEFAULT_MODE="custom_voice"
MODEL_SIZE="0.6b"
LANGUAGE="Auto"
SPEAKER="Vivian"
STYLE_INSTRUCT=""
DEVICE="auto"
DTYPE="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"; shift 2 ;;
    --venv-path)
      VENV_PATH="$2"; shift 2 ;;
    --python-bin)
      PYTHON_BIN="$2"; shift 2 ;;
    --from-source)
      FROM_SOURCE="$2"; shift 2 ;;
    --write-dotenv)
      WRITE_DOTENV="$2"; shift 2 ;;
    --write-config)
      WRITE_CONFIG="$2"; shift 2 ;;
    --config-path)
      CONFIG_PATH="$2"; shift 2 ;;
    --install-system-tools)
      INSTALL_SYSTEM_TOOLS="$2"; shift 2 ;;
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
    *)
      echo "[qwen3-install] unknown option: $1" >&2
      exit 1 ;;
  esac
done

PROJECT_ROOT="$(cd "${PROJECT_ROOT}" && pwd)"
if [[ -z "${VENV_PATH}" ]]; then
  VENV_PATH="${PROJECT_ROOT}/.venv-qwen3-tts"
fi
if [[ -z "${CONFIG_PATH}" ]]; then
  CONFIG_PATH="${PROJECT_ROOT}/project/video/config/qwen3_tts.yaml"
fi

pick_python() {
  if [[ -n "${PYTHON_BIN}" ]]; then
    echo "${PYTHON_BIN}"
    return 0
  fi
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return 0
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return 0
  fi
  if command -v python3.10 >/dev/null 2>&1; then
    echo "python3.10"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  return 1
}

PYTHON_CMD="$(pick_python)" || {
  echo "[qwen3-install] no Python 3.10+ executable found" >&2
  exit 1
}

"${PYTHON_CMD}" - <<'PY'
import sys
major, minor = sys.version_info[:2]
if major != 3 or minor < 10:
    raise SystemExit("Python 3.10+ is required for qwen-tts")
print(f"[qwen3-install] python version ok: {major}.{minor}")
PY

OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')"

install_tools_if_needed() {
  local should_install="$1"
  if [[ "${should_install}" == "false" ]]; then
    return 0
  fi

  local need_sox="false"
  local need_ffmpeg="false"
  if ! command -v sox >/dev/null 2>&1; then
    need_sox="true"
  fi
  if ! command -v ffmpeg >/dev/null 2>&1; then
    need_ffmpeg="true"
  fi

  if [[ "${need_sox}" == "false" && "${need_ffmpeg}" == "false" ]]; then
    return 0
  fi

  if [[ "${OS_NAME}" == "darwin" ]] && command -v brew >/dev/null 2>&1; then
    [[ "${need_sox}" == "true" ]] && brew install sox
    [[ "${need_ffmpeg}" == "true" ]] && brew install ffmpeg
    return 0
  fi

  if [[ "${OS_NAME}" == "linux" ]] && command -v apt-get >/dev/null 2>&1; then
    if [[ "$(id -u)" -eq 0 ]]; then
      apt-get update
      local pkgs=()
      [[ "${need_sox}" == "true" ]] && pkgs+=(sox)
      [[ "${need_ffmpeg}" == "true" ]] && pkgs+=(ffmpeg)
      if [[ ${#pkgs[@]} -gt 0 ]]; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
      fi
    else
      echo "[qwen3-install] warning: missing sox/ffmpeg and no root privileges for apt-get" >&2
    fi
    return 0
  fi

  echo "[qwen3-install] warning: could not auto-install system tools (sox/ffmpeg) on ${OS_NAME}" >&2
}

if [[ "${INSTALL_SYSTEM_TOOLS}" == "true" ]]; then
  install_tools_if_needed "true"
elif [[ "${INSTALL_SYSTEM_TOOLS}" == "auto" ]]; then
  install_tools_if_needed "true"
fi

if [[ ! -d "${VENV_PATH}" ]]; then
  "${PYTHON_CMD}" -m venv "${VENV_PATH}"
fi

VENV_PY="${VENV_PATH}/bin/python"
VENV_PIP="${VENV_PATH}/bin/pip"
RUNNER_PATH="${PROJECT_ROOT}/.agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py"

"${VENV_PIP}" install --upgrade pip setuptools wheel

if [[ "${FROM_SOURCE}" == "auto" ]]; then
  if [[ -d "${PROJECT_ROOT}/third_party/Qwen3-TTS" ]]; then
    FROM_SOURCE="true"
  else
    FROM_SOURCE="false"
  fi
fi

if [[ "${FROM_SOURCE}" == "true" ]]; then
  if [[ ! -d "${PROJECT_ROOT}/third_party/Qwen3-TTS" ]]; then
    mkdir -p "${PROJECT_ROOT}/third_party"
    git clone --depth 1 https://github.com/QwenLM/Qwen3-TTS.git "${PROJECT_ROOT}/third_party/Qwen3-TTS"
  fi
  "${VENV_PIP}" install -e "${PROJECT_ROOT}/third_party/Qwen3-TTS"
else
  "${VENV_PIP}" install --upgrade qwen-tts
fi

"${VENV_PIP}" install --upgrade "huggingface_hub>=0.34,<1.0" "soundfile>=0.12" "numpy>=1.26,<2.4" "pyyaml>=6.0"

normalize_mode() {
  local value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    custom|custom_voice|tts) echo "custom_voice" ;;
    design|voice_design|tts_design) echo "voice_design" ;;
    clone|voice_clone|tts_clone) echo "voice_clone" ;;
    *) echo "custom_voice" ;;
  esac
}

normalize_size() {
  local value="$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr -d ' ')"
  value="${value/gb/b}"
  case "${value}" in
    0.6|06|0-6b|0_6b|0.6b) echo "0.6b" ;;
    1.7|17|1-7b|1_7b|1.7b) echo "1.7b" ;;
    *) echo "0.6b" ;;
  esac
}

pick_default_model() {
  local mode="$1"
  local size="$2"
  case "${mode}" in
    custom_voice)
      [[ "${size}" == "1.7b" ]] && echo "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice" || echo "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
      ;;
    voice_clone)
      [[ "${size}" == "1.7b" ]] && echo "Qwen/Qwen3-TTS-12Hz-1.7B-Base" || echo "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
      ;;
    voice_design)
      echo "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
      ;;
    *)
      echo "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
      ;;
  esac
}

DEFAULT_MODE="$(normalize_mode "${DEFAULT_MODE}")"
MODEL_SIZE="$(normalize_size "${MODEL_SIZE}")"
if [[ "${DEFAULT_MODE}" == "voice_design" ]]; then
  MODEL_SIZE="1.7b"
fi

DEFAULT_MODEL="$(pick_default_model "${DEFAULT_MODE}" "${MODEL_SIZE}")"

STYLE_ESCAPED="${STYLE_INSTRUCT//\"/\\\"}"
STYLE_ARG=""
if [[ -n "${STYLE_ESCAPED}" ]]; then
  STYLE_ARG=" --instruct \\\"${STYLE_ESCAPED}\\\""
fi
QWEN_LOCAL_CMD_VALUE="\"${VENV_PY} ${RUNNER_PATH} --mode custom_voice --input {text_file} --output {output_file} --model-size ${MODEL_SIZE} --language ${LANGUAGE} --speaker ${SPEAKER} --device ${DEVICE} --dtype ${DTYPE}${STYLE_ARG}\""

upsert_env() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  "${PYTHON_CMD}" - "$env_file" "$key" "$value" <<'PY'
import os
import sys

env_path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
lines = []
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

updated = False
out = []
prefix = f"{key}="
for line in lines:
    if line.startswith(prefix):
        out.append(f"{key}={value}")
        updated = True
    else:
        out.append(line)

if not updated:
    out.append(f"{key}={value}")

with open(env_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
PY
}

if [[ "${WRITE_DOTENV}" == "true" ]]; then
  ENV_FILE="${PROJECT_ROOT}/.env"
  [[ -f "${ENV_FILE}" ]] || touch "${ENV_FILE}"

  upsert_env "${ENV_FILE}" "QWEN3_TTS_VENV" "\"${VENV_PATH}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_DEFAULT_MODE" "\"${DEFAULT_MODE}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_MODEL_SIZE" "\"${MODEL_SIZE}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_MODEL" "\"${DEFAULT_MODEL}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_LANGUAGE" "\"${LANGUAGE}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_SPEAKER" "\"${SPEAKER}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_STYLE_INSTRUCT" "\"${STYLE_INSTRUCT}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_DEVICE" "\"${DEVICE}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_DTYPE" "\"${DTYPE}\""
  upsert_env "${ENV_FILE}" "QWEN3_TTS_CONFIG" "\"${CONFIG_PATH}\""
  upsert_env "${ENV_FILE}" "QWEN_LOCAL_CMD" "${QWEN_LOCAL_CMD_VALUE}"
fi

if [[ "${WRITE_CONFIG}" == "true" ]]; then
  "${PROJECT_ROOT}/.agent/skills/qwen3-tts-universal/scripts/init_qwen3_tts_config.sh" \
    --project-root "${PROJECT_ROOT}" \
    --config-path "${CONFIG_PATH}" \
    --model-size "${MODEL_SIZE}" \
    --default-mode "${DEFAULT_MODE}" \
    --language "${LANGUAGE}" \
    --speaker "${SPEAKER}" \
    --style-instruct "${STYLE_INSTRUCT}" \
    --device "${DEVICE}" \
    --dtype "${DTYPE}" \
    --venv-path "${VENV_PATH}" \
    --overwrite false
fi

cat <<EOF
[qwen3-install] done
- project_root: ${PROJECT_ROOT}
- venv: ${VENV_PATH}
- runner: ${RUNNER_PATH}
- default_mode: ${DEFAULT_MODE}
- model_size: ${MODEL_SIZE}
- default_model: ${DEFAULT_MODEL}
- language: ${LANGUAGE}
- speaker: ${SPEAKER}
- device: ${DEVICE}
- dtype: ${DTYPE}
- write_dotenv: ${WRITE_DOTENV}
- write_config: ${WRITE_CONFIG}

Try:
  ${VENV_PY} ${RUNNER_PATH} --mode custom_voice --text "Qwen3-TTS setup complete." --output /tmp/qwen3_setup_test.wav
  ${VENV_PY} ${RUNNER_PATH} --mode list_capabilities
EOF
