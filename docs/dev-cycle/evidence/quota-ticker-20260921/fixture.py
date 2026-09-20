#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FE-043/JONGGA-030/FLOW-006 UI QA용 scratch 전용 합성 Flask API.

원본 checkout, 실제 환경 변수, 시장 수집기와 LLM은 절대 사용하지 않는다. 읽기 API와
합성 현재가 POST만 노출하며, 모든 데이터는 scratch SQLite/메모리에서 실제 ticker,
가격맵, 백테스트 공개 facade를 거쳐 계산한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, g, jsonify, request


SOURCE_REPO = Path("/Users/freelife/vibe/lecture/hodu/closing-bet-demo").resolve()
FIXTURE_PATH = Path("docs/dev-cycle/evidence/quota-ticker-20260921/fixture.py")
SCRATCH_PREFIX = "quota-ticker-20260921-"
STATE_DIR_NAME = ".qa-quota-ticker"
DEFAULT_EMAIL = "quota-fixture@example.test"
OTHER_EMAIL = "quota-other@example.test"
ALLOWED_QUOTA_MODES = {
    "normal", "html-502", "html-404", "html-200", "json-401", "json-403", "json-500",
}
ALLOWED_CONTROL_KEYS = {"identity", "admin", "quota_mode", "remaining"}
ALLOWED_PRODUCT_POSTS = {"/__qa/control", "/api/kr/realtime-prices"}


class FixtureError(RuntimeError):
    """scratch 경계나 fixture 계약 위반을 알린다."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def validate_scratch_repo(raw_repo: str) -> Path:
    """git archive로 만든 이 라운드 전용 scratch에서만 실행한다."""
    repo = Path(raw_repo).expanduser().resolve()
    _assert(repo.is_dir(), "--repo는 존재하는 scratch checkout이어야 합니다.")
    _assert(repo == _repo_root(), "--repo는 이 fixture가 든 checkout이어야 합니다.")
    _assert(repo.name.startswith(SCRATCH_PREFIX), "quota-ticker 전용 scratch checkout만 허용합니다.")
    _assert((repo / FIXTURE_PATH).resolve() == Path(__file__).resolve(), "fixture 경로가 다릅니다.")
    _assert(repo != SOURCE_REPO, "원본 저장소에서는 fixture를 실행할 수 없습니다.")
    _assert(not (repo / ".git").exists(), "git archive scratch checkout만 허용합니다.")
    for env_name in (".env", ".env.production", ".env.vertex"):
        _assert(not (repo / env_name).exists(), f"scratch에 {env_name} 파일이 있으면 실행할 수 없습니다.")
    return repo


def _ticker_dependencies() -> tuple[Any, Any, Any, Any]:
    """이번 변경의 실제 공개 경로만 지연 import한다.

    새 정규화 helper가 빠진 scratch를 canned 성공으로 덮지 않는다. 그 경우 QA 시작이
    즉시 실패해 통합 순서 문제를 드러낸다.
    """
    try:
        from engine.ticker_utils import normalize_ticker
        from services.kr_market_backtest_service import (
            build_cumulative_trade_record,
            build_ticker_price_index,
            calculate_jongga_backtest_stats,
            calculate_vcp_backtest_stats,
        )
        from services.kr_market_data_cache_prices import _build_latest_price_map
    except ImportError as error:
        raise FixtureError(f"JONGGA-030 실제 helper를 import할 수 없습니다: {error}") from error
    return (
        normalize_ticker,
        _build_latest_price_map,
        {
            "build_cumulative_trade_record": build_cumulative_trade_record,
            "build_ticker_price_index": build_ticker_price_index,
            "calculate_jongga_backtest_stats": calculate_jongga_backtest_stats,
            "calculate_vcp_backtest_stats": calculate_vcp_backtest_stats,
        },
        _load_cached_realtime_prices,
    )


def _load_cached_realtime_prices(
    tickers: list[Any],
    *,
    get_data_path: Any,
    logger: logging.Logger,
    max_age_seconds: int = 900,
) -> dict[str, float]:
    """실제 SQLite 호환 조회 구현을 fixture가 호출하는 좁은 adapter다."""
    from services.kr_market_realtime_price_cache import load_cached_realtime_prices

    return load_cached_realtime_prices(
        tickers,
        get_data_path=get_data_path,
        logger=logger,
        max_age_seconds=max_age_seconds,
    )


def _seed_legacy_realtime_prices(storage_dir: Path) -> Path:
    """정규화 이전의 lowercase/미패딩 SQLite 키를 scratch에만 기록한다."""
    db_path = storage_dir / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS realtime_price_cache (
                ticker TEXT PRIMARY KEY,
                price REAL NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = datetime.now().isoformat()
        conn.executemany(
            "INSERT OR REPLACE INTO realtime_price_cache (ticker, price, source, updated_at) VALUES (?, ?, ?, ?)",
            [
                ("0007c0", 15_200.0, "fixture-legacy", now),
                ("5930", 76_200.0, "fixture-legacy", now),
                ("000000", 999_999.0, "fixture-invalid", now),
                ("", 999_998.0, "fixture-invalid", now),
            ],
        )
    return db_path


def _raw_price_frame() -> pd.DataFrame:
    """원시 입력을 유지해 실제 CSV/가격/백테스트 함수가 정규화하도록 한다."""
    raw = pd.DataFrame([
        {"date": "2026-09-17", "ticker": "0007c0", "close": 14_000, "high": 14_200, "low": 13_800},
        {"date": "2026-09-18", "ticker": "0007c0", "close": 14_500, "high": 14_800, "low": 14_100},
        {"date": "2026-09-19", "ticker": "0007c0", "close": 15_200, "high": 15_400, "low": 14_600},
        {"date": "2026-09-19", "ticker": "5930", "close": 76_200, "high": 76_500, "low": 75_800},
        {"date": "2026-09-19", "ticker": "", "close": 1, "high": 1, "low": 1},
        {"date": "2026-09-19", "ticker": "000000", "close": 2, "high": 2, "low": 2},
        {"date": "2026-09-19", "ticker": 0, "close": 3, "high": 3, "low": 3},
        {"date": "2026-09-19", "ticker": "20260211", "close": 4, "high": 4, "low": 4},
    ])
    return raw



def _dashboard_payloads(storage_dir: Path) -> dict[str, Any]:
    """실제 normalizer·가격맵·backtest facade를 통한 화면 payload를 만든다."""
    normalize_ticker, build_latest_price_map, facade, cache_loader = _ticker_dependencies()
    expected = {
        "5930": "005930", "0007c0": "0007C0", "A005930": "005930",
        "005930.KS": "005930", "": "", "000000": "", 0: "", "20260211": "",
    }
    observed = {value: normalize_ticker(value) for value in expected}
    _assert(observed == expected, f"normalize_ticker 계약 불일치: {observed}")

    prices_df = _raw_price_frame()
    price_map = build_latest_price_map(prices_df)
    _assert(price_map == {"0007C0": 15_200.0, "005930": 76_200.0}, f"가격맵 계약 불일치: {price_map}")

    _seed_legacy_realtime_prices(storage_dir)
    cache_prices = cache_loader(
        ["0007C0", "005930", "", "000000"],
        get_data_path=lambda _name: str(storage_dir / "daily_prices.csv"),
        logger=logging.getLogger(__name__),
    )
    _assert(cache_prices == {"0007C0": 15_200.0, "005930": 76_200.0}, f"legacy SQLite 호환 조회 실패: {cache_prices}")

    closing_signal = {
        "stock_code": "0007c0", "stock_name": "아크릴 QA", "market": "KOSDAQ", "grade": "S",
        "entry_price": 14_000, "target_price": 14_700, "stop_price": 13_300,
        "current_price": price_map["0007C0"],
        "score": {"total": 18, "news": 3, "volume": 3, "chart": 2, "supply": 2, "candle": 1, "timing": 1, "llm_reason": "합성 ticker QA 분석입니다."},
        "themes": ["AI", "합성 QA"], "trading_value": 1_240_000_000,
        "change_pct": 8.6, "volume_ratio": 2.4,
        "score_details": {"volume_ratio": 2.4, "foreign_net_buy": 1_240_000_000, "inst_net_buy": 327_600_465, "bonus_score": 2, "bonus_breakdown": {"volume": 2, "candle": 0, "limit_up": 0}},
        "checklist": {"has_news": True, "supply_positive": True, "is_new_high": True, "is_breakout": True, "volume_surge": True},
        "advice": {"trading_tip": "합성 QA 진입 규칙", "selling_strategy": "합성 QA 청산 규칙", "market_context": "합성 중립 시장", "buy_strategy": "거래량 확인 뒤 진입"},
        "news_items": [{"title": "아크릴 QA 합성 뉴스", "url": "https://example.invalid/quota-ticker", "source": "QA"}],
    }
    price_index = facade["build_ticker_price_index"](prices_df)
    closing_stats = facade["calculate_jongga_backtest_stats"](
        [dict(closing_signal)],
        [{"date": "2026-09-17", "signals": [dict(closing_signal)]}],
        price_map,
        prices_df,
        price_index=price_index,
    )
    vcp_log = pd.DataFrame([
        {"ticker": "0007c0", "signal_date": "2026-09-17", "entry_price": 13_200},
        {"ticker": "", "signal_date": "2026-09-17", "entry_price": 1},
        {"ticker": "000000", "signal_date": "2026-09-17", "entry_price": 1},
    ])
    vcp_stats = facade["calculate_vcp_backtest_stats"](vcp_log, price_map, prices_df, price_index=price_index)
    trade = facade["build_cumulative_trade_record"](
        closing_signal, "2026-09-17", prices_df, price_index=price_index,
    )
    _assert(trade is not None and trade["code"] == "0007C0", "누적 성과 ticker가 정규화되지 않았습니다.")
    _assert(closing_stats["count"] == 1 and vcp_stats["count"] == 1, "invalid ticker가 backtest에 섞였습니다.")

    vcp_signal = {
        "ticker": "0007C0", "name": "아크릴 QA", "market": "KOSDAQ", "signal_date": "2026-09-17",
        "entry_price": 13_200, "current_price": price_map["0007C0"], "target_price": 15_180,
        "stop_price": 12_540, "return_pct": (price_map["0007C0"] / 13_200 - 1) * 100, "score": 86, "vcp_score": 17, "contraction_ratio": 0.52,
        "foreign_5d": 1_240_000_000, "inst_5d": 327_600_465,
        "gemini_recommendation": {"action": "BUY", "confidence": 82, "reason": "합성 VCP 수축을 확인했습니다."},
        "gpt_recommendation": {"action": "HOLD", "confidence": 61, "reason": "합성 QA 관망 의견입니다."},
        "news": [{"title": "아크릴 QA VCP 뉴스", "url": "https://example.invalid/quota-ticker-vcp", "source": "QA"}],
    }
    cumulative = {
        "kpi": {"totalSignals": 1, "wins": int(trade["outcome"] == "WIN"), "losses": int(trade["outcome"] == "LOSS"),
                "open": int(trade["outcome"] == "OPEN"), "winRate": closing_stats["win_rate"], "avgRoi": closing_stats["avg_return"],
                "totalRoi": closing_stats["avg_return"], "avgDays": trade["days"], "priceDate": "2026-09-19",
                "profitFactor": None, "recentWinRate": closing_stats["win_rate"], "recentClosedCount": closing_stats["count"],
                "consecutiveLosses": 0, "roiByGrade": {grade: {"count": int(grade == "S"), "wins": int(grade == "S" and trade["outcome"] == "WIN"), "losses": int(grade == "S" and trade["outcome"] == "LOSS"), "winRate": closing_stats["win_rate"] if grade == "S" else 0.0, "avgRoi": closing_stats["avg_return"] if grade == "S" else 0.0, "totalRoi": closing_stats["avg_return"] if grade == "S" else 0.0} for grade in ("S", "A", "B", "D")}},
        "trades": [trade],
    }
    return {
        "jongga": {"date": "2026-09-19", "total_candidates": 1, "filtered_count": 1, "status": "success", "updated_at": "2026-09-19T15:40:00+09:00", "signals": [closing_signal]},
        "vcp": [vcp_signal], "cumulative": cumulative,
        "backtest": {"vcp": vcp_stats, "closing_bet": closing_stats}, "price_map": price_map,
    }


def build_app(repo: Path, *, reset_log: bool = False) -> Flask:
    """현재 UI가 읽는 API shape만 노출하는 Flask fixture를 구축한다."""
    storage_dir = repo / STATE_DIR_NAME / "synthetic-data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    request_log = repo / STATE_DIR_NAME / "requests.jsonl"
    if reset_log:
        request_log.write_text("", encoding="utf-8")
    payloads = _dashboard_payloads(storage_dir)
    app = Flask("quota-ticker-fixture")
    app.testing = True
    lock = threading.Lock()
    state: dict[str, Any] = {"identity": "default", "admin": False, "quota_mode": "normal", "remaining": 8}

    @app.before_request
    def boundary() -> Any:
        identity = state["identity"]
        g.user_email = DEFAULT_EMAIL if identity == "default" else OTHER_EMAIL if identity == "other" else None
        if request.method != "GET" and request.path not in ALLOWED_PRODUCT_POSTS:
            return jsonify({"error": "fixture prohibits product mutation"}), 405
        return None

    @app.after_request
    def record(response: Any) -> Any:
        with lock, request_log.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"method": request.method, "path": request.path, "status": response.status_code}, ensure_ascii=False) + "\n")
        return response

    @app.post("/__qa/control")
    def control() -> Any:
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - ALLOWED_CONTROL_KEYS:
            return jsonify({"error": "control allows identity, admin, quota_mode, remaining only"}), 400
        if "identity" in body and body["identity"] not in {"default", "other", "unauth"}:
            return jsonify({"error": "identity must be default, other, or unauth"}), 400
        if "admin" in body and not isinstance(body["admin"], bool):
            return jsonify({"error": "admin must be boolean"}), 400
        if "quota_mode" in body and body["quota_mode"] not in ALLOWED_QUOTA_MODES:
            return jsonify({"error": "unsupported quota_mode"}), 400
        if "remaining" in body and body["remaining"] not in {3, 8}:
            return jsonify({"error": "remaining must be recovery value 3 or 8"}), 400
        state.update(body)
        return jsonify(dict(state))

    @app.get("/api/auth/session")
    def session() -> Any:
        if state["identity"] == "unauth":
            return jsonify(None)
        email = DEFAULT_EMAIL if state["identity"] == "default" else OTHER_EMAIL
        return jsonify({"user": {"name": "Quota Ticker QA", "email": email, "image": None}, "expires": "2099-12-31T23:59:59.000Z"})

    @app.get("/api/admin/check")
    def admin_check() -> Any:
        return jsonify({"isAdmin": bool(state["admin"]) and state["identity"] != "unauth"})

    @app.get("/api/kr/user/quota")
    @app.get("/api/kr/chatbot/quota")
    def quota() -> Any:
        mode = state["quota_mode"]
        if mode.startswith("html-"):
            status = int(mode.rsplit("-", maxsplit=1)[1])
            return "<!doctype html><title>synthetic quota failure</title>", status, {"Content-Type": "text/html; charset=utf-8"}
        if mode.startswith("json-"):
            status = int(mode.rsplit("-", maxsplit=1)[1])
            return jsonify({"error": "synthetic quota failure", "status": status}), status
        remaining = int(state["remaining"])
        return jsonify({"usage": 10 - remaining, "used": 10 - remaining, "limit": 10, "remaining": remaining})

    @app.post("/api/kr/realtime-prices")
    def realtime_prices() -> Any:
        body = request.get_json(silent=True) or {}
        tickers = body.get("tickers", []) if isinstance(body, dict) else []
        if not isinstance(tickers, list):
            return jsonify({"error": "tickers must be a list"}), 400
        return jsonify({ticker: payloads["price_map"][ticker] for ticker in tickers if ticker in payloads["price_map"]})

    @app.get("/api/portfolio")
    def portfolio() -> Any:
        from services.paper_trading_valuation_helpers import build_valuated_holding, calculate_stock_value_from_rows
        raw = {"ticker": "0007c0", "name": "아크릴 QA", "avg_price": 14000, "quantity": 3, "total_cost": 42000}
        holding, value = build_valuated_holding(raw, payloads["price_map"])
        assert value == calculate_stock_value_from_rows([raw], payloads["price_map"]) == 45600
        return jsonify({"holdings": [holding], "cash": 58000, "total_asset_value": 58000 + value,
                        "total_stock_value": value, "total_profit": value - 42000,
                        "total_profit_rate": (value - 42000) / 100000 * 100, "total_principal": 100000})

    @app.get("/api/portfolio/history")
    def portfolio_history() -> Any:
        return jsonify({"trades": []})

    @app.get("/api/kr/market-gate")
    def market_gate() -> Any:
        return jsonify({"score": 70, "label": "중립", "status": "YELLOW", "kospi_close": 2_700, "kospi_change_pct": 0.2, "kosdaq_close": 780, "kosdaq_change_pct": -0.1, "sectors": [], "source": "synthetic-no-market"})

    @app.get("/api/kr/config/interval")
    def interval() -> Any:
        return jsonify({"interval": 30})

    @app.get("/api/kr/signals")
    def signals() -> Any:
        return jsonify({"signals": payloads["vcp"], "total_scanned": 1, "generated_at": "2026-09-19T15:45:00+09:00"})

    @app.get("/api/kr/ai-analysis")
    def ai_analysis() -> Any:
        return jsonify({"signals": payloads["vcp"], "generated_at": "2026-09-19T15:45:00+09:00"})

    @app.get("/api/kr/signals/dates")
    def signal_dates() -> Any:
        return jsonify(["2026-09-19"])

    @app.get("/api/kr/signals/status")
    def signal_status() -> Any:
        return jsonify({"running": False, "message": "fixture ticker cache ready", "progress": 100})

    @app.get("/api/kr/jongga-v2/latest")
    def jongga() -> Any:
        return jsonify(payloads["jongga"])

    @app.get("/api/kr/jongga-v2/dates")
    def jongga_dates() -> Any:
        return jsonify(["2026-09-19"])

    @app.get("/api/kr/jongga-v2/status")
    def jongga_status() -> Any:
        return jsonify({"is_running": False, "message": "fixture ticker cache ready"})

    @app.get("/api/kr/closing-bet/cumulative")
    def cumulative() -> Any:
        data = payloads["cumulative"]
        return jsonify({**data, "pagination": {"total": len(data["trades"]), "page": 1, "limit": 50, "totalPages": 1}})

    @app.get("/api/kr/backtest-summary")
    def backtest() -> Any:
        return jsonify(payloads["backtest"])

    @app.get("/api/kr/status")
    def status() -> Any:
        return jsonify({"status": "success", "data": {"last_update": "2026-09-19", "signals_count": 1}})

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="quota-ticker scratch-only fixture")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--reset-log", action="store_true")
    args = parser.parse_args()
    try:
        repo = validate_scratch_repo(args.repo)
        _assert(args.port not in {3500, 5501}, "원본 서비스 포트는 사용할 수 없습니다.")
        _assert(1024 <= args.port <= 65535, "port는 1024~65535 범위여야 합니다.")
        from werkzeug.serving import run_simple

        run_simple("127.0.0.1", args.port, build_app(repo, reset_log=args.reset_log), use_reloader=False, use_debugger=False, threaded=True)
        return 0
    except FixtureError as error:
        print(f"fixture error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
