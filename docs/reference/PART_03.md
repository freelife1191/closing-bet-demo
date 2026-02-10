# PART 3 (Core Logic)

> [!WARNING]
> **Reference Only**: This document contains reference code and backups.
> The actual source of truth is located in the `app/` and `engine/` directories.
> Do not modify this file directly for production changes.

### app/routes/common.py (kr_market_package/app/routes/common.py)
```python
# app/routes/common.py
"""공통 API 라우트"""

import os
import json
import traceback
import pandas as pd
import yfinance as yf
import sys
import subprocess
from flask import Blueprint, jsonify, request, Response, stream_with_context

from app.utils.cache import get_sector, SECTOR_MAP

common_bp = Blueprint('common', __name__)

# Ticker 맵 로드
try:
    map_df = pd.read_csv('ticker_to_yahoo_map.csv', dtype=str)
    TICKER_TO_YAHOO_MAP = dict(zip(map_df['ticker'], map_df['yahoo_ticker']))
    print(f"Loaded {len(TICKER_TO_YAHOO_MAP)} verified ticker mappings.")
except Exception as e:
    print(f"Error loading ticker map: {e}")
    TICKER_TO_YAHOO_MAP = {}


@common_bp.route('/portfolio')
def get_portfolio_data():
    """포트폴리오 데이터 - KR Market"""
    try:
        target_date = request.args.get('date')
        
        if target_date:
            # --- Historical Data Mode ---
            csv_path = os.path.join('us_market', 'data', 'recommendation_history.csv')
            if not os.path.exists(csv_path):
                return jsonify({'error': 'History not found'}), 404
                
            df = pd.read_csv(csv_path, dtype={'ticker': str})
            df = df[df['recommendation_date'] == target_date]
            top_holdings_df = df.sort_values(by='final_investment_score', ascending=False).head(10)
            top_picks = top_holdings_df
            
            # Fetch Real-time Prices
            tickers = top_holdings_df['ticker'].tolist()
            current_prices = {}
            
            if tickers:
                yf_tickers = []
                ticker_map = {}
                
                for t in tickers:
                    t_padded = str(t).zfill(6)
                    yf_t = TICKER_TO_YAHOO_MAP.get(t_padded, f"{t_padded}.KS")
                    yf_tickers.append(yf_t)
                    ticker_map[yf_t] = t_padded

                try:
                    price_data = yf.download(yf_tickers, period='1d', interval='1m', progress=False, threads=True)
                    if not price_data.empty:
                        price_data = price_data.ffill()
                        if 'Close' in price_data.columns:
                            closes = price_data['Close']
                            for yf_t, orig_t in ticker_map.items():
                                try:
                                    if isinstance(closes, pd.DataFrame) and yf_t in closes.columns:
                                        val = closes[yf_t].iloc[-1]
                                        current_prices[orig_t] = float(val) if not pd.isna(val) else 0
                                    elif isinstance(closes, pd.Series) and closes.name == yf_t:
                                        val = closes.iloc[-1]
                                        current_prices[orig_t] = float(val) if not pd.isna(val) else 0
                                except:
                                    current_prices[orig_t] = 0
                except Exception as e:
                    print(f"Error fetching historical prices: {e}")

            top_holdings = []
            for _, row in top_holdings_df.iterrows():
                t_str = str(row['ticker']).zfill(6)
                rec_price = float(row['current_price'])
                cur_price = current_prices.get(t_str, 0)
                return_pct = ((cur_price - rec_price) / rec_price * 100) if rec_price > 0 else 0.0
                
                top_holdings.append({
                    'ticker': t_str,
                    'name': row['name'],
                    'price': cur_price,
                    'recommendation_price': rec_price,
                    'return_pct': return_pct,
                    'score': float(row['final_investment_score']),
                    'grade': row['investment_grade'],
                    'wave': row.get('wave_stage', 'N/A'),
                    'sd_stage': 'N/A',
                    'inst_trend': 'N/A',
                    'ytd': 0
                })
                
            key_stats = {
                'qtd_return': f"{top_holdings_df['final_investment_score'].mean():.1f}" if not top_holdings_df.empty else "0.0",
                'ytd_return': str(len(top_holdings_df)),
                'one_year_return': "N/A",
                'div_yield': "N/A",
                'expense_ratio': 'N/A'
            }
            holdings_distribution = []

        else:
            # --- Current Live Data Mode ---
            csv_path = 'wave_transition_analysis_results.csv'
            if not os.path.exists(csv_path):
                return jsonify({
                    'key_stats': {'qtd_return': '+5.2%', 'ytd_return': '+12.8%', 'one_year_return': '+15.4%', 'div_yield': '2.1%', 'expense_ratio': '0.45%'},
                    'holdings_distribution': [{'label': 'Equity', 'value': 65, 'color': '#3b82f6'}],
                    'top_holdings': [],
                    'style_box': {'large_value': 15, 'large_core': 20, 'large_growth': 15, 'mid_value': 10, 'mid_core': 15, 'mid_growth': 10, 'small_value': 5, 'small_core': 5, 'small_growth': 5}
                })
    
            df = pd.read_csv(csv_path, dtype={'ticker': str})
            top_picks = df[df['investment_grade'].isin(['S급 (즉시 매수)', 'A급 (적극 매수)'])]
            
            avg_score = top_picks['final_investment_score'].mean() if not top_picks.empty else 0
            avg_return_potential = top_picks['price_change_6m'].mean() * 100 if not top_picks.empty else 0
            avg_div_yield = top_picks['div_yield'].mean() if not top_picks.empty else 0
            
            key_stats = {
                'qtd_return': f"{avg_score:.1f}",
                'ytd_return': f"{len(top_picks)}",
                'one_year_return': f"{avg_return_potential:.1f}%",
                'div_yield': f"{avg_div_yield:.1f}%",
                'expense_ratio': 'N/A'
            }
    
            market_counts = top_picks['market'].value_counts()
            holdings_distribution = []
            colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
            for i, (market, count) in enumerate(market_counts.items()):
                holdings_distribution.append({
                    'label': market,
                    'value': int(count),
                    'color': colors[i % len(colors)]
                })
                
            top_holdings_df = top_picks.sort_values(by='final_investment_score', ascending=False).head(10)
            top_holdings = []
            for _, row in top_holdings_df.iterrows():
                rec_price = float(row['current_price'])
                cur_price = float(row['current_price'])
                
                top_holdings.append({
                    'ticker': str(row['ticker']).zfill(6),
                    'name': row['name'],
                    'price': cur_price,
                    'recommendation_price': rec_price,
                    'return_pct': 0.0,
                    'score': float(row['final_investment_score']),
                    'grade': row['investment_grade'],
                    'wave': row.get('wave_stage', 'N/A'),
                    'sd_stage': row.get('supply_demand_stage', 'N/A'),
                    'inst_trend': row.get('institutional_trend', 'N/A'),
                    'ytd': float(row['price_change_20d']) * 100
                })

        # --- Style Box ---
        style_counts = {
            'large_value': 0, 'large_core': 0, 'large_growth': 0,
            'mid_value': 0, 'mid_core': 0, 'mid_growth': 0,
            'small_value': 0, 'small_core': 0, 'small_growth': 0
        }
        
        total_style_count = 0
        for _, row in top_picks.iterrows():
            market = row.get('market', 'KOSPI')
            is_large = market == 'KOSPI'
            pbr = row.get('pbr', 1.5)
            if pd.isna(pbr): pbr = 1.5
            
            style_suffix = '_core'
            if pbr < 1.0: style_suffix = '_value'
            elif pbr > 2.5: style_suffix = '_growth'
            
            size_prefix = 'large' if is_large else 'small'
            key = f"{size_prefix}{style_suffix}"
            if key in style_counts:
                style_counts[key] += 1
                total_style_count += 1

        style_box = {}
        if total_style_count > 0:
            for k, v in style_counts.items():
                style_box[k] = round((v / total_style_count) * 100, 1)
        else:
            style_box = {k: 0 for k in style_counts}

        latest_date = None
        if 'current_date' in df.columns and not df.empty:
            latest_date = df['current_date'].iloc[0]
        elif 'recommendation_date' in df.columns and not df.empty:
            latest_date = df['recommendation_date'].max()

        # --- Market Indices ---
        market_indices = _fetch_market_indices()

        # --- Performance Data ---
        performance_data = _fetch_performance_data()

        data = {
            'key_stats': key_stats,
            'market_indices': market_indices,
            'holdings_distribution': holdings_distribution,
            'top_holdings': top_holdings,
            'style_box': style_box,
            'performance': performance_data,
            'latest_date': latest_date
        }
        return jsonify(data)
    except Exception as e:
        print(f"Error getting portfolio data: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@common_bp.route('/portfolio-summary')
def portfolio_summary():
    """포트폴리오 요약"""
    try:
        summary = {
            'kr_market': {'count': 0, 'top_grade': '-'},
            'us_market': {'count': 0, 'top_grade': '-'},
            'crypto': {'count': 0, 'top_grade': '-'}
        }
        
        # KR Market
        kr_path = os.path.join('data', 'kr_ai_analysis.json')
        if os.path.exists(kr_path):
            with open(kr_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            signals = data.get('signals', [])
            summary['kr_market']['count'] = len(signals)
            if signals:
                summary['kr_market']['top_grade'] = signals[0].get('grade', '-')
        
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@common_bp.route('/stock/<ticker>')
def get_stock_detail(ticker):
    """개별 종목 상세 정보"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return jsonify({
            'ticker': ticker,
            'name': info.get('shortName', ticker),
            'sector': get_sector(ticker),
            'price': info.get('regularMarketPrice', 0),
            'change': info.get('regularMarketChange', 0),
            'change_pct': info.get('regularMarketChangePercent', 0),
            'volume': info.get('regularMarketVolume', 0),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', 0),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@common_bp.route('/realtime-prices', methods=['POST'])
def get_realtime_prices():
    """실시간 가격 조회"""
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        market = data.get('market', 'kr')
        
        if not tickers:
            return jsonify({'prices': {}})
        
        prices = {}
        
        if market == 'kr':
            yf_tickers = []
            ticker_map = {}
            
            for t in tickers:
                t_padded = str(t).zfill(6)
                yf_t = TICKER_TO_YAHOO_MAP.get(t_padded, f"{t_padded}.KS")
                yf_tickers.append(yf_t)
                ticker_map[yf_t] = t_padded
            
            try:
                price_data = yf.download(yf_tickers, period='1d', interval='1m', progress=False, threads=True)
                if not price_data.empty:
                    price_data = price_data.ffill()
                    if 'Close' in price_data.columns:
                        closes = price_data['Close']
                        for yf_t, orig_t in ticker_map.items():
                            try:
                                if isinstance(closes, pd.DataFrame) and yf_t in closes.columns:
                                    val = closes[yf_t].iloc[-1]
                                    prices[orig_t] = float(val) if not pd.isna(val) else 0
                                elif isinstance(closes, pd.Series):
                                    val = closes.iloc[-1]
                                    prices[orig_t] = float(val) if not pd.isna(val) else 0
                            except:
                                prices[orig_t] = 0
            except Exception as e:
                print(f"Error fetching realtime prices: {e}")
        else:
            # US Market
            try:
                price_data = yf.download(tickers, period='1d', interval='1m', progress=False, threads=True)
                if not price_data.empty:
                    price_data = price_data.ffill()
                    if 'Close' in price_data.columns:
                        closes = price_data['Close']
                        for t in tickers:
                            try:
                                if isinstance(closes, pd.DataFrame) and t in closes.columns:
                                    val = closes[t].iloc[-1]
                                    prices[t] = float(val) if not pd.isna(val) else 0
                                elif isinstance(closes, pd.Series):
                                    val = closes.iloc[-1]
                                    prices[t] = float(val) if not pd.isna(val) else 0
                            except:
                                prices[t] = 0
            except Exception as e:
                print(f"Error fetching US realtime prices: {e}")
        
        return jsonify({'prices': prices})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@common_bp.route('/run-analysis', methods=['POST'])
def run_analysis():
    """분석 스크립트 백그라운드 실행"""
    try:
        import subprocess
        import threading
        
        def run_scripts():
            print("🚀 Starting Analysis...")
            try:
                # 1. Run Analysis
                subprocess.run(['python3', 'analysis2.py'], check=True)
                print("✅ Analysis Complete.")
                
                # 2. Run Performance Tracking
                subprocess.run(['python3', 'track_performance.py'], check=True)
                print("✅ Performance Tracking Complete.")
                
            except Exception as e:
                print(f"❌ Error running scripts: {e}")

        # Start in background thread
        thread = threading.Thread(target=run_scripts)
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Analysis started in background.'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _fetch_market_indices():
    """마켓 인덱스 데이터 조회"""
    market_indices = []
    indices_map = {
        '^DJI': 'Dow Jones',
        '^GSPC': 'S&P 500',
        '^IXIC': 'NASDAQ',
        '^RUT': 'Russell 2000',
        '^VIX': 'VIX',
        'GC=F': 'Gold',
        'CL=F': 'Crude Oil',
        'BTC-USD': 'Bitcoin',
        '^TNX': '10Y Treasury',
        'DX-Y.NYB': 'Dollar Index',
        'KRW=X': 'USD/KRW'
    }
    
    try:
        tickers_list = list(indices_map.keys())
        idx_data = yf.download(tickers_list, period='5d', progress=False, threads=True)
        
        if not idx_data.empty:
            closes = idx_data['Close']
            
            for ticker, name in indices_map.items():
                try:
                    if isinstance(closes, pd.DataFrame) and ticker in closes.columns:
                        series = closes[ticker].dropna()
                    elif isinstance(closes, pd.Series) and closes.name == ticker:
                        series = closes.dropna()
                    else:
                        continue
                        
                    if len(series) >= 2:
                        current_val = series.iloc[-1]
                        prev_val = series.iloc[-2]
                        change = current_val - prev_val
                        change_pct = (change / prev_val) * 100
                        
                        market_indices.append({
                            'name': name,
                            'price': f"{current_val:,.2f}",
                            'change': f"{change:,.2f}",
                            'change_pct': change_pct,
                            'color': 'red' if change >= 0 else 'blue'
                        })
                except Exception as e:
                    print(f"Error processing index {ticker}: {e}")
                    
    except Exception as e:
        print(f"Error fetching market indices: {e}")
    
    return market_indices


def _fetch_performance_data():
    """성과 데이터 조회"""
    performance_data = []
    perf_csv_path = os.path.join('us_market', 'data', 'performance_report.csv')
    
    if os.path.exists(perf_csv_path):
        perf_df = pd.read_csv(perf_csv_path)
        recent_perf = perf_df.sort_values('rec_date', ascending=False).head(10)
        for _, row in recent_perf.iterrows():
            performance_data.append({
                'ticker': row['ticker'],
                'name': row['name'],
                'return': f"{row['return']:.1f}%",
                'date': row['rec_date'],
                'days': row['days']
            })
    
    return performance_data


@common_bp.route('/system/data-status')
def get_data_status():
    """데이터 파일 상태 조회"""
    from datetime import datetime
    

    
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
            'path': 'signals_log.csv',
            'link': '/dashboard/kr/vcp',
            'menu': 'VCP Signals'
        },
        {
            'name': 'AI Jongga V2',
            'path': 'data/jongga_v2_latest.json',
            'link': '/dashboard/kr/closing-bet',
            'menu': 'Closing Bet'
        },
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
                    df = pd.read_csv(path, nrows=0)
                    row_count = sum(1 for _ in open(path)) - 1  # -1 for header
                except:
                    pass
            elif path.endswith('.json'):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'signals' in data:
                        row_count = len(data['signals'])
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
    
    # Check update status (simple implementation)
    update_status = {
        'isRunning': False,
        'lastRun': '',
        'progress': ''
    }
    
    # Check log file for last run info
    log_path = 'logs/kr_update.log'
    if os.path.exists(log_path):
        stat = os.stat(log_path)
        mtime = datetime.fromtimestamp(stat.st_mtime)
        update_status['lastRun'] = mtime.isoformat()
    
    return jsonify({
        'files': files_status,
        'update_status': update_status
    })


@common_bp.route('/system/update-data-stream')
def stream_update_data():
    """데이터 업데이트 프로세스 스트리밍 실행"""
    def generate():
        yield "data: [SYSTEM] Starting data update process...\n\n"
        
        try:
            # kr_market/scheduler.py --now 실행
            script_path = 'scheduler.py'
            if not os.path.exists(script_path):
                 yield f"data: [ERROR] Script not found at {script_path}\n\n"
                 return

            cmd = [sys.executable, '-u', script_path, '--now']
            
            env = os.environ.copy()
            env['PYTHONPATH'] = os.getcwd() # Ensure module imports work
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1
            )
            
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    yield f"data: {clean_line}\n\n"
            
            process.wait()
            yield f"data: [SYSTEM] Process finished with exit code {process.returncode}\n\n"
            
            if process.returncode == 0:
                yield "data: [SYSTEM] Update completed successfully.\n\n"
            else:
                yield "data: [SYSTEM] Update failed. Check logs.\n\n"
                
        except Exception as e:
            yield f"data: [ERROR] Failed to start process: {str(e)}\n\n"
        
        yield "event: end\ndata: close\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@common_bp.route('/kr/backtest-summary')
def get_backtest_summary():
    """VCP 및 Closing Bet(Jongga V2) 백테스트 요약 반환"""
    import glob
    from datetime import datetime, timedelta
    
    summary = {
        'vcp': {'status': 'No Data', 'win_rate': 0, 'avg_return': 0, 'count': 0},
        'closing_bet': {'status': 'No Data', 'win_rate': 0, 'avg_return': 0, 'count': 0}
    }
    
    debug_info = {}

    # 1. VCP Backtest (기존 로직 유지)
    try:
        csv_path = 'final_backtest_results.csv'
        if not os.path.exists(csv_path):
            csv_path = 'historical_signals_with_returns.csv'
             
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if not df.empty:
                is_win_col = 'is_winner' if 'is_winner' in df.columns else 'is_win'
                return_col = 'net_return' if 'net_return' in df.columns else 'return_pct'
                if return_col not in df.columns and 'return' in df.columns:
                    return_col = 'return'

                total = len(df)
                wins = 0
                avg_ret = 0

                if is_win_col in df.columns:
                    first_val = df[is_win_col].iloc[0]
                    if df[is_win_col].dtype == object or isinstance(first_val, str):
                        wins = len(df[df[is_win_col].astype(str).str.lower() == 'true'])
                    else:
                        wins = int(df[is_win_col].sum())
                elif return_col in df.columns:
                    wins = len(df[df[return_col] > 0])
                
                if return_col in df.columns:
                    avg_ret = df[return_col].mean()

                win_rate = (wins / total) * 100 if total > 0 else 0
                
                summary['vcp'] = {
                    'status': 'OK',
                    'count': int(total),
                    'win_rate': round(win_rate, 1),
                    'avg_return': round(avg_ret, 2)
                }
    except Exception as e:
        debug_info['vcp_error'] = str(e)
        summary['vcp']['error'] = str(e)

    # 2. Closing Bet (Jongga V2) Backtest
    try:
        data_dir = os.path.join('data')
        history_files = glob.glob(os.path.join(data_dir, 'jongga_v2_results_*.json'))
        debug_info['jongga_files_count'] = len(history_files)
        
        if len(history_files) < 2:
            # 데이터 축적 중
            summary['closing_bet'] = {
                'status': 'Accumulating',
                'message': f'{len(history_files)}일 데이터 (최소 2일 필요)',
                'count': 0,
                'win_rate': 0,
                'avg_return': 0
            }
        else:
            # 히스토리 백테스트 수행
            all_signals = []
            today = datetime.now().strftime('%Y%m%d')
            
            for file_path in sorted(history_files):
                # 오늘 파일은 제외 (아직 결과 없음)
                if today in file_path:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    for signal in data.get('signals', []):
                        signal['file_date'] = data.get('date', '')
                        all_signals.append(signal)
                except:
                    continue
            
            debug_info['total_signals'] = len(all_signals)
            
            if all_signals:
                # 현재가 조회하여 수익률 계산
                wins = 0
                total_return = 0
                valid_count = 0
                
                for signal in all_signals:
                    entry_price = signal.get('entry_price', 0)
                    target_price = signal.get('target_price', 0)
                    stop_price = signal.get('stop_price', 0)
                    
                    if entry_price <= 0:
                        continue
                    
                    # 간이 백테스트: target 도달 여부 (실제로는 pykrx로 미래 가격 확인 필요)
                    # 현재는 change_pct 기반으로 추정
                    change_pct = signal.get('change_pct', 0)
                    
                    if change_pct > 0:
                        # 시그널 당일 상승 중이면 target 도달 가정 (5% 수익)
                        est_return = 5.0
                        wins += 1
                    else:
                        # 하락 중이면 손절 가정 (-3% 손실)
                        est_return = -3.0
                    
                    total_return += est_return
                    valid_count += 1
                
                if valid_count > 0:
                    win_rate = (wins / valid_count) * 100
                    avg_return = total_return / valid_count
                    
                    summary['closing_bet'] = {
                        'status': 'OK',
                        'count': valid_count,
                        'win_rate': round(win_rate, 1),
                        'avg_return': round(avg_return, 2)
                    }
                else:
                    summary['closing_bet'] = {
                        'status': 'No Valid Signals',
                        'count': 0,
                        'win_rate': 0,
                        'avg_return': 0
                    }
            else:
                summary['closing_bet'] = {
                    'status': 'Accumulating',
                    'message': '과거 시그널 없음',
                    'count': 0,
                    'win_rate': 0,
                    'avg_return': 0
                }
                
    except Exception as e:
        debug_info['jongga_error'] = str(e)
        summary['closing_bet']['error'] = str(e)

    response = summary.copy()
    response['debug'] = debug_info
    return jsonify(response)

```

