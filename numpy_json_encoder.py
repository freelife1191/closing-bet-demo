#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Numpy/date/time JSON 직렬화 공용 인코더.

engine/services 모두에서 순환 import 없이 재사용하기 위한 독립 모듈.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """Numpy 데이터 타입과 Date/Time 객체를 JSON으로 직렬화한다."""

    def default(self, obj):  # type: ignore[override]
        if isinstance(
            obj,
            (
                np.int_,
                np.intc,
                np.intp,
                np.int8,
                np.int16,
                np.int32,
                np.int64,
                np.uint8,
                np.uint16,
                np.uint32,
                np.uint64,
            ),
        ):
            return int(obj)
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
