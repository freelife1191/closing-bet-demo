#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messenger 하위호환 인터페이스 테스트
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.messenger import Messenger


def _sample_payload() -> dict:
    return {
        "title": "[Test] Notification",
        "gate_info": "Gate",
        "summary_title": "요약",
        "summary_desc": "메시지",
        "signals": [
            {
                "index": 1,
                "name": "테스트",
                "code": "5930",
                "market_icon": "🔵",
                "grade": "A",
                "score": 88.5,
                "change_pct": 1.1,
                "volume_ratio": 2.3,
                "trading_value": 123456,
                "f_buy": 1000,
                "i_buy": 2000,
                "entry": 70000,
                "target": 75000,
                "stop": 68000,
                "ai_reason": "테스트",
            }
        ],
    }


def test_compat_properties_map_to_config():
    messenger = Messenger()
    assert messenger.discord_url == messenger.config.discord_url
    assert messenger.telegram_token == messenger.config.telegram_token
    assert messenger.telegram_chat_id == messenger.config.telegram_chat_id
    assert messenger.smtp_user == messenger.config.smtp_user


def test_compat_send_methods_convert_payload_and_dispatch_to_sender():
    messenger = Messenger()
    calls = []

    class _DummySender:
        def __init__(self, channel):
            self.channel = channel

        def send(self, data):
            calls.append((self.channel, data))
            return True

    messenger.senders = {
        "discord": _DummySender("discord"),
        "telegram": _DummySender("telegram"),
        "email": _DummySender("email"),
    }

    payload = _sample_payload()
    messenger._send_discord(payload)
    messenger._send_telegram(payload)
    messenger._send_email(payload)

    assert [channel for channel, _ in calls] == ["discord", "telegram", "email"]

    message_data = calls[0][1]
    assert message_data.title == "[Test] Notification"
    assert message_data.signals[0].code == "005930"
    assert message_data.signals[0].score == 88.5
