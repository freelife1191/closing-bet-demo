#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네트워크 없이 실제 yfinance history 경로를 검증한다."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _chart_payload(symbol: str, mode: str) -> dict:
    korea = timezone(timedelta(hours=9))
    timestamps = [
        int(datetime(2026, 9, 1, tzinfo=korea).timestamp()),
        int(datetime(2026, 9, 2, tzinfo=korea).timestamp()),
    ]
    meta = {
        "currency": "KRW",
        "symbol": symbol,
        "exchangeTimezoneName": "Asia/Seoul",
        "instrumentType": "EQUITY",
        "validRanges": ["1d", "5d", "1mo", "max"],
        "gmtoffset": 32_400,
    }
    if mode == "error":
        return {"chart": {"result": None, "error": {"description": "synthetic Yahoo failure"}}}
    quote = {} if mode == "empty" else {
        "open": [70_000, 71_000],
        "high": [71_500, 72_000],
        "low": [69_500, 70_500],
        "close": [71_000, 71_500],
        "volume": [100, 200],
    }
    return {
        "chart": {
            "result": [{
                "meta": meta,
                "timestamp": timestamps,
                "indicators": {
                    "quote": [quote],
                    "adjclose": [{"adjclose": [71_000, 71_500]}] if quote else [{}],
                },
                "events": {},
            }],
            "error": None,
        },
    }


def main() -> None:
    import yfinance as yf
    from curl_cffi import Curl, requests
    from curl_cffi.requests.models import Response

    requested_urls: list[str] = []
    chart_calls: dict[str, int] = {}
    external_requests = 0

    def blocked_curl_perform(_curl: Curl) -> None:
        nonlocal external_requests
        external_requests += 1
        raise AssertionError("synthetic transport attempted a real curl request")

    def response_for(url: str, payload: dict | None = None) -> Response:
        response = Response()
        response.url = url
        response.status_code = 200
        response.ok = True
        response.content = b"" if payload is None else json.dumps(payload).encode("utf-8")
        return response

    def synthetic_request(_session: object, method: str, url: str, **_kwargs: object) -> Response:
        requested_urls.append(url)
        if method != "GET":
            raise AssertionError(f"unexpected Yahoo method: {method}")
        if url == "https://fc.yahoo.com":
            return response_for(url)
        if url == "https://query1.finance.yahoo.com/v1/test/getcrumb":
            response = response_for(url)
            response.content = b"synthetic-crumb"
            return response
        chart_prefixes = (
            "https://query1.finance.yahoo.com/v8/finance/chart/",
            "https://query2.finance.yahoo.com/v8/finance/chart/",
        )
        prefix = next((candidate for candidate in chart_prefixes if url.startswith(candidate)), None)
        if prefix is None:
            raise AssertionError(f"real or unsupported network target: {url}")
        symbol = url.removeprefix(prefix)
        chart_calls[symbol] = chart_calls.get(symbol, 0) + 1
        mode = "normal"
        if symbol == "EMPTY.KS" and chart_calls[symbol] > 1:
            mode = "empty"
        if symbol == "ERROR.KS" and chart_calls[symbol] > 1:
            mode = "error"
        return response_for(url, _chart_payload(symbol, mode))

    def synthetic_get(session: object, url: str, **kwargs: object) -> Response:
        return synthetic_request(session, "GET", url, **kwargs)

    requests.Session.request = synthetic_request
    requests.Session.get = synthetic_get
    Curl.perform = blocked_curl_perform

    with tempfile.TemporaryDirectory() as cache_dir:
        # yfinance의 공개 API가 timezone·cookie cache 모두를 이 격리 경로로 보낸다.
        yf.set_tz_cache_location(Path(cache_dir))
        normal = yf.Ticker("005930.KS").history(
            start="2026-09-01", end="2026-09-03", auto_adjust=False, actions=False,
        )
        empty = yf.Ticker("EMPTY.KS").history(
            start="2026-09-01", end="2026-09-03", auto_adjust=False, actions=False,
        )
        failed = yf.Ticker("ERROR.KS").history(
            start="2026-09-01", end="2026-09-03", auto_adjust=False, actions=False,
        )

    assert normal.index[0].strftime("%Y-%m-%d") == "2026-09-01"
    assert normal.loc[normal.index[0], "Close"] == 71_000
    assert list(normal.columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    assert empty.empty
    assert failed.empty
    assert any("/v8/finance/chart/005930.KS" in url for url in requested_urls)
    assert all("yahoo.com" in url for url in requested_urls)
    assert external_requests == 0
    print(json.dumps({
        "ticker": "005930.KS",
        "date": "2026-09-01",
        "close": 71_000,
        "external_requests": external_requests,
    }))


if __name__ == "__main__":
    main()
