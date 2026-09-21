#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared encoder must work without aliases removed in NumPy 2."""
import json
from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from numpy_json_encoder import NumpyEncoder


def test_numpy_scalars_arrays_and_dates_have_stable_json_values():
    payload = {
        "f16": np.float16(1.5), "f32": np.float32(2.5), "f64": np.float64(3.5),
        "integer": np.int64(7), "boolean": np.bool_(True), "array": np.array([1, 2]),
        "date": date(2026, 9, 21), "time": datetime(2026, 9, 21, 1, 2, 3),
        "stamp": pd.Timestamp("2026-09-21T04:05:06"),
    }
    assert json.loads(json.dumps(payload, cls=NumpyEncoder)) == {
        "f16": 1.5, "f32": 2.5, "f64": 3.5, "integer": 7, "boolean": True,
        "array": [1, 2], "date": "2026-09-21", "time": "2026-09-21T01:02:03",
        "stamp": "2026-09-21T04:05:06",
    }


def test_unknown_objects_still_raise_the_json_type_error():
    with pytest.raises(TypeError, match="not JSON serializable"):
        json.dumps(object(), cls=NumpyEncoder)
