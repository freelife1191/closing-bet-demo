#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression: ISSUE-003 — data-status 가 CSV 전체 행을 strptime 하여 7초 이상 걸리던 문제
Found by /qa on 2026-09-01
Report: .gstack/qa-reports/qa-report-localhost-3500-2026-09-01.md
"""

from pathlib import Path

import services.common_data_status_service as common_data_status_service
from services.common_data_status_service import _extract_csv_data_date


def _write_csv(tmp_path: Path, rows: list[str]) -> str:
    csv_path = tmp_path / "daily_prices.csv"
    csv_path.write_text("date,ticker,close\n" + "".join(rows), encoding="utf-8")
    return str(csv_path)


def test_extract_csv_data_date_normalizes_each_distinct_token_once(tmp_path: Path, monkeypatch):
    """중복 날짜가 많아도 정규화는 고유 토큰 수만큼만 수행해야 한다."""
    rows = [f"2026-05-2{day % 2},00593{day % 10},100\n" for day in range(400)]
    csv_path = _write_csv(tmp_path, rows)

    calls: list[str] = []
    original = common_data_status_service._normalize_data_date_token

    def _counting_normalize(value):
        calls.append(str(value))
        return original(value)

    monkeypatch.setattr(
        common_data_status_service,
        "_normalize_data_date_token",
        _counting_normalize,
    )

    assert _extract_csv_data_date(csv_path) == "2026-05-21"
    # 고유 토큰은 2026-05-20 / 2026-05-21 두 개뿐이므로 400행을 다 돌면 안 된다.
    assert len(calls) <= 2, f"고유 토큰 2개 기대, {len(calls)}회 호출됨"


def test_extract_csv_data_date_returns_latest_across_mixed_formats(tmp_path: Path):
    """%Y%m%d 와 %Y-%m-%d 가 섞여 있어도 최신 날짜를 반환해야 한다."""
    csv_path = _write_csv(
        tmp_path,
        [
            "20260103,005930,100\n",
            "2026-05-22,000660,200\n",
            "20260222,035720,300\n",
        ],
    )

    assert _extract_csv_data_date(csv_path) == "2026-05-22"


def test_extract_csv_data_date_returns_none_when_no_parsable_token(tmp_path: Path):
    """파싱 가능한 날짜가 없으면 None 을 반환한다."""
    csv_path = _write_csv(tmp_path, ["not-a-date,005930,100\n", ",000660,200\n"])

    assert _extract_csv_data_date(csv_path) is None
