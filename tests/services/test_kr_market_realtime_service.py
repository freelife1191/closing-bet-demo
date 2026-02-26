#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Realtime Service 단위 테스트
"""

import logging

from services.kr_market_realtime_service import (
    _build_toss_detail_payload,
    _to_market_code,
    _fetch_small_batch_prices,
    fetch_realtime_prices,
)


def test_fetch_small_batch_prices_normalizes_ticker_and_reads_price(monkeypatch):
    def fake_fetch_stock_price(ticker):
        return {"price": 10000 + int(ticker[-1])}

    monkeypatch.setattr("engine.data_sources.fetch_stock_price", fake_fetch_stock_price)

    prices = _fetch_small_batch_prices(["5930", "000660"], logging.getLogger(__name__))

    assert prices["005930"] == 10000.0
    assert prices["000660"] == 10000.0


def test_fetch_small_batch_prices_sets_zero_on_exception(monkeypatch):
    def fake_fetch_stock_price(ticker):
        if ticker == "005930":
            raise RuntimeError("boom")
        return {"price": 71000}

    monkeypatch.setattr("engine.data_sources.fetch_stock_price", fake_fetch_stock_price)

    prices = _fetch_small_batch_prices(["005930", "000660"], logging.getLogger(__name__))

    assert prices["005930"] == 0.0
    assert prices["000660"] == 71000.0


def test_fetch_realtime_prices_uses_small_batch_path(monkeypatch):
    called = {"small": False}

    def fake_small_batch(tickers, _logger, **kwargs):
        assert kwargs.get("normalize_input") is False
        called["small"] = True
        return {str(t).zfill(6): 1.0 for t in tickers}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_small_batch_prices",
        fake_small_batch,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("SQLite fallback should be skipped when small batch prices are complete")
        ),
    )

    result = fetch_realtime_prices(
        tickers=["005930"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert called["small"] is True
    assert result == {"005930": 1.0}


def test_fetch_realtime_prices_small_batch_uses_sqlite_fallback(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_small_batch_prices",
        lambda _tickers, _logger, **_kwargs: {"005930": 0.0, "000660": 71000.0},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda _tickers, **_kwargs: {"005930": 70000.0},
    )

    def _fake_save(prices, **kwargs):
        captured["prices"] = dict(prices)
        captured["source"] = kwargs.get("source")

    monkeypatch.setattr(
        "services.kr_market_realtime_service._save_realtime_prices_to_cache",
        _fake_save,
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert result["005930"] == 70000.0
    assert result["000660"] == 71000.0
    assert captured["source"] == "small_batch"
    assert captured["prices"] == {"005930": 70000.0, "000660": 71000.0}


def test_fetch_realtime_prices_small_batch_queries_sqlite_for_unresolved_tickers_only(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_small_batch_prices",
        lambda _tickers, _logger, **_kwargs: {
            "005930": 70000.0,
            "000660": 0.0,
            "035420": 0.0,
        },
    )

    def _fake_load_cached(tickers, **_kwargs):
        captured["cache_lookup_tickers"] = list(tickers)
        return {"000660": 120000.0}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        _fake_load_cached,
    )

    monkeypatch.setattr(
        "services.kr_market_realtime_service._save_realtime_prices_to_cache",
        lambda *_args, **_kwargs: None,
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert captured["cache_lookup_tickers"] == ["000660", "035420"]
    assert result["005930"] == 70000.0
    assert result["000660"] == 120000.0
    assert result["035420"] == 0.0


def test_fetch_realtime_prices_passes_cached_latest_price_map_to_fill(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda *_args, **_kwargs: {},
    )

    def _fake_fill(tickers, prices, _load_csv_file, latest_price_map=None, **kwargs):
        assert kwargs.get("normalize_input") is False
        captured["tickers"] = tickers
        captured["latest_price_map"] = latest_price_map
        prices["005930"] = float((latest_price_map or {}).get("005930", 0))

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        _fake_fill,
    )

    result = fetch_realtime_prices(
        tickers=["005930", "5930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        load_latest_price_map=lambda: {"005930": 123.0},
    )

    assert captured["latest_price_map"] == {"005930": 123.0}
    assert result["005930"] == 123.0


def test_fetch_realtime_prices_bulk_chain_uses_sqlite_fallback_before_csv(monkeypatch):
    captured: dict[str, object] = {}
    saved_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {"005930": 50000.0},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda _tickers, **_kwargs: {"000660": 120000.0},
    )

    def _fake_save(prices, **kwargs):
        saved_calls.append(
            {
                "prices": dict(prices),
                "source": kwargs.get("source"),
            }
        )

    monkeypatch.setattr(
        "services.kr_market_realtime_service._save_realtime_prices_to_cache",
        _fake_save,
    )

    def _fake_fill(tickers, prices, _load_csv_file, latest_price_map=None, **kwargs):
        captured["fill_tickers"] = list(tickers)
        captured["price_before_fill"] = dict(prices)
        del latest_price_map, kwargs

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        _fake_fill,
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    assert saved_calls[0]["source"] == "bulk_chain"
    assert saved_calls[0]["prices"] == {"005930": 50000.0}
    assert saved_calls[1]["source"] == "bulk_resolved"
    assert saved_calls[1]["prices"] == {"000660": 120000.0}
    assert captured["price_before_fill"]["005930"] == 50000.0
    assert captured["price_before_fill"]["000660"] == 120000.0
    assert result["000660"] == 120000.0


def test_fetch_realtime_prices_bulk_chain_skips_csv_when_cache_fallback_completes_prices(monkeypatch):
    saved_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {"005930": 50000.0},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda _tickers, **_kwargs: {
            "000660": 120000.0,
            "035420": 210000.0,
            "051910": 320000.0,
            "068270": 430000.0,
            "207940": 540000.0,
        },
    )

    def _fake_save(prices, **kwargs):
        saved_calls.append(
            {
                "source": kwargs.get("source"),
                "prices": dict(prices),
            }
        )

    monkeypatch.setattr(
        "services.kr_market_realtime_service._save_realtime_prices_to_cache",
        _fake_save,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cache fallback으로 가격이 완전히 해소되면 CSV fallback은 생략되어야 합니다.")
        ),
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        load_latest_price_map=lambda: (_ for _ in ()).throw(
            AssertionError("가격이 이미 complete면 latest price map 조회도 생략되어야 합니다.")
        ),
    )

    assert result == {
        "005930": 50000.0,
        "000660": 120000.0,
        "035420": 210000.0,
        "051910": 320000.0,
        "068270": 430000.0,
        "207940": 540000.0,
    }
    assert saved_calls[0]["source"] == "bulk_chain"
    assert saved_calls[0]["prices"] == {"005930": 50000.0}
    assert saved_calls[1]["source"] == "bulk_resolved"
    assert saved_calls[1]["prices"] == {
        "000660": 120000.0,
        "035420": 210000.0,
        "051910": 320000.0,
        "068270": 430000.0,
        "207940": 540000.0,
    }


def test_fetch_realtime_prices_reuses_recent_sqlite_cache_without_second_lookup(monkeypatch):
    cache_calls = {"count": 0}
    requested_tickers: list[list[str]] = []

    def _fake_load_cached(_tickers, **_kwargs):
        cache_calls["count"] += 1
        requested_tickers.append(list(_tickers))
        if cache_calls["count"] == 1:
            return {"000660": 120000.0}
        return {}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        _fake_load_cached,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {"005930": 50000.0},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        lambda _tickers, _prices, _load_csv_file, latest_price_map=None, **_kwargs: None,
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert cache_calls["count"] == 2
    assert requested_tickers[0] == ["005930", "000660", "035420", "051910", "068270", "207940"]
    # 1차 recent cache에서 해결된 000660과 네트워크로 해결된 005930은 2차 조회 대상에서 제외된다.
    assert requested_tickers[1] == ["035420", "051910", "068270", "207940"]
    assert result["005930"] == 50000.0
    assert result["000660"] == 120000.0


def test_fetch_realtime_prices_skips_csv_fallback_when_prices_are_complete(monkeypatch):
    cache_calls = {"count": 0}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {
            "005930": 70000.0,
            "000660": 120000.0,
            "035420": 200000.0,
            "051910": 300000.0,
            "068270": 400000.0,
            "207940": 500000.0,
        },
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda *_args, **_kwargs: cache_calls.__setitem__("count", cache_calls["count"] + 1) or {},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("CSV fallback should be skipped when prices are complete")
        ),
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert result["005930"] == 70000.0
    assert result["207940"] == 500000.0
    # 대량 경로 선행 cache short-circuit 1회만 호출되고, complete 응답이므로 후속 fallback은 생략된다.
    assert cache_calls["count"] == 1


def test_fetch_realtime_prices_skips_latest_map_when_network_result_is_complete(monkeypatch):
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: {
            "005930": 70000.0,
            "000660": 120000.0,
            "035420": 200000.0,
            "051910": 300000.0,
            "068270": 400000.0,
            "207940": 500000.0,
        },
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda _tickers, _prices, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda _tickers, _prices, _load_csv_file, _logger, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("네트워크 결과가 complete면 CSV fallback은 호출되면 안 됩니다.")
        ),
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        load_latest_price_map=lambda: (_ for _ in ()).throw(
            AssertionError("네트워크 결과가 complete면 latest map 로드는 호출되면 안 됩니다.")
        ),
    )

    assert result["005930"] == 70000.0
    assert result["207940"] == 500000.0


def test_fetch_realtime_prices_bulk_short_circuits_when_recent_sqlite_cache_is_complete(monkeypatch):
    expected = {
        "005930": 70000.0,
        "000660": 120000.0,
        "035420": 200000.0,
        "051910": 300000.0,
        "068270": 400000.0,
        "207940": 500000.0,
    }

    monkeypatch.setattr(
        "services.kr_market_realtime_service._load_cached_realtime_prices",
        lambda _tickers, **_kwargs: dict(expected),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("완전한 최근 SQLite 캐시 hit 시 네트워크 bulk 호출은 생략되어야 합니다.")
        ),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("완전한 최근 SQLite 캐시 hit 시 네이버 fallback 호출은 생략되어야 합니다.")
        ),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("완전한 최근 SQLite 캐시 hit 시 yfinance fallback 호출은 생략되어야 합니다.")
        ),
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("완전한 최근 SQLite 캐시 hit 시 CSV fallback 호출은 생략되어야 합니다.")
        ),
    )

    result = fetch_realtime_prices(
        tickers=["005930", "000660", "035420", "051910", "068270", "207940"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert result == expected


def test_fetch_realtime_prices_uses_small_batch_for_duplicated_requests(monkeypatch):
    called = {"small": False, "bulk": False}

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_small_batch_prices",
        lambda tickers, _logger, **_kwargs: called.__setitem__("small", True)
        or {ticker: 10.0 for ticker in tickers},
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        lambda _tickers, _logger, **_kwargs: called.__setitem__("bulk", True) or {},
    )

    result = fetch_realtime_prices(
        tickers=["5930", "005930", "660", "000660", "35420", "035420"],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
    )

    assert called["small"] is True
    assert called["bulk"] is False
    assert result == {"005930": 10.0, "000660": 10.0, "035420": 10.0}


def test_fetch_realtime_prices_normalizes_and_deduplicates_before_bulk_chain(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_bulk(tickers, _logger, **kwargs):
        assert kwargs.get("normalize_input") is False
        captured["bulk"] = list(tickers)
        return {}

    def _fake_naver(tickers, _prices, _logger, **kwargs):
        assert kwargs.get("normalize_input") is False
        captured["naver"] = list(tickers)

    def _fake_yf(tickers, _prices, _load_csv_file, _logger, **kwargs):
        assert kwargs.get("normalize_input") is False
        captured["yf"] = list(tickers)
        captured["has_get_data_path"] = callable(kwargs.get("get_data_path"))
        if callable(kwargs.get("get_data_path")):
            captured["sample_data_path"] = kwargs["get_data_path"]("korean_stocks_list.csv")

    def _fake_fill(tickers, prices, _load_csv_file, latest_price_map=None, **kwargs):
        assert kwargs.get("normalize_input") is False
        captured["fill"] = list(tickers)
        prices["005930"] = float((latest_price_map or {}).get("005930", 0))

    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_toss_bulk_prices",
        _fake_bulk,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_naver_missing_prices",
        _fake_naver,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fetch_yfinance_missing_prices",
        _fake_yf,
    )
    monkeypatch.setattr(
        "services.kr_market_realtime_service._fill_missing_prices_from_csv",
        _fake_fill,
    )

    fetch_realtime_prices(
        tickers=[
            "5930",
            "005930",
            "660",
            "000660",
            "35420",
            "035420",
            "51910",
            "051910",
            "68270",
            "068270",
            "207940",
            "271560",
        ],
        load_csv_file=lambda _name: None,
        logger=logging.getLogger(__name__),
        load_latest_price_map=lambda: {"005930": 123.0},
        get_data_path=lambda filename: f"/tmp/{filename}",
    )

    expected = ["005930", "000660", "035420", "051910", "068270", "207940", "271560"]
    assert captured["bulk"] == expected
    assert captured["naver"] == expected
    assert captured["yf"] == expected
    assert captured["fill"] == expected
    assert captured["has_get_data_path"] is True
    assert captured["sample_data_path"] == "/tmp/korean_stocks_list.csv"


def test_to_market_code_maps_korean_labels():
    assert _to_market_code("코스피") == "KOSPI"
    assert _to_market_code("코스닥") == "KOSDAQ"
    assert _to_market_code(None) == "UNKNOWN"


def test_build_toss_detail_payload_includes_change_pct():
    payload = _build_toss_detail_payload(
        "005930",
        {
            "name": "삼성전자",
            "market": "코스피",
            "price": {
                "current": 110,
                "prev_close": 100,
                "open": 101,
                "high": 112,
                "low": 99,
                "volume": 10,
                "trading_value": 1000,
                "high_52w": 120,
                "low_52w": 80,
                "market_cap": 1_000_000,
            },
            "indicators": {"per": 10, "pbr": 1.2},
            "investor_trend": {"foreign": 10, "institution": -5, "individual": -5},
            "financials": {"revenue": 1, "operating_profit": 2, "net_income": 3},
            "stability": {"debt_ratio": 50, "current_ratio": 120},
        },
    )

    assert payload["code"] == "005930"
    assert payload["market"] == "KOSPI"
    assert round(payload["priceInfo"]["change_pct"], 1) == 10.0
