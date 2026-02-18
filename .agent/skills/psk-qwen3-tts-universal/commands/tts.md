---
name: tts
description: Generate custom voice TTS with speaker/language/model-size/style options.
argument-hint: "text" [--speaker Sohee] [--language Korean] [--model-size 1.7b] [--instruct "..."]
allowed-tools: [Bash, Read, Write]
---

# TTS (Custom Voice)

```bash
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode custom_voice \
  --text "안녕하세요. 오늘 리포트를 시작합니다." \
  --output /tmp/custom.wav \
  --model-size 1.7b \
  --speaker Sohee \
  --language Korean \
  --instruct "차분한 아나운서 톤"
```
