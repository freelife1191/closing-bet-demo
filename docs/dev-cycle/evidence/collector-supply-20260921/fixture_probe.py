"""Synthetic fixture preflight through real Flask handlers; no socket or market access."""
import json
from pathlib import Path
import runpy

namespace = runpy.run_path(str(Path(__file__).with_name("fixture.py")))
client = namespace["app"].test_client()
results = []
for mode, expected in [("zero", 0), ("positive", 100_000_000), ("negative", -100_000_000),
                       ("missing", None), ("invalid", None), ("legacy", None)]:
    assert client.post("/__qa/control", json={"mode": mode}).status_code == 200
    first = client.get("/api/kr/stock-detail/005930")
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.json["investorTrend"]["individual"] == expected, (mode, first.json)
    namespace["detail"]._STOCK_DETAIL_CACHE.clear()
    second = client.get("/api/kr/stock-detail/005930")
    assert second.json["investorTrend"]["individual"] == expected
    results.append({"mode": mode, "expected": expected, "actual": first.json["investorTrend"]["individual"], "sqlite_repeat": True})
assert client.post("/__qa/control", json={"mode": "error"}).status_code == 200
assert client.get("/api/kr/stock-detail/005930").status_code == 503
assert client.post("/api/system/env", json={}).status_code == 405
assert client.delete("/api/system/env").status_code == 405
assert client.post("/__qa/control", json={"mode": "zero"}).status_code == 200
print(json.dumps({"checks": results, "expected_error": 503, "forbidden_mutations": 405, "pass": True}))
