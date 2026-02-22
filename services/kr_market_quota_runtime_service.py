#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Quota Runtime Service
"""

from __future__ import annotations

from typing import Callable


def get_user_usage(
    *,
    usage_key: str | None,
    quota_lock,
    load_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
) -> int:
    """사용자 사용량 조회."""
    if not usage_key:
        return 0

    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        return int(quota_data.get(usage_key, 0))


def increment_user_usage(
    *,
    usage_key: str | None,
    quota_lock,
    load_quota_data_unlocked: Callable,
    save_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> int:
    """사용자 사용량 증가."""
    if not usage_key:
        return 0

    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        current_usage = int(quota_data.get(usage_key, 0))
        new_usage = current_usage + 1
        quota_data[usage_key] = new_usage
        save_quota_data_unlocked(
            quota_data=quota_data,
            atomic_write_text=atomic_write_text,
            quota_file_path=quota_file_path,
        )
        return int(new_usage)


def recharge_user_usage(
    *,
    usage_key: str | None,
    amount: int,
    quota_lock,
    load_quota_data_unlocked: Callable,
    save_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> int:
    """사용자 사용량을 amount 만큼 감소(충전)한다."""
    if not usage_key:
        return 0

    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        current_usage = int(quota_data.get(usage_key, 0))
        new_usage = max(0, current_usage - int(amount))
        quota_data[usage_key] = new_usage
        save_quota_data_unlocked(
            quota_data=quota_data,
            atomic_write_text=atomic_write_text,
            quota_file_path=quota_file_path,
        )
    return int(new_usage)
