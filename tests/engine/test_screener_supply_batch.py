#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대량 수급 조회의 호출수·동시성·후보 경계."""
from datetime import datetime
from types import SimpleNamespace
import threading

import pandas as pd
import pytest

from services import investor_trend_5day_service as service
from engine.screener import SmartMoneyScreener


def test_four_references_enter_together_without_reloading_csv(monkeypatch, tmp_path):
    batch = getattr(service, "get_investor_trends_5day_for_tickers", None)
    assert callable(batch), "bounded batch API is missing"
    barrier = threading.Barrier(4)
    calls, loads = [], []
    def load(**kwargs):
        loads.append(threading.get_ident())
        return {}
    def fetch(**kwargs):
        calls.append(kwargs["ticker"])
        barrier.wait(timeout=3)
        return {"foreign": 50, "institution": 100, "latest_date": "2026-09-18",
                "details": [{"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20} for _ in range(5)]}
    service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(service, "_get_or_build_trend_map", load)
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", fetch)
    result = batch(tickers=["000001", "000002", "000003", "000004"], data_dir=str(tmp_path), target_datetime="2026-09-18")
    assert len(result) == len(calls) == 4
    assert loads == [threading.get_ident()]


@pytest.mark.parametrize("limit, expected", [(3, ["000001", "000003"]), (0, []), (-1, [])])
def test_historical_cutoff_does_not_refill_short_price_candidate(monkeypatch, limit, expected):
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 9, 18)
    screener.target_date = "2026-09-18"
    screener.stocks_df = pd.DataFrame([{"ticker": f"{i:06d}", "name": "test", "market": "KOSPI"} for i in range(1, 5)])
    screener.prices_df = pd.DataFrame([{"ticker": "000001"}])  # 비면 [VCP-049] 가 실패로 본다. 분석은 아래 인덱스를 쓴다
    screener.inst_df = pd.DataFrame()
    screener.market_gate = SimpleNamespace(analyze=lambda: {"status": "중립", "is_gate_open": True})
    screener._prices_by_ticker_target = {f"{i:06d}": pd.DataFrame({"close": [100] * (19 if i == 2 else 20)}) for i in range(1, 5)}
    monkeypatch.setattr(screener, "_load_data", lambda: None)
    monkeypatch.setattr(screener, "_detect_vcp_pattern", lambda *args: SimpleNamespace(is_vcp=False))
    monkeypatch.setattr(screener, "_calculate_supply_score", lambda *args: (_ for _ in ()).throw(AssertionError("single supply query used")))
    import engine.screener as module
    calls = []
    def batch(**kwargs):
        calls.extend(kwargs["tickers"])
        return {ticker: None for ticker in kwargs["tickers"]}
    monkeypatch.setattr(module, "get_investor_trends_5day_for_tickers", batch, raising=False)
    # Finishing must receive missing supply exactly once, even for VCP-false candidates.
    finished = []
    def finish(prepared, supply):
        finished.append((prepared[0]["ticker"], supply))
        return {"is_vcp": False}
    monkeypatch.setattr(screener, "_finish_stock_analysis", finish, raising=False)
    screener.run_screening(max_stocks=limit)
    assert calls == expected
    assert [item[0] for item in finished] == calls


def test_batch_only_fetches_missing_csv_and_deduplicates(monkeypatch, tmp_path):
    good = {"foreign": 50, "institution": 100, "latest_date": "2026-09-18", "days": 5,
            "details": [{"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20} for _ in range(5)]}
    monkeypatch.setattr(service, "_get_or_build_trend_map", lambda **kw: {"005930": good})
    calls = []
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", lambda **kw: calls.append(kw["ticker"]) or None)
    service.clear_investor_trend_5day_memory_cache()
    result = service.get_investor_trends_5day_for_tickers(
        tickers=["5930", "005930", "000001", "000001"], data_dir=str(tmp_path), target_datetime="2026-09-18")
    assert calls == ["000001"]
    assert result["005930"]["foreign"] == 50
    assert result["000001"] is None
    with pytest.raises(ValueError):
        service.get_investor_trends_5day_for_tickers(tickers=["005930"] * 5, data_dir=str(tmp_path), target_datetime="2026-09-18")


def test_prepared_batch_results_equal_original_single_analysis(monkeypatch, tmp_path):
    import engine.screener as module
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 9, 18)
    screener.target_date = "2026-09-18"
    candidates = [{"ticker": code, "name": "동등성", "market": "KOSPI"} for code in ["000001", "000002", "000001"]]
    screener._prices_by_ticker_target = {code: pd.DataFrame({"close": [100] * 20, "volume": [1000] * 20}) for code in ["000001", "000002"]}
    monkeypatch.setattr(screener, "_detect_vcp_pattern", lambda *args: SimpleNamespace(
        is_vcp=True, vcp_score=80, entry_price=100, contraction_ratio=0.5))
    trend = {"foreign": 50, "institution": 100,
             "details": [{"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20} for _ in range(5)]}
    monkeypatch.setattr(module, "get_investor_trend_5day_for_ticker", lambda **kw: trend)
    monkeypatch.setattr(module, "get_investor_trends_5day_for_tickers", lambda **kw: {key: trend for key in kw["tickers"]})
    before = [screener._analyze_stock(stock) for stock in candidates]
    after = list(screener._analyze_candidates(candidates))
    assert before == after
    assert len(after) == 3
    assert all(item is not None for item in after)
