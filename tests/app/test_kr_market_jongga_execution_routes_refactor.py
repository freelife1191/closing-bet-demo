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

import pytest
from flask import Blueprint, Flask, g, request


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes.kr_market_jongga_execution_routes import register_jongga_execution_routes
import app.routes.kr_market_jongga_execution_routes as jongga_routes


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


@pytest.fixture(autouse=True)
def _admin_env(monkeypatch):
    """_seed_admin_identity 가 세우는 이메일이 실제로 관리자로 판정되게 한다."""
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")


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
    @app.before_request
    def _seed_admin_identity():
        # [INFRA-042] 가 이 라우트들에 require_admin 을 붙였다. 이 파일이 재는 것은
        # 게이트가 아니라 그 뒤의 위임 동작이므로, 관리자 신원을 세워 두고 그대로 잰다.
        # 게이트 자체는 tests/app/test_admin_gated_routes.py 가 잰다.
        #
        # OPTIONS 에서 일찍 빠지는 것은 실제 before_request 와 같다(app/__init__.py:171).
        # 아래 reanalyze-gemini preflight 검사가 신원 없이 200 을 받는 상태를 지킨다.
        if request.method == "OPTIONS":
            return
        g.user_email = "admin@example.com"

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


def test_run_jongga_v2_screener_route_passes_status_file_lock(tmp_path: Path):
    # [INFRA-115] 확인·저장을 워커 사이에서 직렬화하도록 v2_screener_status.json.lock 을 잡는 잠금을 넘긴다
    import fcntl

    held = []

    def _launch(**kwargs):
        with kwargs["status_lock"]():
            with open(tmp_path / "v2_screener_status.json.lock", "a+") as other:
                try:
                    fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    held.append(False)
                except BlockingIOError:
                    held.append(True)
        return 200, {"status": "started"}

    client = _create_client(str(tmp_path), _build_deps(launch_jongga_v2_screener=_launch))
    response = client.post("/api/kr/jongga-v2/run", json={})

    assert response.status_code == 200
    assert held == [True]


def test_run_jongga_v2_screener_route_checks_running_without_signature_cache(tmp_path: Path):
    # [INFRA-115] 잠금 안의 판정은 (mtime, size) 캐시를 거치지 않는다. 같은 틱·같은 크기로 바뀐 다른 워커 저장을 읽는다
    from services.kr_market_data_cache_service import load_json_payload_from_path

    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text('{"isRunning": false, "ownerPid": 9999}', encoding="utf-8")
    assert load_json_payload_from_path(str(status_file))["isRunning"] is False  # 캐시를 채운다
    before = os.stat(status_file)
    status_file.write_text('{"isRunning": true, "ownerPid": 10000}', encoding="utf-8")
    os.utime(status_file, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert os.stat(status_file).st_size == before.st_size
    captured = {}

    def _launch(**kwargs):
        captured["status"] = kwargs["load_v2_status"]()
        return 409, {"status": "error"}

    client = _create_client(str(tmp_path), _build_deps(launch_jongga_v2_screener=_launch))
    client.post("/api/kr/jongga-v2/run", json={})

    assert captured["status"]["isRunning"] is True


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


def test_get_jongga_v2_status_route_reflects_scheduler_jongga_running(monkeypatch, tmp_path: Path):
    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text(json.dumps({"isRunning": False}), encoding="utf-8")
    monkeypatch.setattr(
        jongga_routes,
        "get_scheduler_runtime_status",
        lambda data_dir="data": {
            "is_data_scheduling_running": True,
            "is_jongga_scheduling_running": True,
            "is_vcp_scheduling_running": False,
        },
    )

    client = _create_client(
        str(tmp_path),
        _build_deps(load_json_file=lambda _filename: {"updated_at": "2026-02-22T09:00:00"}),
    )
    response = client.get("/api/kr/jongga-v2/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isRunning"] is True
    assert payload["status"] == "RUNNING"
    assert payload["message"] == "종가베팅 스케쥴링 진행 중인 상태"
    assert payload["schedulerRunning"] is True


def test_get_jongga_v2_status_route_requests_latest_json_without_deep_copy(tmp_path: Path):
    captured = {"filename": None, "kwargs": None}

    def _load_json_file(filename: str, **kwargs):
        captured["filename"] = filename
        captured["kwargs"] = dict(kwargs)
        return {"updated_at": "2026-02-22T09:00:00"}

    client = _create_client(
        str(tmp_path),
        _build_deps(load_json_file=_load_json_file),
    )
    response = client.get("/api/kr/jongga-v2/status")

    assert response.status_code == 200
    assert captured["filename"] == "jongga_v2_latest.json"
    assert captured["kwargs"]["deep_copy"] is False


def test_get_jongga_v2_status_route_uses_shared_json_loader(monkeypatch, tmp_path: Path):
    import app.routes.kr_market_jongga_execution_routes as route_module

    status_file = tmp_path / "v2_screener_status.json"
    status_file.write_text("{}", encoding="utf-8")
    captured = {"path": None, "kwargs": None}

    def _loader(path: str, **kwargs):
        captured["path"] = path
        captured["kwargs"] = dict(kwargs)
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
    assert captured["kwargs"]["deep_copy"] is False
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
    assert response.get_json() == {"error": "Internal Server Error"}


def test_reanalyze_gemini_route_options_short_circuit(tmp_path: Path):
    """preflight 가 신원 없이 200 을 받는다.

    [INFRA-042] 가 이 라우트에 require_admin 을 붙이면서 응답의 출처가 바뀌었다. 종전에는
    뷰 본문의 `if request.method == "OPTIONS"` 가 {"status": "ok"} 를 냈는데, 이제 게이트가
    그 앞에서 Flask 의 기본 OPTIONS 응답을 돌려주고 뷰를 아예 부르지 않는다. 본문을 실은
    OPTIONS 요청이 무인증으로 뷰에 닿는 경로를 없애기 위해서다.

    그래서 본문 어서트를 상태 코드와 Allow 헤더로 바꿨다. 이 검사가 지키는 성질은 그대로다.
    게이트가 preflight 를 막으면 브라우저가 본 요청을 보내지 않아 화면이 멈춘다.

    뷰 본문의 OPTIONS 분기는 지우지 않고 남겼다. 지금은 닿지 않지만 게이트를 떼면 다시
    살아나는 두 번째 방어다.
    """
    client = _create_client(str(tmp_path), _build_deps())
    response = client.open("/api/kr/jongga-v2/reanalyze-gemini", method="OPTIONS")

    assert response.status_code == 200
    assert "POST" in (response.headers.get("Allow") or "")


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


def test_send_jongga_v2_message_route_skips_duplicate_without_force(monkeypatch, tmp_path: Path):
    sent = {"count": 0}

    class _DummyMessenger:
        def send_screener_result(self, _result):
            sent["count"] += 1

    import engine.messenger as messenger_module

    monkeypatch.setattr(messenger_module, "Messenger", _DummyMessenger)

    client = _create_client(
        str(tmp_path),
        _build_deps(
            load_json_file=lambda _filename: {
                "signals": [
                    {
                        "stock_code": "005930",
                        "stock_name": "삼성전자",
                        "grade": "S",
                        "entry_price": 70500,
                    }
                ]
            },
            build_screener_result_for_message=lambda _file_data: ({"ok": True}, 1, "2026-02-22"),
        ),
    )

    first_response = client.post("/api/kr/jongga-v2/message", json={"target_date": "2026-02-22"})
    second_response = client.post("/api/kr/jongga-v2/message", json={"target_date": "2026-02-22"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json()["status"] == "success"
    assert second_response.get_json()["status"] == "skipped"
    assert second_response.get_json()["duplicate"] is True
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
    # [INFRA-114] 기동 초기화가 소유 워커를 판정하도록 pid 를 남기고, 공개 상태 응답에는 싣지 않는다
    payload = json.loads(status_content)
    assert (payload["ownerPid"], payload["ownerPpid"]) == (os.getpid(), os.getppid())
    status_response = client.get("/api/kr/jongga-v2/status").get_json()
    assert status_response["isRunning"] is True
    assert "ownerPid" not in status_response and "ownerPpid" not in status_response
