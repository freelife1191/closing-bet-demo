---
name: playwright-scene-recorder
description: Use when you need to execute manifest-driven browser automation with Playwright, record scene clips, retry failed scenes, and collect trace/screenshot evidence
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# playwright-scene-recorder

## Mission
Execute manifest-driven Playwright scene recording with deterministic clip outputs and failure evidence.

## Use this skill when
- You need browser scene capture from `project/video/manifest.json`.
- You need retry handling with trace and screenshot evidence for failed scenes.

## Do not use this skill when
- The task is subtitle generation, TTS, or final mastering.
- You need non-browser source capture that does not require Playwright automation.

## Inputs
- `project/video/manifest.json`
- Pipeline runtime scripts under `scripts/pipeline/`
- Browser/runtime services required by the recording stage

## Outputs
- `project/video/scenes/*.mp4`
- `project/video/evidence/record_summary.json`
- `project/video/evidence/failures.log`
- `project/video/evidence/*.png`
- `project/video/evidence/*.zip`

## Quick Commands
- `./scripts/pipeline/ensure_services.sh`
- `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- `./scripts/pipeline/run_stage.sh record --headless false`
- `./scripts/pipeline/rerun_failed.sh --headless false`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills playwright-scene-recorder`
- Confirm artifact exists: `project/video/scenes/*.mp4`
- Confirm artifact exists: `project/video/evidence/record_summary.json`
- Confirm artifact exists: `project/video/evidence/failures.log`

## Failure & Recovery
- Run preflight before recording to catch service/runtime failures early: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scenes first: `./scripts/pipeline/rerun_failed.sh --headless false`
- After recovery, regenerate pipeline validation artifacts: `./scripts/pipeline/run_stage.sh validate`
