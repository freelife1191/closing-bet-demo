---
name: qwen3-tts-universal
description: Use when cross-platform Qwen3-TTS setup and operation skill for macOS/Linux/Windows-WSL PCs. Installs local runtime, configures default command-template (`QWEN_LOCAL_CMD`), and supports custom voice, voice design, and voice clone workflows with model-size, language, speaker, and style-instruction options
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# qwen3-tts-universal

## Mission
Make Qwen3-TTS usable as the default local TTS engine on diverse PCs (Apple Silicon, NVIDIA CUDA, CPU-only) with one repeatable workflow.

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
- `bash
bash .agent/skills/qwen3-tts-universal/scripts/install_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --default-mode custom_voice \
  --model-size 0.6b \
  --language Auto \
  --speaker Vivian \
  --write-dotenv true`
- `bash
bash .agent/skills/qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --mode all`
- `bash
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode custom_voice \
  --text "안녕하세요. 프로젝트 브리핑을 시작합니다." \
  --output /tmp/custom.wav \
  --model-size 1.7b \
  --speaker Sohee \
  --language Korean \
  --instruct "차분하고 또렷한 발표 톤"`
- `bash
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_design \
  --text "This is a design voice test." \
  --output /tmp/design.wav \
  --model-size 1.7b \
  --language English \
  --instruct "Warm, confident female narrator with clear pacing"`
- `bash
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_clone \
  --text "이 문장은 레퍼런스 음성을 따라 읽습니다." \
  --output /tmp/clone.wav \
  --model-size 0.6b \
  --language Korean \
  --ref-audio /path/to/ref.wav \
  --ref-text "원본 레퍼런스 음성의 정확한 대본"`
- `bash
.venv-qwen3-tts/bin/python .agent/skills/qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode script_to_audio \
  --script /path/to/script.md \
  --output /tmp/script.wav \
  --script-tts-mode custom_voice \
  --model-size 0.6b \
  --speaker Vivian \
  --language Auto`
- `bash
./scripts/pipeline/run_stage.sh voice --tts-engine qwen-local-cmd --language ko+en`

## Verification
- `python3 scripts/skills/validate_skill_structure.py --skills qwen3-tts-universal`

## Failure & Recovery
- Run preflight checks first: `./scripts/pipeline/run_stage.sh preflight --tts-engine auto --strict-tts false --auto-start-services true`
- Re-run only failed scope when possible: `./scripts/pipeline/rerun_failed.sh`
- Regenerate validation artifacts: `./scripts/pipeline/run_stage.sh validate`
