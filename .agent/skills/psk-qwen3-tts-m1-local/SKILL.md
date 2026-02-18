---
name: psk-qwen3-tts-m1-local
description: Use when legacy compatibility wrapper for the old Apple Silicon-focused Qwen3-TTS skill. Prefer `psk-qwen3-tts-universal` for cross-platform setup and runtime
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-qwen3-tts-m1-local

## Mission
Operate and verify the psk-qwen3-tts-m1-local workflow with deterministic outputs.

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
- `bash
bash .agent/skills/psk-qwen3-tts-m1-local/scripts/install_qwen3_tts_m1.sh
bash .agent/skills/psk-qwen3-tts-m1-local/scripts/smoke_test_qwen3_tts.sh`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-qwen3-tts-m1-local`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
