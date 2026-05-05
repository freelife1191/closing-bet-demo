#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ambiguous_hold 케이스에서 Z.ai 응답이 어떻게 나오는지 직접 캡처."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from openai import OpenAI  # noqa: E402

from engine.vcp_ai_analyzer_helpers import (  # noqa: E402
    build_vcp_prompt,
    is_low_quality_recommendation,
    is_prompt_echo_response,
    parse_json_response,
)

CASE = {
    "ticker": "000660",
    "name": "SK하이닉스",
    "current_price": 132_000,
    "score": 55,
    "vcp_score": 51,
    "contraction_ratio": 0.95,
    "foreign_5d": 800_000,
    "inst_5d": -550_000,
    "foreign_1d": -120_000,
    "inst_1d": 230_000,
}


SYSTEM_PROMPT = (
    "당신은 한국 주식 기술적 분석가입니다. "
    "반드시 JSON 객체 1개만 출력하고 코드블록/설명문/마크다운을 금지합니다. "
    "JSON 외 텍스트를 단 한 글자도 출력하지 말고, 반드시 '{'로 시작해 '}'로 끝내십시오. "
    "reason은 반드시 한국어로 상세하게 작성하십시오. "
    "reason은 최소 2문장, 최소 90자 이상이어야 합니다. "
    "가능하면 아래 섹션 구조를 포함하십시오: "
    "[핵심 투자 포인트], [리스크 요인], [종합 의견]."
)


def call(client: OpenAI, model: str, prompt: str, temperature: float, max_tokens: int = 1100, prefill: bool = True) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    if prefill:
        messages.append({"role": "assistant", "content": '{"action":"'})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        timeout=120,
    )
    choice = resp.choices[0]
    msg = choice.message
    return {
        "content": (getattr(msg, "content", None) or "").strip(),
        "reasoning_content": (getattr(msg, "reasoning_content", None) or "").strip(),
        "finish_reason": getattr(choice, "finish_reason", None),
        "usage": getattr(resp, "usage", None),
    }


def main() -> int:
    client = OpenAI(
        api_key=os.environ["ZAI_API_KEY"],
        base_url="https://api.z.ai/api/paas/v4",
    )
    prompt = build_vcp_prompt(CASE["name"], CASE)

    model = "glm-4.6V-Flash"
    for label, temp, prefill, max_tok in (
        ("prefill@0.0", 0.0, True, 1100),
        ("prefill@0.3", 0.3, True, 1100),
        ("prefill@0.7", 0.7, True, 1100),
        ("noprefill@0.0", 0.0, False, 1100),
        ("noprefill@0.3", 0.3, False, 1100),
        ("noprefill@0.7", 0.7, False, 1100),
        ("prefill_big@0.0", 0.0, True, 2000),
        ("prefill_big@0.3", 0.3, True, 2000),
    ):
        try:
            out = call(client, model, prompt, temp, max_tokens=max_tok, prefill=prefill)
        except Exception as exc:
            print(f"[{label}] EXC {type(exc).__name__}: {str(exc)[:120]}")
            continue
        content = out["content"]
        rc = out["reasoning_content"]
        finish = out["finish_reason"]
        # 본문 우선, 비면 reasoning_content
        text = content if content else rc
        cand = text if text.lstrip().startswith("{") else ('{"action":"' + text if prefill else text)
        rec = parse_json_response(cand)
        echo = is_prompt_echo_response(text)
        quality_ok = rec is not None and not is_low_quality_recommendation(rec)
        print(
            f"[{label}] finish={finish} content_len={len(content)} reasoning_len={len(rc)} "
            f"echo={echo} parsed={rec is not None} quality_ok={quality_ok} "
            f"reason_len={len(str((rec or {}).get('reason') or ''))} "
            f"action={rec and rec.get('action')!r}"
        )
        if not quality_ok and (content or rc):
            preview = (content or rc)[:200].replace("\n", " ")
            print(f"    preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
