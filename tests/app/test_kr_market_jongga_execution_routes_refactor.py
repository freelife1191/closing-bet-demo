#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Execution Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Blueprint, Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market_jongga_execution_routes import register_jongga_execution_routes


def _build_deps(**overrides):
    base = {
        "load_json_file": lambda _filename: {},
        "launch_jongga_v2_screener": lambda **_kwargs: (200, {"status": "started"}),
        "run_jongga_v2_background_pipeline": lambda **_kwargs: None,
        "execute_single_stock_analysis": lambda **_kwargs: (200, {"status": "ok"}),
        "execute_jongga_gemini_reanalysis": lambda **_kwargs: (200, {"status": "ok"}),
        "resolve_jongga_message_filename": lambda _target_date: "jongga_v2_latest.json",
        "build_screener_result_for_message": lambda _file_data: ({}, 1, "2026-02-22"),
        "select_signals_for_reanalysis": lambda **_kwargs: [],
        "build_jongga_news_analysis_items": lambda _signals: [],
        "apply_gemini_reanalysis_results": lambda **_kwargs: 0,
    }
    base.update(overrides)
    return base


def _create_client(data_dir: str, deps: dict):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("jongga_execution_test", __name__)
    register_jongga_execution_routes(
        bp,
        data_dir=data_dir,
        logger=type("L", (), {"error": lambda *_a, **_k: None})(),
        load_json_file=deps["load_json_file"],
        launch_jongga_v2_screener=deps["launch_jongga_v2_screener"],
        run_jongga_v2_background_pipeline=deps["run_jongga_v2_background_pipeline"],
        execute_single_stock_analysis=deps["execute_single_stock_analysis"],
        execute_jongga_gemini_reanalysis=deps["execute_jongga_gemini_reanalysis"],
        resolve_jongga_message_filename=deps["resolve_jongga_message_filename"],
        build_screener_result_for_message=deps["build_screener_result_for_message"],
        select_signals_for_reanalysis=deps["select_signals_for_reanalysis"],
        build_jongga_news_analysis_items=deps["build_jongga_news_analysis_items"],
        apply_gemini_reanalysis_results=deps["apply_gemini_reanalysis_results"],
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def test_run_jongga_v2_screener_route_delegates_launch(tmp_path: Path):
    captured = {}

    def _launch(**kwargs):
        captured.update(kwargs)
        return 200, {"status": "started"}

    client = _create_client(str(tmp_path), _build_deps(launch_jongga_v2_screener=_launch))
    response = client.post("/api/kr/jongga-v2/run", json={"target_date": "2026-02-22"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "started"
    assert captured["req_data"]["target_date"] == "2026-02-22"
    assert callable(captured["load_v2_status"])
    assert callable(captured["save_v2_status"])


def test_get_jongga_v2_status_route_reads_status_file_and_latest_updated_at(tmp_path: Path):
    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text(json.dumps({"isRunning": True}), encoding="utf-8")

    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {"updated_at": "2026-02-22T09:00:00"},
        ),
    )
    response = client.get("/api/kr/jongga-v2/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isRunning"] is True
    assert payload["status"] == "RUNNING"
    assert payload["updated_at"] == "2026-02-22T09:00:00"


def test_get_jongga_v2_status_route_returns_idle_when_status_file_is_corrupt(tmp_path: Path):
    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text("{invalid json", encoding="utf-8")

    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {"updated_at": "2026-02-22T09:00:00"},
        ),
    )
    response = client.get("/api/kr/jongga-v2/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isRunning"] is False
    assert payload["status"] == "IDLE"
    assert payload["updated_at"] == "2026-02-22T09:00:00"


def test_get_jongga_v2_status_route_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    import app.routes.kr_market_jongga_execution_routes as route_module

    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text("{}", encoding="utf-8")
    captured = {"path": None}

    def _loader(path: str):
        captured["path"] = path
        return {"isRunning": True, "updated_at": "2026-02-22T10:00:00"}

    monkeypatch.setattr(route_module, "load_json_payload_from_path", _loader)

    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {"updated_at": "2026-02-22T09:00:00"},
        ),
    )
    response = client.get("/api/kr/jongga-v2/status")

    assert response.status_code == 200
    assert captured["path"] == str(status_file)
    payload = response.get_json()
    assert payload["isRunning"] is True
    assert payload["status"] == "RUNNING"


def test_analyze_single_stock_route_returns_500_on_exception(tmp_path: Path):
    client = _create_client(
        str(tmp_path),
        _build_deps(
            execute_single_stock_analysis=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )
    response = client.post("/api/kr/jongga-v2/analyze", json={"code": "005930"})

    assert response.status_code == 500
    assert response.get_json() == {"error": "boom"}


def test_reanalyze_gemini_route_options_short_circuit(tmp_path: Path):
    client = _create_client(str(tmp_path), _build_deps())
    response = client.open("/api/kr/jongga-v2/reanalyze-gemini", method="OPTIONS")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_send_jongga_v2_message_route_returns_404_when_no_signal_data(tmp_path: Path):
    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {"signals": []},
        ),
    )
    response = client.post("/api/kr/jongga-v2/message", json={"target_date": "2026-02-22"})

    assert response.status_code == 404
    assert response.get_json()["status"] == "error"


def test_send_jongga_v2_message_route_sends_message(monkeypatch, tmp_path: Path):
    sent = {"count": 0}

    class _DummyMessenger:
        def send_screener_result(self, _result):
            sent["count"] += 1

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _DummyMessenger)

    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {"signals": [{"ticker": "005930"}]},
            build_screener_result_for_message=lambda _file_data: ({"ok": True}, 1, "2026-02-22"),
        ),
    )
    response = client.post("/api/kr/jongga-v2/message", json={"target_date": "2026-02-22"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["target_date"] == "2026-02-22"
    assert sent["count"] == 1


def test_run_jongga_v2_screener_route_persists_status_with_atomic_writer(monkeypatch, tmp_path: Path):
    import app.routes.kr_market_jongga_execution_routes as route_module

    writes: list[tuple[str, str]] = []

    def _atomic_write(path: str, content: str):
        writes.append((path, content))
        Path(path).write_text(content, encoding="utf-8")

    def _launch(**kwargs):
        kwargs["save_v2_status"](True)
        return 200, {"status": "started"}

    monkeypatch.setattr(route_module, "atomic_write_text", _atomic_write)

    client = _create_client(
        str(tmp_path),
        _build_deps(launch_jongga_v2_screener=_launch),
    )
    response = client.post("/api/kr/jongga-v2/run", json={})

    assert response.status_code == 200
    assert writes, "atomic_write_text should be called"
    status_path, status_content = writes[-1]
    assert status_path.endswith("v2_screener_status.json")
    assert "\"isRunning\": true" in status_content
