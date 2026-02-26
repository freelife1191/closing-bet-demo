#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP Service 단위 테스트
"""

import logging
import os
import sys
import json
from typing import Any

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
    resolve_vcp_second_recommendation_key,
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


def test_resolve_vcp_second_recommendation_key_supports_zai_aliases():
    assert resolve_vcp_second_recommendation_key("zai") == "gpt_recommendation"
    assert resolve_vcp_second_recommendation_key("z.ai") == "gpt_recommendation"


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


def test_load_vcp_ai_cache_map_uses_injected_json_loader(tmp_path):
    cache_payload = {
        "signals": [
            {
                "ticker": "005930",
                "gemini_recommendation": {"action": "BUY"},
            }
        ]
    }
    (tmp_path / "ai_analysis_results.json").write_text("{}", encoding="utf-8")
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("ticker,signal_date\n005930,2026-02-21\n", encoding="utf-8")

    loaded_calls: list[tuple[str, dict[str, Any]]] = []

    def _loader(path: str, **kwargs):
        loaded_calls.append((path, dict(kwargs)))
        return cache_payload

    cache_exists, ai_map = load_vcp_ai_cache_map(
        target_date="2026-02-21",
        signals_path=str(signals_path),
        logger=logging.getLogger(__name__),
        load_json_payload_from_path_fn=_loader,
    )

    assert cache_exists is True
    assert loaded_calls
    assert loaded_calls[0][1].get("deep_copy") is False
    assert isinstance(ai_map["005930"]["gemini_recommendation"], dict)


def test_load_vcp_ai_cache_map_applies_ticker_filter(tmp_path):
    cache_payload = {
        "signals": [
            {
                "ticker": "005930",
                "gemini_recommendation": {"action": "BUY"},
            },
            {
                "ticker": "000660",
                "gemini_recommendation": {"action": "SELL"},
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
        ticker_filter={"005930"},
    )

    assert cache_exists is True
    assert "005930" in ai_map
    assert "000660" not in ai_map


def test_load_vcp_ai_cache_map_stops_early_when_required_keys_resolved(tmp_path):
    cache_payload = {
        "signals": [
            {
                "ticker": "005930",
                "gemini_recommendation": {"action": "BUY"},
                "perplexity_recommendation": {"action": "HOLD"},
            },
            {
                "ticker": "000660",
                "gemini_recommendation": {"action": "SELL"},
                "perplexity_recommendation": {"action": "BUY"},
            },
        ]
    }
    (tmp_path / "ai_analysis_results.json").write_text("{}", encoding="utf-8")
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("ticker,signal_date\n005930,2026-02-21\n", encoding="utf-8")

    call_count = {"count": 0}

    def _loader(_path: str):
        call_count["count"] += 1
        return cache_payload

    cache_exists, ai_map = load_vcp_ai_cache_map(
        target_date="2026-02-21",
        signals_path=str(signals_path),
        logger=logging.getLogger(__name__),
        load_json_payload_from_path_fn=_loader,
        ticker_filter={"005930"},
        required_recommendation_keys={"gemini_recommendation", "perplexity_recommendation"},
    )

    assert cache_exists is True
    assert call_count["count"] == 1
    assert "005930" in ai_map
    assert "000660" not in ai_map


def test_execute_vcp_failed_ai_reanalysis_writes_signals_csv_atomically(monkeypatch, tmp_path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "N/A",
                "ai_reason": "분석 실패",
                "ai_confidence": 0,
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

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 80,
                        "reason": "재분석 완료",
                    },
                    "perplexity_recommendation": {
                        "action": "HOLD",
                        "confidence": 65,
                        "reason": "보조 분석",
                    },
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer
    import services.kr_market_vcp_reanalysis_service as reanalysis_service

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    write_calls: dict[str, str] = {}

    def _atomic_write(path: str, content: str, *, invalidate_fn=None):
        del invalidate_fn
        write_calls["path"] = path
        write_calls["content"] = content

    monkeypatch.setattr(reanalysis_service, "atomic_write_text", _atomic_write)

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=signals_df,
        signals_path=str(signals_path),
        update_cache_files=lambda *_args, **_kwargs: 0,
        logger=logging.getLogger(__name__),
    )

    assert status_code == 200
    assert payload["updated_count"] == 1
    assert write_calls["path"] == str(signals_path)
    assert write_calls["content"].startswith("\ufeff")
    assert "005930" in write_calls["content"]


def test_execute_vcp_failed_ai_reanalysis_preserves_full_csv_columns_with_partial_source(
    monkeypatch,
    tmp_path,
):
    full_signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "N/A",
                "ai_reason": "분석 실패",
                "ai_confidence": 0,
                "current_price": 10000,
                "entry_price": 9900,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
                "extra_note": "보존필드",
            }
        ]
    )
    partial_signals_df = full_signals_df[
        [
            "ticker",
            "signal_date",
            "name",
            "current_price",
            "entry_price",
            "score",
            "vcp_score",
            "contraction_ratio",
            "foreign_5d",
            "inst_5d",
            "foreign_1d",
            "inst_1d",
            "ai_action",
            "ai_reason",
            "ai_confidence",
        ]
    ].copy()
    signals_path = tmp_path / "signals_log.csv"
    full_signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 80,
                        "reason": "재분석 완료",
                    },
                    "perplexity_recommendation": {
                        "action": "HOLD",
                        "confidence": 65,
                        "reason": "보조 분석",
                    },
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer
    import services.kr_market_vcp_reanalysis_service as reanalysis_service

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    write_calls = {}

    def _atomic_write(path: str, content: str, *, invalidate_fn=None):
        del invalidate_fn
        write_calls["path"] = path
        write_calls["content"] = content

    loader_calls = []

    def _load_csv_file_for_persist(filename: str):
        loader_calls.append(filename)
        return full_signals_df.copy()

    monkeypatch.setattr(reanalysis_service, "atomic_write_text", _atomic_write)

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=partial_signals_df,
        signals_path=str(signals_path),
        update_cache_files=lambda *_args, **_kwargs: 0,
        logger=logging.getLogger(__name__),
        load_csv_file_for_persist=_load_csv_file_for_persist,
    )

    assert status_code == 200
    assert payload["updated_count"] == 1
    assert write_calls["path"] == str(signals_path)
    assert loader_calls == ["signals_log.csv"]
    assert "extra_note" in write_calls["content"]
    assert "보존필드" in write_calls["content"]


def test_execute_vcp_failed_ai_reanalysis_prefers_deep_copy_false_for_persist_loader(
    monkeypatch,
    tmp_path,
):
    full_signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "N/A",
                "ai_reason": "분석 실패",
                "ai_confidence": 0,
                "current_price": 10000,
                "entry_price": 9900,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
                "extra_note": "보존필드",
            }
        ]
    )
    partial_signals_df = full_signals_df[
        [
            "ticker",
            "signal_date",
            "name",
            "current_price",
            "entry_price",
            "score",
            "vcp_score",
            "contraction_ratio",
            "foreign_5d",
            "inst_5d",
            "foreign_1d",
            "inst_1d",
            "ai_action",
            "ai_reason",
            "ai_confidence",
        ]
    ].copy()
    signals_path = tmp_path / "signals_log.csv"
    full_signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 80,
                        "reason": "재분석 완료",
                    },
                    "perplexity_recommendation": {
                        "action": "HOLD",
                        "confidence": 65,
                        "reason": "보조 분석",
                    },
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer
    import services.kr_market_vcp_reanalysis_service as reanalysis_service

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    write_calls: dict[str, str] = {}

    def _atomic_write(path: str, content: str, *, invalidate_fn=None):
        del invalidate_fn
        write_calls["path"] = path
        write_calls["content"] = content

    persist_loader_calls: list[tuple[str, dict[str, object]]] = []

    def _load_csv_file_for_persist(filename: str, **kwargs):
        persist_loader_calls.append((filename, dict(kwargs)))
        return full_signals_df.copy()

    monkeypatch.setattr(reanalysis_service, "atomic_write_text", _atomic_write)

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=partial_signals_df,
        signals_path=str(signals_path),
        update_cache_files=lambda *_args, **_kwargs: 0,
        logger=logging.getLogger(__name__),
        load_csv_file_for_persist=_load_csv_file_for_persist,
    )

    assert status_code == 200
    assert payload["updated_count"] == 1
    assert write_calls["path"] == str(signals_path)
    assert persist_loader_calls
    assert persist_loader_calls[0][0] == "signals_log.csv"
    assert persist_loader_calls[0][1].get("deep_copy") is False


def test_execute_vcp_failed_ai_reanalysis_force_gemini_skips_cache_load(monkeypatch, tmp_path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "BUY",
                "ai_reason": "기존 분석",
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

    class _DummyAnalyzer:
        @staticmethod
        def get_available_providers():
            return ["gemini", "perplexity"]

        @staticmethod
        async def analyze_batch(_stocks):
            return {
                "005930": {
                    "gemini_recommendation": {
                        "action": "SELL",
                        "confidence": 70,
                        "reason": "Gemini 강제 재분석",
                    }
                }
            }

    import engine.vcp_ai_analyzer as vcp_ai_analyzer
    import services.kr_market_vcp_reanalysis_service as reanalysis_service

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyAnalyzer())
    monkeypatch.setenv("VCP_SECOND_PROVIDER", "perplexity")

    def _must_not_call(*_args, **_kwargs):
        raise AssertionError("force gemini 경로에서 AI 캐시 로드를 호출하면 안됩니다.")

    monkeypatch.setattr(reanalysis_service, "load_vcp_ai_cache_map", _must_not_call)

    status_code, payload = execute_vcp_failed_ai_reanalysis(
        target_date="2026-02-21",
        signals_df=signals_df,
        signals_path=str(signals_path),
        update_cache_files=lambda *_args, **_kwargs: 0,
        logger=logging.getLogger(__name__),
        force_provider="gemini",
    )

    assert status_code == 200
    assert payload["failed_targets"] == 1
    assert payload["updated_count"] == 1


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


def test_execute_vcp_failed_ai_reanalysis_force_gemini_reanalyzes_all_scoped_rows(
    monkeypatch,
    tmp_path,
):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "BUY",
                "ai_reason": "기존 분석",
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
            },
            {
                "ticker": "000660",
                "signal_date": "2026-02-21",
                "name": "SK하이닉스",
                "ai_action": "HOLD",
                "ai_reason": "기존 분석",
                "ai_confidence": 60,
                "current_price": 20000,
                "entry_price": 19800,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            },
        ]
    )
    signals_path = tmp_path / "signals_log.csv"
    signals_df.to_csv(signals_path, index=False, encoding="utf-8-sig")

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
                        "action": "SELL",
                        "confidence": 70,
                        "reason": "Gemini 강제 재분석",
                    }
                },
                "000660": {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 75,
                        "reason": "Gemini 강제 재분석",
                    }
                },
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
        force_provider="gemini",
    )

    assert status_code == 200
    assert payload["failed_targets"] == 2
    assert payload["updated_count"] == 2
    assert captured_stocks["items"]
    assert all(item.get("skip_second") is True for item in captured_stocks["items"])


def test_execute_vcp_failed_ai_reanalysis_force_second_reanalyzes_all_scoped_rows(
    monkeypatch,
    tmp_path,
):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "005930",
                "signal_date": "2026-02-21",
                "name": "삼성전자",
                "ai_action": "BUY",
                "ai_reason": "기존 분석",
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
                    "perplexity_recommendation": {
                        "action": "HOLD",
                        "confidence": 66,
                        "reason": "Second 강제 재분석",
                    }
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
        force_provider="second",
    )

    assert status_code == 200
    assert payload["failed_targets"] == 1
    assert payload["updated_count"] == 1
    assert payload["still_failed_count"] == 0
    assert captured_stocks["items"]
    assert captured_stocks["items"][0].get("skip_gemini") is True
