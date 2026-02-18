---
name: psk-video-manifest-planner
description: Use when you need to build a scene-level video manifest and narration draft from the current codebase and README with deterministic schema and compliance notes
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-video-manifest-planner

## Mission
Operate and verify the psk-video-manifest-planner workflow with deterministic outputs.

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
- Document expected artifact paths for this skill.

## Quick Commands
- `./scripts/pipeline/run_stage.sh validate # placeholder for psk-video-manifest-planner`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-video-manifest-planner`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
