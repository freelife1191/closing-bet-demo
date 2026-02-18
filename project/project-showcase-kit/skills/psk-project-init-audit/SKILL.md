---
name: psk-project-init-audit
description: Use when you need to analyze a project and discover run/stop/health workflow before generating showcase video assets
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-project-init-audit

## Mission
Analyze project documents and executable scripts to discover how to run, stop, and validate the project safely without hardcoding environment assumptions.

## Use this skill when
- You need to initialize project analysis for `project-showcase-kit`.
- You need dynamic run/stop/port discovery before any recording pipeline step.

## Do not use this skill when
- The task is only about video postproduction.
- Runtime discovery is already verified and unchanged.

## Inputs
- Target repository root path
- Project documents: `README.md`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` (if present)
- Runtime scripts and configs: `.env`, `package.json`, `Procfile`, shell scripts

## Outputs
- `project/video/evidence/project_audit.json`
- `project/video/evidence/project_runbook.md`
- `project/video/evidence/project_flows.md`

## Quick Commands
- `python3 .agent/skills/psk-project-init-audit/scripts/run_init_audit.py --project-root .`

## Verification
- `python3 .agent/skills/psk-project-init-audit/scripts/run_init_audit.py --project-root .`
- `test -f project/video/evidence/project_audit.json`
- `test -f project/video/evidence/project_runbook.md`
- `test -f project/video/evidence/project_flows.md`

## Failure & Recovery
- If run/stop commands are unresolved, review `project_audit.json` unresolved fields and confirm manually.
- If ports are unresolved, inspect `.env`, `package.json`, and startup shell scripts, then rerun init audit.
- If outputs are stale, rerun the command with `--overwrite true`.
