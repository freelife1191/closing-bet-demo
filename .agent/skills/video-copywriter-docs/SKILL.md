---
name: video-copywriter-docs
description: Use when you need to generate distribution-ready title/description/hashtags and concise release notes for video assets
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# video-copywriter-docs

## Mission
Produce publish-ready copy and supporting explanation docs.

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
- `project/video/assets/copy.md`
- `project/video/assets/release_notes.md`

## Quick Commands
- `./scripts/pipeline/run_stage.sh validate # placeholder for video-copywriter-docs`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills video-copywriter-docs`
- Confirm artifact exists: `project/video/assets/copy.md`
- Confirm artifact exists: `project/video/assets/release_notes.md`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
