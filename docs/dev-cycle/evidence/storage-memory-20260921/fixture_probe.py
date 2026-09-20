#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""storage-memory fixture의 제품 route·SQLite 경로 계약을 확인한다."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_fixture(repo: Path) -> ModuleType:
    fixture_path = repo / "docs/dev-cycle/evidence/storage-memory-20260921/fixture.py"
    spec = importlib.util.spec_from_file_location("storage_memory_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sse_payload(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.status_code
    assert response.mimetype == "text/event-stream", response.mimetype
    rows = [row for row in response.get_data(as_text=True).split("\n\n") if row.startswith("data: ")]
    assert len(rows) == 1, rows
    return json.loads(rows[0][len("data: "):])


def main() -> None:
    repo = Path.cwd().resolve()
    fixture = _load_fixture(repo)
    fixture.validate_scratch_repo(str(repo))
    app = fixture.build_app(repo, reset_log=True)
    client = app.test_client()

    # 실제 등록 라우트가 실제 HistoryManager를 통해 만든 대화 목록을 반환한다.
    sessions = client.get("/api/kr/chatbot/sessions")
    assert sessions.status_code == 200 and sessions.is_json
    listed = sessions.json["sessions"]
    assert [session["id"] for session in listed] == ["storage-fixture-history"]
    history = client.get("/api/kr/chatbot/history?session_id=storage-fixture-history")
    assert history.status_code == 200 and len(history.json["history"]) == 2

    profile = client.post(
        "/api/kr/chatbot/profile",
        json={"name": "QA 프로필", "persona": "fixture persona"},
    )
    assert profile.status_code == 200 and profile.json["profile"]["name"] == "QA 프로필"

    for command, expected in [
        ("/memory add 일반메모리 보존값", "메모리 저장"),
        ("/memory view", "일반메모리"),
        ("/memory add user_profile 변경금지", "설정 화면"),
        ("/memory clear", "초기화"),
        ("/memory view", "저장된 메모리가 없습니다"),
    ]:
        payload = _sse_payload(client.post(
            "/api/kr/chatbot",
            headers={"Accept": "text/event-stream"},
            json={"message": command, "session_id": "storage-fixture-history"},
        ))
        assert expected in payload["chunk"], (command, payload)

    # /memory clear는 실제 제품 메모리의 일반 항목만 정리하고 예약 profile을 보존한다.
    profile_after = client.get("/api/kr/chatbot/profile")
    assert profile_after.status_code == 200
    assert profile_after.json["profile"] == {"name": "QA 프로필", "persona": "fixture persona"}

    other = client.post("/__qa/control", json={"owner": "other"})
    assert other.status_code == 200
    other_memory = _sse_payload(client.post(
        "/api/kr/chatbot",
        headers={"Accept": "text/event-stream"},
        json={"message": "/memory add 다른사용자 격리값", "session_id": "other-history"},
    ))
    assert "메모리 저장" in other_memory["chunk"]
    assert client.post("/__qa/control", json={"owner": "fixture"}).status_code == 200

    suggestions = client.get("/api/kr/chatbot/suggestions")
    assert suggestions.status_code == 200
    assert suggestions.json["suggestions"] == [
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

    # B2: 실제 cache save/get SQLite 왕복을 마친 대표 대시보드 읽기 응답이다.
    vcp = client.get("/api/kr/signals")
    jongga = client.get("/api/kr/jongga-v2/latest")
    cumulative = client.get("/api/kr/closing-bet/cumulative")
    backtest = client.get("/api/kr/backtest-summary")
    assert vcp.json["signals"][0]["ticker"] == "005930"
    assert vcp.json["signals"][0]["gemini_recommendation"]["action"] == "BUY"
    assert jongga.json["signals"][0]["stock_code"] == "005930"
    assert jongga.json["signals"][0]["score"]["llm_reason"] == "fixture 종가 분석입니다."
    cumulative_trade = cumulative.json["trades"][0]
    assert cumulative_trade["entry"] == 75_000 and cumulative_trade["themes"] == ["반도체", "AI"]
    assert cumulative_trade["priceTrail"] == [75_000, 75_800, 76_200]
    assert cumulative.json["kpi"]["recentClosedCount"] == 1
    assert backtest.json["closing_bet"]["count"] == 1

    state_dir = repo / ".qa-storage-memory"
    db_path = state_dir / "synthetic-data" / "chatbot_storage.db"
    assert db_path.exists(), db_path
    from chatbot.storage_memory_manager import MemoryManager

    reloaded = MemoryManager("probe", data_dir=state_dir / "synthetic-data")
    assert reloaded.get("user_profile", fixture.FIXTURE_OWNER)["value"] == {
        "name": "QA 프로필", "persona": "fixture persona",
    }
    assert reloaded.get("다른사용자", fixture.OTHER_OWNER)["value"] == "격리값"
    assert reloaded.get("daily_suggestions_storage_fixture", "")["value"] == suggestions.json["suggestions"]

    # 허용하지 않은 HTTP mutation은 fixture 경계에서 차단된다.
    assert client.delete("/api/kr/chatbot/history?session_id=storage-fixture-history").status_code == 405
    assert client.post("/api/system/env", json={}).status_code == 405
    print(json.dumps({
        "route_sse_memory_profile_history": "PASS",
        "daily_suggestion_cache_roundtrip": "PASS",
        "dashboard_cache_roundtrip": "PASS",
        "blocked_product_mutations": "PASS",
        "state_dir": str(state_dir),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
