#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Routes - Jongga V2
"""

from __future__ import annotations

from typing import Any

from flask import jsonify

from app.routes.route_execution import execute_json_route as _execute_json_route


def _register_jongga_latest_routes(
    kr_bp: Any,
    *,
    logger: Any,
    data_dir_getter,
    load_json_file,
    load_csv_file,
    get_data_path,
    build_jongga_latest_payload,
    recalculate_jongga_grades,
    sort_jongga_signals,
    normalize_jongga_signals_for_frontend,
    apply_latest_prices_to_jongga_signals,
    load_latest_vcp_price_map,
) -> None:
    @kr_bp.route("/jongga-v2/latest", methods=["GET"])
    def get_jongga_v2_latest():
        """종가베팅 v2 최신 결과 조회"""
        def _handler():
            data = build_jongga_latest_payload(
                data_dir=data_dir_getter(),
                load_json_file=load_json_file,
                load_csv_file=load_csv_file,
                get_data_path=get_data_path,
                recalculate_jongga_grades=recalculate_jongga_grades,
                sort_jongga_signals=sort_jongga_signals,
                normalize_jongga_signals_for_frontend=normalize_jongga_signals_for_frontend,
                apply_latest_prices_to_jongga_signals=apply_latest_prices_to_jongga_signals,
                load_latest_price_map=load_latest_vcp_price_map,
                logger=logger,
            )
            return jsonify(data)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error getting jongga v2 latest",
        )

    @kr_bp.route("/jongga-v2/results", methods=["GET"])
    def get_jongga_v2_results():
        """Frontend compatibility alias for results"""
        return get_jongga_v2_latest()


def _register_jongga_dates_route(
    kr_bp: Any,
    *,
    logger: Any,
    data_dir_getter,
    load_json_file,
    collect_jongga_v2_dates,
) -> None:
    @kr_bp.route("/jongga-v2/dates", methods=["GET"])
    def get_jongga_v2_dates():
        """데이터가 존재하는 날짜 목록 조회"""
        def _handler():
            dates = collect_jongga_v2_dates(
                data_dir=data_dir_getter(),
                load_json_file=load_json_file,
                logger=logger,
            )
            return jsonify(dates)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error getting jongga v2 dates",
        )


def _register_jongga_history_route(
    kr_bp: Any,
    *,
    logger: Any,
    data_dir_getter,
    load_json_file,
    build_jongga_history_payload,
    recalculate_jongga_grades,
    sort_jongga_signals,
) -> None:
    @kr_bp.route("/jongga-v2/history/<target_date>", methods=["GET"])
    def get_jongga_v2_history(target_date: str):
        """특정 날짜의 종가베팅 결과 조회"""
        def _handler():
            status_code, payload = build_jongga_history_payload(
                target_date=target_date,
                data_dir=data_dir_getter(),
                load_json_file=load_json_file,
                recalculate_jongga_grades=recalculate_jongga_grades,
                sort_jongga_signals=sort_jongga_signals,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label=f"Error getting jongga v2 history for {target_date}",
        )


def register_market_data_jongga_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """종가 V2 조회 라우트를 등록한다."""
    _register_jongga_latest_routes(
        kr_bp,
        logger=logger,
        data_dir_getter=deps["data_dir_getter"],
        load_json_file=deps["load_json_file"],
        load_csv_file=deps["load_csv_file"],
        get_data_path=deps["get_data_path"],
        build_jongga_latest_payload=deps["build_jongga_latest_payload"],
        recalculate_jongga_grades=deps["recalculate_jongga_grades"],
        sort_jongga_signals=deps["sort_jongga_signals"],
        normalize_jongga_signals_for_frontend=deps["normalize_jongga_signals_for_frontend"],
        apply_latest_prices_to_jongga_signals=deps["apply_latest_prices_to_jongga_signals"],
        load_latest_vcp_price_map=deps.get("load_latest_vcp_price_map"),
    )
    _register_jongga_dates_route(
        kr_bp,
        logger=logger,
        data_dir_getter=deps["data_dir_getter"],
        load_json_file=deps["load_json_file"],
        collect_jongga_v2_dates=deps["collect_jongga_v2_dates"],
    )
    _register_jongga_history_route(
        kr_bp,
        logger=logger,
        data_dir_getter=deps["data_dir_getter"],
        load_json_file=deps["load_json_file"],
        build_jongga_history_payload=deps["build_jongga_history_payload"],
        recalculate_jongga_grades=deps["recalculate_jongga_grades"],
        sort_jongga_signals=deps["sort_jongga_signals"],
    )

