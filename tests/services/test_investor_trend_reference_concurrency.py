#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""참조 실패 TTL과 공유 요청의 생명주기."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from services import investor_trend_5day_service as service


def request(directory, ticker="005930"):
    return service._get_reference_trend_cached(data_dir=str(directory), source="pykrx", ticker=ticker, target_datetime="2026-09-18")


def success():
    return {"foreign": 50, "institution": 100, "latest_date": "2026-09-18",
            "details": [{"netForeignerBuyVolume": 10, "netInstitutionBuyVolume": 20} for _ in range(5)]}


@pytest.fixture(autouse=True)
def clear():
    service.clear_investor_trend_5day_memory_cache()
    yield
    service.clear_investor_trend_5day_memory_cache()


def test_failed_reference_retries_after_sixty_seconds(monkeypatch, tmp_path):
    clock = [100.0]
    calls = []
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", lambda **kw: calls.append(kw) or None)
    assert request(tmp_path) is None
    clock[0] = 159.99
    assert request(tmp_path) is None
    assert len(calls) == 1
    clock[0] = 160.0
    assert request(tmp_path) is None
    assert len(calls) == 2


def test_clear_during_fetch_cannot_publish_old_result(monkeypatch, tmp_path):
    entered, release = threading.Event(), threading.Event()
    saved = []
    def fetch(**kwargs):
        entered.set()
        assert release.wait(3)
        return success()
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", fetch)
    monkeypatch.setattr(service, "save_json_payload_to_sqlite", lambda **kw: saved.append(kw))
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(request, tmp_path)
        try:
            assert entered.wait(3)
            service.clear_investor_trend_5day_memory_cache()
        finally:
            release.set()
        assert future.result(timeout=3)["foreign"] == 50
    assert saved == []
    assert not service._REFERENCE_CACHE


def test_reference_cache_separates_data_directories(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", lambda **kw: calls.append(kw) or success())
    request(tmp_path / "a")
    request(tmp_path / "b")
    assert len(calls) == 2


@pytest.mark.parametrize("fails", [False, True])
def test_same_key_waiter_shares_result_and_is_always_released(monkeypatch, tmp_path, fails):
    from concurrent.futures import Future
    entered, waited, release = threading.Event(), threading.Event(), threading.Event()
    calls = []
    class ObservedFuture(Future):
        def result(self, timeout=None):
            waited.set()
            return super().result(timeout)
    def fetch(**kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(3)
        if fails:
            raise OSError("synthetic provider failure")
        return success()
    monkeypatch.setattr(service, "Future", ObservedFuture)
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", fetch)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(request, tmp_path)
        assert entered.wait(3)
        waiter = pool.submit(request, tmp_path)
        try:
            assert waited.wait(3)
        finally:
            release.set()
        first, second = owner.result(3), waiter.result(3)
    assert len(calls) == 1
    if fails:
        assert first is second is None
    else:
        first["details"][0]["netForeignerBuyVolume"] = -999
        assert second["details"][0]["netForeignerBuyVolume"] == 10
    assert not service._REFERENCE_INFLIGHT


def test_clear_starts_new_owner_without_old_result_overwriting(monkeypatch, tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
            return success()
        return {**success(), "foreign": 999}
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", fetch)
    with ThreadPoolExecutor(1) as pool:
        old = pool.submit(request, tmp_path)
        try:
            assert entered.wait(3)
            service.clear_investor_trend_5day_memory_cache()
            assert request(tmp_path)["foreign"] == 999
        finally:
            release.set()
        assert old.result(3)["foreign"] == 50
    assert request(tmp_path)["foreign"] == 999
    service.clear_investor_trend_5day_memory_cache()
    assert request(tmp_path)["foreign"] == 999
    assert len(calls) == 2


def test_failure_cache_is_bounded_and_expiry_starts_after_fetch(monkeypatch, tmp_path):
    clock = [100.0]
    calls = []
    def fail(**kwargs):
        calls.append(kwargs)
        clock[0] += 20
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(service, "_REFERENCE_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(service, "_fetch_pykrx_reference_trend", fail)
    request(tmp_path)
    clock[0] = 170
    request(tmp_path)
    assert len(calls) == 1
    request(tmp_path, "000001")
    request(tmp_path, "000002")
    assert len(service._REFERENCE_FAILURES) == 2
