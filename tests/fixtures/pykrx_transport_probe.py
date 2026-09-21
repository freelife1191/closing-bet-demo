#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patched pykrx webio의 인증 쿠키 전송 경계를 실제 requests 경로로 검사한다."""

import json
import socket
from unittest.mock import patch
from urllib.parse import urlsplit

import requests


def main() -> None:
    from pykrx.website.comm import auth, webio

    class ProbeGet(webio.Get):
        def __init__(self, url: str):
            super().__init__()
            self._url = url

        @property
        def url(self) -> str:
            return self._url

    class ProbePost(webio.Post):
        def __init__(self, url: str):
            super().__init__()
            self._url = url

        @property
        def url(self) -> str:
            return self._url

    class ChangingGet(ProbeGet):
        def __init__(self, first: str, second: str):
            super().__init__(first)
            self._second = second
            self.reads = 0

        @property
        def url(self) -> str:
            self.reads += 1
            return self._url if self.reads == 1 else self._second

    sent: list[dict] = []
    send_redirects: list[bool] = []
    external_requests = 0

    def block_socket(*args, **kwargs):
        nonlocal external_requests
        external_requests += 1
        raise AssertionError("real socket blocked")
    session_calls = 0
    krx_session = auth.KRXSession()
    krx_session.session = requests.Session()
    # 도메인 없는 cookie도 인증 세션을 잘못 고르면 모든 host로 흘러간다.
    krx_session.session.cookies.set("krx", "synthetic", domain="data.krx.co.kr", path="/", secure=True)
    krx_session.session.cookies.set("global", "must-not-leak")
    krx_session.session.cookies.set("private", "not-on-this-path", domain="data.krx.co.kr", path="/private", secure=True)
    krx_session.cookies = {"legacy": {"value": "must-not-leak"}}

    def get_session() -> object:
        nonlocal session_calls
        session_calls += 1
        return krx_session

    def fake_adapter_send(_adapter: object, request: requests.PreparedRequest, **_kwargs: object) -> requests.Response:
        sent.append({
            "url": request.url,
            "method": request.method,
            "cookie": request.headers.get("Cookie"),
            "authorization": request.headers.get("Authorization"),
            "proxy_authorization": request.headers.get("Proxy-Authorization"),
            "body": request.body,
        })
        response = requests.Response()
        response.url = request.url
        response.request = request
        response._content = b"{}"
        if request.url.startswith("http://fchart.stock.naver.com/sise.nhn"):
            response._content = (
                b"<protocol><chartdata><item data=\"20260102|70000|72000|69000|71000|1000\"/>"
                b"</chartdata></protocol>"
            )
            response.status_code = 200
            return response
        response.status_code = 302 if urlsplit(request.url).path == "/redirect" else 200
        if response.status_code == 302:
            response.headers["Location"] = "https://evil.example/next"
        return response

    original_send = requests.Session.send

    def capture_send(session: requests.Session, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        send_redirects.append(bool(kwargs.get("allow_redirects", True)))
        return original_send(session, request, **kwargs)

    trusted_get = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    trusted_post = "https://data.krx.co.kr/comm/bldAttendant/executeForResourceBundle.cmd"
    hostile_urls = [
        "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
        "https://data.krx.co.kr:444/comm/bldAttendant/getJsonData.cmd",
        "https://user@data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
        "https://data.krx.co.kr.evil/comm/bldAttendant/getJsonData.cmd",
    ]

    with patch.object(webio, "get_session", side_effect=get_session), \
            patch.object(requests.adapters.HTTPAdapter, "send", fake_adapter_send), \
            patch.object(requests.Session, "send", capture_send), \
            patch.object(requests.sessions, "get_netrc_auth", return_value=None), \
            patch.object(socket, "create_connection", side_effect=block_socket), \
            patch.object(socket.socket, "connect", side_effect=block_socket):
        get = ProbeGet(trusted_get)
        post = ProbePost(trusted_post)
        get.read(query="trusted")
        post.read(payload="trusted")

        before_public = session_calls
        ProbeGet("http://finance.naver.com/item/sise.nhn").read(query="public-http")
        ProbeGet("https://finance.naver.com/item/sise.nhn").read(query="public-https")
        ProbePost("https://example.com/public").read(payload="public-post")
        assert session_calls == before_public

        for hostile in hostile_urls:
            for probe_type in (ProbeGet, ProbePost):
                before = len(sent)
                if "user@" in hostile:
                    try:
                        probe_type(hostile).read(query="hostile")
                    except ValueError:
                        assert len(sent) == before
                    else:
                        raise AssertionError("URL credentials must be rejected")
                else:
                    probe_type(hostile).read(query="hostile")
                    assert sent[-1]["cookie"] is None
                    assert sent[-1]["authorization"] is None
        assert session_calls == before_public

        changing = ChangingGet(trusted_get, "https://evil.example/changed")
        changing.read(query="single-read")
        assert changing.reads == 1

        ProbeGet("https://data.krx.co.kr:443/explicit-port").read(query="trusted")
        for probe_type in (ProbeGet, ProbePost):
            response = probe_type("https://data.krx.co.kr/redirect").read(query="redirect")
            assert response.status_code == 302
        assert not any("evil.example" in item["url"] for item in sent)

        # 상위 공개 API도 Naver HTTP 경로에는 KRX 인증 세션을 조회하지 않는다.
        from pykrx import stock

        before_naver = session_calls
        ohlcv = stock.get_market_ohlcv_by_date("20260102", "20260102", "005930")
        assert ohlcv.iloc[0]["종가"] == 71_000
        assert session_calls == before_naver

        # auth.KRXSession 자체도 webio 우회 호출에서 같은 origin gate를 적용한다.
        direct = auth.KRXSession()
        direct.session = requests.Session()
        direct.session.cookies.set("scoped", "synthetic", domain="data.krx.co.kr", path="/", secure=True)
        direct.session.cookies.set("global", "must-not-leak")
        direct.cookies = {"legacy": {"value": "must-not-leak"}}
        direct.get(trusted_get, headers={}, params={"direct": "get"})
        direct.post(trusted_post, headers={}, data={"direct": "post"})
        sensitive = {"cOoKiE": "explicit-synthetic", "Authorization": "synthetic", "Proxy-Authorization": "synthetic"}
        direct.get("https://example.com/public", headers=sensitive, params={"direct": "external"})
        direct.post("https://example.com/public", headers=sensitive, data={"direct": "external"})
        for method in (direct.get, direct.post):
            before = len(sent)
            response = method("https://data.krx.co.kr/redirect", allow_redirects=True)
            assert response.status_code == 302 and len(sent) == before + 1
        assert "Cookie" not in direct.get_headers()

    def matching(prefix: str, method: str) -> list[dict]:
        return [item for item in sent if item["method"] == method and item["url"].startswith(prefix)]

    trusted_gets = matching(trusted_get, "GET")
    trusted_posts = matching(trusted_post, "POST")
    assert any("krx=synthetic" in (item["cookie"] or "") and "query=trusted" in item["url"] for item in trusted_gets)
    assert any("krx=synthetic" in (item["cookie"] or "") and item["body"] == "payload=trusted" for item in trusted_posts)
    assert all(item["cookie"] is None for item in matching("http://finance.naver.com", "GET"))
    assert all(item["cookie"] is None for item in matching("https://finance.naver.com", "GET"))
    assert all(item["cookie"] is None for item in matching("https://example.com", "GET") + matching("https://example.com", "POST"))
    assert any("scoped=synthetic" in (item["cookie"] or "") for item in trusted_gets)
    assert any("scoped=synthetic" in (item["cookie"] or "") for item in trusted_posts)
    assert all("private=" not in (item["cookie"] or "") and "legacy=" not in (item["cookie"] or "") for item in sent)
    for item, redirect_allowed in zip(sent, send_redirects):
        if urlsplit(item["url"]).hostname == "data.krx.co.kr" and urlsplit(item["url"]).scheme == "https" and urlsplit(item["url"]).port in (None, 443):
            assert redirect_allowed is False
    public = matching("https://example.com", "GET") + matching("https://example.com", "POST")
    assert all(item["authorization"] is None and item["proxy_authorization"] is None for item in public)
    naver = matching("http://fchart.stock.naver.com/sise.nhn", "GET")
    assert len(naver) == 1 and naver[0]["cookie"] is None and naver[0]["authorization"] is None
    assert external_requests == 0
    print(json.dumps({"cases": ["trusted", "public", "hostile", "single-read", "redirect", "naver_ohlcv", "direct_auth"], "external_requests": external_requests}))


if __name__ == "__main__":
    main()
