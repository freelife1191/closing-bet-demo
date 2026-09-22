#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 라우트 통합 테스트

헬퍼 분리 리팩토링 이후에도 실제 API 흐름이 유지되는지 검증한다.
"""

import copy
import io
import json
import os
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from flask import Flask


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.routes import kr_market


class _DummyVcpAnalyzer:
    # 재분석 서비스가 캐시 키를 정할 때 읽는 확정값.
    second_provider = "gpt"

    def get_available_providers(self):
        return ["gemini"]

    async def analyze_batch(self, stocks_to_analyze):
        results = {}
        for item in stocks_to_analyze:
            ticker = str(item.get("ticker", "")).zfill(6)
            if ticker == "000001":
                results[ticker] = {
                    "gemini_recommendation": {
                        "action": "BUY",
                        "confidence": 77,
                        "reason": "재분석 성공",
                    }
                }
            else:
                results[ticker] = {
                    "gemini_recommendation": {
                        "action": "N/A",
                        "confidence": 0,
                        "reason": "분석 실패",
                    }
                }
        return results


class _DummyChatbot:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    def chat_stream(self, message, **kwargs):
        self.calls.append({"message": message, **kwargs})
        for chunk in self._chunks:
            yield chunk


def _create_client():
    app = Flask(__name__)
    app.testing = True
    # [INFRA-027] 라우트는 헤더를 직접 읽지 않고 before_request 가 검증해 둔 g 를 읽는다.
    # 등록하지 않으면 X-Session-Id 를 넣어도 소유자가 조용히 None 이 된다.
    from app import _register_request_context

    _register_request_context(app)
    app.register_blueprint(kr_market.kr_bp, url_prefix="/api/kr")
    return app.test_client()


def _create_client_with_user(user_api_key=None, user_email=None):
    app = Flask(__name__)
    app.testing = True

    @app.before_request
    def _inject_user_context():
        from flask import g

        g.user_api_key = user_api_key
        g.user_email = user_email

    app.register_blueprint(kr_market.kr_bp, url_prefix="/api/kr")
    return app.test_client()


def _install_chatbot_module(monkeypatch, bot):
    # 실제 Vertex 호출 없이, 주입한 fake bot의 구성 완료 전제만 설정한다.
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "isolated-test-project")
    module = types.ModuleType("chatbot")
    module.get_chatbot = lambda: bot
    monkeypatch.setitem(sys.modules, "chatbot", module)


def _prepare_quota_store(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "QUOTA_FILE", str(tmp_path / "user_quota.json"))


def _count_rules(client, path: str, method: str) -> int:
    return sum(
        1
        for rule in client.application.url_map.iter_rules()
        if rule.rule == path and method in rule.methods
    )


def test_reanalyze_vcp_failed_ai_filters_failed_rows_and_updates_csv(monkeypatch, tmp_path: Path):
    signals_df = pd.DataFrame(
        [
            {
                "ticker": "1",
                "signal_date": "2026-02-20",
                "name": "Alpha",
                "ai_action": None,
                "ai_reason": None,
                "ai_confidence": 0,
                "current_price": 10000,
                "entry_price": 9800,
                "score": 7,
                "vcp_score": 6,
                "contraction_ratio": 12,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 0,
                "inst_1d": 0,
            },
            {
                "ticker": "2",
                "signal_date": "2026-02-20",
                "name": "Beta",
                "ai_action": "BUY",
                "ai_reason": "이미 분석 완료",
                "ai_confidence": 85,
                "current_price": 12000,
                "entry_price": 11000,
                "score": 8,
                "vcp_score": 7,
                "contraction_ratio": 10,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            },
            {
                "ticker": "3",
                "signal_date": "2026-02-20",
                "name": "Gamma",
                "ai_action": "HOLD",
                "ai_reason": "분석 실패",
                "ai_confidence": 0,
                "current_price": 9000,
                "entry_price": 9100,
                "score": 6,
                "vcp_score": 5,
                "contraction_ratio": 14,
                "foreign_5d": 0,
                "inst_5d": 0,
                "foreign_1d": 0,
                "inst_1d": 0,
            },
            {
                "ticker": "4",
                "signal_date": "2026-02-19",
                "name": "Delta",
                "ai_action": None,
                "ai_reason": None,
                "ai_confidence": 0,
                "current_price": 15000,
                "entry_price": 14500,
                "score": 7,
                "vcp_score": 6,
                "contraction_ratio": 11,
                "foreign_5d": 1,
                "inst_5d": 1,
                "foreign_1d": 1,
                "inst_1d": 1,
            },
        ]
    )

    output_csv = tmp_path / "signals_log.csv"

    monkeypatch.setattr(kr_market, "load_csv_file", lambda _: signals_df.copy())
    monkeypatch.setattr(kr_market, "get_data_path", lambda filename: str(tmp_path / filename))
    monkeypatch.setattr(kr_market, "_update_vcp_ai_cache_files", lambda *_: 1)
    monkeypatch.setitem(kr_market.VCP_STATUS, "running", False)

    import engine.vcp_ai_analyzer as vcp_ai_analyzer

    monkeypatch.setattr(vcp_ai_analyzer, "get_vcp_analyzer", lambda: _DummyVcpAnalyzer())

    # [INFRA-042] 가 이 라우트에 require_admin 을 붙였다. 이 검사가 재는 것은 실패 행
    # 필터와 CSV 갱신이지 인가가 아니므로 관리자 신원을 세우고 그대로 잰다. 게이트는
    # tests/app/test_admin_gated_routes.py 가 잰다.
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client_with_user(user_email="admin@example.com")
    res = client.post(
        "/api/kr/signals/reanalyze-failed-ai",
        json={"target_date": "2026-02-20"},
    )

    assert res.status_code == 200
    payload = res.get_json()
    assert payload["status"] == "success"
    assert payload["total_in_scope"] == 3
    assert payload["failed_targets"] == 2
    assert payload["updated_count"] == 1
    assert payload["still_failed_count"] == 1
    assert payload["cache_files_updated"] == 1

    assert output_csv.exists()
    written = pd.read_csv(output_csv, dtype={"ticker": str}, keep_default_na=False)
    written["ticker"] = written["ticker"].astype(str).str.zfill(6)

    row1 = written[written["ticker"] == "000001"].iloc[0]
    assert row1["ai_action"] == "BUY"
    # [JONGGA-008] 실패 행이 결측을 담으면서 이 열은 float 이 된다. 실제 signals_log 도
    # 값이 비어 있는 행이 있어 이미 float 으로 읽히므로, CSV 의 표기가 아니라 값을 본다.
    assert float(row1["ai_confidence"]) == 77.0
    assert row1["ai_reason"] == "재분석 성공"

    row3 = written[written["ticker"] == "000003"].iloc[0]
    assert row3["ai_action"] == "N/A"
    # [JONGGA-008] 재분석이 또 실패한 행은 0 이 아니라 빈 칸으로 남는다.
    assert row3["ai_confidence"] == ""
    assert row3["ai_reason"] == "분석 실패"


def test_get_kr_signals_dates_uses_file_mtime_cache(monkeypatch, tmp_path: Path):
    signals_path = tmp_path / "signals_log.csv"
    signals_path.write_text("placeholder", encoding="utf-8")

    call_counter = {"count": 0}

    def _load_csv(_filename):
        call_counter["count"] += 1
        # status·score·is_vcp 는 `[VCP-008]` 이후 날짜 목록도 함께 보는 판정 열이다.
        return pd.DataFrame(
            [
                {"signal_date": "2026-02-20", "status": "OPEN", "score": 85, "is_vcp": True},
                {"signal_date": "2026-02-19", "status": "OPEN", "score": 85, "is_vcp": True},
            ]
        )

    monkeypatch.setattr(kr_market, "load_csv_file", _load_csv)
    monkeypatch.setattr(kr_market, "get_data_path", lambda _filename: str(signals_path))

    client = _create_client()

    first = client.get("/api/kr/signals/dates")
    second = client.get("/api/kr/signals/dates")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == ["2026-02-20", "2026-02-19"]
    assert second.get_json() == ["2026-02-20", "2026-02-19"]
    assert call_counter["count"] == 1

    updated_mtime = signals_path.stat().st_mtime + 2
    os.utime(signals_path, (updated_mtime, updated_mtime))

    third = client.get("/api/kr/signals/dates")
    assert third.status_code == 200
    assert third.get_json() == ["2026-02-20", "2026-02-19"]
    assert call_counter["count"] == 2


def test_get_jongga_v2_latest_recalculates_grades_and_sorts(monkeypatch, tmp_path: Path):
    # 기준일이 과거면 stale 가드가 signals를 비워버리므로 오늘 날짜로 고정한다.
    latest_data = {
        "date": date.today().isoformat(),
        "signals": [
            {
                "ticker": "000001",
                "stock_code": "000001",
                "stock_name": "A",
                "grade": "D",
                "change_pct": 3.0,
                "trading_value": 500_000_000_000,
                "score": {"total": 8},
                "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                "entry_price": 10000,
                "current_price": 10300,
            },
            {
                "ticker": "000002",
                "stock_code": "000002",
                "stock_name": "B",
                "grade": "D",
                "change_pct": 3.0,
                "trading_value": 1_000_000_000_000,
                "score": {"total": 10},
                "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                "entry_price": 10000,
                "current_price": 10400,
            },
            {
                "ticker": "000003",
                "stock_code": "000003",
                "stock_name": "C",
                "grade": "D",
                "change_pct": 1.0,
                "trading_value": 80_000_000_000,
                "score": {"total": 4},
                "score_details": {"foreign_net_buy": 0, "inst_net_buy": 0},
                "entry_price": 10000,
                "current_price": 9900,
            },
        ],
        "by_grade": {"S": 0, "A": 0, "B": 0, "C": 0, "D": 3},
    }

    monkeypatch.setattr(kr_market, "load_json_file", lambda _: copy.deepcopy(latest_data))
    monkeypatch.setattr(kr_market, "get_data_path", lambda filename: str(tmp_path / filename))

    client = _create_client()
    res = client.get("/api/kr/jongga-v2/latest")

    assert res.status_code == 200
    payload = res.get_json()
    signals = payload["signals"]

    # grade 재산정 + 정렬(S>A>B)
    assert signals[0]["stock_code"] == "000002"
    assert signals[0]["grade"] == "S"
    assert signals[1]["stock_code"] == "000001"
    assert signals[1]["grade"] == "A"
    assert signals[2]["stock_code"] == "000003"
    assert signals[2]["grade"] == "D"

    assert payload["by_grade"]["S"] == 1
    assert payload["by_grade"]["A"] == 1
    assert payload["by_grade"]["D"] == 1


def test_get_jongga_v2_history_sorts_signals_with_shared_helper(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "load_json_file", lambda _: {})

    target_file = tmp_path / "jongga_v2_results_20260220.json"
    target_file.write_text(
        json.dumps(
            {
                "date": "2026-02-20",
                "signals": [
                    {
                        "stock_code": "000001",
                        "grade": "A",
                        "change_pct": 3.0,
                        "trading_value": 500_000_000_000,
                        "score": {"total": 8},
                        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                    },
                    {
                        "stock_code": "000002",
                        "grade": "D",
                        "change_pct": 3.0,
                        "trading_value": 1_000_000_000_000,
                        "score": {"total": 10},
                        "score_details": {"foreign_net_buy": 1, "inst_net_buy": 1},
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    client = _create_client()
    res = client.get("/api/kr/jongga-v2/history/2026-02-20")

    assert res.status_code == 200
    payload = res.get_json()
    assert [s["stock_code"] for s in payload["signals"]] == ["000002", "000001"]


def test_chatbot_free_tier_success_stream_increments_quota(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    bot = _DummyChatbot(
        [
            {"chunk": "안녕하세요"},
            {"usage_metadata": {"prompt_tokens": 12, "completion_tokens": 8}},
            {"chunk": " 반갑습니다"},
        ]
    )
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트 메시지"},
        headers={"X-Session-Id": "anon_session-abc"},
    )

    assert response.status_code == 200
    assert response.content_type.startswith("text/event-stream")
    assert "data:" in response.get_data(as_text=True)

    assert kr_market.get_user_usage("anon_session-abc") == 1
    assert bot.calls[0]["owner_id"] == "anon_session-abc"


def test_chatbot_warning_response_skips_quota_increment(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    bot = _DummyChatbot([{"chunk": "⚠️ API 키를 확인해주세요."}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트"},
        headers={"X-Session-Id": "anon_session-warning"},
    )

    assert response.status_code == 200
    assert kr_market.get_user_usage("anon_session-warning") == 0


def test_chatbot_quota_guard_blocks_when_limit_exceeded(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    quota_file = tmp_path / "user_quota.json"
    quota_file.write_text(
        json.dumps({"anon_session-limit": kr_market.MAX_FREE_USAGE}, ensure_ascii=False),
        encoding="utf-8",
    )

    bot = _DummyChatbot([{"chunk": "should-not-run"}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "테스트"},
        headers={"X-Session-Id": "anon_session-limit"},
    )

    assert response.status_code == 402
    payload = response.get_json()
    assert payload["code"] == "QUOTA_EXCEEDED"
    assert bot.calls == []


@pytest.mark.parametrize(
    "command",
    ["/status", "/help", "/clear", "/model", "/memory", "/unknown"],
)
def test_chatbot_slash_command_bypasses_exhausted_quota_without_increment(
    monkeypatch,
    tmp_path: Path,
    command: str,
):
    """파일 없는 정확한 슬래시 명령은 한도를 소진해도 실행하고 차감하지 않는다."""
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    quota_file = tmp_path / "user_quota.json"
    quota_file.write_text(
        json.dumps({"anon_session-command": kr_market.MAX_FREE_USAGE}, ensure_ascii=False),
        encoding="utf-8",
    )
    bot = _DummyChatbot([{"chunk": "명령 응답"}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": command},
        headers={"X-Session-Id": "anon_session-command"},
    )

    assert response.status_code == 200
    assert response.content_type.startswith("text/event-stream")
    assert kr_market.get_user_usage("anon_session-command") == kr_market.MAX_FREE_USAGE


def test_chatbot_slash_command_preserves_session_required_guard(monkeypatch, tmp_path: Path):
    """슬래시 명령도 검증된 세션 식별자 없이는 실행하지 않는다."""
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")
    _install_chatbot_module(monkeypatch, _DummyChatbot([{"chunk": "명령 응답"}]))

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": "/status"},
        headers={"Accept": "text/event-stream"},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_REQUIRED"


def test_chatbot_leading_space_slash_request_remains_quota_limited(monkeypatch, tmp_path: Path):
    """앞 공백이 있는 슬래시 문자열은 명령이 아니므로 쿼터 가드를 통과해야 한다."""
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    quota_file = tmp_path / "user_quota.json"
    quota_file.write_text(
        json.dumps({"anon_session-leading-space": kr_market.MAX_FREE_USAGE}, ensure_ascii=False),
        encoding="utf-8",
    )
    bot = _DummyChatbot([{"chunk": "should-not-run"}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        json={"message": " /status"},
        headers={"X-Session-Id": "anon_session-leading-space"},
    )

    assert response.status_code == 402
    assert response.get_json()["code"] == "QUOTA_EXCEEDED"
    assert bot.calls == []


def test_chatbot_file_attached_slash_request_remains_quota_limited(monkeypatch, tmp_path: Path):
    """첨부가 있는 슬래시 문자열은 명령이 아니므로 쿼터 가드를 통과해야 한다."""
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")

    quota_file = tmp_path / "user_quota.json"
    quota_file.write_text(
        json.dumps({"anon_session-file": kr_market.MAX_FREE_USAGE}, ensure_ascii=False),
        encoding="utf-8",
    )
    bot = _DummyChatbot([{"chunk": "should-not-run"}])
    _install_chatbot_module(monkeypatch, bot)

    client = _create_client()
    response = client.post(
        "/api/kr/chatbot",
        data={"message": "/status", "file": (io.BytesIO(b"upload"), "note.txt")},
        headers={"X-Session-Id": "anon_session-file"},
    )

    assert response.status_code == 402
    assert response.get_json()["code"] == "QUOTA_EXCEEDED"
    assert bot.calls == []


def test_routes_do_not_overlap_for_interval_and_chatbot_history():
    client = _create_client()

    assert _count_rules(client, "/api/kr/config/interval", "GET") == 1
    assert _count_rules(client, "/api/kr/config/interval", "POST") == 1
    assert _count_rules(client, "/api/kr/chatbot/history", "DELETE") == 1


def test_increment_user_usage_is_thread_safe(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    usage_key = "session-concurrent"
    increment_count = 50

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: kr_market.increment_user_usage(usage_key), range(increment_count)))

    assert kr_market.get_user_usage(usage_key) == increment_count


def test_config_interval_post_persists_and_applies_update(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client_with_user(user_email="admin@example.com")
    env_path = tmp_path / ".env"
    env_path.write_text(
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES=30\nSMTP_HOST=old\n",
        encoding="utf-8",
    )
    applied: list[int] = []

    monkeypatch.setattr(
        kr_market,
        "_apply_market_gate_interval",
        applied.append,
    )
    monkeypatch.setattr(kr_market, "_project_env_path", lambda: str(env_path))

    response = client.post("/api/kr/config/interval", json={"interval": "15"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["interval"] == 15
    assert applied == [15]
    assert env_path.read_text(encoding="utf-8") == (
        "MARKET_GATE_UPDATE_INTERVAL_MINUTES=15\nSMTP_HOST=old\n"
    )


def test_config_interval_post_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client_with_user(user_email="admin@example.com")
    response = client.post("/api/kr/config/interval", json={"interval": "abc"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid interval"


def test_config_interval_post_refuses_anonymous(monkeypatch):
    """[INFRA-059] 주기는 서버 전역 스케줄러 값이라 관리자만 바꾼다.

    RED 를 도는 동안에는 게이트가 없어 요청이 실제로 뷰를 통과한다. 두 함수를 목하지
    않으면 app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES 가 바뀌고
    services.scheduler.update_market_gate_interval 이 불려, 같은 프로세스의 다른 검사로
    그 값이 새어 들어간다.
    """
    monkeypatch.setattr(kr_market, "_apply_market_gate_interval", lambda _interval: None)
    monkeypatch.setattr(kr_market, "_persist_market_gate_interval_to_env", lambda _interval: None)

    client = _create_client()
    response = client.post("/api/kr/config/interval", json={"interval": 15})
    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}


def test_config_interval_get_stays_open_for_anonymous():
    """조회까지 막으면 화면이 현재 주기를 보여 주지 못한다.

    handle_interval_config_request 가 GET 에서 apply/persist 를 부르지 않으므로
    (services/kr_market_interval_http_service.py:21-22) 목이 필요 없다.
    """
    client = _create_client()
    response = client.get("/api/kr/config/interval")
    assert response.status_code == 200
    assert "interval" in response.get_json()










@pytest.mark.parametrize("error", [
    OSError(28, "QA_SECRET_SENTINEL", "/private/fake-credentials.env"),
    RuntimeError("QA_SECRET_SENTINEL"),
])
def test_config_interval_errors_do_not_expose_details(monkeypatch, caplog, error):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = _create_client_with_user(user_email="admin@example.com")

    def fail_persistence(_interval):
        raise error

    monkeypatch.setattr(kr_market, "_persist_market_gate_interval_to_env", fail_persistence)
    response = client.post("/api/kr/config/interval", json={"interval": 15})
    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to process interval configuration"}
    assert "QA_SECRET_SENTINEL" not in response.get_data(as_text=True) + caplog.text
    assert "/private/fake-credentials.env" not in response.get_data(as_text=True) + caplog.text
    assert type(error).__name__ in caplog.text


@pytest.mark.parametrize("stored", [False, True])
def test_jongga_history_repairs_missing_exit_prices_without_rewriting_file(monkeypatch, tmp_path, stored):
    """과거 날짜 조회도 최신과 같은 가격 보정을 거치며 저장 원문을 바꾸지 않는다."""
    monkeypatch.setattr(kr_market, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(kr_market, "load_json_file", lambda _: {})
    signal = {"stock_code": "005930", "entry_price": 100000, "grade": "B", "score": {"total": 6, "llm_reason": "목표 142000원 원문"}}
    if stored:
        signal.update(target_price=108000, stop_price=96000)
    path = tmp_path / "jongga_v2_results_20260220.json"
    original = json.dumps({"date": "2026-02-20", "signals": [signal]}).encode()
    path.write_bytes(original)
    response = _create_client().get("/api/kr/jongga-v2/history/2026-02-20")
    assert response.status_code == 200
    row = response.get_json()["signals"][0]
    assert (row["target_price"], row["stop_price"]) == ((108000, 96000) if stored else (105000, 97000))
    assert row["score"]["llm_reason"] == "목표 142000원 원문"
    assert path.read_bytes() == original


def test_chatbot_multipart_command_classification_matches_parser_case(monkeypatch, tmp_path: Path):
    _prepare_quota_store(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-server-key")
    bot = _DummyChatbot([{"chunk": "명령 응답"}])
    _install_chatbot_module(monkeypatch, bot)
    body = '--qa\r\nContent-Disposition: form-data; name="message"\r\n\r\n/status\r\n--qa--\r\n'
    response = _create_client().post(
        "/api/kr/chatbot", data=body,
        content_type="Multipart/Form-Data; boundary=qa",
        headers={"X-Session-Id": "anon_session-command"},
    )
    assert response.status_code == 200
    response.get_data()
    assert bot.calls[0]["message"] == "/status"
    assert kr_market.get_user_usage("anon_session-command") == 0


@pytest.mark.parametrize('body', [{}, {'target_dates': ['2026-02-30']}, []])
def test_retired_gemini_returns_410_without_quota(monkeypatch, body):
    import services.usage_tracker as usage_tracker_module
    def forbidden(*args, **kwargs):
        raise AssertionError('retired route must not consume quota')
    monkeypatch.setattr(usage_tracker_module.usage_tracker, 'check_and_increment', forbidden)
    client = _create_client_with_user(user_api_key='unused-test-key', user_email='tester@example.com')
    response = client.post('/api/kr/reanalyze/gemini', json=body)
    assert response.status_code == 410
    assert response.get_json()['code'] == 'LEGACY_ANALYSIS_RETIRED'
