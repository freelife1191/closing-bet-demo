# Skills Guide

기준일: 2026-02-18

## 1) 공통 사용법
- Codex에게 스킬명을 직접 언급하면 해당 스킬을 우선 적용합니다.
- 실행형 스킬은 `scripts/pipeline/*.sh` 또는 스킬 내부 `scripts/*.sh`를 기준으로 동작합니다.
- 산출물은 기본적으로 `project/video/`와 `out/` 하위에 생성됩니다.

## 2) Qwen3-TTS 전용 스킬

### `psk-qwen3-tts-universal` (권장)
목적: PC 스펙에 맞춰 Qwen3-TTS를 범용 설치/설정/실행.

관련 명령 문서:
- `.agent/skills/psk-qwen3-tts-universal/commands/tts-setup.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/tts-init.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/tts.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/tts-design.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/tts-clone.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/tts-script.md`

핵심 명령:
```bash
bash .agent/skills/psk-qwen3-tts-universal/scripts/install_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --default-mode custom_voice --model-size 0.6b --language Auto --speaker Vivian --write-dotenv true

bash .agent/skills/psk-qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts --mode all
```

러너 예시:
```bash
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py --mode custom_voice --text "안녕하세요" --output /tmp/custom.wav --model-size 1.7b --speaker Sohee --language Korean --instruct "차분한 톤"
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py --mode voice_design --text "Hello" --output /tmp/design.wav --language English --instruct "Warm female narrator"
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py --mode voice_clone --text "클론 테스트" --output /tmp/clone.wav --ref-audio /path/ref.wav --ref-text "레퍼런스 대본"
```

### `psk-qwen3-tts-m1-local` (Legacy)
목적: 기존 경로 호환용. 내부적으로 universal 스킬 스크립트 호출.

## 3) 영상 제작/검증 스킬 목록

| Skill | 설명 | 주 사용 명령 |
|---|---|---|
| `psk-scene-script-architect` | 코드 기반 시나리오/대본 생성 | `./scripts/pipeline/run_stage.sh manifest --language ko+en --duration-sec auto --max-scenes 6` |
| `psk-scene-record-and-capture` | 씬별 녹화/실패증거 수집/재시도 | `./scripts/pipeline/run_stage.sh record --headless false`, `./scripts/pipeline/rerun_failed.sh --headless false` |
| `psk-scene-tts-qwen` | Qwen 우선 나레이션 생성 | `./scripts/pipeline/run_stage.sh voice --tts-engine auto --language ko+en` |
| `psk-scene-subtitle-builder` | 자막 생성/검증 | `./scripts/pipeline/run_stage.sh captions` |
| `psk-video-mastering-editor` | 오디오+영상+자막 마스터링 | `./scripts/pipeline/run_stage.sh render` |
| `psk-promo-asset-studio` | 썸네일 프롬프트/홍보 문구 생성 | `./scripts/pipeline/run_stage.sh assets --thumbnail-mode manual --title "..." --subtitle "..."` |
| `psk-logo-thumbnail-prompt-designer` | 로고/썸네일 생성 프롬프트 설계 | `project/video/assets/thumbnail_prompt.md` 작성/갱신 |
| `psk-video-copywriter-docs` | 릴리즈 카피/문서 작성 | `project/video/assets/copy.md` 갱신 |
| `psk-pipeline-output-validator` | 산출물 객관검증 리포트 생성 | `./scripts/pipeline/run_stage.sh validate` |
| `psk-video-qc-gatekeeper` | A/B/C/D 승인 게이트 관리 | `./scripts/pipeline/run_stage.sh qc --gate-a approved --gate-b approved --gate-c approved --gate-d approved` |
| `psk-video-postproduction-remotion` | Remotion 우선 후반편집(실패 시 ffmpeg fallback) | `./scripts/pipeline/run_stage.sh render` |
| `psk-playwright-scene-recorder` | Playwright 기반 씬 자동녹화 | `./scripts/pipeline/run_stage.sh record` |
| `psk-video-manifest-planner` | Manifest/Script 표준 스키마 생성 | `project/video/manifest.json`, `project/video/script.md` 생성 |
| `psk-video-pipeline-orchestrator` | stage 그래프 기반 전체 파이프라인 운영 | `./scripts/pipeline/run_all.sh --language ko+en --tts-engine auto --thumbnail-mode manual` |
| `psk-video-orchestration-manager` | 실패 라우팅/최소 재실행/매니저 보고 | `./scripts/pipeline/manager_cycle.sh --language ko+en --duration-sec auto --max-scenes 6 --tts-engine auto --thumbnail-mode manual` |
| `psk-video-quality-researcher` | 품질 분석/개선안/재검증 루프 | `./scripts/pipeline/run_stage.sh quality-report` |
| `psk-video-tts-local-free` | 로컬 무료 TTS 우선 전략 운영 | `./scripts/pipeline/run_stage.sh voice --tts-engine auto-local --language ko+en` |

## 4) 코드 품질/프레임워크 스킬

| Skill | 설명 | 사용 방식 |
|---|---|---|
| `codebase-cleanup-refactor-clean` | 리팩터링/클린코드 개선 | 리팩터링 요청 시 스킬명 명시 |
| `nextjs-16` | Next.js 16 패턴/제약 가이드 | Next.js 페이지/액션/라우트 작업 시 참조 |

## 5) 추천 실행 순서 (영상 제작)
1. `./scripts/pipeline/ensure_services.sh`
2. `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --auto-start-services true`
3. `./scripts/pipeline/run_all.sh --language ko+en --duration-sec auto --max-scenes 6 --tts-engine auto --thumbnail-mode manual --auto-start-services true`
4. 실패 시 `./scripts/pipeline/rerun_failed.sh` 또는 실패 stage만 재실행
5. `./scripts/pipeline/run_stage.sh validate`
6. `./scripts/pipeline/run_stage.sh manager-report && ./scripts/pipeline/run_stage.sh quality-report`
7. `./scripts/pipeline/run_stage.sh qc --gate-a approved --gate-b approved --gate-c approved --gate-d approved`

## 6) 핵심 산출물 체크리스트
- `project/video/manifest.json`
- `project/video/script.md`
- `project/video/scenes/*.mp4`
- `project/video/audio/narration.wav`
- `project/video/captions/subtitles.srt`
- `out/final_showcase.mp4`
- `project/video/evidence/validation_report.json`
- `project/video/evidence/manager_report.json`
- `project/video/evidence/quality_research.md`
- `project/video/evidence/signoff.json`

## 7) 스킬별 Canonical Run 문서
- `.agent/skills/psk-logo-thumbnail-prompt-designer/commands/run.md`
- `.agent/skills/psk-pipeline-output-validator/commands/run.md`
- `.agent/skills/psk-promo-asset-studio/commands/run.md`
- `.agent/skills/psk-qwen3-tts-m1-local/commands/run.md`
- `.agent/skills/psk-qwen3-tts-universal/commands/run.md`
- `.agent/skills/psk-playwright-scene-recorder/commands/run.md`
- `.agent/skills/psk-scene-record-and-capture/commands/run.md`
- `.agent/skills/psk-scene-script-architect/commands/run.md`
- `.agent/skills/psk-scene-subtitle-builder/commands/run.md`
- `.agent/skills/psk-scene-tts-qwen/commands/run.md`
- `.agent/skills/psk-video-copywriter-docs/commands/run.md`
- `.agent/skills/psk-video-manifest-planner/commands/run.md`
- `.agent/skills/psk-video-mastering-editor/commands/run.md`
- `.agent/skills/psk-video-orchestration-manager/commands/run.md`
- `.agent/skills/psk-video-pipeline-orchestrator/commands/run.md`
- `.agent/skills/psk-video-postproduction-remotion/commands/run.md`
- `.agent/skills/psk-video-qc-gatekeeper/commands/run.md`
- `.agent/skills/psk-video-quality-researcher/commands/run.md`
- `.agent/skills/psk-video-tts-local-free/commands/run.md`
