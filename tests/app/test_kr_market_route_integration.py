#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 통합 테스트

헬퍼 분리 리팩토링 이후에도 실제 API 흐름이 유지되는지 검증한다.
"""

import copy
import json
import os
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from flask import Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import kr_market


class _DummyVcpAnalyzer:
    def get_available_providers(self):
        return ["gemini"]

    async def analyze_batch(self, stocks_to_analyze):
        results = {}
        for item in stocks_to_analyze:
            ticker = str(item.get("ticker", "")).zfill(6)
            if ticker == "000001":
                results[ticker] = {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 77,
                        "reason": "재분석 성공",
                    }
                }
            else:
                results[ticker] = {
                    "gemini_recommendation": {
                        "action": "N/A",
                        "confidence": 0,
                        "reason": "분석 실패",
                    }
                }
        return results


class _DummyChatbot:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    def chat_stream(self, message, **kwargs):
        self.calls.append({"message": message, **kwargs})
        for chunk in self._chunks:
            yield chunk


def _create_client():
    app = Flask(__name__)
    app.testing = True
    app.register_blueprint(kr_market.kr_bp, url_prefix="/api/kr")
    return app.test_client()


def _create_client_with_user(user_api_key=None, user_email=None):
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _inject_user_context():
        from flask import g

        g.user_api_key = user_api_key
        g.user_email = user_email

    app.register_blueprint(kr_market.kr_bp, url_prefix="/api/kr")
    return app.test_client()


def _install_chatbot_module(monkeypatch, bot):
    module = types.ModuleType("chatbot")
    module.get_chatbot = lambda: bot
    monkeypatch.setitem(sys.modules, "chatbot", module)


def _prepare_quota_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "QUOTA_FILE", str(tmp_path / "user_quota.json"))


def _count_rules(client, path: str, method: str) -> int:
    return sum(
        1
        for rule in client.application.url_map.iter_rules()
        if rule.rule == path and method in rule.methods
    )


def test_reanalyze_vcp_failed_ai_filters_failed_rows_and_updates_csv(monkeypatch, tmp_path: Path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "1",
                "signal_date": "2026-02-20",
                "name": "Alpha",
                "ai_action": None,
                "ai_reason": None,
                "ai_confidence": 0,
                "current_price": 10000,
                "entry_price": 9800,
                "score": 7,
                "vcp_score": 6,
                "contraction_ratio": 12,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 0,
                "inst_1d": 0,
            },
            {
                "ticker": "2",
                "signal_date": "2026-02-20",
                "name": "Beta",
                "ai_action": "BUY",
                "ai_reason": "이미 분석 완료",
                "ai_confidence": 85,
                "current_price": 12000,
                "entry_price": 11000,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            },
            {
                "ticker": "3",
                "signal_date": "2026-02-20",
                "name": "Gamma",
                "ai_action": "HOLD",
                "ai_reason": "분석 실패",
                "ai_confidence": 0,
                "current_price": 9000,
                "entry_price": 9100,
                "score": 6,
                "vcp_score": 5,
                "contraction_ratio": 14,
                "foreign_5d": 0,
                "inst_5d": 0,
                "foreign_1d": 0,
                "inst_1d": 0,
            },
            {
                "ticker": "4",
                "signal_date": "2026-02-19",
                "name": "Delta",
                "ai_action": None,
                "ai_reason": None,
                "ai_confidence": 0,
                "current_price": 15000,
                "entry_price": 14500,
                "score": 7,
                "vcp_score": 6,
                "contraction_ratio": 11,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            },
        ]
    )

    output_csv = tmp_path / "signals_log.csv"

    monkeypatch.setattr(kr_market, "load_csv_file", lambda _: signals_df.copy())
    monkeypatch.setattr(kr_market, "get_data_path", lambda filename: str(tmp_path / filename))
    monkeypatch.setattr(kr_market, "_update_vcp_ai_cache_files", lambda *_: 1)
    monkeypatch.setitem(kr_market.VCP_STATUS, "running", False)

    import engine.vcp_ai_analyzer as vcp_ai_analyzer

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyVcpAnalyzer())

    client = _create_client()
    res = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"target_date": "2026-02-20"},
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload["status"] == "success"
    assert payload["total_in_scope"] == 3
    assert payload["failed_targets"] == 2
    assert payload["updated_count"] == 1
    assert payload["still_failed_count"] == 1
    assert payload["cache_files_updated"] == 1

    assert output_csv.exists()
    written = pd.read_csv(output_csv, dtype={"ticker": str}, keep_default_na=False)
    written["ticker"] = written["ticker"].astype(str).str.zfill(6)

    row1 = written[written["ticker"] == "000001"].iloc[0]
    assert row1["ai_action"] == "BUY"
    assert int(row1["ai_confidence"]) == 77
    assert row1["ai_reason"] == "재분석 성공"

    row3 = written[written["ticker"] == "000003"].iloc[0]
    assert row3["ai_action"] == "N/A"
    assert int(row3["ai_confidence"]) == 0
    assert row3["ai_reason"] == "분석 실패"


def test_get_kr_signals_dates_uses_file_mtime_cache(monkeypatch, tmp_path: Path):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("placeholder", encoding="utf-8")

    call_counter = {"count": 0}

    def _load_csv(_filename):
        call_counter["count"] += 1
        return pd.DataFrame(
            [
                {"signal_date": "2026-02-20"},
                {"signal_date": "2026-02-19"},
            ]
        )

    monkeypatch.setattr(kr_market, "load_csv_file", _load_csv)
    monkeypatch.setattr(kr_market, "get_data_path", lambda _filename: str(signals_path))

    client = _create_client()

    first = client.get("/api/kr/signals/dates")
    second = client.get("/api/kr/signals/dates")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == ["2026-02-20", "2026-02-19"]
    assert second.get_json() == ["2026-02-20", "2026-02-19"]
    assert call_counter["count"] == 1

    updated_mtime = signals_path.stat().st_mtime + 2
    os.utime(signals_path, (updated_mtime, updated_mtime))

    third = client.get("/api/kr/signals/dates")
    assert third.status_code == 200
    assert third.get_json() == ["2026-02-20", "2026-02-19"]
    assert call_counter["count"] == 2


def test_get_jongga_v2_latest_recalculates_grades_and_sorts(monkeypatch, tmp_path: Path):
    latest_data = {
        "date": "2026-02-20",
        "signals": [
            {
                "ticker": "000001",
                "stock_code": "000001",
                "stock_name": "A",
                "grade": "D",
                "change_pct": 3.0,
                "trading_value": 500_000_000_000,
                "score": {"total": 8},
                "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                "entry_price": 10000,
                "current_price": 10300,
            },
            {
                "ticker": "000002",
                "stock_code": "000002",
                "stock_name": "B",
                "grade": "D",
                "change_pct": 3.0,
                "trading_value": 1_000_000_000_000,
                "score": {"total": 10},
                "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                "entry_price": 10000,
                "current_price": 10400,
            },
            {
                "ticker": "000003",
                "stock_code": "000003",
                "stock_name": "C",
                "grade": "D",
                "change_pct": 1.0,
                "trading_value": 80_000_000_000,
                "score": {"total": 4},
                "score_details": {"foreign_net_buy": 0, "inst_net_buy": 0},
                "entry_price": 10000,
                "current_price": 9900,
            },
        ],
        "by_grade": {"S": 0, "A": 0, "B": 0, "C": 0, "D": 3},
    }

    monkeypatch.setattr(kr_market, "load_json_file", lambda _: copy.deepcopy(latest_data))
    monkeypatch.setattr(kr_market, "get_data_path", lambda filename: str(tmp_path / filename))

    client = _create_client()
    res = client.get("/api/kr/jongga-v2/latest")

    assert res.status_code == 200
    payload = res.get_json()
    signals = payload["signals"]

    # grade 재산정 + 정렬(S>A>B)
    assert signals[0]["stock_code"] == "000002"
    assert signals[0]["grade"] == "S"
    assert signals[1]["stock_code"] == "000001"
    assert signals[1]["grade"] == "A"
    assert signals[2]["stock_code"] == "000003"
    assert signals[2]["grade"] == "D"

    assert payload["by_grade"]["S"] == 1
    assert payload["by_grade"]["A"] == 1
    assert payload["by_grade"]["D"] == 1


def test_get_jongga_v2_history_sorts_signals_with_shared_helper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "load_json_file", lambda _: {})

    target_file = tmp_path / "jongga_v2_results_20260220.json"
    target_file.write_text(
        json.dumps(
            {
                "date": "2026-02-20",
                "signals": [
                    {
                        "stock_code": "000001",
                        "grade": "A",
                        "change_pct": 3.0,
                        "trading_value": 500_000_000_000,
                        "score": {"total": 8},
                        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                    },
                    {
                        "stock_code": "000002",
                        "grade": "D",
                        "change_pct": 3.0,
                        "trading_value": 1_000_000_000_000,
                        "score": {"total": 10},
                        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = _create_client()
    res = client.get("/api/kr/jongga-v2/history/2026-02-20")

    assert res.status_code == 200
    payload = res.get_json()
    assert [s["stock_code"] for s in payload["signals"]] == ["000002", "000001"]


def test_chatbot_free_tier_success_stream_increments_quota(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    bot = _DummyChatbot(
        [
            {"chunk": "안녕하세요"},
            {"usage_metadata": {"prompt_tokens": 12, "completion_tokens": 8}},
            {"chunk": " 반갑습니다"},
        ]
    )
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트 메시지"},
        headers={"X-Session-Id": "session-abc"},
    )

    assert response.status_code == 200
    assert response.content_type.startswith("text/event-stream")
    assert "data:" in response.get_data(as_text=True)

    assert kr_market.get_user_usage("session-abc") == 1
    assert bot.calls[0]["owner_id"] == "session-abc"


def test_chatbot_warning_response_skips_quota_increment(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    bot = _DummyChatbot([{"chunk": "⚠️ API 키를 확인해주세요."}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트"},
        headers={"X-Session-Id": "session-warning"},
    )

    assert response.status_code == 200
    assert kr_market.get_user_usage("session-warning") == 0


def test_chatbot_quota_guard_blocks_when_limit_exceeded(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    quota_file = tmp_path / "user_quota.json"
    quota_file.write_text(
        json.dumps({"session-limit": kr_market.MAX_FREE_USAGE}, ensure_ascii=False),
        encoding="utf-8",
    )

    bot = _DummyChatbot([{"chunk": "should-not-run"}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트"},
        headers={"X-Session-Id": "session-limit"},
    )

    assert response.status_code == 402
    payload = response.get_json()
    assert payload["code"] == "QUOTA_EXCEEDED"
    assert bot.calls == []


def test_routes_do_not_overlap_for_interval_and_chatbot_history():
    client = _create_client()

    assert _count_rules(client, "/api/kr/config/interval", "GET") == 1
    assert _count_rules(client, "/api/kr/config/interval", "POST") == 1
    assert _count_rules(client, "/api/kr/chatbot/history", "DELETE") == 1


def test_increment_user_usage_is_thread_safe(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    usage_key = "session-concurrent"
    increment_count = 50

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: kr_market.increment_user_usage(usage_key), range(increment_count)))

    assert kr_market.get_user_usage(usage_key) == increment_count


def test_config_interval_post_parses_string_and_applies_update(monkeypatch):
    client = _create_client()
    applied = {}

    monkeypatch.setattr(
        kr_market,
        "_apply_market_gate_interval",
        lambda interval: applied.setdefault("interval", interval),
    )
    monkeypatch.setattr(kr_market, "_persist_market_gate_interval_to_env", lambda _: None)

    response = client.post("/api/kr/config/interval", json={"interval": "15"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["interval"] == 15
    assert applied["interval"] == 15


def test_config_interval_post_rejects_invalid_value():
    client = _create_client()
    response = client.post("/api/kr/config/interval", json={"interval": "abc"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid interval"


def test_reanalyze_gemini_requires_login_without_api_key():
    client = _create_client()

    response = client.post("/api/kr/reanalyze/gemini", json={})

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["code"] == "UNAUTHORIZED"


def test_reanalyze_gemini_returns_402_when_quota_exceeded(monkeypatch):
    import services.usage_tracker as usage_tracker_module

    monkeypatch.setattr(usage_tracker_module.usage_tracker, "check_and_increment", lambda _email: False)
    client = _create_client_with_user(user_api_key=None, user_email="tester@example.com")

    response = client.post("/api/kr/reanalyze/gemini", json={})

    assert response.status_code == 402
    payload = response.get_json()
    assert payload["code"] == "LIMIT_EXCEEDED"


def test_reanalyze_gemini_runs_batch_with_user_key(monkeypatch):
    monkeypatch.setattr(
        kr_market,
        "run_user_gemini_reanalysis",
        lambda **_kwargs: {"count": 3},
    )
    client = _create_client_with_user(user_api_key="test-key", user_email="tester@example.com")

    response = client.post(
        "/api/kr/reanalyze/gemini",
        json={"target_dates": "2026-02-20"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert "3개 종목" in payload["message"]


def test_reanalyze_gemini_returns_500_when_batch_fails(monkeypatch):
    monkeypatch.setattr(
        kr_market,
        "run_user_gemini_reanalysis",
        lambda **_kwargs: {"error": "batch failed"},
    )
    client = _create_client_with_user(user_api_key="test-key", user_email="tester@example.com")

    response = client.post("/api/kr/reanalyze/gemini", json={})

    assert response.status_code == 500
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["error"] == "batch failed"
