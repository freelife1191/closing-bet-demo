#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[FE-045] 계정 삭제가 무료 사용량과 충전 날짜를 함께 지운다."""

import threading

from services.kr_market_quota_runtime_service import RECHARGE_DAY_PREFIX, delete_user_usage


def _make_store(initial: dict[str, int]):
    """load/save 를 메모리 dict 하나로 잇는 최소 하네스."""
    store = dict(initial)

    def load(**_kwargs):
        return dict(store)

    def save(quota_data, **_kwargs):
        store.clear()
        store.update(quota_data)

    return store, load, save


def _delete(store_fns, usage_key):
    _store, load, save = store_fns
    return delete_user_usage(
        usage_key=usage_key,
        quota_lock=threading.Lock(),
        load_quota_data_unlocked=load,
        save_quota_data_unlocked=save,
        load_json_file=lambda *_a, **_k: {},
        atomic_write_text=lambda *_a, **_k: None,
        quota_file_path="unused.json",
    )


def test_delete_removes_usage_and_recharge_day_but_keeps_others():
    store_fns = _make_store({
        "alice@example.test": 7,
        f"{RECHARGE_DAY_PREFIX}alice@example.test": 20260922,
        "bob@example.test": 3,
    })

    assert _delete(store_fns, "alice@example.test") is True

    assert store_fns[0] == {"bob@example.test": 3}


def test_delete_without_key_or_unknown_owner():
    store_fns = _make_store({"bob@example.test": 3})

    assert _delete(store_fns, None) is False
    assert _delete(store_fns, "nobody@example.test") is True
    assert store_fns[0] == {"bob@example.test": 3}
