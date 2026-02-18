---
name: video-qc-gatekeeper
description: Use when enforce human-in-the-loop gate approvals (A/B/C/D), verify evidence completeness, and produce signoff artifacts that block release when mandatory approvals are missing
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# video-qc-gatekeeper

## Mission
Act as the final approval firewall before release.

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
- `./scripts/pipeline/run_stage.sh validate # placeholder for video-qc-gatekeeper`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills video-qc-gatekeeper`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
