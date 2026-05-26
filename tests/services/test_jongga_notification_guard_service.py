#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종가베팅 알림 중복 방지 서비스 회귀 테스트
"""

from datetime import datetime, timedelta

from services.jongga_notification_guard_service import (
    build_jongga_notification_key,
    build_jongga_notification_payload_digest,
    claim_jongga_notification_send,
    mark_jongga_notification_sent,
)


def test_build_jongga_notification_key_ignores_volatile_fields():
    """기준일이 같으면 payload 세부 내용과 무관하게 같은 알림 키를 써야 한다."""
    base_signal = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "grade": "S",
        "entry_price": 70000,
        "score": {"total": 92},
        "created_at": "2026-02-19T16:10:00",
    }
    updated_signal = {
        **base_signal,
        "created_at": "2026-02-19T16:12:00",
        "llm_reason": "재분석으로 설명 문구가 바뀜",
        "signal_time": "2026-02-19T16:12:00",
        "score_details": {"ai_comment": "다른 코멘트"},
    }

    assert build_jongga_notification_key("2026-02-19", [base_signal]) == (
        build_jongga_notification_key("2026-02-19", [updated_signal])
    )


def test_claim_jongga_notification_send_rejects_duplicate_payload(tmp_path):
    """동일 기준일은 최초 claim 후 중복 claim이 거절되어야 한다."""
    signal = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "grade": "S",
        "entry_price": 70000,
    }

    claimed, key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-02-19",
        signals=[signal],
        now=datetime(2026, 2, 19, 16, 0, 0),
    )
    mark_jongga_notification_sent(
        data_dir=str(tmp_path),
        key=key,
        now=datetime(2026, 2, 19, 16, 1, 0),
    )
    duplicate_claimed, duplicate_key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-02-19",
        signals=[signal],
        now=datetime(2026, 2, 19, 16, 2, 0),
    )

    assert claimed is True
    assert duplicate_claimed is False
    assert duplicate_key == key


def test_claim_jongga_notification_send_rejects_changed_payload_same_date(tmp_path):
    """같은 기준일이면 가격/점수가 바뀐 재분석 결과도 두 번째 발송하면 안 된다."""
    first_signal = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "grade": "S",
        "current_price": 70000,
        "entry_price": 70500,
        "score": {"total": 92},
    }
    changed_signal = {
        **first_signal,
        "current_price": 70100,
        "entry_price": 70600,
        "score": {"total": 93},
    }

    assert build_jongga_notification_payload_digest([first_signal]) != (
        build_jongga_notification_payload_digest([changed_signal])
    )

    first_claimed, key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-05-26",
        signals=[first_signal],
        now=datetime(2026, 5, 26, 17, 7, 0),
    )
    mark_jongga_notification_sent(
        data_dir=str(tmp_path),
        key=key,
        now=datetime(2026, 5, 26, 17, 7, 30),
    )
    second_claimed, second_key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-05-26",
        signals=[changed_signal],
        now=datetime(2026, 5, 26, 17, 10, 0),
    )

    assert first_claimed is True
    assert second_claimed is False
    assert second_key == key


def test_claim_jongga_notification_send_allows_stale_sending_claim(tmp_path):
    """발송 중 상태가 오래 남은 경우 다음 스케줄 실행에서 재시도할 수 있어야 한다."""
    signal = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "grade": "S",
    }

    first_claimed, key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-02-19",
        signals=[signal],
        now=datetime(2026, 2, 19, 16, 0, 0),
    )
    second_claimed, second_key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-02-19",
        signals=[signal],
        now=datetime(2026, 2, 19, 16, 0, 1),
    )
    stale_claimed, stale_key = claim_jongga_notification_send(
        data_dir=str(tmp_path),
        date_str="2026-02-19",
        signals=[signal],
        now=datetime(2026, 2, 19, 16, 0, 0) + timedelta(minutes=31),
    )

    assert first_claimed is True
    assert second_claimed is False
    assert second_key == key
    assert stale_claimed is True
    assert stale_key == key
