#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
응답 본문에 NaN 이 실려 나가지 않는지 확인하는 회귀 테스트

파이썬의 json 은 NaN, Infinity, -Infinity 를 읽고 쓰지만 브라우저의 JSON.parse 는
거부한다. 그래서 curl 로 확인하면 멀쩡해 보이는 응답이 화면에서는 통째로 비는 일이
생긴다. 여기서는 parse_constant 로 브라우저와 같은 엄격도를 만들어 검사한다.
"""

import io
import json
import os
import sys
from typing import Any


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pandas as pd
from flask import Flask, jsonify

from app import _configure_app
from app.routes.kr_market_helpers import _build_vcp_signals_from_dataframe


def _strict_loads(body: str) -> Any:
    """브라우저의 JSON.parse 와 같은 엄격도로 파싱한다."""

    def reject(token: str) -> None:
        raise ValueError(f"JSON 표준에 없는 토큰이 실렸습니다: {token}")

    return json.loads(body, parse_constant=reject)


def _make_configured_app() -> Flask:
    app = Flask(__name__)
    _configure_app(app)
    return app


def test_nan_and_infinity_are_serialized_as_null():
    """앱 설정이 붙인 provider 가 세 토큰을 모두 null 로 바꾼다."""
    app = _make_configured_app()

    @app.route("/probe")
    def probe():
        return jsonify(
            {
                "market": float("nan"),
                "return_pct": float("inf"),
                "score": float("-inf"),
                "name": "휴젤",
            }
        )

    with app.test_client() as client:
        body = client.get("/probe").get_data(as_text=True)

    assert _strict_loads(body) == {
        "market": None,
        "return_pct": None,
        "score": None,
        "name": "휴젤",
    }


def test_nan_inside_a_tuple_is_serialized_as_null():
    """json 은 tuple 을 배열로 쓰므로 그 안의 NaN 도 걸러야 한다."""
    app = _make_configured_app()

    @app.route("/probe")
    def probe():
        return jsonify({"band": (float("nan"), 10.0)})

    with app.test_client() as client:
        body = client.get("/probe").get_data(as_text=True)

    assert _strict_loads(body) == {"band": [None, 10.0]}


def test_vcp_signal_with_a_blank_market_column_survives_a_strict_parser():
    """market 칸이 빈 CSV 행에서 만든 시그널이 브라우저까지 도달한다.

    CSV 의 빈 칸은 pandas 가 NaN 으로 읽으며, VCP 시그널 조립은 market 을 그대로
    담는다. 이 값이 응답에 실리면 화면은 백엔드가 200 을 돌려줘도 시그널을 하나도
    그리지 못한다.
    """
    csv_text = (
        "ticker,name,signal_date,market,status,score,is_vcp,vcp_score\n"
        "145020,휴젤,2026-09-01,,OPEN,88,True,80\n"
    )
    signals_df = pd.read_csv(io.StringIO(csv_text), dtype={"ticker": str})
    signals = _build_vcp_signals_from_dataframe(signals_df)
    assert len(signals) == 1

    app = _make_configured_app()

    @app.route("/probe")
    def probe():
        return jsonify({"signals": signals})

    with app.test_client() as client:
        body = client.get("/probe").get_data(as_text=True)

    parsed = _strict_loads(body)
    assert parsed["signals"][0]["market"] is None
    assert parsed["signals"][0]["ticker"] == "145020"
