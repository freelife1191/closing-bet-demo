# Project Showcase Kit Packaging Design

**Date:** 2026-02-18  
**Status:** Approved (user-confirmed sections 1-4)  
**Owner:** project-showcase-kit

## 1) Goal

`project-showcase-kit` is a reusable package that analyzes any project, discovers how to run/stop services safely, and automatically generates project introduction + feature demonstration video workflow artifacts.

The package must work across multiple AI tools (ClaudeCode, Codex, Gemini, Antigravity) and install skills into root `/.agent/skills` in a namespaced format.

## 2) Approved Decisions

1. Packaging strategy: **src + dist split**.
2. Project name: **project-showcase-kit**.
3. Skill namespace prefix: **`psk-`**.
4. Renaming scope: rename original relevant skills in `/.agent/skills` to `psk-*`.
5. Scope depth: video/audio related full set.
6. Distribution model: one canonical source + per-tool generated variants.

## 3) Architecture

### 3.1 Canonical Skill Source

- Canonical install target remains root skill path:
  - `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/.agent/skills/psk-*`
- All supported tools consume derivatives generated from this canonical set.

### 3.2 Packaging Layout

- Source package root:
  - `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/project-showcase-kit-src`
- Distribution package root:
  - `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/project-showcase-kit-dist`

Proposed structure:

```text
project/project-showcase-kit-src/
  manifest/
    skills-map.yaml
  templates/
    common/
    codex/
    claudecode/
    gemini/
    antigravity/
  scripts/
    build_dist.py
    install_tools.sh

project/project-showcase-kit-dist/
  skills/
    canonical/psk-*
  install/
    codex/install.sh
    claudecode/install.sh
    gemini/install.sh
    antigravity/install.sh
  checklists/
    required.md
```

## 4) Skill Naming and Scope

### 4.1 Naming Convention

- Format: `psk-<domain>-<action>`
- Examples:
  - `psk-project-init-audit`
  - `psk-scene-record`
  - `psk-video-render`
  - `psk-output-validate`

### 4.2 Renaming Scope (approved)

Video/audio-related skill family:

- `video-*`
- `scene-*`
- `playwright-scene-recorder`
- `promo-asset-studio`
- `logo-thumbnail-prompt-designer`
- `pipeline-output-validator`
- `qwen3-tts-*`

## 5) Init Skill Contract (cross-project)

### 5.1 Core init skill

- `psk-project-init-audit`

### 5.2 Required analysis inputs

Read in priority order:

1. `README.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `GEMINI.md`
5. executable scripts/config (`package.json`, `Procfile`, `docker-compose*`, shell scripts, runtime entrypoints)

### 5.3 Required outputs

- `project/video/evidence/project_audit.json`
- `project/video/evidence/project_runbook.md`
- `project/video/evidence/project_flows.md`

### 5.4 Hard constraints

- No hardcoded server assumptions for port/IP/stop command.
- Runtime endpoints and shutdown procedures must be discovered dynamically from analyzed project assets.
- Unresolved values must be marked as pending and require explicit approval before execution.

## 6) Workflow Standard (reusable)

1. Run init audit.
2. Verify run/stop procedures via preflight.
3. Build scene plan + script.
4. Execute record/voice/captions/render pipeline.
5. Validate outputs and collect signoff evidence.

This exact contract must be reusable for other repositories without static environment assumptions.

## 7) Checklist Minimization

Keep one mandatory checklist only:

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/project-showcase-kit-dist/checklists/required.md`

Required checklist gates:

1. Init audit complete (run/stop/health/env captured).
2. Preflight pass.
3. Gate A (script/scene) approved.
4. Gate B (raw capture) approved.
5. Gate C (voice/subtitle) approved.
6. Gate D (final deliverables) approved.
7. Evidence files present (`validation_report`, `manager_report`, `signoff`).

## 8) Packaging and Ignore Policy

### 8.1 Keep in dist

- `psk-*` skills
- templates
- install scripts
- manifests
- required checklist

### 8.2 Exclude by default

- generated scene clips (`*.mp4`)
- generated voice files (`*.wav`)
- large evidence archives (`*.zip`)
- temporary render logs/caches

## 9) Tool-specific Installation Model

- Install result must place final canonical skills into root `/.agent/skills/psk-*`.
- Tool-specific installers are wrappers over canonical content generation/sync.
- Post-install validation must run skill inventory/structure checks.

## 10) Error Handling and Verification

### Error handling

- If project runtime discovery fails, block automation and emit unresolved fields.
- If tool-specific conversion fails, keep canonical package intact and fail fast with recovery hint.

### Verification

- Validate naming consistency (`psk-*`).
- Validate required skill directories/files.
- Validate generated dist install scripts for all 4 tools.
- Validate required checklist completeness and no legacy checklist dependency.

## 11) Out-of-scope for this design step

- Actual implementation edits (renaming, script generation, dist build execution).
- Runtime video artifacts bundling in dist (optional future flag only).
