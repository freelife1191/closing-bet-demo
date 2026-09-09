#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[CHAT-005] KRStockChatbot.close의 종료 전용 계약."""

from __future__ import annotations

import os
import sys
from unittest.mock import Mock

import pytest


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core


def test_close_releases_client_without_reloading_stock_map(monkeypatch):
    bot = object.__new__(chatbot_core.KRStockChatbot)
    client = object()
    bot.client = client
    close_client = Mock()
    monkeypatch.setattr(chatbot_core, "_close_client_impl", close_client)
    monkeypatch.setattr(
        chatbot_core.KRStockChatbot,
        "_load_stock_map",
        lambda _self: pytest.fail("close must not reload the stock map"),
    )

    bot.close()

    close_client.assert_called_once_with(client, chatbot_core.logger)
    assert bot.client is None
