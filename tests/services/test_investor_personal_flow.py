#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""개인 수급의 관측된 0과 자료 없음을 구분한다."""
import pytest

from services import investor_trend_5day_service as service
from services.kr_market_stock_detail_service import _normalize_stock_detail_payload


def payload(value=0):
    return {"foreign": 50, "institution": 100, "days": 5, "latest_date": "2026-09-18",
            "individual": None if value is None else value * 5,
            "details": [{"date": f"2026-09-{day}", "netForeignerBuyVolume": 10,
                         "netInstitutionBuyVolume": 20, "netIndividualsBuyVolume": value}
                        for day in range(18, 13, -1)]}


@pytest.mark.parametrize("value", [0, -500, 500, None])
def test_fresh_personal_value_survives_normalization(value):
    result = service._normalize_external_trend_payload(payload(value), source="pykrx")
    assert result.get("individual", "missing") == (None if value is None else value * 5)


def test_unmarked_complete_detail_cache_does_not_assert_zero():
    cached = {"code": "005930", "investorTrend": {"individual": 0, "foreign": 123}}
    result = _normalize_stock_detail_payload(cached)
    assert result["investorTrend"]["individual"] is None
    assert result["investorTrend"]["foreign"] == 123
    assert cached["investorTrend"]["individual"] == 0


@pytest.mark.parametrize("bad", [True, float("inf"), float("nan"), "bad", 1.5])
def test_marked_detail_cache_still_validates_personal_number(bad):
    cached = {"code": "005930", "investorTrend": {"individual": bad, "individual_schema": 1}}
    assert _normalize_stock_detail_payload(cached)["investorTrend"]["individual"] is None


def test_marked_detail_integral_float_is_normalized_to_integer():
    cached = {"code": "005930", "investorTrend": {"individual": 1.0, "individual_schema": 1}}
    value = _normalize_stock_detail_payload(cached)["investorTrend"]["individual"]
    assert type(value) is int and value == 1


@pytest.mark.parametrize("bad", [True, 1.5, float("inf"), float("nan"), "bad", None])
def test_collector_cache_bad_personal_value_keeps_foreign_and_institution(bad):
    from engine.collectors import KRXCollector
    result = KRXCollector._deserialize_pykrx_supply_payload({
        "foreign_buy_5d": 123, "inst_buy_5d": 456, "retail_buy_5d": bad, "individual_schema": 1,
    })
    assert result is not None
    assert result["foreign_buy_5d"] == 123
    assert result["inst_buy_5d"] == 456
    assert result["retail_buy_5d"] is None


@pytest.mark.parametrize("bad", [None, True, float("nan"), float("inf"), "invalid"])
def test_one_invalid_personal_day_makes_value_unavailable(bad):
    data = payload(50)
    data["details"][2]["netIndividualsBuyVolume"] = bad
    assert service._normalize_external_trend_payload(data, source="pykrx")["individual"] is None


@pytest.mark.parametrize("mutation", ["short", "duplicate", "missing", "outside"])
def test_personal_dates_must_cover_selected_five_days(mutation):
    data = payload(10)
    if mutation == "short":
        data["details"].pop()
    elif mutation == "duplicate":
        data["details"][1]["date"] = data["details"][0]["date"]
    elif mutation == "missing":
        data["details"][1].pop("date")
    else:
        data["details"][1]["date"] = "2026-09-19"
    assert service._normalize_external_trend_payload(data, source="pykrx")["individual"] is None


def test_legacy_and_new_reference_cache_decode():
    data = payload(0)
    old = service._normalize_external_trend_payload(data, source="pykrx", from_cache=True)
    assert old["individual"] is None
    new = service._normalize_external_trend_payload(data, source="pykrx")
    assert new["individual_schema"] == 1
    assert service._normalize_external_trend_payload(new, source="pykrx", from_cache=True)["individual"] == 0


def test_normalized_details_preserve_the_selected_dates():
    data = payload(10)
    normalized = service._normalize_external_trend_payload(data, source="pykrx")
    assert [row.get("date") for row in normalized["details"]] == [row["date"] for row in data["details"]]


def test_personal_cache_cannot_substitute_an_older_day_with_same_latest_date():
    data = payload(10)
    data["individual_schema"] = 1
    data["individual_details"] = [dict(row) for row in data["details"]]
    data["individual_details"][-1]["date"] = "2020-01-01"
    result = service._normalize_external_trend_payload(data, source="pykrx", from_cache=True)
    assert result["individual"] is None


def test_toss_personal_amount_is_not_multiplied_twice():
    from engine.toss_collector_metric_parsers import parse_investor_trend
    data = payload(-10)
    for row in data["details"]:
        row["close"] = 100
    parsed = parse_investor_trend({"result": {"body": data["details"]}}, days=5)
    normalized = service._normalize_external_trend_payload(parsed, source="toss")
    assert normalized["individual"] == -5000
    assert service._normalize_external_trend_payload(normalized, source="toss", from_cache=True)["individual"] == -5000


def test_complete_detail_sqlite_preserves_new_zero_and_legacy_unknown(tmp_path):
    import logging
    from services import kr_market_stock_detail_service as detail
    kwargs = dict(ticker_padded="005930", cache_slot="test", data_dir=str(tmp_path), logger=logging.getLogger(__name__))
    for marker, expected in [(0, None), (1, 0)]:
        source = {"code": "005930", "investorTrend": {"individual": 0, "individual_schema": marker}}
        detail._save_cached_stock_detail_payload(**kwargs, payload=source)
        detail._STOCK_DETAIL_CACHE.clear()
        assert detail._load_cached_stock_detail_payload(**kwargs)["investorTrend"]["individual"] is expected
