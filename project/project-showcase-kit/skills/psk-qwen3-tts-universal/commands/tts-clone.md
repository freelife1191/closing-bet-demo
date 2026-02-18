---
name: tts-clone
description: Generate speech by cloning a reference voice (audio + transcript).
argument-hint: "text" --ref-audio ref.wav --ref-text "..." [--model-size 0.6b]
allowed-tools: [Bash, Read, Write]
---

# TTS Clone

```bash
.venv-qwen3-tts/bin/python .agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py \
  --mode voice_clone \
  --text "이 문장은 레퍼런스 화자의 음색을 유지합니다." \
  --output /tmp/clone.wav \
  --model-size 0.6b \
  --language Korean \
  --ref-audio /path/to/ref.wav \
  --ref-text "레퍼런스 음성에 해당하는 정확한 문장"
```

`--x-vector-only-mode`를 쓰면 `--ref-text` 없이도 실행 가능하지만 품질은 낮아질 수 있습니다.
