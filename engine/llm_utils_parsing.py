#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - LLM Utilities (Parsing)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional


logger = logging.getLogger(__name__)


def extract_json_from_response(response_text: str) -> Optional[dict]:
    """
    LLM 응답에서 JSON 추출 (마크다운 코드 블록 처리).
    """

    if not response_text or not response_text.strip():
        return None

    try:
        text = response_text.strip()

        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        return json.loads(text)
    except json.JSONDecodeError as error:
        logger.error(f"JSON parsing failed: {error}")
        return None


def extract_code_block(text: str, language: str = None) -> Optional[str]:
    """
    마크다운 코드 블록 추출.
    """

    if language:
        pattern = rf"```{language}\s*\n(.*?)\n```"
    else:
        pattern = r"```\s*\n(.*?)\n```"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


__all__ = ["extract_json_from_response", "extract_code_block"]
