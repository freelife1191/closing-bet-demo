#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP cache update service 테스트
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.kr_market_vcp_cache_update_service import update_vcp_ai_cache_files


_DATE = "2026-02-21"
_DATED = "ai_analysis_results_20260221.json"


def _rec(action: str, reason: str = "수축 뒤 거래량이 늘며 돌파 가능성이 높습니다") -> dict:
    return {"action": action, "confidence": 70, "reason": reason}


def _write(tmp_path: Path, filename: str, signals: list, **extra) -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps({"signals": signals, **extra}, ensure_ascii=False), encoding="utf-8")
    return path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _update(tmp_path: Path, *, target_date=_DATE, updated_recommendations=None, ai_results=None) -> int:
    return update_vcp_ai_cache_files(
        target_date=target_date,
        updated_recommendations=updated_recommendations or {},
        get_data_path=lambda filename: str(tmp_path / filename),
        load_json_file=lambda filename: _read(tmp_path / filename),
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
        ai_results=ai_results,
    )


def _by_ticker(path: Path) -> dict:
    return {row["ticker"]: row for row in _read(path)["signals"]}


def test_update_vcp_ai_cache_files_updates_matching_tickers(tmp_path: Path):
    path = _write(tmp_path, _DATED, [
        {"ticker": "005930", "gemini_recommendation": _rec("HOLD")},
        {"ticker": "000660", "gemini_recommendation": _rec("HOLD")},
    ])

    assert _update(tmp_path, updated_recommendations={"005930": _rec("BUY")}) == 1

    rows = _by_ticker(path)
    assert rows["005930"]["gemini_recommendation"]["action"] == "BUY"
    assert rows["000660"]["gemini_recommendation"]["action"] == "HOLD"
    assert "generated_at" in _read(path)


def test_update_vcp_ai_cache_files_updates_second_ai_recommendations(tmp_path: Path):
    path = _write(tmp_path, _DATED, [
        {"ticker": "005930", "gemini_recommendation": _rec("HOLD"), "gpt_recommendation": None},
    ])

    _update(tmp_path, ai_results={"005930": {
        "gpt_recommendation": _rec("SELL"),
        "perplexity_recommendation": _rec("BUY"),
    }})

    row = _by_ticker(path)["005930"]
    assert row["gpt_recommendation"]["action"] == "SELL"
    assert row["perplexity_recommendation"]["action"] == "BUY"
    assert row["gemini_recommendation"]["action"] == "HOLD"


def test_update_vcp_ai_cache_files_normalizes_ticker_keys_for_updates(tmp_path: Path):
    path = _write(tmp_path, _DATED, [{"ticker": "005930", "gemini_recommendation": _rec("HOLD")}])

    _update(tmp_path, updated_recommendations={"5930": _rec("BUY")})

    assert list(_by_ticker(path)) == ["005930"]
    assert _by_ticker(path)["005930"]["gemini_recommendation"]["action"] == "BUY"


def test_update_vcp_ai_cache_files_returns_zero_when_ai_results_have_no_dict_payload(tmp_path: Path):
    path = _write(tmp_path, _DATED, [{"ticker": "005930", "gemini_recommendation": _rec("HOLD")}])
    before = path.read_text(encoding="utf-8")

    assert _update(tmp_path, ai_results={"005930": {"perplexity_recommendation": None}}) == 0
    assert path.read_text(encoding="utf-8") == before


def test_update_vcp_ai_cache_files_adds_ticker_missing_from_cache(tmp_path: Path):
    # 수집 때 모든 AI 가 실패한 종목은 캐시에 없다. 재분석 결과가 그 종목을 새로 넣어야 한다 [VCP-044]
    path = _write(tmp_path, _DATED, [{"ticker": "005930", "gemini_recommendation": _rec("HOLD")}], signal_date=_DATE)

    assert _update(tmp_path, ai_results={"000660": {"gpt_recommendation": _rec("BUY")}}) == 1

    rows = _by_ticker(path)
    assert rows["000660"]["gpt_recommendation"]["action"] == "BUY"
    assert rows["005930"]["gemini_recommendation"]["action"] == "HOLD"


def test_update_vcp_ai_cache_files_creates_dated_file_when_missing(tmp_path: Path):
    # 수집이 전 종목 실패해 날짜 파일이 없던 날도 재분석 결과가 캐시에 남아야 한다 [VCP-044]
    assert _update(tmp_path, ai_results={"000660": {"gpt_recommendation": _rec("BUY")}}) == 1

    payload = _read(tmp_path / _DATED)
    assert payload["signal_date"] == _DATE
    assert payload["signals"][0]["ticker"] == "000660"
    assert payload["signals"][0]["gpt_recommendation"]["action"] == "BUY"


def test_update_vcp_ai_cache_files_leaves_undated_file_of_other_date(tmp_path: Path):
    # 날짜 없는 파일은 다른 날짜의 자료다. 과거 날짜 재분석이 그 파일을 고치면 안 된다 [VCP-044]
    undated = _write(tmp_path, "ai_analysis_results.json",
                     [{"ticker": "000660", "gemini_recommendation": _rec("HOLD")}], signal_date="2026-02-20")
    before = undated.read_text(encoding="utf-8")

    _update(tmp_path, ai_results={"000660": {"gemini_recommendation": _rec("BUY")}})

    assert undated.read_text(encoding="utf-8") == before
    assert _by_ticker(tmp_path / _DATED)["000660"]["gemini_recommendation"]["action"] == "BUY"


def test_update_vcp_ai_cache_files_keeps_valid_verdict_over_failed_result(tmp_path: Path):
    path = _write(tmp_path, _DATED, [{"ticker": "005930", "gemini_recommendation": _rec("HOLD")}])

    _update(tmp_path, ai_results={"005930": {"gemini_recommendation": {"action": "N/A", "reason": "분석 실패"}}})

    assert _by_ticker(path)["005930"]["gemini_recommendation"]["action"] == "HOLD"


def test_update_vcp_ai_cache_files_skips_without_target_date(tmp_path: Path):
    assert _update(tmp_path, target_date=None, ai_results={"000660": {"gpt_recommendation": _rec("BUY")}}) == 0
    assert list(tmp_path.iterdir()) == []


def test_update_vcp_ai_cache_files_writes_undated_file_of_same_date(tmp_path: Path):
    # 주말에 금요일 시그널을 재분석해도 같은 날짜를 가리키는 최신 파일은 따라와야 한다 [VCP-044]
    undated = _write(tmp_path, "kr_ai_analysis.json",
                     [{"ticker": "000660", "gemini_recommendation": _rec("HOLD")}], signal_date=_DATE)

    _update(tmp_path, ai_results={"000660": {"gpt_recommendation": _rec("BUY")}})

    assert _by_ticker(undated)["000660"]["gpt_recommendation"]["action"] == "BUY"
    assert not (tmp_path / "ai_analysis_results.json").exists()


def test_update_vcp_ai_cache_files_writes_undated_files_for_today(tmp_path: Path):
    today = datetime.now().strftime("%Y-%m-%d")

    _update(tmp_path, target_date=today, ai_results={"000660": {"gpt_recommendation": _rec("BUY")}})

    for filename in ("ai_analysis_results.json", "kr_ai_analysis.json"):
        payload = _read(tmp_path / filename)
        assert payload["signal_date"] == today
        assert payload["signals"][0]["gpt_recommendation"]["action"] == "BUY"


def test_update_vcp_ai_cache_files_prefers_raw_gemini_recommendation(tmp_path: Path):
    raw = {**_rec("BUY"), "model": "qa-gemini"}

    _update(tmp_path, updated_recommendations={"000660": _rec("BUY")},
            ai_results={"000660": {"gemini_recommendation": raw}})

    assert _by_ticker(tmp_path / _DATED)["000660"]["gemini_recommendation"]["model"] == "qa-gemini"


def test_update_vcp_ai_cache_files_uses_normalized_gemini_when_raw_is_not_storable(tmp_path: Path):
    _update(tmp_path, updated_recommendations={"000660": _rec("BUY")},
            ai_results={"000660": {"gemini_recommendation": _rec("buy")}})

    assert _by_ticker(tmp_path / _DATED)["000660"]["gemini_recommendation"]["action"] == "BUY"
