#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quota-ticker fixture의 격리, quota 오류, ticker/backtest 계약을 확인한다."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_fixture(repo: Path) -> ModuleType:
    path = repo / "docs/dev-cycle/evidence/quota-ticker-20260921/fixture.py"
    spec = importlib.util.spec_from_file_location("quota_ticker_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _quota(client: Any, mode: str, *, remaining: int = 8) -> Any:
    control = client.post("/__qa/control", json={"quota_mode": mode, "remaining": remaining})
    assert control.status_code == 200, control.get_data(as_text=True)
    return client.get("/api/kr/user/quota")


def main() -> None:
    repo = Path.cwd().resolve()
    fixture = _load_fixture(repo)
    fixture.validate_scratch_repo(str(repo))
    app = fixture.build_app(repo, reset_log=True)
    client = app.test_client()

    session = client.get("/api/auth/session")
    assert session.status_code == 200 and session.json["user"]["email"] == fixture.DEFAULT_EMAIL
    assert client.get("/api/admin/check").json == {"isAdmin": False}
    assert client.post("/__qa/control", json={"identity": "other", "admin": True}).status_code == 200
    assert client.get("/api/auth/session").json["user"]["email"] == fixture.OTHER_EMAIL
    assert client.get("/api/admin/check").json == {"isAdmin": True}
    assert client.post("/__qa/control", json={"identity": "unauth"}).status_code == 200
    assert client.get("/api/auth/session").json is None
    assert client.get("/api/admin/check").json == {"isAdmin": False}
    assert client.post("/__qa/control", json={"identity": "default", "admin": False}).status_code == 200

    normal = _quota(client, "normal", remaining=8)
    assert normal.status_code == 200 and normal.is_json and normal.json["remaining"] == 8
    for mode, status, is_json in [
        ("html-502", 502, False), ("html-404", 404, False), ("html-200", 200, False),
        ("json-401", 401, True), ("json-403", 403, True), ("json-500", 500, True),
    ]:
        response = _quota(client, mode)
        assert response.status_code == status and response.is_json is is_json, (mode, response.status_code, response.mimetype)
    recovered = _quota(client, "normal", remaining=3)
    assert recovered.status_code == 200 and recovered.json["remaining"] == 3
    recovered = _quota(client, "normal", remaining=8)
    assert recovered.status_code == 200 and recovered.json["remaining"] == 8

    vcp = client.get("/api/kr/signals")
    jongga = client.get("/api/kr/jongga-v2/latest")
    cumulative = client.get("/api/kr/closing-bet/cumulative")
    backtest = client.get("/api/kr/backtest-summary")
    assert vcp.status_code == jongga.status_code == cumulative.status_code == backtest.status_code == 200
    assert vcp.json["signals"][0]["ticker"] == "0007C0"
    assert jongga.json["signals"][0]["stock_code"] == "0007c0"
    assert cumulative.json["trades"][0]["code"] == "0007C0"
    assert backtest.json["closing_bet"]["count"] == backtest.json["vcp"]["count"] == 1
    price_response = client.post("/api/kr/realtime-prices", json={"tickers": ["0007C0", "005930", "", "000000"]})
    assert price_response.status_code == 200
    assert price_response.json == {"0007C0": 15_200.0, "005930": 76_200.0}

    portfolio = client.get("/api/portfolio").json
    assert portfolio["holdings"][0]["ticker"] == "0007c0"
    assert portfolio["holdings"][0]["current_price"] == 15200
    assert portfolio["holdings"][0]["is_stale"] is False
    assert portfolio["total_stock_value"] == 45600

    for path in ["/api/system/env", "/api/kr/refresh", "/api/portfolio/buy", "/api/kr/chatbot"]:
        assert client.post(path, json={}).status_code == 405, path
    assert client.delete("/api/kr/jongga-v2/latest").status_code == 405
    print(json.dumps({
        "session_admin_quota_modes": "PASS",
        "quota_recovery_remaining": [3, 8],
        "ticker_price_backtest_ui_shapes": "PASS",
        "blocked_product_mutations": "PASS",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
