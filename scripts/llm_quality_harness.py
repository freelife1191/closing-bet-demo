#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Quality Harness — 실제 LLM 호출로 회귀/품질 검증.

대상:
- VCP analyze_stock (Gemini Vertex + GPT 병렬, 5 케이스 × 3회)
- Perplexity 단독 (3 케이스 × 2회)
- 챗봇 response_flow 스트리밍 (3 시나리오 × 2회)

사용:
    python scripts/llm_quality_harness.py [--report PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import config as app_config_module  # noqa: E402,F401
from engine import config as engine_config_module  # noqa: E402,F401
from engine.config import app_config  # noqa: E402
from engine.vcp_ai_analyzer import VCPMultiAIAnalyzer  # noqa: E402
from engine.vcp_ai_analyzer_helpers import (  # noqa: E402
    build_perplexity_request,
    is_low_quality_recommendation,
)
from engine.genai_client import build_genai_client, vertex_configured  # noqa: E402

import httpx  # noqa: E402

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("llm_quality_harness")
logger.setLevel(logging.INFO)


@dataclass
class CallResult:
    case: str
    provider: str
    iteration: int
    ok: bool
    latency_s: float
    quality_pass: bool
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ---------- Test fixtures (VCP stock_data) ----------

VCP_CASES: list[dict[str, Any]] = [
    {
        "_case_id": "strong_buy",
        "ticker": "005930",
        "name": "삼성전자",
        "current_price": 78_500,
        "score": 92,
        "vcp_score": 88,
        "contraction_ratio": 0.62,
        "foreign_5d": 4_200_000,
        "inst_5d": 1_800_000,
        "foreign_1d": 1_500_000,
        "inst_1d": 720_000,
    },
    {
        "_case_id": "clear_sell",
        "ticker": "035420",
        "name": "NAVER",
        "current_price": 175_000,
        "score": 28,
        "vcp_score": 22,
        "contraction_ratio": 1.35,
        "foreign_5d": -2_300_000,
        "inst_5d": -780_000,
        "foreign_1d": -650_000,
        "inst_1d": -310_000,
    },
    {
        "_case_id": "ambiguous_hold",
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
    },
    {
        "_case_id": "missing_data",
        "ticker": "207940",
        "name": "삼성바이오로직스",
        "current_price": 920_000,
        "score": 60,
        "vcp_score": "N/A",
        "contraction_ratio": "N/A",
        "foreign_5d": "N/A",
        "inst_5d": "N/A",
        "foreign_1d": "N/A",
        "inst_1d": "N/A",
    },
    {
        "_case_id": "edge_low_volume",
        "ticker": "068270",
        "name": "셀트리온",
        "current_price": 178_000,
        "score": 47,
        "vcp_score": 65,
        "contraction_ratio": 0.81,
        "foreign_5d": 50_000,
        "inst_5d": 12_000,
        "foreign_1d": -3_000,
        "inst_1d": 8_000,
    },
]

PERPLEXITY_CASES = VCP_CASES[:3]

CHATBOT_CASES: list[dict[str, str]] = [
    {
        "_case_id": "factual_question",
        "prompt": "최근 한국 코스피 시장에서 외국인 수급이 시장에 어떤 영향을 미치는지 2문장으로 설명해 주세요.",
    },
    {
        "_case_id": "reasoning_format",
        "prompt": (
            "다음 질문에 답하되 응답을 정확히 두 섹션으로 나눠 주세요. "
            "첫 섹션 머리말은 '[추론 과정]'이고 두 번째는 '[답변]'입니다. "
            "질문: VCP(Volatility Contraction Pattern)이 매수 신호로 작동하는 핵심 조건 두 가지는?"
        ),
    },
    {
        "_case_id": "edge_short",
        "prompt": "안녕하세요라고 한 줄로만 답해주세요.",
    },
]


# ---------- Quality assertions ----------


_RULE_BASED_REASON_MARKERS = ("VCP 점수", "수축비율", "이 신호를 종합해 현재 판단은")


def _looks_like_rule_based(rec: dict[str, Any]) -> bool:
    reason = str(rec.get("reason") or "")
    return all(marker in reason for marker in _RULE_BASED_REASON_MARKERS)


def quality_check_vcp(rec: dict[str, Any] | None) -> tuple[bool, str]:
    if rec is None:
        return False, "no_recommendation"
    if is_low_quality_recommendation(rec):
        return False, f"low_quality(action={rec.get('action')!r}, conf={rec.get('confidence')}, reason_len={len(str(rec.get('reason') or ''))})"
    if rec.get("action") not in {"BUY", "SELL", "HOLD"}:
        return False, f"action_invalid:{rec.get('action')!r}"
    try:
        c = int(rec.get("confidence"))
        if not (0 <= c <= 100):
            return False, f"confidence_oob:{c}"
    except Exception:
        return False, "confidence_unparseable"
    reason = str(rec.get("reason") or "")
    if len(reason) < 60:
        return False, f"reason_too_short:{len(reason)}"
    if _looks_like_rule_based(rec):
        return False, "rule_based_fallback (실제 LLM 응답 아님)"
    return True, "ok"


# ---------- Runners ----------


async def _run_direct(
    coro_fn: Callable[[str, dict[str, Any], str | None], Any],
    case: dict[str, Any],
    iteration: int,
    provider: str,
) -> CallResult:
    case_id = case["_case_id"]
    t0 = time.time()
    err: str | None = None
    rec: dict[str, Any] | None = None
    try:
        rec = await coro_fn(case["name"], case, None)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("[%s] %s iter %d 실패: %s", provider, case_id, iteration, err)
    latency = time.time() - t0
    ok_quality, q_reason = quality_check_vcp(rec)
    return CallResult(
        case=case_id,
        provider=provider,
        iteration=iteration,
        ok=rec is not None and err is None,
        latency_s=latency,
        quality_pass=ok_quality,
        detail={
            "quality_reason": q_reason,
            "action": (rec or {}).get("action"),
            "confidence": (rec or {}).get("confidence"),
            "reason_len": len(str((rec or {}).get("reason") or "")),
        },
        error=err,
    )


async def run_gemini_iteration(analyzer: VCPMultiAIAnalyzer, case: dict[str, Any], i: int) -> CallResult:
    return await _run_direct(analyzer._analyze_with_gemini, case, i, "gemini")


async def run_gpt_iteration(analyzer: VCPMultiAIAnalyzer, case: dict[str, Any], i: int) -> CallResult:
    return await _run_direct(analyzer._analyze_with_gpt, case, i, "gpt")


async def run_zai_iteration(analyzer: VCPMultiAIAnalyzer, case: dict[str, Any], i: int) -> CallResult:
    # 각 호출 사이 세션 비활성화 상태를 초기화해서 진짜 호출이 일어나도록 한다.
    setattr(analyzer, "zai_disabled_reason", "")
    return await _run_direct(analyzer._analyze_with_zai, case, i, "zai")


async def perplexity_availability_probe() -> tuple[bool, str | None]:
    """Perplexity API 접근성 확인. 401/429이면 사용 불가."""
    api_key = app_config.PERPLEXITY_API_KEY
    if not api_key:
        return False, "PERPLEXITY_API_KEY missing"
    url, headers, payload = build_perplexity_request(
        prompt="ping. JSON으로만 응답하세요. {\"action\":\"HOLD\",\"confidence\":50,\"reason\":\"test\"}",
        api_key=api_key,
        model=app_config.VCP_PERPLEXITY_MODEL,
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            return True, None
        snippet = (r.text or "")[:160]
        return False, f"HTTP {r.status_code}: {snippet}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def run_perplexity_iteration(
    analyzer: VCPMultiAIAnalyzer,
    case: dict[str, Any],
    iteration: int,
) -> CallResult:
    """Perplexity만 단독으로 호출(분석기 fallback 우회)."""
    case_id = case["_case_id"]
    api_key = app_config.PERPLEXITY_API_KEY
    prompt = analyzer._build_vcp_prompt(case["name"], case)
    url, headers, payload = build_perplexity_request(
        prompt=prompt,
        api_key=api_key,
        model=app_config.VCP_PERPLEXITY_MODEL,
    )
    t0 = time.time()
    err: str | None = None
    rec: dict[str, Any] | None = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            err = f"HTTP {r.status_code}: {(r.text or '')[:200]}"
        else:
            from engine.vcp_ai_analyzer_helpers import (
                extract_perplexity_response_text,
                parse_json_response,
            )
            text = extract_perplexity_response_text(r.json()) or ""
            rec = parse_json_response(text)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
    latency = time.time() - t0
    ok_quality, q_reason = quality_check_vcp(rec)
    return CallResult(
        case=case_id,
        provider="perplexity",
        iteration=iteration,
        ok=rec is not None and err is None,
        latency_s=latency,
        quality_pass=ok_quality,
        detail={
            "quality_reason": q_reason,
            "action": (rec or {}).get("action"),
            "confidence": (rec or {}).get("confidence"),
            "reason_len": len(str((rec or {}).get("reason") or "")),
        },
        error=err,
    )


def run_chatbot_iteration(
    client: Any,
    model: str,
    case: dict[str, str],
    iteration: int,
) -> CallResult:
    case_id = case["_case_id"]
    t0 = time.time()
    err: str | None = None
    text_parts: list[str] = []
    try:
        chat = client.chats.create(model=model, history=[])
        stream = chat.send_message_stream(case["prompt"])
        for chunk in stream:
            piece = getattr(chunk, "text", None)
            if isinstance(piece, str) and piece:
                text_parts.append(piece)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        logger.error("[Chatbot] %s iter %d 실패: %s", case_id, iteration, err)
    latency = time.time() - t0
    text = "".join(text_parts).strip()

    quality_pass = bool(text) and err is None
    if case_id == "reasoning_format":
        quality_pass = quality_pass and ("[추론 과정]" in text and "[답변]" in text)
    elif case_id == "edge_short":
        quality_pass = quality_pass and ("안녕" in text)
    else:
        quality_pass = quality_pass and len(text) >= 30

    return CallResult(
        case=case_id,
        provider=f"chatbot:{model}",
        iteration=iteration,
        ok=bool(text) and err is None,
        latency_s=latency,
        quality_pass=quality_pass,
        detail={
            "text_len": len(text),
            "preview": text[:120].replace("\n", " "),
        },
        error=err,
    )


# ---------- Reporting ----------


def summarize(results: list[CallResult]) -> dict[str, Any]:
    by_provider: dict[str, list[CallResult]] = {}
    for r in results:
        by_provider.setdefault(r.provider.split(":")[0], []).append(r)
    summary: dict[str, Any] = {}
    for prov, items in by_provider.items():
        latencies = [r.latency_s for r in items if r.ok]
        summary[prov] = {
            "total": len(items),
            "ok": sum(1 for r in items if r.ok),
            "quality_pass": sum(1 for r in items if r.quality_pass),
            "p50_s": round(statistics.median(latencies), 2) if latencies else None,
            "p95_s": (
                round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2)
                if len(latencies) >= 2
                else (round(latencies[0], 2) if latencies else None)
            ),
            "failures": [
                {
                    "case": r.case,
                    "iteration": r.iteration,
                    "error": r.error,
                    "quality_reason": r.detail.get("quality_reason"),
                }
                for r in items
                if (not r.ok or not r.quality_pass)
            ],
        }
    return summary


def write_report(
    path: Path,
    results: list[CallResult],
    summary: dict[str, Any],
    skipped: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# LLM Quality Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("## Summary\n")
    lines.append("| Provider | OK | Quality | Total | p50(s) | p95(s) |")
    lines.append("|---|---|---|---|---|---|")
    for prov, s in summary.items():
        lines.append(
            f"| {prov} | {s['ok']} | {s['quality_pass']} | {s['total']} | {s['p50_s']} | {s['p95_s']} |"
        )
    lines.append("\n## Failures\n")
    any_fail = False
    for prov, s in summary.items():
        if not s["failures"]:
            continue
        any_fail = True
        lines.append(f"### {prov}")
        for f in s["failures"]:
            lines.append(f"- case=`{f['case']}` iter={f['iteration']} err=`{f['error']}` quality=`{f['quality_reason']}`")
        lines.append("")
    if not any_fail:
        lines.append("(no failures)\n")

    if skipped:
        lines.append("## Skipped (환경 이슈)\n")
        for s in skipped:
            lines.append(f"- {s}")
        lines.append("")

    lines.append("## Raw\n")
    lines.append("```json")
    lines.append(
        json.dumps(
            [
                {
                    "case": r.case,
                    "provider": r.provider,
                    "iter": r.iteration,
                    "ok": r.ok,
                    "quality": r.quality_pass,
                    "lat": round(r.latency_s, 2),
                    "detail": r.detail,
                    "error": r.error,
                }
                for r in results
            ],
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("```\n")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------- Orchestration ----------


async def main_async(report_path: Path, vcp_iters: int, perplexity_iters: int, chatbot_iters: int) -> int:
    if not vertex_configured():
        logger.error("Vertex AI 환경변수가 설정되지 않았습니다.")
        return 2

    analyzer = VCPMultiAIAnalyzer()
    logger.info("Providers=%s second=%s", analyzer.providers, analyzer.second_provider)

    results: list[CallResult] = []
    skipped: list[str] = []

    # Gemini Vertex
    for case in VCP_CASES:
        for i in range(1, vcp_iters + 1):
            r = await run_gemini_iteration(analyzer, case, i)
            results.append(r)
            logger.info(
                "Gemini %s iter%d %s/%s lat=%.1fs",
                case["_case_id"], i,
                "ok" if r.ok else "FAIL",
                "Q" if r.quality_pass else "q!",
                r.latency_s,
            )

    # GPT (Z.ai gpt-5-nano via responses.create)
    for case in VCP_CASES:
        for i in range(1, vcp_iters + 1):
            r = await run_gpt_iteration(analyzer, case, i)
            results.append(r)
            logger.info(
                "GPT %s iter%d %s/%s lat=%.1fs",
                case["_case_id"], i,
                "ok" if r.ok else "FAIL",
                "Q" if r.quality_pass else "q!",
                r.latency_s,
            )

    # Perplexity (직접 호출, 분석기 fallback 우회) — quota probe 후 진행
    pplx_ok, pplx_err = await perplexity_availability_probe()
    if not pplx_ok:
        skipped.append(f"perplexity unavailable: {pplx_err}")
        logger.warning("Perplexity 사용 불가 — 환경 이슈로 스킵: %s", pplx_err)
    else:
        for case in PERPLEXITY_CASES:
            for i in range(1, perplexity_iters + 1):
                r = await run_perplexity_iteration(analyzer, case, i)
                results.append(r)
                logger.info(
                    "Perplexity %s iter%d %s/%s lat=%.1fs",
                    case["_case_id"], i,
                    "ok" if r.ok else "FAIL",
                    "Q" if r.quality_pass else "q!",
                    r.latency_s,
                )

    # Z.ai (GLM)
    for case in PERPLEXITY_CASES:
        for i in range(1, perplexity_iters + 1):
            r = await run_zai_iteration(analyzer, case, i)
            results.append(r)
            logger.info(
                "Z.ai %s iter%d %s/%s lat=%.1fs",
                case["_case_id"], i,
                "ok" if r.ok else "FAIL",
                "Q" if r.quality_pass else "q!",
                r.latency_s,
            )

    # Chatbot streaming
    chatbot_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    client = build_genai_client()
    for case in CHATBOT_CASES:
        for i in range(1, chatbot_iters + 1):
            r = run_chatbot_iteration(client, chatbot_model, case, i)
            results.append(r)
            logger.info(
                "Chatbot %s iter%d %s/%s lat=%.1fs",
                case["_case_id"], i,
                "ok" if r.ok else "FAIL",
                "Q" if r.quality_pass else "q!",
                r.latency_s,
            )

    summary = summarize(results)
    write_report(report_path, results, summary, skipped=skipped)
    logger.info("Report written: %s", report_path)

    total_calls = len(results)
    ok_calls = sum(1 for r in results if r.ok)
    quality_calls = sum(1 for r in results if r.quality_pass)
    print(f"\n=== Result: ok {ok_calls}/{total_calls}, quality {quality_calls}/{total_calls} ===")
    for prov, s in summary.items():
        print(f"  {prov:14s}  ok={s['ok']:>2}/{s['total']:<2} quality={s['quality_pass']:>2}/{s['total']:<2} p50={s['p50_s']}s p95={s['p95_s']}s")
    if skipped:
        print("\n[Skipped]")
        for line in skipped:
            print(f"  - {line}")

    return 0 if (ok_calls == total_calls and quality_calls == total_calls) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        default=str(ROOT / "docs" / "llm_quality" / f"{datetime.now().strftime('%Y-%m-%d')}.md"),
    )
    parser.add_argument("--vcp-iters", type=int, default=3)
    parser.add_argument("--perplexity-iters", type=int, default=2)
    parser.add_argument("--chatbot-iters", type=int, default=2)
    args = parser.parse_args()

    try:
        return asyncio.run(
            main_async(
                Path(args.report),
                args.vcp_iters,
                args.perplexity_iters,
                args.chatbot_iters,
            )
        )
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
