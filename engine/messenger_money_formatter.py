#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messenger money formatter.
"""

from __future__ import annotations


class MoneyFormatter:
    """금액 포맷터 (조/억/만 단위)"""

    @staticmethod
    def format(val: int | float) -> str:
        """금액 포맷팅."""
        try:
            val_float = float(val)
            val_int = int(val)
            # 정수라면 정수형 우선 사용
            if val_float == val_int:
                val = val_int
            else:
                val = val_float
        except (TypeError, ValueError):
            return str(val)

        abs_val = abs(val)
        if abs_val >= 100_000_000_000:  # 1조 이상
            return f"{val / 100_000_000_000:+.1f}조"
        if abs_val >= 100_000_000:  # 1억 이상
            return f"{val / 100_000_000:+.0f}억"
        if abs_val >= 10_000:  # 1만 이상
            return f"{val / 10_000:+.0f}만"
        return f"{val:+}"
