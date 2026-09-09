#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHAT-008·009 실제 챗봇 라우트용 합성 Flask fixture.

이 fixture는 ``git archive``로 만든 scratch checkout에서만 실행한다. 제품 Flask
factory를 부르지 않고 챗봇·쿼터 라우트만 실제 등록하며, LLM 스트림과 화면 주변의
시장 조회만 합성 값으로 대체한다. 대화·세션·프로필·명령·쿼터 로직은 제품 코드를 쓴다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Iterator

from flask import Blueprint, Flask, g, jsonify, request


DEFAULT_ANONYMOUS_OWNER = "qa_browser_session"
DEFAULT_MODEL = "gemini-3.7-flash"
FIXTURE_STATE_DIRNAME = ".qa-slash-fixture-state"
SOURCE_REPO = Path("/Users/freelife/vibe/lecture/hodu/closing-bet-demo").resolve()


class FixtureError(RuntimeError):
    """격리 규약을 만족하지 못했을 때 발생한다."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_scratch_repo(raw_repo: str) -> Path:
    """현재 fixture가 들어 있는 git-archive scratch만 허용한다."""
    repo = Path(raw_repo).expanduser().resolve()
    fixture_root = _repo_root()
    expected_fixture = repo / "docs/dev-cycle/evidence/slash-batch-20260909/fixture.py"

    _assert(repo.is_dir(), "--repo는 존재하는 scratch checkout이어야 합니다.")
    _assert(repo == fixture_root, "--repo는 이 fixture가 들어 있는 checkout과 같아야 합니다.")
    _assert(expected_fixture.resolve() == Path(__file__).resolve(), "fixture 경로가 예상 위치와 다릅니다.")
    _assert(repo != SOURCE_REPO, "원본 저장소에서는 fixture를 실행할 수 없습니다.")
    _assert(not (repo / ".git").exists(), "git archive로 만든 scratch checkout에서만 실행할 수 있습니다.")
    _assert((repo / "app/routes/kr_market_chatbot_routes.py").is_file(), "챗봇 라우트 소스가 없습니다.")
    _assert((repo / "chatbot/storage.py").is_file(), "챗봇 저장소 소스가 없습니다.")
    return repo


def _prepare_environment(repo: Path) -> None:
    """fixture 프로세스에서만 외부 모델 설정을 무해한 합성 값으로 고정한다."""
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    os.environ["ZAI_API_KEY"] = "qa-fixture-no-network"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    os.environ["SCHEDULER_ENABLED"] = "false"
    os.environ["CHATBOT_AVAILABLE_MODELS"] = DEFAULT_MODEL
    os.environ["GEMINI_MODEL"] = DEFAULT_MODEL
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def _state_dir(repo: Path, *, reset: bool) -> Path:
    state_dir = (repo / FIXTURE_STATE_DIRNAME).resolve()
    _assert(_is_relative_to(state_dir, repo), "합성 상태 경로가 scratch checkout 밖입니다.")
    if state_dir.exists():
        _assert(state_dir.is_dir() and not state_dir.is_symlink(), "기존 합성 상태 경로가 안전하지 않습니다.")
        if reset:
            shutil.rmtree(state_dir)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return state_dir


class _FakeUsage:
    prompt_token_count = 3
    candidates_token_count = 5
    total_token_count = 8


class _FakeChunk:
    def __init__(self, text: str) -> None:
        self.text = text
        self.usage_metadata = _FakeUsage()


class _FakeChatSession:
    def send_message_stream(self, _content_parts: list[Any]) -> Iterator[_FakeChunk]:
        yield _FakeChunk("QA fixture 모델 응답입니다.")


class _FakeChats:
    calls = 0
    def create(self, *, model: str, history: list[dict[str, Any]]) -> _FakeChatSession:
        del model, history
        self.calls += 1
        return _FakeChatSession()


class _FakeClient:
    chats = _FakeChats()


def _build_fixture_chatbot(state_dir: Path) -> Any:
    """실제 저장소·명령 믹스인을 조립하고 모델 호출만 가짜로 바꾼다."""
    from chatbot.chat_handlers import handle_chat_stream
    from chatbot.core_command_mixin import CoreCommandMixin
    from chatbot.runtime_setup_service import get_user_profile, update_user_profile
    from chatbot.storage import HistoryManager, MemoryManager

    class FixtureChatbot(CoreCommandMixin):
        def __init__(self) -> None:
            self.user_id = "qa_fixture"
            self.history = HistoryManager(self.user_id, data_dir=state_dir)
            self.memory = MemoryManager(self.user_id, data_dir=state_dir)
            self.client = _FakeClient()
            self.available_models = [DEFAULT_MODEL]
            self.current_model_name = DEFAULT_MODEL
            self._data_cache: Any = None
            self._cache_timestamp: Any = None

        def _resolve_active_client(self, api_key: str | None) -> tuple[Any, None]:
            del api_key
            return self.client, None

        def _build_chat_payload(
            self,
            user_message: str,
            session_id: str,
            target_model_name: str,
            files: list[Any] | None,
            watchlist: list[Any] | None,
            persona: str | None,
            owner_id: str | None,
        ) -> tuple[list[dict[str, Any]], list[Any]]:
            del target_model_name, files, watchlist, persona, owner_id
            return self.history.get_messages(session_id), [user_message]

        def _normalize_markdown_response(self, text: str) -> str:
            return text

        def get_available_models(self) -> list[str]:
            return list(self.available_models)

        def set_model(self, model_name: str) -> bool:
            if model_name not in self.available_models:
                return False
            self.current_model_name = model_name
            return True

        def get_welcome_message(self) -> str:
            return "QA fixture 스마트머니봇입니다."

        def get_daily_suggestions(
            self,
            watchlist: list[str] | None = None,
            persona: str | None = None,
        ) -> list[str]:
            del watchlist, persona
            return ["QA fixture 질문을 입력하세요."]

        def get_user_profile(self, owner_id: str | None = None) -> dict[str, Any]:
            return get_user_profile(self.memory, owner_id)

        def update_user_profile(self, name: str, persona: str, owner_id: str) -> dict[str, Any]:
            return update_user_profile(self.memory, name, persona, owner_id)

        def get_status(self, owner_id: str | None = None) -> dict[str, Any]:
            return {
                "user_id": self.user_id,
                "model": self.current_model_name,
                "available_models": self.get_available_models(),
                "memory_count": len(self.memory.view(owner_id)) if owner_id else 0,
                "history_count": len(self.history.get_all_sessions(owner_id=owner_id)),
            }

        def chat_stream(
            self,
            user_message: str,
            session_id: str | None = None,
            model: str | None = None,
            files: list[Any] | None = None,
            watchlist: list[Any] | None = None,
            persona: str | None = None,
            api_key: str | None = None,
            owner_id: str | None = None,
        ) -> Iterator[dict[str, Any]]:
            yield from handle_chat_stream(
                bot=self,
                user_message=user_message,
                session_id=session_id,
                model=model,
                files=files,
                watchlist=watchlist,
                persona=persona,
                api_key=api_key,
                owner_id=owner_id,
            )

    return FixtureChatbot()


def build_app(repo: Path, *, reset_state: bool = False) -> Flask:
    """실제 chatbot/quota 라우트와 안전한 화면 보조 GET만 등록한다."""
    _prepare_environment(repo)
    state_dir = _state_dir(repo, reset=reset_state)

    import chatbot
    from app.routes.kr_market_chatbot_routes import register_chatbot_and_quota_routes
    from services.identity_helpers import resolve_anonymous_id

    chatbot._chatbot_instance = _build_fixture_chatbot(state_dir)
    app = Flask(__name__)
    kr_bp = Blueprint("qa_kr", __name__)
    logger = logging.getLogger("slash_batch.fixture")
    usage: dict[str, int] = {}
    _FakeClient.chats.calls = 0

    def get_user_usage(usage_key: str | None) -> int:
        return usage.get(usage_key or "", 0)

    def increment_user_usage(usage_key: str | None) -> int:
        key = usage_key or ""
        usage[key] = get_user_usage(key) + 1
        return usage[key]

    def recharge_user_usage(usage_key: str | None, amount: int) -> tuple[int, bool]:
        del usage_key, amount
        return 0, False

    @app.before_request
    def install_fixture_identity() -> None:
        g.user_email = None
        g.session_id = resolve_anonymous_id(request.headers.get("X-Session-Id")) or DEFAULT_ANONYMOUS_OWNER

    register_chatbot_and_quota_routes(
        kr_bp,
        logger=logger,
        max_free_usage=10,
        get_user_usage_fn=get_user_usage,
        increment_user_usage_fn=increment_user_usage,
        recharge_usage_fn=recharge_user_usage,
    )
    app.register_blueprint(kr_bp, url_prefix="/api/kr")

    safe_get_payloads = {
        "/api/kr/market-gate": {"status": "GREEN", "label": "QA fixture", "sectors": []},
        "/api/kr/signals": {"signals": [], "total_scanned": 0},
        "/api/kr/status": {"last_update": None, "collected_stocks": 0, "signals_count": 0},
    }
    for index, (path, payload) in enumerate(safe_get_payloads.items()):
        app.add_url_rule(
            path,
            endpoint=f"qa_safe_get_{index}",
            view_func=lambda payload=payload: jsonify(payload),
            methods=["GET"],
        )

    @app.get("/__qa/state")
    def qa_state():
        return jsonify(usage=usage, model_calls=_FakeClient.chats.calls,
                       sessions=[{"id":sid,"title":item["title"]} for sid,item in chatbot._chatbot_instance.history.sessions.items()])

    @app.after_request
    def qa_record(response):
        with (state_dir / "requests.jsonl").open("a") as output:
            output.write(json.dumps({"method":request.method,"path":request.path,
                "status":response.status_code,"usage":dict(usage),"model_calls":_FakeClient.chats.calls})+"\n")
        return response

    return app


def _read_sse(response: Any) -> tuple[str, str]:
    events: list[dict[str, Any]] = []
    for raw_line in response.get_data(as_text=True).splitlines():
        if raw_line.startswith("data: "):
            events.append(json.loads(raw_line.removeprefix("data: ")))
    session_id = next((event["session_id"] for event in reversed(events) if event.get("session_id")), "")
    response_text = "".join(str(event.get("chunk", "")) for event in events)
    return session_id, response_text


def run_smoke(repo: Path) -> None:
    """슬래시 명령 무차감과 질문의 실제 저장/제목 생성을 한 요청 흐름으로 검사한다."""
    app = build_app(repo, reset_state=True)
    client = app.test_client()
    headers = {"Accept": "text/event-stream", "X-Session-Id": DEFAULT_ANONYMOUS_OWNER}
    session_id: str | None = None

    for command in ("/help", "/status", "/clear"):
        response = client.post(
            "/api/kr/chatbot",
            headers=headers,
            json={"message": command, "session_id": session_id},
        )
        _assert(response.status_code == 200, f"{command} SSE 응답이 실패했습니다.")
        session_id, command_text = _read_sse(response)
        _assert(session_id, f"{command}가 세션 ID를 반환하지 않았습니다.")
        _assert(command_text, f"{command}가 빈 응답을 반환했습니다.")
        quota = client.get("/api/kr/user/quota", headers=headers).get_json()
        _assert(quota["usage"] == 0, f"{command}가 무료 쿼터를 차감했습니다.")

    question = "QA 제목 확인 질문"
    response = client.post(
        "/api/kr/chatbot",
        headers=headers,
        json={"message": question, "session_id": session_id},
    )
    _assert(response.status_code == 200, "일반 질문 SSE 응답이 실패했습니다.")
    session_id, response_text = _read_sse(response)
    _assert("QA fixture 모델 응답" in response_text, "합성 모델 응답이 누락됐습니다.")

    sessions = client.get("/api/kr/chatbot/sessions", headers=headers).get_json()["sessions"]
    _assert(len(sessions) == 1, "질문 후 소유자 세션 목록이 정확하지 않습니다.")
    _assert(sessions[0]["title"] == question, "첫 비명령 질문이 세션 제목이 되지 않았습니다.")
    history = client.get(f"/api/kr/chatbot/history?session_id={session_id}", headers=headers).get_json()["history"]
    _assert(len(history) == 4, "기존 /clear 기록과 질문/모델 응답이 보존되지 않았습니다.")
    quota = client.get("/api/kr/user/quota", headers=headers).get_json()
    _assert(quota["usage"] == 1 and quota["remaining"] == 9, "일반 질문의 쿼터 증감이 정확하지 않습니다.")

    print(json.dumps({"smoke": "passed", "session_id": session_id, "usage": quota["usage"]}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="CHAT-008·009 scratch chatbot fixture")
    parser.add_argument("--repo", required=True, help="git archive로 만든 scratch checkout")
    parser.add_argument("--reset-state", action="store_true", help="scratch 합성 상태만 비운다")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve_parser = subparsers.add_parser("serve", help="fixture Flask를 loopback에서 실행")
    serve_parser.add_argument("--port", type=int, required=True)
    subparsers.add_parser("smoke", help="네트워크 없이 Flask test_client로 흐름 검사")
    args = parser.parse_args()

    try:
        repo = validate_scratch_repo(args.repo)
        if args.command == "smoke":
            run_smoke(repo)
            return 0

        _assert(args.port not in {3500, 5501}, "원본 서비스 포트는 fixture에 사용할 수 없습니다.")
        from werkzeug.serving import run_simple

        app = build_app(repo, reset_state=args.reset_state)
        run_simple("127.0.0.1", args.port, app, use_reloader=False, use_debugger=False)
        return 0
    except FixtureError as error:
        print(f"fixture error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
