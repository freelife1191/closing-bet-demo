#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-TTS local runner for command-template usage:
  --input {text_file} --output {output_file}
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Qwen3-TTS synthesis")
    parser.add_argument("--input", required=True, help="UTF-8 text file path")
    parser.add_argument("--output", required=True, help="Output wav path")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", default="Auto")
    parser.add_argument("--speaker", default="Vivian")
    parser.add_argument("--instruct", default="")
    parser.add_argument("--device", default="auto", help="auto|mps|cpu|cuda:0")
    parser.add_argument("--dtype", default="auto", help="auto|float32|float16|bfloat16")
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--no-flash-attn", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"input text file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("input text is empty")
    return text


def pick_device(raw: str) -> str:
    value = str(raw).strip().lower()
    if value and value != "auto":
        return raw
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def pick_dtype(raw: str, device: str) -> torch.dtype:
    value = str(raw).strip().lower()
    if value in {"float32", "fp32"}:
        return torch.float32
    if value in {"float16", "fp16"}:
        return torch.float16
    if value in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if device.startswith("cuda"):
        return torch.bfloat16
    if device == "mps":
        return torch.float16
    return torch.float32


def dtype_name(dtype: torch.dtype) -> str:
    mapping = {
        torch.float16: "float16",
        torch.float32: "float32",
        torch.bfloat16: "bfloat16",
    }
    return mapping.get(dtype, str(dtype))


def resolve_speaker(model: Qwen3TTSModel, requested: str) -> str:
    getter = getattr(model.model, "get_supported_speakers", None)
    if not callable(getter):
        return requested
    speakers = getter() or []
    if not speakers:
        return requested

    requested_norm = requested.strip().lower()
    for speaker in speakers:
        if str(speaker).strip().lower() == requested_norm:
            return str(speaker)
    return str(speakers[0])


def build_generate_kwargs(args: argparse.Namespace) -> dict:
    kwargs = {"max_new_tokens": args.max_new_tokens}
    if args.temperature is not None:
        kwargs["temperature"] = args.temperature
    if args.top_p is not None:
        kwargs["top_p"] = args.top_p
    if args.top_k is not None:
        kwargs["top_k"] = args.top_k
    return kwargs


def build_attempts(
    requested_device: str,
    requested_dtype: str,
) -> List[Tuple[str, torch.dtype]]:
    primary_device = pick_device(requested_device)
    primary_dtype = pick_dtype(requested_dtype, primary_device)
    attempts: List[Tuple[str, torch.dtype]] = [(primary_device, primary_dtype)]
    if primary_device == "mps":
        attempts.append(("cpu", torch.float32))
    return attempts


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = read_text(input_path)
    started = time.time()

    attempts = build_attempts(args.device, args.dtype)
    generate_kwargs = build_generate_kwargs(args)
    instruct = args.instruct.strip() or None
    errors: List[str] = []
    resolved_device: Optional[str] = None
    resolved_dtype: Optional[torch.dtype] = None
    wavs = []
    sr = 0

    for device, dtype in attempts:
        model: Optional[Qwen3TTSModel] = None
        try:
            load_kwargs = {"device_map": device, "dtype": dtype}
            if device.startswith("cuda") and not args.no_flash_attn:
                load_kwargs["attn_implementation"] = "flash_attention_2"
            model = Qwen3TTSModel.from_pretrained(args.model, **load_kwargs)

            speaker = resolve_speaker(model, args.speaker)
            wavs, sr = model.generate_custom_voice(
                text=text,
                language=args.language,
                speaker=speaker,
                instruct=instruct,
                **generate_kwargs,
            )
            if not wavs:
                raise RuntimeError("model returned empty audio list")

            resolved_device = device
            resolved_dtype = dtype
            break
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{device}/{dtype_name(dtype)} -> {exc}")
        finally:
            model = None
            gc.collect()
            if device == "mps" and hasattr(torch, "mps"):
                try:
                    torch.mps.empty_cache()
                except Exception:
                    pass

    if resolved_device is None or resolved_dtype is None:
        raise RuntimeError("failed to generate audio: " + " | ".join(errors))

    sf.write(str(output_path), wavs[0], sr)

    duration = len(wavs[0]) / float(sr)
    payload = {
        "model": args.model,
        "resolvedDevice": resolved_device,
        "resolvedDtype": dtype_name(resolved_dtype),
        "language": args.language,
        "speaker": speaker,
        "durationSeconds": duration,
        "elapsedSeconds": time.time() - started,
        "input": str(input_path),
        "output": str(output_path),
    }
    meta_path = output_path.with_suffix(".qwen3.json")
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"qwen3-tts output: {output_path}")
    print(f"qwen3-tts meta: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
