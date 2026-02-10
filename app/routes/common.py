#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공통 API 라우트
"""
from flask import Blueprint, jsonify, request
import pandas as pd
import os
import json
import logging
import logging
import random
import threading
import sys
from datetime import datetime
from threading import Lock, Thread
import traceback
import re

# Add scripts directory to path for importing init_data
scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'scripts')
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

logger = logging.getLogger(__name__)

common_bp = Blueprint('common', __name__)


# ====== ADMIN 권한 확인 API ======
@common_bp.route('/admin/check')
def check_admin():
    """
    ADMIN 권한 확인 API
    - 이메일이 ADMIN_EMAILS 환경변수에 포함되어 있는지 확인
    - 프론트엔드의 useAdmin 훅에서 호출
    """
    email = request.args.get('email', '').strip().lower()
    
    if not email:
        return jsonify({'isAdmin': False, 'error': 'Email required'}), 400

    # 환경변수에서 ADMIN 이메일 목록 로드
    admin_emails_str = os.environ.get('ADMIN_EMAILS', '')
    admin_emails = [e.strip().lower() for e in admin_emails_str.split(',') if e.strip()]
    
    is_admin = email in admin_emails
    
    logger.debug(f"Admin check: {email} -> {is_admin}")
    
    return jsonify({'isAdmin': is_admin})


try:
    import engine.shared as shared_state
except ImportError:
    # Fallback if engine package not found in path
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import engine.shared as shared_state

from services.paper_trading import paper_trading

# Status File Path
UPDATE_STATUS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'update_status.json')
update_lock = Lock()

def load_update_status():
    """상태 파일 로드"""
    default_status = {
        'isRunning': False,
        'startTime': None,
        'currentItem': None,
        'items': []
    }
    
    if os.path.exists(UPDATE_STATUS_FILE):
        try:
            with open(UPDATE_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load update status: {e}")
            return default_status
    return default_status

def save_update_status(status):
    """상태 파일 저장 (Atomic Write)"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(UPDATE_STATUS_FILE), exist_ok=True)
        
        # Write to temp file first
        tmp_file = UPDATE_STATUS_FILE + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno()) # Ensure write to disk
            
        # Atomic replace
        os.replace(tmp_file, UPDATE_STATUS_FILE)
            
    except Exception as e:
        logger.error(f"Failed to save update status: {e}")

def start_update(items_list):
    """업데이트 시작"""
    with update_lock:
        shared_state.STOP_REQUESTED = False
        status = load_update_status()
        status['isRunning'] = True
        status['startTime'] = datetime.now().isoformat()
        status['items'] = [{'name': name, 'status': 'pending'} for name in items_list]
        status['currentItem'] = None
        save_update_status(status)

def update_item_status(name, status_code):
    """아이템 상태 업데이트"""
    with update_lock:
        status = load_update_status()
        for item in status['items']:
            if item['name'] == name:
                item['status'] = status_code
                if status_code == 'running':
                    status['currentItem'] = name
                break
        save_update_status(status)

def stop_update():
    """업데이트 중단"""
    with update_lock:
        shared_state.STOP_REQUESTED = True
        status = load_update_status()
        status['isRunning'] = False
        status['currentItem'] = None
        
        # 명시적으로 실행 중인 항목을 error/stopped로 변경
        for item in status['items']:
            if item['status'] == 'running':
                # 사용자가 중지했으므로 'error'보다는 'stopped'가 맞음 (또는 UI가 인식하는 실패 코드로)
                item['status'] = 'error' 
            elif item['status'] == 'pending':
                item['status'] = 'cancelled' # 대기 중인 건 취소됨 -> UI에서 멈춤 처리
        
        # [사용자 요청] 깔끔하게 중지되고 UI가 처음 시작하기 전으로 초기화
        # 하지만 상태 확인을 위해 items는 남겨두되, cancelled 처리된 것은 UI가 알아서 처리해야 함.
        # 만약 "완전 초기화"를 원한다면 status['items'] = [] 할 수도 있지만, 
        # 직전 실패 내역은 보여주는 게 UX상 나을 수 있음. 일단 상태 코드 변경으로 대응.
        
        save_update_status(status)

def finish_update():
    """업데이트 완료"""
    with update_lock:
        status = load_update_status()
        status['isRunning'] = False
        status['currentItem'] = None
        # 완료 시 items를 남겨두어 UI에서 결과를 확인할 수 있게 함 (다음 start 시 초기화됨)
        # status['items'] = [] 
        save_update_status(status)

@common_bp.route('/system/update-status')
def get_update_status():
    """업데이트 상태만 조회 (가벼운 폴링용)"""
    # 읽기 시에는 Lock을 걸지 않아도 무방 (파일 시스템 원자성 의존)
    # 다만 쓰기와 겹치면 빈 파일 읽을 수 있으므로 Lock 사용 권장
    with update_lock:
        status = load_update_status()
        # DEBUG: 실제 파일 경로 확인용
        status['_debug_path'] = UPDATE_STATUS_FILE
        status['_debug_exists'] = os.path.exists(UPDATE_STATUS_FILE)
        return jsonify(status)


@common_bp.route('/system/start-update', methods=['POST'])
def api_start_update():
    """업데이트 시작 (백그라운드 실행)"""
    data = request.get_json() or {}
    items_list = data.get('items', [])
    target_date = data.get('target_date') # YYYY-MM-DD or None
    force = data.get('force', False) # Force update flag
    
    # 이미 실행 중이면 거부
    current_status = load_update_status()
    if current_status['isRunning']:
        return jsonify({'status': 'error', 'message': 'Already running'}), 400

    # UI 상태 초기화
    start_update(items_list)
    
    # 백그라운드 스레드 실행
    thread = Thread(target=run_background_update, args=(target_date, items_list, force))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'ok'})


def run_background_update(target_date, selected_items=None, force=False):
    """백그라운드에서 순차적으로 데이터 업데이트 실행"""
    import asyncio
    
    # Default to all items if not specified
    if selected_items is None:
        selected_items = ['Daily Prices', 'Institutional Trend', 'Market Gate', 'VCP Signals', 'AI Analysis', 'AI Jongga V2']

    try:
        from scripts import init_data

        # 1. Daily Prices
        if 'Daily Prices' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('Daily Prices', 'running')
            try:
                # Force parameter supported
                init_data.create_daily_prices(target_date, force=force)
                update_item_status('Daily Prices', 'done')
            except Exception as e:
                logger.error(f"Daily Prices Failed: {e}")
                update_item_status('Daily Prices', 'error')
                if shared_state.STOP_REQUESTED: raise e # 중단 요청이면 전체 중단
            
        # 2. Institutional Trend
        if 'Institutional Trend' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('Institutional Trend', 'running')
            try:
                # Force parameter supported
                init_data.create_institutional_trend(target_date, force=force)
                update_item_status('Institutional Trend', 'done')
            except Exception as e:
                logger.error(f"Institutional Trend Failed: {e}")
                update_item_status('Institutional Trend', 'error')
                if shared_state.STOP_REQUESTED: raise e

        # 2.5 Market Gate Analysis
        if 'Market Gate' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('Market Gate', 'running')
            try:
                from engine.market_gate import MarketGate
                mg = MarketGate()
                result = mg.analyze(target_date)
                mg.save_analysis(result, target_date)
                update_item_status('Market Gate', 'done')
            except Exception as e:
                logger.error(f"Market Gate Failed: {e}")
                update_item_status('Market Gate', 'error')
                if shared_state.STOP_REQUESTED: raise e

        # 3. VCP Signals
        if 'VCP Signals' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('VCP Signals', 'running')
            vcp_df = None
            try:
                # 1. 시그널 생성 (기존 로직)
                vcp_df = init_data.create_signals_log(target_date)
                
                # 2. [FIX] 기존 열린 시그널 성과 업데이트 (Tracker 연동)
                try:
                    from engine.signal_tracker import SignalTracker
                    tracker = SignalTracker()
                    tracker.update_open_signals()
                    logger.info("SignalTracker: Open signals updated")
                except Exception as tracker_e:
                    logger.warning(f"SignalTracker update failed (non-critical): {tracker_e}")
                
                update_item_status('VCP Signals', 'done')
            except Exception as e:
                logger.error(f"VCP Signals Failed: {e}")
                update_item_status('VCP Signals', 'error')
                if shared_state.STOP_REQUESTED: raise e

        # 4. AI Analysis
        if 'AI Analysis' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('AI Analysis', 'running')
            try:
                from engine.kr_ai_analyzer import KrAiAnalyzer
                import pandas as pd
                import json
                
                # 경로 설정
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                data_dir = os.path.join(base_dir, 'data')
                signals_path = os.path.join(data_dir, 'signals_log.csv')
                
                if os.path.exists(signals_path):
                    # 우선 메모리에 있는 vcp_df 사용 (실시간성 보장)
                    target_df = pd.DataFrame()
                    analysis_date = target_date if target_date else datetime.now().strftime('%Y-%m-%d')
                    
                    if 'VCP Signals' in selected_items and 'vcp_df' in locals() and vcp_df is not None and hasattr(vcp_df, 'empty') and not vcp_df.empty:
                        logger.info("VCP 결과 메모리에서 로드")
                        target_df = vcp_df.copy()
                        if 'signal_date' in target_df.columns:
                            analysis_date = str(target_df['signal_date'].iloc[0])
                    else:
                        logger.info("VCP 결과 파일에서 로드 시도")
                        df = pd.read_csv(signals_path)
                        if not df.empty and 'signal_date' in df.columns:
                            # 분석 날짜 결정
                            if not target_date:
                                analysis_date = str(df['signal_date'].max())
                                
                            # 해당 날짜 데이터 필터링
                            target_df = df[df['signal_date'].astype(str) == analysis_date].copy()
                    
                    if not target_df.empty:
                            # 티커 정규화 및 중복 제거 (분석 대상 확보)
                            target_df['ticker'] = target_df['ticker'].astype(str).str.zfill(6)
                            target_df = target_df.drop_duplicates(subset=['ticker'])
                            
                            # Score 숫자형 변환 (정렬 오류 방지)
                            if 'score' in target_df.columns:
                                target_df['score'] = pd.to_numeric(target_df['score'], errors='coerce').fillna(0)
                            
                            # 점수 높은 순 정렬 후 상위 20개 분석 (사용자 요청: 전체/다수 분석)
                            target_df = target_df.sort_values('score', ascending=False).head(20)
                            tickers = target_df['ticker'].tolist()
                            
                            # [사용자 요청] 재분석 시 해당 날짜의 기존 AI 결과 파일 삭제 (찌꺼기 데이터 방지)
                            date_str_clean = analysis_date.replace('-', '')
                            target_filename = f'ai_analysis_results_{date_str_clean}.json'
                            target_filepath = os.path.join(data_dir, target_filename)
                            
                            if os.path.exists(target_filepath):
                                try:
                                    os.remove(target_filepath)
                                    logger.info(f"기존 AI 분석 파일 삭제 완료: {target_filename}")
                                except Exception as del_err:
                                    logger.warning(f"기존 AI 파일 삭제 실패: {del_err}")

                            logger.info(f"AI 분석 시작: {len(tickers)} 종목 ({analysis_date})")
                            
                            analyzer = KrAiAnalyzer()
                            # 분석 실행
                            results = analyzer.analyze_multiple_stocks(tickers)
                            
                            # 메타데이터 추가
                            results['generated_at'] = datetime.now().isoformat()
                            results['signal_date'] = analysis_date
                            
                            # 2. 날짜별 파일 저장
                            date_str = analysis_date.replace('-', '')
                            filename = f'ai_analysis_results_{date_str}.json'
                            filepath = os.path.join(data_dir, filename)
                            
                            with open(filepath, 'w', encoding='utf-8') as f:
                                json.dump(results, f, ensure_ascii=False, indent=2)
                            logger.info(f"AI 분석 결과 저장 완료: {filepath}")
                                
                            # 3. 최신 결과 업데이트 (target_date가 없거나 오늘인 경우)
                            # 또는 사용자가 조회할 때 편의를 위해 항상 최신 파일도 갱신할지?
                            # -> 일단 target_date 모드일 때는 최신 파일 건드리지 않는 게 안전 (혼선 방지)
                            is_today = analysis_date == datetime.now().strftime('%Y-%m-%d')
                            if not target_date or is_today:
                                 main_path = os.path.join(data_dir, 'ai_analysis_results.json')
                                 with open(main_path, 'w', encoding='utf-8') as f:
                                    json.dump(results, f, ensure_ascii=False, indent=2)
                            
                            update_item_status('AI Analysis', 'done')
                    else:
                        logger.info(f"[{analysis_date}] 시그널 데이터가 없어 AI 분석 생략")
                        update_item_status('AI Analysis', 'done')

                else:
                    update_item_status('AI Analysis', 'done')

            except Exception as e:
                logger.error(f"AI Analysis Failed: {e}")
                update_item_status('AI Analysis', 'error')
                if shared_state.STOP_REQUESTED: raise e

        # 5. AI Jongga V2
        if 'AI Jongga V2' in selected_items:
            if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
            update_item_status('AI Jongga V2', 'running')
            try:
                # 비동기 실행을 위해 asyncio run
                # run_screener는 engine.generator에 정의됨
                from engine.generator import run_screener
                
                async def run_async_screener():
                    await run_screener(capital=50000000, target_date=target_date)
                    
                asyncio.run(run_async_screener())
                update_item_status('AI Jongga V2', 'done')
                
                # AI Analysis도 완료된 것으로 간주 (run_screener가 다 함)
                update_item_status('AI Analysis', 'done') 
                
            except Exception as e:
                logger.error(f"AI Jongga V2 Failed: {e}")
                update_item_status('AI Jongga V2', 'error')
                if shared_state.STOP_REQUESTED: raise e

    except Exception as e:
        if str(e) == "Stopped by user" or shared_state.STOP_REQUESTED:
            logger.info(f"Background Update Stopped: {e}")
        else:
            logger.error(f"Background Update Failed: {e}")
        # Stop Requested면 무시, 아니면 에러 로깅
    finally:
        finish_update()


@common_bp.route('/system/update-item-status', methods=['POST'])
def api_update_item_status():
    """아이템 상태 업데이트"""
    data = request.get_json() or {}
    name = data.get('name')
    status = data.get('status')
    if name and status:
        update_item_status(name, status)
    return jsonify({'status': 'ok'})


@common_bp.route('/system/finish-update', methods=['POST'])
def api_finish_update():
    """업데이트 완료"""
    finish_update()
    return jsonify({'status': 'ok'})


@common_bp.route('/system/stop-update', methods=['POST'])
def api_stop_update():
    """업데이트 중단 요청"""
    stop_update()
    return jsonify({'status': 'stopped'})


@common_bp.route('/system/log-event', methods=['POST'])
def api_log_event():
    """프론트엔드 이벤트 로깅 (Login, Profile Update 등)"""
    try:
        data = request.get_json() or {}
        action = data.get('action', 'FRONTEND_EVENT')
        details = data.get('details', {})
        
        # User ID extraction
        user_email = request.headers.get('X-User-Email')
        session_id = request.headers.get('X-Session-Id')
        user_id = user_email if (user_email and user_email != 'user@example.com') else session_id
        
        from services.activity_logger import activity_logger
        
        # Ensure session_id is in details
        if 'session_id' not in details and session_id:
            details['session_id'] = session_id
            
        activity_logger.log_action(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Event Log Error: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/portfolio')
def get_portfolio_data():
    """포트폴리오 데이터 (Fast - Cached)"""
    try:
        # Start sync if not running (Lazy Start)
        paper_trading.start_background_sync()
        
        data = paper_trading.get_portfolio_valuation()
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/portfolio/buy', methods=['POST'])
def buy_stock():
    """모의 투자 매수"""
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        name = data.get('name')
        price = data.get('price')
        quantity = int(data.get('quantity', 0))
        
        if not all([ticker, name, price, quantity]):
             return jsonify({'status': 'error', 'message': 'Missing data'}), 400
             
        result = paper_trading.buy_stock(ticker, name, float(price), quantity)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@common_bp.route('/portfolio/sell', methods=['POST'])
def sell_stock():
    """모의 투자 매도"""
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        price = data.get('price')
        quantity = int(data.get('quantity', 0))
        
        if not all([ticker, price, quantity]):
             return jsonify({'status': 'error', 'message': 'Missing data'}), 400
             
        result = paper_trading.sell_stock(ticker, float(price), quantity)
        return jsonify(result)
    except Exception as e:
         return jsonify({'status': 'error', 'message': str(e)}), 500


@common_bp.route('/portfolio/reset', methods=['POST'])
def reset_portfolio():
    """모의 투자 초기화"""
    paper_trading.reset_account()
    return jsonify({'status': 'success', 'message': 'Account reset to 100M KRW'})


@common_bp.route('/portfolio/deposit', methods=['POST'])
def deposit_cash():
    """예수금 충전"""
    try:
        data = request.get_json()
        amount = int(data.get('amount', 0))
        result = paper_trading.deposit_cash(amount)
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@common_bp.route('/portfolio/history')
def get_trade_history():
    """거래 내역 조회"""
    try:
        limit = request.args.get('limit', 50, type=int)
        data = paper_trading.get_trade_history(limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/portfolio/history/asset')
def get_asset_history():
    """자산 변동 내역 조회 (차트용)"""
    try:
        limit = request.args.get('limit', 30, type=int)
        data = paper_trading.get_asset_history(limit)
        return jsonify({'history': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@common_bp.route('/stock/<ticker>')
def get_stock_detail(ticker):
    """개별 종목 상세 정보"""
    try:
        # 샘플 종목 상세
        stock_names = {
            '005930': '삼성전자',
            '000270': '기아',
            '035420': 'NAVER',
            '005380': '현대차'
        }

        name = stock_names.get(ticker, '알 수 없는 종목')
        price = random.randint(50000, 150000)
        change = random.randint(-5000, 5000)
        change_pct = (change / price) * 100

        return jsonify({
            'ticker': ticker.zfill(6),
            'name': name,
            'sector': '기타',
            'price': price,
            'change': change,
            'change_pct': change_pct,
            'volume': random.randint(100000, 10000000),
            'market_cap': price * random.randint(100, 1000),
            'pe_ratio': round(random.uniform(5, 25), 2),
            'dividend_yield': round(random.uniform(0, 5), 2)
        })

    except Exception as e:
        logger.error(f"Error getting stock detail: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/realtime-prices', methods=['POST'])
def get_realtime_prices():
    """실시간 가격 조회"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', [])
        market = data.get('market', 'kr')

        if not tickers:
            return jsonify({'prices': {}})

        prices = {}
        for t in tickers:
            prices[str(t).zfill(6)] = random.randint(50000, 150000)

        return jsonify({'prices': prices})

    except Exception as e:
        logger.error(f"Error fetching realtime prices: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/system/data-status')
def get_data_status():
    """데이터 파일 상태 조회"""
    import json
    
    # Check these data files
    data_files_to_check = [
        {
            'name': 'Daily Prices',
            'path': 'data/daily_prices.csv',
            'link': '/dashboard/kr/closing-bet',
            'menu': 'Closing Bet'
        },
        {
            'name': 'Institutional Trend',
            'path': 'data/all_institutional_trend_data.csv',
            'link': '/dashboard/kr/vcp',
            'menu': 'VCP Signals'
        },
        {
            'name': 'AI Analysis',
            'path': 'data/kr_ai_analysis.json',
            'link': '/dashboard/kr/vcp',
            'menu': 'VCP Signals'
        },
        {
            'name': 'VCP Signals',
            'path': 'data/signals_log.csv',
            'link': '/dashboard/kr/vcp',
            'menu': 'VCP Signals'
        },
        {
            'name': 'AI Jongga V2',
            'path': 'data/jongga_v2_latest.json',
            'link': '/dashboard/kr/closing-bet',
            'menu': 'Closing Bet'
        },
        {
            'name': 'Market Gate',
            'path': 'data/market_gate.json',
            'link': '/dashboard/kr',
            'menu': 'Market Overview'
        }

    ]
    
    files_status = []
    
    for file_info in data_files_to_check:
        path = file_info['path']
        exists = os.path.exists(path)
        
        if exists:
            stat = os.stat(path)
            size_bytes = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime)
            
            # Format size
            if size_bytes > 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            elif size_bytes > 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} B"
            
            # Count rows if CSV
            row_count = None
            if path.endswith('.csv'):
                try:
                    row_count = sum(1 for _ in open(path)) - 1  # -1 for header
                except:
                    pass
            elif path.endswith('.json'):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'signals' in data:
                        row_count = len(data['signals'])
                    elif isinstance(data, list):
                        row_count = len(data)
                except:
                    pass
            
            files_status.append({
                'name': file_info['name'],
                'path': path,
                'exists': True,
                'lastModified': mtime.isoformat(),
                'size': size_str,
                'rowCount': row_count,
                'link': file_info.get('link', ''),
                'menu': file_info.get('menu', '')
            })
        else:
            files_status.append({
                'name': file_info['name'],
                'path': path,
                'exists': False,
                'lastModified': '',
                'size': '-',
                'rowCount': None,
                'link': file_info.get('link', ''),
                'menu': file_info.get('menu', '')
            })
    
    current_status = load_update_status()
    update_status = {
        'isRunning': current_status['isRunning'],
        'lastRun': current_status['startTime'] or datetime.now().isoformat(),
        'progress': current_status['currentItem'] or ''
    }

    return jsonify({
        'files': files_status,
        'update_status': update_status
    })



@common_bp.route('/kr/backtest-summary')
def get_backtest_summary():
    """VCP 및 Closing Bet(Jongga V2) 백테스트 요약 반환"""
    try:
        # 샘플 백테스트 요약
        summary = {
            'vcp': {
                'status': 'OK',
                'win_rate': 62.5,
                'avg_return': 4.2,
                'count': 16
            },
            'closing_bet': {
                'status': 'OK',
                'win_rate': 58.3,
                'avg_return': 3.8,
                'count': 12
            }
        }

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Error getting backtest summary: {e}")
        return jsonify({'error': str(e)}), 500


@common_bp.route('/system/env', methods=['GET', 'POST', 'DELETE'])
def manage_env():
    """환경 변수 관리 (읽기 및 쓰기)"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
    
    if request.method == 'GET':
        try:
            if not os.path.exists(env_path):
                return jsonify({})
                
            env_vars = {}
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # [Fix] 빈 값은 응답에서 제외 (쓰레기값 방지)
                        if not value or value.strip() == '':
                            continue
                        # 중요 키 마스킹 처리 (선택)
                        # [Modified] 사용자 요청: API Key 외에도 이메일, ID 등 개인정보가 포함된 모든 주요 설정값 마스킹
                        sensitive_keywords = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'USER', 'ID', 'URL', 'HOST', 'RECIPIENTS']
                        if any(k in key for k in sensitive_keywords):
                            if len(value) > 8:
                                value = value[:4] + '*' * (len(value) - 8) + value[-4:]
                            else:
                                value = '*' * len(value)
                        env_vars[key] = value
            return jsonify(env_vars)
        except Exception as e:
            logger.error(f"Error reading .env: {e}")
            return jsonify({'error': str(e)}), 500
            
    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            if not data:
                return jsonify({'status': 'ok'})
                
            # 기존 내용 읽기
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            # 업데이트할 키 추적
            updated_keys = set()
            new_lines = []
            
            # 1. 기존 라인 수정
            for line in lines:
                original_line = line
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('#'):
                    new_lines.append(original_line)
                    continue
                    
                if '=' in line_stripped:
                    key = line_stripped.split('=', 1)[0]
                    if key in data:
                        new_value = data[key]
                        # 마스킹된 값이 그대로 들어오면 업데이트 생략 (보안)
                        if '*' in new_value:
                             new_lines.append(original_line)
                             updated_keys.add(key)
                             continue
                        
                        # [Modified] 값이 비어있으면 라인 삭제 (완전 삭제)
                        if not new_value:
                            updated_keys.add(key)
                            # 메모리에서도 삭제
                            if key in os.environ:
                                del os.environ[key]
                            continue
                             
                        new_lines.append(f"{key}={new_value}\n")
                        updated_keys.add(key)
                    else:
                        new_lines.append(original_line)
                else:
                    new_lines.append(original_line)
            
            # 2. 새로운 키 추가
            for key, value in data.items():
                if key not in updated_keys and '*' not in value:
                    if not value: continue # 빈 값은 추가 안 함
                    
                     # 마지막 줄이 개행문자로 끝나지 않으면 추가
                    if new_lines and not new_lines[-1].endswith('\n'):
                        new_lines[-1] += '\n'
                    new_lines.append(f"{key}={value}\n")
            
            # 파일 쓰기
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            # 3. 환경변수 메모리 즉시 반영 (재시작 없이 적용)
            for key, value in data.items():
                if '*' not in value:
                    os.environ[key] = value
                
            return jsonify({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Error updating .env: {e}")
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            # 민감 정보 초기화 (Factory Reset)
            sensitive_keys = [
                'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_API_KEY',
                'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ZAI_API_KEY', 'PERPLEXITY_API_KEY',
                'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
                'DISCORD_WEBHOOK_URL', 'SLACK_WEBHOOK_URL',
                'SMTP_USER', 'SMTP_PASSWORD', 'EMAIL_RECIPIENTS',
                'USER_PROFILE'
            ]
            
            lines = []
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            new_lines = []
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('#'):
                    new_lines.append(line)
                    continue
                
                if '=' in line_stripped:
                    key = line_stripped.split('=', 1)[0]
                    if key in sensitive_keys:
                        new_lines.append(f"{key}=\n")
                        # 메모리에서도 삭제
                        if key in os.environ:
                            os.environ[key] = ""
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            # [New] 모든 사용자 데이터 파일 삭제
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, 'data')
            
            files_to_delete = [
                'user_quota.json', 
                'chatbot_history.json',
                'chatbot_memory.json',
                'chatbot_sessions.json'
            ]
            
            for fname in files_to_delete:
                path = os.path.join(data_dir, fname)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.info(f"Factory Reset: Deleted {fname}")
                    except Exception as e:
                        logger.error(f"Failed to delete {fname}: {e}")
                
            return jsonify({'status': 'ok', 'message': 'All sensitive data and user history types wiped.'})
            
        except Exception as e:
            logger.error(f"Error resetting .env: {e}")
            return jsonify({'error': str(e)}), 500


@common_bp.route('/notification/send', methods=['POST'])
def send_test_notification():
    """알림 테스트 발송"""
    try:
        data = request.get_json() or {}
        platform = data.get('platform') # discord, telegram, email
        
        if not platform:
             return jsonify({'status': 'error', 'message': 'Platform not specified'}), 400
             
        from engine.messenger import Messenger
        messenger = Messenger()
        
        # 테스트용 더미 데이터
        test_data = {
            "title": f"[Test] {platform.upper()} Notification",
            "gate_info": "System Status: Online",
            "summary_title": "테스트 발송입니다",
            "summary_desc": "설정된 정보로 알림이 정상적으로 수신되는지 확인하세요.",
            "signals": [
                {
                    "index": 1,
                    "name": "테스트종목",
                    "code": "005930",
                    "market_icon": "🔵",
                    "grade": "A",
                    "score": 85.5,
                    "change_pct": 1.2,
                    "volume_ratio": 2.5,
                    "trading_value": 5000000000,
                    "f_buy": 1000000000,
                    "i_buy": 500000000,
                    "entry": 70000,
                    "target": 75000, 
                    "stop": 68000,
                    "ai_reason": "AI 분석 테스트 메시지입니다. 시스템이 정상 동작 중입니다."
                }
            ]
        }
        
        # 강제 발송 (Messenger 내부 채널 리스트 무시하고 개별 메소드 호출 시도 또는 환경변수 의존)
        # Messenger 클래스는 초기화 시 환경변수를 읽으므로, 지금 환경변수가 잘 설정되었다면 동작함.
        
        if platform == 'discord':
            if not messenger.discord_url:
                return jsonify({'status': 'error', 'message': 'Discord Webhook URL not set in server env'}), 400
            messenger._send_discord(test_data)
            
        elif platform == 'telegram':
            if not messenger.telegram_token or not messenger.telegram_chat_id:
                return jsonify({'status': 'error', 'message': 'Telegram Token or Chat ID not set'}), 400
            messenger._send_telegram(test_data)
            
        elif platform == 'email':
             if not messenger.smtp_user:
                return jsonify({'status': 'error', 'message': 'SMTP settings not configured'}), 400
             messenger._send_email(test_data)
             
        else:
            return jsonify({'status': 'error', 'message': f'Unknown platform: {platform}'}), 400
            
        return jsonify({'status': 'success', 'message': f'{platform} test message sent'})

    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
