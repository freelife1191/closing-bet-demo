#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Execution Routes

종가베팅 실행/상태/재분석/메시지 엔드포인트를 분리 등록한다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request
from werkzeug.exceptions import BadRequest

from app.routes.route_execution import execute_json_route
from app.routes.route_guards import require_admin
from services.common_update_status_service import _status_file_lock
from services.kr_market_jongga_runtime_service import read_v2_status_uncached, write_v2_status
from services.kr_market_data_cache_service import load_json_payload_from_path
from services.scheduler_runtime_status_service import get_scheduler_runtime_status


def _build_v2_status_io(
    *,
    data_dir: str,
    logger: Any,
) -> tuple[Callable[[bool], None], Callable[[], dict[str, Any]]]:
    v2_status_file = os.path.join(data_dir, "v2_screener_status.json")

    def _save_v2_status(running: bool) -> None:
        write_v2_status(v2_status_file, running, logger)

    def _load_v2_status() -> dict[str, Any]:
        try:
            if not os.path.exists(v2_status_file):
                return {"isRunning": False}
            try:
                loaded = load_json_payload_from_path(v2_status_file, deep_copy=False)
            except TypeError:
                loaded = load_json_payload_from_path(v2_status_file)
            return loaded if isinstance(loaded, dict) else {"isRunning": False}
        except Exception:
            return {"isRunning": False}

    return _save_v2_status, _load_v2_status


def _build_jongga_background_runner(
    *,
    logger: Any,
    run_jongga_v2_background_pipeline: Callable[..., None],
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
            logger=logger,
        )

    return _run_jongga_v2_background


def _register_jongga_run_status_routes(
    kr_bp: Any,
    *,
    data_dir: str,
    logger: Any,
    load_json_file: Callable[..., dict[str, Any]],
    launch_jongga_v2_screener: Callable[..., tuple[int, dict[str, Any]]],
    load_v2_status: Callable[[], dict[str, Any]],
    save_v2_status: Callable[[bool], None],
    run_jongga_background: Callable[[int, list[str] | None, str | None], None],
) -> None:
    @kr_bp.route("/jongga-v2/run", methods=["POST"])
    @require_admin
    def run_jongga_v2_screener_route():
        """종가베팅 v2 스크리너 실행 (비동기 - 백그라운드 스레드)"""
        req_data = request.get_json(silent=True) or {}
        v2_status_file = os.path.join(data_dir, "v2_screener_status.json")
        status_code, payload = launch_jongga_v2_screener(
            req_data=req_data,
            load_v2_status=lambda: read_v2_status_uncached(v2_status_file),
            save_v2_status=save_v2_status,
            run_jongga_background=run_jongga_background,
            logger=logger,
            status_lock=lambda: _status_file_lock(v2_status_file, logger),
        )
        return jsonify(payload), int(status_code)

    @kr_bp.route("/jongga-v2/status", methods=["GET"])
    def get_jongga_v2_status_route():
        """종가베팅 v2 엔진 상태 조회"""
        try:
            latest_data = load_json_file("jongga_v2_latest.json", deep_copy=False)
        except TypeError:
            latest_data = load_json_file("jongga_v2_latest.json")
        updated_at = latest_data.get("updated_at") if latest_data else None
        status = load_v2_status()
        manual_running = bool(status.get("isRunning", False))
        scheduler_status = get_scheduler_runtime_status(data_dir=data_dir)
        scheduler_running = bool(scheduler_status.get("is_jongga_scheduling_running"))
        is_running = manual_running or scheduler_running
        message = ""
        if scheduler_running:
            message = "종가베팅 스케쥴링 진행 중인 상태"
        elif manual_running:
            message = "종가베팅 분석 진행 중..."
        return jsonify(
            {
                "isRunning": is_running,
                "updated_at": updated_at,
                "status": "RUNNING" if is_running else "IDLE",
                "message": message,
                "schedulerRunning": scheduler_running,
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
    @require_admin
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
            error_response_builder=lambda _error: (
                jsonify({"error": "Internal Server Error"}),
                500,
            ),
        )

    @kr_bp.route("/jongga-v2/reanalyze-gemini", methods=["POST", "OPTIONS"])
    @require_admin
    def reanalyze_gemini_all_route():
        """현재 시그널들의 Gemini LLM 분석만 재실행 (Partial / Retry 지원)"""
        # 아래 두 줄은 [INFRA-042] 이후 도달하지 않는다. require_admin 이 그 앞에서
        # Flask 의 기본 OPTIONS 응답을 돌려주고 뷰를 부르지 않기 때문이다. 그래도
        # 지우지 않는다. 게이트를 떼는 순간 methods 에 OPTIONS 가 있는 이 라우트만
        # 본문을 실은 OPTIONS 로 뷰 로직에 닿을 수 있고, 그때 이 두 줄이 그것을 막는다.
        # 적대적 리뷰가 죽은 코드로 지목했으나 남기기로 판단한 자리다.
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
    data_dir: str,
    logger: Any,
    load_json_file: Callable[..., dict[str, Any]],
    resolve_jongga_message_filename: Callable[[str | None], str],
    build_screener_result_for_message: Callable[[dict[str, Any]], tuple[Any, int, Any]],
) -> None:
    @kr_bp.route("/jongga-v2/message", methods=["POST"])
    @require_admin
    def send_jongga_v2_message_route():
        """종가베팅 결과 메시지 수동 발송"""
        # 관리자 신원이 첫 방어이고, JSON 전용은 form 같은 단순 요청 CSRF를 막는 두 번째
        # 방어다. execute_json_route 안에서 BadRequest를 잡으면 기존 415/400 대신 500으로
        # 바뀌므로, 발송 처리에 들어가기 전에 여기서 요청 경계를 확정한다.
        if not request.is_json:
            return jsonify({"status": "error", "error": "JSON 요청 본문이 필요합니다."}), 415

        try:
            data = request.get_json()
        except BadRequest:
            logger.error("Invalid JSON body for jongga message request")
            return jsonify({"status": "error", "error": "올바른 JSON 객체가 필요합니다."}), 400

        if not isinstance(data, dict):
            return jsonify({"status": "error", "error": "JSON 객체가 필요합니다."}), 400

        def _handler():
            target_date = data.get("target_date")

            filename = resolve_jongga_message_filename(target_date)
            try:
                file_data = load_json_file(filename, deep_copy=False)
            except TypeError:
                file_data = load_json_file(filename)
            if not file_data or not file_data.get("signals"):
                return jsonify({"status": "error", "message": "발송할 데이터가 없습니다."}), 404

            from engine.messenger import Messenger
            from services.jongga_notification_guard_service import (
                claim_jongga_notification_send,
                mark_jongga_notification_sent,
                release_jongga_notification_claim,
            )

            force_send = bool(data.get("force"))
            result, signal_count, result_date = build_screener_result_for_message(file_data)
            guard_key = None
            guard_claimed = False
            guard_marked = False
            if not force_send:
                guard_claimed, guard_key = claim_jongga_notification_send(
                    data_dir=data_dir,
                    date_str=str(result_date),
                    signals=file_data.get("signals", []),
                    notification_type="daily",
                )
                if not guard_claimed:
                    return jsonify(
                        {
                            "status": "skipped",
                            "message": f"이미 발송된 종가베팅 메시지입니다. ({result_date})",
                            "target_date": str(result_date),
                            "duplicate": True,
                        }
                    ), 200

            messenger = Messenger()
            try:
                messenger.send_screener_result(result)
                if guard_claimed and guard_key:
                    mark_jongga_notification_sent(data_dir, guard_key)
                    guard_marked = True
            except Exception:
                if guard_claimed and guard_key and not guard_marked:
                    release_jongga_notification_claim(data_dir, guard_key)
                raise

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
            error_response_builder=lambda _error: (
                jsonify({"status": "error", "error": "Internal Server Error"}),
                500,
            ),
        )


def register_jongga_execution_routes(
    kr_bp: Any,
    *,
    data_dir: str,
    logger: Any,
    load_json_file: Callable[..., dict[str, Any]],
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
    )
    _register_jongga_run_status_routes(
        kr_bp,
        data_dir=data_dir,
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
        data_dir=data_dir,
        logger=logger,
        load_json_file=load_json_file,
        resolve_jongga_message_filename=resolve_jongga_message_filename,
        build_screener_result_for_message=build_screener_result_for_message,
    )
