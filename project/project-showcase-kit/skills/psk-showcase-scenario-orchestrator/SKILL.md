---
name: psk-showcase-scenario-orchestrator
description: Use when you need to orchestrate short/normal/detail showcase scenario generation with strict scene-level sync and dual ko/en script contracts
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-showcase-scenario-orchestrator

## Mission
Generate `short/normal/detail` scene plans, dual scripts, and sync bundles, then block downstream stages unless terminology/sync gates pass.

## Use this skill when
- 3버전 쇼케이스를 한 번에 준비해야 할 때
- 씬 단위 싱크/용어 게이트를 선행 통과시켜야 할 때

## Inputs
- `project/video/manifest.json`
- `project/video/scenarios/scenario_*.md`
- `project/video/scenarios/script_*.ko.md`, `script_*.en.md`

## System Prompt Contract
- 역할: 영상 시나리오 오케스트레이터
- 금지: 한국어 대본을 영어 대본에 폴백
- 필수: scene별 `target_sec`, `tts_rate`, `caption_cues`, `scene_extend_budget_sec`
- 톤: 실행 지시형, 모호한 표현 금지

## Output Schema
- `project/video/scenarios/scene_plan_<version>.json`
- `project/video/scenarios/sync_bundle_<version>.json`
- `project/video/scenarios/script_<version>.ko.md`
- `project/video/scenarios/script_<version>.en.md`

## Quick Commands
- `./project/project-showcase-kit/scripts/pipeline/run_stage.sh showcase-scenario --language ko+en`
- `python3 project/project-showcase-kit/scripts/video/build_showcase_scenarios.py --out-dir project/video/scenarios`
- `python3 project/project-showcase-kit/scripts/video/build_dual_scripts.py --scenario-dir project/video/scenarios --out-dir project/video/scenarios`
- `python3 project/project-showcase-kit/scripts/video/build_sync_plans.py --scenario-dir project/video/scenarios --out-dir project/video/scenarios`

## Verification
- `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-showcase-scenario-orchestrator`
- `project/project-showcase-kit/.venvs/verify/bin/python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_plan_bundle_contract.py project/project-showcase-kit/tests/pipeline/test_build_dual_scripts.py project/project-showcase-kit/tests/pipeline/test_apply_showcase_dual_script_policy.py`
- Confirm artifact exists: `project/video/scenarios/scene_plan_short.json`
- Confirm artifact exists: `project/video/scenarios/sync_bundle_short.json`
- Confirm artifact exists: `project/video/scenarios/script_short.en.md`

## Failure & Recovery
- `python3 project/project-showcase-kit/scripts/video/build_showcase_scenarios.py --out-dir project/video/scenarios`
- `python3 project/project-showcase-kit/scripts/video/build_dual_scripts.py --scenario-dir project/video/scenarios --out-dir project/video/scenarios`
- `python3 project/project-showcase-kit/scripts/video/build_sync_plans.py --scenario-dir project/video/scenarios --out-dir project/video/scenarios`
- `python3 project/project-showcase-kit/scripts/video/validate_script_terminology.py --manifest project/video/manifest.json --scenario-glob 'project/video/scenarios/scenario_*.md'`
