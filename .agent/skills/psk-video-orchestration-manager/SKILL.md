---
name: psk-video-orchestration-manager
description: Use when you need to lead end-to-end video production orchestration across manifest, recording, voice, captions, render, assets, QC, and reporting. Use when one manager agent must control failure routing, minimal reruns, and user approval handoff for release readiness
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-video-orchestration-manager

## Mission
Run the whole pipeline as the top-level manager, then drive a strict evidence-based fix loop until release criteria are met.

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
- `./scripts/pipeline/manager_cycle.sh --language ko+en --duration-sec 90 --max-scenes 6 --tts-engine auto --thumbnail-mode manual`
- `./scripts/pipeline/run_all.sh --language ko+en --duration-sec 90 --max-scenes 6 --tts-engine auto --thumbnail-mode manual`
- `./scripts/pipeline/run_all.sh --language ko+en --duration-sec 90 --max-scenes 6 --tts-engine google --strict-tts false --thumbnail-mode manual`
- `./scripts/pipeline/run_stage.sh manager-report`
- `./scripts/pipeline/run_stage.sh quality-report`
- `./scripts/pipeline/run_stage.sh qc --gate-a <status> --gate-b <status> --gate-c <status> --gate-d <status>`
- `./scripts/pipeline/rerun_failed.sh`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-video-orchestration-manager`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
