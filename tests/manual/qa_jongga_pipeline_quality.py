#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
풀 파이프라인 품질 측정 하니스 (Phase3LLMAnalyzer 경유).

매일 종가베팅 생성 파이프라인의 Phase3 입력 shape(StockData/SupplyData/
ScoreDetail 객체 + pre_score/score_details 별도 키)으로 데이터를 만든 뒤
Phase3LLMAnalyzer.execute()를 실제로 호출하여 어댑터+jongga 호출 경로
전체의 LLM 응답 품질을 측정한다.

input  : data/jongga_v2_results_20260505.json (실제 신호 dict)
output : tests/manual/qa_jongga_runs/pipeline_run_<timestamp>.json
metrics:
  - VCP/수축 비율 언급률 (목표 0%)
  - reason 평균 길이 (목표 ≥ 350)
  - reason < 350자 비율 (목표 ≤ 20%)
  - 5섹션 포함률 (목표 ≥ 80%)
  - BUY 비율 (정보)
사용:
  python tests/manual/qa_jongga_pipeline_quality.py [--n 3] [--limit 10]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from engine.llm_analyzer import LLMAnalyzer  # noqa: E402
from engine.models import ScoreDetail, StockData, SupplyData  # noqa: E402
from engine.phases_news_llm import Phase3LLMAnalyzer  # noqa: E402

DATA_PATH = ROOT / "data" / "jongga_v2_results_20260505.json"
OUT_DIR = ROOT / "tests" / "manual" / "qa_jongga_runs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VCP_PATTERNS = [
    r"VCP",
    r"수축\s*비율",
    r"contraction\s*ratio",
    r"변동성\s*수축",
]
SECTION_MARKERS = ["①", "②", "③", "④", "⑤"]
MIN_REASON_LEN = 350


def load_signals(limit: int) -> list[dict[str, Any]]:
    raw = json.loads(DATA_PATH.read_text())
    sigs = raw.get("signals", [])[:limit]
    return [s for s in sigs if s.get("stock_name") and s.get("news_items")]


def _signal_to_phase2_item(sig: dict[str, Any]) -> dict[str, Any]:
    """JSON 신호 dict를 Phase1+2 통과 후 형태로 변환 (어댑터의 역)."""
    stock = StockData(
        code=str(sig.get("stock_code", "")),
        name=str(sig.get("stock_name", "")),
        market=str(sig.get("market", "KOSPI")),
        sector=str(sig.get("sector", "")),
        close=float(sig.get("current_price", 0) or 0),
        change_pct=float(sig.get("change_pct", 0) or 0),
        trading_value=float(sig.get("trading_value", 0) or 0),
        volume=int(sig.get("volume", 0) or 0),
    )

    score_dict = sig.get("score") or {}
    pre_score = ScoreDetail(
        total=float(score_dict.get("total", 0) or 0),
        news=int(score_dict.get("news", 0) or 0),
        volume=int(score_dict.get("volume", 0) or 0),
        chart=int(score_dict.get("chart", 0) or 0),
        candle=int(score_dict.get("candle", 0) or 0),
        timing=int(score_dict.get("timing", 0) or 0),
        supply=int(score_dict.get("supply", 0) or 0),
    )

    score_details = sig.get("score_details") or {}
    foreign = int(score_details.get("foreign_net_buy", 0) or 0)
    inst = int(score_details.get("inst_net_buy", 0) or 0)
    supply_obj = SupplyData(foreign_buy_5d=foreign, inst_buy_5d=inst)

    return {
        "stock": stock,
        "charts": None,
        "supply": supply_obj,
        "pre_score": pre_score,
        "score_details": score_details,
        "temp_grade": sig.get("grade", "C"),
        "vcp": None,
        "news": sig.get("news_items") or [],
    }


def vcp_mentioned(text: str) -> bool:
    return any(re.search(p, text or "", re.IGNORECASE) for p in VCP_PATTERNS)


def section_count(text: str) -> int:
    return sum(1 for m in SECTION_MARKERS if m in (text or ""))


async def run_once(items: list[dict[str, Any]], market_status: dict | None) -> dict[str, Any]:
    analyzer = LLMAnalyzer()
    if not analyzer.client:
        raise RuntimeError("LLM client not initialized — check API key/Vertex auth")
    phase3 = Phase3LLMAnalyzer(analyzer)
    t0 = time.time()
    results = await phase3.execute(items, market_status=market_status)
    elapsed = time.time() - t0
    await analyzer.close()
    return {
        "results": results,
        "elapsed_sec": round(elapsed, 2),
        "phase3_stats": dict(phase3.stats),
    }


def evaluate(run: dict[str, Any], expected_n: int) -> dict[str, Any]:
    results: dict[str, dict] = run["results"]
    if not results:
        return {
            "n": 0,
            "expected_n": expected_n,
            "completion_rate": 0,
            "vcp_mention_rate": 0,
            "reason_len_avg": 0,
            "reason_len_min": 0,
            "reason_len_p50": 0,
            "short_reason_rate": 0,
            "five_section_rate": 0,
            "buy_rate": 0,
        }
    reasons = [(k, str((r or {}).get("reason", "") or "")) for k, r in results.items()]
    actions = [str((r or {}).get("action", "")).upper() for r in results.values()]
    lengths = [len(r) for _, r in reasons]
    vcp_hits = sum(1 for _, r in reasons if vcp_mentioned(r))
    short_hits = sum(1 for L in lengths if L < MIN_REASON_LEN)
    five_section_hits = sum(1 for _, r in reasons if section_count(r) >= 5)
    buy_hits = sum(1 for a in actions if a == "BUY")
    n = len(results)
    return {
        "n": n,
        "expected_n": expected_n,
        "completion_rate": round(n / expected_n, 3) if expected_n else 0,
        "vcp_mention_rate": round(vcp_hits / n, 3),
        "reason_len_avg": round(statistics.mean(lengths), 1),
        "reason_len_min": min(lengths),
        "reason_len_p50": int(statistics.median(lengths)),
        "short_reason_rate": round(short_hits / n, 3),
        "five_section_rate": round(five_section_hits / n, 3),
        "buy_rate": round(buy_hits / n, 3),
    }


def thresholds_pass(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    fails: list[str] = []
    if metrics["completion_rate"] < 0.95:
        fails.append(f"completion_rate={metrics['completion_rate']:.1%} < 95%")
    if metrics["vcp_mention_rate"] > 0.0:
        fails.append(f"vcp_mention_rate={metrics['vcp_mention_rate']:.1%} > 0%")
    if metrics["reason_len_avg"] < MIN_REASON_LEN:
        fails.append(f"reason_len_avg={metrics['reason_len_avg']} < {MIN_REASON_LEN}")
    if metrics["short_reason_rate"] > 0.20:
        fails.append(f"short_reason_rate={metrics['short_reason_rate']:.1%} > 20%")
    if metrics["five_section_rate"] < 0.80:
        fails.append(f"five_section_rate={metrics['five_section_rate']:.1%} < 80%")
    return (len(fails) == 0, fails)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3, help="trial 횟수")
    ap.add_argument("--limit", type=int, default=10, help="trial 당 종목 수")
    args = ap.parse_args()

    signals = load_signals(args.limit)
    items = [_signal_to_phase2_item(s) for s in signals]
    print(f"[load] signals={len(signals)} phase2_items={len(items)}")
    if not items:
        print("ERROR: no items to analyze (check data path)")
        return 2

    market_status = {"is_bullish": True, "description": "정상", "score": 60}

    runs: list[dict[str, Any]] = []
    for i in range(args.n):
        print(f"\n=== TRIAL {i+1}/{args.n} (PIPELINE) ===")
        try:
            run = await run_once(items, market_status)
        except Exception as e:
            print(f"  ERROR: {e}")
            runs.append({"trial": i + 1, "error": str(e)})
            continue
        metrics = evaluate(run, expected_n=len(items))
        run["metrics"] = metrics
        run["trial"] = i + 1
        ok, fails = thresholds_pass(metrics)
        run["pass"] = ok
        run["fails"] = fails
        runs.append(run)
        print(f"  elapsed={run['elapsed_sec']}s  phase3_stats={run['phase3_stats']}")
        print(f"  metrics={json.dumps(metrics, ensure_ascii=False)}")
        print(f"  pass={ok}  fails={fails}")
        if run["results"]:
            first_key = next(iter(run["results"]))
            sample = str(run["results"][first_key].get("reason", ""))[:240]
            print(f"  sample[{first_key}]: {sample}...")

    out_path = OUT_DIR / f"pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "trials": runs,
        "config": {"n": args.n, "limit": args.limit},
        "ts": datetime.utcnow().isoformat(),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n[saved] {out_path}")

    passed_trials = [r for r in runs if r.get("pass")]
    print(f"\n=== SUMMARY ===  passed_trials = {len(passed_trials)}/{len(runs)}")
    valid_runs = [r for r in runs if "metrics" in r]
    if valid_runs:
        avg = {
            k: round(statistics.mean(r["metrics"][k] for r in valid_runs), 3)
            for k in [
                "completion_rate",
                "vcp_mention_rate",
                "reason_len_avg",
                "short_reason_rate",
                "five_section_rate",
                "buy_rate",
            ]
        }
        print(f"avg metrics: {json.dumps(avg, ensure_ascii=False)}")
    return 0 if len(passed_trials) == len(runs) and runs else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
