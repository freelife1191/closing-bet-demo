#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""저장소·메모리 QA를 위한 scratch 전용 Flask fixture.

이 서버는 실제 챗봇 HTTP 등록 라우트와 MemoryManager/HistoryManager를 사용한다.
인증, LLM, 시장 데이터만 합성하며, 상태 변경은 fixture checkout 아래 임시 SQLite와
JSON 스냅샷으로 한정한다. 원본 checkout과 3500/5501 포트에서는 실행할 수 없다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Iterator

from flask import Blueprint, Flask, g, jsonify, request


SOURCE_REPO = Path("/Users/freelife/vibe/lecture/hodu/closing-bet-demo").resolve()
FIXTURE_PATH = Path("docs/dev-cycle/evidence/storage-memory-20260921/fixture.py")
SCRATCH_PREFIX = "storage-memory-20260921-"
STATE_DIR_NAME = ".qa-storage-memory"
BLOCKED_METHODS = {"PUT", "PATCH", "DELETE"}
FIXTURE_OWNER = "storage-fixture@example.test"
OTHER_OWNER = "other-storage-fixture@example.test"


class FixtureError(RuntimeError):
    """scratch 격리 조건이나 fixture 제어 계약 위반이다."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def validate_scratch_repo(raw_repo: str) -> Path:
    """git archive로 만든 이 fixture 전용 scratch만 허용한다."""
    repo = Path(raw_repo).expanduser().resolve()
    _assert(repo.is_dir(), "--repo는 존재하는 scratch checkout이어야 합니다.")
    _assert(repo == _repo_root(), "--repo는 이 fixture가 든 checkout이어야 합니다.")
    _assert(repo.name.startswith(SCRATCH_PREFIX), "storage-memory 전용 scratch checkout만 허용합니다.")
    _assert((repo / FIXTURE_PATH).resolve() == Path(__file__).resolve(), "fixture 경로가 다릅니다.")
    _assert(repo != SOURCE_REPO, "원본 저장소에서는 fixture를 실행할 수 없습니다.")
    _assert(not (repo / ".git").exists(), "git archive scratch checkout만 허용합니다.")
    for env_name in (".env", ".env.production", ".env.vertex"):
        _assert(not (repo / env_name).exists(), f"scratch에 {env_name} 파일이 있으면 실행할 수 없습니다.")
    return repo


def _limit_environment() -> None:
    """제품 코드 import 중에도 외부 모델 자격 증명을 읽지 못하게 비운다."""
    for name in (
        "GOOGLE_API_KEY", "OPENAI_API_KEY", "PERPLEXITY_API_KEY", "ZAI_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "USER_PROFILE",
    ):
        os.environ.pop(name, None)
    # 등록 stream route의 명령 경로는 서버 키의 존재만 먼저 확인한다. 이 값은
    # fixture 프로세스 안의 비밀 아닌 sentinel이며 SafeBot.client는 항상 None이다.
    os.environ["ZAI_API_KEY"] = "fixture-no-network"
    os.environ["CHATBOT_MEMORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS"] = "0"
    os.environ["CHATBOT_HISTORY_LEGACY_SNAPSHOT_INTERVAL_SECONDS"] = "0"


class SyntheticChatbot:
    """제품 저장소를 쓰고 외부 추론만 고정 응답으로 치환한 최소 bot 경계다."""

    def __init__(self, data_dir: Path):
        from chatbot.command_service import handle_command
        from chatbot.runtime_setup_service import get_user_profile, update_user_profile
        from chatbot.storage import HistoryManager
        from chatbot.storage_memory_manager import MemoryManager

        self.memory = MemoryManager("storage-fixture", data_dir=data_dir)
        self.history = HistoryManager("storage-fixture", data_dir=data_dir)
        self._handle_command = handle_command
        self._get_user_profile = get_user_profile
        self._update_user_profile = update_user_profile
        self.available_models = ["fixture-command-model"]
        self.current_model_name = self.available_models[0]
        # KRStockChatbot을 만들지 않는다. 이 값은 등록 route의 명령 전용 SSE가
        # 외부 AI client/ADC 경로로 내려가지 않음을 명시하는 합성 경계다.
        self.client = None
        self._seed_history()

    def _seed_history(self) -> None:
        """실제 HistoryManager 경로로 UI 대화 목록에 보일 안전한 seed를 만든다."""
        if self.history.get_all_sessions(owner_id=FIXTURE_OWNER):
            return
        session_id = self.history.create_session(
            model_name=self.current_model_name,
            owner_id=FIXTURE_OWNER,
            session_id="storage-fixture-history",
        )
        self.history.add_message(session_id, "user", "저장소 QA 대화 목록")
        self.history.add_message(session_id, "model", "합성 응답이며 외부 모델을 호출하지 않았습니다.")

    def get_welcome_message(self) -> str:
        return "저장소 QA fixture입니다."

    def get_available_models(self) -> list[str]:
        return list(self.available_models)

    def get_user_profile(self, owner_id: str | None = None) -> dict[str, Any]:
        return self._get_user_profile(self.memory, owner_id)

    def update_user_profile(self, name: str, persona: str, owner_id: str) -> dict[str, Any]:
        return self._update_user_profile(self.memory, name, persona, owner_id)

    def get_daily_suggestions(
        self,
        watchlist: list[str] | None = None,
        persona: str | None = None,
    ) -> list[dict[str, str]]:
        del watchlist, persona
        cache_key = "daily_suggestions_storage_fixture"
        cached = self.memory.get(cache_key, owner_id="")
        if isinstance(cached, dict) and isinstance(cached.get("value"), list):
            return list(cached["value"])
        suggestions = [
            {
                "title": "저장소 QA",
                "prompt": "일반 메모리와 프로필 보존을 확인해줘",
                "desc": "fixture SQLite 저장소 경계 확인",
                "icon": "fas fa-database",
            },
            {
                "title": "추천 캐시",
                "prompt": "추천 질문 캐시 상태를 알려줘",
                "desc": "재생성 가능한 공용 캐시 확인",
                "icon": "fas fa-lightbulb",
            },
        ]
        if not self.memory.save_daily_suggestions(cache_key, suggestions):
            raise RuntimeError("fixture daily suggestion cache 저장 실패")
        return suggestions

    def chat(self, message: str, model_name: str | None = None) -> dict[str, str]:
        del model_name
        return {"response": self._command_reply(message, None, FIXTURE_OWNER)}

    def _command_reply(self, message: str, session_id: str | None, owner_id: str) -> str:
        if message.strip() == "/clear all":
            return "⚠️ fixture에서는 전체 초기화 명령을 실행하지 않습니다."
        return self._handle_command(self, message, session_id, owner_id)

    def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        model: str | None = None,
        files: list[dict[str, Any]] | None = None,
        watchlist: Any = None,
        persona: str | None = None,
        api_key: str | None = None,
        owner_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        del model, files, watchlist, persona, api_key
        owner = owner_id or FIXTURE_OWNER
        reply = self._command_reply(message, session_id, owner)
        yield {
            "session_id": session_id,
            "chunk": reply,
            "done": True,
            "usage_metadata": {"source": "synthetic-no-llm", "tokens": 0},
        }


def _install_fixture_chatbot(bot: SyntheticChatbot) -> None:
    """등록 라우트가 실제 get_chatbot 호출 대신 fixture bot을 받게 한다."""
    import chatbot

    setattr(chatbot, "get_chatbot", lambda: bot)


def _dashboard_seed_payloads(storage_dir: Path) -> dict[str, Any]:
    """대표 대시보드 읽기 API가 실제 cache SQLite를 한 번 왕복하게 한다."""
    from services import kr_market_backtest_summary_cache as backtest_cache
    from services import kr_market_cumulative_cache as cumulative_cache
    from services import kr_market_data_cache_core as jongga_cache_core
    from services import kr_market_data_cache_jongga as jongga_cache
    from services import kr_market_vcp_signals_cache as vcp_cache

    logger = logging.getLogger(__name__)
    runtime_db = str(storage_dir / "runtime_cache.db")
    jongga_cache._JONGGA_PAYLOAD_SQLITE_DB_PATH = runtime_db
    cumulative_cache._CUMULATIVE_CACHE_DB_PATH = runtime_db
    backtest_cache._BACKTEST_SUMMARY_CACHE_DB_PATH = runtime_db

    jongga_payload = {
        "date": "2026-09-21",
        "total_candidates": 1,
        "filtered_count": 1,
        "status": "success",
        "updated_at": "2026-09-21T15:40:00+09:00",
        "signals": [{
            "stock_code": "005930", "stock_name": "삼성전자", "market": "KOSPI",
            "grade": "S", "current_price": 76_200, "entry_price": 75_500,
            "target_price": 81_000, "stop_price": 72_000,
            "trading_value": 1_240_000_000_000, "change_pct": 2.1, "volume_ratio": 2.4,
            "themes": ["반도체", "AI"],
            "score": {
                "total": 18, "news": 3, "volume": 3, "chart": 2, "supply": 2,
                "candle": 1, "timing": 1, "llm_reason": "fixture 종가 분석입니다.",
            },
            "score_details": {
                "volume_ratio": 2.4, "foreign_net_buy": 1_240_000_000_000,
                "inst_net_buy": 3_276_004_650, "bonus_score": 2,
                "bonus_breakdown": {"volume": 2, "candle": 0, "limit_up": 0},
            },
            "checklist": {"has_news": True, "supply_positive": True},
            "news_items": [{"title": "fixture 종가 뉴스", "url": "https://example.invalid/fixture"}],
        }],
    }
    seed_file = storage_dir / "jongga_v2_results_20260921.json"
    seed_file.write_text(json.dumps(jongga_payload, ensure_ascii=False), encoding="utf-8")
    jongga_cache_core.JONGGA_RESULT_PAYLOADS_CACHE.clear()
    jongga_cache.load_jongga_result_payloads(str(storage_dir), limit=1, logger=logger)
    jongga_cache_core.JONGGA_RESULT_PAYLOADS_CACHE.clear()
    cached_jongga_rows = jongga_cache.load_jongga_result_payloads(str(storage_dir), limit=1, logger=logger)
    _assert(len(cached_jongga_rows) == 1, "jongga cache SQLite roundtrip이 실패했습니다.")

    vcp_rows = [{
        "ticker": "005930", "name": "삼성전자", "market": "KOSPI", "signal_date": "2026-09-21",
        "current_price": 76_200, "entry_price": 75_000, "target_price": 82_000, "stop_price": 72_000,
        "score": 86, "vcp_score": 17, "contraction_ratio": 0.52,
        "foreign_5d": 1_240_000_000_000, "inst_5d": 3_276_004_650, "return_pct": 1.6,
        "gemini_recommendation": {"action": "BUY", "confidence": 82, "reason": "fixture Gemini 의견"},
        "gpt_recommendation": {"action": "HOLD", "confidence": 61, "reason": "fixture GPT 의견"},
    }]
    vcp_signature = ("storage-memory-fixture-vcp", "2026-09-21")
    vcp_cache.save_cached_vcp_signals(
        signature=vcp_signature, payload=vcp_rows, data_dir=str(storage_dir), logger=logger,
    )
    vcp_cache._VCP_SIGNALS_MEMORY_CACHE.clear()
    cached_vcp_rows = vcp_cache.get_cached_vcp_signals(
        signature=vcp_signature, data_dir=str(storage_dir), logger=logger,
    )
    _assert(cached_vcp_rows == vcp_rows, "VCP cache SQLite roundtrip이 실패했습니다.")

    grade_kpi = {"count": 1, "wins": 1, "losses": 0, "winRate": 100.0, "avgRoi": 2.1, "totalRoi": 2.1}
    cumulative_payload = {
        "kpi": {
            "totalSignals": 1, "wins": 1, "losses": 0, "open": 0, "winRate": 100.0,
            "avgRoi": 2.1, "totalRoi": 2.1, "avgDays": 2.0, "priceDate": "2026-09-21",
            "profitFactor": None, "recentWinRate": 100.0, "recentClosedCount": 1, "consecutiveLosses": 0,
            "roiByGrade": {grade: (dict(grade_kpi) if grade == "S" else {key: 0 for key in grade_kpi}) for grade in ("S", "A", "B", "D")},
        },
        "trades": [{
            "id": "fixture-cumulative-001", "date": "2026-09-18", "grade": "S", "name": "삼성전자",
            "code": "005930", "market": "KOSPI", "entry": 75_000, "outcome": "WIN", "roi": 2.1,
            "maxHigh": 3.4, "priceTrail": [75_000, 75_800, 76_200], "days": 2, "score": 18,
            "themes": ["반도체", "AI"],
        }],
    }
    cumulative_signature = ("storage-memory-fixture-cumulative", "2026-09-21")
    cumulative_cache.save_cached_cumulative_payload(
        signature=cumulative_signature, payload=cumulative_payload, logger=logger,
    )
    cumulative_cache.clear_cumulative_cache()
    cached_cumulative = cumulative_cache.get_cached_cumulative_payload(
        signature=cumulative_signature, logger=logger,
    )
    _assert(cached_cumulative == cumulative_payload, "cumulative cache SQLite roundtrip이 실패했습니다.")

    backtest_payload = {
        "vcp": {"status": "success", "count": 1, "win_rate": 100.0, "avg_return": 1.6},
        "closing_bet": {"status": "success", "count": 1, "win_rate": 100.0, "avg_return": 2.1, "candidates": []},
    }
    backtest_signature = ("storage-memory-fixture-backtest", "2026-09-21")
    backtest_cache.save_cached_backtest_summary(
        signature=backtest_signature, payload=backtest_payload, logger=logger,
    )
    backtest_cache.clear_backtest_summary_cache()
    cached_backtest = backtest_cache.get_cached_backtest_summary(
        signature=backtest_signature, logger=logger,
    )
    _assert(cached_backtest == backtest_payload, "backtest cache SQLite roundtrip이 실패했습니다.")
    return {
        "jongga": cached_jongga_rows[0][1],
        "vcp": cached_vcp_rows,
        "cumulative": cached_cumulative,
        "backtest": cached_backtest,
    }


def build_app(repo: Path, *, reset_log: bool = False) -> Flask:
    """실제 챗봇 route 등록과 임시 저장소를 연결한 fixture 앱을 만든다."""
    _limit_environment()
    state_dir = repo / STATE_DIR_NAME
    storage_dir = state_dir / "synthetic-data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    request_log = state_dir / "requests.jsonl"
    if reset_log:
        request_log.write_text("", encoding="utf-8")

    bot = SyntheticChatbot(storage_dir)
    _install_fixture_chatbot(bot)
    dashboard_payloads = _dashboard_seed_payloads(storage_dir)

    from app.routes.kr_market_chatbot_http_routes import register_chatbot_routes

    app = Flask("storage-memory-fixture")
    app.testing = True
    log_lock = threading.Lock()
    state: dict[str, str] = {"owner_id": FIXTURE_OWNER}

    @app.before_request
    def install_fixture_identity_and_boundary() -> Any:
        g.user_email = state["owner_id"]
        g.session_id = "storage-fixture-session"
        if request.method in BLOCKED_METHODS:
            return jsonify({"error": "fixture prohibits product mutation"}), 405
        if request.method == "POST" and request.path not in {
            "/__qa/control", "/api/kr/chatbot", "/api/kr/chatbot/profile", "/api/kr/chatbot/sessions", "/api/kr/realtime-prices",
        }:
            return jsonify({"error": "fixture prohibits product mutation"}), 405
        return None

    @app.after_request
    def record_request(response: Any) -> Any:
        row = {"method": request.method, "path": request.path, "status": response.status_code}
        with log_lock, request_log.open("a", encoding="utf-8") as output:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
        return response

    @app.post("/__qa/control")
    def qa_control() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) - {"owner"}:
            return jsonify({"error": "control body allows only owner"}), 400
        owner = payload.get("owner", "fixture")
        if owner == "fixture":
            state["owner_id"] = FIXTURE_OWNER
        elif owner == "other":
            state["owner_id"] = OTHER_OWNER
        else:
            return jsonify({"error": "owner must be fixture or other"}), 400
        return jsonify({"owner": owner})

    @app.get("/api/auth/session")
    def auth_session() -> Any:
        return jsonify({
            "user": {"name": "저장소 QA", "email": state["owner_id"], "image": None},
            "expires": "2099-12-31T23:59:59.000Z",
        })

    @app.get("/api/admin/check")
    def admin_check() -> Any:
        return jsonify({"isAdmin": False})

    @app.get("/api/kr/user/quota")
    @app.get("/api/kr/chatbot/quota")
    def quota() -> Any:
        return jsonify({"usage": 0, "used": 0, "limit": 10, "remaining": 10})

    @app.get("/api/kr/market-gate")
    def market_gate() -> Any:
        return jsonify({
            "score": 70, "label": "중립", "status": "YELLOW", "kospi_close": 2_700,
            "kospi_change_pct": 0.2, "kosdaq_close": 780, "kosdaq_change_pct": -0.1,
            "sectors": [], "source": "synthetic-no-market",
        })

    @app.get("/api/kr/ai-analysis")
    def ai_analysis() -> Any:
        return jsonify({"signals": dashboard_payloads["vcp"], "generated_at": "2026-09-21T15:40:00+09:00"})

    @app.post("/api/kr/realtime-prices")
    def realtime_prices() -> Any:
        data = request.get_json() or {}
        tickers = data.get("tickers", [])
        return jsonify({row["ticker"]: row["current_price"] for row in dashboard_payloads["vcp"] if row["ticker"] in tickers})

    @app.get("/api/kr/config/interval")
    def interval() -> Any:
        return jsonify({"interval": 30})

    @app.get("/api/kr/signals")
    def vcp_signals() -> Any:
        rows = dashboard_payloads["vcp"]
        return jsonify({"signals": rows, "total_scanned": 1, "generated_at": "2026-09-21T15:40:00+09:00"})

    @app.get("/api/kr/signals/dates")
    def vcp_signal_dates() -> Any:
        return jsonify(["2026-09-21"])

    @app.get("/api/kr/signals/status")
    def vcp_signal_status() -> Any:
        return jsonify({"running": False, "message": "fixture cache ready", "progress": 100})

    @app.get("/api/kr/jongga-v2/latest")
    def jongga_latest() -> Any:
        return jsonify(dashboard_payloads["jongga"])

    @app.get("/api/kr/jongga-v2/dates")
    def jongga_dates() -> Any:
        return jsonify(["2026-09-21"])

    @app.get("/api/kr/jongga-v2/status")
    def jongga_status() -> Any:
        return jsonify({"is_running": False, "message": "fixture cache ready"})

    @app.get("/api/kr/closing-bet/cumulative")
    def cumulative_performance() -> Any:
        payload = dashboard_payloads["cumulative"]
        trades = payload["trades"]
        return jsonify({
            **payload,
            "pagination": {"total": len(trades), "page": 1, "limit": 50, "totalPages": 1},
        })

    @app.get("/api/kr/backtest-summary")
    def backtest_summary() -> Any:
        return jsonify(dashboard_payloads["backtest"])

    @app.get("/api/kr/status")
    def data_status() -> Any:
        return jsonify({"status": "success", "data": {"last_update": "2026-09-21", "signals_count": 1}})

    blueprint = Blueprint("storage-memory-chatbot", __name__)
    register_chatbot_routes(
        blueprint,
        logger=logging.getLogger(__name__),
        max_free_usage=10,
        get_user_usage_fn=lambda _owner: 0,
        increment_user_usage_fn=lambda _owner: 0,
    )
    app.register_blueprint(blueprint, url_prefix="/api/kr")
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="storage-memory scratch-only fixture")
    parser.add_argument("--repo", required=True, help="fixture를 포함한 git archive scratch checkout")
    parser.add_argument("--port", required=True, type=int, help="원본 서비스와 다른 loopback 포트")
    parser.add_argument("--reset-log", action="store_true", help="scratch 요청 로그를 비웁니다")
    args = parser.parse_args()
    try:
        repo = validate_scratch_repo(args.repo)
        _assert(args.port not in {3500, 5501}, "원본 서비스 포트는 사용할 수 없습니다.")
        _assert(1_024 <= args.port <= 65_535, "port는 1024~65535 범위여야 합니다.")
        from werkzeug.serving import run_simple

        run_simple(
            "127.0.0.1",
            args.port,
            build_app(repo, reset_log=args.reset_log),
            use_reloader=False,
            use_debugger=False,
            threaded=True,
        )
        return 0
    except FixtureError as error:
        print(f"fixture error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
