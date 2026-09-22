#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[FE-045] 자기 기록 삭제 경로: 서명된 신원만 통과하고 세 저장소를 모두 부른다.

신원은 before_request 가 g.user_email 로 확정한다. 쿼리·본문의 owner_id 는 무시되어야 한다.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from flask import Blueprint, Flask, g

from app.routes.kr_market_user_data_routes import register_user_data_routes


class _Recorder:
    def __init__(self, *, fail: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def hit(self, name: str, owner: str, result):
        self.calls.append((name, owner))
        if self.fail == name:
            raise RuntimeError(name)
        return result


def _client(*, user_email: str | None, fail: str | None = None, session_count: int = 2):
    recorder = _Recorder(fail=fail)
    bot = SimpleNamespace(
        history=SimpleNamespace(clear_for_owner=lambda owner: recorder.hit("chat_sessions", owner, session_count)),
        memory=SimpleNamespace(delete_owner=lambda owner: recorder.hit("chat_memories", owner, True)),
    )
    paper = SimpleNamespace(delete_account=lambda *, owner_id: recorder.hit("paper_trading", owner_id, True))
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        g.user_email = user_email

    bp = Blueprint("user_data_test", __name__)
    register_user_data_routes(
        bp,
        logger=logging.getLogger("test.user_data"),
        get_chatbot_fn=lambda: bot,
        get_paper_trading_fn=lambda: paper,
        delete_user_usage_fn=lambda owner: recorder.hit("usage", owner, True),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client(), recorder


def test_anonymous_request_is_refused_before_any_store():
    client, recorder = _client(user_email=None)
    response = client.delete(
        "/api/kr/user/data?owner_id=victim@example.test",
        json={"owner_id": "victim@example.test"},
        headers={"X-User-Email": "victim@example.test"},
    )
    assert response.status_code == 401
    assert recorder.calls == []


def test_verified_owner_clears_every_store_with_its_own_email():
    client, recorder = _client(user_email="alice@example.test")
    response = client.delete("/api/kr/user/data", json={"owner_id": "victim@example.test"})
    assert response.status_code == 200
    assert response.get_json()["deleted"] == {
        "chat_sessions": 2, "chat_memories": True, "paper_trading": True, "usage": True,
    }
    assert recorder.calls == [
        (name, "alice@example.test")
        for name in ("chat_sessions", "chat_memories", "paper_trading", "usage")
    ]


def test_one_failing_store_still_clears_the_rest_and_reports_500():
    client, recorder = _client(user_email="alice@example.test", fail="paper_trading")
    response = client.delete("/api/kr/user/data")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["failed"] == ["paper_trading"]
    assert payload["deleted"] == {"chat_sessions": 2, "chat_memories": True, "usage": True}
    assert [name for name, _ in recorder.calls] == ["chat_sessions", "chat_memories", "paper_trading", "usage"]


def test_zero_sessions_is_a_success_not_a_failure():
    """clear_for_owner 의 0 건은 실패(False)가 아니다. `== False` 로 바꾸면 여기서 잡힌다."""
    client, _recorder = _client(user_email="alice@example.test", session_count=0)
    response = client.delete("/api/kr/user/data")
    assert response.status_code == 200
    assert response.get_json()["deleted"]["chat_sessions"] == 0


def test_chatbot_construction_failure_still_clears_the_other_stores():
    """get_chatbot() 의 지연 생성이 던져도 모의투자와 사용량은 지운다(계획 검토 B1)."""
    recorder = _Recorder()
    paper = SimpleNamespace(delete_account=lambda *, owner_id: recorder.hit("paper_trading", owner_id, True))
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _seed_identity():
        g.user_email = "alice@example.test"

    def _broken_chatbot():
        raise RuntimeError("chatbot init failed")

    bp = Blueprint("user_data_broken_bot", __name__)
    register_user_data_routes(
        bp,
        logger=logging.getLogger("test.user_data"),
        get_chatbot_fn=_broken_chatbot,
        get_paper_trading_fn=lambda: paper,
        delete_user_usage_fn=lambda owner: recorder.hit("usage", owner, True),
    )
    app.register_blueprint(bp, url_prefix="/api/kr")
    response = app.test_client().delete("/api/kr/user/data")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["failed"] == ["chat_sessions", "chat_memories"]
    assert payload["deleted"] == {"paper_trading": True, "usage": True}
    assert [name for name, _ in recorder.calls] == ["paper_trading", "usage"]
