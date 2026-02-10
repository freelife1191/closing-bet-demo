# PART 2 (Core Logic)

> [!WARNING]
> **Reference Only**: This document contains reference code and backups.
> The actual source of truth is located in the `app/` and `engine/` directories.
> Do not modify this file directly for production changes.

### app/routes/kr_market.py (kr_market_package/app/routes/kr_market.py)
```python
# app/routes/kr_market.py
"""KR 마켓 API 라우트"""

import os
import json
import traceback
from datetime import datetime
import pandas as pd
from flask import Blueprint, jsonify, request, current_app

kr_bp = Blueprint('kr', __name__)


@kr_bp.route('/market-status')
def get_kr_market_status():
    """한국 시장 상태"""
    try:
        prices_path = os.path.join('data', 'daily_prices.csv')
        if not os.path.exists(prices_path):
            return jsonify({'status': 'UNKNOWN', 'reason': 'No price data'}), 404
            
        df = pd.read_csv(prices_path, dtype={'ticker': str})
        target_ticker = '069500'
        target_name = 'KODEX 200'
        
        market_df = df[df['ticker'] == target_ticker].copy()
        
        if market_df.empty:
            target_ticker = '005930'
            target_name = 'Samsung Elec'
            market_df = df[df['ticker'] == target_ticker].copy()
            
        if market_df.empty:
            return jsonify({'status': 'UNKNOWN', 'reason': 'Market proxy data not found'}), 404
             
        market_df['date'] = pd.to_datetime(market_df['date'])
        market_df = market_df.sort_values('date')
        
        if len(market_df) < 200:
            return jsonify({'status': 'NEUTRAL', 'reason': 'Insufficient data'}), 200
             
        market_df['MA20'] = market_df['current_price'].rolling(20).mean()
        market_df['MA50'] = market_df['current_price'].rolling(50).mean()
        market_df['MA200'] = market_df['current_price'].rolling(200).mean()
        
        last = market_df.iloc[-1]
        price = last['current_price']
        ma20 = last['MA20']
        ma50 = last['MA50']
        ma200 = last['MA200']
        
        status = "NEUTRAL"
        score = 50
        
        if price > ma200 and ma20 > ma50:
            status = "RISK_ON"
            score = 80
        elif price < ma200 and ma20 < ma50:
            status = "RISK_OFF"
            score = 20
            
        return jsonify({
            'status': status,
            'score': score,
            'current_price': float(price),
            'ma200': float(ma200),
            'date': last['date'].strftime('%Y-%m-%d'),
            'symbol': target_ticker,
            'name': target_name
        })

    except Exception as e:
        print(f"Error checking market status: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/signals')
def get_kr_signals():
    """오늘의 VCP + 외인매집 시그널"""
    try:
        # Load ticker name mapping
        name_map = {}
        ticker_map_path = 'data/kr_market/ticker_to_yahoo_map.csv'
        if os.path.exists(ticker_map_path):
            try:
                map_df = pd.read_csv(ticker_map_path, dtype={'ticker': str})
                name_map = dict(zip(map_df['ticker'].str.zfill(6), map_df['name']))
            except:
                pass
        
        json_path = 'data/kr_ai_analysis.json'
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                signals = data.get('signals', [])
                
                # Fill missing names from ticker map
                yahoo_map = {}
                try:
                    if os.path.exists(ticker_map_path):
                        map_df = pd.read_csv(ticker_map_path, dtype={'ticker': str})
                        yahoo_map = dict(zip(map_df['ticker'].str.zfill(6), map_df['yahoo_ticker']))
                except:
                    pass

                for signal in signals:
                    ticker = str(signal.get('ticker', '')).zfill(6)
                    if not signal.get('name'):
                        signal['name'] = name_map.get(ticker, ticker)
                
                # -----------------------------------------------------------
                # Inject Real-time Prices using yfinance
                # -----------------------------------------------------------
                try:
                    import yfinance as yf
                    yf_tickers = []
                    signal_by_yf = {}
                    
                    for s in signals:
                        t = str(s.get('ticker', '')).zfill(6)
                        if not t: continue
                        yf_t = yahoo_map.get(t, f"{t}.KS")
                        yf_tickers.append(yf_t)
                        # Map yahoo ticker back to signal reference
                        # (If distinct signals have same ticker, last one wins, but usually unique)
                        signal_by_yf[yf_t] = s

                    if yf_tickers:
                        # Fetch 1-minute data for today
                        price_data = yf.download(yf_tickers, period='1d', interval='1m', progress=False, threads=True)
                        
                        if not price_data.empty:
                            closes = price_data['Close']
                            
                            # Single ticker case handling
                            if len(yf_tickers) == 1:
                                val = float(closes.iloc[-1])
                                s = signal_by_yf[yf_tickers[0]]
                                s['current_price'] = val
                                # Calculate return from entry
                                entry = float(s.get('entry_price', 0))
                                if entry > 0:
                                    s['return_pct'] = round((val - entry) / entry * 100, 2)
                            else:
                                # Multi ticker case
                                for yf_t, s in signal_by_yf.items():
                                    try:
                                        if yf_t in closes.columns:
                                            # Check if last value is valid (not NaN)
                                            val = closes[yf_t].iloc[-1]
                                            if pd.notna(val) and float(val) > 0:
                                                s['current_price'] = float(val)
                                                
                                                entry = float(s.get('entry_price', 0))
                                                if entry > 0:
                                                    s['return_pct'] = round((float(val) - entry) / entry * 100, 2)
                                    except:
                                        pass
                except Exception as e:
                    print(f"Error fetching realtime signal prices: {e}")
                # -----------------------------------------------------------
                
                signals.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                return jsonify({
                    'signals': signals,
                    'count': len(signals),
                    'generated_at': data.get('generated_at', ''),
                    'source': 'json_live'
                })
            except Exception as e:
                print(f"Error reading JSON: {e}")
                pass
            
        # Fallback to CSV
        signals_path = 'kr_market/signals_log.csv'
        
        if not os.path.exists(signals_path):
            return jsonify({
                'signals': [],
                'count': 0,
                'message': '시그널 로그가 없습니다.'
            })
        
        df = pd.read_csv(signals_path, encoding='utf-8-sig')
        if 'status' in df.columns:
            df = df[df['status'] == 'OPEN']
        
        signals = []
        for _, row in df.iterrows():
            signals.append({
                'ticker': str(row['ticker']).zfill(6),
                'name': row.get('name', ''),
                'market': row.get('market', ''),
                'signal_date': row['signal_date'],
                'foreign_5d': int(row.get('foreign_5d', 0)),
                'inst_5d': int(row.get('inst_5d', 0)),
                'score': float(row.get('score', 0)),
                'contraction_ratio': float(row.get('contraction_ratio', 0)),
                'entry_price': float(row.get('entry_price', 0)),
                'current_price': float(row.get('entry_price', 0)),
                'return_pct': 0,
                'status': row.get('status', 'OPEN')
            })
            
        return jsonify({
            'signals': signals[:20],
            'count': len(signals),
            'source': 'csv_fallback'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# 종가베팅 (Closing Bet) Legacy API - REMOVED
# 현재 engine/ 기반 jongga-v2 API 사용 중
# ============================================================


@kr_bp.route('/stock-chart/<ticker>')
@kr_bp.route('/stock-chart/<ticker>')
def get_kr_stock_chart(ticker):
    """KR 종목 차트 데이터 (실시간 포함)"""
    try:
        # Load from daily_prices.csv
        prices_path = os.path.join('data', 'daily_prices.csv')
        if not os.path.exists(prices_path):
            return jsonify({'error': 'Price data not found'}), 404
        
        df = pd.read_csv(prices_path, dtype={'ticker': str})
        ticker_padded = str(ticker).zfill(6)
        stock_df = df[df['ticker'] == ticker_padded].copy()
        
        if stock_df.empty:
            return jsonify({'error': 'Ticker not found'}), 404
        
        stock_df['date'] = pd.to_datetime(stock_df['date'])
        stock_df = stock_df.sort_values('date')
        
        # Prepare chart data from history
        chart_data = []
        # Optimization: Take last 300 rows to ensure we have enough history but not too much payload
        history_df = stock_df.tail(300)
        
        for _, row in history_df.iterrows():
            chart_data.append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'open': float(row.get('open', row['current_price'])),
                'high': float(row.get('high', row['current_price'])),
                'low': float(row.get('low', row['current_price'])),
                'close': float(row['current_price']),
                'volume': int(row.get('volume', 0))
            })

        # Check if we need to append today's real-time data
        if not history_df.empty:
            last_date = history_df.iloc[-1]['date']
            today = datetime.now().date()
            
            # If last data is not from today (and it's a weekday), try to fetch real-time data
            if last_date.date() < today and today.weekday() < 5:
                try:
                    from pykrx import stock
                    today_str = today.strftime('%Y%m%d')
                    
                    # Fetch just today's OHLCV
                    today_ohlcv = stock.get_market_ohlcv(today_str, today_str, ticker_padded)
                    
                    if not today_ohlcv.empty:
                        # pykrx returns DataFrame with columns: 시가, 고가, 저가, 종가, 거래량
                        row = today_ohlcv.iloc[0]
                        
                        # Only append if we have valid price (> 0) to avoid pre-market zeros
                        if row['종가'] > 0:
                            chart_data.append({
                                'date': today.strftime('%Y-%m-%d'),
                                'open': float(row['시가']),
                                'high': float(row['고가']),
                                'low': float(row['저가']),
                                'close': float(row['종가']),
                                'volume': int(row['거래량'])
                            })
                except Exception as rt_error:
                    print(f"Error fetching real-time data for {ticker_padded}: {rt_error}")
        
        return jsonify({
            'ticker': ticker_padded,
            'data': chart_data
        })
    except Exception as e:
        print(f"Error in get_kr_stock_chart: {e}")
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/ai-summary/<ticker>')
def get_kr_ai_summary(ticker):
    """KR AI 종목 요약"""
    try:
        json_path = 'data/kr_ai_analysis.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            signals = data.get('signals', [])
            for signal in signals:
                if signal.get('ticker') == ticker:
                    return jsonify({
                        'ticker': ticker,
                        'summary': signal.get('ai_analysis', ''),
                        'grade': signal.get('grade', ''),
                        'score': signal.get('score', 0)
                    })
        
        return jsonify({'ticker': ticker, 'summary': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/ai-analysis')
def get_kr_ai_analysis():
    """KR AI 분석 전체"""
    try:
        json_path = 'data/kr_ai_analysis.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({'signals': [], 'generated_at': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/ai-history-dates')
def get_kr_ai_history_dates():
    """AI 분석 히스토리 날짜"""
    try:
        history_dir = os.path.join('data', 'history')
        if not os.path.exists(history_dir):
            return jsonify({'dates': []})
        
        dates = sorted([
            f.replace('.json', '')
            for f in os.listdir(history_dir)
            if f.endswith('.json')
        ], reverse=True)
        
        return jsonify({'dates': dates[:30]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/ai-history/<date>')
def get_kr_ai_history(date):
    """특정 날짜 AI 분석"""
    try:
        history_file = os.path.join('data', 'history', f'{date}.json')
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({'error': 'Date not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/cumulative-return')
def get_kr_cumulative_return():
    """누적 수익률"""
    try:
        perf_path = os.path.join('data', 'performance.json')
        if os.path.exists(perf_path):
            with open(perf_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({'cumulative_return': 0, 'trades': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/performance')
def get_kr_performance():
    """KR 퍼포먼스"""
    try:
        perf_path = os.path.join('data', 'performance.json')
        if os.path.exists(perf_path):
            with open(perf_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        return jsonify({'performance': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/vcp-scan', methods=['POST'])
def kr_vcp_scan():
    """VCP 스캔 실행"""
    try:
        from scheduler import run_vcp_scan
        
        result = run_vcp_scan()
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/update', methods=['POST'])
def kr_update():
    """KR 데이터 업데이트"""
    try:
        from scheduler import run_full_update
        
        result = run_full_update()
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@kr_bp.route('/market-gate')
@kr_bp.route('/market-gate')
def kr_market_gate():
    """KR Market Gate 상태 (Enhanced)"""
    try:
        from market_gate import run_kr_market_gate
        
        # Run enhanced analysis
        res = run_kr_market_gate()
        
        # Helper to safely convert float/NaN
        def safe_float(val):
            import math
            import numpy as np
            if isinstance(val, (float, np.floating)):
                if math.isnan(val) or math.isinf(val):
                    return None
            return val

        # Map sectors to frontend format
        sectors_data = []
        for s in res.sectors:
            sectors_data.append({
                'name': s.name,
                'signal': s.signal.lower(),  # bullish, bearish, neutral
                'change_pct': round(s.change_1d, 2) if safe_float(s.change_1d) is not None else 0,
                'score': s.score
            })
            
        # Determine label based on gate color
        label = "NEUTRAL"
        if res.gate == "GREEN":
            label = "BULLISH"
        elif res.gate == "RED":
            label = "BEARISH"
            
        # Sanitize metrics
        safe_metrics = {}
        for k, v in res.metrics.items():
            safe_metrics[k] = safe_float(v)
            
        return jsonify({
            'status': res.gate,  # RED, YELLOW, GREEN
            'score': res.score,
            'label': label,
            'reasons': res.reasons,
            'sectors': sectors_data,
            'metrics': safe_metrics,
            'updated_at': datetime.now().isoformat()
        })

    except Exception as e:
        traceback.print_exc()
        # Fallback to simple logic if enhanced fails
        try:
            prices_path = os.path.join('data', 'daily_prices.csv')
            if not os.path.exists(prices_path):
                return jsonify({'status': 'NEUTRAL', 'score': 50, 'sectors': []})
            
            df = pd.read_csv(prices_path, dtype={'ticker': str})
            market_df = df[df['ticker'] == '069500'].copy()
            
            if not market_df.empty and len(market_df) > 200:
                last_price = market_df.iloc[-1]['current_price']
                ma200 = market_df['current_price'].rolling(200).mean().iloc[-1]
                
                score = 80 if last_price > ma200 else 20
                status = "RISK_ON" if last_price > ma200 else "RISK_OFF"
                
                return jsonify({
                    'status': status, 
                    'score': score, 
                    'sectors': [],
                    'error': f"Enhanced failed: {str(e)}"
                })
        except:
            pass
            
        return jsonify({'error': str(e), 'sectors': []}), 500



@kr_bp.route('/realtime-prices', methods=['POST'])
def get_kr_realtime_prices():
    """실시간 가격 일괄 조회"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({})

        # 1. Load Ticker Map
        yahoo_map = {}
        ticker_map_path = os.path.join('data', 'kr_market', 'ticker_to_yahoo_map.csv')
        if not os.path.exists(ticker_map_path):
             # Try alternate path just in case
             ticker_map_path = os.path.join('data', 'ticker_to_yahoo_map.csv')

        if os.path.exists(ticker_map_path):
            try:
                map_df = pd.read_csv(ticker_map_path, dtype={'ticker': str})
                yahoo_map = dict(zip(map_df['ticker'].str.zfill(6), map_df['yahoo_ticker']))
            except:
                pass
        
        # 2. Prepare Yahoo Tickers
        yf_tickers = []
        req_ticker_map = {}  # yf_ticker -> request_ticker
        
        for t in tickers:
            orig_t = str(t).zfill(6)
            # Use map if available, else try simple heuristic (KS/KQ logic is hard without db, default to KS)
            # Or assume the caller might send .KS/.KQ? No, frontend sends 6 digits.
            # If map missing, we might fail for Kosdaq.
            # Fallback: Try both? No, too expensive.
            # Just default to .KS if not in map, but usually map should cover it.
            yf_t = yahoo_map.get(orig_t, f"{orig_t}.KS") 
            yf_tickers.append(yf_t)
            req_ticker_map[yf_t] = orig_t

        # 3. Fetch Data
        import yfinance as yf
        # Optimize: 1m interval is good for realtime.
        df = yf.download(yf_tickers, period='1d', interval='1m', progress=False, threads=True)
        
        result = {}
        if not df.empty:
            closes = df['Close']
            
            # Handle Single Ticker Result (Series) vs Multi (DataFrame)
            if len(yf_tickers) == 1:
                val = float(closes.iloc[-1])
                t = req_ticker_map[yf_tickers[0]]
                if val > 0:
                    result[t] = val
            else:
                for yf_t in yf_tickers:
                    try:
                        # yfinance output columns might not match input list order strictly or might skip failed ones
                        if yf_t in closes.columns:
                            val = closes[yf_t].iloc[-1]
                            if pd.notna(val) and float(val) > 0:
                                t = req_ticker_map[yf_t]
                                result[t] = float(val)
                    except:
                        pass
                        
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# Chatbot API Endpoints
# ============================================================

@kr_bp.route('/chatbot', methods=['POST'])
def kr_chatbot():
    """KR 챗봇"""
    try:
        from chatbot import get_chatbot
        
        data = request.get_json() or {}
        message = data.get('message', '')
        
        bot = get_chatbot()
        response = bot.chat(message)
        
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/chatbot/welcome', methods=['GET'])
def kr_chatbot_welcome():
    """챗봇 웰컴 메시지"""
    try:
        from chatbot import get_chatbot
        
        bot = get_chatbot()
        welcome = bot.get_welcome_message()
        
        return jsonify({'message': welcome})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/chatbot/memory', methods=['GET', 'POST', 'DELETE'])
def kr_chatbot_memory():
    """챗봇 메모리 관리"""
    try:
        from chatbot import get_chatbot
        
        bot = get_chatbot()
        
        if request.method == 'GET':
            return jsonify({'memory': bot.get_memory()})
        elif request.method == 'POST':
            data = request.get_json() or {}
            bot.update_memory(data)
            return jsonify({'status': 'ok'})
        elif request.method == 'DELETE':
            bot.clear_memory()
            return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/chatbot/history', methods=['GET', 'DELETE'])
def kr_chatbot_history():
    """챗봇 히스토리"""
    try:
        from chatbot import get_chatbot
        
        bot = get_chatbot()
        
        if request.method == 'GET':
            return jsonify({'history': bot.get_history()})
        elif request.method == 'DELETE':
            bot.clear_history()
            return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@kr_bp.route('/chatbot/status', methods=['GET'])
def kr_chatbot_status():
    """챗봇 상태"""
    try:
        from chatbot import get_chatbot
        
        bot = get_chatbot()
        status = bot.get_status()
        
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@kr_bp.route('/jongga-v2/latest', methods=['GET'])
def get_jongga_v2_latest():
    """종가베팅 v2 최신 결과 조회"""
    try:
        # data 디렉토리 경로 (패키지 루트 기준)
        data_dir = os.path.join(os.path.dirname(current_app.root_path), 'data')
        latest_file = os.path.join(data_dir, 'jongga_v2_latest.json')
        
        if not os.path.exists(latest_file):
            # 파일이 없으면 혹시 날짜별 파일 중 가장 최신 것이라도 찾음
            import glob
            files = glob.glob(os.path.join(data_dir, 'jongga_v2_results_*.json'))
            if not files:
                return jsonify({
                    "date": date.today().isoformat(),
                    "signals": [],
                    "message": "No data available"
                })
            latest_file = max(files, key=os.path.getctime)
            
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return jsonify(data)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@kr_bp.route('/jongga-v2/dates', methods=['GET'])
def get_jongga_v2_dates():
    """데이터가 존재하는 날짜 목록 조회"""
    try:
        data_dir = os.path.join(os.path.dirname(current_app.root_path), 'data')
        # jongga_v2_results_YYYYMMDD.json 패턴 검색
        import glob
        files = glob.glob(os.path.join(data_dir, 'jongga_v2_results_*.json'))
        
        dates = []
        for f in files:
            # 파일명에서 날짜 추출 (jongga_v2_results_20240115.json)
            basename = os.path.basename(f)
            if len(basename) >= 26: # 최소 길이 체크
                input_date = basename[18:26] # 20240115
                formatted = f"{input_date[:4]}-{input_date[4:6]}-{input_date[6:]}"
                dates.append(formatted)
        
        dates.sort(reverse=True) # 최신순 정렬
        return jsonify(dates)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@kr_bp.route('/jongga-v2/history/<date_str>', methods=['GET'])
def get_jongga_v2_history(date_str):
    """
    특정 날짜의 종가베팅 v2 결과 조회
    """
    try:
        base_dir = os.path.join(os.path.dirname(current_app.root_path), 'data')
        filename = f"jongga_v2_results_{date_str}.json"
        
        file_path = os.path.join(base_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Data not found for this date"}), 404
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return jsonify(data)
        
    except Exception as e:
        print(f"Error reading historical data: {e}")
        return jsonify({"error": str(e)}), 500

@kr_bp.route('/jongga-v2/analyze', methods=['POST'])
def analyze_single_stock():
    """
    단일 종목 재분석 요청
    """
    try:
        req_data = request.get_json()
        code = req_data.get('code')
        
        if not code:
            return jsonify({"error": "Stock code is required"}), 400
            
        # Async 함수 실행을 위한 처리
        import asyncio
        from engine.generator import analyze_single_stock_by_code
        
        result = asyncio.run(analyze_single_stock_by_code(code))
        
        if result:
            return jsonify({"status": "success", "signal": result.to_dict()})
        else:
            return jsonify({"status": "failed", "message": "Analysis failed or no signal generated"}), 500
            
    except Exception as e:
        print(f"Error re-analyzing stock {code}: {e}")
        return jsonify({"error": str(e)}), 500

@kr_bp.route('/jongga-v2/run', methods=['POST'])
def run_jongga_v2():
    """
    전체 종가베팅 v2 엔진 실행 (배치)
    """
    try:
        from engine.generator import run_screener
        import asyncio
        
        # 5천만원 기본 자본금으로 실행
        result = asyncio.run(run_screener(capital=50_000_000))
        
        return jsonify({
            "status": "success",
            "date": result.date.isoformat(),
            "filtered_count": result.filtered_count,
            "processing_time": result.processing_time_ms
        })
        
    except Exception as e:
        print(f"Error running Jongga V2 engine: {e}")
        return jsonify({"error": str(e)}), 500
```

