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
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import requests

LIB_DIR = Path(__file__).resolve().parents[1] / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from kr_text_policy import normalize_kr_text
from language_voice_policy import (
    default_language_selection,
    override_command_flag,
    resolve_speaker,
    resolve_supertonic_language,
    resolve_target_languages,
    translate_legacy_scene_text,
    validate_supertonic_languages,
)
from path_policy import resolve_under_project_root


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def default_qwen_speaker() -> str:
    speaker = os.getenv("QWEN3_TTS_SPEAKER", "Sohee").strip()
    return speaker or "Sohee"


def default_qwen_local_cmd() -> str:
    configured = os.getenv("QWEN_LOCAL_CMD", "").strip()
    if configured:
        return configured

    kit_root = Path(__file__).resolve().parents[2]
    venv_python = kit_root / ".venvs/qwen3-tts/bin/python"
    model_size = os.getenv("QWEN3_TTS_MODEL_SIZE", "0.6b").strip() or "0.6b"
    language = os.getenv("QWEN3_TTS_LANGUAGE", "Auto").strip() or "Auto"
    speaker = default_qwen_speaker()
    device = os.getenv("QWEN3_TTS_DEVICE", "auto").strip() or "auto"
    dtype = os.getenv("QWEN3_TTS_DTYPE", "auto").strip() or "auto"
    style_instruct = os.getenv("QWEN3_TTS_STYLE_INSTRUCT", "").strip()
    style_suffix = ""
    if style_instruct:
        escaped_style = style_instruct.replace('"', '\\"')
        style_suffix = f' --instruct "{escaped_style}"'

    universal_runner = kit_root / "skills/psk-qwen3-tts-universal/scripts/qwen3_tts_runner.py"
    if universal_runner.exists() and venv_python.exists():
        return (
            f"{venv_python} {universal_runner} "
            "--mode custom_voice "
            "--input {text_file} --output {output_file} "
            f"--model-size {model_size} --language {language} --speaker {speaker} "
            f"--device {device} --dtype {dtype}{style_suffix}"
        )

    return ""


def default_supertonic_local_cmd() -> str:
    configured = os.getenv("SUPERTONIC_LOCAL_CMD", "").strip()
    if configured:
        return configured

    supertonic_root = os.getenv("SUPERTONIC_ROOT", "").strip()
    if not supertonic_root:
        return ""

    kit_root = Path(__file__).resolve().parents[2]
    runner_path = kit_root / "skills/psk-supertonic-tts-universal/scripts/supertonic_tts_runner.py"
    if not runner_path.exists():
        return ""

    total_step = os.getenv("SUPERTONIC_TOTAL_STEP", "5").strip() or "5"
    speed = os.getenv("SUPERTONIC_SPEED", "1.05").strip() or "1.05"
    default_lang = os.getenv("SUPERTONIC_LANGUAGE", "ko").strip() or "ko"
    default_speaker = os.getenv("SUPERTONIC_SPEAKER", "Sarah").strip() or "Sarah"
    return (
        f'python3 {runner_path} '
        "--input {text_file} --output {output_file} "
        f"--language {default_lang} --speaker {default_speaker} "
        f'--supertonic-root "{supertonic_root}" '
        f"--total-step {total_step} --speed {speed}"
    )


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
    parser.add_argument("--supertonic-local-cmd", default=default_supertonic_local_cmd())
    parser.add_argument("--supertonic-local-cwd", default=os.getenv("SUPERTONIC_LOCAL_CWD", ""))
    parser.add_argument(
        "--supertonic-local-timeout-sec",
        type=float,
        default=float(os.getenv("SUPERTONIC_LOCAL_TIMEOUT_SEC", "300")),
    )

    # Generic local command bridge for qwen-local or other local engines.
    parser.add_argument("--qwen-local-cmd", default=default_qwen_local_cmd())
    parser.add_argument("--qwen-local-cwd", default=os.getenv("QWEN_LOCAL_CWD", ""))
    parser.add_argument(
        "--qwen-local-timeout-sec",
        type=float,
        default=float(os.getenv("QWEN_LOCAL_TIMEOUT_SEC", "600")),
    )
    parser.add_argument(
        "--require-qwen3",
        action="store_true",
        help="Fail if generated engine is not qwen-local-cmd",
    )
    parser.add_argument(
        "--require-engine",
        default="",
        help="Fail if generated engine is not this engine label",
    )
    return parser.parse_args()


def load_manifest_payload(manifest_path: Path) -> Dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def read_manifest_script_for_language(manifest_data: Dict, language_code: str) -> str:
    scenes = manifest_data.get("scenes", [])
    lines: List[str] = []
    for scene in scenes if isinstance(scenes, list) else []:
        row = scene if isinstance(scene, dict) else {}
        by_lang = row.get("narrationByLang")
        narration = ""
        used_explicit = False
        if isinstance(by_lang, dict):
            narration = str(by_lang.get(language_code, "")).strip()
            used_explicit = bool(narration)
            if not narration and language_code != "ko":
                narration = str(by_lang.get("en", "")).strip()
            if not narration:
                narration = str(by_lang.get("ko", "")).strip()
        if not narration:
            narration = str(row.get("narration", "")).strip()
        if narration and not used_explicit:
            narration = translate_legacy_scene_text(narration, language_code)
        if narration:
            lines.append(narration)

    if not lines:
        raise ValueError(f"No narration found in manifest scenes for language={language_code}")

    return "\n".join(lines)


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
    return resolve_supertonic_language(normalized_language)


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
    speaker: str,
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

    def resolve_voice_style_path(root: Path, configured: str, speaker_name: str) -> str:
        candidate_values: List[str] = []

        configured_value = configured.strip()
        if configured_value:
            candidate_values.append(configured_value)

        speaker_key = speaker_name.strip().lower()
        env_by_speaker = {
            "sarah": os.getenv("SUPERTONIC_SARAH_STYLE", "").strip(),
            "jessica": os.getenv("SUPERTONIC_JESSICA_STYLE", "").strip(),
        }
        env_value = env_by_speaker.get(speaker_key, "")
        if env_value:
            candidate_values.append(env_value)

        speaker_defaults = {
            "sarah": ["assets/voice_styles/F1.json", "assets/voice_styles/F2.json"],
            "jessica": ["assets/voice_styles/F2.json", "assets/voice_styles/F1.json"],
        }
        for candidate in speaker_defaults.get(speaker_key, []):
            candidate_values.append(candidate)

        candidate_values.extend(["assets/voice_styles/F1.json", "assets/voice_styles/M1.json"])

        for value in candidate_values:
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                path = root / value
            if path.exists():
                return str(path)
        return ""

    with tempfile.TemporaryDirectory(prefix="supertonic_local_") as temp_dir:
        save_dir = Path(temp_dir) / "results"
        save_dir.mkdir(parents=True, exist_ok=True)

        resolved_voice_style = resolve_voice_style_path(root_path, voice_style, speaker)
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
        if resolved_voice_style:
            cmd.extend(["--voice-style", resolved_voice_style])

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
    timeout_sec: float,
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
                timeout=max(0.1, float(timeout_sec)),
            )
        except subprocess.TimeoutExpired:
            logger.warning("%s command timed out after %.1fs", label, max(0.1, float(timeout_sec)))
            return False, label
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


def _load_system_voices() -> List[str]:
    """Return available macOS `say` voice names."""
    try:
        completed = subprocess.run(
            ["say", "-v", "?"],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return []
    if completed.returncode != 0:
        return []

    voices: List[str] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        name = stripped.split(maxsplit=1)[0]
        if name and name not in voices:
            voices.append(name)
    return voices


def _select_system_voice(language_code: str, requested_speaker: str, available_voices: Sequence[str]) -> str:
    if not available_voices:
        return ""

    lowered = {voice.lower(): voice for voice in available_voices}
    if requested_speaker.strip().lower() in lowered:
        return lowered[requested_speaker.strip().lower()]

    candidates_map = {
        "ko": ["Yuna", "Sohee", "Jiyoung"],
        "en": ["Serena", "Samantha", "Alex"],
        "ja": ["Ono_Anna", "Kyoko", "Otoya"],
        "zh": ["Vivian", "Tingting", "Meijia", "Sin-ji"],
    }
    language = language_code.split("-", 1)[0].lower()
    candidates = candidates_map.get(language, ["Samantha", "Alex"])
    for name in candidates:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return available_voices[0]


def synthesize_with_system_tts(
    text: str,
    output_path: Path,
    language_code: str,
    requested_speaker: str,
) -> Tuple[bool, str, str]:
    """Generate speech via macOS `say` command."""
    if shutil.which("say") is None:
        return False, "system-tts", ""

    voices = _load_system_voices()
    selected_voice = _select_system_voice(language_code, requested_speaker, voices)
    if not selected_voice:
        return False, "system-tts", ""

    with tempfile.TemporaryDirectory(prefix="system_tts_") as temp_dir:
        aiff_path = Path(temp_dir) / "system_tts.aiff"
        cmd = ["say", "-v", selected_voice, "-o", str(aiff_path), text]
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("system-tts execution failed: %s", exc)
            return False, "system-tts", selected_voice

        if completed.returncode != 0 or not aiff_path.exists():
            logger.warning(
                "system-tts command failed (code=%s): %s",
                completed.returncode,
                completed.stderr.strip(),
            )
            return False, "system-tts", selected_voice

        if not run_ffmpeg_convert_to_wav(aiff_path, output_path):
            logger.warning("system-tts output conversion failed")
            return False, "system-tts", selected_voice

    return True, "system-tts", selected_voice


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


def _copy_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    shutil.copy2(src, dst)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2].parent.resolve()


def _safe_scene_duration(value: object, default: float = 1.0) -> float:
    try:
        duration = float(value)
    except Exception:
        return default
    return max(0.1, duration)


def _build_scene_audio_ranges(manifest_data: Dict, duration_seconds: float) -> List[Dict[str, float | str]]:
    scenes = manifest_data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return []

    normalized_duration = max(0.1, float(duration_seconds or 0.0))
    base_weights: List[float] = []
    scene_ids: List[str] = []
    for idx, scene in enumerate(scenes, start=1):
        row = scene if isinstance(scene, dict) else {}
        scene_ids.append(str(row.get("id") or f"scene-{idx:02d}"))
        base_weights.append(_safe_scene_duration(row.get("durationSec", 1.0)))

    source_total = sum(base_weights)
    if source_total <= 0:
        source_total = float(len(base_weights))
        base_weights = [1.0 for _ in base_weights]

    ranges: List[Dict[str, float | str]] = []
    cursor = 0.0
    for idx, scene_id in enumerate(scene_ids):
        weight = base_weights[idx]
        chunk = normalized_duration * (weight / source_total)
        start_sec = cursor
        end_sec = start_sec + chunk
        ranges.append(
            {
                "sceneId": scene_id,
                "startSec": round(start_sec, 3),
                "endSec": round(end_sec, 3),
            }
        )
        cursor = end_sec

    if ranges:
        ranges[-1]["endSec"] = round(normalized_duration, 3)
    return ranges


def _sanitize_voice_command(command_template: str, language_code: str, speaker: str) -> str:
    command = command_template
    if not command.strip():
        return command
    language_flag_value = "Auto" if normalize_language_tag(language_code) == "multi" else language_code
    command = override_command_flag(command, "--language", language_flag_value)
    command = override_command_flag(command, "--speaker", speaker)
    return command


def main() -> int:
    args = parse_args()

    manifest_path = Path(args.manifest).resolve()
    compatibility_output_path = Path(args.out).resolve()
    dict_path = Path(args.pronunciation_dict).resolve()

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1

    project_root = _project_root()
    compatibility_output_path = resolve_under_project_root(project_root, str(compatibility_output_path))
    compatibility_output_path.parent.mkdir(parents=True, exist_ok=True)

    out_audio_dir = resolve_under_project_root(project_root, "out/audio")
    out_audio_dir.mkdir(parents=True, exist_ok=True)

    manifest_data = load_manifest_payload(manifest_path)
    manifest_language = str(manifest_data.get("language", "")).strip()

    pronunciation_map = load_pronunciation_map(dict_path)

    requested_language = args.language.strip() if args.language.strip() else manifest_language
    if not requested_language.strip():
        requested_language = default_language_selection()
    language_codes = resolve_target_languages(requested_language)

    engine_order_map = {
        "auto": ["qwen-local-cmd", "qwen", "supertonic-local", "google"],
        "auto-local": ["qwen-local-cmd", "supertonic-local"],
        "qwen": ["qwen"],
        "qwen-local-cmd": ["qwen-local-cmd"],
        "supertonic-local": ["supertonic-local"],
        "google": ["google"],
    }
    engine_order = engine_order_map[args.engine]
    required_engine = args.require_engine.strip().lower()
    if args.require_qwen3 and not required_engine:
        required_engine = "qwen-local-cmd"
    allow_silence_fallback = bool(args.allow_silence_fallback and not required_engine)
    if required_engine and args.allow_silence_fallback:
        logger.info("require-engine=%s enabled: silence/system fallback is disabled", required_engine)

    if args.engine == "supertonic-local":
        try:
            validate_supertonic_languages(language_codes)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1

    language_results: List[Dict[str, Optional[str]]] = []
    for language_code in language_codes:
        script_text = read_manifest_script_for_language(manifest_data, language_code)
        script_text = normalize_kr_text(script_text)
        script_text = apply_pronunciation_map(script_text, pronunciation_map)
        script_text = normalize_kr_text(script_text)

        normalized_language = normalize_language_tag(language_code)
        qwen_language_type = resolve_qwen_language_type(args.qwen_language_type, normalized_language)
        google_language_code = resolve_google_language_code(args.google_language_code, normalized_language)
        supertonic_local_language = resolve_supertonic_local_language(normalized_language)
        speaker = resolve_speaker(language_code)
        language_output = out_audio_dir / f"narration.{language_code}.wav"
        system_voice = ""

        success = False
        engine_used = ""
        for engine in engine_order:
            engine_speaker = resolve_speaker(language_code, engine=engine)
            if engine == "supertonic-local":
                if supertonic_local_language not in {"ko", "en"}:
                    ok, used = False, "supertonic-local"
                elif args.supertonic_local_cmd.strip():
                    resolved_command = _sanitize_voice_command(
                        command_template=args.supertonic_local_cmd,
                        language_code=supertonic_local_language,
                        speaker=engine_speaker,
                    )
                    ok, used = synthesize_with_local_command(
                        script_text,
                        language_output,
                        command_template=resolved_command,
                        cwd=args.supertonic_local_cwd,
                        label="supertonic-local",
                        timeout_sec=args.supertonic_local_timeout_sec,
                    )
                else:
                    ok, used = synthesize_with_supertonic_local(
                        script_text,
                        language_output,
                        supertonic_root=args.supertonic_root,
                        language=supertonic_local_language,
                        speaker=engine_speaker,
                        voice_style=args.supertonic_voice_style,
                        total_step=args.supertonic_total_step,
                        speed=args.supertonic_speed,
                    )
            elif engine == "qwen-local-cmd":
                resolved_command = _sanitize_voice_command(
                    command_template=args.qwen_local_cmd,
                    language_code=language_code,
                    speaker=engine_speaker,
                )
                ok, used = synthesize_with_local_command(
                    script_text,
                    language_output,
                    command_template=resolved_command,
                    cwd=args.qwen_local_cwd,
                    label="qwen-local-cmd",
                    timeout_sec=args.qwen_local_timeout_sec,
                )
            elif engine == "qwen":
                ok, used = synthesize_with_qwen(
                    script_text,
                    language_output,
                    api_key=args.qwen_api_key,
                    model=args.qwen_model,
                    voice=args.qwen_voice,
                    language_type=qwen_language_type,
                    base_url=args.qwen_base_url,
                )
            elif engine == "google":
                ok, used = synthesize_with_google(
                    script_text,
                    language_output,
                    api_key=args.google_api_key,
                    base_url=args.google_base_url,
                    language_code=google_language_code,
                    voice_name=args.google_voice_name,
                    speaking_rate=args.google_speaking_rate,
                )
            else:
                ok, used = synthesize_with_supertonic_local(
                    script_text,
                    language_output,
                    supertonic_root=args.supertonic_root,
                    language=supertonic_local_language,
                    speaker=engine_speaker,
                    voice_style=args.supertonic_voice_style,
                    total_step=args.supertonic_total_step,
                    speed=args.supertonic_speed,
                )

            if ok:
                success = True
                engine_used = used
                speaker = engine_speaker
                break

        if not success and allow_silence_fallback:
            ok_system, used_system, selected_system_voice = synthesize_with_system_tts(
                text=script_text,
                output_path=language_output,
                language_code=language_code,
                requested_speaker=speaker,
            )
            if ok_system:
                success = True
                engine_used = used_system
                system_voice = selected_system_voice

        if not success and allow_silence_fallback:
            fallback_seconds = args.silence_seconds if args.silence_seconds > 0 else estimate_seconds(script_text)
            write_silence(language_output, fallback_seconds)
            success = True
            engine_used = "silence"
            logger.warning(
                "Voice generation failed for %s, wrote silence fallback: %.1fs",
                language_code,
                fallback_seconds,
            )

        if not success:
            logger.error("Voice generation failed for language=%s", language_code)
            return 1

        if required_engine and engine_used != required_engine:
            logger.error(
                "Strict engine violation for language=%s (required=%s, engine=%s)",
                language_code,
                required_engine,
                engine_used or "unknown",
            )
            return 1

        duration_seconds = read_wav_duration_seconds(language_output)
        duration_for_ranges = duration_seconds if duration_seconds and duration_seconds > 0 else estimate_seconds(script_text)
        scene_audio_ranges = _build_scene_audio_ranges(manifest_data, duration_for_ranges)
        metadata = {
            "manifest": str(manifest_path),
            "output": str(language_output),
            "speaker": speaker,
            "engine": engine_used,
            "characters": len(script_text),
            "durationSeconds": duration_seconds,
            "manifestLanguage": manifest_language,
            "requestedLanguage": requested_language,
            "languageCode": language_code,
            "languageCodes": language_codes,
            "normalizedLanguage": normalized_language,
            "resolved": {
                "supertonicLocalLanguage": supertonic_local_language,
                "qwenLocalCmdConfigured": bool(args.qwen_local_cmd.strip()),
                "qwenLanguageType": qwen_language_type,
                "googleLanguageCode": google_language_code,
                "speaker": speaker,
                "systemVoice": system_voice,
            },
            "sceneAudioRanges": scene_audio_ranges,
            "sceneAppliedSpeedFactor": 1.0,
            "sceneVoiceEndSec": round(duration_for_ranges, 3),
        }
        language_meta = language_output.with_suffix(".json")
        language_meta.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        language_results.append(
            {
                "languageCode": language_code,
                "output": str(language_output),
                "metadata": str(language_meta),
                "speaker": speaker,
                "engine": engine_used,
                "durationSeconds": duration_seconds,
                "characters": len(script_text),
                "sceneAudioRanges": scene_audio_ranges,
            }
        )

    if not language_results:
        logger.error("No language outputs generated")
        return 1

    first_output = Path(str(language_results[0]["output"]))
    _copy_if_needed(first_output, compatibility_output_path)

    compatibility_metadata_path = compatibility_output_path.with_suffix(".json")
    compatibility_metadata = {
        "manifest": str(manifest_path),
        "output": str(compatibility_output_path),
        "engine": str(language_results[0]["engine"]),
        "speaker": str(language_results[0]["speaker"]),
        "durationSeconds": language_results[0]["durationSeconds"],
        "manifestLanguage": manifest_language,
        "requestedLanguage": requested_language,
        "languageCodes": language_codes,
        "audioExports": [str(row["output"]) for row in language_results],
        "metadataExports": [str(row["metadata"]) for row in language_results],
        "tracks": language_results,
        "sceneAudioRanges": language_results[0].get("sceneAudioRanges", []),
    }
    compatibility_metadata_path.write_text(
        json.dumps(compatibility_metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Voice generated (compat): %s", compatibility_output_path)
    logger.info("Metadata generated (compat): %s", compatibility_metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
