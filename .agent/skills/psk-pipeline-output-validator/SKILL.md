---
name: psk-pipeline-output-validator
description: Use when execute objective artifact validation for scene completeness, video/audio integrity, subtitle presence, and report generation to prevent false-positive pipeline success
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-pipeline-output-validator

## Mission
Run deterministic validation checks and emit machine-readable plus human-readable reports.

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
- `project/video/evidence/validation_report.json`
- `project/video/evidence/validation_report.md`

## Quick Commands
- `./scripts/pipeline/run_stage.sh validate`
- `python3 scripts/pipeline/validate_outputs.py --manifest project/video/manifest.json`
- `python3 scripts/pipeline/validate_outputs.py --max-black-ratio 0.95 --max-silence-ratio 0.98 --min-cue-count 1`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-pipeline-output-validator`
- Confirm artifact exists: `project/video/evidence/validation_report.json`
- Confirm artifact exists: `project/video/evidence/validation_report.md`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
