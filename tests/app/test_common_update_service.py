#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common Update Service 단위 테스트
"""

import sys
import types

from services.common_update_service import run_background_update_pipeline


def _noop_logger():
    return types.SimpleNamespace(
        info=lambda *_a, **_k: None,
        warning=lambda *_a, **_k: None,
        error=lambda *_a, **_k: None,
    )


def test_run_background_update_pipeline_daily_prices_and_finish(monkeypatch):
    calls = {"daily_prices": 0, "finish": 0}
    statuses: list[tuple[str, str]] = []

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: calls.__setitem__("daily_prices", calls["daily_prices"] + 1),
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["daily_prices"] == 1
    assert calls["finish"] == 1
    assert statuses == [("Daily Prices", "running"), ("Daily Prices", "done")]


def test_run_background_update_pipeline_honors_stop_request(monkeypatch):
    calls = {"finish": 0}
    statuses: list[tuple[str, str]] = []

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=True)

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["finish"] == 1
    assert statuses == []
    # [INFRA-096] 중단된 작업이 끝나면 중단 요청도 끝난다
    assert shared_state.STOP_REQUESTED is False


def test_run_background_update_pipeline_ai_jongga_does_not_touch_ai_analysis_status(monkeypatch):
    statuses: list[tuple[str, str]] = []
    calls = {"finish": 0, "screener": 0}

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    async def _run_screener(*_a, **_k):
        calls["screener"] += 1

    fake_generator = types.ModuleType("engine.generator")
    fake_generator.run_screener = _run_screener
    monkeypatch.setitem(sys.modules, "engine.generator", fake_generator)

    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)

    run_background_update_pipeline(
        target_date=None,
        selected_items=["AI Jongga V2"],
        force=False,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert calls["screener"] == 1
    assert calls["finish"] == 1
    assert ("AI Jongga V2", "running") in statuses
    assert ("AI Jongga V2", "done") in statuses
    assert ("AI Analysis", "done") not in statuses


def test_run_background_update_pipeline_skips_vcp_when_institutional_trend_failed(monkeypatch):
    statuses: list[tuple[str, str]] = []
    calls = {"vcp": 0, "ai": 0, "finish": 0}

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    from services import common_update_service as update_service

    monkeypatch.setattr(
        update_service,
        "run_institutional_trend_step",
        lambda **_kwargs: False,
    )
    monkeypatch.setattr(
        update_service,
        "run_vcp_signals_step",
        lambda **_kwargs: calls.__setitem__("vcp", calls["vcp"] + 1),
    )
    monkeypatch.setattr(
        update_service,
        "run_ai_analysis_step",
        lambda **_kwargs: calls.__setitem__("ai", calls["ai"] + 1),
    )

    run_background_update_pipeline(
        target_date="2026-03-04",
        selected_items=["Institutional Trend", "VCP Signals", "AI Analysis"],
        force=True,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_noop_logger(),
    )

    assert calls["vcp"] == 0
    assert calls["ai"] == 0
    assert calls["finish"] == 1
    assert ("VCP Signals", "error") in statuses
    assert ("AI Analysis", "error") in statuses


def test_run_background_update_pipeline_preserves_ai_analysis_error_when_ai_jongga_runs(
    monkeypatch,
):
    statuses: list[tuple[str, str]] = []
    calls = {"finish": 0, "screener": 0}

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_daily_prices=lambda *_a, **_k: None,
        create_institutional_trend=lambda *_a, **_k: None,
        create_signals_log=lambda *_a, **_k: None,
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    from services import common_update_service as update_service

    monkeypatch.setattr(
        update_service,
        "run_institutional_trend_step",
        lambda **_kwargs: False,
    )

    async def _run_screener(*_a, **_k):
        calls["screener"] += 1

    fake_generator = types.ModuleType("engine.generator")
    fake_generator.run_screener = _run_screener
    monkeypatch.setitem(sys.modules, "engine.generator", fake_generator)

    run_background_update_pipeline(
        target_date="2026-03-06",
        selected_items=["Institutional Trend", "VCP Signals", "AI Analysis", "AI Jongga V2"],
        force=True,
        update_item_status=lambda name, status: statuses.append((name, status)),
        finish_update=lambda: calls.__setitem__("finish", calls["finish"] + 1),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_noop_logger(),
    )

    assert calls["screener"] == 1
    assert calls["finish"] == 1
    assert ("AI Analysis", "error") in statuses
    assert ("AI Analysis", "done") not in statuses


def test_stop_update_records_request_in_shared_status_not_local_flag(tmp_path):
    # [INFRA-097] 중단 요청은 모든 워커가 읽는 상태 파일에 남고, 요청을 받은 워커의 플래그는 켜지 않는다
    import threading

    from services.common_update_status_service import load_update_status, start_update, stop_update

    status_file = str(tmp_path / "update_status.json")
    lock = threading.Lock()
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)
    kwargs = dict(update_lock=lock, update_status_file=status_file, logger=_noop_logger())

    start_update(items_list=["Daily Prices"], shared_state=shared_state, **kwargs)
    stop_update(**kwargs)

    assert load_update_status(update_status_file=status_file, logger=_noop_logger())["stopRequested"] is True
    assert shared_state.STOP_REQUESTED is False

    start_update(items_list=["Daily Prices"], shared_state=shared_state, **kwargs)
    restarted = load_update_status(update_status_file=status_file, logger=_noop_logger())
    assert restarted["stopRequested"] is False
    # 이 워커가 시작한 실행을 기록해 감시가 같은 워커의 새 실행을 구분한다
    assert shared_state.LOCAL_RUN_START_TIME == restarted["startTime"]


def test_start_update_refuses_while_local_pipeline_active(tmp_path):
    # [INFRA-099] 이 워커에서 중단된 실행이 아직 돌면 새 시작을 받지 않는다. 상태를 그대로 둬야 옛 실행의 감시가 멈춘다
    import threading

    from services.common_update_status_service import load_update_status, start_update, stop_update

    status_file = str(tmp_path / "update_status.json")
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)
    kwargs = dict(update_lock=threading.Lock(), update_status_file=status_file, logger=_noop_logger())

    assert start_update(items_list=["Daily Prices"], shared_state=shared_state, **kwargs) is True
    stop_update(**kwargs)
    stopped = load_update_status(update_status_file=status_file, logger=_noop_logger())
    shared_state.LOCAL_PIPELINE_ACTIVE = True
    shared_state.STOP_REQUESTED = True  # 옛 실행의 감시가 이미 켠 값

    assert start_update(items_list=["VCP Signals"], shared_state=shared_state, **kwargs) is False
    assert load_update_status(update_status_file=status_file, logger=_noop_logger()) == stopped
    assert shared_state.LOCAL_RUN_START_TIME == stopped["startTime"]
    assert shared_state.STOP_REQUESTED is True


def test_run_background_update_pipeline_marks_local_pipeline_active(monkeypatch):
    # [INFRA-099] 도는 동안 켜고, 수집기가 예외로 끝나도 끈다. 켜진 채 남으면 이 워커는 재기동 전까지 시작을 거부한다
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)
    seen: list[bool] = []

    def _collect(*_a, **_k):
        seen.append(shared_state.LOCAL_PIPELINE_ACTIVE)
        raise RuntimeError("boom")

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=_collect)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: None,
        shared_state=shared_state,
        logger=_noop_logger(),
    )

    assert seen == [True]
    assert shared_state.LOCAL_PIPELINE_ACTIVE is False


def test_run_background_update_pipeline_clears_local_pipeline_after_finish_even_if_it_fails(monkeypatch):
    # [INFRA-099] 표시는 finish_update 뒤에 끈다. 먼저 끄면 같은 워커의 새 시작이 끼어들어 그 상태를 끝낼 수 있다.
    # finish_update 가 예외를 내도 끄지 않으면 이 워커는 재기동 전까지 시작을 거부한다(critic 지적 a)
    import pytest

    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)
    seen_at_finish: list[bool] = []

    def _finish():
        seen_at_finish.append(shared_state.LOCAL_PIPELINE_ACTIVE)
        raise OSError("status write failed")

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=lambda *_a, **_k: True)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    with pytest.raises(OSError):
        run_background_update_pipeline(
            target_date="2026-02-21",
            selected_items=["Daily Prices"],
            force=False,
            update_item_status=lambda *_a: None,
            finish_update=_finish,
            shared_state=shared_state,
            logger=_noop_logger(),
        )

    assert seen_at_finish == [True]
    assert shared_state.LOCAL_PIPELINE_ACTIVE is False


def test_run_background_update_pipeline_sees_stop_request_from_other_worker(monkeypatch):
    # [INFRA-097] 다른 워커가 상태에 남긴 중단 요청을 감시 스레드가 이 워커의 플래그로 옮긴다
    import time

    import services.common_update_service as service

    monkeypatch.setattr(service, "STOP_WATCH_INTERVAL_SECONDS", 0.01)
    status = {"isRunning": True, "startTime": "run-1", "stopRequested": False}
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)
    seen: list[bool] = []

    def _collect(*_a, **_k):
        status.update(isRunning=False, stopRequested=True)  # 다른 워커의 stop_update
        deadline = time.monotonic() + 2
        while not shared_state.STOP_REQUESTED and time.monotonic() < deadline:
            time.sleep(0.01)
        seen.append(shared_state.STOP_REQUESTED)

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=_collect)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    finished: list[bool] = []

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: finished.append(True),
        shared_state=shared_state,
        logger=_noop_logger(),
        load_update_status=lambda: dict(status),
    )

    assert seen == [True]
    assert finished == [True]
    assert shared_state.STOP_REQUESTED is False


def test_run_background_update_pipeline_superseded_run_leaves_new_run_alone(monkeypatch):
    # [INFRA-097] 중단된 옛 실행이 늦게 끝나도 그 사이 시작한 새 실행의 중단 요청과 상태를 건드리지 않는다
    status = {"isRunning": True, "startTime": "run-1", "stopRequested": False}
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False)

    def _collect(*_a, **_k):
        status.update(startTime="run-2", stopRequested=True)  # 새 실행이 시작돼 다시 중단됨
        shared_state.STOP_REQUESTED = True

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=_collect)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    finished: list[bool] = []

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: finished.append(True),
        shared_state=shared_state,
        logger=_noop_logger(),
        load_update_status=lambda: dict(status),
    )

    assert finished == []
    # 옛 실행의 워커에 값을 남기지 않는다. 같은 워커의 새 실행이면 그 실행의 감시가 다시 켠다(리뷰 지적 1)
    assert shared_state.STOP_REQUESTED is False


def test_run_background_update_pipeline_without_start_time_still_finishes(monkeypatch):
    # [INFRA-097] 상태에서 startTime 을 읽지 못하면 종전처럼 항상 끝내 isRunning 이 고착되지 않는다(리뷰 지적 3·4)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=lambda *_a, **_k: None)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    finished: list[bool] = []
    reads = iter([{}, {"startTime": "run-2"}])

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: finished.append(True),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False),
        logger=_noop_logger(),
        load_update_status=lambda: next(reads),
    )

    assert finished == [True]


def _run_superseded_before_first_poll(monkeypatch, superseded_by_local_run):
    import time

    import services.common_update_service as service

    monkeypatch.setattr(service, "STOP_WATCH_INTERVAL_SECONDS", 0.01)
    status = {"isRunning": True, "startTime": "run-1", "stopRequested": False}
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False, LOCAL_RUN_START_TIME="run-1")
    seen: list[bool] = []

    def _collect(*_a, **_k):
        # 감시가 처음 읽기 전에 중단과 새 실행 시작이 모두 끝났다
        status.update(isRunning=True, startTime="run-2", stopRequested=False)
        if superseded_by_local_run:
            shared_state.LOCAL_RUN_START_TIME = "run-2"
        deadline = time.monotonic() + 0.3
        while not shared_state.STOP_REQUESTED and time.monotonic() < deadline:
            time.sleep(0.01)
        seen.append(shared_state.STOP_REQUESTED)

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=_collect)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: None,
        shared_state=shared_state,
        logger=_noop_logger(),
        load_update_status=lambda: dict(status),
    )
    return seen


def test_run_background_update_pipeline_stops_when_superseded_by_other_worker(monkeypatch):
    # [INFRA-097] 중단 뒤 1초 안에 다른 워커가 새 실행을 시작해도 옛 실행은 멈춘다(QA S-3)
    assert _run_superseded_before_first_poll(monkeypatch, superseded_by_local_run=False) == [True]


def test_run_background_update_pipeline_superseded_by_local_run_keeps_shared_flag(monkeypatch):
    # [INFRA-097] 새 실행이 같은 워커면 플래그를 함께 쓰므로 옛 실행을 멈추려고 새 실행까지 멈추지 않는다
    assert _run_superseded_before_first_poll(monkeypatch, superseded_by_local_run=True) == [False]


def test_run_background_update_pipeline_ignores_status_without_start_time(monkeypatch):
    # [INFRA-097] 상태 파일이 사라져 기본값(startTime 없음)을 읽어도 정상 실행을 대체된 것으로 보지 않는다(critic 지적 4)
    import time

    import services.common_update_service as service

    monkeypatch.setattr(service, "STOP_WATCH_INTERVAL_SECONDS", 0.01)
    status = {"isRunning": True, "startTime": "run-1", "stopRequested": False}
    shared_state = types.SimpleNamespace(STOP_REQUESTED=False, LOCAL_RUN_START_TIME="run-1")
    seen: list[bool] = []

    def _collect(*_a, **_k):
        status.clear()
        status.update(isRunning=False, currentItem=None, items=[])  # default_update_status 에 startTime 이 없는 경우
        time.sleep(0.1)
        seen.append(shared_state.STOP_REQUESTED)

    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=_collect)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: None,
        shared_state=shared_state,
        logger=_noop_logger(),
        load_update_status=lambda: dict(status),
    )

    assert seen == [False]


def test_run_background_update_pipeline_uses_local_start_time_over_shared_file(monkeypatch):
    # [INFRA-097] 두 워커가 함께 시작해 파일에 다른 워커의 startTime 만 남아도 이 실행의 신원은 이 워커가 정한 값이다(심층 리뷰 2)
    import services.common_update_service as service

    captured: dict = {}
    monkeypatch.setattr(
        service, "_watch_stop_request", lambda _load, start_time, *_a: captured.setdefault("start_time", start_time)
    )
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(create_daily_prices=lambda *_a, **_k: None)
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    finished: list[bool] = []

    run_background_update_pipeline(
        target_date="2026-02-21",
        selected_items=["Daily Prices"],
        force=False,
        update_item_status=lambda *_a: None,
        finish_update=lambda: finished.append(True),
        shared_state=types.SimpleNamespace(STOP_REQUESTED=False, LOCAL_RUN_START_TIME="run-A"),
        logger=_noop_logger(),
        load_update_status=lambda: {"startTime": "run-B"},
    )

    assert captured == {"start_time": "run-A"}
    assert finished == []  # 늦게 쓴 다른 워커의 실행 상태를 끝내지 않는다


def test_route_background_update_wires_status_reader(monkeypatch):
    # [INFRA-097] 라우트 배선이 상태 읽기를 넘기지 않으면 감시가 조용히 꺼진다(심층 리뷰 1)
    import app.routes.common as common

    captured: dict = {}
    monkeypatch.setattr(common, "run_background_update_pipeline", lambda **kwargs: captured.update(kwargs))

    common.run_background_update("2026-02-21", ["Daily Prices"], False)

    assert captured["load_update_status"] is common.load_update_status


def test_route_start_update_returns_refusal(monkeypatch):
    # [INFRA-099] 래퍼가 거부를 돌려주지 않으면 호출자는 None 을 받아 정상 시작으로 본다(심층 리뷰 1)
    import app.routes.common as common

    monkeypatch.setattr(common, "start_update_impl", lambda **_k: False)

    assert common.start_update(["Daily Prices"]) is False


def test_update_item_status_skips_write_for_replaced_run(tmp_path):
    # [INFRA-101] 다른 워커의 새 실행에 대체된 옛 실행은 새 실행의 같은 이름 항목에 쓰지 않는다
    import threading

    from services.common_update_status_service import load_update_status, save_update_status, update_item_status

    status_file = str(tmp_path / "update_status.json")
    kwargs = dict(update_lock=threading.Lock(), update_status_file=status_file, logger=_noop_logger())
    new_run = {
        "isRunning": True,
        "startTime": "run-B",
        "currentItem": None,
        "items": [{"name": "Daily Prices", "status": "pending"}],
    }
    save_update_status(status=new_run, update_status_file=status_file, logger=_noop_logger())

    def _load():
        return load_update_status(update_status_file=status_file, logger=_noop_logger())

    update_item_status(name="Daily Prices", status_code="done", start_time="run-A", **kwargs)
    assert _load() == new_run
    update_item_status(name="Daily Prices", status_code="running", start_time="run-A", **kwargs)
    assert _load() == new_run  # currentItem 도 그대로

    update_item_status(name="Daily Prices", status_code="running", start_time="run-B", **kwargs)
    assert _load()["items"] == [{"name": "Daily Prices", "status": "running"}]
    assert _load()["currentItem"] == "Daily Prices"

    update_item_status(name="Daily Prices", status_code="done", **kwargs)  # 수동 API 는 종전 동작
    assert _load()["items"] == [{"name": "Daily Prices", "status": "done"}]


def test_route_run_background_update_binds_local_start_time(monkeypatch):
    # [INFRA-101] 래퍼는 진입 때의 이 워커 실행 시각을 항목 상태 콜백에 묶어 넘긴다
    import app.routes.common as common

    item_calls: list[dict] = []
    monkeypatch.setattr(common, "update_item_status_impl", lambda **kwargs: item_calls.append(kwargs))
    monkeypatch.setattr(common.shared_state, "LOCAL_RUN_START_TIME", "run-A", raising=False)

    def _pipeline(**kwargs):
        common.shared_state.LOCAL_RUN_START_TIME = "run-later"
        kwargs["update_item_status"]("Daily Prices", "done")

    monkeypatch.setattr(common, "run_background_update_pipeline", _pipeline)

    common.run_background_update("2026-02-21", ["Daily Prices"], False)

    assert [(c["name"], c["status_code"], c["start_time"]) for c in item_calls] == [("Daily Prices", "done", "run-A")]

    common.shared_state.LOCAL_RUN_START_TIME = None  # start_update 를 거치지 않은 실행은 종전처럼 확인하지 않는다
    common.run_background_update("2026-02-21", ["Daily Prices"], False)
    assert item_calls[-1]["start_time"] is None
