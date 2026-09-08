#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INFRA-064: latest GET admission, shared cooldown and user-visible state.

Only external analysis and thread scheduling are doubled. Real route, file lock,
state transitions and cleanup execute against tmp_path; no create_app().
"""
import logging
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from flask import Blueprint, Flask

from app.routes import kr_market
from app.routes.kr_market_system_http_routes import _register_market_gate_routes
from services import kr_market_market_gate_validity as validity


@pytest.fixture
def refresh(monkeypatch, tmp_path):
    clock = {"now": 1_000.0}
    calls = {"analyze": 0, "save": 0, "fail": False, "start_fail": False}
    scheduled = []

    class Analysis:
        def analyze(self):
            calls["analyze"] += 1
            if calls["fail"]:
                raise RuntimeError("synthetic analysis failure")
            return {"score": 72}

        def save_analysis(self, result):
            assert result == {"score": 72}
            calls["save"] += 1

    class Thread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self):
            if calls["start_fail"]:
                raise RuntimeError("synthetic thread failure")
            scheduled.append(self.target)

    monkeypatch.setitem(sys.modules, "engine.market_gate", types.SimpleNamespace(MarketGate=Analysis))
    monkeypatch.setattr(kr_market, "threading", types.SimpleNamespace(Thread=Thread))
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "_market_gate_now", lambda: clock["now"], raising=False)
    monkeypatch.setattr(kr_market, "is_market_gate_updating", False)
    monkeypatch.setattr(kr_market, "_market_gate_process_lock_handle", None)
    yield clock, calls, scheduled, tmp_path
    for target in scheduled:
        target()
    handle = kr_market._market_gate_process_lock_handle
    if handle is not None:
        handle.close()
    kr_market._market_gate_process_lock_handle = None
    kr_market.is_market_gate_updating = False


def _client(files, trigger):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("gate_cooldown_test", __name__)
    deps = {name: getattr(validity, name) for name in (
        "resolve_market_gate_filename", "evaluate_market_gate_validity",
        "apply_market_gate_snapshot_fallback", "build_market_gate_initializing_payload",
        "build_market_gate_empty_payload", "normalize_market_gate_payload",
    )}
    deps.update(load_json_file=lambda name, **_kw: dict(files.get(name, {})),
                trigger_market_gate_background_refresh=trigger)
    _register_market_gate_routes(bp, logger=logging.getLogger(__name__), deps=deps)
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


@pytest.mark.parametrize("query", ["date=19990101", "date=1999-01-02", "date=", "date=%20", "date=%ED%95%9C%EA%B8%80", "date=../../missing"])
def test_dated_missing_get_never_starts_today_analysis(refresh, query):
    _, calls, scheduled, _ = refresh
    response = _client({}, kr_market._trigger_market_gate_background_refresh).get('/api/kr/market-gate?' + query)
    assert response.status_code == 200
    assert response.json["message"] == "데이터 없음"
    assert response.json["status"] != "initializing"
    assert scheduled == []
    assert calls["analyze"] == 0


def test_dated_existing_snapshot_is_returned_without_refresh(refresh):
    files = {"market_gate_19990101.json": {"total_score": 72, "status": "GREEN", "dataset_date": "1999-01-01"}}
    response = _client(files, kr_market._trigger_market_gate_background_refresh).get('/api/kr/market-gate?date=1999-01-01')
    assert response.json["score"] == 72
    assert response.json["dataset_date"] == "1999-01-01"
    assert refresh[2] == []


@pytest.mark.parametrize("fail", [False, True])
def test_cooldown_begins_at_completion_and_survives_failed_analysis(refresh, fail):
    clock, calls, scheduled, _ = refresh
    calls["fail"] = fail
    assert kr_market._trigger_market_gate_background_refresh() is True
    clock["now"] = 1_600.0  # Long analysis: start-time cooldown alone is insufficient.
    scheduled.pop(0)()
    assert calls["analyze"] == 1
    assert calls["save"] == (0 if fail else 1)
    clock["now"] = 1_899.0
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert scheduled == []
    clock["now"] = 1_900.0
    assert kr_market._trigger_market_gate_background_refresh() is True
    scheduled.pop(0)()
    assert calls["analyze"] == 2


def test_inflight_get_keeps_initializing_without_starting_duplicate(refresh):
    client = _client({}, kr_market._trigger_market_gate_background_refresh)
    assert client.get('/api/kr/market-gate').json["status"] == "initializing"
    assert client.get('/api/kr/market-gate').json["status"] == "initializing"
    assert len(refresh[2]) == 1


def test_failed_refresh_returns_empty_during_cooldown_not_false_initializing(refresh):
    refresh[1]["fail"] = True
    client = _client({}, kr_market._trigger_market_gate_background_refresh)
    client.get('/api/kr/market-gate')
    refresh[2].pop(0)()
    response = client.get('/api/kr/market-gate')
    assert response.json["message"] == "데이터 없음"
    assert response.json["status"] != "initializing"
    assert refresh[1]["analyze"] == 1
    assert refresh[2] == []


def test_cooldown_retains_snapshot_score_instead_of_initializing(refresh):
    kr_market._trigger_market_gate_background_refresh()
    refresh[2].pop(0)()
    files = {"jongga_v2_latest.json": {"date": "2026-09-01", "market_status": {"total_score": 72, "status": "GREEN", "sectors": [{"name": "QA"}]}}}
    response = _client(files, kr_market._trigger_market_gate_background_refresh).get('/api/kr/market-gate')
    assert response.json["score"] == 72
    assert response.json["dataset_date"] == "2026-09-01"
    assert response.json["status"] != "initializing"


def test_thread_start_failure_releases_lock_and_preserves_cooldown(refresh):
    clock, calls, scheduled, path = refresh
    calls["start_fail"] = True
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert kr_market.is_market_gate_updating is False
    assert kr_market._market_gate_process_lock_handle is None
    calls["start_fail"] = False
    assert kr_market._trigger_market_gate_background_refresh() is False
    clock["now"] += 300
    assert kr_market._trigger_market_gate_background_refresh() is True
    assert len(scheduled) == 1


@pytest.mark.parametrize("raw", ["garbage", "NaN", "Infinity", "-1"])
def test_corrupt_cooldown_fails_closed_then_recovers(refresh, raw):
    clock, _, scheduled, path = refresh
    (path / '.market_gate_refresh.lock').write_text(raw)
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert scheduled == []
    clock["now"] += 300
    assert kr_market._trigger_market_gate_background_refresh() is True


def test_missing_fcntl_never_runs_uncoordinated_analysis(refresh, monkeypatch):
    monkeypatch.setattr(kr_market, 'fcntl', None)
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert refresh[2] == []


def test_lock_io_error_fails_closed_without_leaked_inflight_flag(refresh, monkeypatch):
    path = refresh[3] / 'not_a_directory'
    path.write_text('fixture')
    monkeypatch.setattr(kr_market, 'DATA_DIR', str(path))
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert kr_market.is_market_gate_updating is False
    assert kr_market._market_gate_process_lock_handle is None


def test_other_worker_sees_active_lock_then_shared_cooldown(refresh):
    clock, _, scheduled, path = refresh
    assert kr_market._trigger_market_gate_background_refresh() is True
    child = '''import sys,types,json
from app.routes import kr_market as k
k.DATA_DIR=sys.argv[1]
k._market_gate_now=lambda:float(sys.argv[2])
started=[]
class Thread:
 def __init__(self,**kw): pass
 def start(self): started.append(1)
k.threading=types.SimpleNamespace(Thread=Thread)
result=k._trigger_market_gate_background_refresh()
print(json.dumps({'result':result,'started':len(started)}))
'''
    env = {k: os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG') if k in os.environ}
    env.update(SCHEDULER_ENABLED='false', PYTHONDONTWRITEBYTECODE='1')
    def worker():
        import json
        out = subprocess.run([sys.executable, '-B', '-c', child, str(path), str(clock['now'])], env=env, capture_output=True, text=True, timeout=30, check=True)
        return json.loads(out.stdout.splitlines()[-1])
    assert worker() == {'result': True, 'started': 0}
    scheduled.pop(0)()
    assert worker() == {'result': False, 'started': 0}


def test_fresh_latest_get_never_schedules(refresh):
    from datetime import datetime
    files = {"market_gate.json": {"total_score": 72, "status": "GREEN", "timestamp": datetime.now().isoformat(), "dataset_date": datetime.now().strftime('%Y-%m-%d')}}
    response = _client(files, kr_market._trigger_market_gate_background_refresh).get('/api/kr/market-gate')
    assert response.json["score"] == 72
    assert refresh[2] == []


def test_explicit_today_is_still_read_only(refresh):
    from datetime import datetime
    response = _client({}, kr_market._trigger_market_gate_background_refresh).get('/api/kr/market-gate?date=' + datetime.now().strftime('%Y-%m-%d'))
    assert response.json["message"] == "데이터 없음"
    assert refresh[2] == []


@pytest.mark.parametrize('raw', ['100000000000', '1' * 128 + 'garbage'])
def test_future_or_oversized_state_recovers_after_one_cooldown(refresh, raw):
    clock, _, scheduled, path = refresh
    (path / '.market_gate_refresh.lock').write_text(raw)
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert scheduled == []
    clock['now'] += 300
    assert kr_market._trigger_market_gate_background_refresh() is True


def test_save_failure_still_preserves_cooldown(refresh, monkeypatch):
    def failed_save(self, result):
        raise OSError('synthetic save failure')
    monkeypatch.setattr(sys.modules['engine.market_gate'].MarketGate, 'save_analysis', failed_save)
    kr_market._trigger_market_gate_background_refresh()
    refresh[2].pop(0)()
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert kr_market.is_market_gate_updating is False
    assert kr_market._market_gate_process_lock_handle is None


def test_completion_write_failure_cannot_erase_shared_cooldown(refresh, monkeypatch):
    import builtins
    clock, calls, scheduled, path = refresh
    fail = {'write': False}
    original_open = builtins.open

    class Handle:
        def __init__(self, real):
            self.real = real

        def __getattr__(self, name):
            return getattr(self.real, name)

        def write(self, value):
            if fail['write']:
                raise OSError('synthetic timestamp write failure')
            return self.real.write(value)

    monkeypatch.setattr(kr_market, 'open', lambda *a, **kw: Handle(original_open(*a, **kw)), raising=False)
    assert kr_market._trigger_market_gate_background_refresh() is True
    clock['now'] = 1_600.0
    fail['write'] = True
    scheduled.pop(0)()
    fail['write'] = False
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert calls['analyze'] == 1


def test_abandoned_running_marker_is_cooled_before_retry(refresh):
    clock, _, scheduled, path = refresh
    (path / '.market_gate_refresh.lock').write_text('running')
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert scheduled == []
    clock['now'] += 299
    assert kr_market._trigger_market_gate_background_refresh() is False
    clock['now'] += 1
    assert kr_market._trigger_market_gate_background_refresh() is True


def test_completion_close_error_still_clears_local_inflight_state(refresh, monkeypatch):
    kr_market._trigger_market_gate_background_refresh()
    handle = kr_market._market_gate_process_lock_handle

    class CloseError:
        def __getattr__(self, name):
            return getattr(handle, name)

        def close(self):
            handle.close()
            raise OSError('synthetic close failure after fd closure')

    kr_market._market_gate_process_lock_handle = CloseError()
    refresh[2].pop(0)()
    assert kr_market.is_market_gate_updating is False
    assert kr_market._market_gate_process_lock_handle is None
    assert kr_market._trigger_market_gate_background_refresh() is False


@pytest.mark.parametrize('raw', ['cooldown:1300.0:end', 'garbage'])
def test_cooldown_reader_contention_is_not_reported_as_running(refresh, raw):
    import fcntl
    path = refresh[3] / '.market_gate_refresh.lock'
    with path.open('w+') as owner:
        owner.write(raw)
        owner.flush()
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert kr_market._trigger_market_gate_background_refresh() is False
        assert refresh[2] == []


def test_partial_completion_flush_is_not_accepted_as_expired_timestamp(refresh, monkeypatch):
    import builtins
    original_open = builtins.open
    fail = {'flush': False}

    class Handle:
        def __init__(self, real):
            self.real = real
            self.pending = None

        def __getattr__(self, name):
            return getattr(self.real, name)

        def write(self, value):
            if fail['flush']:
                self.pending = value
                return len(value)
            return self.real.write(value)

        def flush(self):
            if fail['flush']:
                # Enough bytes to replace all of "running", but no complete record.
                self.real.write(self.pending[:7])
                self.real.flush()
                raise OSError('synthetic partial flush')
            return self.real.flush()

    monkeypatch.setattr(kr_market, 'open', lambda *a, **kw: Handle(original_open(*a, **kw)), raising=False)
    assert kr_market._trigger_market_gate_background_refresh() is True
    refresh[0]['now'] = 2_000_000_000.0
    fail['flush'] = True
    refresh[2].pop(0)()
    fail['flush'] = False
    assert kr_market._trigger_market_gate_background_refresh() is False
    assert refresh[1]['analyze'] == 1
