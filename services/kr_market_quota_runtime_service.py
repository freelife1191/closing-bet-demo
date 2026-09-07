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


# 충전 이력을 사용량과 같은 파일에 둔다. load_quota_data_unlocked 가 모든 값을
# safe_usage_count 로 정수화하므로 날짜를 문자열로 넣으면 0 으로 뭉개져 제한이 매번
# 통과된다. 그래서 20260907 형태의 정수로 적는다. 이 접두사는 사용량 키(이메일 또는
# anon_ 로 시작하는 익명 ID)와 충돌하지 않는다.
RECHARGE_DAY_PREFIX = "recharge_day:"


def recharge_user_usage(
    *,
    usage_key: str | None,
    amount: int,
    today: int,
    quota_lock,
    load_quota_data_unlocked: Callable,
    save_quota_data_unlocked: Callable,
    load_json_file: Callable[[str], dict],
    atomic_write_text: Callable[[str, str], None],
    quota_file_path: str,
) -> tuple[int, bool]:
    """사용자 사용량을 amount 만큼 감소(충전)한다. 하루 한 번만 허용한다.

    돌려주는 두 번째 값은 실제로 충전했는지 여부다. 부르는 자리가 그것을 보고 안내
    문구를 고른다. 사용량만 돌려주면 거절과 「이미 0회」를 구분할 수 없다.
    """
    if not usage_key:
        return 0, False

    day_key = f"{RECHARGE_DAY_PREFIX}{usage_key}"
    with quota_lock:
        quota_data = load_quota_data_unlocked(load_json_file=load_json_file)
        current_usage = int(quota_data.get(usage_key, 0))
        if int(quota_data.get(day_key, 0)) >= int(today):
            return current_usage, False

        new_usage = max(0, current_usage - int(amount))
        quota_data[usage_key] = new_usage
        quota_data[day_key] = int(today)
        save_quota_data_unlocked(
            quota_data=quota_data,
            atomic_write_text=atomic_write_text,
            quota_file_path=quota_file_path,
        )
    return int(new_usage), True
