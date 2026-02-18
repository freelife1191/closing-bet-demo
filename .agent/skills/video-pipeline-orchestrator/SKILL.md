---
name: video-pipeline-orchestrator
description: Use when you need to operate the shell-based video pipeline deterministically using scripts/pipeline, with stage dependency control, gate-aware execution, and targeted reruns for failed outputs
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# video-pipeline-orchestrator

## Mission
Execute and recover the stage pipeline with deterministic ordering and minimum rerun cost.

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
- `./scripts/pipeline/ensure_services.sh`
- `./scripts/pipeline/run_all.sh --language ko+en --tts-engine auto --thumbnail-mode manual`
- `./scripts/pipeline/run_all.sh --language ko+en --tts-engine google --strict-tts false --thumbnail-mode manual`
- `./scripts/pipeline/manager_cycle.sh --language ko+en --tts-engine auto --thumbnail-mode manual`
- `./scripts/pipeline/run_stage.sh <stage>`
- `./scripts/pipeline/rerun_failed.sh`
- `./scripts/pipeline/rerun_failed.sh --headless false`
- `./scripts/pipeline/run_stage.sh voice --tts-engine <engine> --language ko+en`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills video-pipeline-orchestrator`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
