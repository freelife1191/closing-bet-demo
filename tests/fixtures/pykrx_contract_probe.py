#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actual pykrx parsing with transport-only synthetic KRX responses."""
import json
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import requests

responses = {
    "MDCSTAT01501": {"OutBlock_1": [{"ISU_SRT_CD": "005930", "TDD_OPNPRC": "70,000", "TDD_HGPRC": "72000", "TDD_LWPRC": "69000", "TDD_CLSPRC": "71000", "ACC_TRDVOL": "1,000", "ACC_TRDVAL": "71000000", "FLUC_RT": "1.43", "MKTCAP": "1000000000"}]},
    "MDCSTAT03501": {"output": [{"ISU_SRT_CD": "005930", "BPS": "10000", "PER": "10", "PBR": "1", "EPS": "1000", "DVD_YLD": "2", "DPS": "500"}]},
    "MDCSTAT02401": {"output": [{"ISU_SRT_CD": "5930", "ISU_NM": "합성", "ASK_TRDVOL": "1000", "BID_TRDVOL": "2000", "NETBID_TRDVOL": "1000", "ASK_TRDVAL": "70000000", "BID_TRDVAL": "140000000", "NETBID_TRDVAL": "70000000"}]},
    "MDCSTAT00301": {"output": [{"TRD_DD": "2026/01/02", "OPNPRC_IDX": "2500", "HGPRC_IDX": "2600", "LWPRC_IDX": "2400", "CLSPRC_IDX": "2550", "ACC_TRDVOL": "1000", "ACC_TRDVAL": "1000000", "MKTCAP": "10000000"}]},
    "MDCSTAT02302": {"output": [{"TRD_DD": "2026/01/02", "TRDVAL1": "10", "TRDVAL2": "20", "TRDVAL3": "-60", "TRDVAL4": "30", "TRDVAL_TOT": "0"}]},
}
seen = []


def fake_post(self, **params):
    assert self.url == "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    assert params["bld"].startswith("dbms/MDC/STAT/standard/")
    seen.append(dict(params))
    payload = responses[params["bld"].rsplit("/", 1)[-1]]
    return SimpleNamespace(json=lambda: payload)


with patch.object(requests.sessions.Session, "request", side_effect=AssertionError("Unexpected HTTP")) as network:
    # A clean subprocess has no inherited KRX credentials or earlier test module doubles.
    from pykrx import stock
    from pykrx.stock import stock_api
    from pykrx.website.comm.webio import Post
    from pykrx.website.krx.market import wrap

    with patch.object(Post, "read", fake_post), patch.object(wrap, "get_stock_ticker_isin", return_value="KR7005930003"), patch.object(stock_api, "get_index_ticker_name", return_value="합성 지수"):
        prices = stock.get_market_ohlcv_by_ticker("20260102", "ALL")
        assert list(prices.index) == ["005930"]
        assert list(prices.columns) == ["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률", "시가총액"]
        assert prices.loc["005930", "종가"] == 71_000 and prices.loc["005930", "거래량"] == 1_000
        assert seen[-1]["mktId"] == "ALL" and seen[-1]["trdDd"] == "20260102"

        fundamentals = stock.get_market_fundamental_by_ticker("20260102", "ALL")
        assert list(fundamentals.columns) == ["BPS", "PER", "PBR", "EPS", "DIV", "DPS"]
        assert fundamentals.loc["005930", ["EPS", "PER", "DIV"]].tolist() == [1000, 10, 2]
        assert seen[-1]["mktId"] == "ALL" and seen[-1]["trdDd"] == "20260102"

        flows = stock.get_market_net_purchases_of_equities_by_ticker("20260102", "20260102", "ALL", "외국인")
        assert list(flows.index) == ["005930"]
        assert flows.loc["005930", ["순매수거래량", "순매수거래대금"]].tolist() == [1000, 70000000]
        assert str(seen[-1]["invstTpCd"]) == "9000" and seen[-1]["strtDd"] == "20260102"

        index = stock.get_index_ohlcv_by_date("20260102", "20260102", "1001")
        assert list(index.index.strftime("%Y-%m-%d")) == ["2026-01-02"]
        assert index.iloc[0]["종가"] == 2550
        assert seen[-1]["indIdx"] == "1" and seen[-1]["indIdx2"] == "001"

        business_day = stock.get_nearest_business_day_in_a_week("20260103")
        assert business_day == "20260102"
        assert seen[-1]["indIdx"] == "1" and seen[-1]["indIdx2"] == "001"

        daily_flow = stock.get_market_trading_value_by_date("20260102", "20260102", "005930")
        assert list(daily_flow.columns) == ["기관합계", "기타법인", "개인", "외국인합계", "전체"]
        assert daily_flow.iloc[0].tolist() == [10, 20, -60, 30, 0]
        assert seen[-1]["isuCd"] == "KR7005930003"
    assert network.call_count == 0

print(json.dumps({"cases": ["ohlcv", "fundamentals", "net_purchases", "index", "business_day", "daily_flow"], "numpy": np.__version__, "requests": seen, "external_requests": network.call_count}, ensure_ascii=False))
