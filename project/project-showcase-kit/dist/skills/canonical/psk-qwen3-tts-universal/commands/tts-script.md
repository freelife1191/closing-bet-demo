---
name: tts-script
description: Convert markdown/text script into narration audio with chunking and pause.
argument-hint: script.md [--mode custom_voice|voice_design|voice_clone] [--pause 0.65]
allowed-tools: [Bash, Read, Write]
---

# TTS Script

```bash
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode script_to_audio \
  --script /Users/freelife/vibe/lecture/hodu/closing-bet-demo/project/video/script.md \
  --output /tmp/script.wav \
  --script-tts-mode custom_voice \
  --model-size 0.6b \
  --speaker Vivian \
  --language Auto \
  --pause-sec 0.65
```
