---
name: psk-video-quality-researcher
description: Use when produce evidence-based quality analysis for generated video outputs and recommend ranked improvements across script, recording, TTS, captions, render, and promotion assets
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-video-quality-researcher

## Mission
Turn validation and manager evidence into a prioritized quality upgrade plan that can be executed and verified.

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
- `./scripts/pipeline/run_stage.sh validate`
- `./scripts/pipeline/run_stage.sh manager-report`
- `./scripts/pipeline/run_stage.sh quality-report`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-video-quality-researcher`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
