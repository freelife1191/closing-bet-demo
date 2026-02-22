#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Chatbot Service 단위 테스트
"""

import json
import logging

from services.kr_market_chatbot_service import (
    check_chatbot_quota_guard,
    detect_chatbot_device_type,
    extract_chatbot_client_ip,
    handle_chatbot_history_request,
    handle_chatbot_profile_request,
    handle_chatbot_sessions_request,
    maybe_increment_chatbot_usage,
    parse_chatbot_request_payload,
    parse_chatbot_watchlist_json,
    parse_chatbot_watchlist_query,
    resolve_chatbot_owner_id,
    resolve_chatbot_usage_context,
    should_increment_free_quota,
    stream_chatbot_response,
    stream_chatbot_response_chunks,
)


class _DummyHistory:
    def __init__(self):
        self.deleted_session = None
        self.deleted_message = None
        self.cleared_all = False

    def get_all_sessions(self, owner_id=None):
        return [{"id": "s1", "owner_id": owner_id}]

    def create_session(self, model_name=None, owner_id=None):
        return f"{owner_id or 'anon'}:{model_name or 'default'}"

    def get_messages(self, session_id):
        return [{"role": "user", "content": f"hello:{session_id}"}]

    def clear_all(self):
        self.cleared_all = True

    def delete_session(self, session_id):
        self.deleted_session = session_id

    def delete_message(self, session_id, msg_index):
        self.deleted_message = (session_id, msg_index)
        return msg_index == 0


class _DummyBot:
    def __init__(self):
        self.history = _DummyHistory()

    def get_user_profile(self):
        return {"name": "tester", "persona": "swing"}

    def update_user_profile(self, name, persona):
        return {"name": name, "persona": persona}


class _StreamBot:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    def chat_stream(self, message, **kwargs):
        self.calls.append({"message": message, **kwargs})
        for chunk in self._chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


class _DummyFileStorage:
    def __init__(self, filename: str, content_type: str, body: bytes):
        self.filename = filename
        self.content_type = content_type
        self._body = body

    def read(self):
        return self._body


class _DummyFiles:
    def __init__(self, files):
        self._files = files

    def __contains__(self, key):
        return key == "file" and bool(self._files)

    def getlist(self, key):
        return list(self._files) if key == "file" else []


def test_resolve_chatbot_owner_id_prefers_authenticated_email():
    assert resolve_chatbot_owner_id("user@a.com", "session-x") == "user@a.com"
    assert resolve_chatbot_owner_id("user@example.com", "session-x") == "session-x"
    assert resolve_chatbot_owner_id(None, "session-x") == "session-x"


def test_handle_chatbot_sessions_request_get_returns_filtered_sessions():
    bot = _DummyBot()
    status, payload = handle_chatbot_sessions_request(
        bot=bot,
        method="GET",
        owner_id="owner-1",
        req_data={},
    )
    assert status == 200
    assert payload["sessions"][0]["owner_id"] == "owner-1"


def test_handle_chatbot_sessions_request_post_creates_session():
    bot = _DummyBot()
    status, payload = handle_chatbot_sessions_request(
        bot=bot,
        method="POST",
        owner_id="owner-2",
        req_data={"model": "gemini-2.0-flash"},
    )
    assert status == 200
    assert payload["session_id"] == "owner-2:gemini-2.0-flash"


def test_handle_chatbot_history_request_get_returns_messages():
    bot = _DummyBot()
    status, payload = handle_chatbot_history_request(
        bot=bot,
        method="GET",
        session_id="session-a",
        msg_index_str=None,
    )
    assert status == 200
    assert payload["history"][0]["content"] == "hello:session-a"


def test_handle_chatbot_history_request_delete_paths():
    bot = _DummyBot()

    status, payload = handle_chatbot_history_request(bot, "DELETE", "all", None)
    assert status == 200
    assert payload["status"] == "cleared all"
    assert bot.history.cleared_all is True

    status, payload = handle_chatbot_history_request(bot, "DELETE", None, None)
    assert status == 400
    assert payload["error"] == "Missing session_id"

    status, payload = handle_chatbot_history_request(bot, "DELETE", "session-b", None)
    assert status == 200
    assert payload["status"] == "deleted session"
    assert bot.history.deleted_session == "session-b"

    status, payload = handle_chatbot_history_request(bot, "DELETE", "session-c", "x")
    assert status == 400
    assert payload["error"] == "Invalid index format"

    status, payload = handle_chatbot_history_request(bot, "DELETE", "session-c", "1")
    assert status == 404
    assert payload["error"] == "Message not found"

    status, payload = handle_chatbot_history_request(bot, "DELETE", "session-c", "0")
    assert status == 200
    assert payload["status"] == "deleted message"


def test_handle_chatbot_profile_request_get_and_post():
    bot = _DummyBot()

    status, payload = handle_chatbot_profile_request(bot, "GET", {})
    assert status == 200
    assert payload["profile"]["name"] == "tester"

    status, payload = handle_chatbot_profile_request(bot, "POST", {"persona": "value"})
    assert status == 400
    assert payload["error"] == "Name is required"

    status, payload = handle_chatbot_profile_request(
        bot,
        "POST",
        {"name": "new-user", "persona": "value"},
    )
    assert status == 200
    assert payload["profile"]["name"] == "new-user"


def test_parse_chatbot_watchlist_query():
    assert parse_chatbot_watchlist_query(None) is None
    assert parse_chatbot_watchlist_query("") is None
    assert parse_chatbot_watchlist_query(" 005930, 000660 , ,035420 ") == [
        "005930",
        "000660",
        "035420",
    ]


def test_resolve_chatbot_usage_context_for_authenticated_and_session_user():
    context_auth = resolve_chatbot_usage_context(
        user_api_key_header="  key-1  ",
        user_email_header="user@test.com",
        session_id_header="session-a",
    )
    assert context_auth["user_api_key"] == "key-1"
    assert context_auth["usage_key"] == "user@test.com"

    context_guest = resolve_chatbot_usage_context(
        user_api_key_header="",
        user_email_header="user@example.com",
        session_id_header="session-b",
    )
    assert context_guest["user_api_key"] is None
    assert context_guest["usage_key"] == "session-b"


def test_check_chatbot_quota_guard_cases():
    status = check_chatbot_quota_guard(
        user_api_key="user-key",
        usage_key=None,
        max_free_usage=10,
        get_user_usage_fn=lambda _k: 0,
        server_key_available=False,
    )
    assert status == (False, None)

    use_free_tier, error = check_chatbot_quota_guard(
        user_api_key=None,
        usage_key=None,
        max_free_usage=10,
        get_user_usage_fn=lambda _k: 0,
        server_key_available=True,
    )
    assert use_free_tier is False
    assert error[0] == 400
    assert error[1]["code"] == "SESSION_REQUIRED"

    use_free_tier, error = check_chatbot_quota_guard(
        user_api_key=None,
        usage_key="session-1",
        max_free_usage=10,
        get_user_usage_fn=lambda _k: 0,
        server_key_available=False,
    )
    assert use_free_tier is False
    assert error[0] == 503
    assert error[1]["code"] == "SERVER_CONFIG_MISSING"

    use_free_tier, error = check_chatbot_quota_guard(
        user_api_key=None,
        usage_key="session-2",
        max_free_usage=10,
        get_user_usage_fn=lambda _k: 10,
        server_key_available=True,
    )
    assert use_free_tier is False
    assert error[0] == 402
    assert error[1]["code"] == "QUOTA_EXCEEDED"

    use_free_tier, error = check_chatbot_quota_guard(
        user_api_key=None,
        usage_key="session-3",
        max_free_usage=10,
        get_user_usage_fn=lambda _k: 3,
        server_key_available=True,
    )
    assert use_free_tier is True
    assert error is None


def test_parse_chatbot_watchlist_json_handles_error():
    logger = logging.getLogger("test")
    assert parse_chatbot_watchlist_json('["A","B"]', logger=logger) == ["A", "B"]
    assert parse_chatbot_watchlist_json("not-json", logger=logger) is None


def test_parse_chatbot_request_payload_supports_json_and_multipart():
    logger = logging.getLogger("test")

    json_payload = parse_chatbot_request_payload(
        content_type="application/json",
        form_data={},
        request_files=_DummyFiles([]),
        request_json={"message": "hi", "model": "m1", "session_id": "s1", "persona": "p1"},
        default_session_id="fallback",
        logger=logger,
    )
    assert json_payload["message"] == "hi"
    assert json_payload["model_name"] == "m1"
    assert json_payload["session_id"] == "s1"
    assert json_payload["persona"] == "p1"

    multipart_payload = parse_chatbot_request_payload(
        content_type="multipart/form-data; boundary=xyz",
        form_data={"message": "file", "model": "m2", "watchlist": '["005930"]'},
        request_files=_DummyFiles([_DummyFileStorage("a.txt", "text/plain", b"abc")]),
        request_json=None,
        default_session_id="fallback",
        logger=logger,
    )
    assert multipart_payload["message"] == "file"
    assert multipart_payload["watchlist"] == ["005930"]
    assert len(multipart_payload["files"]) == 1
    assert multipart_payload["files"][0]["mime_type"] == "text/plain"


def test_device_ip_and_quota_increment_helpers():
    assert detect_chatbot_device_type("iphone", "Mozilla") == "MOBILE"
    assert detect_chatbot_device_type("linux", "Desktop") == "WEB"

    assert extract_chatbot_client_ip("1.2.3.4, 5.6.7.8", "9.9.9.9") == "1.2.3.4"
    assert extract_chatbot_client_ip(None, "9.9.9.9") == "9.9.9.9"

    assert should_increment_free_quota(True, False, "정상 응답") is True
    assert should_increment_free_quota(True, True, "정상 응답") is False
    assert should_increment_free_quota(True, False, "⚠️ 경고") is False

    increments = {"count": 0}

    def _inc(_usage_key):
        increments["count"] += 1
        return increments["count"]

    maybe_increment_chatbot_usage(
        use_free_tier=True,
        usage_key="session-1",
        stream_has_error=False,
        full_response="정상 응답",
        increment_user_usage_fn=_inc,
        logger=logging.getLogger("test"),
    )
    maybe_increment_chatbot_usage(
        use_free_tier=True,
        usage_key="session-1",
        stream_has_error=False,
        full_response="⚠️ 경고",
        increment_user_usage_fn=_inc,
        logger=logging.getLogger("test"),
    )
    assert increments["count"] == 1


def test_stream_chatbot_response_chunks_success_calls_finalize():
    bot = _StreamBot(
        [
            {"chunk": "안녕"},
            {"usage_metadata": {"prompt_tokens": 11}},
            {"chunk": " 반가워"},
        ]
    )
    finalized = {}

    def _finalize(full_response, usage_metadata, stream_has_error):
        finalized["full_response"] = full_response
        finalized["usage_metadata"] = usage_metadata
        finalized["stream_has_error"] = stream_has_error

    chunks = list(
        stream_chatbot_response_chunks(
            bot=bot,
            payload={
                "message": "hi",
                "session_id": "s1",
                "model_name": "m1",
                "files": [],
                "watchlist": None,
                "persona": None,
            },
            user_api_key=None,
            usage_key="owner-1",
            logger=logging.getLogger("test"),
            on_finalize=_finalize,
        )
    )

    assert len(chunks) == 3
    assert all(item.startswith("data: ") for item in chunks)
    assert finalized["full_response"] == "안녕 반가워"
    assert finalized["usage_metadata"] == {"prompt_tokens": 11}
    assert finalized["stream_has_error"] is False


def test_stream_chatbot_response_chunks_yields_error_event_when_exception():
    bot = _StreamBot([RuntimeError("boom")])
    finalized = {}

    def _finalize(full_response, usage_metadata, stream_has_error):
        finalized["full_response"] = full_response
        finalized["usage_metadata"] = usage_metadata
        finalized["stream_has_error"] = stream_has_error

    chunks = list(
        stream_chatbot_response_chunks(
            bot=bot,
            payload={
                "message": "hi",
                "session_id": "s2",
                "model_name": "m2",
                "files": [],
                "watchlist": None,
                "persona": None,
            },
            user_api_key=None,
            usage_key="owner-2",
            logger=logging.getLogger("test"),
            on_finalize=_finalize,
        )
    )

    assert len(chunks) == 1
    raw_json = chunks[0].replace("data: ", "").strip()
    error_payload = json.loads(raw_json)
    assert error_payload["error"] == "boom"
    assert finalized["full_response"] == ""
    assert finalized["usage_metadata"] == {}
    assert finalized["stream_has_error"] is True


def test_stream_chatbot_response_runs_finalize_hooks():
    bot = _StreamBot([{"chunk": "hello"}])
    logged = {"calls": 0}
    increments = {"calls": 0}

    def _log_activity(full_response, usage_metadata, stream_has_error):
        logged["calls"] += 1
        assert full_response == "hello"
        assert usage_metadata == {}
        assert stream_has_error is False

    def _increment(_usage_key):
        increments["calls"] += 1
        return increments["calls"]

    chunks = list(
        stream_chatbot_response(
            bot=bot,
            payload={
                "message": "hi",
                "session_id": "s2",
                "model_name": "m2",
                "files": [],
                "watchlist": None,
                "persona": None,
            },
            user_api_key=None,
            usage_key="session-x",
            use_free_tier=True,
            logger=logging.getLogger("test"),
            increment_user_usage_fn=_increment,
            log_activity_fn=_log_activity,
        )
    )

    assert len(chunks) == 1
    assert logged["calls"] == 1
    assert increments["calls"] == 1
