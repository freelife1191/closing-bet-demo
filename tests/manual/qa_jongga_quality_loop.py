#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실 LLM 호출 기반 종가베팅 품질 측정 하니스.

input  : data/jongga_v2_results_20260505.json (20개 실제 신호)
output : tests/manual/qa_jongga_runs/run_<timestamp>.json
metrics:
  - VCP/수축 비율 언급률 (목표 0%)
  - reason 평균 길이 (목표 ≥ 250)
  - reason < 250자 비율 (목표 ≤ 20%)
  - 5섹션(① 뉴스 ② 거래대금 ③ 수급 ④ 리스크 ⑤ 매매) 포함률 (목표 ≥ 80%)
  - BUY 비율 (정보 메트릭)
사용:
  python tests/manual/qa_jongga_quality_loop.py [--n 3] [--limit 10]
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

from app.routes.kr_market_jongga_reanalysis_helpers import (  # noqa: E402
    _build_jongga_news_analysis_items,
)
from engine.llm_analyzer import LLMAnalyzer  # noqa: E402

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
MIN_REASON_LEN = 250


def load_signals(limit: int) -> list[dict[str, Any]]:
    raw = json.loads(DATA_PATH.read_text())
    sigs = raw.get("signals", [])[:limit]
    cleaned = []
    for s in sigs:
        if s.get("stock_name") and s.get("news_items"):
            cleaned.append(s)
    return cleaned


def vcp_mentioned(text: str) -> bool:
    return any(re.search(p, text or "", re.IGNORECASE) for p in VCP_PATTERNS)


def section_count(text: str) -> int:
    return sum(1 for m in SECTION_MARKERS if m in (text or ""))


async def run_once(items: list[dict[str, Any]], market_status: dict | None) -> dict[str, Any]:
    analyzer = LLMAnalyzer()
    if not analyzer.client:
        raise RuntimeError("LLM client not initialized — check API key/Vertex auth")
    t0 = time.time()
    results = await analyzer.analyze_news_batch_jongga(items, market_status=market_status)
    elapsed = time.time() - t0
    await analyzer.close()
    return {"results": results, "elapsed_sec": round(elapsed, 2)}


def evaluate(run: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, dict] = run["results"]
    if not results:
        return {
            "n": 0,
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
    ap.add_argument("--n", type=int, default=3, help="number of trial runs")
    ap.add_argument("--limit", type=int, default=10, help="max signals per run")
    args = ap.parse_args()

    signals = load_signals(args.limit)
    items = _build_jongga_news_analysis_items(signals)
    print(f"[load] signals={len(signals)} items={len(items)}")
    if not items:
        print("ERROR: no items to analyze (check data path)")
        return 2

    market_status = {"is_bullish": True, "description": "정상", "score": 60}

    runs: list[dict[str, Any]] = []
    for i in range(args.n):
        print(f"\n=== TRIAL {i+1}/{args.n} ===")
        try:
            run = await run_once(items, market_status)
        except Exception as e:
            print(f"  ERROR: {e}")
            runs.append({"trial": i + 1, "error": str(e)})
            continue
        metrics = evaluate(run)
        run["metrics"] = metrics
        run["trial"] = i + 1
        ok, fails = thresholds_pass(metrics)
        run["pass"] = ok
        run["fails"] = fails
        runs.append(run)
        print(f"  elapsed={run['elapsed_sec']}s")
        print(f"  metrics={json.dumps(metrics, ensure_ascii=False)}")
        print(f"  pass={ok}  fails={fails}")
        # Sample reason
        if run["results"]:
            first_key = next(iter(run["results"]))
            sample = str(run["results"][first_key].get("reason", ""))[:200]
            print(f"  sample[{first_key}]: {sample}...")

    out_path = OUT_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "trials": runs,
        "config": {"n": args.n, "limit": args.limit},
        "ts": datetime.utcnow().isoformat(),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n[saved] {out_path}")

    # Aggregate
    passed_trials = [r for r in runs if r.get("pass")]
    print(f"\n=== SUMMARY ===  passed_trials = {len(passed_trials)}/{len(runs)}")
    valid_runs = [r for r in runs if "metrics" in r]
    if valid_runs:
        avg = {
            k: round(statistics.mean(r["metrics"][k] for r in valid_runs), 3)
            for k in ["vcp_mention_rate", "reason_len_avg", "short_reason_rate", "five_section_rate", "buy_rate"]
        }
        print(f"avg metrics: {json.dumps(avg, ensure_ascii=False)}")
    return 0 if len(passed_trials) == len(runs) and runs else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
