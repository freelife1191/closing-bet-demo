#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vertex AI 인증 환경 점검 스크립트."""

import os
import sys
from pathlib import Path

env_path = Path(".env").resolve()
print(f"Loading .env from: {env_path}")

from dotenv import load_dotenv

load_dotenv(env_path)


def _mask(value: str | None, keep: int = 6) -> str:
    if not value:
        return "(unset)"
    return value[:keep] + "..." if len(value) > keep else value


print(
    "GOOGLE_GENAI_USE_VERTEXAI :",
    os.getenv("GOOGLE_GENAI_USE_VERTEXAI"),
)
print("GOOGLE_CLOUD_PROJECT     :", os.getenv("GOOGLE_CLOUD_PROJECT"))
print("GOOGLE_CLOUD_LOCATION    :", os.getenv("GOOGLE_CLOUD_LOCATION"))
print(
    "GOOGLE_APPLICATION_CREDENTIALS:",
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
)

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if cred_path:
    p = Path(cred_path)
    print(f"  → exists={p.exists()}, size={p.stat().st_size if p.exists() else 'N/A'}")

try:
    from google import genai  # noqa: F401

    print("google.genai imported successfully.")
except ImportError as e:
    print(f"Failed to import google.genai: {e}")

# 실제 클라이언트 생성까지 시도
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from engine.genai_client import build_genai_client

    client = build_genai_client()
    print(f"Client built OK: {type(client).__name__}")
except Exception as e:
    print(f"Client build failed: {e}")
