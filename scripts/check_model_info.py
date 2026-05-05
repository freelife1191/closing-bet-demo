#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vertex AI에서 특정 Gemini 모델의 응답 메타데이터를 확인하는 스크립트."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from engine.genai_client import build_genai_client, vertex_configured


def probe(model_name: str) -> None:
    print(f"\n=== {model_name} ===")
    try:
        client = build_genai_client()
        response = client.models.generate_content(
            model=model_name,
            contents="Hello, reply with one word.",
        )
        text = getattr(response, "text", None)
        print(f"Response text       : {text}")
        print(f"Response model_ver  : {getattr(response, 'model_version', None)}")
        print(f"Usage metadata      : {getattr(response, 'usage_metadata', None)}")
    except Exception as e:
        print(f"Error fetching {model_name}: {e}")


if __name__ == "__main__":
    if not vertex_configured():
        print("Error: Vertex AI 설정이 비어있습니다.")
        sys.exit(1)

    for name in (
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-flash",
    ):
        probe(name)
