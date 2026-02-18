---
name: tts-design
description: Generate speech with voice design model using style instruction.
argument-hint: "text" --instruct "style prompt" [--language English] [--output file.wav]
allowed-tools: [Bash, Read, Write]
---

# TTS Design

```bash
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_design \
  --text "We are launching the new feature today." \
  --output /tmp/design.wav \
  --language English \
  --instruct "Warm and confident female narrator, medium speaking rate"
```
