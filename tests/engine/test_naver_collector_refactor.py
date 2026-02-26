#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector 분해 회귀 테스트
"""

import asyncio
import os
import sys
import types
from types import SimpleNamespace

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import engine.collectors.krx as krx_module
from engine.collectors.naver import NaverFinanceCollector
import engine.collectors.naver_pykrx_mixin as pykrx_mixin_module
import engine.collectors.naver_request_mixin as request_mixin_module


def test_request_retries_on_429_then_succeeds(monkeypatch):
    collector = NaverFinanceCollector()
    calls = {"count": 0}

    def _fake_get(_url, headers=None, timeout=10):
        _ = headers, timeout
        calls["count"] += 1
        if calls["count"] == 1:
            return SimpleNamespace(status_code=429, ok=False)
        return SimpleNamespace(status_code=200, ok=True, text="<html></html>")

    monkeypatch.setattr(request_mixin_module.requests, "get", _fake_get)
    monkeypatch.setattr(request_mixin_module.time, "sleep", lambda _v: None)

    response = collector._request("https://finance.naver.com/item/main.naver?code=005930")
    assert response is not None
    assert response.ok is True
    assert calls["count"] == 2


def test_extractors_fill_expected_fields():
    from bs4 import BeautifulSoup

    collector = NaverFinanceCollector()
    result = collector._create_empty_result_dict("005930")
    html = """
    <html>
      <div class="wrap_company"><h2><a>삼성전자</a></h2></div>
      <img class="kospi" alt="코스피"/>
      <p class="no_today"><span class="blind">70,000</span></p>
      <td class="first"><span class="blind">69,000</span></td>
      <table class="no_info">
        <td><span class="blind">0</span></td>
        <td><span class="blind">71,000</span></td>
        <td><span class="blind">0</span></td>
        <td><span class="blind">68,000</span></td>
      </table>
      <table class="tab_con1">
        <tr><th>52주 최고</th><td><span class="blind">80,000</span></td></tr>
        <tr><th>52주 최저</th><td><span class="blind">50,000</span></td></tr>
      </table>
      <span id="_per">12.3</span>
      <span id="_pbr">1.2</span>
      <span id="_market_sum">2,000억원</span>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    collector._extract_stock_name(soup, result)
    collector._extract_market_info(soup, result)
    collector._extract_current_price(soup, result)
    collector._extract_prev_close(soup, result)
    collector._extract_ohlcv(soup, result)
    collector._extract_52week_range(soup, result)
    collector._extract_indicators(soup, result)
    collector._extract_market_cap(soup, result)

    assert result["name"] == "삼성전자"
    assert result["market"] == "KOSPI"
    assert result["priceInfo"]["current"] == 70000
    assert result["priceInfo"]["prevClose"] == 69000
    assert result["priceInfo"]["high"] == 71000
    assert result["priceInfo"]["low"] == 68000
    assert result["yearRange"]["high_52w"] == 80000
    assert result["yearRange"]["low_52w"] == 50000
    assert result["indicators"]["per"] == 12.3
    assert result["indicators"]["pbr"] == 1.2
    assert result["indicators"]["marketCap"] == 2000 * 100_000_000


def test_naver_pykrx_investor_trend_prefers_unified_service(monkeypatch):
    collector = NaverFinanceCollector(config=SimpleNamespace(DATA_DIR="data"))
    captured: dict[str, object] = {}

    def _fake_get_investor_trend_5day_for_ticker(**kwargs):
        captured.update(kwargs)
        return {
            "foreign": 510_000_000,
            "institution": -210_000_000,
        }

    monkeypatch.setattr(
        pykrx_mixin_module,
        "get_investor_trend_5day_for_ticker",
        _fake_get_investor_trend_5day_for_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", None)

    result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_investor_trend("5930", result))

    assert captured["ticker"] == "005930"
    assert captured["verify_with_references"] is False
    assert result["investorTrend"]["foreign"] == 510_000_000
    assert result["investorTrend"]["institution"] == -210_000_000
    assert result["investorTrend"]["individual"] == 0


def test_naver_pykrx_investor_trend_uses_sqlite_summary_cache(monkeypatch):
    collector = NaverFinanceCollector(config=SimpleNamespace(DATA_DIR="data"))

    monkeypatch.setattr(
        pykrx_mixin_module,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: {
            "foreign": 101,
            "institution": 202,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        },
    )
    monkeypatch.setattr(
        krx_module.KRXCollector,
        "_load_pykrx_supply_summary_snapshot",
        lambda self, *, ticker, end_date: {
            "foreign_buy_5d": 700_000_000,
            "inst_buy_5d": -200_000_000,
            "retail_buy_5d": -500_000_000,
        },
    )
    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_trading_value_by_date=lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("pykrx 조회는 sqlite summary cache hit에서 호출되면 안 됩니다.")
        )
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_investor_trend("5930", result))

    assert result["investorTrend"]["foreign"] == 700_000_000
    assert result["investorTrend"]["institution"] == -200_000_000
    assert result["investorTrend"]["individual"] == -500_000_000


def test_naver_pykrx_fundamental_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = NaverFinanceCollector(config=SimpleNamespace(DATA_DIR="data"))
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    monkeypatch.setattr(
        pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, ticker, target_date: (
                str(tmp_path / f"{ticker}__{target_date}.snapshot"),
                (31, 31),
            )
        ),
    )
    monkeypatch.setattr(
        pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_market_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, target_date: (
                str(tmp_path / f"market__{target_date}.snapshot"),
                (32, 32),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_fundamental_by_ticker(target_date: str):
        calls["count"] += 1
        _ = target_date
        return pd.DataFrame(
            {
                "PER": [10.5],
                "PBR": [1.3],
                "EPS": [4200],
                "BPS": [33000],
                "DIV": [2.1],
            },
            index=["005930"],
        )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_fundamental_by_ticker=_fake_get_market_fundamental_by_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first_result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_fundamental_data("005930", first_result))
    assert calls["count"] == 1
    assert first_result["indicators"]["per"] == 10.5
    assert first_result["indicators"]["pbr"] == 1.3
    assert first_result["indicators"]["eps"] == 4200.0

    with pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    fake_pykrx.stock.get_market_fundamental_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("pykrx 펀더멘탈 조회는 sqlite snapshot hit에서 호출되면 안 됩니다.")
    )

    second_result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_fundamental_data("005930", second_result))
    assert calls["count"] == 1
    assert second_result["indicators"]["per"] == 10.5
    assert second_result["indicators"]["pbr"] == 1.3
    assert second_result["indicators"]["eps"] == 4200.0


def test_naver_pykrx_fundamental_reuses_market_snapshot_sqlite_for_second_ticker(monkeypatch, tmp_path):
    collector = NaverFinanceCollector(config=SimpleNamespace(DATA_DIR="data"))
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    monkeypatch.setattr(
        pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, ticker, target_date: (
                str(tmp_path / ".krx_collector_cache" / "ticker" / f"{ticker}__{target_date}.snapshot"),
                (95, 95),
            )
        ),
    )
    monkeypatch.setattr(
        pykrx_mixin_module.NaverPykrxMixin,
        "_pykrx_market_fundamental_sqlite_context",
        classmethod(
            lambda cls, *, target_date: (
                str(tmp_path / ".krx_collector_cache" / "market" / f"{target_date}.snapshot"),
                (96, 96),
            )
        ),
    )

    calls = {"count": 0}

    def _fake_get_market_fundamental_by_ticker(target_date: str):
        calls["count"] += 1
        _ = target_date
        return pd.DataFrame(
            {
                "PER": [10.5, 8.2],
                "PBR": [1.3, 0.9],
                "EPS": [4200, 3100],
                "BPS": [33000, 27000],
                "DIV": [2.1, 1.4],
            },
            index=["005930", "000660"],
        )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(
        get_market_fundamental_by_ticker=_fake_get_market_fundamental_by_ticker,
    )
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first_result = collector._create_empty_result_dict("005930")
    asyncio.run(collector._get_fundamental_data("005930", first_result))
    assert calls["count"] == 1
    assert first_result["indicators"]["per"] == 10.5

    with pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_fundamental_cache.clear()
    with pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache_lock:
        pykrx_mixin_module.NaverPykrxMixin._pykrx_market_fundamental_cache.clear()

    fake_pykrx.stock.get_market_fundamental_by_ticker = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("시장 펀더멘탈 sqlite snapshot hit에서는 pykrx 재호출이 없어야 합니다.")
    )

    second_result = collector._create_empty_result_dict("000660")
    asyncio.run(collector._get_fundamental_data("000660", second_result))
    assert calls["count"] == 1
    assert second_result["indicators"]["per"] == 8.2
    assert second_result["indicators"]["pbr"] == 0.9
    assert second_result["indicators"]["eps"] == 3100.0


def test_get_financials_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = NaverFinanceCollector()
    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    monkeypatch.setattr(
        NaverFinanceCollector,
        "_current_cache_slot",
        classmethod(lambda cls, now=None: "202602261500"),
    )
    monkeypatch.setattr(
        NaverFinanceCollector,
        "_cache_sqlite_context",
        classmethod(
            lambda cls, *, namespace, code, cache_slot: (
                str(tmp_path / ".naver_finance_cache" / namespace / f"{code}__{cache_slot}.snapshot"),
                (71, 81),
            )
        ),
    )

    html = """
    <html>
      <table class="gHead01">
        <tr><th>매출액</th><td>1,000</td></tr>
        <tr><th>영업이익</th><td>200</td></tr>
        <tr><th>당기순이익</th><td>150</td></tr>
      </table>
    </html>
    """
    collector._request = lambda *_a, **_k: SimpleNamespace(status_code=200, ok=True, text=html)

    first = asyncio.run(collector.get_financials("5930"))
    assert first["revenue"] == 1000 * 100_000_000
    assert first["operatingProfit"] == 200 * 100_000_000
    assert first["netIncome"] == 150 * 100_000_000

    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    collector._request = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("sqlite financial cache should be reused")
    )

    second = asyncio.run(collector.get_financials("005930"))
    assert second == first


def test_get_themes_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = NaverFinanceCollector()
    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    monkeypatch.setattr(
        NaverFinanceCollector,
        "_current_cache_slot",
        classmethod(lambda cls, now=None: "202602261500"),
    )
    monkeypatch.setattr(
        NaverFinanceCollector,
        "_cache_sqlite_context",
        classmethod(
            lambda cls, *, namespace, code, cache_slot: (
                str(tmp_path / ".naver_finance_cache" / namespace / f"{code}__{cache_slot}.snapshot"),
                (72, 82),
            )
        ),
    )

    html = """
    <html>
      <div class="sub_section"><td><a>반도체</a></td></div>
      <div class="section trade_compare"><em><a>전기전자</a></em></div>
      <div class="wrap_company"><a>KOSPI</a><a>AI</a></div>
    </html>
    """
    collector._request = lambda *_a, **_k: SimpleNamespace(status_code=200, ok=True, text=html)

    first = asyncio.run(collector.get_themes("5930"))
    assert first == ["반도체", "전기전자", "AI"]

    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    collector._request = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("sqlite themes cache should be reused")
    )

    second = asyncio.run(collector.get_themes("005930"))
    assert second == ["반도체", "전기전자", "AI"]


def test_get_stock_detail_info_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    collector = NaverFinanceCollector()
    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    monkeypatch.setattr(
        NaverFinanceCollector,
        "_current_cache_slot",
        classmethod(lambda cls, now=None: "202602261500"),
    )
    monkeypatch.setattr(
        NaverFinanceCollector,
        "_cache_sqlite_context",
        classmethod(
            lambda cls, *, namespace, code, cache_slot: (
                str(tmp_path / ".naver_finance_cache" / namespace / f"{code}__{cache_slot}.snapshot"),
                (73, 83),
            )
        ),
    )

    html = """
    <html>
      <div class="wrap_company"><h2><a>삼성전자</a></h2></div>
      <img class="kospi" alt="코스피"/>
      <p class="no_today"><span class="blind">70,000</span></p>
      <td class="first"><span class="blind">69,000</span></td>
      <table class="no_info">
        <td><span class="blind">0</span></td>
        <td><span class="blind">71,000</span></td>
        <td><span class="blind">0</span></td>
        <td><span class="blind">68,000</span></td>
      </table>
    </html>
    """
    collector._request = lambda *_a, **_k: SimpleNamespace(status_code=200, ok=True, text=html)
    monkeypatch.setattr(
        collector,
        "_get_investor_trend",
        lambda *_a, **_k: asyncio.sleep(0),
    )
    monkeypatch.setattr(
        collector,
        "_get_fundamental_data",
        lambda *_a, **_k: asyncio.sleep(0),
    )

    first = asyncio.run(collector.get_stock_detail_info("5930"))
    assert first is not None
    assert first["code"] == "005930"
    assert first["name"] == "삼성전자"

    with collector._naver_cache_lock:
        collector._naver_cache.clear()

    collector._request = lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("sqlite detail_info cache should be reused")
    )
    second = asyncio.run(collector.get_stock_detail_info("005930"))
    assert second is not None
    assert second["code"] == "005930"
    assert second["name"] == "삼성전자"


def test_generator_runtime_mixin_prefers_modular_naver_collector():
    import engine.generator_runtime_mixin as runtime_mixin_module
    from engine.collectors.naver import NaverFinanceCollector as ModularNaverCollector

    assert runtime_mixin_module.NaverFinanceCollector is ModularNaverCollector


def test_collectors_module_exposes_modular_naver_collector():
    import engine.collectors as collectors_module
    from engine.collectors.naver import NaverFinanceCollector as ModularNaverCollector

    assert collectors_module.NaverFinanceCollector is ModularNaverCollector
