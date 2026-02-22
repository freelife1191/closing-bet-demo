#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_service 유틸 회귀 테스트
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.data_service as data_service
from chatbot.data_service import (
    build_daily_suggestions_cache_key,
    build_daily_suggestions_prompt,
    build_watchlist_suggestions_text,
    default_daily_suggestions,
    fetch_market_gate,
    fetch_mock_data,
    get_cached_daily_suggestions,
    get_cached_data,
)


class _FakeMemory:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        _ = key
        return self.value


class _FakeBot:
    def __init__(self, data_fetcher=None):
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60
        self.data_fetcher = data_fetcher


def test_get_cached_data_uses_fetcher_and_cache():
    calls = {"count": 0}

    def _fetch():
        calls["count"] += 1
        return {"market": {"ok": True}, "vcp_stocks": [], "sector_scores": {}}

    bot = _FakeBot(data_fetcher=_fetch)
    first = get_cached_data(bot)
    second = get_cached_data(bot)

    assert first["market"]["ok"] is True
    assert second["market"]["ok"] is True
    assert calls["count"] == 1


def test_get_cached_data_falls_back_to_mock_when_fetcher_fails():
    def _raise():
        raise RuntimeError("boom")

    bot = _FakeBot(data_fetcher=_raise)
    result = get_cached_data(bot)
    assert result == {"market": {}, "vcp_stocks": [], "sector_scores": {}}


def test_get_cached_data_refreshes_when_cache_is_older_than_a_day():
    calls = {"count": 0}

    def _fetch():
        calls["count"] += 1
        return {"market": {"ok": True}, "vcp_stocks": [], "sector_scores": {}}

    bot = _FakeBot(data_fetcher=_fetch)
    bot._data_cache = {"market": {"stale": True}, "vcp_stocks": [], "sector_scores": {}}
    bot._cache_timestamp = datetime.now() - timedelta(days=1)

    result = get_cached_data(bot)
    assert result["market"]["ok"] is True
    assert calls["count"] == 1


def test_fetch_market_gate_reads_json(tmp_path: Path):
    data_dir = tmp_path
    (data_dir / "market_gate.json").write_text(
        '{"status": "GREEN", "total_score": 9}', encoding="utf-8"
    )
    result = fetch_market_gate(data_dir)
    assert result["status"] == "GREEN"
    assert result["total_score"] == 9


def test_fetch_market_gate_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    data_dir = tmp_path
    target = data_dir / "market_gate.json"
    target.write_text('{"status": "GREEN"}', encoding="utf-8")

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"status": "YELLOW", "total_score": 7}

    monkeypatch.setattr(data_service, "load_json_payload_from_path", _loader)

    result = data_service.fetch_market_gate(data_dir)
    assert captured["path"] == str(target)
    assert result == {"status": "YELLOW", "total_score": 7}


def test_fetch_market_gate_returns_empty_for_non_dict_payload(monkeypatch, tmp_path: Path):
    data_dir = tmp_path
    (data_dir / "market_gate.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(data_service, "load_json_payload_from_path", lambda _path: [])

    assert data_service.fetch_market_gate(data_dir) == {}


def test_get_cached_daily_suggestions_respects_ttl():
    now = datetime.now()
    cached = {
        "updated_at": (now - timedelta(minutes=10)).isoformat(),
        "value": [{"title": "ok"}],
    }
    memory = _FakeMemory(cached)
    assert get_cached_daily_suggestions(memory, "k", now) == [{"title": "ok"}]

    expired = {
        "updated_at": (now - timedelta(hours=2)).isoformat(),
        "value": [{"title": "old"}],
    }
    memory_expired = _FakeMemory(expired)
    assert get_cached_daily_suggestions(memory_expired, "k", now) is None


def test_build_watchlist_suggestions_text_formats_items():
    stock_map = {"삼성전자": "005930"}

    def _format(name, ticker):
        return f"{name}-{ticker}"

    result = build_watchlist_suggestions_text(["삼성전자"], stock_map, _format)
    assert "삼성전자-005930" in result

    no_match = build_watchlist_suggestions_text(["없는종목"], stock_map, _format)
    assert "데이터 없음" in no_match


def test_build_daily_suggestions_prompt_includes_jongga_by_persona():
    prompt_with_jongga = build_daily_suggestions_prompt(
        persona=None,
        market_summary="MKT",
        vcp_text="VCP",
        news_text="NEWS",
        watchlist_text="WATCH",
        fetch_jongga_data_fn=lambda: "JONGGA",
    )
    assert "JONGGA" in prompt_with_jongga

    prompt_vcp = build_daily_suggestions_prompt(
        persona="vcp",
        market_summary="MKT",
        vcp_text="VCP",
        news_text="NEWS",
        watchlist_text="WATCH",
        fetch_jongga_data_fn=lambda: "JONGGA",
    )
    assert "JONGGA" not in prompt_vcp


def test_build_daily_suggestions_prompt_prefers_preloaded_jongga_text():
    calls = {"count": 0}

    def _fetch():
        calls["count"] += 1
        return "FETCHED_JONGGA"

    prompt = build_daily_suggestions_prompt(
        persona=None,
        market_summary="MKT",
        vcp_text="VCP",
        news_text="NEWS",
        watchlist_text="WATCH",
        fetch_jongga_data_fn=_fetch,
        jongga_text="PRELOADED_JONGGA",
    )

    assert "PRELOADED_JONGGA" in prompt
    assert calls["count"] == 0


def test_build_cache_key_and_defaults():
    key = build_daily_suggestions_cache_key(["B", "A"], None)
    assert key == "daily_suggestions_default_A_B"

    defaults = default_daily_suggestions()
    assert len(defaults) == 5
    assert defaults[0]["title"] == "시장 현황"


def test_fetch_mock_data_shape():
    data = fetch_mock_data()
    assert "market" in data
    assert "vcp_stocks" in data
