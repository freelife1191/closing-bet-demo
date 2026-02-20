---
name: psk-promo-asset-studio
description: Use when generating markdown prompt packs for thumbnail, YouTube description, project overview, and Gemini PPT slides
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# psk-promo-asset-studio

## Mission
Generate promotion prompt assets as deterministic markdown files for downstream creative tools.

## Use this skill when
- 영상 제작 마지막 단계에서 홍보용 프롬프트 패키지가 필요할 때
- 썸네일/설명문/문서/PPT 초안 생성을 일관된 포맷으로 위임할 때

## Inputs
- `project/video/manifest.json`
- `project/video/evidence/quality_report.json`
- run arguments: `--title`, `--subtitle`, `--language`

## System Prompt Contract
- 역할: 제품 마케팅 프롬프트 엔지니어
- 금지: 과장 수익 문구, 근거 없는 성능 주장
- 필수: `System Prompt`, `User Prompt`, `Output Format`, `Quality Checklist` 섹션
- 언어: ko+en 시청자 기준 설명 포함

## Output Schema
- `project/video/assets/thumbnail_prompt_nanobanana_pro.md`
- `project/video/assets/youtube_description_prompt.md`
- `project/video/assets/project_overview_doc_prompt.md`
- `project/video/assets/ppt_slide_prompt_gemini.md`

## Quick Commands
- `./project/project-showcase-kit/scripts/pipeline/run_stage.sh assets --thumbnail-mode manual --title "Smart Money Bot KR Showcase" --subtitle "Scene Gate + Sync Precision" --language ko+en`

## Verification
- `python3 project/project-showcase-kit/scripts/skills/validate_skill_structure.py --skills psk-promo-asset-studio`
- `project/project-showcase-kit/.venvs/verify/bin/python -m pytest -q project/project-showcase-kit/tests/pipeline/test_assets_prompt_pack_contract.py`
- Confirm artifact exists: `project/video/assets/thumbnail_prompt_nanobanana_pro.md`
- Confirm artifact exists: `project/video/assets/youtube_description_prompt.md`
- Confirm artifact exists: `project/video/assets/project_overview_doc_prompt.md`
- Confirm artifact exists: `project/video/assets/ppt_slide_prompt_gemini.md`

## Failure & Recovery
- `./project/project-showcase-kit/scripts/pipeline/run_stage.sh assets --thumbnail-mode manual --title "..." --subtitle "..." --language ko+en`
- `./project/project-showcase-kit/scripts/pipeline/run_stage.sh validate`
