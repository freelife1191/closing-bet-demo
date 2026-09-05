#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[CHAT-016] 세션 소유자 접근 판정 회귀 테스트

목록 필터와 접근 검사는 기준이 다르다. 목록은 「확실히 내 것인가」를 묻고 접근은
「확실히 남의 것인가」를 묻는다. 이 구분이 무너지면 둘 중 하나가 깨진다. 접근에
목록 기준을 쓰면 소유자가 기록되지 않은 레거시 세션이 통째로 열리지 않고, 목록에
접근 기준을 쓰면 레거시 세션이 모든 사용자의 목록에 나타난다.
"""

import os
import sys


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import chatbot.core as chatbot_core
from chatbot.storage_history_helpers import (
    is_session_accessible_by_owner,
    should_include_session_for_owner,
)


def test_owned_session_is_accessible_only_by_its_owner():
    session = {"owner_id": "owner-a"}

    assert is_session_accessible_by_owner(session, "owner-a") is True
    assert is_session_accessible_by_owner(session, "owner-b") is False
    assert is_session_accessible_by_owner(session, None) is False


def test_legacy_session_without_owner_stays_accessible():
    """owner_id 가 비어 있는 세션은 세션 ID 를 아는 요청에 열려 있다."""
    for session in ({"owner_id": None}, {"owner_id": ""}, {}):
        assert is_session_accessible_by_owner(session, "owner-a") is True
        assert is_session_accessible_by_owner(session, None) is True


def test_listing_filter_excludes_legacy_sessions():
    """목록은 소유자가 정확히 일치할 때만 포함한다. 접근 기준과 갈리는 자리다."""
    legacy = {"owner_id": None}

    assert should_include_session_for_owner(legacy, "owner-a") is False
    assert is_session_accessible_by_owner(legacy, "owner-a") is True

    assert should_include_session_for_owner({"owner_id": "owner-a"}, "owner-a") is True
    assert should_include_session_for_owner({"owner_id": "owner-a"}, "owner-b") is False


def test_listing_filter_refuses_unknown_requester():
    """소유자를 모르는 요청은 어느 세션도 목록으로 받지 못한다.

    이 분기가 없으면 owner_id 가 None 인 요청과 소유자가 비어 있는 레거시 세션이
    서로 같다고 판정되어, 인증 헤더 없는 요청이 레거시 세션 전부를 목록으로 받는다.
    목록 응답은 messages 까지 함께 실으므로 그것만으로 대화 전문이 새어 나간다.
    """
    for owner_id in (None, ""):
        assert should_include_session_for_owner({"owner_id": None}, owner_id) is False
        assert should_include_session_for_owner({"owner_id": ""}, owner_id) is False
        assert should_include_session_for_owner({}, owner_id) is False
        assert should_include_session_for_owner({"owner_id": "owner-a"}, owner_id) is False


def test_get_all_sessions_returns_nothing_for_unknown_requester(monkeypatch, tmp_path):
    """목록 조회의 실제 경로에서도 같은 판정이 나오는지 본다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u1")

    mine = manager.create_session(owner_id="owner-a")
    legacy = manager.create_session(owner_id=None)
    for session_id in (mine, legacy):
        manager.add_message(session_id, "user", "삼성전자 어때?")

    assert manager.get_all_sessions(owner_id=None) == []
    assert manager.get_all_sessions(owner_id="") == []
    assert [s["id"] for s in manager.get_all_sessions(owner_id="owner-a")] == [mine]


def test_history_manager_rejects_other_owner_and_unknown_session(monkeypatch, tmp_path):
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u1")

    owned = manager.create_session(owner_id="owner-a")
    legacy = manager.create_session(owner_id=None)

    assert manager.is_session_accessible(owned, "owner-a") is True
    assert manager.is_session_accessible(owned, "owner-b") is False
    assert manager.is_session_accessible(legacy, "owner-b") is True

    # 없는 세션은 남의 세션과 같은 판정을 받아야 존재 여부가 새지 않는다.
    assert manager.is_session_accessible("no-such-session", "owner-a") is False


def test_clear_for_owner_removes_only_that_owners_sessions(monkeypatch, tmp_path):
    """`/clear all` 이 부르는 경로다. 남의 세션과 레거시 세션은 남아야 한다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u1")

    mine = manager.create_session(owner_id="owner-a")
    theirs = manager.create_session(owner_id="owner-b")
    legacy = manager.create_session(owner_id=None)

    removed = manager.clear_for_owner("owner-a")

    assert removed == 1
    assert manager.get_session(mine) is None
    assert manager.get_session(theirs) is not None
    assert manager.get_session(legacy) is not None


def test_clear_for_owner_refuses_empty_owner(monkeypatch, tmp_path):
    """소유자를 모르면 아무것도 지우지 않는다. 레거시 세션 보호가 목적이다."""
    monkeypatch.setattr(chatbot_core, "DATA_DIR", tmp_path)
    manager = chatbot_core.HistoryManager(user_id="u1")

    legacy = manager.create_session(owner_id=None)

    assert manager.clear_for_owner(None) == 0
    assert manager.clear_for_owner("") == 0
    assert manager.get_session(legacy) is not None
