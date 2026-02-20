# Project Showcase Video Quality & Sync Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `project-showcase-kit`의 3버전 쇼케이스 영상(`short/normal/detail`)을 씬 단위 품질 게이트와 `ko+en` 분리 대본 정책으로 안정적으로 생성하고, 홍보 프롬프트 md 자산을 자동 산출한다.

**Architecture:** 기존 `run_all.sh -> run_stage.sh` 체인은 유지하되, pre-production(`scene_plan + dual_script + sync_bundle`)과 production(`scene runner + retry + scene gate`)을 분리해 씬 합격 후에만 다음 씬으로 진행한다. 영어 대본은 한국어 폴백을 금지하고 별도 생성물로 관리한다. post-production에서 버전 게이트/런타임 예산/홍보 프롬프트 자산을 일괄 검증한다.

**Tech Stack:** Python 3.11, Bash, Node.js(Playwright), ffmpeg/ffprobe, pytest, JSON/Markdown

---

사전 적용 스킬: `@superpowers:test-driven-development`, `@superpowers:systematic-debugging`, `@superpowers:verification-before-completion`

### Task 1: 듀얼 대본 생성기 추가 (`ko/en` 완전 분리)

**Files:**
- Create: `project/project-showcase-kit/scripts/video/build_dual_scripts.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_build_dual_scripts.py`
- Modify: `project/project-showcase-kit/scripts/video/build_showcase_scenarios.py`

**Step 1: Write the failing test**

```python
def test_dual_scripts_are_generated_and_english_has_low_hangul_ratio(tmp_path: Path):
    # scenario_short.md 입력
    # expected outputs:
    # - script_short.ko.md
    # - script_short.en.md
    # - en 텍스트 한글 비율 <= 0.05
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_dual_scripts.py::test_dual_scripts_are_generated_and_english_has_low_hangul_ratio`
Expected: FAIL (`build_dual_scripts.py` 미존재)

**Step 3: Write minimal implementation**

```python
# build_dual_scripts.py
# - 입력: scenario_*.md
# - 출력: script_<version>.ko.md / script_<version>.en.md
# - en 생성 규칙: ko와 독립 문장 생성 + hangul_ratio 검사
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_build_dual_scripts.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/build_dual_scripts.py \
  project/project-showcase-kit/tests/pipeline/test_build_dual_scripts.py \
  project/project-showcase-kit/scripts/video/build_showcase_scenarios.py
git commit -m "feat: add dual ko/en script builder with english contamination guard"
```

### Task 2: 시나리오 적용 경로의 영어 폴백 제거

**Files:**
- Modify: `project/project-showcase-kit/scripts/video/apply_showcase_scenario.py`
- Modify: `project/project-showcase-kit/scripts/lib/language_voice_policy.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_apply_showcase_dual_script_policy.py`

**Step 1: Write the failing test**

```python
def test_apply_showcase_fails_when_en_missing_or_korean_contaminated(tmp_path: Path):
    # en 대본 누락/오염 시 비정상 종료 기대
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_apply_showcase_dual_script_policy.py`
Expected: FAIL (현재는 ko 폴백 허용)

**Step 3: Write minimal implementation**

```python
# apply_showcase_scenario.py
# - script_<version>.en.md를 우선 소스로 읽는다.
# - en 문구 미존재/한글 오염 임계 초과 시 ValueError 발생.
# - translate_legacy_scene_text 폴백 경로 제거.
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_apply_showcase_dual_script_policy.py project/project-showcase-kit/tests/pipeline/test_showcase_manifest_from_scenario_stage_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/apply_showcase_scenario.py \
  project/project-showcase-kit/scripts/lib/language_voice_policy.py \
  project/project-showcase-kit/tests/pipeline/test_apply_showcase_dual_script_policy.py
git commit -m "feat: enforce strict english script policy in showcase apply stage"
```

### Task 3: `scene_plan`/`sync_bundle` 산출물 계약 도입

**Files:**
- Modify: `project/project-showcase-kit/scripts/video/build_showcase_scenarios.py`
- Modify: `project/project-showcase-kit/scripts/video/build_sync_plans.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_scene_plan_bundle_contract.py`
- Modify: `project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py`

**Step 1: Write the failing test**

```python
def test_showcase_generates_scene_plan_and_sync_bundle(tmp_path: Path):
    # expected files:
    # - scene_plan_short.json
    # - sync_bundle_short.json
    # expected fields:
    # - scene_id, target_sec, tts_rate, caption_cues, scene_extend_budget_sec
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_plan_bundle_contract.py`
Expected: FAIL (신규 json 산출물 없음)

**Step 3: Write minimal implementation**

```python
# build_showcase_scenarios.py
# - markdown 외 scene_plan_<version>.json 생성
# build_sync_plans.py
# - tts_plan/caption_plan 외 sync_bundle_<version>.json 생성
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_plan_bundle_contract.py project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/build_showcase_scenarios.py \
  project/project-showcase-kit/scripts/video/build_sync_plans.py \
  project/project-showcase-kit/tests/pipeline/test_scene_plan_bundle_contract.py \
  project/project-showcase-kit/tests/pipeline/test_build_sync_plans.py
git commit -m "feat: add scene plan and sync bundle artifacts"
```

### Task 4: 씬 게이트 평가기 추가 (엄격 임계값)

**Files:**
- Create: `project/project-showcase-kit/scripts/pipeline/stage_scene_gate.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_scene_gate_thresholds.py`

**Step 1: Write the failing test**

```python
def test_scene_gate_fails_when_boundary_delta_exceeds_threshold(tmp_path: Path):
    # threshold: boundary<=0.15, caption_voice<=0.10
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_gate_thresholds.py`
Expected: FAIL (`stage_scene_gate.py` 미존재)

**Step 3: Write minimal implementation**

```python
# stage_scene_gate.py
# 입력: scene media/meta + captions
# 출력: scene_gate_report.json
# 규칙: boundary delta / caption-voice delta / action rate / static frame ratio 평가
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_gate_thresholds.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_scene_gate.py \
  project/project-showcase-kit/tests/pipeline/test_scene_gate_thresholds.py
git commit -m "feat: add strict per-scene quality gate evaluator"
```

### Task 5: 씬별 재시도 오케스트레이터 추가 (최대 3회)

**Files:**
- Create: `project/project-showcase-kit/scripts/pipeline/stage_scene_runner.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_stage.sh`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_all.sh`
- Create: `project/project-showcase-kit/tests/pipeline/test_scene_runner_retry_policy.py`

**Step 1: Write the failing test**

```python
def test_scene_runner_retries_failed_scene_up_to_three_times(tmp_path: Path):
    # scene-01 fail->pass, scene-02 pass 시도 시
    # expected: scene-01 최대 3회 내 통과, scene-02 진행
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_runner_retry_policy.py`
Expected: FAIL (`scene-runner` stage 미구현)

**Step 3: Write minimal implementation**

```python
# stage_scene_runner.py
# for each scene:
#   run record/voice/captions/scene-gate
#   fail -> retry <=3
#   pass -> next scene
# run_stage.sh에 stage 추가, run_all.sh 기본 흐름 연결
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_runner_retry_policy.py project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_scene_runner.py \
  project/project-showcase-kit/scripts/pipeline/run_stage.sh \
  project/project-showcase-kit/scripts/pipeline/run_all.sh \
  project/project-showcase-kit/tests/pipeline/test_scene_runner_retry_policy.py
git commit -m "feat: add scene-by-scene runner with retry gate"
```

### Task 6: 음성 메타에 scene ranges 추가 + 자막 씬 경계 정렬

**Files:**
- Modify: `project/project-showcase-kit/scripts/video/gen_voice.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_captions.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_voice_scene_audio_ranges.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_captions_scene_boundary_alignment.py`

**Step 1: Write the failing test**

```python
def test_voice_metadata_contains_scene_audio_ranges(tmp_path: Path):
    # narration.json에 sceneAudioRanges 필드 기대
    ...

def test_captions_respects_scene_boundaries_with_strict_threshold(tmp_path: Path):
    # cue가 scene end를 넘지 않거나 허용 범위 내인지 검증
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_voice_scene_audio_ranges.py project/project-showcase-kit/tests/pipeline/test_captions_scene_boundary_alignment.py`
Expected: FAIL (신규 필드/로직 없음)

**Step 3: Write minimal implementation**

```python
# gen_voice.py
# - sceneAudioRanges, sceneAppliedSpeedFactor, sceneVoiceEndSec 출력
# stage_captions.py
# - sceneAudioRanges 기반 cue 재배치
# - scene_caption_voice_end_delta_sec 계산/메타 기록
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_voice_scene_audio_ranges.py project/project-showcase-kit/tests/pipeline/test_captions_scene_boundary_alignment.py project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/gen_voice.py \
  project/project-showcase-kit/scripts/pipeline/stage_captions.py \
  project/project-showcase-kit/tests/pipeline/test_voice_scene_audio_ranges.py \
  project/project-showcase-kit/tests/pipeline/test_captions_scene_boundary_alignment.py
git commit -m "feat: add scene-aware voice ranges and caption boundary alignment"
```

### Task 7: 검증/리포트 확장 (scene/version/runtime budget)

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/validate_outputs.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_quality_report.py`
- Create: `project/project-showcase-kit/scripts/pipeline/stage_runtime_budget_report.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_scene_version_runtime_reports.py`

**Step 1: Write the failing test**

```python
def test_validate_outputs_includes_scene_and_runtime_budget_checks(tmp_path: Path):
    # expected checks:
    # - scene_gate_pass
    # - version_gate_pass
    # - runtime_budget_within_120min
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_version_runtime_reports.py`
Expected: FAIL (신규 체크 미구현)

**Step 3: Write minimal implementation**

```python
# validate_outputs.py: 신규 게이트 반영
# stage_quality_report.py: scene_gate/version_gate 지표 포함
# stage_runtime_budget_report.py: 총 실행시간/버전별 시간 계산
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_scene_version_runtime_reports.py project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/validate_outputs.py \
  project/project-showcase-kit/scripts/pipeline/stage_quality_report.py \
  project/project-showcase-kit/scripts/pipeline/stage_runtime_budget_report.py \
  project/project-showcase-kit/tests/pipeline/test_scene_version_runtime_reports.py
git commit -m "feat: add scene/version/runtime budget reporting gates"
```

### Task 8: 홍보 프롬프트 md 4종 생성기로 `assets` 단계 업그레이드

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_assets.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_assets_prompt_pack_contract.py`
- Modify: `project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py`

**Step 1: Write the failing test**

```python
def test_assets_stage_generates_required_prompt_pack_markdown(tmp_path: Path):
    # expected files:
    # - thumbnail_prompt_nanobanana_pro.md
    # - youtube_description_prompt.md
    # - project_overview_doc_prompt.md
    # - ppt_slide_prompt_gemini.md
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_assets_prompt_pack_contract.py`
Expected: FAIL (현재 파일명/내용 계약 불일치)

**Step 3: Write minimal implementation**

```python
# stage_assets.py
# - 4종 프롬프트 md 생성
# - 각 문서에 system prompt / user prompt / output schema / quality checklist 포함
# - assets_index.json 갱신
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_assets_prompt_pack_contract.py project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_assets.py \
  project/project-showcase-kit/tests/pipeline/test_assets_prompt_pack_contract.py \
  project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py
git commit -m "feat: generate promo prompt markdown pack in assets stage"
```

### Task 9: 스킬 계약 강화 (오케스트레이션/홍보 프롬프트)

**Files:**
- Modify: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/SKILL.md`
- Modify: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/commands/run.md`
- Modify: `project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator/commands/validate.md`
- Modify: `project/project-showcase-kit/skills/psk-promo-asset-studio/SKILL.md`
- Modify: `project/project-showcase-kit/skills/psk-promo-asset-studio/commands/run.md`
- Modify: `project/project-showcase-kit/skills/psk-promo-asset-studio/commands/validate.md`
- Modify: `project/project-showcase-kit/config/target_skills.yaml`
- Modify: `project/project-showcase-kit/docs/SKILLS_GUIDE.md`
- Modify: `project/project-showcase-kit/tests/skills/test_skill_inventory.py`
- Modify: `project/project-showcase-kit/tests/skills/test_skill_docs_consistency.py`

**Step 1: Write the failing test**

```python
def test_orchestrator_and_promo_skill_docs_define_system_prompt_contracts():
    # SKILL.md에 system prompt 가이드/검증 규칙 필수
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/skills/test_skill_inventory.py project/project-showcase-kit/tests/skills/test_skill_docs_consistency.py`
Expected: FAIL (신규 문서 계약 미반영)

**Step 3: Write minimal implementation**

```markdown
# SKILL.md 업데이트
- Mission/Inputs/Outputs/Verification 강화
- 프롬프트 생성용 system prompt 템플릿 명시
- 산출 md 파일명 계약 명시
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/skills/test_skill_inventory.py project/project-showcase-kit/tests/skills/test_skill_docs_consistency.py project/project-showcase-kit/tests/skills/test_validate_skill_structure.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/skills/psk-showcase-scenario-orchestrator \
  project/project-showcase-kit/skills/psk-promo-asset-studio \
  project/project-showcase-kit/config/target_skills.yaml \
  project/project-showcase-kit/docs/SKILLS_GUIDE.md \
  project/project-showcase-kit/tests/skills/test_skill_inventory.py \
  project/project-showcase-kit/tests/skills/test_skill_docs_consistency.py
git commit -m "docs: strengthen orchestrator and promo skill prompt contracts"
```

### Task 10: 전체 플로우 문서/체크리스트 갱신 + 통합 검증

**Files:**
- Modify: `project/jobs/QUICK_START.md`
- Modify: `project/jobs/STEP2.md`
- Modify: `project/checklist/1. Production_Workflow.md`
- Create: `project/project-showcase-kit/tests/pipeline/test_docs_scene_gate_contract.py`

**Step 1: Write the failing test**

```python
def test_quick_start_mentions_scene_retry_gate_and_prompt_pack_outputs():
    # quick start에 scene retry(3회), strict sync 임계값, prompt pack 경로 명시 기대
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_docs_scene_gate_contract.py`
Expected: FAIL (문서 미반영)

**Step 3: Write minimal implementation**

```markdown
# QUICK_START/STEP/checklist 갱신
- scene runner 사용법
- 게이트 임계값
- 3버전/2언어 출력 계약
- 홍보 프롬프트 md 파일 목록
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_docs_scene_gate_contract.py project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/jobs/QUICK_START.md \
  project/jobs/STEP2.md \
  project/checklist/1.\ Production_Workflow.md \
  project/project-showcase-kit/tests/pipeline/test_docs_scene_gate_contract.py
git commit -m "docs: update workflow for scene gates and promo prompt outputs"
```

### Task 11: 최종 검증 배치 실행 (증거 수집)

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/run_all.sh`
- Create: `project/project-showcase-kit/tests/pipeline/test_pipeline_showcase_quality_e2e_contract.py`

**Step 1: Write the failing test**

```python
def test_run_all_generates_three_versions_two_languages_and_gate_reports(tmp_path: Path):
    # expected outputs:
    # - final_showcase.short|normal|detail.ko|en.mp4
    # - scene_gate_report.json
    # - version_gate_report.json
    # - runtime_budget_report.json
    ...
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_pipeline_showcase_quality_e2e_contract.py`
Expected: FAIL (전체 계약 미완성)

**Step 3: Write minimal implementation**

```bash
# run_all.sh 기본 흐름을
# showcase-scenario -> scene-runner -> render(version/lang) -> assets -> validate/report
# 기준으로 연결
```

**Step 4: Run test to verify it passes**

Run:
`python -m pytest -q project/project-showcase-kit/tests/pipeline/test_pipeline_showcase_quality_e2e_contract.py`

Then run full regression:
`python -m pytest -q project/project-showcase-kit/tests/pipeline`

Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/run_all.sh \
  project/project-showcase-kit/tests/pipeline/test_pipeline_showcase_quality_e2e_contract.py
git commit -m "feat: enforce end-to-end showcase quality pipeline contracts"
```

## Final Verification Checklist (must run before merge)

1. `python -m pytest -q project/project-showcase-kit/tests/pipeline`
2. `python -m pytest -q project/project-showcase-kit/tests/skills`
3. `python -m pytest -q project/project-showcase-kit/tests`
4. `./project/project-showcase-kit/scripts/pipeline/run_all.sh --language ko+en --showcase-scenario true --strict-tts true --skip-health --auto-start-services false`
5. 아티팩트 확인:
   - `project/out/final_showcase.short.ko.mp4`, `.en.mp4`
   - `project/out/final_showcase.normal.ko.mp4`, `.en.mp4`
   - `project/out/final_showcase.detail.ko.mp4`, `.en.mp4`
   - `project/video/evidence/scene_gate_report.json`
   - `project/video/evidence/version_gate_report.json`
   - `project/video/evidence/runtime_budget_report.json`
   - `project/video/assets/thumbnail_prompt_nanobanana_pro.md`
   - `project/video/assets/youtube_description_prompt.md`
   - `project/video/assets/project_overview_doc_prompt.md`
   - `project/video/assets/ppt_slide_prompt_gemini.md`
