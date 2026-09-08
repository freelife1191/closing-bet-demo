import os
import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from typing import TextIO
from time import time as _market_gate_now

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
)
from services.common_env_service import resolve_env_path
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
from app.routes.route_guards import require_admin
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
_MIN_MARKET_GATE_REFRESH_INTERVAL = 300  # 완료(실패 포함) 후 워커 공통 5분
_MIN_JONGGA_RUN_INTERVAL = timedelta(minutes=5)  # Minimum 5 minutes between runs

# Constants
DATA_DIR = 'data'

_invalidate_file_cache = invalidate_file_cache_service
_project_env_path = resolve_env_path
_atomic_write_text = lambda file_path, content: atomic_write_text_service(
    file_path,
    content,
    invalidate_fn=_invalidate_file_cache,
)
_persist_market_gate_interval_to_env = lambda interval: persist_market_gate_interval_to_env_service(
    interval=interval,
    env_path=_project_env_path(),
    atomic_write_text=_atomic_write_text,
    apply_interval_fn=_apply_market_gate_interval,
)
_apply_market_gate_interval = lambda interval: apply_market_gate_interval_service(
    interval=interval,
    logger=logger,
)
get_data_path = lambda filename: os.path.join(DATA_DIR, filename)
load_json_file = lambda filename, **kwargs: load_json_file_service(DATA_DIR, filename, **kwargs)
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


def _interval_config_response(method: str, req_data: dict):
    """config/interval 의 두 라우트가 공유하는 몸통.

    GET 에 설정 콜백을 넘겨도 handle_interval_config_request 가 호출하지 않고 반환한다.
    """
    try:
        from engine.config import app_config
        status_code, payload = handle_interval_config_request_service(
            method=method,
            req_data=req_data,
            current_interval=app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES,
            set_interval_fn=_persist_market_gate_interval_to_env,
        )
        return jsonify(payload), int(status_code)

    except Exception as e:
        logger.error("Interval Config Error: %s", type(e).__name__)
        return jsonify({'error': 'Failed to process interval configuration'}), 500


@kr_bp.route('/config/interval', methods=['GET'])
def get_interval_config():
    """Market Gate 업데이트 주기 조회. 화면이 현재 값을 보여 주므로 열어 둔다."""
    return _interval_config_response("GET", {})


# 한 뷰에 두 메서드를 두지 않는 이유가 있다. require_admin 은 메서드를 가리지 않으므로
# 한 뷰에 붙이면 조회까지 막히고 화면이 현재 주기를 보여 주지 못한다. 나누면 어느
# 메서드가 열려 있는지가 라우트 선언에서 바로 보이고, tests/app/test_admin_gated_routes.py
# 의 목록 불변식이 POST 라우트만 훑으므로 이 자리가 그 목록에 자동으로 걸린다([INFRA-059]).
@kr_bp.route('/config/interval', methods=['POST'])
@require_admin
def set_interval_config():
    """관리자 주기를 루트 .env에 저장한 뒤 요청 워커의 런타임에 적용한다."""
    return _interval_config_response("POST", request.get_json(silent=True) or {})

# VCP Screener Status State (file-backed for multi-worker gunicorn)
from services.file_backed_status import FileBackedStatus

VCP_STATUS = FileBackedStatus(
    file_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'data',
        'vcp_status.json',
    ),
    defaults={
        'running': False,
        'status': 'idle',  # idle, running, success, error, cancelled
        'task_type': None,  # screener | reanalysis_failed_ai
        'cancel_requested': False,
        'message': '',
        'last_run': None,
        'progress': 0,
    },
)

register_market_data_http_route_group(
    kr_bp,
    logger=logger,
    data_dir_getter=lambda: DATA_DIR,
    load_csv_file_fn=lambda filename, **kwargs: load_csv_file(filename, **kwargs),
    load_json_file_fn=lambda filename, **kwargs: load_json_file(filename, **kwargs),
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


def _write_market_gate_cooldown(handle: TextIO, *, running: bool = False) -> None:
    """같은 inode에 기록한다. 쓰기 실패가 기존 예약을 빈 파일로 만들지 않는다."""
    handle.seek(0)
    record = "running" if running else f"cooldown:{_market_gate_now() + _MIN_MARKET_GATE_REFRESH_INTERVAL}:end"
    handle.write(record)
    handle.flush()
    handle.truncate()


def _finish_market_gate_refresh() -> None:
    """성공·분석 실패·스레드 기동 실패가 모두 같은 정리를 거친다."""
    global is_market_gate_updating, _market_gate_process_lock_handle
    with _market_gate_lock:
        handle = _market_gate_process_lock_handle
        try:
            if handle is not None:
                _write_market_gate_cooldown(handle)
        except OSError:
            logger.exception("[Market Gate] 완료 쿨다운 기록 실패")
        finally:
            try:
                if handle is not None:
                    handle.close()  # close가 flock도 해제한다.
            except OSError:
                logger.exception("[Market Gate] 공유 잠금 파일 닫기 실패")
            finally:
                _market_gate_process_lock_handle = None
                is_market_gate_updating = False


def _trigger_market_gate_background_refresh() -> bool:
    """True는 새 시작 또는 실행 중, False는 쿨다운/실행 불가다.

    최신 GET 전용이다. 관리자 강제 갱신과 스케줄러의 정책은 바꾸지 않는다.
    """
    global is_market_gate_updating, _market_gate_process_lock_handle

    with _market_gate_lock:
        if is_market_gate_updating:
            return True
        if fcntl is None:
            logger.error("[Market Gate] 공유 잠금 사용 불가: 자동 분석 억제")
            return False

        handle: TextIO | None = None
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            lock_path = os.path.join(DATA_DIR, '.market_gate_refresh.lock')
            handle = open(os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600), 'r+', encoding='utf-8')
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # 잠금 경합은 쿨다운 조회/복구 중에도 발생한다. 실행 표식만 인정한다.
                handle.seek(0)
                running = handle.read(129).strip() == "running"
                handle.close()
                return running
            handle.seek(0)
            try:
                raw = handle.read(129).strip()
                if not raw:
                    next_allowed = 0.0  # 이전 버전의 빈 잠금 파일 허용
                elif raw.startswith("cooldown:") and raw.endswith(":end"):
                    next_allowed = float(raw[9:-4])
                else:
                    raise ValueError("incomplete cooldown")
                now = _market_gate_now()
                if (len(raw) > 128 or not math.isfinite(next_allowed) or next_allowed < 0
                        or next_allowed > now + _MIN_MARKET_GATE_REFRESH_INTERVAL):
                    raise ValueError("invalid cooldown")
            except (ValueError, UnicodeError):
                logger.warning("[Market Gate] 손상된 쿨다운: 5분 뒤 재시도")
                _write_market_gate_cooldown(handle)
                handle.close()
                return False
            if _market_gate_now() < next_allowed:
                handle.close()
                return False
            _write_market_gate_cooldown(handle, running=True)  # 중단/완료 기록 실패 시 다음 워커가 5분 예약으로 복구한다.
        except (OSError, UnicodeError):
            logger.exception("[Market Gate] 공유 쿨다운 사용 실패: 자동 분석 억제")
            if handle is not None:
                handle.close()
            return False

        _market_gate_process_lock_handle = handle
        is_market_gate_updating = True

    def run_analysis() -> None:
        try:
            from engine.market_gate import MarketGate

            market_gate = MarketGate()
            result = market_gate.analyze()
            market_gate.save_analysis(result)
            logger.info("[Market Gate] 백그라운드 분석 및 저장 완료")
        except Exception:
            logger.exception("[Market Gate] 백그라운드 분석 실패")
        finally:
            _finish_market_gate_refresh()

    try:
        threading.Thread(target=run_analysis, daemon=True).start()
    except Exception:
        logger.exception("[Market Gate] 백그라운드 스레드 기동 실패")
        _finish_market_gate_refresh()
        return False
    return True


register_system_and_execution_route_groups(
    kr_bp,
    logger=logger,
    data_dir=DATA_DIR,
    load_json_file_fn=lambda filename, **kwargs: load_json_file(filename, **kwargs),
    load_csv_file_fn=lambda filename, **kwargs: load_csv_file(filename, **kwargs),
    get_data_path_fn=lambda filename: get_data_path(filename),
    trigger_market_gate_background_refresh_fn=_trigger_market_gate_background_refresh,
    run_user_gemini_reanalysis_fn=lambda **kwargs: run_user_gemini_reanalysis(**kwargs),
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

# 한국 시장을 다루는 서비스이므로 하루의 경계도 KST 로 센다. 서버가 UTC 면 자정부터
# 오전 9시 사이에 하루가 두 번 바뀐 것처럼 보여 충전이 두 번 된다.
KST = timezone(timedelta(hours=9))


def _recharge_user_usage(usage_key: str | None, amount: int) -> tuple[int, bool]:
    """사용자 사용량을 amount 만큼 감소(충전)한다. 하루 한 번만 허용한다."""
    return recharge_user_usage_service(
        usage_key=usage_key,
        amount=amount,
        today=int(datetime.now(KST).strftime("%Y%m%d")),
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
