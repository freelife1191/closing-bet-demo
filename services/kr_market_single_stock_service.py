#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market single-stock analysis response service.
"""

from __future__ import annotations

from typing import Any, Callable


def _build_sample_single_stock_response(code: str) -> dict[str, Any]:
    return {
        "status": "success",
        "signal": {
            "stock_code": str(code).zfill(6),
            "stock_name": "샘플 종목",
            "grade": "A",
            "score": {
                "total": 8,
                "news": 2,
                "volume": 3,
                "chart": 1,
                "candle": 0,
                "timing": 1,
                "supply": 1,
            },
        },
        "message": "engine 모듈을 사용할 수 없어 샘플 데이터를 반환합니다.",
    }


def _serialize_single_stock_signal(signal: Any) -> dict[str, Any]:
    return {
        "stock_code": getattr(signal, "stock_code", ""),
        "stock_name": getattr(signal, "stock_name", ""),
        "grade": signal.grade.value if hasattr(getattr(signal, "grade", None), "value") else getattr(signal, "grade", ""),
        "score": signal.score.total if hasattr(getattr(signal, "score", None), "total") else getattr(signal, "score", 0),
    }


def execute_single_stock_analysis(code: str | None, logger: Any, run_coro_in_fresh_loop_fn: Callable[..., Any]) -> tuple[int, dict[str, Any]]:
    """단일 종목 재분석을 실행하고 HTTP 응답용 payload를 반환한다."""
    if not code:
        return 400, {"error": "Stock code is required"}

    try:
        from engine.generator import analyze_single_stock_by_code, update_single_signal_json
    except ImportError:
        return 200, _build_sample_single_stock_response(code)

    try:
        signal = run_coro_in_fresh_loop_fn(analyze_single_stock_by_code(code), logger=logger)
    except Exception as error:
        logger.error(f"Error re-analyzing stock {code}: {error}")
        return 500, {"error": str(error)}

    if not signal:
        return 404, {"status": "error", "error": f"{code} 종목을 찾을 수 없습니다."}

    try:
        update_single_signal_json(code, signal)
    except Exception as error:
        logger.warning(f"Failed to persist single signal ({code}): {error}")

    return 200, {"status": "success", "signal": _serialize_single_stock_signal(signal)}

