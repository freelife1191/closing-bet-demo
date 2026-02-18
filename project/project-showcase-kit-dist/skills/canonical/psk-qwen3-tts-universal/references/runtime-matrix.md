# Runtime Matrix

## Recommended defaults
- CPU only: `--device cpu --dtype float32 --model-size 0.6b`
- Apple Silicon: `--device auto --dtype auto --model-size 0.6b`
- NVIDIA CUDA (>=16GB VRAM): `--device cuda:0 --dtype bfloat16 --model-size 1.7b`

## Guidance
- If OOM occurs, drop to `--model-size 0.6b`.
- If generation fails on GPU/MPS, retry with `--device cpu --dtype float32`.
- For long scripts, use `--mode script_to_audio` and tune `--split-max-chars`.
