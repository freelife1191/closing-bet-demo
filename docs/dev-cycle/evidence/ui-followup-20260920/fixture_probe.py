#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scratch 합성 fixture 계약을 검증한다.

이 파일은 제품 테스트를 대신하지 않는다. 다만 실제 종가 AI 추출·정규화 헬퍼에
상충 입력을 전달해 UI용 합성 입력이 백엔드 계약과 분리되지 않았는지 확인한다.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from app.routes.kr_market_jongga_ai_payload_helpers import _extract_jongga_ai_evaluation
from app.routes.kr_market_jongga_normalize_helpers import _normalize_jongga_signals_for_frontend


def _load_fixture(repo: Path) -> ModuleType:
    fixture_path = repo / "docs/dev-cycle/evidence/ui-followup-20260920/fixture.py"
    spec = importlib.util.spec_from_file_location("ui_followup_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _conflicting_signal(fixture: ModuleType) -> dict[str, Any]:
    payload = fixture._closing_payload("normal")
    return next(signal for signal in payload["signals"] if signal["stock_code"] == "000660")


def main() -> None:
    repo = Path.cwd()
    fixture = _load_fixture(repo)
    app = fixture.build_app(repo, reset_log=True)
    client = app.test_client()

    for path in [
        "/api/auth/session", "/api/kr/config/interval", "/api/kr/status", "/api/kr/backtest-summary", "/api/kr/closing-bet/cumulative",
        "/api/admin/check",
        "/api/system/env",
        "/api/kr/user/quota",
        "/api/kr/jongga-v2/latest",
        "/api/kr/ai-analysis",
        "/api/kr/signals",
        "/api/portfolio",
        "/api/system/data-status",
    ]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        assert response.is_json, path

    for path in [
        "/api/auth/signout",
        "/api/auth/signin/google",
        "/api/system/env",
        "/api/portfolio/buy",
        "/api/kr/chatbot",
    ]:
        response = client.post(path)
        assert response.status_code == 405, (path, response.status_code)

    assert client.post("/__qa/control", json={"mode": "normal"}).status_code == 200
    assert client.get("/api/admin/check").json["isAdmin"] is False
    print("fixture required GET, fake auth, and mutation boundaries PASS")

    assert client.post("/__qa/control", json={"mode": "d-only"}).status_code == 200
    response = client.get("/api/kr/jongga-v2/latest").json
    assert len(response["signals"]) == 1 and response["signals"][0]["grade"] == "D"

    assert client.post("/__qa/control", json={"mode": "zero"}).status_code == 200
    response = client.get("/api/kr/stock-detail/005930").json
    assert "investorTrend5Day" not in response
    assert response["investorTrend"] == {"institution": 0, "individual": 0}

    assert client.post("/__qa/control", json={"mode": "admin", "price_mode": "success"}).status_code == 200
    response = client.post("/api/kr/realtime-prices", json={"tickers": ["005930"]})
    assert response.status_code == 200 and response.json["prices"]["005930"] == 76_200
    assert client.post("/__qa/control", json={"price_mode": "error"}).status_code == 200
    response = client.post("/api/kr/realtime-prices", json={"tickers": ["005930"]})
    assert response.status_code == 503 and response.json["error"] == "합성 현재가 조회 실패"

    for refresh_path in ["/api/kr/market-gate/update", "/api/kr/refresh"]:
        assert client.post("/__qa/control", json={"refresh_mode": "success"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 200 and response.json["source"] == "synthetic-ui-fixture"
        assert client.post("/__qa/control", json={"refresh_mode": "error-500"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 500 and response.is_json
        assert client.post("/__qa/control", json={"refresh_mode": "html-500"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 500 and response.mimetype == "text/html"
        assert client.post("/__qa/control", json={"refresh_mode": "forbidden"}).status_code == 200
        response = client.post(refresh_path, json={"target_date": "2026-09-20"})
        assert response.status_code == 403 and response.is_json
    timeout_control = client.post("/__qa/control", json={"refresh_mode": "timeout"})
    assert timeout_control.status_code == 200 and timeout_control.json["refresh_mode"] == "timeout"
    print("refresh 500/HTML/403/success and price success/failure fixture contracts PASS")

    source_signal = _conflicting_signal(fixture)
    before_extract = deepcopy(source_signal)
    selected = _extract_jongga_ai_evaluation(source_signal)
    assert selected == {
        "action": "HOLD",
        "confidence": 0,
        "reason": "새 HOLD 판정: 진입을 보류합니다.",
    }
    assert source_signal == before_extract

    analysis_response = client.get("/api/kr/ai-analysis")
    assert analysis_response.status_code == 200
    transformed_signal = next(
        signal for signal in analysis_response.json["signals"] if signal["ticker"] == "000660"
    )
    assert transformed_signal["gemini_recommendation"] == selected

    normalized = [deepcopy(source_signal)]
    _normalize_jongga_signals_for_frontend(normalized)
    assert normalized[0]["ai_evaluation"] == selected
    assert normalized[0]["score"]["ai_evaluation"]["action"] == "BUY"
    assert normalized[0]["score_details"]["ai_evaluation"]["action"] == "SELL"
    print("conflicting AI fixture passes actual extraction and normalization helpers PASS")
    assert client.post("/__qa/control", json={"mode": "malformed-ai"}).status_code == 200
    response = client.get("/api/kr/ai-analysis")
    assert response.status_code == 200
    malformed = next(row for row in response.json["signals"] if row["ticker"] == "000660")
    assert malformed["gemini_recommendation"] == {"action": "BUY"}
    print("malformed AI fields removed by actual response transform PASS")



if __name__ == "__main__":
    main()
