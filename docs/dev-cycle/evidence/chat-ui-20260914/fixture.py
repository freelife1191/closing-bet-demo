#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT-019·020 브라우저 실측 전용 합성 Flask fixture.

git archive scratch에서만 실행한다. 이전 슬래시 fixture의 실제 챗봇·히스토리
라우트를 그대로 쓰고, 이 파일은 VCP 화면의 읽기 응답과 한 번짜리 삭제 경계만 합성한다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

from flask import Flask, jsonify, request


SOURCE_REPO = Path("/Users/freelife/vibe/lecture/hodu/closing-bet-demo").resolve()
BASE_FIXTURE = Path("docs/dev-cycle/evidence/slash-batch-20260909/fixture.py")
FIXTURE_PATH = Path("docs/dev-cycle/evidence/chat-ui-20260914/fixture.py")
VALID_DELETE_ERRORS = {404, 500}

STOCKS = {
    "005930": {"name": "삼성전자", "price": 76_200, "market": "KOSPI"},
    "000660": {"name": "SK하이닉스", "price": 184_500, "market": "KOSPI"},
}


class FixtureError(RuntimeError):
    """scratch 격리 또는 control 입력이 잘못되었을 때 쓴다."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def validate_scratch_repo(raw_repo: str) -> Path:
    """이 fixture가 든, git metadata가 없는 archive checkout만 허용한다."""
    repo = Path(raw_repo).expanduser().resolve()
    _assert(repo.is_dir(), "--repo는 존재하는 scratch checkout이어야 합니다.")
    _assert(repo == _repo_root(), "--repo는 이 fixture가 들어 있는 checkout과 같아야 합니다.")
    _assert((repo / FIXTURE_PATH).resolve() == Path(__file__).resolve(), "fixture 경로가 예상과 다릅니다.")
    _assert(repo != SOURCE_REPO, "원본 저장소에서는 fixture를 실행할 수 없습니다.")
    _assert(not (repo / ".git").exists(), "git archive scratch checkout에서만 실행할 수 있습니다.")
    _assert((repo / BASE_FIXTURE).is_file(), "재사용할 슬래시 fixture가 없습니다.")
    return repo


def _load_base_fixture(repo: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("chat_ui_base_fixture", repo / BASE_FIXTURE)
    _assert(spec is not None and spec.loader is not None, "슬래시 fixture를 불러올 수 없습니다.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _recommendation(action: str, confidence: int, reason: str) -> dict[str, Any]:
    return {"action": action, "confidence": confidence, "reason": reason}


def _signal(ticker: str, *, score: int, contraction: float) -> dict[str, Any]:
    stock = STOCKS[ticker]
    price = stock["price"]
    return {
        "ticker": ticker,
        "name": stock["name"],
        "market": stock["market"],
        "signal_date": "2026-09-14",
        "entry_price": price - 1_200,
        "current_price": price,
        "stop_price": price - 3_500,
        "target_price": price + 4_800,
        "return_pct": 1.6,
        "foreign_5d": 1_450_000,
        "inst_5d": 980_000,
        "score": score,
        "vcp_score": 17,
        "contraction_ratio": contraction,
        "gemini_recommendation": _recommendation("BUY", 82, "합성 VCP 수축과 수급 개선을 확인했습니다."),
        "gpt_recommendation": _recommendation("HOLD", 67, "합성 fixture의 분할 진입 확인 의견입니다."),
    }


SIGNALS = [_signal("005930", score=86, contraction=0.52), _signal("000660", score=81, contraction=0.58)]


def _chart_payload(ticker: str) -> dict[str, Any]:
    stock = STOCKS.get(ticker, STOCKS["005930"])
    base_price = int(stock["price"])
    start = date(2026, 8, 3)
    rows: list[dict[str, int | str]] = []
    for index in range(30):
        close = base_price - 3_000 + index * 105 + (index % 4) * 40
        rows.append({
            "date": (start + timedelta(days=index)).isoformat(),
            "open": close - 130,
            "high": close + 320,
            "low": close - 280,
            "close": close,
            "volume": 900_000 + index * 11_000,
        })
    return {"ticker": ticker, "data": rows}


def _stock_detail_payload(ticker: str) -> dict[str, Any]:
    stock = STOCKS.get(ticker, {"name": f"종목 {ticker}", "price": 0, "market": "UNKNOWN"})
    price = int(stock["price"])
    return {
        "code": ticker.zfill(6), "name": stock["name"], "market": stock["market"],
        "priceInfo": {"current": price, "prevClose": price - 700, "open": price - 500,
                      "high": price + 900, "low": price - 1_000, "change": 700,
                      "change_pct": 0.9, "volume": 1_200_000, "trading_value": 91_440_000_000},
        "yearRange": {"high_52w": price + 12_000, "low_52w": price - 18_000},
        "indicators": {"marketCap": 450_000_000_000_000, "per": 15.2, "pbr": 1.4},
        "investorTrend": {"foreign": 1_450_000, "institution": 980_000, "individual": -2_430_000},
        "financials": {"revenue": 0, "operatingProfit": 0, "netIncome": 0},
        "safety": {"debtRatio": 0, "currentRatio": 0},
    }


def _install_vcp_routes(app: Flask) -> None:
    """이전 fixture의 빈 안전 GET만 동일 endpoint로 대체하고 VCP GET을 보탠다."""
    app.view_functions["qa_safe_get_0"] = lambda: jsonify({
        "score": 78, "label": "QA 합성 정상", "status": "GREEN",
        "kospi_close": 2_680.1, "kospi_change_pct": 0.6,
        "kosdaq_close": 780.2, "kosdaq_change_pct": 0.3,
        "sectors": [{"name": "반도체", "change_pct": 1.2, "signal": "bullish"}],
    })
    app.view_functions["qa_safe_get_1"] = lambda: jsonify({
        "signals": SIGNALS, "total_scanned": 2, "generated_at": "2026-09-14T09:00:00+09:00",
    })

    @app.get("/api/kr/signals/dates")
    def qa_signal_dates() -> Any:
        return jsonify(["2026-09-14"])

    @app.get("/api/kr/ai-analysis")
    def qa_ai_analysis() -> Any:
        return jsonify({"signals": [{key: value for key, value in signal.items()
                                      if key in {"ticker", "gpt_recommendation", "gemini_recommendation"}}
                                    for signal in SIGNALS]})

    @app.get("/api/kr/signals/status")
    def qa_vcp_status() -> Any:
        return jsonify({"running": False, "status": "idle", "message": "QA fixture 대기", "progress": 0})

    @app.get("/api/kr/stock-chart/<ticker>")
    def qa_stock_chart(ticker: str) -> Any:
        return jsonify(_chart_payload(ticker))

    @app.get("/api/kr/stock-detail/<ticker>")
    def qa_stock_detail(ticker: str) -> Any:
        return jsonify(_stock_detail_payload(ticker))

    @app.post("/api/kr/realtime-prices")
    def qa_realtime_prices() -> Any:
        tickers = (request.get_json(silent=True) or {}).get("tickers", [])
        return jsonify({str(ticker): STOCKS.get(str(ticker), {}).get("price", 0) for ticker in tickers})


def _parse_control_payload(payload: Any) -> dict[str, Any]:
    _assert(isinstance(payload, dict), "control 본문은 JSON 객체여야 합니다.")
    unknown = set(payload) - {"next_delete_error", "real_session_missing", "stale_message_index", "delay_ms", "next_chat_delay_ms", "seed_pairs", "next_post_delay_ms", "post_session_id"}
    _assert(not unknown, f"허용하지 않는 control 키: {', '.join(sorted(unknown))}")
    result: dict[str, Any] = {}
    if "next_delete_error" in payload:
        status = payload["next_delete_error"]
        _assert(status is None or status in VALID_DELETE_ERRORS, "next_delete_error는 404, 500 또는 null입니다.")
        result["next_delete_error"] = status
    if "delay_ms" in payload:
        delay = payload["delay_ms"]
        _assert(isinstance(delay, int) and 0 <= delay <= 10_000, "delay_ms는 0~10000 정수입니다.")
        result["delay_ms"] = delay
    for key in ("real_session_missing", "stale_message_index", "next_chat_delay_ms", "seed_pairs", "next_post_delay_ms", "post_session_id"):
        if key in payload:
            result[key] = payload[key]
    return result


def _install_control(app: Flask, base: ModuleType) -> None:
    """실제 라우트의 다음 DELETE 경계만 제어하고, 상태 변경은 HistoryManager로 수행한다."""
    import chatbot

    control: dict[str, Any] = {"next_delete_error": None, "delay_ms": 0, "next_chat_delay_ms": 0}

    original_stream = base._FakeChatSession.send_message_stream

    def delayed_stream(session: Any, parts: Any) -> Iterator[Any]:
        delay = control["next_chat_delay_ms"] or 0
        control["next_chat_delay_ms"] = 0
        if delay:
            yield base._FakeChunk("QA 지연 응답 시작. ")
            time.sleep(delay / 1_000)
        yield from original_stream(session, parts)

    base._FakeChatSession.send_message_stream = delayed_stream

    @app.before_request
    def delay_post_headers() -> None:
        if request.method == "POST" and request.path == "/api/kr/chatbot" and control.get("next_post_delay_ms"):
            if request.headers.get("X-Session-Id") == control.get("post_session_id"):
                delay = control.pop("next_post_delay_ms")
                time.sleep(delay / 1_000)

    @app.before_request
    def qa_intercept_next_history_delete() -> Any:
        if request.method != "DELETE" or request.path != "/api/kr/chatbot/history":
            return None
        error, delay = control["next_delete_error"], control["delay_ms"]
        control.update(next_delete_error=None, delay_ms=0)
        if delay:
            time.sleep(delay / 1_000)
        if error:
            return jsonify({"error": "QA fixture injected delete error"}), error
        return None

    @app.after_request
    def record_fixture_request(response: Any) -> Any:
        history = chatbot.get_chatbot().history
        with (history.data_dir / "requests-detailed.jsonl").open("a") as output:
            output.write(json.dumps({"method":request.method, "path":request.path,
                "status":response.status_code, "session_id":request.args.get("session_id"),
                "index":request.args.get("index"), "time":time.time()}) + "\n")
        return response

    @app.post("/__qa/control")
    def qa_control() -> Any:
        payload = _parse_control_payload(request.get_json(silent=True))
        history = chatbot.get_chatbot().history
        if "next_delete_error" in payload:
            control["next_delete_error"] = payload["next_delete_error"]
        if "delay_ms" in payload:
            control["delay_ms"] = payload["delay_ms"]
        if "next_post_delay_ms" in payload:
            delay = payload["next_post_delay_ms"]
            _assert(isinstance(delay, int) and 0 <= delay <= 10000, "invalid post delay")
            control["next_post_delay_ms"] = delay
            control["post_session_id"] = payload.get("post_session_id")
        if "next_chat_delay_ms" in payload:
            delay = payload["next_chat_delay_ms"]
            _assert(isinstance(delay, int) and 0 <= delay <= 10000, "invalid chat delay")
            control["next_chat_delay_ms"] = delay
        if "seed_pairs" in payload:
            seed = payload["seed_pairs"]
            _assert(isinstance(seed, dict) and isinstance(seed.get("count"), int) and 0 < seed["count"] <= 30, "invalid seed")
            _assert(history.get_session(seed["session_id"]) is not None, "missing fixture session")
            for index in range(seed["count"]):
                history.add_message(seed["session_id"], "user", f"합성 보관 질문 {index}")
                history.add_message(seed["session_id"], "model", f"합성 보관 답변 {index}")
        removed_session = None
        if "real_session_missing" in payload:
            session_id = payload["real_session_missing"]
            _assert(isinstance(session_id, str) and session_id, "real_session_missing은 세션 ID 문자열입니다.")
            _assert(history.delete_session(session_id), "실제 HistoryManager에 해당 세션이 없습니다.")
            removed_session = session_id
        stale_removed = None
        if "stale_message_index" in payload:
            stale = payload["stale_message_index"]
            _assert(isinstance(stale, dict), "stale_message_index는 session_id와 index 객체입니다.")
            session_id, index = stale.get("session_id"), stale.get("index")
            _assert(isinstance(session_id, str) and isinstance(index, int), "stale_message_index 형식이 잘못됐습니다.")
            _assert(history.delete_message(session_id, index), "실제 HistoryManager에서 삭제할 메시지가 없습니다.")
            stale_removed = {"session_id": session_id, "index": index}
        return jsonify({"next_delete_error": control["next_delete_error"], "delay_ms": control["delay_ms"],
                        "real_session_missing": removed_session, "stale_message_index": stale_removed})


def build_app(repo: Path, *, reset_state: bool = False) -> Flask:
    base = _load_base_fixture(repo)
    app = base.build_app(repo, reset_state=reset_state)
    _install_vcp_routes(app)
    _install_control(app, base)
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="CHAT-019·020 scratch VCP/chat fixture")
    parser.add_argument("--repo", required=True, help="git archive로 만든 scratch checkout")
    parser.add_argument("--reset-state", action="store_true", help="scratch의 합성 상태만 비운다")
    command = parser.add_subparsers(dest="command", required=True)
    serve = command.add_parser("serve", help="loopback fixture를 실행한다")
    serve.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    try:
        repo = validate_scratch_repo(args.repo)
        _assert(args.port not in {3500, 5501}, "원본 서비스 포트는 fixture에 사용할 수 없습니다.")
        from werkzeug.serving import run_simple

        run_simple("127.0.0.1", args.port, build_app(repo, reset_state=args.reset_state),
                   use_reloader=False, use_debugger=False, threaded=True)
        return 0
    except FixtureError as error:
        print(f"fixture error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
