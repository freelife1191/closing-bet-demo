---
name: tts-setup
description: Install and wire up qwen3-tts-universal for cross-platform local usage.
argument-hint: [--model-size 0.6b|1.7b] [--speaker Vivian] [--language Auto]
allowed-tools: [Bash, Read, Write]
---

# TTS Setup

## Goal
Create venv, install `qwen-tts`, write `.env`, and prepare runtime config.

## Command
```bash
bash .agent/skills/qwen3-tts-universal/scripts/install_qwen3_tts.sh \
  --project-root /Users/freelife/vibe/lecture/hodu/closing-bet-demo \
  --venv-path /Users/freelife/vibe/lecture/hodu/closing-bet-demo/.venv-qwen3-tts \
  --model-size 0.6b \
  --default-mode custom_voice \
  --speaker Vivian \
  --language Auto \
  --write-dotenv true
```

## Verify
```bash
bash .agent/skills/qwen3-tts-universal/scripts/smoke_test_qwen3_tts.sh --mode custom_voice
```
