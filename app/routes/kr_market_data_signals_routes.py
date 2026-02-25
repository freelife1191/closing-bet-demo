#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Routes - Signals/Chart/Realtime
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from flask import jsonify, request

from app.routes.route_execution import execute_json_route as _execute_json_route
from app.routes.kr_market_signal_common import _format_signal_date
from services.kr_market_csv_utils import load_csv_readonly

def _create_signal_dates_reader(
    *,
    load_csv_file: Callable[..., Any],
    get_data_path: Callable[[str], str],
) -> Callable[[], list[str]]:
    cache: dict[str, Any] = {
        "path": None,
        "mtime": None,
        "dates": [],
    }

    def _read_signal_dates() -> list[str]:
        signals_path = get_data_path("signals_log.csv")
        try:
            mtime = os.path.getmtime(signals_path)
        except OSError:
            mtime = None

        if cache["path"] == signals_path and cache["mtime"] == mtime:
            return list(cache["dates"])

        dates: list[str] = []
        df = load_csv_readonly(
            load_csv_file,
            "signals_log.csv",
            usecols=["signal_date"],
        )
        if not df.empty and "signal_date" in df.columns:
            normalized_dates = (
                df["signal_date"]
                .dropna()
                .astype(str)
                .map(_format_signal_date)
                .tolist()
            )
            dates = sorted({item for item in normalized_dates if item}, reverse=True)

        cache["path"] = signals_path
        cache["mtime"] = mtime
        cache["dates"] = dates
        return dates

    return _read_signal_dates


def _register_market_status_route(
    kr_bp: Any,
    *,
    logger: Any,
    build_market_status_payload: Callable[..., dict[str, Any]],
    load_csv_file: Callable[..., Any],
) -> None:
    @kr_bp.route('/market-status')
    def get_kr_market_status():
        """한국 시장 상태"""
        def _handler():
            payload = build_market_status_payload(load_csv_file=load_csv_file)
            return jsonify(payload)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error checking market status",
        )


def _register_signals_route(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
    load_latest_vcp_price_map_fn: Callable[[], dict[str, float]],
    count_total_scanned_stocks_fn: Callable[[str], int],
) -> None:
    @kr_bp.route('/signals')
    def get_kr_signals():
        """오늘의 VCP + 외인매집 시그널 (BLUEPRINT 로직 적용)"""
        def _handler():
            req_date = request.args.get("date")
            payload = deps["build_vcp_signals_payload"](
                req_date=req_date,
                load_csv_file=deps["load_csv_file"],
                load_json_file=deps["load_json_file"],
                filter_signals_dataframe_by_date=deps["filter_signals_dataframe_by_date"],
                build_vcp_signals_from_dataframe=deps["build_vcp_signals_from_dataframe"],
                load_latest_vcp_price_map=load_latest_vcp_price_map_fn,
                apply_latest_prices_to_jongga_signals=deps["apply_latest_prices_to_jongga_signals"],
                sort_and_limit_vcp_signals=deps["sort_and_limit_vcp_signals"],
                build_ai_data_map=deps["build_ai_data_map"],
                merge_legacy_ai_fields_into_map=deps["merge_legacy_ai_fields_into_map"],
                merge_ai_data_into_vcp_signals=deps["merge_ai_data_into_vcp_signals"],
                count_total_scanned_stocks=count_total_scanned_stocks_fn,
                logger=logger,
                data_dir=deps["data_dir_getter"](),
            )
            return jsonify(payload)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error getting signals",
        )


def _register_signal_dates_route(
    kr_bp: Any,
    *,
    logger: Any,
    read_signal_dates: Callable[[], list[str]],
) -> None:
    @kr_bp.route('/signals/dates')
    def get_kr_signals_dates():
        """VCP 시그널 데이터가 존재하는 날짜 목록 조회"""
        def _handler():
            return jsonify(read_signal_dates())

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error getting signal dates",
        )


def _register_vcp_status_route(kr_bp: Any, *, vcp_status: dict[str, Any]) -> None:
    @kr_bp.route('/signals/status')
    def get_vcp_status():
        """VCP 스크리너 상태 조회"""
        response = jsonify(vcp_status)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


def _register_vcp_run_route(
    kr_bp: Any,
    *,
    logger: Any,
    vcp_status: dict[str, Any],
    start_vcp_screener_run: Callable[..., tuple[int, dict[str, Any]]],
    run_vcp_background: Callable[[str | None, int | None], None],
) -> None:
    @kr_bp.route('/signals/run', methods=['POST'])
    def run_vcp_signals_screener():
        """
        VCP 시그널 스크리너 실행 (특정 날짜 지원)

        Request Body:
            target_date: (Optional) YYYY-MM-DD 형식
            max_stocks: (Optional) 최대 종목 수
        """
        def _handler():
            req_data = request.get_json(silent=True) or {}
            status_code, payload = start_vcp_screener_run(
                req_data=req_data,
                status_state=vcp_status,
                background_runner=run_vcp_background,
            )
            return jsonify(payload), int(status_code)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error running VCP screener",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "error": str(error)}),
                500,
            ),
        )


def _register_vcp_reanalyze_route(
    kr_bp: Any,
    *,
    logger: Any,
    vcp_status: dict[str, Any],
    load_csv_file: Callable[..., Any],
    get_data_path: Callable[[str], str],
    validate_vcp_reanalysis_source_frame: Callable[..., tuple[int | None, dict[str, Any] | None]],
    execute_vcp_failed_ai_reanalysis: Callable[..., tuple[int, dict[str, Any]]],
    update_vcp_ai_cache_files: Callable[[str | None, dict[str, Any], dict[str, Any] | None], int],
) -> None:
    reanalysis_status_lock = threading.Lock()
    force_provider_labels = {
        "gemini": "Gemini",
        "second": "Second AI",
    }

    def _normalize_force_provider(raw_value: Any) -> str | None | object:
        normalized = str(raw_value or "").strip().lower()
        if normalized in {"", "auto", "default", "failed", "none"}:
            return None
        if normalized in {"gemini"}:
            return "gemini"
        if normalized in {"second", "secondary", "2nd"}:
            return "second"
        return _INVALID_FORCE_PROVIDER

    _INVALID_FORCE_PROVIDER = object()

    def _update_status(**kwargs: Any) -> None:
        with reanalysis_status_lock:
            vcp_status.update(kwargs)

    @kr_bp.route('/signals/reanalyze-failed-ai', methods=['POST'])
    def reanalyze_vcp_failed_ai():
        """VCP 시그널 중 AI 분석 실패 건만 재분석"""
        def _handler():
            if vcp_status.get('running'):
                if vcp_status.get('task_type') == 'reanalysis_failed_ai':
                    return jsonify({
                        'status': 'error',
                        'message': '실패 AI 재분석이 이미 진행 중입니다.'
                    }), 409
                return jsonify({
                    'status': 'error',
                    'message': 'VCP 스크리너가 실행 중입니다. 완료 후 다시 시도해 주세요.'
                }), 409

            req_data = request.get_json(silent=True) or {}
            target_date = req_data.get('target_date')
            background_mode = bool(req_data.get('background'))
            force_provider = _normalize_force_provider(req_data.get("force_provider"))
            if force_provider is _INVALID_FORCE_PROVIDER:
                return jsonify({
                    "status": "error",
                    "message": "force_provider는 gemini 또는 second만 사용할 수 있습니다.",
                }), 400
            force_label = force_provider_labels.get(str(force_provider or ""), "")
            start_prefix = f"{force_label} 강제 " if force_label else ""

            signals_df = load_csv_file('signals_log.csv')
            error_code, error_payload = validate_vcp_reanalysis_source_frame(signals_df)
            if error_payload is not None:
                return jsonify(error_payload), int(error_code)

            if not background_mode:
                status_code, payload = execute_vcp_failed_ai_reanalysis(
                    target_date=target_date,
                    signals_df=signals_df,
                    signals_path=get_data_path('signals_log.csv'),
                    update_cache_files=update_vcp_ai_cache_files,
                    logger=logger,
                    force_provider=force_provider,
                )
                return jsonify(payload), int(status_code)

            _update_status(
                running=True,
                status='running',
                task_type='reanalysis_failed_ai',
                cancel_requested=False,
                progress=0,
                message=f'{start_prefix}실패 AI 재분석 시작...',
            )

            def _should_stop() -> bool:
                return bool(vcp_status.get('cancel_requested'))

            def _on_progress(current: int, total: int, ticker: str) -> None:
                progress = int((current * 100) / total) if total > 0 else 0
                if current < total and progress >= 100:
                    progress = 99
                _update_status(
                    status='running',
                    progress=max(0, min(progress, 100)),
                    message=f'{start_prefix}실패 AI 재분석 진행 중... ({current}/{total}) {ticker}',
                )

            def _run_background_reanalysis() -> None:
                try:
                    status_code, payload = execute_vcp_failed_ai_reanalysis(
                        target_date=target_date,
                        signals_df=signals_df,
                        signals_path=get_data_path('signals_log.csv'),
                        update_cache_files=update_vcp_ai_cache_files,
                        logger=logger,
                        force_provider=force_provider,
                        should_stop=_should_stop,
                        on_progress=_on_progress,
                    )
                    payload_status = str(payload.get('status', '')).lower()
                    payload_message = str(payload.get('message', ''))

                    if status_code >= 400 or payload_status == 'error':
                        _update_status(
                            status='error',
                            message=payload_message or '실패 AI 재분석 실패',
                        )
                    elif payload_status == 'cancelled':
                        _update_status(
                            status='cancelled',
                            message=payload_message or '사용자 요청으로 재분석이 중지되었습니다.',
                        )
                    else:
                        _update_status(
                            status='success',
                            progress=100,
                            message=payload_message or '실패 AI 재분석 완료',
                        )
                except Exception as error:
                    logger.error(f"Failed AI reanalysis background error: {error}")
                    _update_status(
                        status='error',
                        message=f'실패 AI 재분석 실패: {error}',
                    )
                finally:
                    _update_status(
                        running=False,
                        last_run=datetime.now().isoformat(),
                        task_type=None,
                        cancel_requested=False,
                    )

            threading.Thread(target=_run_background_reanalysis, daemon=True).start()
            return jsonify({
                'status': 'started',
                'message': f'{start_prefix}실패 AI 재분석을 백그라운드에서 시작했습니다.',
                'target_date': target_date,
                'force_provider': force_provider,
            }), 202

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error reanalyzing VCP failed AI",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "message": str(error)}),
                500,
            ),
        )

    @kr_bp.route('/signals/reanalyze-failed-ai/stop', methods=['POST'])
    def stop_reanalyze_vcp_failed_ai():
        """실패 AI 재분석 중지 요청"""
        def _handler():
            message_text = str(vcp_status.get("message", ""))
            is_reanalysis_running = bool(vcp_status.get("running")) and (
                vcp_status.get("task_type") == "reanalysis_failed_ai"
                or "재분석" in message_text
            )
            if not is_reanalysis_running:
                return jsonify({
                    'status': 'error',
                    'message': '진행 중인 실패 AI 재분석 작업이 없습니다.'
                }), 409

            _update_status(
                task_type='reanalysis_failed_ai',
                cancel_requested=True,
                status='running',
                message='실패 AI 재분석 중지 요청을 처리 중입니다...',
            )
            return jsonify({
                'status': 'stopping',
                'message': '중지 요청이 접수되었습니다.',
            }), 202

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error stopping VCP failed AI reanalysis",
            error_response_builder=lambda error: (
                jsonify({"status": "error", "message": str(error)}),
                500,
            ),
        )


def _register_stock_chart_route(
    kr_bp: Any,
    *,
    logger: Any,
    load_csv_file: Callable[..., Any],
    build_stock_chart_payload: Callable[..., dict[str, Any]],
    resolve_chart_period_days: Callable[[str | None], int],
) -> None:
    @kr_bp.route('/stock-chart/<ticker>')
    def get_kr_stock_chart(ticker: str):
        """KR 종목 차트 데이터"""
        def _handler():
            period = request.args.get('period', '3m').lower()
            payload = build_stock_chart_payload(
                ticker=ticker,
                period_days=resolve_chart_period_days(period),
                load_csv_file=load_csv_file,
            )
            return jsonify(payload)

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error in get_kr_stock_chart",
        )


def _register_realtime_prices_route(
    kr_bp: Any,
    *,
    logger: Any,
    load_csv_file: Callable[..., Any],
    get_data_path: Callable[[str], str],
    fetch_realtime_prices: Callable[..., dict[str, float]],
    load_latest_vcp_price_map_fn: Callable[[], dict[str, float]],
) -> None:
    @kr_bp.route('/realtime-prices', methods=['POST'])
    def get_kr_realtime_prices():
        """실시간 가격 일괄 조회 (Unified Data Source)"""
        def _handler():
            data = request.get_json(silent=True) or {}
            tickers = data.get('tickers', [])
            if not isinstance(tickers, list):
                tickers = [tickers]

            prices = fetch_realtime_prices(
                tickers=tickers,
                load_csv_file=load_csv_file,
                logger=logger,
                load_latest_price_map=load_latest_vcp_price_map_fn,
                get_data_path=get_data_path,
            )
            return jsonify({'prices': prices})

        return _execute_json_route(
            handler=_handler,
            logger=logger,
            error_label="Error fetching realtime prices",
        )


def register_market_data_signal_routes(
    kr_bp: Any,
    *,
    logger: Any,
    deps: dict[str, Any],
) -> None:
    """시그널/차트/실시간 가격 라우트를 등록한다."""
    load_csv_file = deps["load_csv_file"]
    get_data_path = deps["get_data_path"]
    vcp_status = deps["vcp_status"]

    def _load_latest_vcp_price_map() -> dict[str, float]:
        return deps["load_latest_vcp_price_map"]()

    def _count_total_scanned_stocks(data_dir: str) -> int:
        count_fn = deps["count_total_scanned_stocks"]
        try:
            count_value = count_fn(data_dir)
        except TypeError:
            # 하위 호환: 기존 무인자 콜백도 허용한다.
            count_value = count_fn()
        if count_value is None:
            return 0
        return int(count_value)

    def _run_vcp_background(target_date_arg: str | None, max_stocks_arg: int | None) -> None:
        deps["run_vcp_background_pipeline"](
            target_date=target_date_arg,
            max_stocks=max_stocks_arg,
            status_state=vcp_status,
            logger=logger,
        )

    read_signal_dates = _create_signal_dates_reader(
        load_csv_file=load_csv_file,
        get_data_path=get_data_path,
    )

    _register_market_status_route(
        kr_bp,
        logger=logger,
        build_market_status_payload=deps["build_market_status_payload"],
        load_csv_file=load_csv_file,
    )
    _register_signals_route(
        kr_bp,
        logger=logger,
        deps=deps,
        load_latest_vcp_price_map_fn=_load_latest_vcp_price_map,
        count_total_scanned_stocks_fn=_count_total_scanned_stocks,
    )
    _register_signal_dates_route(
        kr_bp,
        logger=logger,
        read_signal_dates=read_signal_dates,
    )
    _register_vcp_status_route(kr_bp, vcp_status=vcp_status)
    _register_vcp_run_route(
        kr_bp,
        logger=logger,
        vcp_status=vcp_status,
        start_vcp_screener_run=deps["start_vcp_screener_run"],
        run_vcp_background=_run_vcp_background,
    )
    _register_vcp_reanalyze_route(
        kr_bp,
        logger=logger,
        vcp_status=vcp_status,
        load_csv_file=load_csv_file,
        get_data_path=get_data_path,
        validate_vcp_reanalysis_source_frame=deps["validate_vcp_reanalysis_source_frame"],
        execute_vcp_failed_ai_reanalysis=deps["execute_vcp_failed_ai_reanalysis"],
        update_vcp_ai_cache_files=deps["update_vcp_ai_cache_files"],
    )
    _register_stock_chart_route(
        kr_bp,
        logger=logger,
        load_csv_file=load_csv_file,
        build_stock_chart_payload=deps["build_stock_chart_payload"],
        resolve_chart_period_days=deps["resolve_chart_period_days"],
    )
    _register_realtime_prices_route(
        kr_bp,
        logger=logger,
        load_csv_file=load_csv_file,
        get_data_path=get_data_path,
        fetch_realtime_prices=deps["fetch_realtime_prices"],
        load_latest_vcp_price_map_fn=_load_latest_vcp_price_map,
    )
