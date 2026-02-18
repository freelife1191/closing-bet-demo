---
name: scene-script-architect
description: Use when you need to analyze project code and generate scene-by-scene scenario plus narration script grounded in actual routes/features
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# scene-script-architect

## Mission
Create `manifest.json` and `script.md` with realistic, testable scenes.

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
- `project/video/manifest.json`
- `project/video/script.md`

## Quick Commands
- `./scripts/pipeline/run_stage.sh manifest --language ko+en --duration-sec 90 --max-scenes 6`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills scene-script-architect`
- Confirm artifact exists: `project/video/manifest.json`
- Confirm artifact exists: `project/video/script.md`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
