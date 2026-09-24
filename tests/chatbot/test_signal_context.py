#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signal_context 유틸 회귀 테스트
"""

import logging
import os
import sys
from pathlib import Path


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.signal_context as signal_context


LOGGER = logging.getLogger("test.signal_context")


def test_load_jongga_signals_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    target = tmp_path / "jongga_v2_latest.json"
    target.write_text("{}", encoding="utf-8")

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"signals": [{"stock_name": "삼성전자"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    signals = signal_context.load_jongga_signals(tmp_path, LOGGER)
    assert captured["path"] == str(target)
    assert signals == [{"stock_name": "삼성전자"}]


def test_load_vcp_ai_payload_prefers_primary_file(monkeypatch, tmp_path: Path):
    primary = tmp_path / "kr_ai_analysis.json"
    fallback = tmp_path / "ai_analysis_results.json"
    primary.write_text("{}", encoding="utf-8")
    fallback.write_text("{}", encoding="utf-8")

    called_paths: list[str] = []

    def _loader(path: str):
        called_paths.append(path)
        return {"signals": [{"name": "PRIMARY"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    payload = signal_context.load_vcp_ai_payload(tmp_path, LOGGER)
    assert called_paths == [str(primary)]
    assert payload == {"signals": [{"name": "PRIMARY"}]}


def test_load_vcp_ai_payload_falls_back_to_secondary_file(monkeypatch, tmp_path: Path):
    fallback = tmp_path / "ai_analysis_results.json"
    fallback.write_text("{}", encoding="utf-8")

    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"signals": [{"name": "FALLBACK"}]}

    monkeypatch.setattr(signal_context, "load_json_payload_from_path", _loader)

    payload = signal_context.load_vcp_ai_payload(tmp_path, LOGGER)
    assert captured["path"] == str(fallback)
    assert payload == {"signals": [{"name": "FALLBACK"}]}


# [CHAT-031] 시그널·뉴스·AI 분석 문맥의 기준일과 건수


def test_build_vcp_analysis_summary_text_counts_and_dates():
    from datetime import date

    payload = {
        "signal_date": "2026-05-05",
        "signals": [
            {"name": "A", "score": 70, "gemini_recommendation": {"action": "HOLD", "reason": "r"}},
            {"name": "B", "score": 80, "gemini_recommendation": {"action": "BUY", "reason": "good"}},
        ],
    }

    text = signal_context.build_vcp_analysis_summary_text(payload, today=date(2026, 9, 22))

    assert text.startswith("분석 2건 (기준일 2026-05-05, 140일 경과), 매수 추천 1건\n")
    assert "- **B**: 80점 (매수 추천)" in text
    assert "**A**" not in text


def test_build_vcp_analysis_summary_text_omits_missing_score():
    # 재분석이 캐시에 새로 넣은 행은 점수가 없다. 「0점」으로 적으면 LLM 이 실제 0점으로 읽는다 [CHAT-045]
    signals = [
        {"ticker": "030200", "stock_name": "KT", "gemini_recommendation": {"action": "BUY", "reason": "r"}},
        {"name": None, "stock_name": "한화", "score": None, "vcp_score": 55,
         "gemini_recommendation": {"action": "BUY", "reason": "r"}},
    ]

    text = signal_context.build_vcp_buy_recommendations_text(signals)

    assert "- **KT** (매수 추천)" in text
    assert "0점" not in text
    assert "- **한화**: 55점 (매수 추천)" in text


def test_build_vcp_analysis_summary_text_distinguishes_no_buy_from_no_analysis():
    from datetime import date

    payload = {
        "signal_date": "2026-05-05",
        "signals": [{"name": "A", "gemini_recommendation": {"action": "HOLD"}}],
    }

    text = signal_context.build_vcp_analysis_summary_text(payload, today=date(2026, 5, 6))

    assert text == (
        "분석 1건 (기준일 2026-05-05, 1일 경과), 매수 추천 0건\n"
        "- 매수 추천 종목 없음 (분석 결과가 전부 HOLD/SELL)"
    )
    assert signal_context.build_vcp_analysis_summary_text({"signals": []}, today=date(2026, 5, 6)) == ""


def test_build_latest_news_text_and_jongga_candidates_carry_as_of():
    from datetime import date

    signals = [
        {
            "signal_date": "2026-09-21",
            "stock_name": "A",
            "stock_code": "000001",
            "grade": "S",
            "score": {"total": 10},
            "news_items": [{"title": "T", "source": "S"}],
        }
    ]

    news = signal_context.build_latest_news_text(signals, limit=5, today=date(2026, 9, 22))
    jongga = signal_context.build_jongga_candidates_text(signals, limit=3, today=date(2026, 9, 22))

    assert news == "(기준일 2026-09-21, 1일 경과)\n- [S] T"
    assert jongga.startswith("(기준일 2026-09-21, 1일 경과)\n- **A** (000001): S급, 점수 10점 (2026-09-21)\n")
    assert signal_context.build_latest_news_text([], today=date(2026, 9, 22)) == ""
