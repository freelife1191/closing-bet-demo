---
name: scene-tts-qwen
description: Use when you need to generate narration audio with Qwen-first policy and local fallbacks (supertonic/google)
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# scene-tts-qwen

## Mission
Generate narration wav from manifest with Qwen as primary engine.

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
- `project/video/audio/narration.wav`
- `project/video/audio/narration.json`

## Quick Commands
- `./scripts/pipeline/run_stage.sh voice --tts-engine auto --language ko+en`
- `python3 scripts/video/gen_voice.py --engine qwen --manifest project/video/manifest.json --language ko+en --out project/video/audio/narration.wav`
- `./scripts/pipeline/run_stage.sh voice --tts-engine google --language ko+en`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills scene-tts-qwen`
- Confirm artifact exists: `project/video/audio/narration.wav`
- Confirm artifact exists: `project/video/audio/narration.json`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
