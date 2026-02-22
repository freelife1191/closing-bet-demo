#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market System HTTP Routes

Market Gate/재분석/갱신 상태 라우트 등록을 담당한다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import jsonify, request

from app.routes.route_execution import execute_json_route as _execute_json_route
_COMMON_UPDATE_HANDLERS: tuple[Callable[[], dict[str, Any]], Callable[[list[str]], None], Callable[..., None]] | None = None


def _resolve_common_update_handlers() -> tuple[
    Callable[[], dict[str, Any]],
    Callable[[list[str]], None],
    Callable[..., None],
]:
    """공통 업데이트 핸들러를 지연 로드하고 캐시한다."""
    global _COMMON_UPDATE_HANDLERS
    if _COMMON_UPDATE_HANDLERS is None:
        from .common import load_update_status, run_background_update, start_update

        _COMMON_UPDATE_HANDLERS = (
            load_update_status,
            start_update,
            run_background_update,
        )
    return _COMMON_UPDATE_HANDLERS


def register_system_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """시스템 관리성 라우트를 블루프린트에 등록한다."""
    _register_market_gate_routes(kr_bp, logger=logger, deps=deps)
    _register_reanalyze_gemini_route(kr_bp, logger=logger, deps=deps)
    _register_refresh_route(kr_bp, logger=logger, deps=deps)
    _register_init_data_route(kr_bp, logger=logger, deps=deps)
    _register_status_route(kr_bp, logger=logger, deps=deps)


def _register_market_gate_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/market-gate')
    def get_kr_market_gate():
        """KR Market Gate 상태 (프론트엔드 호환 형식)"""
        def _handler():
            target_date = request.args.get('date')
            filename = deps["resolve_market_gate_filename"](target_date)
            gate_data = deps["load_json_file"](filename)
            gate_data = gate_data if isinstance(gate_data, dict) else {}
            is_valid, needs_update = deps["evaluate_market_gate_validity"](
                gate_data=gate_data,
                target_date=target_date,
            )
            gate_data, is_valid = deps["apply_market_gate_snapshot_fallback"](
                gate_data=gate_data,
                is_valid=is_valid,
                target_date=target_date,
                load_json_file=deps["load_json_file"],
                logger=logger,
            )

            if not is_valid or needs_update:
                if not is_valid:
                    logger.info("[Market Gate] 유효한 데이터 없음. 백그라운드 분석 자동 시작.")
                elif needs_update:
                    logger.info("[Market Gate] 데이터 갱신 필요. 백그라운드 분석 자동 시작.")

                deps["trigger_market_gate_background_refresh"]()
                gate_data = deps["build_market_gate_initializing_payload"]()

            if not gate_data:
                gate_data = deps["build_market_gate_empty_payload"]()

            return jsonify(deps["normalize_market_gate_payload"](gate_data))

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error in get_kr_market_gate",
        )

    @kr_bp.route('/market-gate/update', methods=['POST'])
    def update_kr_market_gate():
        """Market Gate 및 관련 데이터(Smart Money) 강제 업데이트"""
        def _handler():
            data = request.get_json() or {}
            target_date = data.get('target_date')
            status_code, payload = deps["execute_market_gate_update"](
                target_date=target_date,
                logger=logger,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="[Update] Market Gate 갱신 중 오류",
        )


def _register_reanalyze_gemini_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/reanalyze/gemini', methods=['POST'])
    def reanalyze_gemini():
        """
        [AI] 기존 시그널 대상 Gemini 심층 재분석 (사용자 요청 기반)
        * 정책:
          - 개인 키 있음: 무제한
          - 개인 키 없음: 10회 제한 (usage_tracker)
        """
        def _handler():
            from flask import g
            from services.usage_tracker import usage_tracker

            user_api_key = g.get('user_api_key')
            user_email = g.get('user_email')
            req_data = request.get_json(silent=True) or {}
            status_code, payload = deps["execute_user_gemini_reanalysis_request"](
                user_api_key=user_api_key,
                user_email=user_email,
                req_data=req_data,
                usage_tracker=usage_tracker,
                project_root=deps["project_root_getter"](),
                logger=logger,
                run_reanalysis_func=deps["run_user_gemini_reanalysis"],
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error reanalyzing gemini",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "error": str(error)}),
                500,
            ),
        )


def _register_refresh_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/refresh', methods=['POST'])
    def refresh_kr_data():
        """KR 데이터 전체 갱신 (Market Gate + AI Analysis) - Background Async"""
        def _handler():
            req_data = request.get_json() or {}
            target_date = req_data.get('target_date', None)
            load_update_status, start_update, run_background_update = _resolve_common_update_handlers()

            items_list = ['Market Gate', 'AI Analysis']
            status_code, payload = deps["launch_background_update_job"](
                items_list=items_list,
                target_date=target_date,
                load_update_status=load_update_status,
                start_update=start_update,
                run_background_update=run_background_update,
                logger=logger,
            )
            if status_code == 200:
                payload['message'] = '데이터 갱신 작업이 백그라운드에서 시작되었습니다.'
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Refresh start failed",
            error_response_builder=lambda error: (
                jsonify(
                    {
                        "status": "error",
                        "message": f"데이터 갱신 시작 실패: {str(error)}",
                    }
                ),
                500,
            ),
        )


def _register_init_data_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/init-data', methods=['POST'])
    def init_data_endpoint():
        """개별 데이터 초기화 API - Background Async"""
        def _handler():
            req_data = request.get_json() or {}
            data_type = req_data.get('type', 'all')
            target_date = req_data.get('target_date', None)
            load_update_status, start_update, run_background_update = _resolve_common_update_handlers()

            status_code, payload = deps["launch_init_data_update"](
                data_type=data_type,
                target_date=target_date,
                load_update_status=load_update_status,
                start_update=start_update,
                run_background_update=run_background_update,
                logger=logger,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Init data start failed",
            error_response_builder=lambda error: (
                jsonify(
                    {
                        "status": "error",
                        "message": f"데이터 초기화 시작 실패: {str(error)}",
                    }
                ),
                500,
            ),
        )


def _register_status_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/status', methods=['GET'])
    def get_data_status():
        """데이터 수집 상태 확인"""
        def _handler():
            status = deps["build_data_status_payload"](
                get_data_path=deps["get_data_path"],
                load_csv_file=deps["load_csv_file"],
                load_json_file=deps["load_json_file"],
            )
            return jsonify({'status': 'success', 'data': status})

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Status check failed",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "message": str(error)}),
                500,
            ),
        )
