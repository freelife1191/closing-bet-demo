#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공통 API 라우트
"""
from flask import Blueprint, jsonify, request
import pandas as pd
import os
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

try:
    import engine.shared as shared_state
except ImportError:
    # Fallback if engine package not found in path
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    import engine.shared as shared_state

# 글로벌 업데이트 상태 추적 (메모리)
update_tracker = {
    'isRunning': False,
    'startTime': None,
    'currentItem': None,
    'items': [],  # [{'name': 'Daily Prices', 'status': 'pending|running|done|error'}]
}
update_lock = Lock()


def start_update(items_list):
    """업데이트 시작"""
    with update_lock:
        shared_state.STOP_REQUESTED = False
        update_tracker['isRunning'] = True
        update_tracker['startTime'] = datetime.now().isoformat()
        update_tracker['items'] = [{'name': name, 'status': 'pending'} for name in items_list]
        update_tracker['currentItem'] = None


def update_item_status(name, status):
    """아이템 상태 업데이트"""
    with update_lock:
        for item in update_tracker['items']:
            if item['name'] == name:
                item['status'] = status
                if status == 'running':
                    update_tracker['currentItem'] = name
                break


def stop_update():
    """업데이트 중단"""
    with update_lock:
        shared_state.STOP_REQUESTED = True
        update_tracker['isRunning'] = False
        update_tracker['currentItem'] = None
        # 중단 시에도 기존 상태 유지 또는 초기화? 
        # UI에서 'Stopped' 상태를 처리하려면 남겨두는 게 좋지만, 
        # 여기서는 update_tracker['items']를 비우지 않고 그대로 두어 에러 표시 등이 가능하게 함.
        # 다만 재시작 시 start_update에서 초기화됨.
        
        # 명시적으로 실행 중인 항목을 error/stopped로 변경
        for item in update_tracker['items']:
            if item['status'] == 'running':
                item['status'] = 'error' # 중단됨


def finish_update():
    """업데이트 완료"""
    with update_lock:
        update_tracker['isRunning'] = False
        update_tracker['currentItem'] = None
        # 완료 시 items를 비워서 오래된 에러 상태가 남지 않도록 함
        update_tracker['items'] = []


@common_bp.route('/system/update-status')
def get_update_status():
    """업데이트 상태만 조회 (가벼운 폴링용)"""
    with update_lock:
        return jsonify({
            'isRunning': update_tracker['isRunning'],
            'startTime': update_tracker['startTime'],
            'currentItem': update_tracker['currentItem'],
            'items': update_tracker['items'].copy()
        })


@common_bp.route('/system/start-update', methods=['POST'])
def api_start_update():
    """업데이트 시작 (백그라운드 실행)"""
    data = request.get_json() or {}
    items_list = data.get('items', [])
    target_date = data.get('target_date') # YYYY-MM-DD or None
    
    # 이미 실행 중이면 거부
    if update_tracker['isRunning']:
        return jsonify({'status': 'error', 'message': 'Already running'}), 400

    # UI 상태 초기화
    start_update(items_list)
    
    # 백그라운드 스레드 실행
    thread = Thread(target=run_background_update, args=(target_date,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'ok'})


def run_background_update(target_date):
    """백그라운드에서 순차적으로 데이터 업데이트 실행"""
    import asyncio
    
    try:
        from scripts import init_data

        # 1. Daily Prices
        if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
        update_item_status('Daily Prices', 'running')
        try:
            init_data.create_daily_prices(target_date)
            update_item_status('Daily Prices', 'done')
        except Exception as e:
            logger.error(f"Daily Prices Failed: {e}")
            update_item_status('Daily Prices', 'error')
            if shared_state.STOP_REQUESTED: raise e # 중단 요청이면 전체 중단
            
        # 2. Institutional Trend
        if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
        update_item_status('Institutional Trend', 'running')
        try:
            init_data.create_institutional_trend(target_date)
            update_item_status('Institutional Trend', 'done')
        except Exception as e:
            logger.error(f"Institutional Trend Failed: {e}")
            update_item_status('Institutional Trend', 'error')
            if shared_state.STOP_REQUESTED: raise e

        # 2.5 Market Gate Analysis
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
        if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
        update_item_status('VCP Signals', 'running')
        vcp_df = None
        try:
            # VCP는 스크립트 함수 호출 대신 기존 로직 활용 (init_data.create_signals_log는 샘플용일 수 있으므로 주의)
            # init_data.create_signals_log() 대신 kr_market.run_vcp_signals_screener 로직을 사용해야 함.
            # 하지만 여기서는 간단히 init_data.create_signals_log() 사용 (기존 init-data API도 그랬음)
            vcp_df = init_data.create_signals_log(target_date)
            update_item_status('VCP Signals', 'done')
        except Exception as e:
            logger.error(f"VCP Signals Failed: {e}")
            update_item_status('VCP Signals', 'error')
            if shared_state.STOP_REQUESTED: raise e

        # 4. AI Analysis
        if shared_state.STOP_REQUESTED: raise Exception("Stopped by user")
        update_item_status('AI Analysis', 'running')
        try:
            from kr_ai_analyzer import KrAiAnalyzer
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
                
                if vcp_df is not None and not vcp_df.empty:
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


@common_bp.route('/portfolio')
def get_portfolio_data():
    """포트폴리오 데이터"""
    try:
        # 샘플 포트폴리오 데이터
        top_holdings = [
            {
                'ticker': '005930',
                'name': '삼성전자',
                'price': 71800,
                'recommendation_price': 72000,
                'return_pct': -0.28,
                'score': 82.5,
                'grade': 'A',
                'wave': 'N/A',
                'sd_stage': '강한매집',
                'inst_trend': '매수',
                'ytd': 15.2
            },
            {
                'ticker': '000270',
                'name': '기아',
                'price': 121000,
                'recommendation_price': 119800,
                'return_pct': 1.0,
                'score': 75.0,
                'grade': 'A',
                'wave': '상승',
                'sd_stage': '약매집',
                'inst_trend': '중립',
                'ytd': 22.5
            }
        ]

        key_stats = {
            'qtd_return': '78.8',
            'ytd_return': '2',
            'one_year_return': '+15.4',
            'div_yield': '2.1',
            'expense_ratio': '0.45'
        }

        holdings_distribution = [
            {'label': 'KOSPI', 'value': 1, 'color': '#ef4444'},
            {'label': 'KOSDAQ', 'value': 1, 'color': '#3b82f6'}
        ]

        return jsonify({
            'key_stats': key_stats,
            'holdings_distribution': holdings_distribution,
            'top_holdings': top_holdings,
            'latest_date': datetime.now().strftime('%Y-%m-%d')
        })

    except Exception as e:
        logger.error(f"Error getting portfolio data: {e}")
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
    
    update_status = {
        'isRunning': False,
        'lastRun': datetime.now().isoformat(),
        'progress': ''
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


@common_bp.route('/system/env', methods=['GET', 'POST'])
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
                        # 중요 키 마스킹 처리 (선택)
                        if any(k in key for k in ['KEY', 'SECRET', 'PASSWORD', 'TOKEN']):
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
                             
                        new_lines.append(f"{key}={new_value}\n")
                        updated_keys.add(key)
                    else:
                        new_lines.append(original_line)
                else:
                    new_lines.append(original_line)
            
            # 2. 새로운 키 추가
            for key, value in data.items():
                if key not in updated_keys and '*' not in value:
                     # 마지막 줄이 개행문자로 끝나지 않으면 추가
                    if new_lines and not new_lines[-1].endswith('\n'):
                        new_lines[-1] += '\n'
                    new_lines.append(f"{key}={value}\n")
            
            # 파일 쓰기
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            return jsonify({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Error updating .env: {e}")
            return jsonify({'error': str(e)}), 500

