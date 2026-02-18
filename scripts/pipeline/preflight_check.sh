#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

MANIFEST_PATH="project/video/manifest.json"
REQUIRE_HEALTH="true"
STRICT_TTS="true"
TTS_ENGINE="auto"
AUTO_START_SERVICES="true"
FRONTEND_PORT="${FRONTEND_PORT:-3500}"
BACKEND_PORT="${FLASK_PORT:-5501}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST_PATH="$2"; shift 2 ;;
    --skip-health)
      REQUIRE_HEALTH="false"; shift 1 ;;
    --strict-tts)
      STRICT_TTS="$2"; shift 2 ;;
    --tts-engine)
      TTS_ENGINE="$2"; shift 2 ;;
    --auto-start-services)
      AUTO_START_SERVICES="$2"; shift 2 ;;
    *)
      echo "[preflight] unknown option: $1" >&2
      exit 1 ;;
  esac
done

cd "${ROOT_DIR}"

log_info "preflight checks start"

require_cmd node
require_cmd npx
require_cmd ffmpeg
require_cmd ffprobe
require_cmd curl

if [[ ! -f frontend/package.json ]]; then
  echo "[preflight] missing frontend/package.json" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "[preflight] frontend/node_modules not found. run: cd frontend && npm install" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules/playwright ]]; then
  echo "[preflight] playwright dependency missing. run: cd frontend && npm install -D playwright @playwright/test" >&2
  exit 1
fi

if [[ ! -d frontend/node_modules/tsx ]]; then
  echo "[preflight] tsx dependency missing. run: cd frontend && npm install -D tsx" >&2
  exit 1
fi

"${PYTHON}" - <<'PY'
import sys
required = ("requests",)
missing = []
for module in required:
    try:
        __import__(module)
    except Exception:
        missing.append(module)
if missing:
    print("[preflight] missing python modules:", ", ".join(missing))
    sys.exit(1)
PY

if [[ "${REQUIRE_HEALTH}" == "true" ]]; then
  FRONTEND_OK="false"
  BACKEND_OK="false"

  if curl -fsS --max-time 3 "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null || curl -fsS --max-time 3 "http://localhost:${FRONTEND_PORT}" >/dev/null; then
    FRONTEND_OK="true"
  fi

  if curl -fsS --max-time 3 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null || curl -fsS --max-time 3 "http://localhost:${BACKEND_PORT}/health" >/dev/null; then
    BACKEND_OK="true"
  fi

  if [[ "${FRONTEND_OK}" != "true" || "${BACKEND_OK}" != "true" ]]; then
    if [[ "${AUTO_START_SERVICES}" == "true" ]]; then
      log_info "health check failed, attempting auto-start via ensure_services.sh"
      "${SCRIPT_DIR}/ensure_services.sh" --frontend-port "${FRONTEND_PORT}" --backend-port "${BACKEND_PORT}" --wait-seconds 60
      FRONTEND_OK="false"
      BACKEND_OK="false"
      if curl -fsS --max-time 3 "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null || curl -fsS --max-time 3 "http://localhost:${FRONTEND_PORT}" >/dev/null; then
        FRONTEND_OK="true"
      fi
      if curl -fsS --max-time 3 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null || curl -fsS --max-time 3 "http://localhost:${BACKEND_PORT}/health" >/dev/null; then
        BACKEND_OK="true"
      fi
    fi
  fi

  if [[ "${FRONTEND_OK}" != "true" ]]; then
    echo "[preflight] frontend health check failed: http://127.0.0.1:${FRONTEND_PORT}" >&2
    exit 1
  fi
  if [[ "${BACKEND_OK}" != "true" ]]; then
    echo "[preflight] backend health check failed: http://127.0.0.1:${BACKEND_PORT}/health" >&2
    exit 1
  fi
fi

if [[ -f "${MANIFEST_PATH}" ]]; then
  "${PYTHON}" - <<'PY' "${MANIFEST_PATH}"
import json
import sys
from pathlib import Path
manifest_path = Path(sys.argv[1])
try:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
except Exception:
    print(f"[preflight] manifest json parse failed: {manifest_path}")
    sys.exit(1)
scenes = data.get("scenes")
if not isinstance(scenes, list) or len(scenes) == 0:
    print(f"[preflight] manifest exists but scenes is empty: {manifest_path}")
    sys.exit(1)
PY
fi

if [[ -n "${SUPERTONIC_ROOT:-}" && ! -d "${SUPERTONIC_ROOT}" ]]; then
  echo "[preflight] SUPERTONIC_ROOT path not found: ${SUPERTONIC_ROOT}" >&2
  exit 1
fi

# Default Qwen3-TTS local command when venv/runner are present.
if [[ -z "${QWEN_LOCAL_CMD:-}" ]]; then
  DEFAULT_QWEN3_VENV_PY="${ROOT_DIR}/.venv-qwen3-tts/bin/python"
  DEFAULT_QWEN3_UNIVERSAL_RUNNER="${ROOT_DIR}/.agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py"
  DEFAULT_QWEN3_LEGACY_RUNNER="${ROOT_DIR}/.agent/skills/psk-qwen3-tts-m1-local/scripts/qwen3_tts_local_runner.py"
  DEFAULT_QWEN3_MODEL_SIZE="${QWEN3_TTS_MODEL_SIZE:-0.6b}"
  DEFAULT_QWEN3_LANGUAGE="${QWEN3_TTS_LANGUAGE:-Auto}"
  DEFAULT_QWEN3_SPEAKER="${QWEN3_TTS_SPEAKER:-Vivian}"
  DEFAULT_QWEN3_DEVICE="${QWEN3_TTS_DEVICE:-auto}"
  DEFAULT_QWEN3_DTYPE="${QWEN3_TTS_DTYPE:-auto}"
  DEFAULT_QWEN3_STYLE_INSTRUCT="${QWEN3_TTS_STYLE_INSTRUCT:-}"
  DEFAULT_QWEN3_MODEL="${QWEN3_TTS_MODEL:-Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice}"
  DEFAULT_QWEN3_STYLE_ARG=""
  if [[ -n "${DEFAULT_QWEN3_STYLE_INSTRUCT}" ]]; then
    DEFAULT_QWEN3_STYLE_ESCAPED="${DEFAULT_QWEN3_STYLE_INSTRUCT//\"/\\\"}"
    DEFAULT_QWEN3_STYLE_ARG=" --instruct \"${DEFAULT_QWEN3_STYLE_ESCAPED}\""
  fi

  if [[ -x "${DEFAULT_QWEN3_VENV_PY}" && -f "${DEFAULT_QWEN3_UNIVERSAL_RUNNER}" ]]; then
    QWEN_LOCAL_CMD="${DEFAULT_QWEN3_VENV_PY} ${DEFAULT_QWEN3_UNIVERSAL_RUNNER} --mode custom_voice --input {text_file} --output {output_file} --model-size ${DEFAULT_QWEN3_MODEL_SIZE} --language ${DEFAULT_QWEN3_LANGUAGE} --speaker ${DEFAULT_QWEN3_SPEAKER} --device ${DEFAULT_QWEN3_DEVICE} --dtype ${DEFAULT_QWEN3_DTYPE}${DEFAULT_QWEN3_STYLE_ARG}"
    export QWEN_LOCAL_CMD
    log_info "preflight auto-wired QWEN_LOCAL_CMD to qwen3-tts universal runner"
  elif [[ -x "${DEFAULT_QWEN3_VENV_PY}" && -f "${DEFAULT_QWEN3_LEGACY_RUNNER}" ]]; then
    QWEN_LOCAL_CMD="${DEFAULT_QWEN3_VENV_PY} ${DEFAULT_QWEN3_LEGACY_RUNNER} --input {text_file} --output {output_file} --model ${DEFAULT_QWEN3_MODEL} --language Auto --speaker Vivian --device auto"
    export QWEN_LOCAL_CMD
    log_info "preflight auto-wired QWEN_LOCAL_CMD to qwen3-tts legacy runner"
  fi
fi

QWEN_READY="false"
if [[ -n "${QWEN_LOCAL_CMD:-}" || -n "${DASHSCOPE_API_KEY:-}" ]]; then
  QWEN_READY="true"
fi

SUPERTONIC_READY="false"
if [[ -n "${SUPERTONIC_ROOT:-}" && -d "${SUPERTONIC_ROOT}" ]]; then
  SUPERTONIC_READY="true"
fi

GOOGLE_READY="false"
if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
  GOOGLE_READY="true"
fi

case "${TTS_ENGINE}" in
  auto)
    if [[ "${QWEN_READY}" != "true" ]]; then
      echo "[preflight] auto requires Qwen path. set QWEN_LOCAL_CMD or DASHSCOPE_API_KEY" >&2
      exit 1
    fi
    if [[ "${STRICT_TTS}" == "true" && "${SUPERTONIC_READY}" != "true" && "${GOOGLE_READY}" != "true" ]]; then
      echo "[preflight] auto fallback not configured. set SUPERTONIC_ROOT or GOOGLE_API_KEY" >&2
      exit 1
    fi
    ;;
  auto-local)
    if [[ -z "${QWEN_LOCAL_CMD:-}" ]]; then
      echo "[preflight] auto-local requires QWEN_LOCAL_CMD" >&2
      exit 1
    fi
    if [[ "${SUPERTONIC_READY}" != "true" ]]; then
      echo "[preflight] auto-local requires SUPERTONIC_ROOT" >&2
      exit 1
    fi
    ;;
  qwen-local-cmd)
    if [[ -z "${QWEN_LOCAL_CMD:-}" ]]; then
      echo "[preflight] qwen-local-cmd requires QWEN_LOCAL_CMD" >&2
      exit 1
    fi
    ;;
  qwen)
    if [[ -z "${DASHSCOPE_API_KEY:-}" ]]; then
      echo "[preflight] qwen requires DASHSCOPE_API_KEY" >&2
      exit 1
    fi
    ;;
  supertonic-local)
    if [[ "${SUPERTONIC_READY}" != "true" ]]; then
      echo "[preflight] supertonic-local requires SUPERTONIC_ROOT" >&2
      exit 1
    fi
    ;;
  google)
    if [[ "${GOOGLE_READY}" != "true" ]]; then
      echo "[preflight] google requires GOOGLE_API_KEY" >&2
      exit 1
    fi
    ;;
  *)
    echo "[preflight] unsupported tts engine: ${TTS_ENGINE}" >&2
    exit 1
    ;;
esac

log_info "preflight checks passed"
