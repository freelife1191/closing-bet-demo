#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver collector 분해 회귀 테스트
"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.collectors.naver import NaverFinanceCollector
import engine.collectors.naver_request_mixin as request_mixin_module


def test_request_retries_on_429_then_succeeds(monkeypatch):
    collector = NaverFinanceCollector()
    calls = {"count": 0}

    def _fake_get(_url, headers=None, timeout=10):
        _ = headers, timeout
        calls["count"] += 1
        if calls["count"] == 1:
            return SimpleNamespace(status_code=429, ok=False)
        return SimpleNamespace(status_code=200, ok=True, text="<html></html>")

    monkeypatch.setattr(request_mixin_module.requests, "get", _fake_get)
    monkeypatch.setattr(request_mixin_module.time, "sleep", lambda _v: None)

    response = collector._request("https://finance.naver.com/item/main.naver?code=005930")
    assert response is not None
    assert response.ok is True
    assert calls["count"] == 2


def test_extractors_fill_expected_fields():
    from bs4 import BeautifulSoup

    collector = NaverFinanceCollector()
    result = collector._create_empty_result_dict("005930")
    html = """
    <html>
      <div class="wrap_company"><h2><a>삼성전자</a></h2></div>
      <img class="kospi" alt="코스피"/>
      <p class="no_today"><span class="blind">70,000</span></p>
      <td class="first"><span class="blind">69,000</span></td>
      <table class="no_info">
        <td><span class="blind">0</span></td>
        <td><span class="blind">71,000</span></td>
        <td><span class="blind">0</span></td>
        <td><span class="blind">68,000</span></td>
      </table>
      <table class="tab_con1">
        <tr><th>52주 최고</th><td><span class="blind">80,000</span></td></tr>
        <tr><th>52주 최저</th><td><span class="blind">50,000</span></td></tr>
      </table>
      <span id="_per">12.3</span>
      <span id="_pbr">1.2</span>
      <span id="_market_sum">2,000억원</span>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    collector._extract_stock_name(soup, result)
    collector._extract_market_info(soup, result)
    collector._extract_current_price(soup, result)
    collector._extract_prev_close(soup, result)
    collector._extract_ohlcv(soup, result)
    collector._extract_52week_range(soup, result)
    collector._extract_indicators(soup, result)
    collector._extract_market_cap(soup, result)

    assert result["name"] == "삼성전자"
    assert result["market"] == "KOSPI"
    assert result["priceInfo"]["current"] == 70000
    assert result["priceInfo"]["prevClose"] == 69000
    assert result["priceInfo"]["high"] == 71000
    assert result["priceInfo"]["low"] == 68000
    assert result["yearRange"]["high_52w"] == 80000
    assert result["yearRange"]["low_52w"] == 50000
    assert result["indicators"]["per"] == 12.3
    assert result["indicators"]["pbr"] == 1.2
    assert result["indicators"]["marketCap"] == 2000 * 100_000_000
