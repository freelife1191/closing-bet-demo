#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Service 단위 테스트
"""

import logging
import os
import sys
import json

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.kr_market_vcp_service import (
    collect_failed_vcp_rows,
    collect_missing_vcp_ai_rows,
    execute_vcp_failed_ai_reanalysis,
    load_vcp_ai_cache_map,
    merge_vcp_reanalysis_target_rows,
    prepare_vcp_signals_scope,
)


def test_prepare_vcp_signals_scope_uses_latest_date_when_target_missing():
    signals_df = pd.DataFrame(
        [
            {"ticker": "1", "signal_date": "2026-02-20", "ai_action": "BUY", "ai_reason": "ok"},
            {"ticker": "2", "signal_date": "2026-02-21", "ai_action": "N/A", "ai_reason": "분석 실패"},
        ]
    )

    date_key, scoped = prepare_vcp_signals_scope(signals_df, target_date=None)

    assert date_key == "2026-02-21"
    assert len(scoped) == 1
    assert scoped.iloc[0]["ticker"] == "000002"


def test_collect_failed_vcp_rows_preserves_index_and_count():
    scoped_df = pd.DataFrame(
        [
            {"ticker": "000001", "ai_action": "BUY", "ai_reason": "ok"},
            {"ticker": "000002", "ai_action": "N/A", "ai_reason": "분석 실패"},
            {"ticker": "000003", "ai_action": "HOLD", "ai_reason": "No analysis available."},
        ],
        index=[10, 20, 30],
    )

    def is_failed(row):
        return row.get("ai_action") not in {"BUY", "SELL", "HOLD"} or row.get("ai_reason") in {
            "분석 실패",
            "No analysis available.",
        }

    failed_rows, total_count = collect_failed_vcp_rows(scoped_df, is_failed=is_failed)

    assert total_count == 3
    assert [idx for idx, _ in failed_rows] == [20, 30]
    assert failed_rows[0][1]["ticker"] == "000002"
    assert failed_rows[1][1]["ticker"] == "000003"


def test_collect_missing_vcp_ai_rows_flags_gemini_or_second_missing():
    scoped_df = pd.DataFrame(
        [
            {"ticker": "000001"},
            {"ticker": "000002"},
            {"ticker": "000003"},
        ],
        index=[1, 2, 3],
    )
    ai_data_map = {
        "000001": {
            "gemini_recommendation": {"action": "BUY"},
            "perplexity_recommendation": {"action": "HOLD"},
        },
        "000002": {
            "gemini_recommendation": {"action": "BUY"},
        },
        "000003": {
            "perplexity_recommendation": {"action": "SELL"},
        },
    }

    rows = collect_missing_vcp_ai_rows(
        scoped_df=scoped_df,
        ai_data_map=ai_data_map,
        second_recommendation_key="perplexity_recommendation",
    )

    assert [idx for idx, _ in rows] == [2, 3]


def test_merge_vcp_reanalysis_target_rows_deduplicates_by_index():
    primary = [(10, {"ticker": "000001"})]
    additional = [(10, {"ticker": "000001"}), (20, {"ticker": "000002"})]

    merged = merge_vcp_reanalysis_target_rows(primary, additional)

    assert [idx for idx, _ in merged] == [10, 20]


def test_load_vcp_ai_cache_map_reads_existing_cache_files(tmp_path):
    cache_payload = {
        "signals": [
            {
                "ticker": "005930",
                "gemini_recommendation": {"action": "BUY"},
                "perplexity_recommendation": {"action": "HOLD"},
            },
            {
                "stock_code": "000660",
                "gpt_recommendation": {"action": "SELL"},
            },
        ]
    }
    (tmp_path / "ai_analysis_results.json").write_text(
        json.dumps(cache_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("ticker,signal_date\n005930,2026-02-21\n", encoding="utf-8")

    cache_exists, ai_map = load_vcp_ai_cache_map(
        target_date="2026-02-21",
        signals_path=str(signals_path),
        logger=logging.getLogger(__name__),
    )

    assert cache_exists is True
    assert isinstance(ai_map["005930"]["gemini_recommendation"], dict)
    assert isinstance(ai_map["005930"]["perplexity_recommendation"], dict)
    assert isinstance(ai_map["000660"]["gpt_recommendation"], dict)


def test_execute_vcp_failed_ai_reanalysis_targets_missing_second_ai(monkeypatch, tmp_path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "BUY",
                "ai_reason": "기존 Gemini 분석 완료",
                "ai_confidence": 80,
                "current_price": 10000,
                "entry_price": 9900,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            }
        ]
    )
    signals_path = tmp_path / "signals_log.csv"
    signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")

    # second provider(perplexity) 추천 누락 상태를 만든다.
    (tmp_path / "ai_analysis_results.json").write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "ticker": "005930",
                        "gemini_recommendation": {
                            "action": "BUY",
                            "confidence": 80,
                            "reason": "기존 Gemini 분석 완료",
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured_stocks = {"items": []}

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            captured_stocks["items"] = list(_stocks)
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "HOLD",
                        "confidence": 66,
                        "reason": "재분석 갱신",
                    },
                    "perplexity_recommendation": {
                        "action": "BUY",
                        "confidence": 71,
                        "reason": "Second AI 갱신",
                    },
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    captured = {"called": 0, "ai_results": None}

    def _update_cache_files(_target_date, _updated_recommendations, ai_results=None):
        captured["called"] += 1
        captured["ai_results"] = ai_results
        return 1

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=signals_df,
        signals_path=str(signals_path),
        update_cache_files=_update_cache_files,
        logger=logging.getLogger(__name__),
    )

    assert status_code == 200
    assert payload["failed_targets"] == 1
    assert payload["updated_count"] == 1
    assert payload["cache_files_updated"] == 1
    assert captured["called"] == 1
    assert isinstance(captured["ai_results"]["005930"]["perplexity_recommendation"], dict)
    assert captured_stocks["items"]
    assert captured_stocks["items"][0].get("skip_gemini") is True


def test_execute_vcp_failed_ai_reanalysis_targets_missing_gemini_only(monkeypatch, tmp_path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "BUY",
                "ai_reason": "기존 분석 완료",
                "ai_confidence": 80,
                "current_price": 10000,
                "entry_price": 9900,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            }
        ]
    )
    signals_path = tmp_path / "signals_log.csv"
    signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")

    # second provider(perplexity)는 있고 gemini만 누락된 상태.
    (tmp_path / "ai_analysis_results.json").write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "ticker": "005930",
                        "perplexity_recommendation": {
                            "action": "BUY",
                            "confidence": 72,
                            "reason": "기존 Second 분석",
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured_stocks = {"items": []}

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            captured_stocks["items"] = list(_stocks)
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "HOLD",
                        "confidence": 66,
                        "reason": "Gemini 재분석",
                    },
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=signals_df,
        signals_path=str(signals_path),
        update_cache_files=lambda *_args, **_kwargs: 1,
        logger=logging.getLogger(__name__),
    )

    assert status_code == 200
    assert payload["failed_targets"] == 1
    assert payload["updated_count"] == 1
    assert captured_stocks["items"]
    assert captured_stocks["items"][0].get("skip_second") is True
