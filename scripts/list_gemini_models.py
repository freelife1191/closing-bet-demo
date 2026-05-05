#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vertex AI 환경에서 사용 가능한 Gemini 모델 목록 출력."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from engine.genai_client import build_genai_client, vertex_configured


def list_models() -> None:
    if not vertex_configured():
        print("Error: Vertex AI 설정이 비어있습니다. "
              "GOOGLE_GENAI_USE_VERTEXAI=true / GOOGLE_CLOUD_PROJECT / "
              "GOOGLE_APPLICATION_CREDENTIALS를 .env에 지정하세요.")
        return

    print(f"Project : {os.getenv('GOOGLE_CLOUD_PROJECT')}")
    print(f"Location: {os.getenv('GOOGLE_CLOUD_LOCATION', 'global')}")
    print("Fetching available models from Vertex AI...")

    try:
        client = build_genai_client()
        for m in client.models.list():
            name = getattr(m, "name", "?")
            display = getattr(m, "display_name", "")
            print(f"- {name}  ({display})")
    except Exception as exc:
        print(f"Error listing models: {exc}")


if __name__ == "__main__":
    list_models()
