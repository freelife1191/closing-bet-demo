#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공용 JSON 인코더는 NumPy의 제거된 별칭 없이도 값을 보존한다."""

import json
from datetime import date, datetime

import numpy as np
import pytest

from numpy_json_encoder import NumpyEncoder


@pytest.mark.parametrize("alias_removed", [False, True])
def test_numpy_values_and_dates_roundtrip_without_legacy_alias(monkeypatch, alias_removed):
    if alias_removed:
        monkeypatch.delattr(np, "float_", raising=False)
    payload = {
        "float16": np.float16(1.5),
        "float32": np.float32(2.5),
        "float64": np.float64(3.5),
        "integer": np.int64(7),
        "boolean": np.bool_(True),
        "array": np.array([1, 2]),
        "date": date(2026, 9, 21),
        "datetime": datetime(2026, 9, 21, 1, 2, 3),
    }
    assert json.loads(json.dumps(payload, cls=NumpyEncoder)) == {
        "float16": 1.5, "float32": 2.5, "float64": 3.5,
        "integer": 7, "boolean": True, "array": [1, 2],
        "date": "2026-09-21", "datetime": "2026-09-21T01:02:03",
    }


def test_unsupported_objects_keep_json_type_error_without_legacy_alias(monkeypatch):
    monkeypatch.delattr(np, "float_", raising=False)
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps(object(), cls=NumpyEncoder)
