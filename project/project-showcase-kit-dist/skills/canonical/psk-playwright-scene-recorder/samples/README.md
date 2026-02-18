# Samples

Use manifest-driven recording inputs.

- Required input example: `project/video/manifest.json`
- Recommended execution order:
  1. `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
  2. `./scripts/pipeline/run_stage.sh record --headless false`
  3. `./scripts/pipeline/rerun_failed.sh --headless false` (only when failures exist)
