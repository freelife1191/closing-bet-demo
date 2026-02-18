---
name: tts-init
description: Initialize or update qwen3-tts yaml config for defaults and reference voice.
argument-hint: [--reference-audio path.wav] [--reference-text "..."] [--output-dir path]
allowed-tools: [Bash, Read, Write]
---

# TTS Init

## Goal
Write `project/video/config/qwen3_tts.yaml` with default mode/model/language/speaker/style and optional clone reference.

## Command
```bash
bash .agent/skills/qwen3-tts-universal/scripts/init_qwen3_tts_config.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --config-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/video/config/qwen3_tts.yaml \
  --default-mode custom_voice \
  --model-size 0.6b \
  --language Auto \
  --speaker Vivian \
  --style-instruct "차분하고 또렷한 발표 톤" \
  --reference-audio /path/to/ref.wav \
  --reference-text "레퍼런스 대본" \
  --overwrite true
```
