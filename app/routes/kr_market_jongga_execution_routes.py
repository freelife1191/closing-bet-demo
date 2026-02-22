#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Execution Routes

종가베팅 실행/상태/재분석/메시지 엔드포인트를 분리 등록한다.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request

from app.routes.route_execution import execute_json_route
from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)


def _build_v2_status_io(
    *,
    data_dir: str,
    logger: Any,
) -> tuple[Callable[[bool], None], Callable[[], dict[str, Any]]]:
    v2_status_file = os.path.join(data_dir, "v2_screener_status.json")

    def _save_v2_status(running: bool) -> None:
        try:
            atomic_write_text(
                v2_status_file,
                json.dumps(
                    {
                        "isRunning": running,
                        "updated_at": datetime.now().isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception as error:
            logger.error(f"Failed to save V2 status: {error}")

    def _load_v2_status() -> dict[str, Any]:
        try:
            if not os.path.exists(v2_status_file):
                return {"isRunning": False}
            loaded = load_json_payload_from_path(v2_status_file)
            return loaded if isinstance(loaded, dict) else {"isRunning": False}
        except Exception:
            return {"isRunning": False}

    return _save_v2_status, _load_v2_status


def _build_jongga_background_runner(
    *,
    logger: Any,
    run_jongga_v2_background_pipeline: Callable[..., None],
    save_v2_status: Callable[[bool], None],
) -> Callable[[int, list[str] | None, str | None], None]:
    def _run_jongga_v2_background(
        capital: int = 50_000_000,
        markets: list[str] | None = None,
        target_date: str | None = None,
    ) -> None:
        run_jongga_v2_background_pipeline(
            capital=capital,
            markets=markets,
            target_date=target_date,
            save_status=save_v2_status,
            logger=logger,
        )

    return _run_jongga_v2_background


def _register_jongga_run_status_routes(
    kr_bp: Any,
    *,
    logger: Any,
    load_json_file: Callable[[str], dict[str, Any]],
    launch_jongga_v2_screener: Callable[..., tuple[int, dict[str, Any]]],
    load_v2_status: Callable[[], dict[str, Any]],
    save_v2_status: Callable[[bool], None],
    run_jongga_background: Callable[[int, list[str] | None, str | None], None],
) -> None:
    @kr_bp.route("/jongga-v2/run", methods=["POST"])
    def run_jongga_v2_screener_route():
        """종가베팅 v2 스크리너 실행 (비동기 - 백그라운드 스레드)"""
        req_data = request.get_json(silent=True) or {}
        status_code, payload = launch_jongga_v2_screener(
            req_data=req_data,
            load_v2_status=load_v2_status,
            save_v2_status=save_v2_status,
            run_jongga_background=run_jongga_background,
            logger=logger,
        )
        return jsonify(payload), int(status_code)

    @kr_bp.route("/jongga-v2/status", methods=["GET"])
    def get_jongga_v2_status_route():
        """종가베팅 v2 엔진 상태 조회"""
        latest_data = load_json_file("jongga_v2_latest.json")
        updated_at = latest_data.get("updated_at") if latest_data else None
        status = load_v2_status()
        is_running = status.get("isRunning", False)
        return jsonify(
            {
                "isRunning": is_running,
                "updated_at": updated_at,
                "status": "RUNNING" if is_running else "IDLE",
            }
        )


def _register_jongga_analysis_routes(
    kr_bp: Any,
    *,
    data_dir: str,
    logger: Any,
    execute_single_stock_analysis: Callable[..., tuple[int, dict[str, Any]]],
    execute_jongga_gemini_reanalysis: Callable[..., tuple[int, dict[str, Any]]],
    select_signals_for_reanalysis: Callable[..., list[dict[str, Any]]],
    build_jongga_news_analysis_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    apply_gemini_reanalysis_results: Callable[..., int],
) -> None:
    @kr_bp.route("/jongga-v2/analyze", methods=["POST"])
    def analyze_single_stock_route():
        """단일 종목 재분석 요청"""
        def _handler():
            req_data = request.get_json(silent=True) or {}
            code = req_data.get("code")
            status_code, payload = execute_single_stock_analysis(code=code, logger=logger)
            return jsonify(payload), int(status_code)

        return execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error re-analyzing stock",
            error_response_builder=lambda error: (jsonify({"error": str(error)}), 500),
        )

    @kr_bp.route("/jongga-v2/reanalyze-gemini", methods=["POST", "OPTIONS"])
    def reanalyze_gemini_all_route():
        """현재 시그널들의 Gemini LLM 분석만 재실행 (Partial / Retry 지원)"""
        if request.method == "OPTIONS":
            return jsonify({"status": "ok"}), 200

        req_data = request.get_json(silent=True) or {}
        status_code, payload = execute_jongga_gemini_reanalysis(
            req_data=req_data,
            data_dir=Path(data_dir),
            select_signals_for_reanalysis=select_signals_for_reanalysis,
            build_jongga_news_analysis_items=build_jongga_news_analysis_items,
            apply_gemini_reanalysis_results=apply_gemini_reanalysis_results,
            logger=logger,
        )
        return jsonify(payload), int(status_code)


def _register_jongga_message_route(
    kr_bp: Any,
    *,
    logger: Any,
    load_json_file: Callable[[str], dict[str, Any]],
    resolve_jongga_message_filename: Callable[[str | None], str],
    build_screener_result_for_message: Callable[[dict[str, Any]], tuple[Any, int, Any]],
) -> None:
    @kr_bp.route("/jongga-v2/message", methods=["POST"])
    def send_jongga_v2_message_route():
        """종가베팅 결과 메시지 수동 발송"""
        def _handler():
            data = request.get_json(silent=True) or {}
            target_date = data.get("target_date")

            filename = resolve_jongga_message_filename(target_date)
            file_data = load_json_file(filename)
            if not file_data or not file_data.get("signals"):
                return jsonify({"status": "error", "message": "발송할 데이터가 없습니다."}), 404

            from engine.messenger import Messenger

            result, signal_count, result_date = build_screener_result_for_message(file_data)
            messenger = Messenger()
            messenger.send_screener_result(result)

            return jsonify(
                {
                    "status": "success",
                    "message": f"메시지 발송 요청 완료 ({signal_count}개 종목)",
                    "target_date": str(result_date),
                }
            )

        return execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Message resend failed",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "error": str(error)}),
                500,
            ),
        )


def register_jongga_execution_routes(
    kr_bp: Any,
    *,
    data_dir: str,
    logger: Any,
    load_json_file: Callable[[str], dict[str, Any]],
    launch_jongga_v2_screener: Callable[..., tuple[int, dict[str, Any]]],
    run_jongga_v2_background_pipeline: Callable[..., None],
    execute_single_stock_analysis: Callable[..., tuple[int, dict[str, Any]]],
    execute_jongga_gemini_reanalysis: Callable[..., tuple[int, dict[str, Any]]],
    resolve_jongga_message_filename: Callable[[str | None], str],
    build_screener_result_for_message: Callable[[dict[str, Any]], tuple[Any, int, Any]],
    select_signals_for_reanalysis: Callable[..., list[dict[str, Any]]],
    build_jongga_news_analysis_items: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    apply_gemini_reanalysis_results: Callable[..., int],
) -> None:
    """종가베팅 실행 관련 라우트를 blueprint에 등록한다."""
    save_v2_status, load_v2_status = _build_v2_status_io(data_dir=data_dir, logger=logger)
    run_jongga_background = _build_jongga_background_runner(
        logger=logger,
        run_jongga_v2_background_pipeline=run_jongga_v2_background_pipeline,
        save_v2_status=save_v2_status,
    )
    _register_jongga_run_status_routes(
        kr_bp,
        logger=logger,
        load_json_file=load_json_file,
        launch_jongga_v2_screener=launch_jongga_v2_screener,
        load_v2_status=load_v2_status,
        save_v2_status=save_v2_status,
        run_jongga_background=run_jongga_background,
    )
    _register_jongga_analysis_routes(
        kr_bp,
        data_dir=data_dir,
        logger=logger,
        execute_single_stock_analysis=execute_single_stock_analysis,
        execute_jongga_gemini_reanalysis=execute_jongga_gemini_reanalysis,
        select_signals_for_reanalysis=select_signals_for_reanalysis,
        build_jongga_news_analysis_items=build_jongga_news_analysis_items,
        apply_gemini_reanalysis_results=apply_gemini_reanalysis_results,
    )
    _register_jongga_message_route(
        kr_bp,
        logger=logger,
        load_json_file=load_json_file,
        resolve_jongga_message_filename=resolve_jongga_message_filename,
        build_screener_result_for_message=build_screener_result_for_message,
    )
