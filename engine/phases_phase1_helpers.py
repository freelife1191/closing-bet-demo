#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase1Analyzer 보조 로직.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def analyze_vcp_for_stock(*, stock: Any, charts: Any, logger) -> Optional[Dict[str, Any]]:
    """
    차트 기반 VCP 패턴을 분석하고 결과를 반환한다.

    반환값:
      {"score": int, "ratio": float, "is_vcp": bool} 또는 None
    """
    try:
        import pandas as pd

        from engine.vcp import detect_vcp_pattern

        if not charts or len(charts.closes) < 60:
            return None

        df = pd.DataFrame(
            {
                "open": charts.opens,
                "high": charts.highs,
                "low": charts.lows,
                "close": charts.closes,
                "volume": charts.volumes,
                "date": charts.dates,
            }
        )
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")

        vcp_result = detect_vcp_pattern(df, stock.code, stock.name)
        vcp_data = {
            "score": vcp_result.vcp_score,
            "ratio": vcp_result.contraction_ratio,
            "is_vcp": vcp_result.is_vcp,
        }

        # downstream analyzer가 stock 객체에서 직접 읽는 필드 유지
        setattr(stock, "vcp_score", vcp_result.vcp_score)
        setattr(stock, "contraction_ratio", vcp_result.contraction_ratio)
        return vcp_data
    except Exception as error:
        logger.debug(f"VCP analysis failed for {stock.name}: {error}")
        return None

