#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate narration audio from manifest scenes.

Supported engines:
- qwen (default in auto chain)
- qwen-local-cmd
- supertonic-local
- google
"""

import argparse
import base64
import json
import logging
import math
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def default_qwen_local_cmd() -> str:
    configured = os.getenv("QWEN_LOCAL_CMD", "").strip()
    if configured:
        return configured

    project_root = Path(__file__).resolve().parents[2]
    venv_python = project_root / ".venv-qwen3-tts/bin/python"
    model_size = os.getenv("QWEN3_TTS_MODEL_SIZE", "0.6b").strip() or "0.6b"
    language = os.getenv("QWEN3_TTS_LANGUAGE", "Auto").strip() or "Auto"
    speaker = os.getenv("QWEN3_TTS_SPEAKER", "Vivian").strip() or "Vivian"
    device = os.getenv("QWEN3_TTS_DEVICE", "auto").strip() or "auto"
    dtype = os.getenv("QWEN3_TTS_DTYPE", "auto").strip() or "auto"
    style_instruct = os.getenv("QWEN3_TTS_STYLE_INSTRUCT", "").strip()
    style_suffix = ""
    if style_instruct:
        escaped_style = style_instruct.replace('"', '\\"')
        style_suffix = f' --instruct "{escaped_style}"'

    universal_runner = project_root / ".agent/skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py"
    if universal_runner.exists() and venv_python.exists():
        return (
            f"{venv_python} {universal_runner} "
            "--mode custom_voice "
            "--input {text_file} --output {output_file} "
            f"--model-size {model_size} --language {language} --speaker {speaker} "
            f"--device {device} --dtype {dtype}{style_suffix}"
        )

    legacy_runner = project_root / ".agent/skills/psk-qwen3-tts-m1-local/scripts/qwen3_tts_local_runner.py"
    model = os.getenv("QWEN3_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice").strip()
    if legacy_runner.exists() and venv_python.exists():
        return (
            f"{venv_python} {legacy_runner} "
            "--input {text_file} --output {output_file} "
            f"--model {model} --language Auto --speaker Vivian --device auto"
        )

    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate narration wav")
    parser.add_argument("--manifest", default="project/video/manifest.json")
    parser.add_argument("--out", default="project/video/audio/narration.wav")
    parser.add_argument(
        "--engine",
        default="auto",
        choices=[
            "qwen",
            "qwen-local-cmd",
            "supertonic-local",
            "google",
            "auto",
            "auto-local",
        ],
    )
    parser.add_argument(
        "--language",
        default="",
        help="Override manifest language, e.g. ko, en, ja, ko+en, multi",
    )
    parser.add_argument("--pronunciation-dict", default="project/video/pronunciation_dict.json")
    parser.add_argument("--allow-silence-fallback", action="store_true")
    parser.add_argument("--silence-seconds", type=float, default=0.0)

    # Qwen (Alibaba Cloud Model Studio / DashScope)
    parser.add_argument("--qwen-api-key", default=os.getenv("DASHSCOPE_API_KEY", ""))
    parser.add_argument("--qwen-model", default=os.getenv("QWEN_TTS_MODEL", "qwen3-tts-flash"))
    parser.add_argument("--qwen-voice", default=os.getenv("QWEN_TTS_VOICE", "Cherry"))
    parser.add_argument(
        "--qwen-language-type",
        default=os.getenv("QWEN_TTS_LANGUAGE_TYPE", ""),
    )
    parser.add_argument(
        "--qwen-base-url",
        default=os.getenv(
            "QWEN_TTS_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        ),
    )

    # Google Cloud Text-to-Speech
    parser.add_argument("--google-api-key", default=os.getenv("GOOGLE_API_KEY", ""))
    parser.add_argument(
        "--google-base-url",
        default=os.getenv("GOOGLE_TTS_BASE_URL", "https://texttospeech.googleapis.com/v1/text:synthesize"),
    )
    parser.add_argument("--google-language-code", default=os.getenv("GOOGLE_TTS_LANGUAGE_CODE", ""))
    parser.add_argument("--google-voice-name", default=os.getenv("GOOGLE_TTS_VOICE_NAME", ""))
    parser.add_argument("--google-speaking-rate", type=float, default=1.0)

    # Supertone local (ONNX examples from supertonic repo / supertonic_readme.md)
    parser.add_argument("--supertonic-root", default=os.getenv("SUPERTONIC_ROOT", ""))
    parser.add_argument("--supertonic-voice-style", default=os.getenv("SUPERTONIC_VOICE_STYLE", ""))
    parser.add_argument("--supertonic-total-step", type=int, default=int(os.getenv("SUPERTONIC_TOTAL_STEP", "5")))
    parser.add_argument("--supertonic-speed", type=float, default=float(os.getenv("SUPERTONIC_SPEED", "1.05")))

    # Generic local command bridge for qwen-local or other local engines.
    parser.add_argument("--qwen-local-cmd", default=default_qwen_local_cmd())
    parser.add_argument("--qwen-local-cwd", default=os.getenv("QWEN_LOCAL_CWD", ""))
    return parser.parse_args()


def read_manifest_info(manifest_path: Path) -> Tuple[str, str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_language = str(data.get("language", "")).strip()
    scenes = data.get("scenes", [])
    lines: List[str] = []
    for scene in scenes:
        narration = str(scene.get("narration", "")).strip()
        if narration:
            lines.append(narration)

    if not lines:
        raise ValueError("No narration found in manifest scenes")

    return "\n".join(lines), manifest_language


def normalize_language_tag(language: str) -> str:
    normalized = language.lower().replace("_", "-").strip()
    if not normalized:
        return "ko"
    if normalized in {"multi", "multilingual"}:
        return "multi"
    if "+" in normalized or "," in normalized or "/" in normalized:
        return "multi"
    return normalized.split("-", 1)[0]


def resolve_qwen_language_type(configured: str, normalized_language: str) -> str:
    if configured.strip():
        return configured.strip()

    if normalized_language == "multi":
        return "Auto"

    mapping = {
        "ko": "Korean",
        "en": "English",
        "ja": "Japanese",
        "zh": "Chinese",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "ru": "Russian",
        "id": "Indonesian",
        "vi": "Vietnamese",
        "th": "Thai",
    }
    return mapping.get(normalized_language, "Auto")


def resolve_google_language_code(configured: str, normalized_language: str) -> str:
    if configured.strip():
        return configured.strip()

    if normalized_language == "multi":
        # For bilingual scripts, prefer Qwen Auto; keep Korean default for Google fallback.
        return "ko-KR"

    mapping = {
        "ko": "ko-KR",
        "en": "en-US",
        "ja": "ja-JP",
        "zh": "cmn-CN",
        "de": "de-DE",
        "fr": "fr-FR",
        "es": "es-ES",
        "pt": "pt-PT",
        "ru": "ru-RU",
        "it": "it-IT",
    }
    return mapping.get(normalized_language, "en-US")


def resolve_supertonic_local_language(normalized_language: str) -> str:
    if normalized_language == "multi":
        return "ko"
    supported = {"en", "ko", "es", "pt", "fr"}
    if normalized_language in supported:
        return normalized_language
    return "en"


def load_pronunciation_map(dict_path: Path) -> Dict[str, str]:
    if not dict_path.exists():
        return {}

    try:
        data = json.loads(dict_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load pronunciation dictionary: %s", exc)
        return {}


def apply_pronunciation_map(text: str, replacements: Dict[str, str]) -> str:
    updated = text
    for source, target in replacements.items():
        updated = updated.replace(source, target)
    return updated


def split_text_chunks(text: str, max_chars: int) -> List[str]:
    cleaned = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    if len(cleaned) <= max_chars:
        return [cleaned]

    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]
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
            return

        chunks.append(current)
        current = part

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            push(paragraph)
            continue

        sentences = [s.strip() for s in sentence_sep.split(paragraph) if s.strip()]
        if not sentences:
            sentences = [paragraph]

        for sentence in sentences:
            if len(sentence) <= max_chars:
                push(sentence)
                continue

            # Hard split very long sentence.
            for idx in range(0, len(sentence), max_chars):
                piece = sentence[idx : idx + max_chars].strip()
                push(piece)

    if current:
        chunks.append(current)
    return chunks


def run_ffmpeg_convert_to_wav(input_path: Path, wav_path: Path) -> bool:
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-ar",
            "22050",
            "-ac",
            "1",
            str(wav_path),
        ]
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return completed.returncode == 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffmpeg conversion failed: %s", exc)
        return False


def combine_audio_segments(segment_paths: Sequence[Path], output_path: Path) -> bool:
    if not segment_paths:
        return False

    if len(segment_paths) == 1:
        return run_ffmpeg_convert_to_wav(segment_paths[0], output_path)

    cmd = ["ffmpeg", "-y"]
    for path in segment_paths:
        cmd.extend(["-i", str(path)])

    input_labels = "".join(f"[{idx}:a]" for idx, _ in enumerate(segment_paths))
    filter_graph = f"{input_labels}concat=n={len(segment_paths)}:v=0:a=1[aout]"
    cmd.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[aout]",
            "-ar",
            "22050",
            "-ac",
            "1",
            str(output_path),
        ]
    )

    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            logger.warning("ffmpeg concat failed: %s", completed.stderr.strip())
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffmpeg concat exception: %s", exc)
        return False


def download_binary(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
    try:
        response = requests.get(url, headers=headers, timeout=180)
    except requests.RequestException as exc:
        logger.warning("Download failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.warning("Download failed (status=%s): %s", response.status_code, url)
        return None

    return response.content


def synthesize_with_qwen(
    text: str,
    output_path: Path,
    api_key: str,
    model: str,
    voice: str,
    language_type: str,
    base_url: str,
) -> Tuple[bool, str]:
    if not api_key:
        logger.warning("Qwen API key not set (DASHSCOPE_API_KEY)")
        return False, "qwen"

    chunks = split_text_chunks(text, max_chars=550)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with tempfile.TemporaryDirectory(prefix="qwen_tts_") as temp_dir:
        segment_paths: List[Path] = []
        for idx, chunk in enumerate(chunks, start=1):
            payload = {
                "model": model,
                "input": {
                    "text": chunk,
                    "voice": voice,
                    "language_type": language_type,
                },
            }

            try:
                response = requests.post(base_url, headers=headers, json=payload, timeout=240)
            except requests.RequestException as exc:
                logger.warning("Qwen request failed: %s", exc)
                return False, "qwen"

            if response.status_code != 200:
                logger.warning("Qwen request failed (status=%s): %s", response.status_code, response.text[:240])
                return False, "qwen"

            try:
                data = response.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Qwen response JSON parse failed: %s", exc)
                return False, "qwen"

            audio_url = (
                data.get("output", {})
                .get("audio", {})
                .get("url")
            )
            if not audio_url:
                logger.warning("Qwen response missing output.audio.url: %s", data)
                return False, "qwen"

            audio_bytes = download_binary(str(audio_url))
            if not audio_bytes:
                return False, "qwen"

            segment_path = Path(temp_dir) / f"qwen_{idx:03d}.wav"
            segment_path.write_bytes(audio_bytes)
            segment_paths.append(segment_path)

        ok = combine_audio_segments(segment_paths, output_path)
        return (ok, "qwen")


def synthesize_with_google(
    text: str,
    output_path: Path,
    api_key: str,
    base_url: str,
    language_code: str,
    voice_name: str,
    speaking_rate: float,
) -> Tuple[bool, str]:
    if not api_key:
        logger.warning("Google API key not set (GOOGLE_API_KEY)")
        return False, "google"

    chunks = split_text_chunks(text, max_chars=3000)
    endpoint = f"{base_url}?key={api_key}"

    with tempfile.TemporaryDirectory(prefix="google_tts_") as temp_dir:
        segment_paths: List[Path] = []
        for idx, chunk in enumerate(chunks, start=1):
            voice_payload: Dict[str, str] = {"languageCode": language_code}
            if voice_name:
                voice_payload["name"] = voice_name

            payload = {
                "input": {"text": chunk},
                "voice": voice_payload,
                "audioConfig": {
                    "audioEncoding": "LINEAR16",
                    "speakingRate": speaking_rate,
                },
            }

            try:
                response = requests.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )
            except requests.RequestException as exc:
                logger.warning("Google TTS request failed: %s", exc)
                return False, "google"

            if response.status_code != 200:
                logger.warning("Google TTS failed (status=%s): %s", response.status_code, response.text[:240])
                return False, "google"

            try:
                data = response.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google TTS response JSON parse failed: %s", exc)
                return False, "google"

            audio_content = data.get("audioContent")
            if not audio_content:
                logger.warning("Google TTS response missing audioContent: %s", data)
                return False, "google"

            try:
                audio_bytes = base64.b64decode(audio_content)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Google TTS base64 decode failed: %s", exc)
                return False, "google"

            segment_path = Path(temp_dir) / f"google_{idx:03d}.wav"
            segment_path.write_bytes(audio_bytes)
            segment_paths.append(segment_path)

        ok = combine_audio_segments(segment_paths, output_path)
        return (ok, "google")


def synthesize_with_supertonic_local(
    text: str,
    output_path: Path,
    supertonic_root: str,
    language: str,
    voice_style: str,
    total_step: int,
    speed: float,
) -> Tuple[bool, str]:
    if not supertonic_root.strip():
        logger.warning("SUPERTONIC_ROOT is not set for supertonic-local engine")
        return False, "supertonic-local"

    root_path = Path(supertonic_root).resolve()
    example_path = root_path / "example_onnx.py"
    if not example_path.exists():
        logger.warning("supertonic-local example not found: %s", example_path)
        return False, "supertonic-local"

    with tempfile.TemporaryDirectory(prefix="supertonic_local_") as temp_dir:
        save_dir = Path(temp_dir) / "results"
        save_dir.mkdir(parents=True, exist_ok=True)

        cmd: List[str] = [
            "uv",
            "run",
            "example_onnx.py",
            "--text",
            text,
            "--lang",
            language,
            "--save-dir",
            str(save_dir),
            "--n-test",
            "1",
            "--total-step",
            str(max(1, total_step)),
            "--speed",
            str(speed),
        ]
        if voice_style:
            cmd.extend(["--voice-style", voice_style])

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(root_path),
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("supertonic-local execution failed: %s", exc)
            return False, "supertonic-local"

        if completed.returncode != 0:
            logger.warning(
                "supertonic-local command failed (code=%s): %s",
                completed.returncode,
                completed.stderr.strip(),
            )
            return False, "supertonic-local"

        audio_files: List[Path] = []
        for pattern in ("*.wav", "*.mp3", "*.flac", "*.ogg", "*.m4a"):
            audio_files.extend(save_dir.rglob(pattern))

        if not audio_files:
            logger.warning("supertonic-local produced no audio files in %s", save_dir)
            return False, "supertonic-local"

        latest = max(audio_files, key=lambda item: item.stat().st_mtime)
        if not run_ffmpeg_convert_to_wav(latest, output_path):
            logger.warning("supertonic-local output conversion failed: %s", latest)
            return False, "supertonic-local"

        return True, "supertonic-local"


def synthesize_with_local_command(
    text: str,
    output_path: Path,
    command_template: str,
    cwd: str,
    label: str,
) -> Tuple[bool, str]:
    if not command_template.strip():
        logger.warning("%s command template is not set", label)
        return False, label

    with tempfile.TemporaryDirectory(prefix=f"{label}_") as temp_dir:
        text_file = Path(temp_dir) / "input.txt"
        raw_output = Path(temp_dir) / "output.wav"
        text_file.write_text(text, encoding="utf-8")

        safe_text = text.replace('"', '\\"')
        command = command_template.format(
            text_file=str(text_file),
            output_file=str(raw_output),
            text=safe_text,
        )

        run_cwd = cwd.strip() if cwd.strip() else None
        try:
            completed = subprocess.run(
                command,
                cwd=run_cwd,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s command execution failed: %s", label, exc)
            return False, label

        if completed.returncode != 0:
            logger.warning("%s command failed (code=%s): %s", label, completed.returncode, completed.stderr.strip())
            return False, label

        if not raw_output.exists():
            logger.warning("%s command did not produce output file: %s", label, raw_output)
            return False, label

        if not run_ffmpeg_convert_to_wav(raw_output, output_path):
            logger.warning("%s output conversion failed", label)
            return False, label

        return True, label


def write_silence(output_path: Path, seconds: float, sample_rate: int = 22_050) -> None:
    duration = max(seconds, 1.0)
    frame_count = int(sample_rate * duration)
    silence = b"\x00\x00" * frame_count

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


def estimate_seconds(text: str) -> float:
    # Conservative estimate for Korean/English narration pace.
    estimated = len(text) / 8.0
    return max(8.0, math.ceil(estimated))


def read_wav_duration_seconds(path: Path) -> Optional[float]:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            if frame_rate <= 0:
                return None
            return frame_count / frame_rate
    except Exception:
        return None


def main() -> int:
    args = parse_args()

    manifest_path = Path(args.manifest).resolve()
    output_path = Path(args.out).resolve()
    dict_path = Path(args.pronunciation_dict).resolve()

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    script_text, manifest_language = read_manifest_info(manifest_path)
    pronunciation_map = load_pronunciation_map(dict_path)
    script_text = apply_pronunciation_map(script_text, pronunciation_map)

    requested_language = args.language.strip() if args.language.strip() else manifest_language
    if not requested_language.strip():
        requested_language = "ko"
    normalized_language = normalize_language_tag(requested_language)
    qwen_language_type = resolve_qwen_language_type(args.qwen_language_type, normalized_language)
    google_language_code = resolve_google_language_code(args.google_language_code, normalized_language)
    supertonic_local_language = resolve_supertonic_local_language(normalized_language)

    engine_order_map = {
        "auto": ["qwen-local-cmd", "qwen", "supertonic-local", "google"],
        "auto-local": ["qwen-local-cmd", "supertonic-local"],
        "qwen": ["qwen"],
        "qwen-local-cmd": ["qwen-local-cmd"],
        "supertonic-local": ["supertonic-local"],
        "google": ["google"],
    }
    engine_order = engine_order_map[args.engine]

    success = False
    engine_used = ""

    for engine in engine_order:
        if engine == "supertonic-local":
            ok, used = synthesize_with_supertonic_local(
                script_text,
                output_path,
                supertonic_root=args.supertonic_root,
                language=supertonic_local_language,
                voice_style=args.supertonic_voice_style,
                total_step=args.supertonic_total_step,
                speed=args.supertonic_speed,
            )
        elif engine == "qwen-local-cmd":
            ok, used = synthesize_with_local_command(
                script_text,
                output_path,
                command_template=args.qwen_local_cmd,
                cwd=args.qwen_local_cwd,
                label="qwen-local-cmd",
            )
        elif engine == "qwen":
            ok, used = synthesize_with_qwen(
                script_text,
                output_path,
                api_key=args.qwen_api_key,
                model=args.qwen_model,
                voice=args.qwen_voice,
                language_type=qwen_language_type,
                base_url=args.qwen_base_url,
            )
        elif engine == "google":
            ok, used = synthesize_with_google(
                script_text,
                output_path,
                api_key=args.google_api_key,
                base_url=args.google_base_url,
                language_code=google_language_code,
                voice_name=args.google_voice_name,
                speaking_rate=args.google_speaking_rate,
            )
        else:
            ok, used = synthesize_with_supertonic_local(
                script_text,
                output_path,
                supertonic_root=args.supertonic_root,
                language=supertonic_local_language,
                voice_style=args.supertonic_voice_style,
                total_step=args.supertonic_total_step,
                speed=args.supertonic_speed,
            )

        if ok:
            success = True
            engine_used = used
            break

    if not success and args.allow_silence_fallback:
        fallback_seconds = args.silence_seconds if args.silence_seconds > 0 else estimate_seconds(script_text)
        write_silence(output_path, fallback_seconds)
        success = True
        engine_used = "silence"
        logger.warning("Voice generation failed, wrote silence fallback: %.1fs", fallback_seconds)

    if not success:
        logger.error("Voice generation failed for all engines")
        return 1

    duration_seconds = read_wav_duration_seconds(output_path)
    metadata = {
        "manifest": str(manifest_path),
        "output": str(output_path),
        "engine": engine_used,
        "characters": len(script_text),
        "durationSeconds": duration_seconds,
        "manifestLanguage": manifest_language,
        "requestedLanguage": requested_language,
        "normalizedLanguage": normalized_language,
        "resolved": {
            "supertonicLocalLanguage": supertonic_local_language,
            "qwenLocalCmdConfigured": bool(args.qwen_local_cmd.strip()),
            "qwenLanguageType": qwen_language_type,
            "googleLanguageCode": google_language_code,
        },
    }

    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Voice generated: %s", output_path)
    logger.info("Metadata generated: %s", metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
