#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified local Qwen3-TTS runner.

Supports:
- custom voice (speaker + language + optional style instruction)
- voice design (language + style instruction)
- voice clone (reference audio/text)
- script to audio (paragraph/chunk synthesis)
- command-template usage: --input {text_file} --output {output_file}
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


MODEL_MAP: Dict[str, Dict[str, str]] = {
    "custom_voice": {
        "0.6b": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    },
    "voice_clone": {
        "0.6b": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    },
    "voice_design": {
        "1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    },
}

MODE_ALIASES: Dict[str, str] = {
    "": "custom_voice",
    "custom": "custom_voice",
    "custom_voice": "custom_voice",
    "tts": "custom_voice",
    "design": "voice_design",
    "voice_design": "voice_design",
    "tts_design": "voice_design",
    "clone": "voice_clone",
    "voice_clone": "voice_clone",
    "tts_clone": "voice_clone",
    "script": "script_to_audio",
    "script_to_audio": "script_to_audio",
    "tts_script": "script_to_audio",
    "list": "list_capabilities",
    "list_capabilities": "list_capabilities",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Qwen3-TTS unified local runner")
    parser.add_argument("command", nargs="?", default="", help="custom|design|clone|script|list")
    parser.add_argument(
        "--mode",
        default=os.getenv("QWEN3_TTS_DEFAULT_MODE", "custom_voice"),
        help="custom_voice|voice_design|voice_clone|script_to_audio|list_capabilities",
    )

    parser.add_argument("--input", default="", help="Input text or script file path")
    parser.add_argument("--text", default="", help="Input text inline")
    parser.add_argument("--script", default="", help="Script file path (.md/.txt)")
    parser.add_argument("--output", default="", help="Output wav path")
    parser.add_argument("--meta-out", default="", help="Output metadata json path")

    parser.add_argument("--model", default=os.getenv("QWEN3_TTS_MODEL", ""), help="Explicit model id/path override")
    parser.add_argument("--model-size", default=os.getenv("QWEN3_TTS_MODEL_SIZE", "0.6b"), help="0.6b|1.7b")
    parser.add_argument("--language", default=os.getenv("QWEN3_TTS_LANGUAGE", "Auto"), help="Auto|Korean|English|...")
    parser.add_argument("--speaker", default=os.getenv("QWEN3_TTS_SPEAKER", "Vivian"), help="Custom voice speaker")
    parser.add_argument(
        "--instruct",
        default=os.getenv("QWEN3_TTS_STYLE_INSTRUCT", ""),
        help="Style instruction for custom/design",
    )

    parser.add_argument("--ref-audio", default="", help="Reference audio path for voice clone")
    parser.add_argument("--ref-text", default="", help="Reference transcript for voice clone")
    parser.add_argument("--ref-text-file", default="", help="Reference transcript file for voice clone")
    parser.add_argument("--x-vector-only-mode", action="store_true", help="Clone with speaker embedding only")

    parser.add_argument(
        "--script-tts-mode",
        default="custom_voice",
        help="When mode=script_to_audio: custom_voice|voice_design|voice_clone",
    )
    parser.add_argument("--split-max-chars", type=int, default=280)
    parser.add_argument("--pause-sec", type=float, default=0.65)

    parser.add_argument("--device", default=os.getenv("QWEN3_TTS_DEVICE", "auto"), help="auto|cuda:0|mps|cpu")
    parser.add_argument("--dtype", default=os.getenv("QWEN3_TTS_DTYPE", "auto"), help="auto|float16|float32|bfloat16")
    parser.add_argument("--no-flash-attn", action="store_true")

    parser.add_argument("--max-new-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)

    parser.add_argument("--strict-speaker", action="store_true", help="Fail if speaker is unsupported")
    parser.add_argument("--strict-language", action="store_true", help="Fail if language is unsupported")
    return parser.parse_args()


def normalize_mode(raw: str) -> str:
    key = str(raw).strip().lower()
    if key in MODE_ALIASES:
        return MODE_ALIASES[key]
    raise ValueError(f"unsupported mode: {raw}")


def normalize_model_size(raw: str) -> str:
    token = str(raw).strip().lower().replace(" ", "")
    token = token.replace("gb", "b")
    token = token.replace("g", "") if token.endswith("g") else token
    if token in {"0.6", "06", "0_6b", "0-6b"}:
        token = "0.6b"
    if token in {"1.7", "17", "1_7b", "1-7b"}:
        token = "1.7b"
    if token not in {"0.6b", "1.7b"}:
        return "0.6b"
    return token


def resolve_model_id(mode: str, model_size: str, explicit_model: str) -> Tuple[str, str]:
    if explicit_model.strip():
        return explicit_model.strip(), model_size

    size = normalize_model_size(model_size)
    if mode == "voice_design":
        # Current released VoiceDesign checkpoint is 1.7B.
        size = "1.7b"

    model_by_size = MODEL_MAP.get(mode)
    if not model_by_size:
        raise ValueError(f"model map not found for mode={mode}")

    if size not in model_by_size:
        size = sorted(model_by_size.keys())[0]

    return model_by_size[size], size


def read_text_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"text file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"text file is empty: {path}")
    return text


def read_ref_text(args: argparse.Namespace) -> str:
    if args.ref_text_file.strip():
        return read_text_file(Path(args.ref_text_file).expanduser().resolve())
    return args.ref_text.strip()


def load_primary_text(args: argparse.Namespace) -> Tuple[str, Optional[Path]]:
    if args.text.strip():
        return args.text.strip(), None
    if args.input.strip():
        input_path = Path(args.input).expanduser().resolve()
        return read_text_file(input_path), input_path
    raise ValueError("text input is required: set --text or --input")


def load_script_text(args: argparse.Namespace) -> Tuple[str, Path]:
    script_raw = args.script.strip() or args.input.strip()
    if not script_raw:
        raise ValueError("script mode requires --script or --input")
    script_path = Path(script_raw).expanduser().resolve()
    return read_text_file(script_path), script_path


def clean_script_content(text: str) -> str:
    lines: List[str] = []
    in_code_block = False
    for raw in text.splitlines():
        line = raw.rstrip()
        striped = line.strip()

        if striped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not striped:
            lines.append("")
            continue
        if striped.startswith("#"):
            continue
        if striped in {"---", "***", "___"}:
            continue

        striped = re.sub(r"^[-*+]\s+", "", striped)
        striped = re.sub(r"^\d+\.\s+", "", striped)
        lines.append(striped)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def split_script_chunks(text: str, max_chars: int) -> List[str]:
    normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n") if p.strip()]
    sentence_sep = re.compile(r"(?<=[.!?。！？])\s+")

    chunks: List[str] = []
    current = ""

    def push(part: str) -> None:
        nonlocal current
        if not part:
            return
        if not current:
            current = part
            return
        candidate = f"{current} {part}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = part

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            push(paragraph)
            continue

        pieces = [s.strip() for s in sentence_sep.split(paragraph) if s.strip()]
        if not pieces:
            pieces = [paragraph]

        for piece in pieces:
            if len(piece) <= max_chars:
                push(piece)
                continue
            for idx in range(0, len(piece), max_chars):
                push(piece[idx : idx + max_chars].strip())

    if current:
        chunks.append(current)
    return chunks


def pick_device(raw: str) -> str:
    value = str(raw).strip().lower()
    if value and value != "auto":
        return raw

    if torch.cuda.is_available():
        return "cuda:0"
    if torch.backends.mps.is_available():
        return "mps"
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
        is_bf16_supported = False
        try:
            is_bf16_supported = bool(torch.cuda.is_bf16_supported())
        except Exception:
            is_bf16_supported = False
        return torch.bfloat16 if is_bf16_supported else torch.float16
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


def build_attempts(device_raw: str, dtype_raw: str) -> List[Tuple[str, torch.dtype]]:
    primary_device = pick_device(device_raw)
    primary_dtype = pick_dtype(dtype_raw, primary_device)
    attempts: List[Tuple[str, torch.dtype]] = [(primary_device, primary_dtype)]

    if primary_device.startswith("cuda") and primary_dtype != torch.float16:
        attempts.append((primary_device, torch.float16))

    if primary_device != "cpu":
        attempts.append(("cpu", torch.float32))

    deduped: List[Tuple[str, torch.dtype]] = []
    seen = set()
    for item in attempts:
        key = (item[0], dtype_name(item[1]))
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    return deduped


def build_generation_kwargs(args: argparse.Namespace) -> Dict[str, object]:
    kwargs: Dict[str, object] = {"max_new_tokens": args.max_new_tokens}
    if args.temperature is not None:
        kwargs["temperature"] = args.temperature
    if args.top_p is not None:
        kwargs["top_p"] = args.top_p
    if args.top_k is not None:
        kwargs["top_k"] = args.top_k
    return kwargs


def choose_supported_value(
    requested: str,
    supported: Optional[Sequence[str]],
    fallback: str,
    strict: bool,
    value_name: str,
) -> str:
    req = requested.strip()
    if not req:
        return fallback

    if not supported:
        return req

    low_map = {str(item).strip().lower(): str(item) for item in supported}
    matched = low_map.get(req.lower())
    if matched:
        return matched

    if strict:
        raise ValueError(f"unsupported {value_name}: {requested}; supported={sorted(low_map.values())}")

    if req.lower() == "auto" and any(k == "auto" for k in low_map):
        return low_map["auto"]

    return fallback


def model_cleanup(device: str) -> None:
    gc.collect()
    if device == "mps" and hasattr(torch, "mps"):
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
    if device.startswith("cuda") and torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


def ensure_output_path(mode: str, output_raw: str) -> Path:
    if output_raw.strip():
        output = Path(output_raw).expanduser().resolve()
    else:
        stamp = int(time.time())
        output = Path.cwd() / f"qwen3_tts_{mode}_{stamp}.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def synthesize_custom_voice(
    model: Qwen3TTSModel,
    text: str,
    language: str,
    speaker: str,
    instruct: str,
    strict_speaker: bool,
    strict_language: bool,
    kwargs: Dict[str, object],
) -> Tuple[np.ndarray, int, Dict[str, str]]:
    supported_speakers = model.get_supported_speakers()
    supported_languages = model.get_supported_languages()

    resolved_speaker = choose_supported_value(
        requested=speaker,
        supported=supported_speakers,
        fallback=(supported_speakers[0] if supported_speakers else speaker),
        strict=strict_speaker,
        value_name="speaker",
    )
    resolved_language = choose_supported_value(
        requested=language,
        supported=supported_languages,
        fallback=("Auto" if language.strip() else "Auto"),
        strict=strict_language,
        value_name="language",
    )

    wavs, sr = model.generate_custom_voice(
        text=text,
        language=resolved_language,
        speaker=resolved_speaker,
        instruct=instruct.strip() or None,
        **kwargs,
    )
    if not wavs:
        raise RuntimeError("custom voice returned empty audio")

    return wavs[0], int(sr), {
        "resolvedSpeaker": resolved_speaker,
        "resolvedLanguage": resolved_language,
    }


def synthesize_voice_design(
    model: Qwen3TTSModel,
    text: str,
    language: str,
    instruct: str,
    strict_language: bool,
    kwargs: Dict[str, object],
) -> Tuple[np.ndarray, int, Dict[str, str]]:
    if not instruct.strip():
        raise ValueError("voice_design requires --instruct")

    supported_languages = model.get_supported_languages()
    resolved_language = choose_supported_value(
        requested=language,
        supported=supported_languages,
        fallback="Auto",
        strict=strict_language,
        value_name="language",
    )

    wavs, sr = model.generate_voice_design(
        text=text,
        language=resolved_language,
        instruct=instruct,
        **kwargs,
    )
    if not wavs:
        raise RuntimeError("voice design returned empty audio")

    return wavs[0], int(sr), {
        "resolvedLanguage": resolved_language,
    }


def synthesize_voice_clone(
    model: Qwen3TTSModel,
    text: str,
    language: str,
    ref_audio: str,
    ref_text: str,
    x_vector_only_mode: bool,
    strict_language: bool,
    kwargs: Dict[str, object],
) -> Tuple[np.ndarray, int, Dict[str, str]]:
    ref_audio_path = Path(ref_audio).expanduser().resolve()
    if not ref_audio_path.exists():
        raise FileNotFoundError(f"ref audio not found: {ref_audio_path}")

    if not x_vector_only_mode and not ref_text.strip():
        raise ValueError("voice_clone requires --ref-text or --ref-text-file unless --x-vector-only-mode")

    supported_languages = model.get_supported_languages()
    resolved_language = choose_supported_value(
        requested=language,
        supported=supported_languages,
        fallback="Auto",
        strict=strict_language,
        value_name="language",
    )

    wavs, sr = model.generate_voice_clone(
        text=text,
        language=resolved_language,
        ref_audio=str(ref_audio_path),
        ref_text=(ref_text.strip() or None),
        x_vector_only_mode=x_vector_only_mode,
        **kwargs,
    )
    if not wavs:
        raise RuntimeError("voice clone returned empty audio")

    return wavs[0], int(sr), {
        "resolvedLanguage": resolved_language,
        "refAudio": str(ref_audio_path),
        "xVectorOnlyMode": str(bool(x_vector_only_mode)).lower(),
    }


def synthesize_by_mode(
    mode: str,
    model: Qwen3TTSModel,
    text: str,
    args: argparse.Namespace,
    kwargs: Dict[str, object],
    clone_ref_text: str,
) -> Tuple[np.ndarray, int, Dict[str, str]]:
    if mode == "custom_voice":
        return synthesize_custom_voice(
            model=model,
            text=text,
            language=args.language,
            speaker=args.speaker,
            instruct=args.instruct,
            strict_speaker=args.strict_speaker,
            strict_language=args.strict_language,
            kwargs=kwargs,
        )
    if mode == "voice_design":
        return synthesize_voice_design(
            model=model,
            text=text,
            language=args.language,
            instruct=args.instruct,
            strict_language=args.strict_language,
            kwargs=kwargs,
        )
    if mode == "voice_clone":
        return synthesize_voice_clone(
            model=model,
            text=text,
            language=args.language,
            ref_audio=args.ref_audio,
            ref_text=clone_ref_text,
            x_vector_only_mode=args.x_vector_only_mode,
            strict_language=args.strict_language,
            kwargs=kwargs,
        )
    raise ValueError(f"unsupported synthesis mode: {mode}")


def synthesize_script(
    model: Qwen3TTSModel,
    script_text: str,
    script_mode: str,
    args: argparse.Namespace,
    kwargs: Dict[str, object],
    clone_ref_text: str,
) -> Tuple[np.ndarray, int, Dict[str, str]]:
    cleaned = clean_script_content(script_text)
    chunks = split_script_chunks(cleaned, max(80, int(args.split_max_chars)))
    if not chunks:
        raise ValueError("script has no readable lines after cleanup")

    merged: List[np.ndarray] = []
    out_sr: Optional[int] = None

    for idx, chunk in enumerate(chunks):
        wav, sr, _ = synthesize_by_mode(
            mode=script_mode,
            model=model,
            text=chunk,
            args=args,
            kwargs=kwargs,
            clone_ref_text=clone_ref_text,
        )
        if out_sr is None:
            out_sr = sr
        if sr != out_sr:
            raise RuntimeError(f"sample rate mismatch in script synthesis: {out_sr} vs {sr}")
        merged.append(wav.astype(np.float32))

        if idx < len(chunks) - 1 and args.pause_sec > 0:
            silence = np.zeros(int(args.pause_sec * out_sr), dtype=np.float32)
            merged.append(silence)

    if out_sr is None:
        raise RuntimeError("script synthesis produced no output")

    combined = np.concatenate(merged) if len(merged) > 1 else merged[0]
    return combined, out_sr, {
        "scriptChunks": str(len(chunks)),
        "scriptMode": script_mode,
    }


def run_mode(
    mode: str,
    model_id: str,
    model_size: str,
    args: argparse.Namespace,
    output_path: Optional[Path],
    text_payload: Optional[str],
    script_payload: Optional[str],
    input_path: Optional[Path],
    clone_ref_text: str,
) -> Dict[str, object]:
    attempts = build_attempts(args.device, args.dtype)
    kwargs = build_generation_kwargs(args)

    attempt_errors: List[str] = []
    resolved_device = ""
    resolved_dtype = ""
    final_audio: Optional[np.ndarray] = None
    final_sr = 0
    mode_meta: Dict[str, str] = {}
    supported_speakers: Optional[Sequence[str]] = None
    supported_languages: Optional[Sequence[str]] = None

    started = time.time()

    for device, dtype in attempts:
        model: Optional[Qwen3TTSModel] = None
        try:
            load_kwargs: Dict[str, object] = {
                "device_map": device,
                "dtype": dtype,
            }
            if device.startswith("cuda") and not args.no_flash_attn:
                load_kwargs["attn_implementation"] = "flash_attention_2"

            model = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)
            supported_speakers = model.get_supported_speakers()
            supported_languages = model.get_supported_languages()

            if mode == "list_capabilities":
                payload = {
                    "model": model_id,
                    "modelSize": model_size,
                    "resolvedDevice": device,
                    "resolvedDtype": dtype_name(dtype),
                    "supportedSpeakers": list(supported_speakers or []),
                    "supportedLanguages": list(supported_languages or []),
                }
                return payload

            if mode == "script_to_audio":
                script_mode = normalize_mode(args.script_tts_mode)
                if script_mode in {"script_to_audio", "list_capabilities"}:
                    raise ValueError("--script-tts-mode must be custom_voice|voice_design|voice_clone")

                audio, sr, extra = synthesize_script(
                    model=model,
                    script_text=str(script_payload or ""),
                    script_mode=script_mode,
                    args=args,
                    kwargs=kwargs,
                    clone_ref_text=clone_ref_text,
                )
            else:
                audio, sr, extra = synthesize_by_mode(
                    mode=mode,
                    model=model,
                    text=str(text_payload or ""),
                    args=args,
                    kwargs=kwargs,
                    clone_ref_text=clone_ref_text,
                )

            final_audio = audio
            final_sr = sr
            mode_meta = extra
            resolved_device = device
            resolved_dtype = dtype_name(dtype)
            break
        except Exception as exc:  # noqa: BLE001
            attempt_errors.append(f"{device}/{dtype_name(dtype)} -> {exc}")
        finally:
            model = None
            model_cleanup(device)

    if mode == "list_capabilities":
        raise RuntimeError("failed to list capabilities: " + " | ".join(attempt_errors))

    if final_audio is None or final_sr <= 0:
        raise RuntimeError("failed to synthesize audio: " + " | ".join(attempt_errors))

    if output_path is None:
        raise ValueError("output path is required")

    sf.write(str(output_path), final_audio, final_sr)

    duration = float(len(final_audio)) / float(final_sr)
    payload: Dict[str, object] = {
        "mode": mode,
        "model": model_id,
        "modelSize": model_size,
        "resolvedDevice": resolved_device,
        "resolvedDtype": resolved_dtype,
        "language": args.language,
        "speaker": args.speaker,
        "instruct": args.instruct,
        "durationSeconds": duration,
        "elapsedSeconds": time.time() - started,
        "input": str(input_path) if input_path else "<inline>",
        "output": str(output_path),
        "attempts": [f"{d}/{dtype_name(t)}" for d, t in attempts],
        "attemptErrors": attempt_errors,
        "supportedSpeakers": list(supported_speakers or []),
        "supportedLanguages": list(supported_languages or []),
    }
    payload.update(mode_meta)
    return payload


def main() -> int:
    args = parse_args()

    command_mode = normalize_mode(args.command)
    option_mode = normalize_mode(args.mode)
    mode = command_mode if args.command.strip() else option_mode

    if mode == "script_to_audio":
        script_payload, script_path = load_script_text(args)
        text_payload: Optional[str] = None
        input_path = script_path
    elif mode == "list_capabilities":
        script_payload = None
        text_payload = None
        input_path = None
    else:
        text_payload, text_path = load_primary_text(args)
        script_payload = None
        input_path = text_path

    clone_ref_text = read_ref_text(args)

    model_mode = mode
    if mode == "script_to_audio":
        model_mode = normalize_mode(args.script_tts_mode)
    if mode == "list_capabilities":
        model_mode = "custom_voice"

    model_id, resolved_model_size = resolve_model_id(
        mode=model_mode,
        model_size=args.model_size,
        explicit_model=args.model,
    )

    output_path: Optional[Path] = None
    if mode != "list_capabilities":
        output_path = ensure_output_path(mode, args.output)

    payload = run_mode(
        mode=mode,
        model_id=model_id,
        model_size=resolved_model_size,
        args=args,
        output_path=output_path,
        text_payload=text_payload,
        script_payload=script_payload,
        input_path=input_path,
        clone_ref_text=clone_ref_text,
    )

    if args.meta_out.strip():
        meta_path = Path(args.meta_out).expanduser().resolve()
    elif output_path is not None:
        meta_path = output_path.with_suffix(".qwen3.json")
    else:
        meta_path = Path.cwd() / "qwen3_tts_capabilities.json"

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if mode == "list_capabilities":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"qwen3-tts output: {output_path}")
    print(f"qwen3-tts meta: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
