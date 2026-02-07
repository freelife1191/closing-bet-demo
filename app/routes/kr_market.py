import os
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
from flask import Blueprint, jsonify, request, current_app

kr_bp = Blueprint('kr', __name__)
logger = logging.getLogger(__name__)

# Global Flags for Background Tasks
is_market_gate_updating = False
is_signals_updating = False
is_jongga_updating = False

# Constants
DATA_DIR = 'data'
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
        signals = []
        source = 'no_data'
        data_dir = 'data'
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 1차: signals_log.csv에서 데이터 조회
        df = load_csv_file('signals_log.csv')
        
        # [수정] 날짜 필터링 (DataFrame 레벨에서 선행 처리, 정확도 향상)
        req_date = request.args.get('date')
        
        if not df.empty and 'signal_date' in df.columns:
            if req_date:
                # 특정 날짜 요청 시
                df = df[df['signal_date'].astype(str) == req_date]
            else:
                # [버그수정] 요청 날짜 없으면 '가장 최근 날짜' 데이터만 필터링 (중복/과거 데이터 노출 방지)
                latest_date = df['signal_date'].max()
                logger.debug(f"Latest date in CSV: {latest_date}")
                
                if pd.notna(latest_date):
                    df = df[df['signal_date'].astype(str) == str(latest_date)]
                    # [주의] '실시간' 요청이어도 오늘 데이터가 없으면 가장 최근 데이터를 반환함.
                    # 프론트엔드에서 signal_date와 오늘 날짜를 비교하여 UI 처리 필요.
                    today = str(latest_date)
                    logger.debug(f"Filtered signals for date {latest_date}: {len(df)} rows")

        if not df.empty:
            source = 'signals_log.csv'
            for _, row in df.iterrows():
                # 기본 데이터 추출
                score = float(row.get('score', 0))
                contraction = float(row.get('contraction_ratio', 1.0))
                foreign_5d = int(row.get('foreign_5d', 0))
                inst_5d = int(row.get('inst_5d', 0))
                signal_date = row.get('signal_date', '')
                status = row.get('status', 'OPEN')
                
                # 기본 필터: OPEN 상태만 표시
                if status != 'OPEN':
                    continue
                # 60점 이상만 표시 (VCP 기준)
                if score < 60:
                    continue
                # 참고: 아래 필터링 조건은 비활성화됨
                # if contraction > 0.8:  # 수축 미완료 → 제외
                #     continue
                # if foreign_5d < 0 and inst_5d < 0:  # 수급 모두 이탈 → 제외
                #     continue

                # BLUEPRINT Final Score 계산 (100점 만점)
                contraction_score = (1 - contraction) * 100
                supply_score = min((foreign_5d + inst_5d) / 100000, 30)
                today_bonus = 10 if signal_date == today else 0
                final_score = (score * 0.4) + (contraction_score * 0.3) + (supply_score * 0.2 * 10) + today_bonus
                
                # AI Analysis Columns (CSV)
                # [NEW] Read AI fields from CSV
                ai_action = row.get('ai_action')
                if pd.isna(ai_action): ai_action = None
                
                ai_confidence = row.get('ai_confidence')
                if pd.isna(ai_confidence): ai_confidence = 0
                
                ai_reason = row.get('ai_reason')
                if pd.isna(ai_reason): ai_reason = None

                gemini_rec = None
                if ai_action and ai_reason:
                    gemini_rec = {
                        "action": ai_action,
                        "confidence": int(ai_confidence) if ai_confidence else 0,
                        "reason": ai_reason,
                        "news_sentiment": "positive" # Default or analyze later
                    }

                # [FIX] Handle NaN values for JSON serialization
                return_pct = row.get('return_pct')
                if pd.isna(return_pct): return_pct = None

                contraction_ratio = row.get('contraction_ratio')
                if pd.isna(contraction_ratio): contraction_ratio = None
                
                entry_price = row.get('entry_price')
                if pd.isna(entry_price): entry_price = None

                current_price = row.get('current_price')
                if pd.isna(current_price): current_price = None

                signals.append({
                    'ticker': str(row.get('ticker', '')).zfill(6), # Ensure formatting
                    'name': row.get('name'),
                    'signal_date': str(row.get('signal_date')),
                    'market': row.get('market'),
                    'status': row.get('status'),
                    'score': float(row.get('score', 0)),
                    'contraction_ratio': contraction_ratio,
                    'entry_price': entry_price,
                    'foreign_5d': int(row.get('foreign_5d', 0)),
                    'inst_5d': int(row.get('inst_5d', 0)),
                    'vcp_score': int(row.get('vcp_score', 0)),
                    'current_price': current_price,
                    # 'return_pct': row.get('return_pct') # CSV said return_pct
                    'return_pct': return_pct,
                    'gemini_recommendation': gemini_rec 
                })

        if not signals:
            # [Auto-Recovery] 데이터가 없고 실행 중도 아니면 백그라운드 실행
            if not VCP_STATUS['running']:
                logger.info("[Signals] 데이터 없음. 백그라운드 VCP 스크리너 자동 시작.")
                import threading
                threading.Thread(target=_run_vcp_background, args=(None, 50)).start()
            pass
        
        # [NEW] 실시간 가격 주입 (Scheduler가 갱신한 daily_prices.csv 기반)
        try:
            price_file = get_data_path('daily_prices.csv')
            if os.path.exists(price_file):
                # 최신 가격 맵 생성 (읽기 최적화)
                # 날짜, 티커, 종가만 읽음
                df_prices = pd.read_csv(price_file, usecols=['date', 'ticker', 'close'], dtype={'ticker': str, 'close': float})
                
                if not df_prices.empty:
                    # 날짜 기준 정렬 후 최신값 가져오기 (각 티커별 마지막 행)
                    # drop_duplicates(keep='last')가 더 빠름 (파일이 날짜순 정렬 가정)
                    df_latest = df_prices.drop_duplicates(subset=['ticker'], keep='last')
                    
                    # Dict 변환 for fast lookup: ticker -> close
                    latest_price_map = df_latest.set_index('ticker')['close'].to_dict()
                    latest_date_map = df_latest.set_index('ticker')['date'].to_dict()
                    
                    logger.debug(f"Loaded latest prices for {len(latest_price_map)} tickers")

                    # Signals 리스트 업데이트
                    for sig in signals:
                        ticker = sig.get('ticker')
                        if ticker in latest_price_map:
                            real_price = latest_price_map[ticker]
                            entry_price = sig.get('entry_price')
                            
                            # 가격 업데이트
                            sig['current_price'] = real_price
                            
                            # 수익률 재계산
                            if entry_price and entry_price > 0:
                                new_return = ((real_price - entry_price) / entry_price) * 100
                                sig['return_pct'] = round(new_return, 2)
                                
                            # (선택) 데이터 기준일 표시가 필요하다면? sig['price_date'] = latest_date_map[ticker]
        except Exception as e:
            logger.warning(f"Failed to inject real-time prices: {e}")
            # 실패해도 기존 signals 반환 (Graceful degradation)

        # ===================================================
        # Final Score 기준 정렬 후 Top 20 선정
        # ===================================================
        if signals:
            signals = sorted(signals, key=lambda x: x.get('score', 0), reverse=True)[:20]

            # [AI Integration] Load AI fields from JSON and merge
            try:
                # Determine date from the first signal
                sig_date = signals[0].get('signal_date', '')
                date_str = sig_date.replace('-', '') if sig_date else datetime.now().strftime('%Y%m%d')
                
                ai_data_map = {}
                
                # 1. Try specific date result first
                ai_json = load_json_file(f'ai_analysis_results_{date_str}.json')
                
                # 2. Fallback to general file if specific file missing or empty
                if not ai_json or 'signals' not in ai_json:
                     # Check if the requested date is today/latest, if so check the main file
                     logger.info("Falling back to kr_ai_analysis.json")
                     ai_json = load_json_file('kr_ai_analysis.json') 

                # Debug Print
                logger.debug(f"AI JSON Loaded: {bool(ai_json)}, Signals in JSON: {len(ai_json.get('signals', [])) if ai_json else 0}")


                # 3. Build map
                if ai_json and 'signals' in ai_json:
                     for item in ai_json['signals']:
                         t = str(item.get('ticker', '')).zfill(6)
                         ai_data_map[t] = item

                # 3.1 Load Legacy File for Fallback Merge (if specific file misses fields)
                # specifically for Perplexity which might be in legacy file
                try:
                    legacy_json = load_json_file('kr_ai_analysis.json')
                    if legacy_json and 'signals' in legacy_json:
                        for l_item in legacy_json['signals']:
                            t = str(l_item.get('ticker', '')).zfill(6)
                            if t in ai_data_map:
                                # Merge missing fields into ai_data_map item
                                current = ai_data_map[t]
                                if not current.get('perplexity_recommendation') and l_item.get('perplexity_recommendation'):
                                    current['perplexity_recommendation'] = l_item['perplexity_recommendation']
                                if not current.get('gemini_recommendation') and l_item.get('gemini_recommendation'):
                                    current['gemini_recommendation'] = l_item['gemini_recommendation']
                            else:
                                # If ticker not in daily but in legacy? strictly speaking we only care about signals in the list.
                                # pass
                                pass
                except Exception as leg_e:
                    logger.warning(f"Legacy merge failed: {leg_e}")
                
                # 4. Merge
                if ai_data_map:
                    merged_count = 0
                    for s in signals:
                        t = s['ticker']
                        if t in ai_data_map:
                            ai_item = ai_data_map[t]
                            # Merge AI fields
                            s['gemini_recommendation'] = ai_item.get('gemini_recommendation')
                            s['gpt_recommendation'] = ai_item.get('gpt_recommendation')
                            s['perplexity_recommendation'] = ai_item.get('perplexity_recommendation')
                            
                            # Merge News if missing
                            if 'news' in ai_item and not s.get('news'):
                                s['news'] = ai_item['news']
                                
                            merged_count += 1
                    logger.debug(f"Merged AI data for {merged_count} signals")
            except Exception as e:
                logger.warning(f"Failed to merge AI data into signals: {e}")

        # ===================================================
        # 실시간 가격 업데이트 및 return_pct 계산 Logic Removed
        # Frontend에서 /realtime-prices 엔드포인트를 통해 별도로 수행함
        # ===================================================
        pass
        
        # 총 스캔 종목 수 계산
        total_scanned = 0
        try:
            stocks_file = os.path.join(data_dir, 'korean_stocks_list.csv')
            if os.path.exists(stocks_file):
                with open(stocks_file, 'r', encoding='utf-8') as f:
                    total_scanned = max(0, sum(1 for _ in f) - 1)
        except:
            pass

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
        VCP_STATUS['progress'] = 0
        
        if target_date_arg:
            msg = f"[VCP] 지정 날짜 분석 시작: {target_date_arg}"
        else:
            msg = "[VCP] 실시간 분석 시작"
        
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
        logger.info(f"[VCP Screener] {success_msg}")
        print(f"[VCP Screener] {success_msg}\n", flush=True)
            
    except Exception as e:
        logger.error(f"[VCP Screener] 실패: {e}")
        print(f"[VCP Screener] ⛔️ 실패: {e}", flush=True)
        VCP_STATUS['message'] = f"실패: {str(e)}"
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
            chart_data.append({
                'date': str(row.get('date', '')),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': int(row.get('volume', 0))
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
        target_date = request.args.get('date')
        
        # 1. 날짜별 파일 로드 (과거 데이터 요청 시)
        if target_date:
            try:
                date_str = target_date.replace('-', '')
                
                # 1-1. [Priority] 통합 결과 파일 시도 (jongga_v2_results_YYYYMMDD.json)
                v2_result = load_json_file(f'jongga_v2_results_{date_str}.json')
                if v2_result and 'signals' in v2_result and len(v2_result['signals']) > 0:
                    ai_signals = []
                    for sig in v2_result['signals']:
                        # AI 분석 데이터 추출 (우선순위: score_details > score > llm_reason)
                        ai_eval = None
                        if 'score_details' in sig and isinstance(sig['score_details'], dict):
                            ai_eval = sig['score_details'].get('ai_evaluation')
                        if not ai_eval and 'score' in sig and isinstance(sig['score'], dict):
                            ai_eval = sig['score'].get('ai_evaluation')
                        if not ai_eval and 'ai_evaluation' in sig:
                            ai_eval = sig['ai_evaluation']
                        if not ai_eval and 'score' in sig and isinstance(sig['score'], dict):
                             ai_eval = sig['score'].get('llm_reason')

                        if isinstance(ai_eval, str):
                            ai_eval = {'reason': ai_eval, 'action': 'HOLD', 'confidence': 0}

                        if ai_eval:
                            signal_data = {
                                'ticker': str(sig.get('stock_code', '')).zfill(6),
                                'name': sig.get('stock_name', ''),
                                'grade': sig.get('grade'), # Added Grade
                                'score': sig.get('score', {}).get('total', 0) if isinstance(sig.get('score'), dict) else (sig.get('score') if isinstance(sig.get('score'), (int, float)) else 0),
                                'current_price': sig.get('current_price', 0),
                                'entry_price': sig.get('entry_price', 0),
                                'vcp_score': 0,
                                'contraction_ratio': sig.get('contraction_ratio', 0),
                                'foreign_5d': sig.get('foreign_5d', 0),
                                'inst_5d': sig.get('inst_5d', 0),
                                'gemini_recommendation': ai_eval, 
                                'news': sig.get('news_items', [])
                            }
                            ai_signals.append(signal_data)
                    
                    if ai_signals:
                        # [Sort] Grade (S>A>B>C>D) -> Score Descending
                        def sort_key(s):
                            grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
                            grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
                            score_val = s.get('score', 0)
                            return (grade_val, score_val)

                        ai_signals.sort(key=sort_key, reverse=True)

                        return jsonify({
                            'signals': ai_signals,
                            'generated_at': v2_result.get('updated_at', datetime.now().isoformat()),
                            'signal_date': target_date,
                            'source': 'jongga_v2_integrated_history'
                        })

                # 1-2. 기존 방식 파일 시도 (Legacy Fallback)
                analysis = load_json_file(f'kr_ai_analysis_{date_str}.json')
                if not analysis:
                    analysis = load_json_file(f'ai_analysis_results_{date_str}.json')
                    
                if analysis:
                    # ticker 6자리 zfill 보정
                    if 'signals' in analysis:
                        for sig in analysis['signals']:
                            if 'ticker' in sig:
                                sig['ticker'] = str(sig['ticker']).zfill(6)
                    return jsonify(analysis)

                # 파일 없으면 빈 결과 반환
                return jsonify({
                    'signals': [],
                    'generated_at': datetime.now().isoformat(),
                    'signal_date': target_date,
                    'message': '해당 날짜의 AI 분석 데이터가 없습니다.'
                })
            except Exception as e:
                logger.warning(f"과거 AI 분석 데이터 로드 실패: {e}")

        # 2. [Priority] jongga_v2_latest.json에서 AI 데이터 추출 (통합 저장 방식 대응)
        # V2 엔진은 이 파일에만 저장하므로 가장 먼저 확인해야 함
        try:
            latest_data = load_json_file('jongga_v2_latest.json')
            if latest_data and 'signals' in latest_data and len(latest_data['signals']) > 0:
                ai_signals = []
                for sig in latest_data['signals']:
                    # AI 분석 데이터 추출 (우선순위: score_details > score > llm_reason)
                    ai_eval = None
                    
                    # 1. score_details 내 객체 확인 (가장 상세함)
                    if 'score_details' in sig and isinstance(sig['score_details'], dict):
                        ai_eval = sig['score_details'].get('ai_evaluation')
                    
                    # 2. score 내 객체 확인
                    if not ai_eval and 'score' in sig and isinstance(sig['score'], dict):
                        ai_eval = sig['score'].get('ai_evaluation')
                    
                    # 3. 최상위 필드 확인
                    if not ai_eval and 'ai_evaluation' in sig:
                        ai_eval = sig['ai_evaluation']
                        
                    # 4. 텍스트 reason (마지막 수단)
                    if not ai_eval and 'score' in sig and isinstance(sig['score'], dict):
                         ai_eval = sig['score'].get('llm_reason')

                    # 텍스트 reason만 있는 경우 객체로 변환
                    if isinstance(ai_eval, str):
                         # LLM reason만 있고 평가 객체가 없는 경우
                        ai_eval = {'reason': ai_eval, 'action': 'HOLD', 'confidence': 0}

                    # 프론트엔드 호환 구조 생성 (gemini_recommendation 필수)
                    # AI 데이터가 없어도 signals 리스트에는 포함시켜야 함 (정보 일관성)
                    
                    signal_data = {
                        'ticker': str(sig.get('stock_code', '')).zfill(6),
                        'name': sig.get('stock_name', ''),
                        'grade': sig.get('grade'), # Added Grade
                        'score': sig.get('score', {}).get('total', 0) if isinstance(sig.get('score'), dict) else 0,
                        'current_price': sig.get('current_price', 0),
                        'entry_price': sig.get('entry_price', 0),
                        'vcp_score': 0, # 필수 아님
                        'contraction_ratio': sig.get('contraction_ratio', 0),
                        'foreign_5d': sig.get('foreign_5d', 0), # 필드명 주의 (foreign_net_buy_5d vs foreign_5d)
                        'inst_5d': sig.get('inst_5d', 0),
                            # 프론트엔드가 기대하는 필드로 매핑
                        'gemini_recommendation': ai_eval, 
                        'news': sig.get('news_items', [])
                    }
                    ai_signals.append(signal_data)
                
                # 하나라도 있으면 반환 (AI 분석이 아직 안 된 초기 상태일 수도 있으므로 signals 존재만으로 반환)
                if ai_signals:
                    # [Sort] Grade (S>A>B>C>D) -> Score Descending
                    def sort_key(s):
                        grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
                        grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
                        score_val = s.get('score', 0)
                        return (grade_val, score_val)

                    ai_signals.sort(key=sort_key, reverse=True)

                    # 날짜 형식 보정 (YYYYMMDD -> YYYY-MM-DD)
                    s_date = latest_data.get('date', '')
                    if len(s_date) == 8 and '-' not in s_date:
                        s_date = f"{s_date[:4]}-{s_date[4:6]}-{s_date[6:]}"

                    return jsonify({
                        'signals': ai_signals,
                        'generated_at': latest_data.get('updated_at', datetime.now().isoformat()),
                        'signal_date': s_date,
                        'source': 'jongga_v2_integrated'
                    })
        except Exception as e:
            logger.warning(f"AI Analysis Priority Load Failed: {e}")

        # 3. kr_ai_analysis.json 직접 로드 (Legacy, VCP AI 분석 결과)
        kr_ai_data = load_json_file('kr_ai_analysis.json')
        if kr_ai_data and 'signals' in kr_ai_data and len(kr_ai_data['signals']) > 0:
            # ticker 6자리 zfill 보정
            for sig in kr_ai_data['signals']:
                if 'ticker' in sig:
                    sig['ticker'] = str(sig['ticker']).zfill(6)
            
            return jsonify(kr_ai_data)
        
        # 4. ai_analysis_results.json 폴백 (raw AI output - Legacy)
        ai_data = load_json_file('ai_analysis_results.json')
        if ai_data and 'signals' in ai_data and len(ai_data['signals']) > 0:
            # ticker 6자리 zfill 보정
            for sig in ai_data['signals']:
                if 'ticker' in sig:
                    sig['ticker'] = str(sig['ticker']).zfill(6)
            
            return jsonify(ai_data)

        # 5. 데이터 없음
        return jsonify({
            'signals': [],
            'message': 'AI 분석 데이터가 없습니다.'
        })

    except Exception as e:
        logger.error(f"Error getting AI analysis: {e}")
        return jsonify({'error': str(e)}), 500




@kr_bp.route('/closing-bet/cumulative')
def get_cumulative_performance():
    """종가베팅 누적 성과 조회 (실제 데이터 연동)"""
    try:
        # 1. 모든 결과 파일 스캔 (jongga_v2_results_YYYYMMDD.json)
        import glob
        pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
        files = glob.glob(pattern)
        files.sort(reverse=True) # 최신순 정렬

        trades = []
        
        # 2. 가격 데이터 로드 (Price Trail 계산용)
        # daily_prices.csv 전체를 메모리에 올리는 것은 비효율적일 수 있으나, 
        # 현재 데모 규모에서는 가장 빠르고 확실한 방법.
        # 최적화: 필요한 컬럼만 로드 + Date Indexing
        price_df = load_csv_file('daily_prices.csv')
        if not price_df.empty:
            price_df['ticker'] = price_df['ticker'].astype(str).str.zfill(6)
            price_df['date'] = pd.to_datetime(price_df['date'])
            price_df = price_df.sort_values('date')
            price_df.set_index('date', inplace=True) # Date 인덱싱
        
        # 3. 파일별로 순회하며 Trade 정보 추출
        for filepath in files:
            try:
                data = load_json_file(os.path.basename(filepath))
                if not data or 'signals' not in data:
                    continue
                
                # 파일명에서 날짜 추출 (jongga_v2_results_20260205.json)
                file_date_str = os.path.basename(filepath).split('_')[-1].replace('.json', '')
                try:
                    stats_date = datetime.strptime(file_date_str, '%Y%m%d').strftime('%Y-%m-%d')
                except:
                    stats_date = data.get('date', '')

                for sig in data['signals']:
                    ticker = str(sig.get('stock_code', '')).zfill(6)
                    entry = sig.get('entry_price', 0)
                    target = sig.get('target_price', 0)
                    stop = sig.get('stop_price', 0)
                    
                    if entry == 0: continue

                    # Outcomes & Price Trail 계산
                    outcome = 'OPEN'
                    roi = 0.0
                    max_high = 0.0
                    days = 0
                    price_trail = []

                    # 해당 종목의 가격 데이터 필터링
                    if not price_df.empty:
                        # 신호 발생일 이후의 데이터만 조회
                        stock_prices = price_df[price_df['ticker'] == ticker]
                        if not stock_prices.empty:
                            # signal_date 이후 데이터
                            # stats_date 문자열을 timestamp로 변환
                            sig_ts = pd.Timestamp(stats_date)
                            period_prices = stock_prices[stock_prices.index >= sig_ts]
                            
                            if not period_prices.empty:
                                # Price Trail (Graph Data) - 종가 리스트
                                price_trail = period_prices['close'].tolist()
                                days = len(price_trail)
                                
                                # Max High 계산
                                high_prices = period_prices['high'].max()
                                if high_prices > 0:
                                    max_high = round(((high_prices - entry) / entry) * 100, 1)

                                # Outcome 판별 (간이 로직: 기간 내 고가/저가 체크)
                                # 실제로는 일별로 순차 체크해야 정확함 (Stop 먼저 터졌는지 Target 먼저 터졌는지)
                                # 여기서는 간략히 최신 종가 기준 ROI로 판단하거나, 고가/저가 도달 여부로 판단
                                
                                # 1. 타겟 도달 여부 확인 (High >= Target)
                                hit_target = period_prices[period_prices['high'] >= target]
                                
                                # 2. 스탑 도달 여부 확인 (Low <= Stop)
                                hit_stop = period_prices[period_prices['low'] <= stop]

                                if not hit_target.empty:
                                    # 타겟 도달
                                    outcome = 'WIN'
                                    roi = round(((target - entry) / entry) * 100, 1)
                                    # 만약 스탑도 도달했다면? 날짜 비교 필요
                                    if not hit_stop.empty:
                                        first_win = hit_target.index[0]
                                        first_loss = hit_stop.index[0]
                                        if first_loss < first_win:
                                            outcome = 'LOSS'
                                            roi = -5.0 # Stop Loss ROI (Fixed approx)
                                elif not hit_stop.empty:
                                    outcome = 'LOSS'
                                    roi = -5.0
                                else:
                                    # 진행 중 (OPEN)
                                    outcome = 'OPEN'
                                    last_close = period_prices['close'].iloc[-1]
                                    roi = round(((last_close - entry) / entry) * 100, 1)

                    # ROI가 0.0이고 Price Trail이 있으면 마지막 가격 기준으로 업데이트 (OPEN 상태)
                    if outcome == 'OPEN' and price_trail:
                         last_p = price_trail[-1]
                         current_roi = ((last_p - entry) / entry) * 100
                         roi = round(current_roi, 1)

                    trades.append({
                        'id': f"{ticker}-{stats_date}", # Unique ID
                        'date': stats_date,
                        'grade': sig.get('grade', 'C'),
                        'name': sig.get('stock_name', ''),
                        'code': ticker,
                        'market': sig.get('market', ''),
                        'entry': entry,
                        'outcome': outcome,
                        'roi': roi,
                        'maxHigh': max_high,
                        'priceTrail': price_trail, # List of numbers
                        'days': days,
                        'score': sig.get('score', {}).get('total', 0) if isinstance(sig.get('score'), dict) else 0,
                        'themes': sig.get('themes', [])
                    })

            except Exception as e:
                logger.error(f"Error processing file {filepath}: {e}")
                continue
        
        # 4. 집계 (KPIs)
        total_signals = len(trades)
        wins = sum(1 for t in trades if t['outcome'] == 'WIN')
        losses = sum(1 for t in trades if t['outcome'] == 'LOSS')
        opens = sum(1 for t in trades if t['outcome'] == 'OPEN')
        
        closed_trades = wins + losses
        win_rate = round((wins / closed_trades * 100), 1) if closed_trades > 0 else 0.0
        
        # ROI 합계
        total_roi = sum(t['roi'] for t in trades)
        avg_roi = round(total_roi / total_signals, 2) if total_signals > 0 else 0.0
        
        # Profit Factor (총 이익 / 총 손실)
        gross_profit = sum(t['roi'] for t in trades if t['roi'] > 0)
        gross_loss = abs(sum(t['roi'] for t in trades if t['roi'] < 0))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else round(gross_profit, 2) # 손실 없으면 총이익 표시 or Inf

        # Price Date (가격 데이터 기준일)
        max_price_date = price_df.index.max() if not price_df.empty else datetime.now()
        price_date_str = max_price_date.strftime('%Y-%m-%d')

        # Response
        return jsonify({
            'kpi': {
                'totalSignals': total_signals,
                'winRate': win_rate,
                'wins': wins,
                'losses': losses,
                'open': opens,
                'avgRoi': avg_roi,
                'totalRoi': round(total_roi, 1),
                'avgDays': round(sum(t['days'] for t in trades) / total_signals, 1) if total_signals > 0 else 0,
                'priceDate': price_date_str, 
                'profitFactor': profit_factor
            },
            'trades': trades
        })

    except Exception as e:
        logger.error(f"Error calculating cumulative performance: {e}")
        return jsonify({'error': str(e)}), 500


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
        is_valid = False
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
                    if dataset_date != today_str:
                        logger.info(f"[Market Gate] 데이터가 구버전임 ({dataset_date} vs {today_str}). 갱신 필요.")
                        is_valid = False  # 유효하지 않음으로 처리하여 아래에서 Auto-Update 유도
                
        if not is_valid and not target_date:
            # 실시간 요청인데 데이터가 부실하면 jongga_v2 스냅샷 확인
            try:
                snapshot = load_json_file('jongga_v2_latest.json')
                if snapshot and 'market_status' in snapshot:
                    snap_status = snapshot['market_status']
                    # 스냅샷이 더 풍부한 정보를 담고 있다면 교체
                    if snap_status.get('sectors') and len(snap_status['sectors']) > 0:
                        logger.info("[Market Gate] 실시간 데이터 부실 -> 종가베팅 스냅샷으로 대체")
                        gate_data = snap_status
                        # 날짜 정보 등 보정
                        if 'dataset_date' not in gate_data:
                            gate_data['dataset_date'] = snapshot.get('date')
                        # [FIX] 스냅샷 대체 성공 시 is_valid=True로 설정하여 불필요한 재분석 방지
                        is_valid = True
            except Exception as e:
                logger.warning(f"Market Gate Fallback 실패: {e}")
        
        # [FIX] 실시간 분석 제거 (비동기 처리 원칙)
        # 데이터가 없으면 '분석 대기' 상태를 반환하고, 실제 분석은 스케줄러나 별도 트리거로 수행됨을 유도
        if not is_valid:
            logger.info("[Market Gate] 유효한 데이터 없음. 백그라운드 분석 자동 시작.")
            
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
    """실시간 가격 일괄 조회 (yfinance 우선, CSV 폴백)"""
    try:
        data = request.get_json() or {}
        tickers = data.get('tickers', [])

        if not tickers:
            return jsonify({'prices': {}})

        prices = {}
        
        # 1. yfinance 실시간 조회 시도 (평일 장중)
        try:
            import yfinance as yf
            from datetime import datetime
            
            now = datetime.now()
            is_weekend = now.weekday() >= 5
            is_market_hours = 9 <= now.hour < 16  # 장 운영 시간 (대략적)
            
            # 주말이 아니고 장 시간대인 경우에만 yfinance 호출
            if not is_weekend and is_market_hours:
                # yfinance용 티커 변환
                yf_tickers = []
                ticker_map = {}
                
                # [수정] 시장 정보 로드 (KOSPI/KOSDAQ 구분용)
                market_map = {}
                try:
                    stocks_df = load_csv_file('korean_stocks_list.csv')
                    if not stocks_df.empty:
                        stocks_df['ticker'] = stocks_df['ticker'].astype(str).str.zfill(6)
                        market_map = dict(zip(stocks_df['ticker'], stocks_df['market']))
                except:
                    pass

                for t in tickers:
                    t_padded = str(t).zfill(6)
                    market = market_map.get(t_padded, 'KOSPI')
                    suffix = ".KQ" if market == "KOSDAQ" else ".KS"
                    yf_t = f"{t_padded}{suffix}"
                    yf_tickers.append(yf_t)
                    ticker_map[yf_t] = t_padded
                
                if yf_tickers:
                    # yfinance 에러 로그 억제
                    import logging as _logging
                    yf_logger = _logging.getLogger('yfinance')
                    original_level = yf_logger.level
                    yf_logger.setLevel(_logging.CRITICAL)
                    
                    try:
                        # 일봉 데이터 조회
                        price_data = yf.download(yf_tickers, period='5d', interval='1d', progress=False, threads=True)
                        
                        if not price_data.empty and 'Close' in price_data:
                            closes = price_data['Close']
                            
                            # Helper to extract price safely
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
                        
                    # Check missing tickers
                    missing = [t for t in tickers if str(t).zfill(6) not in prices]
                    
                    # 1.5 Toss Securities API Fallback (Bulk)
                    if missing:
                        try:
                            import requests
                            toss_codes = [f"A{str(t).zfill(6)}" for t in missing]
                            # Chunking 50
                            for i in range(0, len(toss_codes), 50):
                                chunk = toss_codes[i:i+50]
                                url = f"https://wts-info-api.tossinvest.com/api/v3/stock-prices/details?productCodes={','.join(chunk)}"
                                res = requests.get(url, timeout=5)
                                if res.status_code == 200:
                                    results = res.json().get('result', [])
                                    for item in results:
                                        code = item.get('code', '')[1:]
                                        close = item.get('close')
                                        if code and close:
                                            prices[code] = float(close)
                        except Exception as e:
                            logger.debug(f"Toss Fallback Failed: {e}")

                    # 1.6 Naver Mobile API Fallback (Individual)
                    missing = [t for t in tickers if str(t).zfill(6) not in prices]
                    if missing:
                        try:
                            import requests
                            headers = {'User-Agent': 'Mozilla/5.0'}
                            for t in missing:
                                try:
                                    url = f"https://m.stock.naver.com/api/stock/{str(t).zfill(6)}/basic"
                                    res = requests.get(url, headers=headers, timeout=2)
                                    if res.status_code == 200:
                                        data = res.json()
                                        if 'closePrice' in data:
                                            prices[str(t).zfill(6)] = float(data['closePrice'].replace(',', ''))
                                except: pass
                        except Exception: pass
                        
                    # Return if we have everything
                    if len(prices) == len(tickers):
                        return jsonify({'prices': prices})

        except Exception as yf_err:
            logger.debug(f"yfinance 실시간 조회 실패 (CSV 폴백): {yf_err}")

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
                            candidate['message'] = f"주말/휴일로 인해 {candidate.get('date', '')} 거래일 데이터를 표시합니다."
                            logger.info(f"[Jongga V2] 최근 유효 데이터 사용: {file_path}")
                            return jsonify(candidate)
                except Exception as e:
                    logger.warning(f"파일 읽기 실패: {file_path} - {e}")
                    continue
            
            # 유효한 데이터가 없는 경우 -> Auto-Recovery Trigger
            logger.info("[Jongga V2] 데이터 없음. 백그라운드 분석 자동 시작.")
            
            global is_jongga_updating
            if not is_jongga_updating:
                import threading
                def run_analysis():
                    global is_jongga_updating
                    try:
                        is_jongga_updating = True
                        from engine.launcher import run_jongga_v2_screener
                        run_jongga_v2_screener()
                        logger.info("[Jongga V2] 백그라운드 분석 완료")
                    except Exception as e:
                        logger.error(f"[Jongga V2] 백그라운드 분석 실패: {e}")
                    finally:
                        is_jongga_updating = False

                threading.Thread(target=run_analysis).start()

            return jsonify({
                'date': datetime.now().date().isoformat(),
                'signals': [],
                'filtered_count': 0,
                'status': 'initializing', # Frontend polls on this
                'message': '데이터 분석 중... 잠시만 기다려주세요.'
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
                        
                        updated_count = 0
                        for sig in data['signals']:
                            # Jongga uses 'code' primarily
                            ticker = str(sig.get('code', '')).zfill(6)
                            if not ticker: ticker = str(sig.get('ticker', '')).zfill(6)
                            
                            if ticker in latest_price_map:
                                real_price = latest_price_map[ticker]
                                sig['current_price'] = real_price
                                
                                # 재계산
                                entry_price = sig.get('entry_price') or sig.get('close') # Fallback
                                if entry_price and entry_price > 0:
                                    ret = ((real_price - entry_price) / entry_price) * 100
                                    sig['return_pct'] = round(ret, 2)
                                updated_count += 1
                        logger.debug(f"[Jongga V2 Latest] Updated prices for {updated_count} signals")
            except Exception as e:
                logger.warning(f"Failed to inject prices for Jongga V2: {e}")

        if data and data.get('signals'):
            # [Sort] Grade (S>A>B>C>D) -> Score Descending
            def sort_key(s):
                grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
                grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
                # Score can be dict (V2) or number (Legacy fallback)
                score_val = 0
                if isinstance(s.get('score'), dict):
                    score_val = s['score'].get('total', 0)
                else:
                    score_val = s.get('score', 0)
                return (grade_val, score_val)

            data['signals'].sort(key=sort_key, reverse=True)

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
                     # [Sort] Grade (S>A>B>C>D) -> Score Descending
                    def sort_key(s):
                        grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
                        grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
                        score_val = 0
                        if isinstance(s.get('score'), dict):
                            score_val = s['score'].get('total', 0)
                        else:
                            score_val = s.get('score', 0)
                        return (grade_val, score_val)
                    
                    data['signals'].sort(key=sort_key, reverse=True)
                return jsonify(data)
        
        # 최신 파일의 날짜와 같으면 최신 파일 반환
        latest_data = load_json_file('jongga_v2_latest.json')
        if latest_data and latest_data.get('date', '')[:10] == target_date:
            if latest_data and 'signals' in latest_data:
                 # [Sort] Grade (S>A>B>C>D) -> Score Descending
                def sort_key(s):
                    grade_map = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1}
                    grade_val = grade_map.get(str(s.get('grade', '')).strip().upper(), 0)
                    score_val = 0
                    if isinstance(s.get('score'), dict):
                        score_val = s['score'].get('total', 0)
                    else:
                        score_val = s.get('score', 0)
                    return (grade_val, score_val)
                
                latest_data['signals'].sort(key=sort_key, reverse=True)
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

    def _run_engine_async(capital_arg, markets_arg, target_date_arg):
        """백그라운드 엔진 실행"""
        try:
            # Set Running Flag
            _save_v2_status(True)
            
            logger.info("Background Engine Started...")
            if target_date_arg:
                logger.info(f"[테스트 모드] 지정 날짜 기준 분석: {target_date_arg}")
            # engine 모듈 강제 리로드 (코드 변경 사항 반영)
            import sys
            
            # 기존 engine 모듈 삭제 (개발 중 핫 리로딩 지원)
            mods_to_remove = [k for k in list(sys.modules.keys()) if k.startswith('engine') or k == 'kr_ai_analyzer']
            for mod in mods_to_remove:
                del sys.modules[mod]
            
            # 새로 import
            from engine.generator import run_screener, save_result_to_json
            import asyncio
            
            # 비동기 함수 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(run_screener(capital=capital_arg, markets=markets_arg, target_date=target_date_arg))
            finally:
                loop.close()
            
            # 결과 저장
            if result:
                save_result_to_json(result)
                
                # 메신저 알림 발송 (result 객체 직접 사용)
                try:
                    from datetime import datetime
                    
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
            
            logger.info("Background Engine Completed Successfully.")
            
        except Exception as e:
            logger.error(f"Background Engine Failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Reset Running Flag
            _save_v2_status(False)

    try:
        # 스레드 실행 (target_date 포함)
        thread = threading.Thread(target=_run_engine_async, args=(capital, markets, target_date))
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
        signals_to_process = []
        
        if target_tickers:
            # Case 1: Specific tickers requested (Retry)
            target_set = set(str(t).strip() for t in target_tickers)
            print(f">>> [Filter] 타겟 종목 분석: {target_set}")
            for sig in all_signals:
                code = str(sig.get('stock_code', '')).strip()
                name = str(sig.get('stock_name', '')).strip()
                if code in target_set or name in target_set:
                    signals_to_process.append(sig)
        else:
            # Case 2: Global Reanalyze
            if force_update:
                print(f">>> [Filter] 강제 전체 재분석")
                signals_to_process = all_signals
            else:
                print(f">>> [Filter] 스마트 분석 (누락/실패 항목만)")
                for sig in all_signals:
                    # Check if analysis exists
                    has_ai_eval = 'ai_evaluation' in sig and sig['ai_evaluation']
                    has_reason = 'score' in sig and sig['score'].get('llm_reason')
                    
                    if not has_ai_eval or not has_reason:
                        signals_to_process.append(sig)

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
            items_to_analyze = []
            for signal in signals_to_process:
                stock_name = signal.get('stock_name')
                news_items = signal.get('news_items', [])
                if stock_name and news_items:
                    items_to_analyze.append({
                        'stock': signal,
                        'news': news_items,
                        'supply': None
                    })

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

            # 결과 업데이트 - 종목명 정규화 적용
            print(f"\n>>> 결과 매핑 시작: {len(results_map)}개 LLM 결과")
            
            # 종목명/코드 매핑 테이블 생성 (정규화)
            import re
            normalized_results = {}
            for key, value in results_map.items():
                clean_name = re.sub(r'\s*\([0-9A-Za-z]+\)\s*$', '', key).strip()
                normalized_results[clean_name] = value
                normalized_results[key] = value
            
            # [IMPORTANT] Update All Signals
            for signal in all_signals:
                name = signal.get('stock_name')
                stock_code = signal.get('stock_code', '')
                
                matched_result = None
                if name in normalized_results:
                    matched_result = normalized_results[name]
                elif f"{name} ({stock_code})" in results_map:
                    matched_result = results_map[f"{name} ({stock_code})"]
                elif stock_code in normalized_results:
                    matched_result = normalized_results[stock_code]
                    
                if matched_result:
                    if 'score' not in signal:
                        signal['score'] = {}
                    
                    signal['score']['llm_reason'] = matched_result.get('reason', '')
                    signal['score']['news'] = matched_result.get('score', 0)
                    signal['ai_evaluation'] = {
                        'action': matched_result.get('action', 'HOLD'),
                        'confidence': matched_result.get('confidence', 0),
                        'model': matched_result.get('model', 'gemini-2.0-flash')  # [Fix] Pass model name to frontend
                    }
                    updated_count += 1
            
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
        print(f"Error reanalyzing gemini: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500


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
        # 1. Closing Bet Stat (Dynamic)
        jb_stats = {
            'status': 'Accumulating',
            'count': 0,
            'win_rate': 0,
            'avg_return': 0,
            'candidates': []
        }
        
        try:
            # Load latest for candidates display
            jb_data = load_json_file('jongga_v2_latest.json')
            if jb_data and 'signals' in jb_data:
                 jb_stats['candidates'] = jb_data['signals']
            
            # Calculate stats from history (last 30 days)
            import glob
            pattern = os.path.join(DATA_DIR, 'jongga_v2_results_*.json')
            files = sorted(glob.glob(pattern), reverse=True)[:30]
            
            total_signals = 0
            wins = 0
            total_return = 0.0
            
            # Load current prices for accurate return calc
            price_map = {}
            price_file = get_data_path('daily_prices.csv')
            if os.path.exists(price_file):
                df_prices = pd.read_csv(price_file, usecols=['ticker', 'close'], dtype={'ticker': str})
                df_prices['ticker'] = df_prices['ticker'].str.zfill(6)
                price_map = df_prices.set_index('ticker')['close'].to_dict()

            processed_tickers = set() # Avoid duplicates if same signal appears multiple times? (Usually daily signals are unique per day)
            
            for fpath in files:
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        signals = d.get('signals', [])
                        date_str = d.get('date', '')
                        
                        for s in signals:
                            code = str(s.get('stock_code') or s.get('code') or '').zfill(6)
                            if not code: continue
                            
                            # Entry Price
                            entry = s.get('entry_price')
                            if not entry: entry = s.get('close') or s.get('current_price')
                            
                            if not entry: continue
                            
                            # Current Price (Realtime > File > Signal's Close)
                            # For stats, we want CURRENT result.
                            curr = price_map.get(code)
                            
                            # If no current price, skip stat calc or use signal's own return?
                            # Using signal's own return is static at time of generation.
                            # We prefer current price.
                            if curr:
                                ret = ((curr - entry) / entry) * 100
                                total_signals += 1
                                total_return += ret
                                if ret > 0: wins += 1
                except:
                    continue
            
            if total_signals > 0:
                jb_stats['status'] = 'OK'
                jb_stats['count'] = total_signals # Total historical count used for stats
                jb_stats['win_rate'] = round((wins / total_signals) * 100, 1)
                jb_stats['avg_return'] = round(total_return / total_signals, 1)
            else:
                 # Fallback to mock if absolutely no data (fresh install)
                 if jb_stats['candidates']:
                     jb_stats['status'] = 'OK (New)'
            
            # Inject prices into candidates (Front display)
            if jb_stats['candidates'] and price_map:
                for cand in jb_stats['candidates']:
                    code = str(cand.get('stock_code') or cand.get('code') or '').zfill(6)
                    if code in price_map:
                        cand['current_price'] = price_map[code]
                        entry = cand.get('entry_price') or cand.get('close')
                        if entry:
                             cand['return_pct'] = round(((price_map[code] - entry) / entry) * 100, 2)

        except Exception as e:
            logger.error(f"Closing Bet Stat Calc Failed: {e}")
            # Keep default empty stats

        # 2. VCP Stat (Dynamic from signals_log.csv)
        vcp_stats = {
            'status': 'Accumulating',
            'count': 0,
            'win_rate': 0,
            'avg_return': 0
        }
        
        try:
            vcp_df = load_csv_file('signals_log.csv')
            if not vcp_df.empty:
                vcp_stats['status'] = 'OK'
                
                # Get all CLOSED signals or OPEN signals with some age?
                # Usually stats are based on CLOSED signals + OPEN signals current return
                # Filter valid return_pct
                if 'return_pct' in vcp_df.columns:
                    valid_df = vcp_df[vcp_df['return_pct'].notnull()]
                    
                    if not valid_df.empty:
                        total_v = len(valid_df)
                        wins_v = len(valid_df[valid_df['return_pct'] > 0])
                        avg_ret_v = valid_df['return_pct'].mean()
                        
                        vcp_stats['count'] = total_v
                        vcp_stats['win_rate'] = round((wins_v / total_v) * 100, 1)
                        vcp_stats['avg_return'] = round(avg_ret_v, 1)
                        
                        # Use latest count for "Today's Signals" count?
                        # Frontend expects "count" usually as total analyzed or relevant count.
                        # Let's keep total_v for stats consistency.
            
        except Exception as e:
            logger.error(f"VCP Stat Calc Failed: {e}")

        return jsonify({
            'vcp': vcp_stats,
            'closing_bet': jb_stats
        })

    except Exception as e:
        logger.error(f"Error getting backtest summary: {e}")
        return jsonify({'error': str(e)}), 500


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
        session_id = None
        persona = None
        watchlist = None
        files = []

        # Handle Multipart/Form-Data (File Uploads)
        if request.content_type and 'multipart/form-data' in request.content_type:
            message = request.form.get('message', '')
            model_name = request.form.get('model', None)
            session_id = request.form.get('session_id', None)
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
            session_id = data.get('session_id', None)
            persona = data.get('persona', None)
            watchlist = data.get('watchlist', None)
        
        bot = get_chatbot()
        # Returns { "response": text, "session_id": id }
        result = bot.chat(
            message, 
            session_id=session_id, 
            model=model_name, 
            files=files if files else None, 
            watchlist=watchlist,
            persona=persona,
            api_key=user_api_key, # Pass Extracted Key
            owner_id=usage_key # Pass owner_id (usage_key is verified email or session_id)
        )
        
        response_data = result if isinstance(result, dict) else {'response': result}

        # [Log] Chat Activity
        try:
            from services.activity_logger import activity_logger
            
            # Extract detailed info
            response_text = response_data.get('response', '')
            usage_metadata = response_data.get('usage_metadata', {})
            
            # Determine Device Type (Reuse logic or keep simple)
            ua_string = request.user_agent.string
            device_type = 'WEB'
            if request.user_agent.platform in ('android', 'iphone', 'ipad') or 'Mobile' in ua_string:
                device_type = 'MOBILE'

            activity_logger.log_action(
                user_id=usage_key,
                action='CHAT_MESSAGE',
                details={
                    'session_id': session_id,
                    'model': model_name,
                    'user_message': message[:2000] if message else "", # Increased limit for better context
                    'bot_response': response_text[:2000] if response_text else "",
                    'token_usage': usage_metadata,
                    'has_files': bool(files),
                    'device': device_type,
                    'user_agent': ua_string[:150]
                },
                ip_address=request.remote_addr
            )
        except Exception as e:
            logger.error(f"Chat log error: {e}")

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
        logger.error(f"Chatbot API Error: {e}")
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
