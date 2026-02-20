#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

MANIFEST_PATH="project/video/manifest.json"
SCRIPT_OUT="project/video/script.md"
SCENARIO_DIR="project/video/scenarios"
SCENARIO_OUT="project/video/scenarios"
SCENARIO_VERSION="normal"
SCENARIO_FILE=""
MANIFEST_FROM_SCENARIO="auto"
BASE_URL="${PSK_RECORD_BASE_URL:-http://127.0.0.1:3500}"
LANGUAGE="ko+en"
DURATION_SEC="auto"
MAX_SCENES="3"
REUSE_EXISTING="true"
REUSE_EXISTING_SET="false"
CACHE_MODE="auto"
HEADLESS="false"
TTS_ENGINE="${TTS_ENGINE_DEFAULT:-supertonic-local}"
QWEN_LOCAL_TIMEOUT_SEC="${QWEN_LOCAL_TIMEOUT_SEC:-}"
THUMBNAIL_MODE="manual"
TITLE="오늘 장마감 핵심 시그널"
SUBTITLE="AI가 뽑은 KR 시장 인사이트"
STRICT_TTS="true"
STRICT_REMOTION="true"
BURN_IN_CAPTIONS="${PSK_BURN_IN_CAPTIONS:-true}"
SHOWCASE_SCENARIO="true"
AUTO_START_SERVICES="true"
SKIP_HEALTH="false"
GATE_A="approved"
GATE_B="approved"
GATE_C="approved"
GATE_D="approved"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST_PATH="$2"; shift 2 ;;
    --script-out)
      SCRIPT_OUT="$2"; shift 2 ;;
    --scenario-dir)
      SCENARIO_DIR="$2"; shift 2 ;;
    --scenario-out)
      SCENARIO_OUT="$2"; shift 2 ;;
    --scenario-version)
      SCENARIO_VERSION="$2"; shift 2 ;;
    --scenario-file)
      SCENARIO_FILE="$2"; shift 2 ;;
    --manifest-from-scenario)
      MANIFEST_FROM_SCENARIO="$2"; shift 2 ;;
    --base-url)
      BASE_URL="$2"; shift 2 ;;
    --language)
      LANGUAGE="$2"; shift 2 ;;
    --duration-sec)
      DURATION_SEC="$2"; shift 2 ;;
    --max-scenes)
      MAX_SCENES="$2"; shift 2 ;;
    --reuse-existing)
      REUSE_EXISTING="$2"; REUSE_EXISTING_SET="true"; shift 2 ;;
    --cache-mode)
      CACHE_MODE="$2"; shift 2 ;;
    --headless)
      HEADLESS="$2"; shift 2 ;;
    --tts-engine)
      TTS_ENGINE="$2"; shift 2 ;;
    --qwen-local-timeout-sec)
      QWEN_LOCAL_TIMEOUT_SEC="$2"; shift 2 ;;
    --thumbnail-mode)
      THUMBNAIL_MODE="$2"; shift 2 ;;
    --title)
      TITLE="$2"; shift 2 ;;
    --subtitle)
      SUBTITLE="$2"; shift 2 ;;
    --strict-tts)
      STRICT_TTS="$2"; shift 2 ;;
    --strict-remotion)
      STRICT_REMOTION="$2"; shift 2 ;;
    --burn-in-captions)
      BURN_IN_CAPTIONS="$2"; shift 2 ;;
    --showcase-scenario)
      SHOWCASE_SCENARIO="$2"; shift 2 ;;
    --auto-start-services)
      AUTO_START_SERVICES="$2"; shift 2 ;;
    --skip-health)
      SKIP_HEALTH="true"; shift 1 ;;
    --gate-a)
      GATE_A="$2"; shift 2 ;;
    --gate-b)
      GATE_B="$2"; shift 2 ;;
    --gate-c)
      GATE_C="$2"; shift 2 ;;
    --gate-d)
      GATE_D="$2"; shift 2 ;;
    --yes|--auto-approve)
      shift 1 ;;
    # Compatibility no-op options.
    --profile|--sync-policy|--sync-policies-config|--auto-speed-from-script|--tts-speed-factor|--caption-speed-factor|--fit-to-target|--engine-healthcheck|--engine-health-timeout-sec|--engine-timeout-sec|--engine-request-timeout-sec|--sync-tolerance-sec|--max-sentence-delta-sec|--max-scene-end-delta-sec|--max-scene-duration-delta-sec|--max-av-sync-delta-sec|--max-caption-end-delta-sec|--voice-meta|--captions-json|--captions-meta)
      shift 2 ;;
    *)
      echo "[pipeline] unknown option: $1" >&2
      exit 1 ;;
  esac
done

case "${CACHE_MODE}" in
  auto|refresh)
    ;;
  *)
    echo "[pipeline] unknown cache-mode: ${CACHE_MODE} (expected: auto|refresh)" >&2
    exit 1
    ;;
esac

case "${MANIFEST_FROM_SCENARIO}" in
  auto|true|false)
    ;;
  *)
    echo "[pipeline] unknown manifest-from-scenario: ${MANIFEST_FROM_SCENARIO} (expected: auto|true|false)" >&2
    exit 1
    ;;
esac

if [[ "${CACHE_MODE}" == "refresh" ]]; then
  REUSE_EXISTING="false"
elif [[ "${REUSE_EXISTING_SET}" != "true" ]]; then
  REUSE_EXISTING="true"
fi

cd "${ROOT_DIR}"
log_info "pipeline start (restored-full-stage)"
log_info "pipeline config tts-engine=${TTS_ENGINE} cache-mode=${CACHE_MODE} reuse-existing=${REUSE_EXISTING} showcase-scenario=${SHOWCASE_SCENARIO} scenario-version=${SCENARIO_VERSION} manifest-from-scenario=${MANIFEST_FROM_SCENARIO}"

# Always delegate manifest handling to stage-level cache validation.
"${SCRIPT_DIR}/run_stage.sh" manifest \
  --manifest "${MANIFEST_PATH}" \
  --script-out "${SCRIPT_OUT}" \
  --language "${LANGUAGE}" \
  --duration-sec "${DURATION_SEC}" \
  --max-scenes "${MAX_SCENES}" \
  --reuse-existing "${REUSE_EXISTING}"

if [[ "${SHOWCASE_SCENARIO}" == "true" ]]; then
  "${SCRIPT_DIR}/run_stage.sh" showcase-scenario \
    --manifest "${MANIFEST_PATH}" \
    --language "${LANGUAGE}" \
    --scenario-dir "${SCENARIO_DIR}" \
    --scenario-out "${SCENARIO_OUT}" \
    --scenario-version "${SCENARIO_VERSION}" \
    --reuse-existing "${REUSE_EXISTING}"
fi

APPLY_SHOWCASE_MANIFEST="false"
if [[ "${MANIFEST_FROM_SCENARIO}" == "true" ]]; then
  APPLY_SHOWCASE_MANIFEST="true"
elif [[ "${MANIFEST_FROM_SCENARIO}" == "auto" ]]; then
  MANIFEST_IS_DEFAULT="$("${PYTHON}" - <<'PY' "${MANIFEST_PATH}" "${ROOT_DIR}/project/video/manifest.json"
from pathlib import Path
import sys
try:
    provided = Path(sys.argv[1]).resolve()
    default = Path(sys.argv[2]).resolve()
except Exception:
    print("false")
    raise SystemExit(0)
print("true" if provided == default else "false")
PY
)"
  if [[ "${SHOWCASE_SCENARIO}" == "true" && "${MANIFEST_IS_DEFAULT}" == "true" ]]; then
    APPLY_SHOWCASE_MANIFEST="true"
  fi
fi

if [[ "${APPLY_SHOWCASE_MANIFEST}" == "true" ]]; then
  SHOWCASE_APPLY_ARGS=(
    --manifest "${MANIFEST_PATH}"
    --script-out "${SCRIPT_OUT}"
    --language "${LANGUAGE}"
    --scenario-dir "${SCENARIO_DIR}"
    --scenario-out "${SCENARIO_OUT}"
    --scenario-version "${SCENARIO_VERSION}"
    --base-url "${BASE_URL}"
    --reuse-existing "${REUSE_EXISTING}"
  )
  if [[ -n "${SCENARIO_FILE}" ]]; then
    SHOWCASE_APPLY_ARGS+=(--scenario-file "${SCENARIO_FILE}")
  fi
  "${SCRIPT_DIR}/run_stage.sh" manifest-from-scenario "${SHOWCASE_APPLY_ARGS[@]}"
fi

PREFLIGHT_ARGS=(
  --manifest "${MANIFEST_PATH}"
  --strict-tts "${STRICT_TTS}"
  --tts-engine "${TTS_ENGINE}"
  --auto-start-services "${AUTO_START_SERVICES}"
)
if [[ "${SKIP_HEALTH}" == "true" ]]; then
  PREFLIGHT_ARGS+=(--skip-health)
fi
"${SCRIPT_DIR}/run_stage.sh" preflight "${PREFLIGHT_ARGS[@]}"

"${SCRIPT_DIR}/run_stage.sh" sync-policy
"${SCRIPT_DIR}/run_stage.sh" scene-runner --manifest "${MANIFEST_PATH}"
"${SCRIPT_DIR}/run_stage.sh" record --manifest "${MANIFEST_PATH}" --headless "${HEADLESS}" --reuse-existing "${REUSE_EXISTING}"
VOICE_ARGS=(
  "${SCRIPT_DIR}/run_stage.sh"
  voice
  --manifest "${MANIFEST_PATH}"
  --language "${LANGUAGE}"
  --tts-engine "${TTS_ENGINE}"
  --strict-tts "${STRICT_TTS}"
)
if [[ -n "${QWEN_LOCAL_TIMEOUT_SEC}" ]]; then
  VOICE_ARGS+=(--qwen-local-timeout-sec "${QWEN_LOCAL_TIMEOUT_SEC}")
fi
"${VOICE_ARGS[@]}"
"${SCRIPT_DIR}/run_stage.sh" captions --manifest "${MANIFEST_PATH}" --language "${LANGUAGE}"
"${SCRIPT_DIR}/run_stage.sh" render --manifest "${MANIFEST_PATH}" --language "${LANGUAGE}" --strict-remotion "${STRICT_REMOTION}" --burn-in-captions "${BURN_IN_CAPTIONS}"
"${SCRIPT_DIR}/run_stage.sh" assets --manifest "${MANIFEST_PATH}" --language "${LANGUAGE}" --thumbnail-mode "${THUMBNAIL_MODE}" --title "${TITLE}" --subtitle "${SUBTITLE}"
"${SCRIPT_DIR}/run_stage.sh" validate --manifest "${MANIFEST_PATH}"
"${SCRIPT_DIR}/run_stage.sh" manager-report --manifest "${MANIFEST_PATH}"
"${SCRIPT_DIR}/run_stage.sh" quality-report --manifest "${MANIFEST_PATH}"
"${SCRIPT_DIR}/run_stage.sh" qc --manifest "${MANIFEST_PATH}" --gate-a "${GATE_A}" --gate-b "${GATE_B}" --gate-c "${GATE_C}" --gate-d "${GATE_D}"

log_info "pipeline success (full-stage chain)"
