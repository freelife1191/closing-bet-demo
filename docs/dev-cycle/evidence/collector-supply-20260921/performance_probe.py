"""Actual reference/cache code with synthetic delayed provider; no market request."""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time


if len(sys.argv) == 1:
    runs = []
    for mode in ("serial", "batch"):
        for iteration in range(3):
            output = subprocess.run([sys.executable, __file__, mode], capture_output=True, text=True, timeout=60, check=True)
            row = json.loads(output.stdout.splitlines()[-1])
            runs.append(row)
            print(json.dumps(row), flush=True)
    medians = {mode: statistics.median(row["seconds"] for row in runs if row["mode"] == mode) for mode in ("serial", "batch")}
    assert len({row["digest"] for row in runs}) == 1
    assert all(row["fetches"] == 600 for row in runs)
    assert all(row["maximum_active"] <= 4 for row in runs)
    assert medians["batch"] <= medians["serial"] * 0.5
    print(json.dumps({"runs": runs, "medians": medians, "ratio": medians["batch"] / medians["serial"], "pass": True}), flush=True)
else:
    from services import investor_trend_5day_service as service
    mode = sys.argv[1]
    assert mode in {"serial", "batch"}
    lock = threading.Lock()
    counters = {"active": 0, "maximum": 0, "fetches": 0}
    def fetch(**kwargs):
        with lock:
            counters["active"] += 1
            counters["fetches"] += 1
            counters["maximum"] = max(counters["maximum"], counters["active"])
        try:
            time.sleep(0.05)
            return {"foreign": 50, "institution": 100, "latest_date": "2026-09-18", "days": 5,
                    "details": [{"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20} for _ in range(5)]}
        finally:
            with lock:
                counters["active"] -= 1
    service._get_or_build_trend_map = lambda **kwargs: {}
    service._fetch_pykrx_reference_trend = fetch
    with tempfile.TemporaryDirectory(prefix="supply-performance-") as directory:
        keys = [f"{index:06d}" for index in range(1, 601)]
        result = {}
        start = time.monotonic()
        if mode == "serial":
            for key in keys:
                result[key] = service.get_investor_trend_5day_for_ticker(ticker=key, data_dir=directory, target_datetime="2026-09-18")
        else:
            for offset in range(0, len(keys), 4):
                result.update(service.get_investor_trends_5day_for_tickers(tickers=keys[offset:offset+4], data_dir=directory, target_datetime="2026-09-18"))
        elapsed = time.monotonic() - start
        digest = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        print(json.dumps({"mode": mode, "seconds": elapsed, "fetches": counters["fetches"], "maximum_active": counters["maximum"], "digest": digest}))
