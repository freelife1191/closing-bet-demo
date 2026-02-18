---
name: psk-logo-thumbnail-prompt-designer
description: Use when design text-safe prompt templates for logo and thumbnail generation with Korean typography constraints
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-logo-thumbnail-prompt-designer

## Mission
Create robust prompts for external generators to produce logo/thumbnail candidates.

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
- `project/video/assets/thumbnail_prompt.md`
- `project/video/assets/logo_prompt.md`

## Quick Commands
- `./scripts/pipeline/run_stage.sh validate # placeholder for psk-logo-thumbnail-prompt-designer`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-logo-thumbnail-prompt-designer`
- Confirm artifact exists: `project/video/assets/thumbnail_prompt.md`
- Confirm artifact exists: `project/video/assets/logo_prompt.md`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
