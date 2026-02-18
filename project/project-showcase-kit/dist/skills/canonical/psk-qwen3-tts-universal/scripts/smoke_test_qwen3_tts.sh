#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SKILL_DIR}/../../../.." && pwd)"

PROJECT_ROOT="${PROJECT_ROOT_DEFAULT}"
VENV_PATH=""
RUNNER_PATH=""
MODE="all"
MODEL_SIZE="${QWEN3_TTS_MODEL_SIZE:-0.6b}"
LANGUAGE="${QWEN3_TTS_LANGUAGE:-Auto}"
SPEAKER="${QWEN3_TTS_SPEAKER:-Vivian}"
STYLE_INSTRUCT="${QWEN3_TTS_STYLE_INSTRUCT:-차분하고 명확한 설명 톤으로 말해줘.}"
REF_AUDIO=""
REF_TEXT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-root)
      PROJECT_ROOT="$2"; shift 2 ;;
    --venv-path)
      VENV_PATH="$2"; shift 2 ;;
    --runner-path)
      RUNNER_PATH="$2"; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --model-size)
      MODEL_SIZE="$2"; shift 2 ;;
    --language)
      LANGUAGE="$2"; shift 2 ;;
    --speaker)
      SPEAKER="$2"; shift 2 ;;
    --style-instruct)
      STYLE_INSTRUCT="$2"; shift 2 ;;
    --ref-audio)
      REF_AUDIO="$2"; shift 2 ;;
    --ref-text)
      REF_TEXT="$2"; shift 2 ;;
    *)
      echo "[qwen3-smoke] unknown option: $1" >&2
      exit 1 ;;
  esac
done

PROJECT_ROOT="$(cd "${PROJECT_ROOT}" && pwd)"
[[ -n "${VENV_PATH}" ]] || VENV_PATH="${PROJECT_ROOT}/.venv-qwen3-tts"
[[ -n "${RUNNER_PATH}" ]] || RUNNER_PATH="${PROJECT_ROOT}/.agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py"
PYTHON_BIN="${VENV_PATH}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[qwen3-smoke] python not found in venv: ${PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${RUNNER_PATH}" ]]; then
  echo "[qwen3-smoke] runner not found: ${RUNNER_PATH}" >&2
  exit 1
fi

OUT_DIR="${PROJECT_ROOT}/out/qwen3_tts_smoke"
mkdir -p "${OUT_DIR}"

CUSTOM_TEXT="${OUT_DIR}/custom_input.txt"
DESIGN_TEXT="${OUT_DIR}/design_input.txt"
CLONE_TEXT="${OUT_DIR}/clone_input.txt"

cat > "${CUSTOM_TEXT}" <<'TXT'
안녕하세요. 이 파일은 psk-qwen3-tts-universal 스킬의 custom voice 스모크 테스트용 입력입니다.
This sentence validates multilingual synthesis in one run.
TXT

cat > "${DESIGN_TEXT}" <<'TXT'
지금부터 품질 연구 결과를 차분하고 명료한 톤으로 전달하겠습니다.
TXT

cat > "${CLONE_TEXT}" <<'TXT'
이 문장은 레퍼런스 음성을 기반으로 클로닝이 동작하는지 확인하기 위한 테스트입니다.
TXT

run_and_check() {
  local label="$1"
  local wav="$2"
  shift 2

  echo "[qwen3-smoke] running: ${label}"
  "${PYTHON_BIN}" "${RUNNER_PATH}" "$@"

  if [[ ! -f "${wav}" ]]; then
    echo "[qwen3-smoke] missing output wav: ${wav}" >&2
    exit 1
  fi

  if command -v ffprobe >/dev/null 2>&1; then
    local duration
    duration="$(ffprobe -v error -show_entries format=duration -of default=nk=1:nw=1 "${wav}")"
    echo "[qwen3-smoke] ${label} duration=${duration}s"
  fi
}

if [[ "${MODE}" == "custom_voice" || "${MODE}" == "all" ]]; then
  run_and_check \
    "custom_voice" \
    "${OUT_DIR}/custom.wav" \
    --mode custom_voice \
    --input "${CUSTOM_TEXT}" \
    --output "${OUT_DIR}/custom.wav" \
    --model-size "${MODEL_SIZE}" \
    --language "${LANGUAGE}" \
    --speaker "${SPEAKER}"
fi

if [[ "${MODE}" == "voice_design" || "${MODE}" == "all" ]]; then
  run_and_check \
    "voice_design" \
    "${OUT_DIR}/design.wav" \
    --mode voice_design \
    --input "${DESIGN_TEXT}" \
    --output "${OUT_DIR}/design.wav" \
    --language "${LANGUAGE}" \
    --instruct "${STYLE_INSTRUCT}" \
    --model-size 1.7b
fi

if [[ "${MODE}" == "voice_clone" || "${MODE}" == "all" ]]; then
  if [[ -z "${REF_AUDIO}" ]]; then
    REF_AUDIO="${OUT_DIR}/custom.wav"
    if [[ ! -f "${REF_AUDIO}" ]]; then
      run_and_check \
        "custom_voice_ref" \
        "${OUT_DIR}/custom.wav" \
        --mode custom_voice \
        --input "${CUSTOM_TEXT}" \
        --output "${OUT_DIR}/custom.wav" \
        --model-size "${MODEL_SIZE}" \
        --language "${LANGUAGE}" \
        --speaker "${SPEAKER}"
    fi
  fi

  if [[ -z "${REF_TEXT}" ]]; then
    REF_TEXT="$(cat "${CUSTOM_TEXT}")"
  fi

  run_and_check \
    "voice_clone" \
    "${OUT_DIR}/clone.wav" \
    --mode voice_clone \
    --input "${CLONE_TEXT}" \
    --output "${OUT_DIR}/clone.wav" \
    --model-size "${MODEL_SIZE}" \
    --language "${LANGUAGE}" \
    --ref-audio "${REF_AUDIO}" \
    --ref-text "${REF_TEXT}"
fi

if [[ "${MODE}" == "list" || "${MODE}" == "all" ]]; then
  echo "[qwen3-smoke] running: list_capabilities"
  "${PYTHON_BIN}" "${RUNNER_PATH}" --mode list_capabilities --model-size "${MODEL_SIZE}" --meta-out "${OUT_DIR}/capabilities.json"
fi

echo "[qwen3-smoke] success"
echo "[qwen3-smoke] outputs: ${OUT_DIR}"
