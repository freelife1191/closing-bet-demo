---
name: video-tts-local-free
description: Use when you need to generate narration with local free engines (qwen-local-cmd/supertonic-local) and avoid cloud API dependency by default
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# video-tts-local-free

## Mission
Operate and verify the video-tts-local-free workflow with deterministic outputs.

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
- `./scripts/pipeline/run_stage.sh voice --tts-engine auto-local --language ko+en`
- `python3 scripts/video/gen_voice.py --engine qwen-local-cmd --language ko+en --manifest project/video/manifest.json --out project/video/audio/narration.wav`
- `python3 scripts/video/gen_voice.py --engine supertonic-local --language ko+en --manifest project/video/manifest.json --out project/video/audio/narration.wav`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills video-tts-local-free`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
