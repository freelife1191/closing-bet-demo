---
name: video-mastering-editor
description: Use when merge clips, narration, and subtitles into a final master video with remotion-first + ffmpeg fallback
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# video-mastering-editor

## Mission
Produce final video output and preserve render evidence.

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
- `out/final_showcase.mp4`
- `project/video/evidence/render.log`

## Quick Commands
- `./scripts/pipeline/run_stage.sh render`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills video-mastering-editor`
- Confirm artifact exists: `out/final_showcase.mp4`
- Confirm artifact exists: `project/video/evidence/render.log`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
