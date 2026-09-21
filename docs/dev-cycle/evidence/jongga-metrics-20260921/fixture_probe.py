#!/usr/bin/env python3
"""Scratch-only real parser/service/cache smoke, no external provider."""
import json
from fixture import app, state, data_dir
client = app.test_client()
results = []
for mode, period, bonus in [("known", "2026Q1", 9), ("legacy", None, 8), ("invalid", None, 7)]:
    assert client.post("/__qa/control", json={"mode": mode}).status_code == 200
    response = client.get("/api/kr/stock-detail/005930")
    body = response.get_json()
    assert response.status_code == 200
    assert body["financials"].get("netIncomePeriod") == period
    assert body["financials"]["netIncome"] == 2_600_000_000
    assert body["indicators"]["eps"] == -266
    assert body["indicators"]["per"] == -1147.6
    cached = client.get("/api/kr/stock-detail/005930").get_json()
    assert cached == body
    signal = client.get("/api/kr/jongga-v2/latest").get_json()["signals"][0]
    assert signal["score_details"]["bonus_score"] == bonus
    assert signal["score"]["total"] == 7 + bonus
    results.append({"mode": mode, "body": body, "bonus": bonus, "total": 7 + bonus})
print(json.dumps(results, ensure_ascii=False, indent=2))
