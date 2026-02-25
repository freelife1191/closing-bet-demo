#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 헬퍼 계약(Contract) 테스트

리팩토링 전/후 동작이 동일해야 하는 판별/재산정 규칙을 고정한다.
"""

import json
import logging
import os
import sys
import types
from datetime import datetime

import pandas as pd
import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market import (
    _apply_gemini_reanalysis_results,
    _apply_vcp_reanalysis_updates,
    _apply_latest_prices_to_jongga_signals,
    _build_jongga_news_analysis_items,
    _build_vcp_stock_payloads,
    _extract_vcp_ai_recommendation,
    _is_jongga_ai_analysis_completed,
    _is_meaningful_ai_reason,
    _is_vcp_ai_analysis_failed,
    _normalize_jongga_signals_for_frontend,
    _normalize_text,
    _recalculate_jongga_grade,
    _recalculate_jongga_grades,
    _select_signals_for_gemini_reanalysis,
    _sort_jongga_signals,
)
from app.routes.kr_market_helpers import (
    _aggregate_cumulative_kpis,
    _build_ai_signals_from_jongga_results,
    _build_cumulative_trade_record,
    _build_vcp_signals_from_dataframe,
    _filter_signals_dataframe_by_date,
    _paginate_items,
    _prepare_cumulative_price_dataframe,
    _should_use_jongga_ai_payload,
)
from services import kr_market_route_service as route_service


TEST_LOGGER = logging.getLogger("tests.kr_market_route_service")


def test_normalize_text_handles_none_and_strip():
    assert _normalize_text(None) == ""
    assert _normalize_text("  abc  ") == "abc"
    assert _normalize_text(123) == "123"


def test_is_meaningful_ai_reason_rejects_placeholders_case_insensitive():
    assert _is_meaningful_ai_reason("분석 실패") is False
    assert _is_meaningful_ai_reason("No Analysis Available.") is False
    assert _is_meaningful_ai_reason("  ") is False
    assert _is_meaningful_ai_reason(None) is False


def test_is_meaningful_ai_reason_accepts_real_reason():
    assert _is_meaningful_ai_reason("기관/외국인 수급 동시 개선") is True


def test_jongga_completed_when_only_llm_reason_exists_without_ai_eval():
    signal = {"score": {"llm_reason": "실적 모멘텀과 수급이 개선됨"}}
    assert _is_jongga_ai_analysis_completed(signal) is True


def test_jongga_not_completed_when_action_invalid_even_if_reason_exists():
    signal = {
        "ai_evaluation": {"action": "STRONG_BUY", "reason": "수급 개선"},
        "score": {},
    }
    assert _is_jongga_ai_analysis_completed(signal) is False


def test_jongga_completed_when_ai_reason_is_placeholder_but_llm_reason_is_valid():
    signal = {
        "ai_evaluation": {"action": "BUY", "reason": "분석 실패"},
        "score": {"llm_reason": "거래대금과 수급이 동반 증가"},
    }
    assert _is_jongga_ai_analysis_completed(signal) is True


def test_jongga_not_completed_for_non_dict_input():
    assert _is_jongga_ai_analysis_completed(None) is False


def test_vcp_failed_for_non_dict_input():
    assert _is_vcp_ai_analysis_failed(None) is True


def test_vcp_failed_when_reason_is_placeholder():
    row = {"ai_action": "BUY", "ai_reason": "-"}
    assert _is_vcp_ai_analysis_failed(row) is True


def test_vcp_failed_when_action_invalid():
    row = {"ai_action": "N/A", "ai_reason": "의미 있는 분석"}
    assert _is_vcp_ai_analysis_failed(row) is True


def test_vcp_not_failed_when_action_and_reason_are_valid():
    row = {"ai_action": "HOLD", "ai_reason": "변동성 수축이 지속되어 관망"}
    assert _is_vcp_ai_analysis_failed(row) is False


def test_recalculate_jongga_grade_promotes_to_s_on_threshold():
    signal = {
        "grade": "A",
        "trading_value": 1_000_000_000_000,
        "change_pct": 3.0,
        "score": {"total": 10},
        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
    }
    grade, changed = _recalculate_jongga_grade(signal)
    assert grade == "S"
    assert changed is True
    assert signal["grade"] == "S"


def test_recalculate_jongga_grade_allows_zero_change_pct():
    signal = {
        "grade": "D",
        "trading_value": 1_000_000_000_000,
        "change_pct": 0.0,
        "score": {"total": 10},
        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
    }
    grade, changed = _recalculate_jongga_grade(signal)
    assert grade == "S"
    assert changed is True
    assert signal["grade"] == "S"


def test_recalculate_jongga_grade_returns_d_when_parse_fails():
    signal = {
        "grade": "D",
        "trading_value": "not-a-number",
        "change_pct": 3.0,
        "score": {"total": 10},
        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
    }
    grade, changed = _recalculate_jongga_grade(signal)
    assert grade == "D"
    assert changed is False


def test_recalculate_jongga_grade_uses_signal_level_supply_fallback_keys():
    signal = {
        "grade": "A",
        "trading_value": 1_000_000_000_000,
        "change_pct": 0.5,
        "score": {"total": 10},
        "foreign_5d": 1_000_000,
        "inst_5d": 2_000_000,
        "score_details": {},
    }
    grade, changed = _recalculate_jongga_grade(signal)
    assert grade == "S"
    assert changed is True
    assert signal["grade"] == "S"


def test_recalculate_jongga_grade_parses_percent_and_currency_strings():
    signal = {
        "grade": "A",
        "trading_value": "1,000,000,000,000원",
        "change_pct": "0.5%",
        "score": {"total": "10"},
        "score_details": {"foreign_net_buy": "1", "inst_net_buy": "1"},
    }

    grade, changed = _recalculate_jongga_grade(signal)

    assert grade == "S"
    assert changed is True
    assert signal["grade"] == "S"


def test_recalculate_jongga_grades_updates_by_grade_and_unknown_grade_count():
    data = {
        "signals": [
            {
                "grade": "D",
                "trading_value": 1_000_000_000_000,
                "change_pct": 3.0,
                "score": {"total": 10},
                "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
            },
            {
                "grade": "Z",
                "trading_value": 1,
                "change_pct": 0,
                "score": {"total": 0},
                "score_details": {"foreign_net_buy": 0, "inst_net_buy": 0},
            },
        ],
        "by_grade": {"S": 0, "A": 0, "B": 0, "C": 0, "D": 2},
    }

    changed = _recalculate_jongga_grades(data)

    assert changed is True
    assert data["by_grade"]["S"] == 1
    assert data["by_grade"]["D"] == 1


def test_recalculate_jongga_grades_returns_false_for_invalid_payload():
    assert _recalculate_jongga_grades({}) is False
    assert _recalculate_jongga_grades({"signals": "invalid"}) is False


def test_sort_jongga_signals_orders_by_grade_then_score():
    signals = [
        {"grade": "A", "score": {"total": 6}, "stock_code": "000001"},
        {"grade": "S", "score": {"total": 5}, "stock_code": "000002"},
        {"grade": "A", "score": {"total": 9}, "stock_code": "000003"},
        {"grade": "D", "score": {"total": 20}, "stock_code": "000004"},
    ]

    _sort_jongga_signals(signals)

    assert [s["stock_code"] for s in signals] == ["000002", "000003", "000001", "000004"]


def test_apply_latest_prices_to_jongga_signals_updates_current_and_return():
    signals = [
        {"ticker": "000001", "entry_price": 10_000},
        {"code": "000002", "close": 20_000},
        {"stock_code": "000003", "entry_price": 0},
    ]
    latest_price_map = {"000001": 10_500, "000002": 19_000}

    updated = _apply_latest_prices_to_jongga_signals(signals, latest_price_map)

    assert updated == 2
    assert signals[0]["current_price"] == 10_500
    assert signals[0]["return_pct"] == 5.0
    assert signals[1]["current_price"] == 19_000
    assert signals[1]["return_pct"] == -5.0
    assert "current_price" not in signals[2]


def test_apply_latest_prices_to_jongga_signals_normalizes_prefixed_ticker():
    signals = [{"ticker": "A005930", "entry_price": 70_000}]
    latest_price_map = {"005930": 71_000}

    updated = _apply_latest_prices_to_jongga_signals(signals, latest_price_map)

    assert updated == 1
    assert signals[0]["current_price"] == 71_000
    assert signals[0]["return_pct"] == round(((71_000 - 70_000) / 70_000) * 100, 2)


def test_normalize_jongga_signals_for_frontend_fills_required_fields():
    signals = [
        {
            "ticker": "1",
            "name": "테스트",
            "score": 7,
            "entry_price": 10_000,
            "current_price": 10_300,
            "ai_action": "BUY",
            "ai_confidence": 70,
            "ai_reason": "근거 있음",
        }
    ]

    _normalize_jongga_signals_for_frontend(signals)
    normalized = signals[0]

    assert normalized["stock_code"] == "000001"
    assert normalized["stock_name"] == "테스트"
    assert normalized["score"]["total"] == 7
    assert normalized["change_pct"] == 3.0
    assert normalized["target_price"] == 10_900
    assert normalized["stop_price"] == 9_500
    assert normalized["ai_evaluation"]["action"] == "BUY"


def test_normalize_jongga_signals_for_frontend_handles_string_supply_values():
    signals = [
        {
            "ticker": "2",
            "name": "문자열수급",
            "score": 5,
            "entry_price": 10_000,
            "current_price": 10_000,
            "foreign_5d": "1200",
            "inst_5d": "-300",
        }
    ]

    _normalize_jongga_signals_for_frontend(signals)

    checklist = signals[0]["checklist"]
    assert checklist["supply_demand"] is True


def test_normalize_jongga_signals_for_frontend_backfills_ticker_and_name_from_stock_fields():
    signals = [
        {
            "stock_code": "5930",
            "stock_name": "삼성전자",
            "score": {"total": 9},
            "entry_price": "100,000",
            "current_price": "101,500",
        }
    ]

    _normalize_jongga_signals_for_frontend(signals)
    normalized = signals[0]

    assert normalized["stock_code"] == "005930"
    assert normalized["ticker"] == "005930"
    assert normalized["stock_name"] == "삼성전자"
    assert normalized["name"] == "삼성전자"
    assert normalized["change_pct"] == 1.5


def test_build_vcp_stock_payloads_maps_numeric_fields_safely():
    rows = [
        {
            "ticker": "1",
            "name": "Alpha",
            "current_price": "10000",
            "score": "7.5",
            "vcp_score": None,
            "contraction_ratio": "x",
        }
    ]

    payloads = _build_vcp_stock_payloads(rows)

    assert len(payloads) == 1
    assert payloads[0]["ticker"] == "000001"
    assert payloads[0]["current_price"] == 10000.0
    assert payloads[0]["score"] == 7.5
    assert payloads[0]["vcp_score"] == 0.0
    assert payloads[0]["contraction_ratio"] == 0.0


def test_extract_vcp_ai_recommendation_valid_and_invalid_cases():
    ai_results = {
        "000001": {
            "gemini_recommendation": {
                "action": "BUY",
                "confidence": "77",
                "reason": "의미 있는 분석",
            }
        },
        "000002": {
            "gemini_recommendation": {
                "action": "N/A",
                "confidence": 0,
                "reason": "분석 실패",
            }
        },
    }

    valid = _extract_vcp_ai_recommendation(ai_results, "000001")
    invalid = _extract_vcp_ai_recommendation(ai_results, "000002")

    assert valid == (True, "BUY", 77, "의미 있는 분석")
    assert invalid == (False, "N/A", 0, "분석 실패")


def test_apply_vcp_reanalysis_updates_writes_success_and_failure_rows():
    import pandas as pd

    signals_df = pd.DataFrame(
        [
            {"ticker": "000001", "ai_action": "", "ai_confidence": 0, "ai_reason": ""},
            {"ticker": "000002", "ai_action": "", "ai_confidence": 0, "ai_reason": ""},
        ]
    )
    failed_rows = [
        (0, {"ticker": "000001"}),
        (1, {"ticker": "000002"}),
    ]
    ai_results = {
        "000001": {
            "gemini_recommendation": {
                "action": "HOLD",
                "confidence": 66,
                "reason": "추가 확인 필요",
            }
        },
        "000002": {
            "gemini_recommendation": {
                "action": "N/A",
                "confidence": 0,
                "reason": "분석 실패",
            }
        },
    }

    updated_count, still_failed_count, recommendations = _apply_vcp_reanalysis_updates(
        signals_df,
        failed_rows,
        ai_results,
    )

    assert updated_count == 1
    assert still_failed_count == 1
    assert recommendations["000001"]["action"] == "HOLD"
    assert signals_df.at[0, "ai_action"] == "HOLD"
    assert signals_df.at[1, "ai_action"] == "N/A"


def test_select_signals_for_gemini_reanalysis_with_target_tickers():
    all_signals = [
        {"stock_code": "000001", "stock_name": "Alpha"},
        {"stock_code": "000002", "stock_name": "Beta"},
    ]

    selected = _select_signals_for_gemini_reanalysis(
        all_signals=all_signals,
        target_tickers=["000002"],
        force_update=False,
    )

    assert len(selected) == 1
    assert selected[0]["stock_code"] == "000002"


def test_select_signals_for_gemini_reanalysis_smart_mode_uses_completion_state():
    all_signals = [
        {"stock_code": "000001", "ai_evaluation": {"action": "BUY", "reason": "완료"}, "score": {}},
        {"stock_code": "000002", "ai_evaluation": {"action": "N/A", "reason": "분석 실패"}, "score": {}},
    ]

    selected = _select_signals_for_gemini_reanalysis(
        all_signals=all_signals,
        target_tickers=[],
        force_update=False,
    )

    assert len(selected) == 1
    assert selected[0]["stock_code"] == "000002"


def test_build_jongga_news_analysis_items_skips_missing_news():
    signals = [
        {"stock_name": "Alpha", "news_items": [{"title": "a"}]},
        {"stock_name": "Beta", "news_items": []},
        {"stock_name": "", "news_items": [{"title": "b"}]},
    ]

    items = _build_jongga_news_analysis_items(signals)

    assert len(items) == 1
    assert items[0]["stock"]["stock_name"] == "Alpha"


def test_apply_gemini_reanalysis_results_matches_name_and_updates_fields():
    signals = [
        {"stock_name": "삼성전자", "stock_code": "005930", "score": {}},
        {"stock_name": "하이닉스", "stock_code": "000660", "score": {}},
    ]
    results_map = {
        "삼성전자 (005930)": {"action": "BUY", "confidence": 80, "reason": "호재", "score": 2},
        "000660": {"action": "HOLD", "confidence": 65, "reason": "관망", "score": 1},
    }

    updated_count = _apply_gemini_reanalysis_results(signals, results_map)

    assert updated_count == 2
    assert signals[0]["score"]["llm_reason"] == "호재"
    assert signals[0]["ai_evaluation"]["action"] == "BUY"
    assert signals[1]["score"]["news"] == 1
    assert signals[1]["ai_evaluation"]["action"] == "HOLD"


def test_filter_signals_dataframe_by_date_prefers_latest_when_date_missing():
    signals_df = pd.DataFrame(
        [
            {"signal_date": "2026-02-20", "ticker": "1"},
            {"signal_date": "2026-02-21", "ticker": "2"},
        ]
    )

    filtered_df, today = _filter_signals_dataframe_by_date(
        signals_df,
        req_date=None,
        default_today="2026-02-19",
    )

    assert today == "2026-02-21"
    assert len(filtered_df) == 1
    assert str(filtered_df.iloc[0]["ticker"]) == "2"


def test_filter_signals_dataframe_by_date_normalizes_datetime_date_values():
    signals_df = pd.DataFrame(
        [
            {"signal_date": "2025-11-26 00:00:00", "ticker": "1"},
            {"signal_date": "2025-11-27 00:00:00", "ticker": "2"},
        ]
    )

    filtered_df, today = _filter_signals_dataframe_by_date(
        signals_df,
        req_date="2025-11-26",
        default_today="2025-11-28",
    )

    assert today == "2025-11-28"
    assert len(filtered_df) == 1
    assert str(filtered_df.iloc[0]["ticker"]) == "1"


def test_build_vcp_signals_from_dataframe_filters_closed_and_low_score():
    signals_df = pd.DataFrame(
        [
            {"ticker": "1", "status": "OPEN", "score": 70, "signal_date": "2026-02-21"},
            {"ticker": "2", "status": "CLOSED", "score": 95, "signal_date": "2026-02-21"},
            {"ticker": "3", "status": "OPEN", "score": 55, "signal_date": "2026-02-21"},
        ]
    )

    signals = _build_vcp_signals_from_dataframe(signals_df)

    assert len(signals) == 1
    assert signals[0]["ticker"] == "000001"
    assert signals[0]["score"] == 70.0


def test_build_ai_signals_from_jongga_results_include_without_ai_option():
    jongga_signals = [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "grade": "S",
            "score": {"total": 11, "llm_reason": "상승 모멘텀"},
            "score_details": {"ai_evaluation": {"action": "BUY", "confidence": 90, "reason": "강세"}},
        },
        {
            "stock_code": "000660",
            "stock_name": "하이닉스",
            "grade": "A",
            "score": {"total": 8},
        },
    ]

    with_ai_only = _build_ai_signals_from_jongga_results(
        jongga_signals,
        include_without_ai=False,
        allow_numeric_score_fallback=True,
    )
    include_all = _build_ai_signals_from_jongga_results(
        jongga_signals,
        include_without_ai=True,
        allow_numeric_score_fallback=False,
    )

    assert len(with_ai_only) == 1
    assert with_ai_only[0]["ticker"] == "005930"
    assert len(include_all) == 2


def test_should_use_jongga_ai_payload_uses_timestamp_priority():
    jongga_data = {"updated_at": "2026-02-21T09:30:00", "signals": [{"stock_code": "1"}]}
    newer_vcp = {"generated_at": "2026-02-21T09:31:00", "signals": [{"ticker": "1"}]}
    older_vcp = {"generated_at": "2026-02-21T09:00:00", "signals": [{"ticker": "1"}]}

    assert _should_use_jongga_ai_payload(jongga_data, older_vcp) is True
    assert _should_use_jongga_ai_payload(jongga_data, newer_vcp) is False


def test_cumulative_trade_record_and_kpi_follow_target_stop_rules():
    raw_price_df = pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "open": 100, "high": 101, "low": 99, "close": 100},
            {"date": "2026-02-21", "ticker": "005930", "open": 101, "high": 110, "low": 100, "close": 108},
            {"date": "2026-02-21", "ticker": "000660", "open": 100, "high": 102, "low": 94, "close": 95},
        ]
    )
    price_df = _prepare_cumulative_price_dataframe(raw_price_df)

    win_signal = {"ticker": "005930", "entry_price": 100, "grade": "S", "name": "삼성전자", "score": {"total": 10}}
    loss_signal = {"ticker": "000660", "entry_price": 100, "grade": "A", "name": "하이닉스", "score": {"total": 8}}

    win_trade = _build_cumulative_trade_record(win_signal, "2026-02-20", price_df)
    loss_trade = _build_cumulative_trade_record(loss_signal, "2026-02-20", price_df)

    assert win_trade["outcome"] == "WIN"
    assert win_trade["roi"] == 9.0
    assert loss_trade["outcome"] == "LOSS"
    assert loss_trade["roi"] == -5.0

    kpi = _aggregate_cumulative_kpis([win_trade, loss_trade], price_df, datetime(2026, 2, 21))
    assert kpi["totalSignals"] == 2
    assert kpi["wins"] == 1
    assert kpi["losses"] == 1
    assert kpi["winRate"] == 50.0


def test_paginate_items_normalizes_invalid_page_limit():
    items = [{"id": i} for i in range(5)]
    page_items, page_meta = _paginate_items(items, page=0, limit=-1)

    assert len(page_items) == 5
    assert page_meta["page"] == 1
    assert page_meta["limit"] == 50


def test_route_service_target_date_ai_payload_prefers_jongga_results():
    payloads = {
        "jongga_v2_results_20260220.json": {
            "signals": [{"stock_code": "000001"}],
            "updated_at": "2026-02-20T09:00:00",
        }
    }

    result = route_service.build_ai_analysis_payload_for_target_date(
        target_date="2026-02-20",
        load_json_file=lambda name: payloads.get(name, {}),
        build_ai_signals_from_jongga_results=lambda *_args, **_kwargs: [{"stock_code": "000001"}],
        normalize_ai_payload_tickers=lambda data: {"normalized": data},
        logger=TEST_LOGGER,
        now=datetime(2026, 2, 21, 9, 0, 0),
    )

    assert result["source"] == "jongga_v2_integrated_history"
    assert result["signal_date"] == "2026-02-20"
    assert result["generated_at"] == "2026-02-20T09:00:00"
    assert len(result["signals"]) == 1


def test_route_service_latest_ai_payload_falls_back_to_kr_ai():
    payloads = {
        "jongga_v2_latest.json": {},
        "ai_analysis_results.json": {},
        "kr_ai_analysis.json": {"signals": [{"ticker": "000001"}]},
    }

    result = route_service.build_latest_ai_analysis_payload(
        load_json_file=lambda name: payloads.get(name, {}),
        should_use_jongga_ai_payload=lambda *_args: False,
        build_ai_signals_from_jongga_results=lambda *_args, **_kwargs: [],
        normalize_ai_payload_tickers=lambda data: {"normalized": True, **data},
        format_signal_date=lambda value: value,
    )

    assert result["normalized"] is True
    assert len(result["signals"]) == 1


def test_route_service_jongga_latest_no_data_payload(tmp_path):
    result = route_service.build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: {},
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=lambda _signals, _price_map: 0,
        logger=TEST_LOGGER,
        now=datetime(2026, 2, 21, 9, 0, 0),
    )

    assert result["status"] == "no_data"
    assert result["signals"] == []
    assert result["date"] == "2026-02-21"


def test_route_service_jongga_latest_updates_prices_and_writes_latest_file(tmp_path):
    latest_payload = {
        "date": "2026-02-21",
        "signals": [{"ticker": "000001", "entry_price": 10000, "grade": "A"}],
    }
    (tmp_path / "daily_prices.csv").write_text(
        "date,ticker,close\n2026-02-21,000001,10150\n",
        encoding="utf-8",
    )

    flags = {"sorted": False, "normalized": False, "price_updated": False}

    def _recalculate(payload):
        payload["recalculated"] = True
        return True

    def _sort(_signals):
        flags["sorted"] = True

    def _normalize(_signals):
        flags["normalized"] = True

    def _apply_prices(signals, latest_price_map):
        signals[0]["current_price"] = latest_price_map["000001"]
        flags["price_updated"] = True
        return 1

    result = route_service.build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: latest_payload,
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=_recalculate,
        sort_jongga_signals=_sort,
        normalize_jongga_signals_for_frontend=_normalize,
        apply_latest_prices_to_jongga_signals=_apply_prices,
        logger=TEST_LOGGER,
    )

    assert flags["price_updated"] is True
    assert flags["sorted"] is True
    assert flags["normalized"] is True
    assert result["signals"][0]["current_price"] == 10150.0

    persisted = json.loads((tmp_path / "jongga_v2_latest.json").read_text(encoding="utf-8"))
    assert persisted["recalculated"] is True


def test_route_service_parse_target_dates_normalizes_scalar_and_list():
    assert route_service.parse_target_dates({}) == []
    assert route_service.parse_target_dates({"target_dates": " 2026-02-20 "}) == ["2026-02-20"]
    assert route_service.parse_target_dates({"target_dates": ["2026-02-20", "", None]}) == ["2026-02-20"]


def test_route_service_run_user_gemini_reanalysis_imports_scripts_module(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "init_data.py").write_text(
        "def create_kr_ai_analysis_with_key(target_dates=None, api_key=None):\n"
        "    return {'count': len(target_dates or []), 'has_key': bool(api_key)}\n",
        encoding="utf-8",
    )

    monkeypatch.delitem(sys.modules, "init_data", raising=False)
    result = route_service.run_user_gemini_reanalysis(
        project_root=str(tmp_path),
        target_dates=["2026-02-20", "2026-02-21"],
        api_key="user-key",
    )

    assert result["count"] == 2
    assert result["has_key"] is True


def test_route_service_background_pipeline_resets_status_on_error(monkeypatch):
    status_calls = []

    async def _run_screener(*_args, **_kwargs):
        raise RuntimeError("engine failed")

    def _save_result(_result):
        raise AssertionError("save_result_to_json should not be called")

    generator_module = types.ModuleType("engine.generator")
    generator_module.run_screener = _run_screener
    generator_module.save_result_to_json = _save_result

    monkeypatch.setattr(route_service, "_reload_engine_submodules", lambda: None)
    monkeypatch.setitem(sys.modules, "engine.generator", generator_module)

    with pytest.raises(RuntimeError, match="engine failed"):
        route_service.run_jongga_v2_background_pipeline(
            capital=50_000_000,
            markets=None,
            target_date=None,
            save_status=status_calls.append,
            logger=TEST_LOGGER,
        )

    assert status_calls == [True, False]
