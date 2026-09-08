#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부류 A 여섯 라우트에 인가 게이트가 붙어 있는지 잰다([INFRA-042]).

데코레이터 자체는 tests/app/test_route_guards.py 가 잰다. 여기서 재는 것은 「그것이
이 여섯 자리에 실제로 붙어 있는가」다. 둘을 한 파일에 두면 데코레이터를 지웠을 때
어느 쪽이 깨진 것인지 구분이 안 된다.

의존성을 「불리면 AssertionError 를 내는 가짜」로 넣는다. 그래야 게이트가 없을 때
호출이 실제로 일어났다는 것을 검사가 직접 증명한다. app.view_functions 에서 뷰를 꺼내
__wrapped__ 속성이 있는지 보는 방식은 쓰지 않는다. 데코레이터가 붙었다는 사실만 재고
거부가 실제로 일어나는지는 재지 못하며, functools.wraps 를 쓰는 다른 데코레이터에도
똑같이 반응한다.

블루프린트를 url_prefix 없이 등록하므로 경로가 실제 앱(/api/kr/...)과 다르다. 의도한
것이다. 이 파일은 게이트만 재고 경로 배선은 재지 않는다. 그쪽은 각 라우트의 기존
refactor 검사가 맡는다.
"""

import logging
import os
import sys
import threading

import pytest

from flask import Blueprint, Flask, g, request

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


# 라우트가 부르는 것은 error/info 둘뿐이고 그마저 게이트에 막혀 도달하지 않는다.
_LOGGER = logging.getLogger("test_admin_gated_routes")


def _must_not_run(*_args, **_kwargs):
    raise AssertionError("게이트를 지나 실행 경로에 도달했다")


def _build_app(register, monkeypatch, *, identity_email=None):
    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("probe_bp", __name__)
    register(bp)

    @app.before_request
    def _seed_identity():
        if request.method == "OPTIONS":
            return
        g.user_email = identity_email

    app.register_blueprint(bp)
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    return app.test_client()


def test_signals_run_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_data_signals_routes import _register_vcp_run_route

    def register(bp):
        _register_vcp_run_route(
            bp,
            logger=_LOGGER,
            vcp_status={},
            start_vcp_screener_run=_must_not_run,
            run_vcp_background=_must_not_run,
        )

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/signals/run", json={})
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_signals_run_passes_for_admin(monkeypatch):
    """막는 것만 재면 게이트가 전부를 막아도 통과한다."""
    from app.routes.kr_market_data_signals_routes import _register_vcp_run_route

    def register(bp):
        _register_vcp_run_route(
            bp,
            logger=_LOGGER,
            vcp_status={},
            start_vcp_screener_run=lambda **_k: (200, {"status": "started"}),
            run_vcp_background=lambda *_a: None,
        )

    client = _build_app(register, monkeypatch, identity_email="admin@example.com")
    res = client.post("/signals/run", json={})
    assert res.status_code == 200


def test_init_data_refuses_anonymous(monkeypatch):
    from app.routes.kr_market_system_http_routes import _register_init_data_route

    def register(bp):
        _register_init_data_route(
            bp,
            logger=_LOGGER,
            deps={"launch_init_data_update": _must_not_run},
        )

    client = _build_app(register, monkeypatch, identity_email=None)
    res = client.post("/init-data", json={"type": "all"})
    assert res.status_code == 403


def _register_jongga(bp, tmp_path):
    from app.routes.kr_market_jongga_execution_routes import (
        register_jongga_execution_routes,
    )

    register_jongga_execution_routes(
        bp,
        # tmp_path 를 쓴다. 403 경로는 파일에 닿지 않지만, 나중에 「관리자는 통과한다」
        # 갈래를 보태면 그 경로가 v2_screener_status.json 을 실제로 쓴다. 고정 경로를
        # 두면 그때 /tmp 에 파일이 남는다. 이웃 검사도 전부 tmp_path 를 쓴다.
        data_dir=str(tmp_path),
        logger=_LOGGER,
        load_json_file=_must_not_run,
        launch_jongga_v2_screener=_must_not_run,
        run_jongga_v2_background_pipeline=_must_not_run,
        execute_single_stock_analysis=_must_not_run,
        execute_jongga_gemini_reanalysis=_must_not_run,
        resolve_jongga_message_filename=_must_not_run,
        build_screener_result_for_message=_must_not_run,
        select_signals_for_reanalysis=_must_not_run,
        build_jongga_news_analysis_items=_must_not_run,
        apply_gemini_reanalysis_results=_must_not_run,
    )


def test_jongga_message_refuses_anonymous_even_with_force(monkeypatch, tmp_path):
    """{"force": true} 로도 우회되지 않는다.

    force 는 claim_jongga_notification_send 중복 가드를 건너뛰는 값이라
    (kr_market_jongga_execution_routes.py:216) 게이트가 없으면 횟수 제한 없이 실제
    종가베팅 시그널 메시지가 나간다. 게이트는 그보다 앞에 있어야 한다.

    의존성을 전부 실패하는 가짜로 두었다. 게이트가 없으면 resolve_jongga_message_filename
    이 불려 AssertionError 가 나므로, 이 검사는 「403 이 나왔다」와 「발송 준비에 닿지
    않았다」를 함께 잰다.
    """
    client = _build_app(
        lambda bp: _register_jongga(bp, tmp_path), monkeypatch, identity_email=None
    )
    res = client.post(
        "/jongga-v2/message", json={"target_date": "2026-02-22", "force": True}
    )
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_jongga_run_refuses_anonymous(monkeypatch, tmp_path):
    client = _build_app(
        lambda bp: _register_jongga(bp, tmp_path), monkeypatch, identity_email=None
    )
    res = client.post("/jongga-v2/run", json={"target_date": "2026-02-22"})
    assert res.status_code == 403


def test_jongga_reanalyze_refuses_anonymous(monkeypatch, tmp_path):
    client = _build_app(
        lambda bp: _register_jongga(bp, tmp_path), monkeypatch, identity_email=None
    )
    res = client.post("/jongga-v2/reanalyze-gemini", json={})
    assert res.status_code == 403


def test_jongga_reanalyze_preflight_passes_without_identity(monkeypatch, tmp_path):
    """이 라우트만 methods 에 OPTIONS 를 둔다. 게이트가 preflight 를 막으면 안 된다."""
    client = _build_app(
        lambda bp: _register_jongga(bp, tmp_path), monkeypatch, identity_email=None
    )
    res = client.open("/jongga-v2/reanalyze-gemini", method="OPTIONS")
    assert res.status_code == 200


def test_start_update_refuses_anonymous(monkeypatch):
    """스레드 기동에 닿기 전에 막는다.

    load_update_status 는 통과시킨다. api_start_update 가 그것을 먼저 부르고
    (common_update_routes.py:130-136) isRunning 을 본 뒤에야 스레드 기동에 닿으므로,
    그것까지 실패 가짜로 두면 게이트가 없을 때 첫 호출에서 터져 「403 이 났다」는 재지만
    「스레드가 뜨지 않았다」는 증명하지 못한다.

    **_k 를 받는 이유는 라우트가 deep_copy=False 로 부르고 TypeError 를 잡아 인자 없이
    다시 부르기 때문이다(같은 파일 :130-133).
    """
    from app.routes.common_route_context import CommonRouteContext
    from app.routes.common_update_routes import register_common_update_routes

    ctx = CommonRouteContext(
        logger=_LOGGER,
        update_lock=threading.Lock(),
        update_status_file="/dev/null",
        load_update_status=lambda **_k: {"isRunning": False},
        start_update=_must_not_run,
        update_item_status=_must_not_run,
        stop_update=_must_not_run,
        finish_update=_must_not_run,
        run_background_update=_must_not_run,
        paper_trading=None,
    )

    client = _build_app(
        lambda bp: register_common_update_routes(bp, ctx),
        monkeypatch,
        identity_email=None,
    )
    res = client.post("/system/start-update", json={"items": ["AI Jongga V2"]})
    assert res.status_code == 403


def _update_ctx():
    from app.routes.common_route_context import CommonRouteContext

    return CommonRouteContext(
        logger=_LOGGER,
        update_lock=threading.Lock(),
        update_status_file="/dev/null",
        load_update_status=lambda **_k: {"isRunning": False},
        start_update=_must_not_run,
        update_item_status=_must_not_run,
        stop_update=_must_not_run,
        finish_update=_must_not_run,
        run_background_update=_must_not_run,
        paper_trading=None,
    )


@pytest.mark.parametrize(
    "path, payload",
    [
        ("/system/stop-update", {}),
        ("/system/finish-update", {}),
        ("/system/update-item-status", {"name": "AI Jongga V2", "status": "error"}),
    ],
)
def test_update_control_routes_refuse_anonymous(monkeypatch, path, payload):
    """시작만 잠그고 중단을 열어 두면 비대칭이 남는다([INFRA-042] 적대적 리뷰 F2).

    stop-update 는 STOP_REQUESTED 를 세우고 isRunning 을 내리며 running 항목을 error 로,
    pending 항목을 cancelled 로 바꾼다. 게이트가 없으면 익명 요청 한 번이 관리자가 시작한
    갱신을 죽인다. update-item-status 는 임의의 name 과 status 를 공유 상태 파일에 쓴다.

    화면 쪽은 stop-update 만 부르고(data-status/page.tsx:391) 그 페이지는 isAdmin 으로
    막혀 있다. 나머지 둘은 화면 호출자가 없다. 그래서 게이트를 세워도 화면이 바뀌지 않는다.
    """
    from app.routes.common_update_routes import register_common_update_routes

    client = _build_app(
        lambda bp: register_common_update_routes(bp, _update_ctx()),
        monkeypatch,
        identity_email=None,
    )
    res = client.post(path, json=payload)
    assert res.status_code == 403
    assert res.get_json() == {"error": "Forbidden"}


def test_options_does_not_reach_the_view_even_with_a_body(monkeypatch):
    """게이트의 OPTIONS 갈래가 뷰를 부르지 않는다([INFRA-042] 리뷰 셋의 공통 지적).

    Flask 는 methods 에 OPTIONS 를 적은 라우트에 한해 자동 응답을 끄고 뷰를 부른다. 그
    요청에는 본문을 실을 수 있으므로, 게이트가 OPTIONS 를 뷰로 넘기면
    `curl -X OPTIONS -d '{...}'` 한 줄이 무인증으로 뷰에 닿는다. 지금은 그런 라우트가
    jongga-v2/reanalyze-gemini 하나뿐이고 그 뷰가 첫 줄에서 빠지지만, 그 불변식을 지키는
    것이 주석뿐이면 다음에 조기 반환을 빠뜨린 라우트가 생기는 순간 그 자리가 열린다.

    여기서는 조기 반환이 **없는** 뷰를 일부러 세워 그 상황을 재현한다. 게이트가 기본
    OPTIONS 응답으로 끝내므로 뷰는 불리지 않아야 한다.
    """
    from app.routes.route_guards import require_admin

    app = Flask(__name__)
    app.testing = True
    reached = []

    @app.before_request
    def _seed():
        if request.method == "OPTIONS":
            return
        g.user_email = None

    # 조기 반환이 없다. 게이트가 넘기면 본문이 그대로 실행된다.
    @app.route("/probe", methods=["POST", "OPTIONS"])
    @require_admin
    def probe():
        reached.append(request.method)
        return {"ran": True}

    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    client = app.test_client()

    res = client.open("/probe", method="OPTIONS", data=b'{"force": true}')
    assert res.status_code == 200
    assert "POST" in (res.headers.get("Allow") or "")
    assert reached == [], f"OPTIONS 가 뷰에 닿았다: {reached}"

    # preflight 를 막지도 않는다. 막으면 브라우저가 본 요청을 보내지 않는다.
    res = client.open(
        "/probe",
        method="OPTIONS",
        headers={"Origin": "http://ui.test", "Access-Control-Request-Method": "POST"},
    )
    assert res.status_code == 200


# 아래 목록이 이 저장소의 인가 경계다. 라우트를 더하거나 빼면 여기도 함께 고친다.
# 이름으로 하나씩 여는 위 검사들만 두면 일곱 번째 관리자 전용 라우트가 조용히 무검사로
# 들어온다([INFRA-042] 적대적 리뷰 F7).
GATED_ROUTES = frozenset(
    {
        "/api/kr/jongga-v2/run",
        "/api/kr/jongga-v2/reanalyze-gemini",
        "/api/kr/jongga-v2/message",
        "/api/kr/jongga-v2/analyze",
        "/api/kr/signals/run",
        "/api/kr/signals/reanalyze-failed-ai",
        "/api/kr/signals/reanalyze-failed-ai/stop",
        "/api/kr/init-data",
        "/api/system/start-update",
        "/api/system/stop-update",
        "/api/system/finish-update",
        "/api/system/update-item-status",
        # 아래는 이번 라운드가 만든 것이 아니라 종전부터 닫혀 있던 자리다. 데코레이터가
        # 아니라 뷰 몸통의 if 문으로 같은 판정을 한다. 방식이 달라도 인가 경계이므로 이
        # 목록에 함께 둔다. 게이트를 지우면 아래 검사가 잡는다.
        "/api/notification/send",
    }
)


def _decorated_paths(app) -> set[str]:
    """is_admin_email 로 인가를 판정하는 POST 라우트의 경로를 모은다.

    등록된 뷰가 참조하는 전역 이름에 is_admin_email 이 있는지로 가린다. require_admin 이
    감싼 자리와 뷰 몸통에서 직접 부르는 자리가 함께 걸리며, 그것이 의도다. 목록이 뜻하는
    것은 「데코레이터가 붙은 자리」가 아니라 「관리자 전용 라우트」이기 때문이다.

    functools.wraps 가 남기는 __wrapped__ 로는 가릴 수 없다. 다른 데코레이터도 그것을
    남기고, 인라인 게이트는 아예 감싸이지 않아 걸리지 않는다.

    소지 비밀로 닫은 자리는 여기 걸리지 않는다. common_update_routes.py 의
    verify_admin_api_token 은 「이 사람이 누구인가」가 아니라 「이 값을 아는가」를 보므로
    is_admin_email 을 부르지 않는다. 그 게이트는 종류가 달라 이 목록의 대상이 아니다.

    뷰를 실제로 호출해 403 이 나는지 보는 방법도 있지만 쓰지 않는다. 그러려면 열두 라우트의
    의존성을 전부 세워야 하고, 게이트를 지나간 뒤 의존성이 없어 터지는 것과 게이트가 막은
    것을 구분하기 어렵다. 그 확인은 아래 개별 시나리오가 각 라우트마다 따로 한다.
    """
    found = set()
    for rule in app.url_map.iter_rules():
        if "POST" not in (rule.methods or set()):
            continue
        view = app.view_functions.get(rule.endpoint)
        names = getattr(getattr(view, "__code__", None), "co_names", ())
        if "is_admin_email" in names:
            found.add(str(rule.rule))
    return found


def test_gated_route_list_matches_reality():
    """게이트가 붙은 자리와 위 목록이 일치한다.

    실제 앱을 세워 url_map 을 훑는다. 라우트를 새로 만들면서 게이트를 빠뜨리면 이 검사가
    아니라 목록이 먼저 어긋나므로, 이 검사는 「빠뜨렸다」가 아니라 「목록을 갱신하지
    않았다」를 잡는다. 인가 경계를 한 자리에 모아 두는 것이 목적이다.
    """
    from app import create_app

    app = create_app()
    actual = _decorated_paths(app)

    missing = GATED_ROUTES - actual
    extra = actual - GATED_ROUTES
    assert not missing, f"목록에 있는데 게이트가 없다: {sorted(missing)}"
    assert not extra, f"게이트가 붙었는데 목록에 없다: {sorted(extra)}"
