# Qwen3-TTS M1 Runtime Profile

## Source
- Qwen3-TTS official repository: `QwenLM/Qwen3-TTS`
- Python package: `qwen-tts`

## Apple Silicon Guidance
- Prefer model: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` for lower memory and faster startup.
- Do not use `flash-attn` on Apple Silicon path.
- Runtime device order:
  1. `mps`
  2. `cpu` fallback
- Runtime dtype order:
  1. `float16` on `mps`
  2. `float32` on `cpu`

## Supported Premium Speakers (CustomVoice model family)
- `Vivian`
- `Serena`
- `Uncle_Fu`
- `Dylan`
- `Eric`
- `Ryan`
- `Aiden`
- `Ono_Anna`
- `Sohee`

## Validation Targets
- `narration.wav` exists and playable.
- Sidecar metadata includes resolved device/dtype.
- Pipeline metadata: `project/video/audio/narration.json` contains engine `qwen-local-cmd`.
