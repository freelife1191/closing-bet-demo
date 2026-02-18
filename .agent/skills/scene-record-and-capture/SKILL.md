---
name: scene-record-and-capture
description: Use when you need to run scene-by-scene browser recording, collect failure screenshots/traces, and rerun failed scenes only
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# scene-record-and-capture

## Mission
Record deterministic scene clips and produce evidence for failures.

## Use this skill when
- You need this skill's workflow in the video production pipeline.
- You want deterministic outputs with explicit verification evidence.

## Do not use this skill when
- The task is unrelated to this skill's domain.
- You need a different specialized skill with stricter scope.

## Inputs
- Project sources and pipeline scripts
- Runtime environment variables required by the referenced commands

## Outputs
- `project/video/scenes/*.mp4`
- `project/video/evidence/record_summary.json`
- `project/video/evidence/failures.log`
- `project/video/evidence/*.png`
- `project/video/evidence/*.zip`

## Quick Commands
- `./scripts/pipeline/ensure_services.sh`
- `./scripts/pipeline/run_stage.sh record --headless false`
- `./scripts/pipeline/rerun_failed.sh --headless false`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills scene-record-and-capture`
- Confirm artifact exists: `project/video/scenes/*.mp4`
- Confirm artifact exists: `project/video/evidence/record_summary.json`
- Confirm artifact exists: `project/video/evidence/failures.log`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
