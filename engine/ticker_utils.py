#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국내 종목코드 정규화 유틸리티."""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime
from numbers import Integral, Real
from typing import Any


# [FLOW-028] 마지막 자리도 영문자를 받는다. 옛 우선주(00088K)와 새 형식(0220WL)을 숫자만 남겨 읽으면 다른 종목 키가 된다
_TICKER_PATTERN = re.compile(r"(?<![0-9])[0-9][0-9A-Z]{5}(?![0-9])")
_FRACTIONAL_TEXT_PATTERN = re.compile(r"[+-]?[0-9]+\.[0-9]+")
_SIGNED_INTEGER_TEXT_PATTERN = re.compile(r"[+-][0-9]+")


def normalize_ticker(value: Any) -> str:
    """값에서 여섯 자리 국내 종목코드를 추출한다. 유효하지 않으면 빈 문자열이다."""
    if value is None or isinstance(value, (bool, date, datetime, os.PathLike)):
        return ""

    if isinstance(value, Integral):
        if value <= 0:
            return ""
        text = str(value)
    elif isinstance(value, Real):
        numeric_value = float(value)
        if (
            not math.isfinite(numeric_value)
            or numeric_value <= 0
            or not numeric_value.is_integer()
        ):
            return ""
        text = str(int(numeric_value))
    else:
        text = str(value).strip().upper()
        if _FRACTIONAL_TEXT_PATTERN.fullmatch(text) or _SIGNED_INTEGER_TEXT_PATTERN.fullmatch(text):
            return ""

    matched = _TICKER_PATTERN.search(text)
    if matched is not None:
        code = matched.group()
    else:
        code = re.sub(r"[^0-9]", "", text).zfill(6)

    return code if len(code) == 6 and code.strip("0") else ""
