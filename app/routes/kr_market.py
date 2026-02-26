import os
import logging
import threading
from datetime import timedelta
from typing import TextIO

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX 환경 호환
    fcntl = None

from flask import Blueprint, jsonify, request
from services.kr_market_route_service import (
    parse_jongga_reanalyze_request_options,
    run_jongga_news_reanalysis_batch,
    run_user_gemini_reanalysis,
    update_vcp_ai_cache_files,
)
from services.kr_market_quota_service import (
    load_quota_data_unlocked as load_quota_data_unlocked_service,
    save_quota_data_unlocked as save_quota_data_unlocked_service,
)
from services.kr_market_interval_service import (
    apply_market_gate_interval as apply_market_gate_interval_service,
    persist_market_gate_interval_to_env as persist_market_gate_interval_to_env_service,
    project_env_path as project_env_path_service,
)
from services.kr_market_interval_http_service import (
    handle_interval_config_request as handle_interval_config_request_service,
)
from services.kr_market_quota_runtime_service import (
    get_user_usage as get_user_usage_service,
    increment_user_usage as increment_user_usage_service,
    recharge_user_usage as recharge_user_usage_service,
)
from services.kr_market_data_cache_service import (
    BACKTEST_PRICE_SNAPSHOT_CACHE as _BACKTEST_PRICE_SNAPSHOT_CACHE,
    CSV_FILE_CACHE as _CSV_FILE_CACHE,
    FILE_CACHE_LOCK as _FILE_CACHE_LOCK,
    JSON_FILE_CACHE as _JSON_FILE_CACHE,
    JONGGA_RESULT_PAYLOADS_CACHE as _JONGGA_RESULT_PAYLOADS_CACHE,
    LATEST_VCP_PRICE_MAP_CACHE as _LATEST_VCP_PRICE_MAP_CACHE,
    SCANNED_STOCK_COUNT_CACHE as _SCANNED_STOCK_COUNT_CACHE,
    atomic_write_text as atomic_write_text_service,
    count_total_scanned_stocks as count_total_scanned_stocks_service,
    invalidate_file_cache as invalidate_file_cache_service,
    load_backtest_price_snapshot as load_backtest_price_snapshot_service,
    load_csv_file as load_csv_file_service,
    load_jongga_result_payloads as load_jongga_result_payloads_service,
    load_json_file as load_json_file_service,
    load_latest_vcp_price_map as load_latest_vcp_price_map_service,
)
from app.routes.kr_market_chatbot_routes import register_chatbot_and_quota_routes
from app.routes.kr_market_route_registry import (
    register_market_data_http_route_group,
    register_system_and_execution_route_groups,
)

from app.routes.kr_market_helpers import (
    _apply_gemini_reanalysis_results,
    _apply_latest_prices_to_jongga_signals,
    _apply_vcp_reanalysis_updates,
    _build_jongga_news_analysis_items,
    _build_latest_price_map,
    _build_vcp_stock_payloads,
    _calculate_scenario_return,
    _extract_vcp_ai_recommendation,
    _is_jongga_ai_analysis_completed,
    _is_meaningful_ai_reason,
    _is_vcp_ai_analysis_failed,
    _normalize_jongga_signals_for_frontend,
    _normalize_text,
    _recalculate_jongga_grade,
    _recalculate_jongga_grades,
    _select_signals_for_gemini_reanalysis,
    _sort_jongga_signals,
)

kr_bp = Blueprint('kr', __name__)
logger = logging.getLogger(__name__)

# Global Flags for Background Tasks (with locks for thread safety)
is_market_gate_updating = False
is_signals_updating = False
is_jongga_updating = False

# Thread locks for preventing race conditions
_jongga_lock = threading.Lock()
_market_gate_lock = threading.Lock()
_signals_lock = threading.Lock()
_market_gate_process_lock_handle: TextIO | None = None

# Timestamp tracking to prevent infinite loops
_jongga_last_run = None
_MIN_JONGGA_RUN_INTERVAL = timedelta(minutes=5)  # Minimum 5 minutes between runs

# Constants
DATA_DIR = 'data'

_invalidate_file_cache = invalidate_file_cache_service
_project_env_path = lambda: project_env_path_service(__file__)
_atomic_write_text = lambda file_path, content: atomic_write_text_service(
    file_path,
    content,
    invalidate_fn=_invalidate_file_cache,
)
_persist_market_gate_interval_to_env = lambda interval: persist_market_gate_interval_to_env_service(
    interval=interval,
    env_path=_project_env_path(),
    atomic_write_text=_atomic_write_text,
)
_apply_market_gate_interval = lambda interval: apply_market_gate_interval_service(
    interval=interval,
    logger=logger,
)
get_data_path = lambda filename: os.path.join(DATA_DIR, filename)
load_json_file = lambda filename: load_json_file_service(DATA_DIR, filename)
load_csv_file = lambda filename, **kwargs: load_csv_file_service(DATA_DIR, filename, **kwargs)
_load_latest_vcp_price_map = lambda: load_latest_vcp_price_map_service(DATA_DIR, logger=logger)
_count_total_scanned_stocks = count_total_scanned_stocks_service
_load_jongga_result_payloads = lambda limit=0: load_jongga_result_payloads_service(
    data_dir=DATA_DIR,
    limit=limit,
    logger=logger,
)
_load_backtest_price_snapshot = lambda: load_backtest_price_snapshot_service(
    DATA_DIR,
    build_latest_price_map=_build_latest_price_map,
)
_parse_reanalyze_request_options = parse_jongga_reanalyze_request_options
_run_jongga_news_reanalysis_batch = lambda analyzer, app_config, items_to_analyze, market_status: run_jongga_news_reanalysis_batch(
    analyzer=analyzer,
    app_config=app_config,
    items_to_analyze=items_to_analyze,
    market_status=market_status,
    logger=logger,
)


def _update_vcp_ai_cache_files(
    target_date: str,
    updated_recommendations: dict,
    ai_results: dict | None = None,
) -> int:
    return update_vcp_ai_cache_files(
        target_date=target_date,
        updated_recommendations=updated_recommendations,
        ai_results=ai_results,
        get_data_path=get_data_path,
        load_json_file=load_json_file,
        logger=logger,
    )


@kr_bp.route('/config/interval', methods=['GET', 'POST'])
def handle_interval_config():
    """Market Gate 업데이트 주기 조회 및 설정"""
    try:
        from engine.config import app_config
        status_code, payload = handle_interval_config_request_service(
            method=request.method,
            req_data=request.get_json(silent=True) or {},
            current_interval=app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES,
            apply_interval_fn=_apply_market_gate_interval,
            persist_interval_fn=_persist_market_gate_interval_to_env,
        )
        return jsonify(payload), int(status_code)

    except Exception as e:
        logger.error(f"Interval Config Error: {e}")
        return jsonify({'error': str(e)}), 500

# VCP Screener Status State
VCP_STATUS = {
    'running': False,
    'status': 'idle',  # idle, running, success, error
    'task_type': None,  # screener | reanalysis_failed_ai
    'cancel_requested': False,
    'message': '',
    'last_run': None,
    'progress': 0
}

register_market_data_http_route_group(
    kr_bp,
    logger=logger,
    data_dir_getter=lambda: DATA_DIR,
    load_csv_file_fn=lambda filename, **kwargs: load_csv_file(filename, **kwargs),
    load_json_file_fn=lambda filename: load_json_file(filename),
    get_data_path_fn=lambda filename: get_data_path(filename),
    vcp_status=VCP_STATUS,
    update_vcp_ai_cache_files_fn=lambda target_date, updated_recommendations, ai_results=None: _update_vcp_ai_cache_files(
        target_date,
        updated_recommendations,
        ai_results,
    ),
    load_latest_vcp_price_map_fn=lambda: _load_latest_vcp_price_map(),
    count_total_scanned_stocks_fn=_count_total_scanned_stocks,
    load_jongga_result_payloads_fn=lambda limit=0: _load_jongga_result_payloads(limit=limit),
    load_backtest_price_snapshot_fn=lambda: _load_backtest_price_snapshot(),
)


def _trigger_market_gate_background_refresh() -> bool:
    """Market Gate 분석을 백그라운드에서 1회 트리거한다."""
    global is_market_gate_updating
    global _market_gate_process_lock_handle

    with _market_gate_lock:
        if is_market_gate_updating:
            return False

        if fcntl is not None:
            os.makedirs(DATA_DIR, exist_ok=True)
            lock_path = os.path.join(DATA_DIR, '.market_gate_refresh.lock')
            lock_handle: TextIO | None = None
            try:
                lock_handle = open(lock_path, 'a+', encoding='utf-8')
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                _market_gate_process_lock_handle = lock_handle
            except BlockingIOError:
                if lock_handle is not None:
                    lock_handle.close()
                return False
            except Exception:
                try:
                    if lock_handle is not None:
                        lock_handle.close()
                except Exception:
                    pass
                raise

        is_market_gate_updating = True

    def run_analysis():
        global is_market_gate_updating
        global _market_gate_process_lock_handle
        try:
            from engine.market_gate import MarketGate

            market_gate = MarketGate()
            result = market_gate.analyze()
            market_gate.save_analysis(result)
            logger.info("[Market Gate] 백그라운드 분석 및 저장 완료")
        except Exception as e:
            logger.error(f"[Market Gate] 백그라운드 분석 실패: {e}")
        finally:
            with _market_gate_lock:
                is_market_gate_updating = False
                if _market_gate_process_lock_handle is not None and fcntl is not None:
                    try:
                        fcntl.flock(_market_gate_process_lock_handle.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                    try:
                        _market_gate_process_lock_handle.close()
                    except Exception:
                        pass
                    _market_gate_process_lock_handle = None

    threading.Thread(target=run_analysis, daemon=True).start()
    return True


register_system_and_execution_route_groups(
    kr_bp,
    logger=logger,
    data_dir=DATA_DIR,
    load_json_file_fn=lambda filename: load_json_file(filename),
    load_csv_file_fn=lambda filename, **kwargs: load_csv_file(filename, **kwargs),
    get_data_path_fn=lambda filename: get_data_path(filename),
    trigger_market_gate_background_refresh_fn=_trigger_market_gate_background_refresh,
    run_user_gemini_reanalysis_fn=lambda **kwargs: run_user_gemini_reanalysis(**kwargs),
    project_root_getter=lambda: os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
)

def calculate_scenario_return(ticker, entry_price, signal_date, current_price, price_df, target_pct=0.15, stop_pct=0.05):
    """헬퍼 모듈 시나리오 계산 로직에 대한 호환 래퍼."""
    return _calculate_scenario_return(
        ticker=ticker,
        entry_price=entry_price,
        signal_date=signal_date,
        current_price=current_price,
        price_df=price_df,
        target_pct=target_pct,
        stop_pct=stop_pct,
    )


# ==============================================================================
# Chatbot & Quota Shared State
# ==============================================================================

QUOTA_FILE = os.path.join(DATA_DIR, 'user_quota.json')
MAX_FREE_USAGE = 10
_quota_lock = threading.Lock()


def get_user_usage(email):
    """사용자 사용량 조회"""
    return get_user_usage_service(
        usage_key=email,
        quota_lock=_quota_lock,
        load_quota_data_unlocked=load_quota_data_unlocked_service,
        load_json_file=load_json_file,
    )


def increment_user_usage(email):
    """사용자 사용량 증가"""
    return increment_user_usage_service(
        usage_key=email,
        quota_lock=_quota_lock,
        load_quota_data_unlocked=load_quota_data_unlocked_service,
        save_quota_data_unlocked=save_quota_data_unlocked_service,
        load_json_file=load_json_file,
        atomic_write_text=_atomic_write_text,
        quota_file_path=QUOTA_FILE,
    )

def _recharge_user_usage(usage_key: str | None, amount: int) -> int:
    """사용자 사용량을 amount 만큼 감소(충전)한다."""
    return recharge_user_usage_service(
        usage_key=usage_key,
        amount=amount,
        quota_lock=_quota_lock,
        load_quota_data_unlocked=load_quota_data_unlocked_service,
        save_quota_data_unlocked=save_quota_data_unlocked_service,
        load_json_file=load_json_file,
        atomic_write_text=_atomic_write_text,
        quota_file_path=QUOTA_FILE,
    )


register_chatbot_and_quota_routes(
    kr_bp,
    logger=logger,
    max_free_usage=MAX_FREE_USAGE,
    get_user_usage_fn=get_user_usage,
    increment_user_usage_fn=increment_user_usage,
    recharge_usage_fn=_recharge_user_usage,
)
