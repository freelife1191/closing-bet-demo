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
from app.routes.route_guards import require_admin
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
            try:
                filename = deps["resolve_market_gate_filename"](target_date)
            except ValueError:
                logger.warning("[Market Gate] Invalid date query rejected before file access")
                return jsonify({"error": "날짜는 유효한 YYYY-MM-DD 또는 YYYYMMDD 형식이어야 합니다."}), 400
            raw_gate_data = deps["load_json_file"](filename)
            raw_gate_data = raw_gate_data if isinstance(raw_gate_data, dict) else {}

            source_is_valid, _needs_update = deps["evaluate_market_gate_validity"](
                gate_data=raw_gate_data,
                target_date=target_date,
            )

            gate_data, is_valid = deps["apply_market_gate_snapshot_fallback"](
                gate_data=raw_gate_data,
                is_valid=source_is_valid,
                target_date=target_date,
                load_json_file=deps["load_json_file"],
                logger=logger,
            )

            # 조회는 저장 자료만 반환한다. 갱신은 관리자 POST와 스케줄러가 담당한다.
            if not is_valid:
                gate_data = deps["build_market_gate_empty_payload"]()

            if not gate_data:
                gate_data = deps["build_market_gate_empty_payload"]()

            return jsonify(deps["normalize_market_gate_payload"](gate_data))

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error in get_kr_market_gate",
        )

    @kr_bp.route('/market-gate/update', methods=['POST'])
    @require_admin
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
        """구형 모의 분석은 키·쿼터·파일 접근 전에 종료한다."""
        return jsonify({
            "status": "error", "code": "LEGACY_ANALYSIS_RETIRED",
            "message": "구형 분석이 종료되었습니다. VCP 화면의 재분석 기능을 사용하세요.",
        }), 410



def _register_refresh_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    @kr_bp.route('/refresh', methods=['POST'])
    @require_admin
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
            error_response_builder=lambda _error: (
                jsonify(
                    {
                        "status": "error",
                        "message": "Internal Server Error",
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
    @require_admin
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
            error_response_builder=lambda _error: (
                jsonify(
                    {
                        "status": "error",
                        "message": "Internal Server Error",
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
            error_response_builder=lambda _error: (
                jsonify({"status": "error", "message": "Internal Server Error"}),
                500,
            ),
        )
