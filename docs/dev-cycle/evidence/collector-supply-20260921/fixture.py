#!/usr/bin/env python3
"""Scratch-only UI fixture. Real changed parsers, detail service and SQLite; synthetic providers."""
import argparse
import json
import logging
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[4]
assert ROOT.name.startswith("collector-supply-20260921-") and not (ROOT / ".git").exists()
assert os.environ.get("PYTHON_DOTENV_DISABLED") == "1"
assert not (ROOT / ".env").exists()

import pandas as pd
from flask import Flask, jsonify, request
from engine.toss_collector import TossCollector
from engine.toss_collector_metric_parsers import parse_investor_trend
from services import kr_market_stock_detail_service as detail
from services.kr_market_data_cache_sqlite_payload import save_json_payload_to_sqlite

app = Flask("collector-supply-fixture")
logger = logging.getLogger(__name__)
state = {"mode": "zero", "version": 0}
data_dir = ROOT / ".qa-supply" / "data"
data_dir.mkdir(parents=True, exist_ok=True)
log = ROOT / ".qa-supply" / "requests.jsonl"
dates = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
pd.DataFrame([{"ticker": "005930", "date": day, "foreign_buy": 200_000_000, "inst_buy": 100_000_000} for day in dates]).to_csv(data_dir / "all_institutional_trend_data.csv", index=False)
detail._current_stock_detail_cache_slot = lambda: f"qa-{state['version']}"


def synthetic_detail(self, ticker):
    personal = {"zero": 0, "positive": 200_000, "negative": -200_000, "legacy": 0}.get(state["mode"])
    rows = [{"date": day, "netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20,
             "netIndividualsBuyVolume": personal, "close": 100} for day in reversed(dates)]
    if state["mode"] == "invalid":
        rows[2]["netIndividualsBuyVolume"] = "Infinity"
    return {"code": ticker, "name": "수급 검증", "market": "KOSPI",
            "price": {"current": 70_000, "prev_close": 69_000, "open": 69_000, "high": 71_000, "low": 68_000,
                      "volume": 2_000_000, "trading_value": 140_000_000_000},
            "indicators": {"market_cap": 100_000_000_000},
            "investor_trend": parse_investor_trend({"result": {"body": rows}}, 5),
            "financials": {}, "stability": {}}


TossCollector.get_full_stock_detail = synthetic_detail
TossCollector._safe_request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("External provider prohibited"))


@app.before_request
def boundary():
    if request.method != "GET" and request.path not in {"/__qa/control", "/api/kr/realtime-prices"}:
        return jsonify({"error": "fixture mutation prohibited"}), 405


@app.after_request
def record(response):
    with log.open("a") as output:
        output.write(json.dumps({"method": request.method, "path": request.path, "status": response.status_code, "mode": state["mode"]}) + "\n")
    return response


@app.post("/__qa/control")
def control():
    body = request.get_json() or {}
    mode = body.get("mode")
    if mode not in {"zero", "positive", "negative", "missing", "invalid", "error", "legacy"}:
        return jsonify({"error": "unknown mode"}), 400
    state.update(mode=mode, version=state["version"] + 1)
    detail._STOCK_DETAIL_CACHE.clear()
    return jsonify(state)


@app.get("/api/kr/stock-detail/<ticker>")
def stock_detail(ticker):
    if state["mode"] == "error":
        return jsonify({"error": "합성 조회 실패"}), 503
    if state["mode"] == "legacy":
        payload = detail.build_toss_detail_payload(ticker, synthetic_detail(None, ticker))
        payload["investorTrend"].pop("individual_schema", None)
        key, signature, _ = detail._stock_detail_sqlite_context(ticker_padded=ticker, cache_slot=detail._current_stock_detail_cache_slot(), data_dir=str(data_dir))
        save_json_payload_to_sqlite(filepath=key, signature=signature, payload=payload, logger=logger, max_rows=100)
    payload = detail.fetch_stock_detail_payload(ticker=ticker, load_csv_file=lambda filename: pd.read_csv(data_dir / filename) if (data_dir / filename).exists() else pd.DataFrame(), logger=logger, data_dir=str(data_dir))
    return jsonify(payload)


@app.get("/api/auth/session")
def session():
    return jsonify({})


@app.get("/api/admin/check")
def admin():
    return jsonify({"isAdmin": False})


@app.get("/api/kr/user/quota")
@app.get("/api/kr/chatbot/quota")
def quota():
    return jsonify({"usage": 2, "limit": 10, "remaining": 8})


@app.get("/api/kr/jongga-v2/latest")
def jongga():
    today = datetime.now().strftime("%Y-%m-%d")
    signal = {"stock_code": "005930", "stock_name": "수급 검증", "market": "KOSPI", "sector": "검증",
              "grade": "B", "score": {"total": 12, "base_score": 10, "bonus_score": 2},
              "current_price": 70000, "entry_price": 70000, "stop_price": 68000, "target_price": 75000,
              "change_pct": 1.5, "trading_value": 140_000_000_000, "signal_date": today,
              "checklist": {"has_news": False, "volume_surge": False, "supply_positive": True},
              "score_details": {"foreign_net_buy": 1_000_000_000, "inst_net_buy": 500_000_000}, "news": []}
    return jsonify({"date": today, "updated_at": datetime.now().isoformat(), "status": "ok", "signals": [signal], "total_candidates": 1, "filtered_count": 1})


@app.get("/api/kr/jongga-v2/dates")
def jongga_dates():
    return jsonify([])


@app.get("/api/kr/jongga-v2/status")
def status():
    return jsonify({"is_running": False})


@app.get("/api/kr/market-gate")
def gate():
    return jsonify({"score": 70, "label": "중립", "status": "YELLOW", "sectors": []})


@app.get("/api/kr/config/interval")
def interval():
    return jsonify({"interval": 30})


@app.post("/api/kr/realtime-prices")
def prices():
    return jsonify({"005930": {"price": 70000, "change_pct": 1.5}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    assert Path(args.repo).resolve() == ROOT and args.port == 57942
    app.run(host="127.0.0.1", port=args.port, use_reloader=False, threaded=True)
