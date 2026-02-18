# Project Skills Modernization Design (Video Pipeline)

Date: 2026-02-18
Status: Approved
Scope: Project-created video pipeline skills only (`scene-*`, `video-*`, `pipeline-*`, `promo-*`, `logo-*`, `qwen3-*`)

## 1) Goal
Improve skill hit-rate and execution efficiency by standardizing project skills to a structured, testable, and compatibility-safe format modeled after `qwen3-tts-universal`.

## 2) Constraints
- Do not modify superpowers skills under `/Users/freelife/.agents/skills/superpowers`.
- Keep backward compatibility at 100% for existing commands/paths.
- Produce per-skill detailed reports including before/after, rationale, and verification logs.
- Prefer deterministic, script-backed execution over narrative-only skill docs.

## 3) Target Skills
- `logo-thumbnail-prompt-designer`
- `pipeline-output-validator`
- `promo-asset-studio`
- `qwen3-tts-m1-local`
- `qwen3-tts-universal`
- `scene-record-and-capture`
- `scene-script-architect`
- `scene-subtitle-builder`
- `scene-tts-qwen`
- `video-copywriter-docs`
- `video-manifest-planner`
- `video-mastering-editor`
- `video-orchestration-manager`
- `video-pipeline-orchestrator`
- `video-postproduction-remotion`
- `video-qc-gatekeeper`
- `video-quality-researcher`
- `video-tts-local-free`

## 4) Architecture
### 4.1 Core Skill Layer
Standardize each skill directory to include:
- `SKILL.md` (trigger-first / CSO optimized)
- `commands/` (task-level command references)
- `scripts/` (runtime wrappers/validators)
- `config/` (template defaults)
- `samples/` (repro inputs)
- `references/` (deep docs and troubleshooting)

### 4.2 Compatibility Layer
Ensure zero-break migration:
- Preserve legacy command paths and argument patterns.
- Add wrapper/alias scripts where path or behavior changes.
- Keep stage orchestration scripts (`scripts/pipeline/*.sh`) unchanged unless required for compatibility.

### 4.3 Quality Gate Layer
Every skill must have:
- At least one smoke execution path.
- Explicit pass/fail criteria.
- Artifact checks tied to real output files/metadata.

## 5) Standardized Skill Spec
## 5.1 SKILL.md template
Required sections:
- Mission
- Use this skill when / Do not use this skill when
- Inputs/Outputs
- Quick Commands
- Verification
- Failure & Recovery

`description` policy:
- Start with `Use when ...`
- Mention trigger conditions only (not workflow summary)
- Keep concise and searchable

## 5.2 commands/*
- Split operational actions (`setup/run/rerun/validate/report`) into separate files.
- Each command doc must include argument hint, command, expected artifacts, and success criteria.

## 5.3 scripts/*
- Wrappers validate env/inputs before running core commands.
- Common error messages and normalized exit handling.
- Maintain compatibility aliases for old calls.

## 5.4 config/samples/references
- `config/*.template.yaml`: default values and env mapping.
- `samples/*`: minimum reproducible inputs for smoke tests.
- `references/*`: troubleshooting, runtime constraints, operator notes.

## 6) Execution Flow
1. Inventory each target skill (current structure, commands, gaps).
2. Apply standard template per skill.
3. Add compatibility wrappers/aliases.
4. Run static + runtime verification.
5. Generate per-skill detailed report.
6. Repeat until all target skills satisfy DoD.

## 7) Error Handling Model
Classify failures uniformly:
- Environment missing (ports/tools/keys)
- Invalid inputs (manifest/script/assets)
- Execution failure (non-zero, missing artifacts)

Each class must map to immediate recovery command(s).

## 8) Definition of Done
A skill is complete when:
- Structured directories exist (or are explicitly N/A with rationale).
- Trigger-first `SKILL.md` is present.
- Smoke path executes and verifies outputs.
- Legacy commands continue to work.
- Detailed per-skill report exists with evidence and logs.

## 9) Verification Strategy
- Static lint: required sections/files/command references.
- Runtime smoke: one representative command per skill.
- Compatibility regression: execute legacy command forms.

## 10) Risks and Mitigations
- Risk: Over-standardization may add maintenance burden.
  - Mitigation: keep templates minimal, avoid redundant docs.
- Risk: compatibility wrappers drift from canonical commands.
  - Mitigation: wrappers call canonical scripts directly.
- Risk: false-positive verification.
  - Mitigation: enforce artifact existence + key metadata assertions.

## 11) Deliverables
- Design doc: this file
- Implementation plan doc (next): `docs/plans/2026-02-18-project-skills-modernization.md`
- Per-skill detailed report bundle under `docs/plans/reports/` (during execution)
