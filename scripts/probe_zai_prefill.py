#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Z.ai GLM 모델이 assistant prefill로 JSON을 출력하는지 확인."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from openai import OpenAI  # noqa: E402

from engine.config import app_config  # noqa: E402
from engine.vcp_ai_analyzer_helpers import (  # noqa: E402
    build_vcp_prompt,
    is_low_quality_recommendation,
    parse_json_response,
)


def main() -> int:
    client = OpenAI(
        api_key=os.environ["ZAI_API_KEY"],
        base_url="https://api.z.ai/api/paas/v4",
    )
    stock_data = {
        "ticker": "005930",
        "current_price": 78_500,
        "score": 92,
        "vcp_score": 88,
        "contraction_ratio": 0.62,
        "foreign_5d": 4_200_000,
        "inst_5d": 1_800_000,
        "foreign_1d": 1_500_000,
        "inst_1d": 720_000,
    }
    prompt = build_vcp_prompt("삼성전자", stock_data)
    system = (
        "당신은 한국 주식 기술적 분석가입니다. "
        "JSON 객체 1개만 출력하고 코드블록/설명문/마크다운을 금지합니다. "
        "반드시 '{'로 시작해 '}'로 끝내십시오. "
        "필수 키는 action, confidence, reason. "
        "reason은 반드시 한국어 2문장 이상 90자 이상."
    )

    # 5개 다른 종목으로 prefill 신뢰도 검증
    fixtures = [
        ("삼성전자", stock_data),
        ("NAVER", {**stock_data, "score": 28, "foreign_5d": -2_300_000, "inst_5d": -780_000, "foreign_1d": -650_000, "inst_1d": -310_000}),
        ("SK하이닉스", {**stock_data, "score": 55, "foreign_5d": 800_000, "inst_5d": -550_000}),
        ("바이오로직스", {**stock_data, "score": 60, "vcp_score": "N/A"}),
        ("셀트리온", {**stock_data, "score": 47, "foreign_5d": 50_000, "inst_5d": 12_000}),
    ]

    def _call_once(model: str, p: str, max_tokens: int = 1100) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": p},
                {"role": "assistant", "content": '{"action":"'},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            timeout=120,
        )
        return (resp.choices[0].message.content or "").strip()

    model = "glm-4.6V-Flash"
    print(f"========== model={model} (prefill + retry, max_tokens=1100) ==========")
    success = 0
    for name, data in fixtures:
        p = build_vcp_prompt(name, data)
        text = ""
        attempts = 0
        for attempt in range(3):
            attempts = attempt + 1
            try:
                text = _call_once(model, p)
            except Exception as exc:
                print(f"[{name}] attempt {attempts} EXC: {type(exc).__name__}: {str(exc)[:120]}")
                continue
            ok = text.startswith("{") and text.endswith("}") and "reason" in text
            if ok:
                break
        # production parser에 맡겨 첫 JSON object만 추출
        # prefill의 `{"action":"`이 응답에 포함되지 않아 응답이 `BUY",...`로 시작할 수 있어 prefix를 보정
        candidate = text
        if not candidate.lstrip().startswith("{"):
            candidate = '{"action":"' + text
        rec = parse_json_response(candidate)
        ok = rec is not None and not is_low_quality_recommendation(rec)
        if ok:
            success += 1
        print(f"[{name}] attempts={attempts} parsed={rec is not None} quality_ok={ok} action={rec and rec.get('action')!r} reason_len={len(str((rec or {}).get('reason') or ''))}")
    print(f"\nsuccess: {success}/{len(fixtures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
