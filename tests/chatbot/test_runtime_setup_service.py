#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
runtime_setup_service 유틸 회귀 테스트
"""

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from chatbot.runtime_setup_service import (
    close_client,
    create_genai_client,
    get_user_profile,
    init_models,
    init_user_profile_from_env,
    load_stock_map,
    clear_stock_map_cache,
    resolve_active_client,
    resolve_api_key,
    update_user_profile,
)


class _FakeLogger:
    def warning(self, *args, **kwargs):
        _ = (args, kwargs)

    def debug(self, *args, **kwargs):
        _ = (args, kwargs)

    def info(self, *args, **kwargs):
        _ = (args, kwargs)

    def error(self, *args, **kwargs):
        _ = (args, kwargs)


class _FakeMemory:
    def __init__(self):
        self.memories = {}

    def add(self, key, value):
        self.memories[key] = value

    def get(self, key):
        if key not in self.memories:
            return None
        return {"value": self.memories[key]}

    def update(self, key, value):
        self.memories[key] = value


@pytest.fixture(autouse=True)
def _clear_runtime_setup_cache():
    clear_stock_map_cache()
    yield
    clear_stock_map_cache()


def test_resolve_api_key_priority(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1")
    monkeypatch.setenv("GOOGLE_API_KEY", "g2")
    monkeypatch.setenv("ZAI_API_KEY", "z1")
    assert resolve_api_key("explicit") == "explicit"
    assert resolve_api_key(None) == "g1"


def test_init_models_uses_first_when_current_missing(monkeypatch):
    monkeypatch.setenv("CHATBOT_AVAILABLE_MODELS", "m1,m2")
    models, current = init_models("missing", "default")
    assert models == ["m1", "m2"]
    assert current == "m1"


def test_create_genai_client_with_factory_success():
    logger = _FakeLogger()
    client = create_genai_client(
        api_key="k",
        gemini_available=True,
        user_id="u1",
        logger=logger,
        client_factory=lambda api_key: {"client_key": api_key},
    )
    assert client == {"client_key": "k"}


def test_create_genai_client_returns_none_when_unavailable():
    logger = _FakeLogger()
    client = create_genai_client(
        api_key="k",
        gemini_available=False,
        user_id="u1",
        logger=logger,
    )
    assert client is None


def test_resolve_active_client_error_on_bad_api_key():
    logger = _FakeLogger()

    def _raise(_api_key):
        raise RuntimeError("bad")

    client, err = resolve_active_client(
        current_client=None,
        api_key="bad",
        logger=logger,
        client_factory=_raise,
    )
    assert client is None
    assert "API Key 오류" in err


def test_resolve_active_client_without_any_client_returns_guide():
    logger = _FakeLogger()
    client, err = resolve_active_client(
        current_client=None,
        api_key=None,
        logger=logger,
    )
    assert client is None
    assert "AI 모델이 설정되지 않았습니다" in err


def test_load_stock_map_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "korean_stocks_list.csv"
    csv_path.write_text("name,ticker\n삼성전자,005930\n", encoding="utf-8")

    stock_map, ticker_map = load_stock_map(tmp_path, _FakeLogger())
    assert stock_map["삼성전자"] == "005930"
    assert ticker_map["005930"] == "삼성전자"


def test_load_stock_map_reuses_sqlite_cache_after_memory_clear(monkeypatch, tmp_path: Path):
    csv_path = tmp_path / "korean_stocks_list.csv"
    csv_path.write_text("name,ticker\n삼성전자,005930\n하이닉스,000660\n", encoding="utf-8")

    first_stock_map, first_ticker_map = load_stock_map(tmp_path, _FakeLogger())
    assert first_stock_map["삼성전자"] == "005930"
    assert first_ticker_map["000660"] == "하이닉스"

    clear_stock_map_cache()
    monkeypatch.setattr(
        pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite cache")),
    )

    second_stock_map, second_ticker_map = load_stock_map(tmp_path, _FakeLogger())
    assert second_stock_map == first_stock_map
    assert second_ticker_map == first_ticker_map

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM chatbot_stock_map_cache
            WHERE source_path = ?
            """,
            (str(csv_path.resolve()),),
        )
        row = cursor.fetchone()
    assert row and row[0] >= 1


def test_profile_init_get_update(monkeypatch):
    logger = _FakeLogger()
    memory = _FakeMemory()
    monkeypatch.setenv("USER_PROFILE", "공격적 투자자")

    init_user_profile_from_env(memory, logger)
    profile = get_user_profile(memory)
    assert profile["persona"] == "공격적 투자자"

    updated = update_user_profile(memory, "테스터", "중립")
    assert updated == {"name": "테스터", "persona": "중립"}
    profile2 = get_user_profile(memory)
    assert profile2["name"] == "테스터"
    assert profile2["persona"] == "중립"


def test_close_client_noop_when_none():
    close_client(None, _FakeLogger())
