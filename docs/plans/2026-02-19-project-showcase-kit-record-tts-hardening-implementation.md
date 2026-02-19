# project-showcase-kit Record/TTS Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** `project-showcase-kit` 파이프라인에서 실제 화면 녹화, 언어별 TTS+자막 생성, 길이 동기화, `project` 경로 경계 강제를 모두 신뢰 가능하게 만든다.

**Architecture:** 기존 stage 체인을 유지하면서 `record/voice/captions/render/validate`의 계약을 강화한다. 공통 경로 가드와 언어/스피커 정책을 라이브러리로 중앙화하고, stage는 이 정책만 참조한다. 단위 테스트 선행(TDD) 후 통합 테스트를 반복 실행해 회귀를 차단한다.

**Tech Stack:** Bash(run_stage/run_all), Python(argparse/json/subprocess), Playwright(Node), ffmpeg/ffprobe, pytest

---

## 실행 전 고정 규칙
- 기준 루트: `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project`
- 구현 중 항상 @test-driven-development 원칙 적용
- 완료 주장 전 @verification-before-completion 원칙 적용

### Task 1: 경로 경계 정책 모듈 도입

**Files:**
- Create: `project/project-showcase-kit/scripts/lib/path_policy.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_path_policy.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/common.sh`

**Step 1: Write the failing test**

```python
def test_resolve_under_project_root_rejects_escape(tmp_path):
    from path_policy import resolve_under_project_root
    project_root = tmp_path / "project"
    project_root.mkdir()
    with pytest.raises(ValueError):
        resolve_under_project_root(project_root, "../out/final_showcase.mp4")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_path_policy.py::test_resolve_under_project_root_rejects_escape`
Expected: FAIL (`ImportError` 또는 `resolve_under_project_root` 미정의)

**Step 3: Write minimal implementation**

```python
def resolve_under_project_root(project_root: Path, raw_path: str) -> Path:
    target = (project_root / raw_path).resolve()
    if project_root.resolve() not in target.parents and target != project_root.resolve():
        raise ValueError("path escapes project root")
    return target
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_path_policy.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/lib/path_policy.py project/project-showcase-kit/tests/pipeline/test_path_policy.py project/project-showcase-kit/scripts/pipeline/common.sh
git commit -m "test: add project-root path policy guard"
```

### Task 2: 언어/스피커 정책 중앙화

**Files:**
- Create: `project/project-showcase-kit/scripts/lib/language_voice_policy.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_language_voice_policy.py`
- Modify: `project/project-showcase-kit/scripts/lib/kr_text_policy.py`

**Step 1: Write the failing test**

```python
def test_resolve_speaker_by_language():
    from language_voice_policy import resolve_speaker
    assert resolve_speaker("ko") == "Sohee"
    assert resolve_speaker("en") == "Serena"
    assert resolve_speaker("ja") == "Ono_Anna"
    assert resolve_speaker("zh") == "Vivian"
    assert resolve_speaker("de") == "Vivian"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_language_voice_policy.py::test_resolve_speaker_by_language`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
SPEAKER_MAP = {"ko": "Sohee", "en": "Serena", "ja": "Ono_Anna", "zh": "Vivian"}
def resolve_speaker(language_code: str) -> str:
    return SPEAKER_MAP.get(language_code.lower(), "Vivian")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_language_voice_policy.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/lib/language_voice_policy.py project/project-showcase-kit/tests/pipeline/test_language_voice_policy.py project/project-showcase-kit/scripts/lib/kr_text_policy.py
git commit -m "feat: add language speaker mapping policy"
```

### Task 3: manifest 계약(scene.url/actions/narrationByLang) 확장

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/generate_manifest.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_manifest_contract.py`
- Modify: `project/project-showcase-kit/tests/pipeline/test_pipeline_minimal.py`

**Step 1: Write the failing test**

```python
def test_generated_manifest_contains_record_fields(tmp_path):
    # generate_manifest 실행 후
    # scene에 url/actions/narrationByLang 포함 검증
    assert "url" in scene
    assert isinstance(scene["actions"], list)
    assert set(["ko", "en"]).issubset(scene["narrationByLang"].keys())
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_manifest_contract.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
scene["url"] = scene.get("url") or "http://127.0.0.1:3500"
scene["actions"] = scene.get("actions") or [{"type": "wait", "ms": 1000}]
scene["narrationByLang"] = build_multilingual_narration(...)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_manifest_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/generate_manifest.py project/project-showcase-kit/tests/pipeline/test_manifest_contract.py project/project-showcase-kit/tests/pipeline/test_pipeline_minimal.py
git commit -m "feat: extend manifest contract for scene recording"
```

### Task 4: record stage를 Playwright 실제 녹화로 교체

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_record.py`
- Create: `project/project-showcase-kit/scripts/pipeline/stage_record_playwright.mjs`
- Create: `project/project-showcase-kit/tests/pipeline/test_record_playwright_contract.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/preflight_check.sh`

**Step 1: Write the failing test**

```python
def test_record_stage_writes_failure_evidence_on_action_error(tmp_path):
    # 잘못된 selector action 포함 manifest로 record 실행
    # record_summary.json에 failedSceneIds, screenshot/trace 경로가 존재해야 함
    assert payload["status"] == "fail"
    assert payload["failedSceneIds"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_record_playwright_contract.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# stage_record.py
# python에서 manifest 파싱 후 node(stage_record_playwright.mjs) 호출
# 반환 메타를 project/video/evidence/record_summary.json으로 저장
```

```js
// stage_record_playwright.mjs
// scene.url 이동 -> actions 실행 -> video 저장
// 실패 시 screenshot + trace 저장
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_record_playwright_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_record.py project/project-showcase-kit/scripts/pipeline/stage_record_playwright.mjs project/project-showcase-kit/tests/pipeline/test_record_playwright_contract.py project/project-showcase-kit/scripts/pipeline/preflight_check.sh
git commit -m "feat: switch record stage to playwright capture"
```

### Task 5: voice stage 언어별 출력 + speaker 매핑 적용

**Files:**
- Modify: `project/project-showcase-kit/scripts/video/gen_voice.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_stage.sh`
- Create: `project/project-showcase-kit/tests/pipeline/test_voice_multilang_outputs.py`
- Modify: `project/project-showcase-kit/tests/pipeline/test_pipeline_language_sync.py`

**Step 1: Write the failing test**

```python
def test_voice_generates_per_language_outputs_and_speakers(tmp_path):
    # language=ko+en+ja+zh 실행 시
    # project/out/audio/narration.<lang>.wav 존재
    # 메타 speaker가 매핑값과 일치
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_voice_multilang_outputs.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
for code in target_languages:
    speaker = resolve_speaker(code)
    # 언어별 TTS 실행 및 narration.<code>.wav/meta 저장
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_voice_multilang_outputs.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/video/gen_voice.py project/project-showcase-kit/scripts/pipeline/run_stage.sh project/project-showcase-kit/tests/pipeline/test_voice_multilang_outputs.py project/project-showcase-kit/tests/pipeline/test_pipeline_language_sync.py
git commit -m "feat: add multilingual voice outputs with speaker policy"
```

### Task 6: captions 길이 동기화(잘림 방지) 강화

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_captions.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py`
- Modify: `project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py`

**Step 1: Write the failing test**

```python
def test_caption_end_covers_audio_duration(tmp_path):
    # 오디오가 scene 합보다 긴 케이스
    # 마지막 caption end >= audio duration
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
durations, source_total = _scaled_scene_durations(...)
captions[-1]["endSec"] = max(captions[-1]["endSec"], target_duration)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_captions.py project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py
git commit -m "fix: enforce caption timeline coverage for audio"
```

### Task 7: render 언어별 산출물 + 길이 보장

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/stage_render.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_render_duration_policy.py`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_all.sh`

**Step 1: Write the failing test**

```python
def test_render_duration_is_max_of_scene_voice_caption(tmp_path):
    # render_meta.durationSec가 max(scene, voice, captions_end)인지 검증
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_render_duration_policy.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
duration = max(manifest_duration, voice_duration, captions_end, 4.0)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_render_duration_policy.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/stage_render.py project/project-showcase-kit/tests/pipeline/test_render_duration_policy.py project/project-showcase-kit/scripts/pipeline/run_all.sh
git commit -m "fix: enforce render duration policy and per-language outputs"
```

### Task 8: validate stage 확장(경로 경계 + 언어별 계약)

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/validate_outputs.py`
- Create: `project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py`

**Step 1: Write the failing test**

```python
def test_validate_fails_when_output_outside_project_root(tmp_path):
    # 의도적으로 경계 밖 출력 메타를 주입했을 때 fail
    assert payload["status"] == "fail"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
checks.append(make_check("output_within_project_root", is_within_project_root(...), detail))
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/validate_outputs.py project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py
git commit -m "feat: validate project-root boundary and multilingual artifacts"
```

### Task 9: orchestrator 기본값/출력 경로를 `project` 기준으로 통일

**Files:**
- Modify: `project/project-showcase-kit/scripts/pipeline/common.sh`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_stage.sh`
- Modify: `project/project-showcase-kit/scripts/pipeline/run_all.sh`
- Modify: `project/project-showcase-kit/scripts/pipeline/manager_cycle.sh`
- Modify: `project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py`

**Step 1: Write the failing test**

```python
def test_run_all_default_language_is_ko_en():
    # run_all.sh 기본 language가 ko+en인지 검증
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py::test_run_all_default_language_is_ko_en`
Expected: FAIL

**Step 3: Write minimal implementation**

```bash
LANGUAGE="ko+en"
OUT_VIDEO="project/out/final_showcase.mp4"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/project-showcase-kit/scripts/pipeline/common.sh project/project-showcase-kit/scripts/pipeline/run_stage.sh project/project-showcase-kit/scripts/pipeline/run_all.sh project/project-showcase-kit/scripts/pipeline/manager_cycle.sh project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py
git commit -m "refactor: align orchestrator defaults and project-local output paths"
```

### Task 10: QUICK_START/STEP/checklist 문서 정합성 보강

**Files:**
- Modify: `project/jobs/QUICK_START.md`
- Modify: `project/jobs/STEP1.md`
- Modify: `project/jobs/STEP2.md`
- Modify: `project/jobs/STEP3.md`
- Modify: `project/jobs/STEP4.md`
- Modify: `project/jobs/STEP5.md`
- Modify: `project/checklist/1. Production_Workflow.md`
- Modify: `project/checklist/2. Candidate_Decisions.md`
- Create: `project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py`

**Step 1: Write the failing test**

```python
def test_quick_start_mentions_language_and_speaker_policy():
    text = Path("project/jobs/QUICK_START.md").read_text(encoding="utf-8")
    assert "ko+en" in text
    assert "Sohee" in text and "Serena" in text and "Ono_Anna" in text and "Vivian" in text
    assert "project/out" in text
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py`
Expected: FAIL

**Step 3: Write minimal implementation**

```markdown
## 언어/스피커 설정
- 기본: ko+en
- 단일: ko 또는 en
- 추가: ja, zh
- speaker 매핑: ko=Sohee, en=Serena, ja=Ono_Anna, zh/기타=Vivian
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py`
Expected: PASS

**Step 5: Commit**

```bash
git add project/jobs/QUICK_START.md project/jobs/STEP1.md project/jobs/STEP2.md project/jobs/STEP3.md project/jobs/STEP4.md project/jobs/STEP5.md project/checklist/1.\ Production_Workflow.md project/checklist/2.\ Candidate_Decisions.md project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py
git commit -m "docs: update quick start and step checklist for language/speaker policy"
```

### Task 11: 단위 테스트 전체 통과 확보

**Files:**
- Test: `project/project-showcase-kit/tests/pipeline/*.py`

**Step 1: Run focused unit suites**

Run:
`python -m pytest -q project/project-showcase-kit/tests/pipeline/test_path_policy.py project/project-showcase-kit/tests/pipeline/test_language_voice_policy.py project/project-showcase-kit/tests/pipeline/test_manifest_contract.py project/project-showcase-kit/tests/pipeline/test_record_playwright_contract.py project/project-showcase-kit/tests/pipeline/test_voice_multilang_outputs.py project/project-showcase-kit/tests/pipeline/test_captions_sync_policy.py project/project-showcase-kit/tests/pipeline/test_render_duration_policy.py project/project-showcase-kit/tests/pipeline/test_validate_output_contract.py project/project-showcase-kit/tests/pipeline/test_docs_quick_start_contract.py`

Expected: PASS

**Step 2: Fix any failures minimally**

```python
# 실패 스택트레이스 기준으로 최소 수정만 반영
```

**Step 3: Re-run focused unit suites**

Run: 위와 동일
Expected: PASS

**Step 4: Commit**

```bash
git add project/project-showcase-kit
git commit -m "test: stabilize pipeline unit suites for record/tts hardening"
```

### Task 12: 통합 테스트 반복 + 산출물 검증

**Files:**
- Test: `project/project-showcase-kit/tests/pipeline/test_pipeline_minimal.py`
- Test: `project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py`
- Test: `project/project-showcase-kit/tests/pipeline/test_pipeline_language_sync.py`
- Test: `project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py`

**Step 1: Run integration suite (1차)**

Run: `python -m pytest -q project/project-showcase-kit/tests/pipeline/test_pipeline_minimal.py project/project-showcase-kit/tests/pipeline/test_pipeline_full_stages.py project/project-showcase-kit/tests/pipeline/test_pipeline_language_sync.py project/project-showcase-kit/tests/pipeline/test_pipeline_runtime_units.py`
Expected: PASS

**Step 2: Run full suite**

Run: `python -m pytest -q project/project-showcase-kit/tests`
Expected: PASS

**Step 3: Repeat integration suite (2차)**

Run: Step 1과 동일
Expected: PASS

**Step 4: Runtime smoke**

Run:
`./scripts/pipeline/run_all.sh --language ko+en --tts-engine qwen-local-cmd --strict-tts true --skip-health --auto-start-services false`

Expected: `project/out/final_showcase.ko.mp4`, `project/out/final_showcase.en.mp4`, `project/video/evidence/validation_report.json(status=pass)`

**Step 5: Commit**

```bash
git add project/project-showcase-kit/tests project/jobs project/checklist
git commit -m "chore: finalize record/tts hardening with integration verification"
```

## 최종 검증 체크리스트
- [ ] 기본 언어 `ko+en` 실행 시 2개 언어 영상 생성
- [ ] 단일 언어 `ko` 또는 `en` 실행 시 단일 산출물 생성
- [ ] `ja`, `zh` 추가 시 speaker 매핑 적용
- [ ] TTS/자막/렌더 길이 동기화 검증 pass
- [ ] 모든 산출물이 `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/project` 하위에만 생성
- [ ] `project/jobs/QUICK_START.md`와 실제 옵션 동작 일치
