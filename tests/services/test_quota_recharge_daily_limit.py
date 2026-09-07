#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[INFRA-027] 충전 하루 1회 제한 회귀 테스트

이 제한이 없으면 사이드바의 + 버튼을 두 번 눌러 무료 10회가 초기화된다.
"""

import os
import sys
import threading

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.kr_market_quota_runtime_service import recharge_user_usage


def _make_store(initial: dict[str, int]):
    """load/save 를 메모리 dict 하나로 잇는 최소 하네스."""
    store = dict(initial)

    def load(**_kwargs):
        return dict(store)

    def save(quota_data, **_kwargs):
        store.clear()
        store.update(quota_data)

    return store, load, save


def _recharge(store_fns, usage_key: str, today: int):
    _store, load, save = store_fns
    return recharge_user_usage(
        usage_key=usage_key,
        amount=5,
        today=today,
        quota_lock=threading.Lock(),
        load_quota_data_unlocked=load,
        save_quota_data_unlocked=save,
        load_json_file=lambda *_a, **_k: {},
        atomic_write_text=lambda *_a, **_k: None,
        quota_file_path="unused.json",
    )


def test_first_recharge_of_the_day_succeeds():
    store_fns = _make_store({"owner@example.com": 8})

    usage, recharged = _recharge(store_fns, "owner@example.com", 20260907)

    assert recharged is True
    assert usage == 3


def test_second_recharge_same_day_is_refused():
    store_fns = _make_store({"owner@example.com": 8})

    _recharge(store_fns, "owner@example.com", 20260907)
    usage, recharged = _recharge(store_fns, "owner@example.com", 20260907)

    assert recharged is False
    assert usage == 3


def test_next_day_recharge_succeeds():
    store_fns = _make_store({"owner@example.com": 8})

    _recharge(store_fns, "owner@example.com", 20260907)
    usage, recharged = _recharge(store_fns, "owner@example.com", 20260908)

    assert recharged is True
    assert usage == 0


def test_recharge_day_is_recorded_per_user():
    store_fns = _make_store({"owner@example.com": 8, "other@example.com": 8})

    _recharge(store_fns, "owner@example.com", 20260907)
    usage, recharged = _recharge(store_fns, "other@example.com", 20260907)

    assert recharged is True
    assert usage == 3


def test_missing_usage_key_does_nothing():
    store_fns = _make_store({})

    usage, recharged = _recharge(store_fns, "", 20260907)

    assert recharged is False
    assert usage == 0


def test_recharge_day_is_stored_as_integer():
    """날짜를 문자열로 넣으면 load_quota_data_unlocked 의 safe_usage_count 가 0 으로 뭉갠다.

    그러면 제한이 매번 통과되므로, 저장하는 값이 정수인지를 여기서 고정한다.
    """
    store, load, save = _make_store({"owner@example.com": 8})

    _recharge((store, load, save), "owner@example.com", 20260907)

    assert store["recharge_day:owner@example.com"] == 20260907
    assert isinstance(store["recharge_day:owner@example.com"], int)
