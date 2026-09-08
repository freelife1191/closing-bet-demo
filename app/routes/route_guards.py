#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Route Guards

라우트에 붙이는 인가 게이트. 판정 자체는 services/admin_helpers.py 가 맡고 여기서는
Flask 의 요청 문맥에서 신원을 꺼내 넘기는 일만 한다.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from flask import current_app, g, jsonify, request

from services.admin_helpers import is_admin_email


def require_admin(view: Callable[..., Any]) -> Callable[..., Any]:
    """관리자 신원이 확정된 요청만 통과시킨다.

    판정 근거는 before_request 가 서명을 검증해 넣어 둔 g.user_email 이다. 브라우저가
    보낸 헤더를 그대로 믿지 않는다. 화면의 useAdmin 훅도 /api/admin/check 를 거쳐 같은
    is_admin_email 로 판정하므로, 버튼이 보이는 조건과 요청이 통과하는 조건이 같다.

    거부 형식은 common_update_routes.py:230 의 관리자 토큰 게이트와 맞춘다.

    OPTIONS 를 막으면 안 된다. before_request 가 OPTIONS 에서 일찍 반환해 g.user_email 을
    세우지 않으므로(app/__init__.py:171), 여기서 막으면 preflight 가 403 을 받아 브라우저가
    본 요청을 아예 보내지 않는다. 관리자에게도 화면이 멈춘다.

    그렇다고 뷰로 넘기지도 않는다. Flask 는 methods 에 OPTIONS 를 적은 라우트에 한해
    자동 응답을 끄고 뷰를 부르는데, 그 요청에는 본문을 실을 수 있어 curl -X OPTIONS -d ...
    한 줄이 무인증으로 뷰에 닿는다. 지금은 그런 라우트가 jongga-v2/reanalyze-gemini 하나뿐이고
    그 뷰가 첫 줄에서 빠지지만, 그 불변식을 지키는 것이 주석뿐이면 다음에 OPTIONS 를 methods
    에 두면서 조기 반환을 빠뜨린 라우트가 생기는 순간 그 자리가 통째로 열린다. 발송 핸들러가
    같은 파일에 있다.

    그래서 Flask 의 기본 OPTIONS 응답을 여기서 돌려주고 끝낸다. preflight 는 200 과 Allow
    헤더를 그대로 받고, 뷰는 어떤 경우에도 불리지 않는다. 세 리뷰(보안·적대적·Codex)가 각각
    독립적으로 같은 결론을 냈고 실측으로 확인했다([INFRA-042]).

    ponytail: 관리자 한 단계만 있다. 역할이 여러 개가 되면 그때 인자를 받는 형태로 바꾼다.
    """

    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if request.method == "OPTIONS":
            return current_app.make_default_options_response()
        if not is_admin_email(g.get("user_email")):
            return jsonify({"error": "Forbidden"}), 403
        return view(*args, **kwargs)

    return wrapped
