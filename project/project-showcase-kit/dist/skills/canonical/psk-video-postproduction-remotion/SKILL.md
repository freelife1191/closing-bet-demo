---
name: psk-video-postproduction-remotion
description: Use when you need to compose scene clips, narration, and subtitles into final output using Remotion with ffmpeg fallback
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-video-postproduction-remotion

## Mission
Operate and verify the psk-video-postproduction-remotion workflow with deterministic outputs.

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
- `./scripts/pipeline/run_stage.sh validate # placeholder for psk-video-postproduction-remotion`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills psk-video-postproduction-remotion`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
