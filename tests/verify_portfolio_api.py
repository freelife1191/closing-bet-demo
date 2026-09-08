#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""임시 DB와 bare Flask Blueprint로 포트폴리오 API를 안전하게 확인한다."""

import base64
import hashlib
import hmac
import logging
import os
import tempfile
import time
from types import SimpleNamespace
from pathlib import Path
import sys

from flask import Blueprint, Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routes.common_portfolio_routes import register_common_portfolio_routes
from services.paper_trading import PaperTradingService

KEY = "verify-portfolio-api-key"
OWNER = "verify@example.test"


def _identity(email: str, method: str, path: str) -> str:
    encoded = base64.urlsafe_b64encode(email.encode()).decode().rstrip("=")
    prefix = f"v2.{encoded}.{int(time.time()) + 60}"
    encoded_path = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    payload = f"{prefix}.{method}.{encoded_path}"
    return f"{prefix}.{hmac.new(KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()}"


def main() -> None:
    previous_secret = os.environ.get("INTERNAL_IDENTITY_SECRET")
    os.environ["INTERNAL_IDENTITY_SECRET"] = KEY
    try:
        with tempfile.TemporaryDirectory() as directory:
            service = PaperTradingService(db_path=os.path.join(directory, "portfolio.sqlite3"), auto_start_sync=False)
            service.start_background_sync = lambda: None
            service._wait_for_initial_price_sync = lambda holdings, prices: prices
            service.price_cache.update({"005380": 491_500, "45226K": 9_970, "452260": 1_907})
            app = Flask(__name__)
            blueprint = Blueprint("verify_portfolio", __name__)
            register_common_portfolio_routes(blueprint, SimpleNamespace(paper_trading=service, logger=logging.getLogger(__name__)))
            app.register_blueprint(blueprint, url_prefix="/api")
            client = app.test_client()
            assert client.get("/api/portfolio").status_code == 401
            def headers(method: str, path: str) -> dict[str, str]:
                return {"X-Auth-Identity": _identity(OWNER, method, path)}
            assert client.post("/api/portfolio/reset", headers=headers("POST", "/api/portfolio/reset")).status_code == 200
            for ticker, name, price, quantity in [("005380", "현대차", 491_500, 2), ("45226K", "한화갤러리아우", 9_970, 2), ("452260", "한화갤러리아", 1_907, 2)]:
                response = client.post("/api/portfolio/buy", headers=headers("POST", "/api/portfolio/buy"), json={"ticker": ticker, "name": name, "price": price, "quantity": quantity})
                assert response.status_code == 200 and response.get_json()["status"] == "success"
            response = client.get("/api/portfolio", headers=headers("GET", "/api/portfolio"))
            assert response.status_code == 200
            assert {holding["ticker"] for holding in response.get_json()["holdings"]} == {"005380", "45226K", "452260"}
            print("PASS: unsigned GET=401, signed reset/buy/portfolio owner flow verified")
    finally:
        if previous_secret is None:
            os.environ.pop("INTERNAL_IDENTITY_SECRET", None)
        else:
            os.environ["INTERNAL_IDENTITY_SECRET"] = previous_secret


if __name__ == "__main__":
    main()
