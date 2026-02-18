---
name: promo-asset-studio
description: Use when generate thumbnail prompt packs, draft copy assets, and optional placeholder thumbnails for promotion
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# promo-asset-studio

## Mission
Generate promotion assets aligned with final video message.

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
- `project/video/assets/copy.md`
- `project/video/assets/thumbnail.png`

## Quick Commands
- `./scripts/pipeline/run_stage.sh assets --thumbnail-mode manual --title "오늘 장마감 핵심 시그널" --subtitle "AI가 뽑은 KR 시장 인사이트"`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills promo-asset-studio`
- Confirm artifact exists: `project/video/assets/thumbnail_prompt.md`
- Confirm artifact exists: `project/video/assets/copy.md`
- Confirm artifact exists: `project/video/assets/thumbnail.png`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
