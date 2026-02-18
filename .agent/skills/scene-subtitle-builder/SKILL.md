---
name: scene-subtitle-builder
description: Use when you need to generate subtitles from narration audio and validate timing/cue quality
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# scene-subtitle-builder

## Mission
Create accurate subtitle file and metadata from generated narration.

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
- `project/video/captions/subtitles.srt`
- `project/video/captions/subtitles.json`

## Quick Commands
- `./scripts/pipeline/run_stage.sh captions`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills scene-subtitle-builder`
- Confirm artifact exists: `project/video/captions/subtitles.srt`
- Confirm artifact exists: `project/video/captions/subtitles.json`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
