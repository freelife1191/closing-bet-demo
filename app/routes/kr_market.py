import os
import json
import logging
import threading
from datetime import datetime, timedelta
import pandas as pd
from flask import Blueprint, jsonify, request, current_app

from app.routes.kr_market_helpers import (
    _VALID_AI_ACTIONS,
    _aggregate_cumulative_kpis,
    _apply_latest_prices_to_jongga_signals,
    _apply_gemini_reanalysis_results,
    _apply_vcp_reanalysis_updates,
    _build_ai_data_map,
    _build_ai_signals_from_jongga_results,
    _build_cumulative_trade_record,
    _build_jongga_news_analysis_items,
    _build_latest_price_map,
    _build_vcp_stock_payloads,
    _build_vcp_signals_from_dataframe,
    _calculate_jongga_backtest_stats,
    _calculate_scenario_return,
    _calculate_vcp_backtest_stats,
    _extract_stats_date_from_results_filename,
    _extract_vcp_ai_recommendation,
    _filter_signals_dataframe_by_date,
    _format_signal_date,
    _is_jongga_ai_analysis_completed,
    _is_meaningful_ai_reason,
    _is_vcp_ai_analysis_failed,
    _merge_ai_data_into_vcp_signals,
    _merge_legacy_ai_fields_into_map,
    _normalize_jongga_signals_for_frontend,
    _normalize_ai_payload_tickers,
    _normalize_text,
    _paginate_items,
    _prepare_cumulative_price_dataframe,
    _recalculate_jongga_grade,
    _recalculate_jongga_grades,
    _select_signals_for_gemini_reanalysis,
    _should_use_jongga_ai_payload,
    _sort_and_limit_vcp_signals,
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

# Timestamp tracking to prevent infinite loops
_jongga_last_run = None
_MIN_JONGGA_RUN_INTERVAL = timedelta(minutes=5)  # Minimum 5 minutes between runs

# Constants
DATA_DIR = 'data'


def _update_vcp_ai_cache_files(target_date: str, updated_recommendations: dict) -> int:
    """
    VCP AI 결과 캐시 파일(ai_analysis_results/kr_ai_analysis)에
    재분석된 Gemini 결과를 반영한다.
    """
    if not updated_recommendations:
        return 0

    date_str = str(target_date or "").replace("-", "")
    candidate_files = [
        f"ai_analysis_results_{date_str}.json" if date_str else "",
        "ai_analysis_results.json",
        f"kr_ai_analysis_{date_str}.json" if date_str else "",
        "kr_ai_analysis.json",
    ]

    updated_files = 0
    now_iso = datetime.now().isoformat()

    for filename in candidate_files:
        if not filename:
            continue
        filepath = get_data_path(filename)
        if not os.path.exists(filepath):
            continue

        try:
            data = load_json_file(filename)
            signals = data.get("signals", []) if isinstance(data, dict) else []
            if not isinstance(signals, list) or not signals:
                continue

            changed = False
            for item in signals:
                if not isinstance(item, dict):
                    continue

                ticker = str(item.get("ticker") or item.get("stock_code") or "").zfill(6)
                if ticker in updated_recommendations:
                    item["gemini_recommendation"] = updated_recommendations[ticker]
                    changed = True

            if changed:
                data["generated_at"] = now_iso
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                updated_files += 1

        except Exception as e:
            logger.warning(f"VCP AI cache update failed ({filename}): {e}")

    return updated_files


@kr_bp.route('/config/interval', methods=['GET', 'POST'])
def handle_interval_config():
    """Market Gate 업데이트 주기 조회 및 설정"""
    try:
        from services.scheduler import update_market_gate_interval
        from engine.config import app_config
        
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            new_interval = data.get('interval')
            
            if new_interval and isinstance(new_interval, int) and new_interval > 0:
                # 1. Config 업데이트
                app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES = new_interval
                
                # 2. Scheduler 업데이트
                update_market_gate_interval(new_interval)
                
                return jsonify({
                    'status': 'success', 
                    'message': f'Updated interval to {new_interval} minutes',
                    'interval': new_interval
                })
            else:
                return jsonify({'error': 'Invalid interval'}), 400
                
        else: # GET
            return jsonify({
                'interval': app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES
            })

    except Exception as e:
        logger.error(f"Interval Config Error: {e}")
        return jsonify({'error': str(e)}), 500


def get_data_path(filename: str) -> str:
    """데이터 파일 경로 반환"""
    return os.path.join(DATA_DIR, filename)


def load_json_file(filename: str) -> dict:
    """JSON 파일 로드"""
    filepath = get_data_path(filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_csv_file(filename: str) -> pd.DataFrame:
    """CSV 파일 로드"""
    filepath = get_data_path(filename)
    if os.path.exists(filepath):
        return pd.read_csv(filepath, low_memory=False)
    return pd.DataFrame()


def _load_latest_vcp_price_map() -> dict:
    """daily_prices.csv에서 ticker별 최신 종가 맵을 로드한다."""
    price_file = get_data_path("daily_prices.csv")
    if not os.path.exists(price_file):
        return {}

    df_prices = pd.read_csv(
        price_file,
        usecols=["date", "ticker", "close"],
        dtype={"ticker": str, "close": float},
    )
    if df_prices.empty:
        return {}

    df_latest = df_prices.drop_duplicates(subset=["ticker"], keep="last")
    latest_price_map = df_latest.set_index("ticker")["close"].to_dict()
    logger.debug(f"Loaded latest prices for {len(latest_price_map)} tickers")
    return latest_price_map


def _count_total_scanned_stocks(data_dir: str) -> int:
    """스캔 대상 종목 수(korean_stocks_list.csv 라인 수-헤더)를 반환한다."""
    stocks_file = os.path.join(data_dir, "korean_stocks_list.csv")
    if not os.path.exists(stocks_file):
        return 0

    with open(stocks_file, "r", encoding="utf-8") as file:
        return max(0, sum(1 for _ in file) - 1)


def _load_jongga_result_payloads(limit: int = 0) -> list:
    """
    jongga_v2_results 파일들을 최신순으로 로드한다.
    반환값: [(filepath, payload), ...]
    """
    import glob

    pattern = os.path.join(DATA_DIR, "jongga_v2_results_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if limit > 0:
        files = files[:limit]

    payloads = []
    for filepath in files:
        try:
            payload = load_json_file(os.path.basename(filepath))
            if isinstance(payload, dict):
                payloads.append((filepath, payload))
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
    return payloads


def _load_backtest_price_snapshot() -> tuple[pd.DataFrame, dict]:
    """
    백테스트용 가격 스냅샷 로드.
    반환값: (전체 가격 DataFrame, ticker별 최신 종가 맵)
    """
    price_file = get_data_path("daily_prices.csv")
    if not os.path.exists(price_file):
        return pd.DataFrame(), {}

    df_prices_full = pd.read_csv(
        price_file,
        usecols=["date", "ticker", "close", "high", "low"],
        dtype={"ticker": str},
    )
    df_prices_full["ticker"] = df_prices_full["ticker"].astype(str).str.zfill(6)
    return df_prices_full, _build_latest_price_map(df_prices_full)


@kr_bp.route('/market-status')
def get_kr_market_status():
    """한국 시장 상태"""
    try:
        # daily_prices.csv에서 KODEX 200 데이터 조회
        df = load_csv_file('daily_prices.csv')
        
        if df.empty:
            return jsonify({
                'status': 'NEUTRAL',
                'score': 50,
                'current_price': 0,
                'ma200': 0,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'symbol': '069500',
                'name': 'KODEX 200',
                'message': '데이터 파일이 없습니다. 데이터 수집이 필요합니다.'
            })
        
        # KODEX 200 (069500) 필터링
        kodex = df[df['ticker'].astype(str).str.zfill(6) == '069500']
        if kodex.empty:
            kodex = df.head(1)  # 없으면 첫 종목 사용
        
        latest = kodex.iloc[-1] if not kodex.empty else {}
        current_price = float(latest.get('close', 0))
        
        return jsonify({
            'status': 'NEUTRAL',
            'score': 50,
            'current_price': current_price,
            'ma200': current_price * 0.98,  # 예시
            'date': str(latest.get('date', datetime.now().strftime('%Y-%m-%d'))),
            'symbol': '069500',
            'name': 'KODEX 200'
        })
    except Exception as e:
        logger.error(f"Error checking market status: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/signals')
def get_kr_signals():
    """오늘의 VCP + 외인매집 시그널 (BLUEPRINT 로직 적용)"""
    try:
        source = "no_data"
        data_dir = "data"
        today = datetime.now().strftime("%Y-%m-%d")

        req_date = request.args.get("date")
        signals_df = load_csv_file("signals_log.csv")
        signals_df, today = _filter_signals_dataframe_by_date(signals_df, req_date, today)
        if req_date:
            logger.debug(f"Signals requested for explicit date: {req_date}")
        elif not signals_df.empty:
            logger.debug(f"Filtered latest signal rows: {len(signals_df)}")

        signals = _build_vcp_signals_from_dataframe(signals_df)
        if signals:
            source = "signals_log.csv"

        try:
            latest_price_map = _load_latest_vcp_price_map()
            if latest_price_map:
                _apply_latest_prices_to_jongga_signals(signals, latest_price_map)
        except Exception as e:
            logger.warning(f"Failed to inject real-time prices: {e}")

        if signals:
            signals = _sort_and_limit_vcp_signals(signals, limit=20)
            try:
                sig_date = signals[0].get("signal_date", "")
                date_str = sig_date.replace("-", "") if sig_date else datetime.now().strftime("%Y%m%d")
                ai_json = load_json_file(f"ai_analysis_results_{date_str}.json")
                if not ai_json or "signals" not in ai_json:
                    logger.info("Falling back to kr_ai_analysis.json")
                    ai_json = load_json_file("kr_ai_analysis.json")

                logger.debug(
                    "AI JSON Loaded: %s, Signals in JSON: %d",
                    bool(ai_json),
                    len(ai_json.get("signals", [])) if isinstance(ai_json, dict) else 0,
                )

                ai_data_map = _build_ai_data_map(ai_json)
                try:
                    legacy_json = load_json_file("kr_ai_analysis.json")
                    _merge_legacy_ai_fields_into_map(ai_data_map, legacy_json)
                except Exception as legacy_error:
                    logger.warning(f"Legacy merge failed: {legacy_error}")

                merged_count = _merge_ai_data_into_vcp_signals(signals, ai_data_map)
                logger.debug(f"Merged AI data for {merged_count} signals")
            except Exception as e:
                logger.warning(f"Failed to merge AI data into signals: {e}")

        total_scanned = 0
        try:
            total_scanned = _count_total_scanned_stocks(data_dir)
        except Exception:
            total_scanned = 0

        return jsonify({
            'signals': signals,
            'count': len(signals),
            'total_scanned': total_scanned,
            'generated_at': datetime.now().isoformat(),
            'source': source
        })

    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/signals/dates')
def get_kr_signals_dates():
    """VCP 시그널 데이터가 존재하는 날짜 목록 조회"""
    try:
        dates = []
        df = load_csv_file('signals_log.csv')
        
        if not df.empty and 'signal_date' in df.columns:
            # 유니크한 날짜 추출 및 정렬 (내림차순)
            dates = sorted(df['signal_date'].unique().tolist(), reverse=True)
            
        return jsonify(dates)
    except Exception as e:
        logger.error(f"Error getting signal dates: {e}")
        return jsonify({'error': str(e)}), 500



# VCP Screener Status State
VCP_STATUS = {
    'running': False,
    'status': 'idle', # idle, running, success, error
    'message': '',
    'last_run': None,
    'progress': 0
}

@kr_bp.route('/signals/status')
def get_vcp_status():
    """VCP 스크리너 상태 조회"""
    return jsonify(VCP_STATUS)

def _run_vcp_background(target_date_arg, max_stocks_arg):
    """백그라운드 VCP 스크리너 실행 (Module Level Helper)"""
    try:
        VCP_STATUS['running'] = True
        VCP_STATUS['status'] = 'running'
        VCP_STATUS['progress'] = 0
        
        if target_date_arg:
            msg = f"[VCP] 지정 날짜 분석 시작: {target_date_arg}"
        else:
            msg = "[VCP] 실시간 분석 시작..."
        
        VCP_STATUS['message'] = msg
        logger.info(msg)
        print(f"\n{msg}", flush=True)
            
        from scripts import init_data
        
        # 1. 최신 데이터 수집 (가격 업데이트)
        VCP_STATUS['message'] = "가격 데이터 업데이트 중..."
        logger.info(f"[VCP Screener] 최신 가격 데이터 수집 시작")
        print(f"[VCP Screener] 최신 가격 데이터 수집 시작...", flush=True)
        init_data.create_daily_prices(target_date=target_date_arg)
        VCP_STATUS['progress'] = 30
        
        # 1.5 수급 데이터 업데이트 (필수)
        VCP_STATUS['message'] = "수급 데이터 분석 중..."
        logger.info(f"[VCP Screener] 기관/외인 수급 데이터 업데이트")
        print(f"[VCP Screener] 기관/외인 수급 데이터 업데이트...", flush=True)
        init_data.create_institutional_trend(target_date=target_date_arg)
        VCP_STATUS['progress'] = 50
        
        # 2. 실제 데이터 기반 VCP 스크리너 실행 (init_data.py) + AI 분석
        VCP_STATUS['message'] = "VCP 패턴 분석 및 AI 진단 중..."
        logger.info(f"[VCP Screener] VCP 시그널 분석 및 AI 수행")
        print(f"[VCP Screener] VCP 시그널 분석 및 AI 수행...", flush=True)
        
        # run_ai=True로 AI 자동 수행
        result_df = init_data.create_signals_log(target_date=target_date_arg, run_ai=True)
        VCP_STATUS['progress'] = 80

        # [NEW] 최신 가격 업데이트 (Entry != Current 반영을 위해)
        VCP_STATUS['message'] = "최신 가격 동기화 중..."
        logger.info(f"[VCP Screener] 최신 가격 동기화 수행")
        init_data.update_vcp_signals_recent_price()
        VCP_STATUS['progress'] = 100
        
        if isinstance(result_df, pd.DataFrame):
            success_msg = f"완료: {len(result_df)}개 시그널 감지"
        elif result_df:
            success_msg = "완료: 성공"
        else:
            success_msg = "완료: 조건 충족 종목 없음"
            
        VCP_STATUS['message'] = success_msg
        VCP_STATUS['status'] = 'success'
        logger.info(f"[VCP Screener] {success_msg}")
        print(f"[VCP Screener] {success_msg}\n", flush=True)
            
    except Exception as e:
        logger.error(f"[VCP Screener] 실패: {e}")
        print(f"[VCP Screener] ⛔️ 실패: {e}", flush=True)
        VCP_STATUS['message'] = f"실패: {str(e)}"
        VCP_STATUS['status'] = 'error'
        import traceback
        traceback.print_exc()
    finally:
            VCP_STATUS['running'] = False
            VCP_STATUS['last_run'] = datetime.now().isoformat()

@kr_bp.route('/signals/run', methods=['POST'])
def run_vcp_signals_screener():
    """
    VCP 시그널 스크리너 실행 (특정 날짜 지원)
    
    Request Body:
        target_date: (Optional) YYYY-MM-DD 형식, 테스트용 날짜 지정
        max_stocks: (Optional) 스캔할 최대 종목 수 (기본 50)
    """
    import threading
    try:
        # 이미 실행 중이면 에러
        if VCP_STATUS['running']:
            return jsonify({'status': 'error', 'message': 'Already running'}), 409

        req_data = request.get_json(silent=True) or {}
        target_date = req_data.get('target_date', None)  # YYYY-MM-DD 형식
        max_stocks = req_data.get('max_stocks', 50)
        
        # [RACE CONDITION FIX]
        # 스레드 시작 전에 상태를 먼저 업데이트하여 프론트엔드 폴링 시 'idle'로 오인하는 것 방지
        VCP_STATUS['running'] = True
        VCP_STATUS['status'] = 'running'
        VCP_STATUS['progress'] = 0
        VCP_STATUS['message'] = "분석 요청 중..."

        thread = threading.Thread(target=_run_vcp_background, args=(target_date, max_stocks))
        thread.daemon = True
        thread.start()
        
        msg = 'VCP Screener started in background.'
        if target_date:
            msg = f'[테스트 모드] {target_date} 기준 VCP 분석 시작.'
            
        return jsonify({
            'status': 'started',
            'message': msg,
            'target_date': target_date
        })
        
    except Exception as e:
        logger.error(f"Error running VCP screener: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500



@kr_bp.route('/signals/reanalyze-failed-ai', methods=['POST'])
def reanalyze_vcp_failed_ai():
    """VCP 시그널 중 AI 분석 실패 건만 재분석"""
    try:
        if VCP_STATUS.get('running'):
            return jsonify({
                'status': 'error',
                'message': 'VCP 스크리너가 실행 중입니다. 완료 후 다시 시도해 주세요.'
            }), 409

        req_data = request.get_json(silent=True) or {}
        target_date = req_data.get('target_date')
        target_date = str(target_date).strip() if target_date else None

        signals_df = load_csv_file('signals_log.csv')
        if signals_df.empty:
            return jsonify({'status': 'error', 'message': 'signals_log.csv 데이터가 없습니다.'}), 404

        if 'ticker' not in signals_df.columns:
            return jsonify({'status': 'error', 'message': 'signals_log.csv에 ticker 컬럼이 없습니다.'}), 400
        if 'signal_date' not in signals_df.columns:
            return jsonify({'status': 'error', 'message': 'signals_log.csv에 signal_date 컬럼이 없습니다.'}), 400

        signals_df['ticker'] = signals_df['ticker'].astype(str).str.zfill(6)
        signals_df['signal_date'] = signals_df['signal_date'].astype(str)

        if target_date:
            target_date_alt = target_date.replace('-', '')
            scoped_df = signals_df[
                (signals_df['signal_date'] == target_date) |
                (signals_df['signal_date'] == target_date_alt)
            ].copy()
        else:
            latest_date = signals_df['signal_date'].max()
            target_date = str(latest_date)
            scoped_df = signals_df[signals_df['signal_date'] == str(latest_date)].copy()

        if scoped_df.empty:
            return jsonify({
                'status': 'error',
                'message': f'해당 날짜({target_date})의 VCP 시그널 데이터가 없습니다.'
            }), 404

        failed_mask = scoped_df.apply(
            lambda row: _is_vcp_ai_analysis_failed(row.to_dict()),
            axis=1
        )
        failed_df = scoped_df[failed_mask].copy()

        total_in_scope = len(scoped_df)
        failed_targets = len(failed_df)

        if failed_targets == 0:
            return jsonify({
                'status': 'success',
                'message': '재분석이 필요한 실패 항목이 없습니다.',
                'target_date': target_date,
                'total_in_scope': total_in_scope,
                'failed_targets': 0,
                'updated_count': 0,
                'still_failed_count': 0,
                'cache_files_updated': 0,
            })

        from engine.vcp_ai_analyzer import get_vcp_analyzer
        analyzer = get_vcp_analyzer()
        if not analyzer.get_available_providers():
            return jsonify({
                'status': 'error',
                'message': '사용 가능한 AI Provider가 없습니다.'
            }), 503

        failed_rows = [(idx, row.to_dict()) for idx, row in failed_df.iterrows()]
        stocks_to_analyze = _build_vcp_stock_payloads([row for _, row in failed_rows])

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ai_results = loop.run_until_complete(analyzer.analyze_batch(stocks_to_analyze))
        finally:
            loop.close()

        updated_count, still_failed_count, updated_recommendations = _apply_vcp_reanalysis_updates(
            signals_df,
            failed_rows,
            ai_results,
        )

        signals_path = get_data_path('signals_log.csv')
        signals_df.to_csv(signals_path, index=False, encoding='utf-8-sig')

        cache_files_updated = _update_vcp_ai_cache_files(target_date, updated_recommendations)

        return jsonify({
            'status': 'success',
            'message': f'실패 {failed_targets}건 중 {updated_count}건 재분석 완료',
            'target_date': target_date,
            'total_in_scope': total_in_scope,
            'failed_targets': failed_targets,
            'updated_count': updated_count,
            'still_failed_count': still_failed_count,
            'cache_files_updated': cache_files_updated,
        })

    except Exception as e:
        logger.error(f"Error reanalyzing VCP failed AI: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@kr_bp.route('/stock-chart/<ticker>')
def get_kr_stock_chart(ticker):
    """KR 종목 차트 데이터"""
    try:
        # period 파라미터 처리 (기본값: 3m)
        period = request.args.get('period', '3m').lower()
        period_days = {
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365
        }.get(period, 90)  # 기본 3개월
        
        # daily_prices.csv에서 해당 종목 데이터 조회
        df = load_csv_file('daily_prices.csv')
        ticker_padded = str(ticker).zfill(6)
        
        if df.empty:
            return jsonify({
                'ticker': ticker_padded,
                'data': [],
                'message': '데이터 파일이 없습니다.'
            })
        
        # ticker 컬럼 패딩
        df['ticker'] = df['ticker'].astype(str).str.zfill(6)
        stock_df = df[df['ticker'] == ticker_padded]
        
        if stock_df.empty:
            return jsonify({
                'ticker': ticker_padded,
                'data': [],
                'message': '해당 종목 데이터가 없습니다.'
            })
        
        # period에 따라 필터링
        if 'date' in stock_df.columns:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
            stock_df = stock_df[stock_df['date'] >= cutoff_date]
        
        chart_data = []
        for _, row in stock_df.iterrows():
            close_price = float(row.get('close', 0))
            volume = int(row.get('volume', 0))
            if close_price <= 0 or volume <= 0:
                continue

            chart_data.append({
                'date': str(row.get('date', '')),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': close_price,
                'volume': volume
            })

        return jsonify({
            'ticker': ticker_padded,
            'data': chart_data
        })

    except Exception as e:
        logger.error(f"Error in get_kr_stock_chart: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/ai-analysis')
def get_kr_ai_analysis():
    """KR AI 분석 전체 - kr_ai_analysis.json 직접 읽기 (V2 호환 최적화)"""
    try:
        target_date = request.args.get("date")

        if target_date:
            try:
                date_str = target_date.replace("-", "")
                v2_result = load_json_file(f"jongga_v2_results_{date_str}.json")
                v2_signals = _build_ai_signals_from_jongga_results(
                    v2_result.get("signals", []),
                    include_without_ai=False,
                    allow_numeric_score_fallback=True,
                )
                if v2_signals:
                    return jsonify(
                        {
                            "signals": v2_signals,
                            "generated_at": v2_result.get("updated_at", datetime.now().isoformat()),
                            "signal_date": target_date,
                            "source": "jongga_v2_integrated_history",
                        }
                    )

                analysis = load_json_file(f"kr_ai_analysis_{date_str}.json")
                if not analysis:
                    analysis = load_json_file(f"ai_analysis_results_{date_str}.json")

                if analysis:
                    return jsonify(_normalize_ai_payload_tickers(analysis))

                return jsonify(
                    {
                        "signals": [],
                        "generated_at": datetime.now().isoformat(),
                        "signal_date": target_date,
                        "message": "해당 날짜의 AI 분석 데이터가 없습니다.",
                    }
                )
            except Exception as e:
                logger.warning(f"과거 AI 분석 데이터 로드 실패: {e}")

        jongga_data = load_json_file("jongga_v2_latest.json")
        vcp_data = load_json_file("ai_analysis_results.json")

        if _should_use_jongga_ai_payload(jongga_data, vcp_data):
            ai_signals = _build_ai_signals_from_jongga_results(
                jongga_data.get("signals", []),
                include_without_ai=True,
                allow_numeric_score_fallback=False,
            )
            if ai_signals:
                return jsonify(
                    {
                        "signals": ai_signals,
                        "generated_at": jongga_data.get("updated_at", datetime.now().isoformat()),
                        "signal_date": _format_signal_date(jongga_data.get("date", "")),
                        "source": "jongga_v2_integrated_history",
                    }
                )

        kr_ai_data = load_json_file("kr_ai_analysis.json")
        if kr_ai_data and "signals" in kr_ai_data and len(kr_ai_data["signals"]) > 0:
            return jsonify(_normalize_ai_payload_tickers(kr_ai_data))

        ai_data = load_json_file("ai_analysis_results.json")
        if ai_data and "signals" in ai_data and len(ai_data["signals"]) > 0:
            return jsonify(_normalize_ai_payload_tickers(ai_data))

        return jsonify({"signals": [], "message": "AI 분석 데이터가 없습니다."})

    except Exception as e:
        logger.error(f"Error getting AI analysis: {e}")
        return jsonify({'error': str(e)}), 500




@kr_bp.route('/closing-bet/cumulative')
def get_cumulative_performance():
    """종가베팅 누적 성과 조회 (실제 데이터 연동)"""
    try:
        result_payloads = _load_jongga_result_payloads()
        raw_price_df = load_csv_file("daily_prices.csv")
        price_df = _prepare_cumulative_price_dataframe(raw_price_df)

        if not raw_price_df.empty and price_df.empty:
            logger.warning("daily_prices.csv missing required columns (date, ticker)")

        trades = []
        for filepath, data in result_payloads:
            signals = data.get("signals", [])
            if not isinstance(signals, list):
                continue

            stats_date = _extract_stats_date_from_results_filename(
                filepath,
                fallback_date=data.get("date", ""),
            )
            for signal in signals:
                trade = _build_cumulative_trade_record(signal, stats_date, price_df)
                if trade:
                    trades.append(trade)

        kpi = _aggregate_cumulative_kpis(trades, price_df, datetime.now())
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))
        paginated_trades, pagination = _paginate_items(trades, page, limit)

        return jsonify({"kpi": kpi, "trades": paginated_trades, "pagination": pagination})

    except Exception as e:
        logger.error(f"Error calculating cumulative performance: {e}")
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/market-gate')
def get_kr_market_gate():
    """KR Market Gate 상태 (프론트엔드 호환 형식)"""
    try:
        target_date = request.args.get('date')
        
        # 1차: market_gate.json 파일 사용 (가장 완전한 데이터)
        if target_date:

            # 여러 날짜 형식 지원
            try:
                if '-' in target_date:
                    date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                    date_str = date_obj.strftime('%Y%m%d')
                else:
                    date_str = target_date # 이미 YYYYMMDD 가정
            except:
                date_str = target_date.replace('-', '')
                
            filename = f'market_gate_{date_str}.json'
        else:
            filename = 'market_gate.json'
            
        gate_data = load_json_file(filename)
        
        # [2026-02-03 추가] 데이터 유효성 검사 및 Fallback (jongga_v2_latest.json 사용)
        # [2026-02-03 추가] 데이터 유효성 검사 및 Fallback (jongga_v2_latest.json 사용)
        is_valid = False
        needs_update = False  # [FIX] 백그라운드 갱신 필요 여부 플래그 추가

        if gate_data:
            # 1. Status가 "분석 대기"가 아니거나
            # 2. Sectors 데이터가 있거나
            # 3. Total Score가 50(Default)이 아닌 경우 유효하다고 판단
            if gate_data.get('status') != "분석 대기 (Neutral)" or \
               (gate_data.get('sectors') and len(gate_data['sectors']) > 0) or \
               gate_data.get('total_score', 50) != 50:
                is_valid = True
                
            # [2026-02-06 Improved] 데이터 최신성 검사 (Staleness Check)
            # 실시간 요청(target_date is None)인 경우, 저장된 데이터 날짜가 오늘과 다르면 갱신 트리거
            if not target_date and is_valid:
                dataset_date = gate_data.get('dataset_date', '')
                today_str = datetime.now().strftime('%Y-%m-%d')
                
                # 주말(토/일)이 아니면 오늘 날짜와 비교
                if datetime.now().weekday() < 5: 
                    current_hour = datetime.now().hour
                    
                    # [2026-02-09 Fix] 
                    # 1. 오전 9시 이전에는 장 시작 전이므로 전일 데이터 허용 (로그 방지)
                    # 2. 최근 30분 내에 분석된 데이터라면, 날짜가 다르더라도(장중/휴장 등) 유효하다고 판단 (무한 루프 방지)
                    is_recent_analysis = False
                    if gate_data.get('timestamp'):
                        try:
                            last_update = datetime.fromisoformat(gate_data['timestamp'])
                            if (datetime.now() - last_update).total_seconds() < 1800: # 30분
                                is_recent_analysis = True
                        except: pass

                    if current_hour >= 9 and not is_recent_analysis:
                        if dataset_date != today_str:
                            logger.info(f"[Market Gate] 데이터가 구버전임 ({dataset_date} vs {today_str}). 갱신 필요.")
                            # is_valid = False  # [FIX] 유효성 취소 대신 갱신 플래그만 설정 (UI에는 기존 데이터 표시)
                            needs_update = True
                
        if (not is_valid or needs_update) and not target_date:
            # 실시간 요청인데 데이터가 부실하면 jongga_v2 스냅샷 확인
            try:
                snapshot = load_json_file('jongga_v2_latest.json')
                if snapshot and 'market_status' in snapshot:
                    snap_status = snapshot['market_status']
                    # 스냅샷이 더 풍부한 정보를 담고 있다면 교체
                    if snap_status.get('sectors') and len(snap_status['sectors']) > 0:
                        logger.info("[Market Gate] 실시간 데이터 부실 또는 구버전 -> 종가베팅 스냅샷으로 대체 (UI용)")
                        gate_data = snap_status
                        # 날짜 정보 등 보정
                        if 'dataset_date' not in gate_data:
                            gate_data['dataset_date'] = snapshot.get('date')
                        # [FIX] 스냅샷 대체 성공 시 is_valid=True로 설정하여 불필요한 재분석 방지? 
                        # -> 아니요, 배경에서는 갱신해야 함. UI용으로는 Valid함.
                        is_valid = True
            except Exception as e:
                logger.warning(f"Market Gate Fallback 실패: {e}")
        
        # [FIX] 실시간 분석 제거 (비동기 처리 원칙)
        # 데이터가 없거나 갱신이 필요하면 백그라운드 분석 트리거
        if not is_valid or needs_update:
            if not is_valid:
                logger.info("[Market Gate] 유효한 데이터 없음. 백그라운드 분석 자동 시작.")
            elif needs_update:
                logger.info("[Market Gate] 데이터 갱신 필요. 백그라운드 분석 자동 시작.")
            
            # [Auto-Recovery] 백그라운드 분석 트리거
            global is_market_gate_updating
            if not is_market_gate_updating:
                import threading
                def run_analysis():
                    global is_market_gate_updating
                    try:
                        is_market_gate_updating = True
                        from engine.market_gate import MarketGate
                        mg = MarketGate()
                        result = mg.analyze()
                        mg.save_analysis(result)  # Explicitly save the result
                        logger.info("[Market Gate] 백그라운드 분석 및 저장 완료")
                    except Exception as e:
                        logger.error(f"[Market Gate] 백그라운드 분석 실패: {e}")
                    finally:
                        is_market_gate_updating = False

                threading.Thread(target=run_analysis).start()

            gate_data = {
                'score': 50,
                'label': 'Initializing...',
                'status': 'initializing', # Frontend polls on this status
                'is_gate_open': True,
                'kospi_close': 0,
                'kospi_change_pct': 0,
                'kosdaq_close': 0,
                'kosdaq_change_pct': 0,
                'updated_at': datetime.now().isoformat(),
                'message': '데이터 분석 중... 잠시만 기다려주세요.'
            }
        
        # 3차: 기본 데이터 (위에서 처리했으므로 중복 방지용 안전장치)
        if not gate_data:
            gate_data = {
                'score': 50,
                'label': 'Neutral',
                'status': 'YELLOW',
                'is_gate_open': True,
                'kospi_close': 0,
                'kospi_change_pct': 0,
                'kosdaq_close': 0,
                'kosdaq_change_pct': 0,
                'updated_at': datetime.now().isoformat(),
                'message': '데이터 없음'
            }
        
        # 프론트엔드 호환성: 누락된 필드 보완
        if 'score' not in gate_data and 'total_score' in gate_data:
            gate_data['score'] = gate_data['total_score']
        if 'label' not in gate_data:
            color = gate_data.get('color', gate_data.get('status', 'GRAY'))
            label_map = {'GREEN': 'Bullish', 'YELLOW': 'Neutral', 'RED': 'Bearish'}
            gate_data['label'] = label_map.get(color, 'Neutral')
        
        # indices 데이터 flatten (kospi_close, kosdaq_close 등)
        if 'indices' in gate_data:
            indices = gate_data['indices']
            if 'kospi' in indices:
                gate_data['kospi_close'] = indices['kospi'].get('value', 0)
                gate_data['kospi_change_pct'] = indices['kospi'].get('change_pct', 0)
            if 'kosdaq' in indices:
                gate_data['kosdaq_close'] = indices['kosdaq'].get('value', 0)
                gate_data['kosdaq_change_pct'] = indices['kosdaq'].get('change_pct', 0)
        elif 'metrics' in gate_data:
            metrics = gate_data['metrics']
            if 'kospi_close' not in gate_data:
                gate_data['kospi_close'] = metrics.get('kospi', 0)
            if 'kosdaq_close' not in gate_data:
                gate_data['kosdaq_close'] = metrics.get('kosdaq', 0)

        return jsonify(gate_data)

    except Exception as e:
        logger.error(f"Error in get_kr_market_gate: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/market-gate/update', methods=['POST'])
def update_kr_market_gate():
    """Market Gate 및 관련 데이터(Smart Money) 강제 업데이트"""
    try:
        data = request.get_json() or {}
        target_date = data.get('target_date')
        
        logger.info(f"[Update] Market Gate 및 Smart Money 데이터 갱신 요청 (Date: {target_date})")

        # 1. [Smart Money] 수급 데이터(기관/외인) 우선 갱신
        # Market Gate 분석 시 이 데이터가 사용되므로 먼저 실행해야 함
        from scripts import init_data
        try:
             # force=True는 아니지만, create_institutional_trend 내부 로직에 따라 필요한 경우 갱신
             # 명시적으로 실행하여 최신 상태 보장
             logger.info("[Update] 수급 데이터(Smart Money) 동기화 시작...")
             init_data.create_institutional_trend(target_date=target_date, force=True)
             logger.info("[Update] 수급 데이터 동기화 완료")
        except Exception as e:
            logger.error(f"[Update] 수급 데이터 갱신 실패 (무시하고 진행): {e}")

        # 2. [Market Gate] 시장 지표 분석 및 저장
        from engine.market_gate import MarketGate
        mg = MarketGate()
        
        # 분석 실행
        result = mg.analyze(target_date=target_date)
        
        # 결과 저장
        saved_path = mg.save_analysis(result, target_date=target_date)
        
        logger.info(f"[Update] Market Gate 분석 완료 및 저장: {saved_path}")
        
        return jsonify({
            'status': 'success',
            'message': 'Market Gate and Smart Money data updated successfully',
            'data': result
        })

    except Exception as e:
        logger.error(f"[Update] Market Gate 갱신 중 오류: {e}")
        return jsonify({'error': str(e)}), 500



@kr_bp.route('/realtime-prices', methods=['POST'])
def get_kr_realtime_prices():
    """실시간 가격 일괄 조회 (Unified Data Source)"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', [])

        if not tickers:
            return jsonify({'prices': {}})

        prices = {}
        
        # [Optimization] 소량 요청(예: 매수 모달)은 정밀도 높은 fetch_stock_price 사용
        # 대량 요청(예: 포트폴리오 목록)은 기존 Bulk 로직 유지
        if len(tickers) <= 5:
            from engine.data_sources import fetch_stock_price
            for t in tickers:
                t_str = str(t).zfill(6)
                try:
                    # fetch_stock_price returns dict {price, change_pct, ...}
                    rt_data = fetch_stock_price(t_str)
                    if rt_data and rt_data.get('price'):
                         prices[t_str] = rt_data['price']
                    else:
                         prices[t_str] = 0 # Failed
                except Exception as e:
                    logger.warning(f"Failed to fetch stock price for {t}: {e}")
                    prices[t_str] = 0
            
            return jsonify({'prices': prices})

        # --- 기존 Bulk Logic (5개 초과 시) ---
        # 폴백 순서: 토스(Bulk) → 네이버(개별) → yfinance(Bulk)
        
        try:
            import requests
            from datetime import datetime
            
            # 1. 토스 증권 API (Bulk) - 가장 빠르고 한국 주식에 최적화
            try:
                toss_codes = [f"A{str(t).zfill(6)}" for t in tickers]
                for i in range(0, len(toss_codes), 50):
                    chunk = toss_codes[i:i+50]
                    url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes={','.join(chunk)}"
                    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
                    res = requests.get(url, headers=headers, timeout=5)
                    if res.status_code == 200:
                        results = res.json().get('result', [])
                        for item in results:
                            code = item.get('code', '')
                            clean_code = code[1:] if code.startswith('A') else code
                            close = item.get('close')
                            if clean_code and close:
                                prices[clean_code] = float(close)
            except Exception as e:
                logger.debug(f"Toss Bulk API Failed: {e}")

            # 2. 네이버 증권 API (개별) - 토스 실패 종목에 대해
            missing = [t for t in tickers if str(t).zfill(6) not in prices]
            if missing:
                naver_headers = {'User-Agent': 'Mozilla/5.0'}
                for t in missing:
                    try:
                        url = f"https://m.stock.naver.com/api/stock/{str(t).zfill(6)}/basic"
                        res = requests.get(url, headers=naver_headers, timeout=2)
                        if res.status_code == 200:
                            data = res.json()
                            if 'closePrice' in data:
                                prices[str(t).zfill(6)] = float(data['closePrice'].replace(',', ''))
                    except:
                        pass

            # 3. yfinance (Bulk) - 토스/네이버 모두 실패 시 최종 폴백
            missing = [t for t in tickers if str(t).zfill(6) not in prices]
            if missing:
                now = datetime.now()
                is_weekend = now.weekday() >= 5
                is_market_hours = 9 <= now.hour < 16
                
                if not is_weekend and is_market_hours:
                    try:
                        import yfinance as yf
                        
                        # 시장 정보 로드 (KOSPI/KOSDAQ 구분용)
                        market_map = {}
                        try:
                            stocks_df = load_csv_file('korean_stocks_list.csv')
                            if not stocks_df.empty:
                                stocks_df['ticker'] = stocks_df['ticker'].astype(str).str.zfill(6)
                                market_map = dict(zip(stocks_df['ticker'], stocks_df['market']))
                        except:
                            pass

                        yf_tickers = []
                        ticker_map = {}
                        for t in missing:
                            t_padded = str(t).zfill(6)
                            market = market_map.get(t_padded, 'KOSPI')
                            suffix = ".KQ" if market == "KOSDAQ" else ".KS"
                            yf_t = f"{t_padded}{suffix}"
                            yf_tickers.append(yf_t)
                            ticker_map[yf_t] = t_padded
                        
                        if yf_tickers:
                            import logging as _logging
                            yf_logger = _logging.getLogger('yfinance')
                            original_level = yf_logger.level
                            yf_logger.setLevel(_logging.CRITICAL)
                            
                            try:
                                price_data = yf.download(yf_tickers, period='5d', interval='1d', progress=False, threads=True)
                                
                                if not price_data.empty and 'Close' in price_data:
                                    closes = price_data['Close']
                                    
                                    def extract_price(t_sym, data_src):
                                        try:
                                            if isinstance(data_src, pd.DataFrame) and t_sym in data_src.columns:
                                                series = data_src[t_sym].dropna()
                                                if not series.empty: return float(series.iloc[-1])
                                            elif isinstance(data_src, pd.Series):
                                                return float(data_src.iloc[-1])
                                        except: pass
                                        return None

                                    for yf_t in yf_tickers:
                                        val = extract_price(yf_t, closes)
                                        if val:
                                            prices[ticker_map[yf_t]] = val
                            finally:
                                yf_logger.setLevel(original_level)
                    except Exception as yf_err:
                        logger.debug(f"yfinance Fallback Failed: {yf_err}")
                        
            # Return if we have everything
            if len(prices) >= len(tickers):
                return jsonify({'prices': prices})

        except Exception as bulk_err:
            logger.debug(f"Bulk 가격 조회 실패 (CSV 폴백): {bulk_err}")

        # 2. CSV 폴백 (yfinance 실패 또는 주말/장외)
        df = load_csv_file('daily_prices.csv')
        
        if not df.empty:
            df['ticker'] = df['ticker'].astype(str).str.zfill(6)
            for t in tickers:
                ticker_padded = str(t).zfill(6)
                if ticker_padded in prices:
                    continue  # 이미 yfinance로 가져온 것은 스킵
                    
                stock_df = df[df['ticker'] == ticker_padded]
                if not stock_df.empty:
                    prices[ticker_padded] = float(stock_df.iloc[-1].get('close', 0))
                else:
                    prices[ticker_padded] = 0
        else:
            # 데이터가 없으면 0 반환
            for t in tickers:
                tp = str(t).zfill(6)
                if tp not in prices:
                    prices[tp] = 0

        return jsonify({'prices': prices})

    except Exception as e:
        logger.error(f"Error fetching realtime prices: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/jongga-v2/latest', methods=['GET'])
def get_jongga_v2_latest():
    """종가베팅 v2 최신 결과 조회"""
    try:
        # jongga_v2_latest.json 파일에서 데이터 로드
        data = load_json_file('jongga_v2_latest.json')
        
        # 빈 데이터이거나 signals가 0개인 경우 최근 유효 데이터 검색
        if not data or len(data.get('signals', [])) == 0:
            import glob
            # 날짜별 파일 검색 (최신순 정렬)
            pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
            files = sorted(glob.glob(pattern), reverse=True)
            
            # 유효한 데이터가 있는 파일 찾기
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        candidate = json.load(f)
                        if len(candidate.get('signals', [])) > 0:
                            # 유효한 데이터 발견 - 주말/휴일 안내 메시지 추가
                            if _recalculate_jongga_grades(candidate):
                                with open(file_path, 'w', encoding='utf-8') as wf:
                                    json.dump(candidate, wf, ensure_ascii=False, indent=2)
                            candidate['message'] = f"주말/휴일로 인해 {candidate.get('date', '')} 거래일 데이터를 표시합니다."
                            logger.info(f"[Jongga V2] 최근 유효 데이터 사용: {file_path}")
                            return jsonify(candidate)
                except Exception as e:
                    logger.warning(f"파일 읽기 실패: {file_path} - {e}")
                    continue
            
            # 유효한 데이터가 없는 경우 -> 데이터 없음 응답 반환 (자동 실행 비활성화)
            now = datetime.now()
            logger.info("[Jongga V2] 종가베팅 데이터 없음. 자동 실행 비활성화 상태.")

            return jsonify({
                'date': now.date().isoformat(),
                'signals': [],
                'filtered_count': 0,
                'status': 'no_data',
                'message': '현재 종가베팅 데이터가 없습니다. [업데이트] 버튼을 눌러 분석을 실행해주세요.'
            })
        
        # [NEW] 실시간 가격 주입 (Jongga V2)
        if data and data.get('signals'):
            try:
                price_file = get_data_path('daily_prices.csv')
                if os.path.exists(price_file):
                    df_prices = pd.read_csv(price_file, usecols=['date', 'ticker', 'close'], dtype={'ticker': str, 'close': float})
                    if not df_prices.empty:
                        df_latest = df_prices.drop_duplicates(subset=['ticker'], keep='last')
                        latest_price_map = df_latest.set_index('ticker')['close'].to_dict()
                        updated_count = _apply_latest_prices_to_jongga_signals(
                            data['signals'],
                            latest_price_map,
                        )
                        logger.debug(f"[Jongga V2 Latest] Updated prices for {updated_count} signals")
            except Exception as e:
                logger.warning(f"Failed to inject prices for Jongga V2: {e}")

        if data and data.get('signals'):
            # 저장 데이터의 grade가 이전 규칙으로 남아 있는 케이스 보정
            if _recalculate_jongga_grades(data):
                with open(get_data_path('jongga_v2_latest.json'), 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            _sort_jongga_signals(data['signals'])
            _normalize_jongga_signals_for_frontend(data['signals'])

        return jsonify(data)

    except Exception as e:
        logger.error(f"Error getting jongga v2 latest: {e}")
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/jongga-v2/results', methods=['GET'])
def get_jongga_v2_results():
    """Frontend compatibility alias for results"""
    return get_jongga_v2_latest()


@kr_bp.route('/jongga-v2/dates', methods=['GET'])
def get_jongga_v2_dates():
    """데이터가 존재하는 날짜 목록 조회"""
    try:
        # DATA_DIR에서 날짜별 파일 목록 조회 (예: jongga_v2_results_20260130.json)
        dates = []
        import glob
        pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
        files = glob.glob(pattern)
        
        for file_path in files:
            filename = os.path.basename(file_path)
            # jongga_v2_results_20260130.json -> 20260130
            date_part = filename.replace('jongga_v2_results_', '').replace('.json', '')
            
            # YYYYMMDD -> YYYY-MM-DD 변환
            if len(date_part) == 8:
                formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"
                dates.append(formatted_date)
            else:
                # 다른 형식이 있다면 그대로 추가하거나 무시
                dates.append(date_part)
        
        # 최신 데이터 날짜도 확인하여 목록에 없으면 추가
        try:
            latest_data = load_json_file('jongga_v2_latest.json')
            if latest_data and 'date' in latest_data:
                latest_date = latest_data['date'][:10]  # YYYY-MM-DD만 추출
                if latest_date not in dates:
                    dates.append(latest_date)
        except:
            pass
        
        # 날짜 정렬 (최신순) 및 중복 제거
        dates = sorted(list(set(dates)), reverse=True)
        return jsonify(dates)

    except Exception as e:
        logger.error(f"Error getting jongga v2 dates: {e}")
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/jongga-v2/history/<target_date>', methods=['GET'])
def get_jongga_v2_history(target_date):
    """특정 날짜의 종가베팅 결과 조회"""
    try:
        # 날짜 형식 변환: YYYY-MM-DD -> YYYYMMDD
        date_str = target_date.replace('-', '')
        
        # 기본 디렉토리에서 해당 날짜 파일 로드(예: jongga_v2_results_20260130.json)
        history_file = os.path.join(DATA_DIR, f'jongga_v2_results_{date_str}.json')
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data and 'signals' in data:
                    # 저장 데이터의 grade 보정
                    _recalculate_jongga_grades(data)
                    _sort_jongga_signals(data['signals'])
                return jsonify(data)
        
        # 최신 파일의 날짜와 같으면 최신 파일 반환
        latest_data = load_json_file('jongga_v2_latest.json')
        if latest_data and latest_data.get('date', '')[:10] == target_date:
            if latest_data and 'signals' in latest_data:
                _recalculate_jongga_grades(latest_data)
                _sort_jongga_signals(latest_data['signals'])
            return jsonify(latest_data)
        
        return jsonify({
            'error': f'{target_date} 날짜의 데이터가 없습니다.',
            'date': target_date,
            'signals': []
        }), 404

    except Exception as e:
        logger.error(f"Error getting jongga v2 history for {target_date}: {e}")
        return jsonify({"error": str(e)}), 500



# V2 Status File
V2_STATUS_FILE = os.path.join(DATA_DIR, 'v2_screener_status.json')

def _save_v2_status(running: bool):
    try:
        with open(V2_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'isRunning': running, 
                'updated_at': datetime.now().isoformat()
            }, f)
    except Exception as e:
        logger.error(f"Failed to save V2 status: {e}")

def _load_v2_status():
    try:
        if not os.path.exists(V2_STATUS_FILE):
             return {'isRunning': False}
        with open(V2_STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'isRunning': False}


def _run_jongga_v2_background(capital: int = 50_000_000, markets: list = None, target_date: str = None):
    """
    백그라운드에서 Jongga V2 엔진 실행 (Flask request context 불필요)

    Args:
        capital: 초기 투자금 (기본값: 5000만원)
        markets: 대상 시장 리스트 ['KOSPI', 'KOSDAQ']
        target_date: 분석 기준일 (YYYY-MM-DD, 테스트용)
    """
    if markets is None:
        markets = ['KOSPI', 'KOSDAQ']

    # Set Running Flag
    _save_v2_status(True)

    logger.info("[Background] Jongga V2 Engine Started...")
    if target_date:
        logger.info(f"[테스트 모드] 지정 날짜 기준 분석: {target_date}")

    try:
        # engine 모듈 강제 리로드 (코드 변경 사항 반영)
        import sys

        # [FIX] 기존 engine 모듈 삭제 시 외부 라이브러리(yfinance, pykrx, FinanceDataReader 등)를
        # 간접적으로 깨뜨리지 않도록, 삭제 대상을 프로젝트 engine 서브모듈로 한정
        # 특히 engine.__init__은 외부 라이브러리를 import하므로 제외
        PRESERVE_MODULES = {'engine'}  # engine 패키지 자체는 보존
        mods_to_remove = [
            k for k in list(sys.modules.keys())
            if k.startswith('engine.') and k not in PRESERVE_MODULES
        ]
        for mod in mods_to_remove:
            del sys.modules[mod]

        # 새로 import
        from engine.generator import run_screener, save_result_to_json
        import asyncio

        # 비동기 함수 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_screener(capital=capital, markets=markets, target_date=target_date))
        finally:
            # [FIX] Close all async generators before closing the loop
            # This prevents "Task was destroyed but it is pending" error
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as e:
                logger.warning(f"Error shutting down async generators: {e}")
            loop.close()

        # 결과 저장
        if result:
            save_result_to_json(result)

            # 메신저 알림 발송 (result 객체 직접 사용)
            try:
                # Signal 객체 리스트를 딕셔너리 리스트로 변환 (Notifier 호환성)
                signals = [s.to_dict() for s in result.signals]
                date_str = result.date.strftime('%Y-%m-%d') if hasattr(result.date, 'strftime') else str(result.date)

                if signals:
                    from services.notifier import send_jongga_notification
                    results = send_jongga_notification(signals, date_str)
                    logger.info(f"[Notification] 메신저 발송 결과: {results}")
                else:
                    logger.info("[Notification] 발송할 시그널 없음 (0개)")

            except Exception as notify_error:
                logger.error(f"[Notification] 메신저 발송 중 오류: {notify_error}")

        logger.info("[Background] Jongga V2 Engine Completed Successfully.")

    finally:
        # Always reset status, even on error
        _save_v2_status(False)
        logger.info("[Background] Jongga V2 Status reset to False")


@kr_bp.route('/jongga-v2/run', methods=['POST'])
def run_jongga_v2_screener():
    """종가베팅 v2 스크리너 실행 (비동기 - 백그라운드 스레드)"""
    import threading

    # Check file based status
    status = _load_v2_status()
    if status.get('isRunning', False):
        return jsonify({
            'status': 'error',
            'message': 'Engine is already running. Please wait.'
        }), 409

    req_data = request.get_json(silent=True) or {}
    capital = req_data.get('capital', 50_000_000)
    markets = req_data.get('markets', ['KOSPI', 'KOSDAQ'])
    target_date = req_data.get('target_date', None)  # YYYY-MM-DD 형식 (테스트용)

    def _run_wrapper():
        """Wrapper for background execution with status management"""
        try:
            _run_jongga_v2_background(capital=capital, markets=markets, target_date=target_date)
        except Exception as e:
            logger.error(f"Background Engine Failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reset Running Flag
            _save_v2_status(False)

    try:
        # 스레드 실행 (target_date 포함)
        thread = threading.Thread(target=_run_wrapper)
        thread.daemon = True
        thread.start()
        
        # 즉시 상태 파일 업데이트 (스레드 시작 전 레이스 컨디션 방지, 근데 스레드 안에서도 덮어쓰는데 뭐.. 안전하게 여기서도 True)
        _save_v2_status(True)
        
        msg = 'Engine started in background. Poll /jongga-v2/status for completion.'
        if target_date:
            msg = f'[테스트 모드] {target_date} 기준 분석 시작. Poll /jongga-v2/status for completion.'
        
        return jsonify({
            'status': 'started',
            'message': msg,
            'target_date': target_date
        })

    except ImportError as e:
        _save_v2_status(False)
        logger.error(f"Import error running screener: {e}")
        return jsonify({
            'status': 'error',
            'error': '스크리너 모듈을 불러올 수 없습니다.',
            'details': str(e)
        }), 500
    except Exception as e:
        _save_v2_status(False)
        logger.error(f"Error running jongga v2 screener: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@kr_bp.route('/jongga-v2/status', methods=['GET'])
def get_jongga_v2_status():
    """종가베팅 v2 엔진 상태 조회"""
    
    # 최신 데이터 날짜 조회
    latest_data = load_json_file('jongga_v2_latest.json')
    updated_at = latest_data.get('updated_at') if latest_data else None
    
    # Check status file
    status = _load_v2_status()
    is_running = status.get('isRunning', False)
    
    return jsonify({
        'isRunning': is_running,
        'updated_at': updated_at,
        'status': 'RUNNING' if is_running else 'IDLE'
    })


@kr_bp.route('/jongga-v2/analyze', methods=['POST'])
def analyze_single_stock():
    """단일 종목 재분석 요청"""
    try:
        req_data = request.get_json()
        code = req_data.get('code')

        if not code:
            return jsonify({"error": "Stock code is required"}), 400

        # engine의 단일 종목 분석 함수 호출
        try:
            from engine.generator import analyze_single_stock_by_code, update_single_signal_json
            import asyncio
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                signal = loop.run_until_complete(analyze_single_stock_by_code(code))
            finally:
                loop.close()
            
            if signal:
                update_single_signal_json(code, signal)
                return jsonify({
                    'status': 'success',
                    'signal': {
                        'stock_code': signal.stock_code,
                        'stock_name': signal.stock_name,
                        'grade': signal.grade.value if hasattr(signal.grade, 'value') else signal.grade,
                        'score': signal.score.total if hasattr(signal.score, 'total') else signal.score
                    }
                })
            else:
                return jsonify({
                    'status': 'error',
                    'error': f'{code} 종목을 찾을 수 없습니다.'
                }), 404
                
        except ImportError:
            # engine 모듈이 없으면 샘플 응답 반환
            return jsonify({
                'status': 'success',
                'signal': {
                    'stock_code': code.zfill(6),
                    'stock_name': '샘플 종목',
                    'grade': 'A',
                    'score': {'total': 8, 'news': 2, 'volume': 3, 'chart': 1, 'candle': 0, 'timing': 1, 'supply': 1}
                },
                'message': 'engine 모듈을 사용할 수 없어 샘플 데이터를 반환합니다.'
            })

    except Exception as e:
        logger.error(f"Error re-analyzing stock {code}: {e}")
        return jsonify({"error": str(e)}), 500


@kr_bp.route('/jongga-v2/reanalyze-gemini', methods=['POST', 'OPTIONS'])
def reanalyze_gemini_all():
    """현재 시그널들의 Gemini LLM 분석만 재실행 (Partial / Retry 지원)"""
    # 즉시 출력으로 요청 도달 확인
    print(f"\n{'='*60}")
    print(f">>> REANALYZE GEMINI API CALLED - Method: {request.method}")
    print(f"{'='*60}\n")
    
    # OPTIONS preflight 처리
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    
    try:
        print(">>> [API] 요청 처리 시작...")
        import json
        import asyncio
        from pathlib import Path
        import sys
        sys.stdout.flush()
        
        # Request Parameters
        req_data = request.get_json(silent=True) or {}
        target_tickers = req_data.get('target_tickers', []) # List of strings
        force_update = req_data.get('force', False)
        
        print(f">>> 요청 파라미터: target_tickers={target_tickers}, force={force_update}")

        # 최신 결과 파일 로드
        latest_file = Path(__file__).parent.parent.parent / 'data' / 'jongga_v2_latest.json'
        
        if not latest_file.exists():
            print(">>> [ERROR] 데이터 파일 없음!")
            return jsonify({'status': 'error', 'error': '분석할 시그널이 없습니다. 먼저 엔진을 실행하세요.'}), 404
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        all_signals = data.get('signals', [])
        print(f">>> [Data] 로드된 후보 종목: 총 {len(all_signals)}개")
        
        # signals가 비어있는 경우 최근 유효 데이터 검색
        if not all_signals:
            print(">>> [Data] 시그널 없음 - 최근 유효 데이터 검색 중...")
            import glob
            pattern = str(Path(__file__).parent.parent.parent / 'data' / 'jongga_v2_results_*.json')
            files = sorted(glob.glob(pattern), reverse=True)
            
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        candidate = json.load(f)
                        if len(candidate.get('signals', [])) > 0:
                            data = candidate
                            all_signals = data.get('signals', [])
                            latest_file = Path(file_path)  # 파일 경로 업데이트
                            print(f">>> [Data] 유효 데이터 발견: {file_path} ({len(all_signals)}개 시그널)")
                            break
                except Exception as e:
                    print(f">>> [Data] 파일 읽기 실패: {file_path} - {e}")
                    continue
        
        if not all_signals:
            return jsonify({'status': 'error', 'error': '분석할 시그널이 없습니다. 평일에 엔진을 먼저 실행해주세요.'}), 404
            
        # --- Filter Signals to Analyze ---
        signals_to_process = _select_signals_for_gemini_reanalysis(
            all_signals=all_signals,
            target_tickers=target_tickers,
            force_update=force_update,
        )
        if target_tickers:
            target_set = set(str(t).strip() for t in target_tickers)
            print(f">>> [Filter] 타겟 종목 분석: {target_set}")
        elif force_update:
            print(f">>> [Filter] 강제 전체 재분석")
        else:
            print(f">>> [Filter] 스마트 분석 (누락/실패 항목만)")

        print(f">>> [Filter] 최종 분석 대상: {len(signals_to_process)}개 / 전체 {len(all_signals)}개")
        
        if not signals_to_process:
            return jsonify({
                'status': 'success', 
                'message': '모든 종목에 AI 분석이 완료되어 있습니다. 재분석이 필요하면 force=true 옵션을 사용하세요.'
            })

        # LLM 분석기 로드
        print(">>> [Engine] LLM 분석기 로드 중...")
        try:
            from engine.llm_analyzer import LLMAnalyzer
            from engine.config import app_config
            
            analyzer = LLMAnalyzer()
            
            # Market Gate 상태 조회
            market_status = None
            try:
                from engine.market_gate import MarketGate
                mg = MarketGate()
                market_status = mg.analyze()
            except Exception as e:
                print(f"Error checking market gate: {e}")

            # 배치 분석 데이터 준비
            items_to_analyze = _build_jongga_news_analysis_items(signals_to_process)

            if not items_to_analyze:
                return jsonify({'status': 'error', 'error': '분석 대상 종목들에 뉴스가 없어 분석할 수 없습니다.'}), 404

            # Chunking (Check Provider)
            is_analysis_llm = analyzer.provider == 'gemini'
            chunk_size = app_config.ANALYSIS_LLM_CHUNK_SIZE if is_analysis_llm else app_config.LLM_CHUNK_SIZE
            
            chunks = [items_to_analyze[i:i + chunk_size] for i in range(0, len(items_to_analyze), chunk_size)]
            
            results_map = {}
            updated_count = 0
            
            import time
            total_start_time = time.time()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            print(f"\n{'='*70}")
            print(f">>> Gemini 배치 분석 시작: 총 {len(items_to_analyze)}개 종목")
            print(f"{'='*70}")
            
            try:
                # 병렬 처리를 위한 비동기 함수
                async def process_chunk(chunk_idx, chunk_data):
                    chunk_start = time.time()
                    chunk_stock_names = [item.get('stock', {}).get('stock_name', 'Unknown') for item in chunk_data]
                    print(f"\n>>> 청크 {chunk_idx + 1}/{len(chunks)} 처리 시작: {chunk_stock_names}")
                    
                    chunk_results = await analyzer.analyze_news_batch(chunk_data, market_status)
                    
                    if chunk_results:
                        for name, res in chunk_results.items():
                            print(f"    ✓ {name}: {res.get('action', 'N/A')}")
                    
                    return chunk_results or {}
                
                # 모든 청크 순차/병렬 처리 (Concurrency 제어 + Delay 적용)
                async def process_all_chunks():
                    concurrency = app_config.ANALYSIS_LLM_CONCURRENCY if is_analysis_llm else app_config.LLM_CONCURRENCY
                    delay = app_config.ANALYSIS_LLM_REQUEST_DELAY if is_analysis_llm else 0.5
                    
                    semaphore = asyncio.Semaphore(concurrency)
                    results = []
                    
                    # 청크 단위로 순차 실행하되, 내부적으로 Semaphore로 동시성 제어
                    for i, chunk in enumerate(chunks):
                        async with semaphore:
                            res = await process_chunk(i, chunk)
                            results.append(res)
                        
                        # 마지막 청크가 아니면 대기
                        if i < len(chunks) - 1:
                            print(f">>> [Rate Limit] 청크 간 대기: {delay}초...")
                            await asyncio.sleep(delay)
                            
                    return results
                
                all_results = loop.run_until_complete(process_all_chunks())
                
                # 결과 병합
                for chunk_result in all_results:
                    if chunk_result:
                        results_map.update(chunk_result)
                        
            finally:
                loop.close()
                
            total_elapsed = time.time() - total_start_time
            print(f"\n>>> 전체 LLM 분석 완료: {total_elapsed:.2f}초 소요")

            print(f"\n>>> 결과 매핑 시작: {len(results_map)}개 LLM 결과")
            updated_count = _apply_gemini_reanalysis_results(
                all_signals=all_signals,
                results_map=results_map,
            )
            
            # 저장
            data['updated_at'] = datetime.now().isoformat()
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            return jsonify({
                'status': 'success',
                'message': f'{updated_count}개 종목의 Gemini 분석이 완료되었습니다.'
            })
            
        except ImportError as e:
            return jsonify({'status': 'error', 'error': f'LLM 모듈 로드 실패: {e}'}), 500
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"\n{'='*70}\n[ERROR] reanalyze_gemini_all FAILED!\n{trace}\n{'='*70}\n")
        logger.error(f"Error reanalyzing gemini: {e}\n{trace}")
        return jsonify({'status': 'error', 'error': str(e), 'traceback': trace}), 500


@kr_bp.route('/jongga-v2/message', methods=['POST'])
def send_jongga_v2_message():
    """종가베팅 결과 메시지 수동 발송"""
    try:
        data = request.get_json(silent=True) or {}
        target_date = data.get('target_date')
        
        # 1. 파일 로드
        if target_date:
            try:
                if '-' in target_date:
                    date_str = target_date.replace('-', '')
                else:
                    date_str = target_date
            except:
                date_str = target_date

            filename = f'jongga_v2_results_{date_str}.json'
            file_data = load_json_file(filename)
        else:
            file_data = load_json_file('jongga_v2_latest.json')
            
        if not file_data or not file_data.get('signals'):
            return jsonify({'status': 'error', 'message': '발송할 데이터가 없습니다.'}), 404
            
        # 2. 객체 복원 (Messenger 호환성)
        from engine.models import ScreenerResult, Signal, ScoreDetail, ChecklistDetail, SignalStatus, Grade
        from engine.messenger import Messenger
        from datetime import datetime
        
        signals = []
        for s in file_data.get('signals', []):
            # ScoreDetail 복원 (total 포함)
            sc = s.get('score', {})
            score_obj = ScoreDetail(**sc)
            
            # ChecklistDetail 복원
            cl = s.get('checklist', {})
            checklist_obj = ChecklistDetail(**cl)
            
            # 날짜/시간
            try:
                sig_date = datetime.strptime(s['signal_date'], '%Y-%m-%d').date()
            except:
                sig_date = datetime.now().date()
                
            try:
                sig_time = datetime.fromisoformat(s['signal_time'])
            except:
                 sig_time = datetime.now()
            
            try:
                created_at = datetime.fromisoformat(s['created_at'])
            except:
                created_at = datetime.now()
            
            # Enum 처리
            grade_val = s['grade']
            if isinstance(grade_val, str):
                try:
                    grade = Grade(grade_val)
                except:
                    grade = grade_val
            else:
                grade = grade_val
                
            status_val = s['status']
            if isinstance(status_val, str):
                try:
                    status = SignalStatus(status_val)
                except:
                    status = status_val
            else:
                status = status_val

            signal_obj = Signal(
                stock_code=s['stock_code'],
                stock_name=s['stock_name'],
                market=s['market'],
                sector=s['sector'],
                signal_date=sig_date,
                signal_time=sig_time,
                grade=grade,
                score=score_obj,
                checklist=checklist_obj,
                news_items=s['news_items'],
                current_price=s['current_price'],
                entry_price=s['entry_price'],
                stop_price=s['stop_price'],
                target_price=s['target_price'],
                r_value=s['r_value'],
                position_size=s['position_size'],
                quantity=s['quantity'],
                r_multiplier=s['r_multiplier'],
                trading_value=s['trading_value'],
                change_pct=s['change_pct'],
                status=status,
                created_at=created_at,
                score_details=s.get('score_details'),
                volume_ratio=s.get('volume_ratio'),
                themes=s.get('themes', [])
            )
            signals.append(signal_obj)
            
        # ScreenerResult 복원
        res_date_val = file_data.get('date', '')
        if 'T' in res_date_val:
             res_date = datetime.fromisoformat(res_date_val).date()
        else:
            try:
                res_date = datetime.strptime(res_date_val, '%Y-%m-%d').date()
            except:
                res_date = datetime.now().date()
            
        result = ScreenerResult(
            date=res_date,
            total_candidates=file_data.get('total_candidates', 0),
            filtered_count=file_data.get('filtered_count', 0),
            scanned_count=file_data.get('scanned_count', 0),
            signals=signals,
            by_grade=file_data.get('by_grade', {}),
            by_market=file_data.get('by_market', {}),
            processing_time_ms=file_data.get('processing_time_ms', 0),
            market_status=file_data.get('market_status'),
            market_summary=file_data.get('market_summary', ""),
            trending_themes=file_data.get('trending_themes', [])
        )
        
        # 3. 메시지 발송
        messenger = Messenger()
        messenger.send_screener_result(result)
        
        return jsonify({
            'status': 'success', 
            'message': f'메시지 발송 요청 완료 ({len(signals)}개 종목)',
            'target_date': str(res_date)
        })
        
    except Exception as e:
        logger.error(f"Message resend failed: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@kr_bp.route('/reanalyze/gemini', methods=['POST'])
def reanalyze_gemini():
    """
    [AI] 기존 시그널 대상 Gemini 심층 재분석 (사용자 요청 기반)
    * 정책:
      - 개인 키 있음: 무제한
      - 개인 키 없음: 10회 제한 (usage_tracker)
    """
    try:
        from flask import g
        from services.usage_tracker import usage_tracker

        user_api_key = g.get('user_api_key')
        user_email = g.get('user_email')

        # 1. 권한/한도 체크
        if not user_api_key:
            if not user_email:
                # 로그인 안 함
                return jsonify({'status': 'error', 'code': 'UNAUTHORIZED', 'message': '로그인이 필요합니다.'}), 401
            
            # 무료 사용량 체크
            allowed = usage_tracker.check_and_increment(user_email)
            if not allowed:
                return jsonify({
                    'status': 'error', 
                    'code': 'LIMIT_EXCEEDED', 
                    'message': '무료 AI 분석 횟수(10회)를 모두 소진했습니다. 개인 API Key를 설정해주세요.'
                }), 402 # Payment Required

        # 2. 데이터 로드
        data = request.get_json(silent=True) or {}
        target_dates = data.get('target_dates', []) # List of strings 'YYYY-MM-DD'
        
        # 날짜 지정 없으면 최신 날짜
        if not target_dates:
             # Load latest log to find date? or just today
             pass 

        # (기존 로직 유지)
        import sys
        import os
        scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts')
        if scripts_dir not in sys.path:
             sys.path.insert(0, scripts_dir)
             
        from engine.llm_analyzer import LLMAnalyzer
        
        # [중요] 개인 키 주입 (없으면 None -> Config 공용 키 사용)
        analyzer = LLMAnalyzer(api_key=user_api_key)
        
        if not analyzer.client:
             return jsonify({'status': 'error', 'message': 'AI 엔진 초기화 실패'}), 500

        # ... (이하 로직은 analyzer 인스턴스를 사용하므로, 
        # 기존 코드에서 `LLMAnalyzer()` 호출하는 부분을 `analyzer` 재사용하도록 수정해야 함)
        # 현재는 이 함수 내에서 직접 LLMAnalyzer를 새로 생성해서 쓰는 구조가 아니라
        # init_data 모듈의 함수(create_kr_ai_analysis)를 호출하는 구조임.
        # 따라서 init_data 쪽 함수도 api_key를 인자로 받도록 수정하거나, 
        # 여기서 직접 구현해야 함. 
        # ==> *전략 수정*: 여기서 직접 구현하는 것이 깔끔함 (Controller Logic)
        
        from engine.models import StockData, SupplyData
        from engine.market_gate import MarketGate
        
        # ... (분석 로직 구현 생략 - 너무 길어지므로 핵심만)
        # 기존 init_data.create_kr_ai_analysis는 "배치 작업용"이라 공용키를 씀.
        # 여기서는 "사용자 요청"이므로 직접 처리.
        
        # 간소화: 기존 로직 호출하되, LLMAnalyzer만 교체 가능한 구조가 아님.
        # -> init_data 모듈 수정 대신, 여기서 필요한 로직을 수행.
        
        logger.info(f"Gemini Re-analysis triggered by user (Key provided: {bool(user_api_key)})")
        
        # ... (기존 코드의 데이터 로딩 및 분석 재구성 필요)
        # 시간 관계상, init_data의 함수를 호출하되, 
        # init_data.py를 수정하여 api_key를 받을 수 있게 하는 것이 효율적임.
        
        from init_data import create_kr_ai_analysis_with_key
        
        result = create_kr_ai_analysis_with_key(target_dates, api_key=user_api_key)
        
        updated_count = result.get('count', 0)
        chunks = [] # Dummy for compat 
        
        if 'chunks' in result:
            chunks_info = f"{len(result['chunks'])} chunks processed"
            logger.info(f"Gemini re-analysis completed: {chunks_info}")
            
        return jsonify({
            'status': 'success',
            'message': f'{updated_count}개 종목의 Gemini 배치 분석이 완료되었습니다.'
        })
        
    except ImportError as e:
        return jsonify({'status': 'error', 'error': f'LLM 모듈 로드 실패: {e}'}), 500
    except Exception as e:
        print(f"Error reanalyzing gemini: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500

@kr_bp.route('/refresh', methods=['POST'])
def refresh_kr_data():
    """KR 데이터 전체 갱신 (Market Gate + AI Analysis) - Background Async"""
    try:
        req_data = request.get_json() or {}
        target_date = req_data.get('target_date', None)
        
        # 1. Use background update mechanism from common
        from .common import load_update_status, start_update, run_background_update
        from threading import Thread
        
        # Check running status
        status = load_update_status()
        if status.get('isRunning', False):
             return jsonify({'status': 'error', 'message': 'Update already in progress'}), 409
             
        # Define items to update
        items_list = ['Market Gate', 'AI Analysis']
        
        # Start update
        start_update(items_list)
        
        thread = Thread(target=run_background_update, args=(target_date, items_list))
        thread.daemon = True
        thread.start()
        
        logger.info("Data refresh started in background")
        
        return jsonify({
            'status': 'started',
            'message': '데이터 갱신 작업이 백그라운드에서 시작되었습니다.',
            'items': items_list
        })
        
    except Exception as e:
        logger.error(f"Refresh start failed: {e}")
        return jsonify({
            'status': 'error',
            'message': f'데이터 갱신 시작 실패: {str(e)}'
        }), 500


@kr_bp.route('/init-data', methods=['POST'])
def init_data_endpoint():
    """개별 데이터 초기화 API - Background Async"""
    try:
        req_data = request.get_json() or {}
        data_type = req_data.get('type', 'all')
        target_date = req_data.get('target_date', None)  # 날짜 지정 (YYYY-MM-DD)
        
        # 1. Map type to common items
        items_map = {
            'prices': ['Daily Prices'],
            'institutional': ['Institutional Trend'],
            'signals': ['VCP Signals'],
            'all': ['Daily Prices', 'Institutional Trend', 'VCP Signals']
        }
        
        items_list = items_map.get(data_type, [])
        if not items_list:
            return jsonify({'status': 'error', 'message': f'Unknown data type: {data_type}'}), 400
            
        # 2. Use background update mechanism
        from .common import load_update_status, start_update, run_background_update
        from threading import Thread
        
        # Check running status
        status = load_update_status()
        if status.get('isRunning', False):
             return jsonify({'status': 'error', 'message': 'Update already in progress'}), 409
             
        # Start update
        start_update(items_list)
        
        thread = Thread(target=run_background_update, args=(target_date, items_list))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Init data started in background: {data_type}")
        return jsonify({
            'status': 'started', 
            'type': data_type, 
            'target_date': target_date,
            'message': f'{data_type} 업데이트가 백그라운드에서 시작되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"Init data start failed: {e}")
        return jsonify({
            'status': 'error',
            'message': f'데이터 초기화 시작 실패: {str(e)}'
        }), 500

@kr_bp.route('/status', methods=['GET'])
def get_data_status():
    """데이터 수집 상태 확인"""
    try:
        status = {
            'last_update': None,
            'collected_stocks': 0,
            'signals_count': 0,
            'market_status': 'UNKNOWN',
            'files': {}
        }
        
        # 파일 상태 확인
        files = {
            'stocks': 'korean_stocks_list.csv',
            'prices': 'daily_prices.csv',
            'signals': 'signals_log.csv',
            'market_gate': 'market_gate.json',
            'jongga': 'jongga_v2_latest.json'
        }
        
        for key, filename in files.items():
            filepath = get_data_path(filename)
            if os.path.exists(filepath):
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                status['files'][key] = {
                    'exists': True,
                    'updated_at': mtime.isoformat(),
                    'size': os.path.getsize(filepath)
                }
                
                # 가장 최근 파일 수정 시간을 전체 업데이트 시간으로 간주
                if status['last_update'] is None or mtime > datetime.fromisoformat(status['last_update']):
                    status['last_update'] = mtime.isoformat()
            else:
                status['files'][key] = {'exists': False}
        
        # 데이터 카운트 (가능한 경우)
        try:
            stocks_df = load_csv_file('korean_stocks_list.csv')
            if not stocks_df.empty:
                status['collected_stocks'] = len(stocks_df)
                
            signals_df = load_csv_file('signals_log.csv')
            if not signals_df.empty:
                status['signals_count'] = len(signals_df)
                
            gate_data = load_json_file('market_gate.json')
            if gate_data:
                status['market_status'] = gate_data.get('status', 'UNKNOWN')
                
        except Exception:
            pass
            
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@kr_bp.route('/backtest-summary')
def get_backtest_summary():
    """백테스팅 결과 요약 (VCP + Closing Bet) - Dynamic Calculation"""
    try:
        candidates = []
        latest_payload = load_json_file("jongga_v2_latest.json")
        if isinstance(latest_payload, dict) and isinstance(latest_payload.get("signals"), list):
            candidates = latest_payload.get("signals", [])

        try:
            price_df_full, price_map = _load_backtest_price_snapshot()
        except Exception as e:
            logger.error(f"Backtest price loading failed: {e}")
            price_df_full, price_map = pd.DataFrame(), {}

        jb_stats = {
            "status": "Accumulating",
            "count": 0,
            "win_rate": 0,
            "avg_return": 0,
            "candidates": candidates,
        }
        try:
            history_payloads = [payload for _, payload in _load_jongga_result_payloads(limit=30)]
            jb_stats = _calculate_jongga_backtest_stats(
                candidates,
                history_payloads,
                price_map,
                price_df_full,
            )
        except Exception as e:
            logger.error(f"Closing Bet Stat Calc Failed: {e}")

        vcp_stats = {
            "status": "Accumulating",
            "count": 0,
            "win_rate": 0,
            "avg_return": 0,
        }
        try:
            vcp_df = load_csv_file("signals_log.csv")
            vcp_stats = _calculate_vcp_backtest_stats(vcp_df, price_map, price_df_full)
        except Exception as e:
            logger.error(f"VCP Stat Calc Failed: {e}")

        return jsonify({"vcp": vcp_stats, "closing_bet": jb_stats})

    except Exception as e:
        logger.error(f"Backtest Summary Error: {e}")
        return jsonify({'error': str(e)}), 500

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


@kr_bp.route('/stock-detail/<ticker>')
def get_stock_detail(ticker):
    """
    종목 상세 정보 조회 API (토스증권 데이터)
    - 코스피/코스닥 여부
    - 시세 정보 (현재가, 전일가, 고가, 저가, 52주 범위)
    - 투자 지표 (PER, PBR, ROE, PSR, EPS, BPS, 배당수익률, 시가총액)
    - 투자자 동향 (외국인, 기관, 개인)
    - 재무 정보 (매출, 영업이익, 순이익)
    - 안정성 지표 (부채비율, 유동비율)
    """
    try:
        ticker_padded = str(ticker).zfill(6)
        
        # TossCollector 사용 시도
        try:
            from engine.toss_collector import TossCollector
            
            collector = TossCollector()
            toss_data = collector.get_full_stock_detail(ticker_padded)
            
            if toss_data and toss_data.get('name'):
                # 토스증권 응답을 프론트엔드 형식으로 변환
                price = toss_data.get('price', {})
                indicators = toss_data.get('indicators', {})
                investor_trend = toss_data.get('investor_trend', {})
                financials = toss_data.get('financials', {})
                stability = toss_data.get('stability', {})
                
                # 마켓 정보 변환 (코스피 -> KOSPI)
                market = toss_data.get('market', 'UNKNOWN')
                if market == '코스피':
                    market = 'KOSPI'
                elif market == '코스닥':
                    market = 'KOSDAQ'
                
                result = {
                    'code': ticker_padded,
                    'name': toss_data.get('name', ''),
                    'market': market,
                    'priceInfo': {
                        'current': price.get('current', 0),
                        'prevClose': price.get('prev_close', 0),
                        'open': price.get('open', 0),
                        'high': price.get('high', 0),
                        'low': price.get('low', 0),
                        'change': price.get('current', 0) - price.get('prev_close', 0),
                        'change_pct': ((price.get('current', 0) - price.get('prev_close', 0)) / price.get('prev_close', 1) * 100) if price.get('prev_close', 0) else 0,
                        'volume': price.get('volume', 0),
                        'trading_value': price.get('trading_value', 0),
                    },
                    'yearRange': {
                        'high_52w': price.get('high_52w', 0),
                        'low_52w': price.get('low_52w', 0),
                    },
                    'indicators': {
                        'marketCap': price.get('market_cap', 0),
                        'per': indicators.get('per', 0),
                        'pbr': indicators.get('pbr', 0),
                        'eps': indicators.get('eps', 0),
                        'bps': indicators.get('bps', 0),
                        'dividendYield': indicators.get('dividend_yield', 0),
                        'roe': indicators.get('roe', 0),
                        'psr': indicators.get('psr', 0),
                    },
                    'investorTrend': {
                        'foreign': investor_trend.get('foreign', 0),
                        'institution': investor_trend.get('institution', 0),
                        'individual': investor_trend.get('individual', 0),
                    },
                    'financials': {
                        'revenue': financials.get('revenue', 0),
                        'operatingProfit': financials.get('operating_profit', 0),
                        'netIncome': financials.get('net_income', 0),
                    },
                    'safety': {
                        'debtRatio': stability.get('debt_ratio', 0),
                        'currentRatio': stability.get('current_ratio', 0),
                    },
                }
                
                # 5일 누적 수급 데이터 추가 (종가베팅 로직과 동일)
                try:
                    trend_df = load_csv_file('all_institutional_trend_data.csv')
                    if not trend_df.empty:
                        trend_code = str(ticker_padded)
                        if 'ticker' in trend_df.columns:
                            filtered = trend_df[trend_df['ticker'].astype(str).str.zfill(6) == trend_code]
                            if not filtered.empty:
                                recent_5 = filtered.tail(5)
                                foreign_net_5 = int(recent_5['foreign_buy'].sum())
                                inst_net_5 = int(recent_5['inst_buy'].sum())
                                
                                result['investorTrend5Day'] = {
                                    'foreign': foreign_net_5,
                                    'institution': inst_net_5
                                }
                except Exception as e:
                    logger.warning(f"Failed to calculate 5-day trend for {ticker}: {e}")

                return jsonify(result)
        except Exception as e:
            logger.warning(f"TossCollector 실패, NaverFinanceCollector로 폴백: {e}")
        
        # 폴백: NaverFinanceCollector
        try:
            import asyncio
            from engine.collectors import NaverFinanceCollector
            
            collector = NaverFinanceCollector()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                detail_info = loop.run_until_complete(
                    collector.get_stock_detail_info(ticker_padded)
                )
                financials = loop.run_until_complete(
                    collector.get_financials(ticker_padded)
                )
            finally:
                loop.close()
            
            if detail_info:
                detail_info['financials'] = financials
                return jsonify(detail_info)
                
        except ImportError as e:
            logger.warning(f"NaverFinanceCollector import 실패: {e}")
            # 폴백: 기본 정보만 반환
            return jsonify({
                'code': ticker_padded,
                'name': f'종목 {ticker_padded}',
                'market': 'UNKNOWN',
                'priceInfo': {
                    'current': 0,
                    'prevClose': 0,
                    'high': 0,
                    'low': 0,
                },
                'yearRange': {
                    'high_52w': 0,
                    'low_52w': 0,
                },
                'indicators': {
                    'marketCap': 0,
                    'per': 0,
                    'pbr': 0,
                },
                'investorTrend': {
                    'foreign': 0,
                    'institution': 0,
                    'individual': 0,
                },
                'financials': {
                    'revenue': 0,
                    'operatingProfit': 0,
                    'netIncome': 0,
                },
                'safety': {
                    'debtRatio': 0,
                    'currentRatio': 0,
                },
                'message': 'NaverFinanceCollector를 사용할 수 없어 기본 데이터를 반환합니다.'
            })

    except Exception as e:
        logger.error(f"Error getting stock detail for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# Chatbot API Endpoints
# ============================================================

@kr_bp.route('/chatbot/welcome', methods=['GET'])
def kr_chatbot_welcome():
    """챗봇 웰컴 메시지"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        msg = bot.get_welcome_message()
        return jsonify({'message': msg})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/chatbot/sessions', methods=['GET', 'POST'])
def kr_chatbot_sessions():
    """챗봇 세션 관리"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        
        # [Fix] Owner Isolation
        user_email = request.headers.get('X-User-Email')
        session_id_header = request.headers.get('X-Session-Id')
        owner_id = user_email if (user_email and user_email != 'user@example.com') else session_id_header

        if request.method == 'GET':
            # List all sessions (Filtered by owner)
            sessions = bot.history.get_all_sessions(owner_id=owner_id)
            return jsonify({'sessions': sessions})
            
        elif request.method == 'POST':
            # Create new session
            data = request.get_json() or {}
            model_name = data.get('model', None)
            session_id = bot.history.create_session(model_name=model_name, owner_id=owner_id)
            return jsonify({'session_id': session_id, 'message': 'New session created'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/chatbot', methods=['POST'])
def kr_chatbot():
    """KR 챗봇 (멀티모달 + 세션 지원 + API Key/Quota 연동)"""
    try:
        from chatbot import get_chatbot
        
        # [Auth & Quota Logic]
        # 1. API Key & Session Check
        user_api_key = request.headers.get('X-Gemini-Key')
        user_email = request.headers.get('X-User-Email')
        session_id = request.headers.get('X-Session-Id')  # 브라우저 고유 세션 ID
        
        if user_api_key:
            user_api_key = user_api_key.strip()

        use_free_tier = False
        # 사용량 추적 키: 로그인한 경우 이메일, 아니면 세션 ID 사용
        is_authenticated = user_email and user_email != 'user@example.com'
        usage_key = user_email if is_authenticated else session_id

        if not user_api_key:
            # Key 미제공 시 - 세션 ID 또는 이메일 기반으로 무료 티어 제공
            if not usage_key:
                 return jsonify({'error': '세션 정보가 없습니다. 페이지를 새로고침 해주세요.', 'code': 'SESSION_REQUIRED'}), 400
            
            # 무료 티어(Server Key) 가용성 체크
            from engine.config import app_config
            server_key_available = bool(app_config.GOOGLE_API_KEY or app_config.ZAI_API_KEY)
             
            if not server_key_available:
                 return jsonify({'error': '시스템 API Key가 설정되지 않았습니다.', 'code': 'SERVER_CONFIG_MISSING'}), 503

            # 쿼터 확인 (이메일 또는 세션 ID 기준)
            used = get_user_usage(usage_key)
            if used >= MAX_FREE_USAGE:
                 return jsonify({'error': '무료 사용량(10회)을 초과했습니다. [설정 > API]에서 개인 API Key를 등록해주세요.', 'code': 'QUOTA_EXCEEDED'}), 402
            
            use_free_tier = True

        # 2. Parameters Parsing (JSON or Multipart)
        message = ""
        model_name = None
        # Use header_session_id safely retrieved above as default 
        parsed_session_id = session_id 
        persona = None
        watchlist = None
        files = []

        # Handle Multipart/Form-Data (File Uploads)
        if request.content_type and 'multipart/form-data' in request.content_type:
            message = request.form.get('message', '')
            model_name = request.form.get('model', None)
            parsed_session_id = request.form.get('session_id', parsed_session_id)
            persona = request.form.get('persona', None)
            
            watchlist_str = request.form.get('watchlist', None)
            if watchlist_str:
                try:
                    import json
                    watchlist = json.loads(watchlist_str)
                except:
                    pass
            
            if 'file' in request.files:
                uploaded_files = request.files.getlist('file')
                for file in uploaded_files:
                    if file.filename == '':
                        continue
                    
                    file_content = file.read()
                    mime_type = file.content_type
                    
                    files.append({
                        "mime_type": mime_type,
                        "data": file_content
                    })
        
        # Handle JSON (Text Only)
        else:
            data = request.get_json() or {}
            message = data.get('message', '')
            model_name = data.get('model', None)
            parsed_session_id = data.get('session_id', parsed_session_id)
            persona = data.get('persona', None)
            watchlist = data.get('watchlist', None)
        
        bot = get_chatbot()

        from flask import Response, stream_with_context
        import json

        def generate():
            full_response = ""
            usage_metadata = {}
            for chunk in bot.chat_stream(
                message, 
                session_id=parsed_session_id, 
                model=model_name, 
                files=files if files else None, 
                watchlist=watchlist,
                persona=persona,
                api_key=user_api_key,
                owner_id=usage_key
            ):
                if "chunk" in chunk:
                    full_response += chunk["chunk"]
                if "usage_metadata" in chunk:
                    usage_metadata = chunk["usage_metadata"]
                
                # Server-Sent Events format
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # [Log] Chat Activity after streaming completes
            try:
                from services.activity_logger import activity_logger
                ua_string = request.user_agent.string
                device_type = 'WEB'
                if request.user_agent.platform in ('android', 'iphone', 'ipad') or 'Mobile' in ua_string:
                    device_type = 'MOBILE'

                real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if real_ip and ',' in real_ip:
                    real_ip = real_ip.split(',')[0].strip()

                activity_logger.log_action(
                    user_id=usage_key,
                    action='CHAT_MESSAGE',
                    details={
                        'session_id': session_id,
                        'model': model_name,
                        'user_message': message[:2000] if message else "",
                        'bot_response': full_response[:2000] if full_response else "",
                        'token_usage': usage_metadata,
                        'has_files': bool(files),
                        'device': device_type,
                        'user_agent': ua_string[:150]
                    },
                    ip_address=real_ip
                )
            except Exception as e:
                logger.error(f"[{usage_key}] Chat log error: {e}")

        response = Response(stream_with_context(generate()), content_type='text/event-stream')
        # Prevent proxy buffering so SSE chunks are delivered immediately.
        response.headers['Cache-Control'] = 'no-cache, no-transform'
        response.headers['X-Accel-Buffering'] = 'no'
        response.headers['Connection'] = 'keep-alive'
        return response

        # 3. Quota Update (If Free Tier & Success)
        if use_free_tier:
             # 에러가 아니고, 경고 메시지(⚠️)가 아닐 때만 차감
             resp_text = response_data.get('response', '')
             has_error = response_data.get('error')
             starts_with_warning = str(resp_text).startswith('⚠️')
             logger.info(f"[QUOTA] use_free_tier={use_free_tier}, has_error={has_error}, starts_with_warning={starts_with_warning}, usage_key={usage_key}")
             
             if not has_error and not starts_with_warning:
                 new_usage = increment_user_usage(usage_key)
                 logger.info(f"[QUOTA] 사용량 차감 완료: {usage_key} -> {new_usage}회")
             else:
                 logger.info(f"[QUOTA] 차감 스킵: error={has_error}, warning={starts_with_warning}")
        
        return jsonify(response_data)
             
    except Exception as e:
        logger.error(f"[{usage_key}] Chatbot API Error: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/chatbot/models', methods=['GET'])
def kr_chatbot_models():
    """사용 가능 모델 목록"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        models = bot.get_available_models()
        current = bot.current_model_name
        return jsonify({'models': models, 'current': current})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/chatbot/suggestions', methods=['GET'])
def kr_chatbot_suggestions():
    """AI 기반 동적 추천 질문 생성"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        
        # 관심종목 파라미터 (comma separated)
        watchlist_param = request.args.get('watchlist')
        watchlist = [w.strip() for w in watchlist_param.split(',')] if watchlist_param else None
        
        # 페르소나 파라미터
        persona = request.args.get('persona')

        suggestions = bot.get_daily_suggestions(watchlist=watchlist, persona=persona)
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        logger.error(f"Suggestions API Error: {e}")
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/chatbot/history', methods=['GET', 'DELETE'])
def kr_chatbot_history():
    """챗봇 히스토리 (세션별)"""
    try:
        from chatbot import get_chatbot
        
        bot = get_chatbot()
        session_id = request.args.get('session_id')
        
        if request.method == 'GET':
            if session_id:
                history = bot.history.get_messages(session_id)
                return jsonify({'history': history})
            else:
                return jsonify({'history': []}) # Should call /sessions for list
                
        elif request.method == 'DELETE':
            if session_id == 'all':
                bot.history.clear_all()
                return jsonify({'status': 'cleared all'})
            elif session_id:
                msg_index_str = request.args.get('index')
                if msg_index_str is not None:
                    try:
                        msg_index = int(msg_index_str)
                        success = bot.history.delete_message(session_id, msg_index)
                        if success:
                            return jsonify({'status': 'deleted message'})
                        else:
                            return jsonify({'error': 'Message not found'}), 404
                    except ValueError:
                        return jsonify({'error': 'Invalid index format'}), 400
                else:
                    bot.history.delete_session(session_id)
                    return jsonify({'status': 'deleted session'})
            else:
                return jsonify({'error': 'Missing session_id'}), 400
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/chatbot/profile', methods=['GET', 'POST'])
def kr_chatbot_profile():
    """사용자 프로필 설정"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        
        if request.method == 'GET':
            profile = bot.get_user_profile()
            return jsonify({'profile': profile})
            
        elif request.method == 'POST':
            data = request.get_json() or {}
            name = data.get('name')
            persona = data.get('persona')
            
            if not name:
                return jsonify({'error': 'Name is required'}), 400
                
            updated = bot.update_user_profile(name, persona)
            return jsonify({'message': 'Profile updated', 'profile': updated})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/config/interval', methods=['GET', 'POST'])
def handle_config_interval():
    """매크로 지표 업데이트 주기 설정 (GET/POST)"""
    # .env 파일 경로 찾기
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    
    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            interval = int(data.get('interval', 30))
            
            if interval < 1 or interval > 1440:
                return jsonify({'error': 'Interval must be between 1 and 1440 minutes'}), 400
                
            # 1. 스케줄러 업데이트
            try:
                from services import scheduler
                scheduler.update_market_gate_interval(interval)
            except ImportError:
                logger.warning("Scheduler module not found, skipping runtime update")
            except Exception as e:
                logger.error(f"Scheduler update failed: {e}")

            # 2. 메모리 설정 업데이트
            from engine.config import app_config
            app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES = interval
            
            # 3. .env 파일 업데이트 (영구 저장)
            if os.path.exists(env_path):
                import re
                with open(env_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 정규식으로 기존 설정 교체 또는 추가
                pattern = r"^MARKET_GATE_UPDATE_INTERVAL_MINUTES=\d+"
                new_line = f"MARKET_GATE_UPDATE_INTERVAL_MINUTES={interval}"
                
                if re.search(pattern, content, re.MULTILINE):
                    content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
                else:
                    content += f"\n{new_line}"
                    
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return jsonify({
                'status': 'success', 
                'interval': interval,
                'message': f'Update interval set to {interval} minutes'
            })
            
        except Exception as e:
            logger.error(f"Failed to update interval: {e}")
            return jsonify({'error': str(e)}), 500

    else:  # GET
        try:
            from engine.config import app_config
            return jsonify({'interval': app_config.MARKET_GATE_UPDATE_INTERVAL_MINUTES})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# ==============================================================================
# Chatbot & Quota Routes (Free Tier Logic)
# ==============================================================================

QUOTA_FILE = os.path.join(DATA_DIR, 'user_quota.json')
MAX_FREE_USAGE = 10

def get_user_usage(email):
    """사용자 사용량 조회"""
    data = load_json_file('user_quota.json')
    return data.get(email, 0)

def increment_user_usage(email):
    """사용자 사용량 증가"""
    data = load_json_file('user_quota.json')
    current = data.get(email, 0)
    data[email] = current + 1
    
    with open(QUOTA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return current + 1

@kr_bp.route('/user/quota')
def get_user_quota_info():
    """사용자 쿼터 정보 반환 (이메일 또는 세션 ID 기반)"""
    try:
        user_email = request.args.get('email') or request.headers.get('X-User-Email')
        session_id = request.args.get('session_id') or request.headers.get('X-Session-Id')
        
        # 로그인한 경우 이메일, 아니면 세션 ID 사용
        is_authenticated = user_email and user_email != 'user@example.com'
        usage_key = user_email if is_authenticated else session_id
        
        if not usage_key:
            return jsonify({'usage': 0, 'limit': MAX_FREE_USAGE, 'remaining': MAX_FREE_USAGE, 'message': '무료 10회 사용 가능'})
            
        used = get_user_usage(usage_key)
        remaining = max(0, MAX_FREE_USAGE - used)
        
        # Check Server Key Availability
        from engine.config import app_config
        server_key_available = bool(app_config.GOOGLE_API_KEY or app_config.ZAI_API_KEY)

        return jsonify({
            'usage': used,
            'limit': MAX_FREE_USAGE,
            'remaining': remaining,
            'is_exhausted': used >= MAX_FREE_USAGE,
            'server_key_configured': server_key_available
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/user/quota/recharge', methods=['POST'])
def recharge_user_quota():
    """무료 사용량 5회 충전"""
    try:
        data = request.get_json() or {}
        user_email = data.get('email') or request.headers.get('X-User-Email')
        session_id = data.get('session_id') or request.headers.get('X-Session-Id')
        
        # 로그인한 경우 이메일, 아니면 세션 ID 사용
        is_authenticated = user_email and user_email != 'user@example.com'
        usage_key = user_email if is_authenticated else session_id
        
        if not usage_key:
            return jsonify({'error': '세션 정보가 없습니다.'}), 400
        
        # 현재 사용량 조회 후 5회 차감 (최소 0)
        quota_data = load_json_file('user_quota.json')
        current_usage = quota_data.get(usage_key, 0)
        new_usage = max(0, current_usage - 5)
        quota_data[usage_key] = new_usage
        
        with open(QUOTA_FILE, 'w', encoding='utf-8') as f:
            json.dump(quota_data, f, indent=2)
        
        remaining = max(0, MAX_FREE_USAGE - new_usage)
        
        return jsonify({
            'status': 'success',
            'usage': new_usage,
            'limit': MAX_FREE_USAGE,
            'remaining': remaining,
            'message': f'5회 충전 완료! (남은 횟수: {remaining}회)'
        })
    except Exception as e:
        logger.error(f"Recharge quota error: {e}")
        return jsonify({'error': str(e)}), 500



@kr_bp.route('/chatbot/history', methods=['DELETE'])
def clear_chat_history():
    """대화 기록 초기화"""
    try:
        from chatbot import get_chatbot
        bot = get_chatbot()
        bot.history.clear_all()
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
