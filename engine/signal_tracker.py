#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - Signal Tracker
실시간 시그널 기록 및 성과 추적 시스템

기능:
1. 오늘의 시그널 탐지 및 기록
2. 과거 시그널 성과 자동 업데이트
3. 전략 성과 통계 리포트
4. 점진적 전략 개선용 데이터 축적
"""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SignalTracker:
    """시그널 추적 및 성과 기록"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        self.signals_log_path = os.path.join(self.data_dir, 'signals_log.csv')
        self.performance_path = os.path.join(self.data_dir, 'strategy_performance.json')
        
        # 전략 파라미터 (BLUEPRINT 검증된 최적값)
        self.strategy_params = {
            'foreign_min': 50000,        # 최소 외인 순매수
            'consecutive_min': 3,        # 최소 연속 매수일
            'contraction_max': 0.8,      # 최대 축소비
            'near_high_pct': 0.92,       # 고점 대비 %
            'hold_days': 5,              # 기본 보유 기간
            'stop_loss_pct': 7.0,        # 손절 %
        }
        
        # 로컬 가격 데이터 로드
        self.price_df = self._load_price_data()
        
        logger.info("✅ Signal Tracker 초기화 완료")
    
    def _load_price_data(self) -> pd.DataFrame:
        """로컬 가격 데이터 로드"""
        price_path = os.path.join(self.data_dir, 'daily_prices.csv')
        
        if os.path.exists(price_path):
            df = pd.read_csv(price_path, low_memory=False)
            df['ticker'] = df['ticker'].astype(str).str.zfill(6)
            df['date'] = pd.to_datetime(df['date'])
            logger.info(f"   📊 가격 데이터 로드: {len(df):,}개 레코드")
            return df
        else:
            logger.warning("⚠️ 가격 데이터 파일이 없습니다")
            return pd.DataFrame()
    
    def detect_vcp_forming(self, ticker: str) -> Tuple[bool, Dict]:
        """VCP 형성 초기 감지 (로컬 데이터 사용)"""
        try:
            if self.price_df.empty:
                return False, {}
            
            # 해당 종목 가격 데이터
            ticker_prices = self.price_df[self.price_df['ticker'] == ticker].sort_values('date')
            
            if len(ticker_prices) < 20:
                return False, {}
            
            recent = ticker_prices.tail(20)
            
            # 컬럼명 확인
            price_col = 'current_price' if 'current_price' in recent.columns else 'close'
            high_col = 'high' if 'high' in recent.columns else price_col
            low_col = 'low' if 'low' in recent.columns else price_col
            
            # 전반부/후반부 범위
            first_half = recent.head(10)
            second_half = recent.tail(10)
            
            range_first = first_half[high_col].max() - first_half[low_col].min()
            range_second = second_half[high_col].max() - second_half[low_col].min()
            
            if range_first == 0:
                return False, {}
            
            contraction = range_second / range_first
            current_price = recent.iloc[-1][price_col]
            recent_high = recent[price_col].max()
            
            near_high = current_price >= recent_high * self.strategy_params['near_high_pct']
            contracting = contraction <= self.strategy_params['contraction_max']
            
            is_vcp = near_high and contracting
            
            return is_vcp, {
                'contraction_ratio': round(contraction, 3),
                'price_from_high_pct': round((recent_high - current_price) / recent_high * 100, 2),
                'current_price': round(current_price, 0),
                'recent_high': round(recent_high, 0),
                'near_high': near_high,
                'is_uptrend': current_price > recent.iloc[0][price_col] * 0.98
            }
            
        except Exception as e:
            logger.warning(f"⚠️ {ticker} VCP 감지 실패: {e}")
            return False, {}
    
    def scan_today_signals(self) -> pd.DataFrame:
        """오늘의 시그널 스캔"""
        logger.info("🔍 오늘의 시그널 스캔 시작...")
        
        inst_path = os.path.join(self.data_dir, 'all_institutional_trend_data.csv')
        
        if not os.path.exists(inst_path):
            logger.error("❌ 수급 데이터 파일이 없습니다")
            return pd.DataFrame()
        
        try:
            # Raw Data 로드
            raw_df = pd.read_csv(inst_path, encoding='utf-8-sig')
            raw_df['ticker'] = raw_df['ticker'].astype(str).str.zfill(6)
            
            # 수급 데이터 가공 (5일 누적 및 점수 계산)
            processed_data = []
            
            # 종목별 그룹화
            for ticker, group in raw_df.groupby('ticker'):
                group = group.sort_values('date')
                if len(group) < 5:
                    continue
                
                recent = group.tail(5)
                foreign_5d = recent['foreign_buy'].sum()
                inst_5d = recent['inst_buy'].sum()
                
                # 수급 점수 계산 (init_data.py 로직 참조)
                score = 0
                # 외국인
                if foreign_5d > 1000000000: score += 40
                elif foreign_5d > 500000000: score += 25
                elif foreign_5d > 0: score += 10
                
                # 기관
                if inst_5d > 500000000: score += 30
                elif inst_5d > 200000000: score += 20
                elif inst_5d > 0: score += 10
                
                # 연속 매수
                consecutive = 0
                for val in reversed(recent['foreign_buy'].values):
                    if val > 0: consecutive += 1
                    else: break
                score += min(consecutive * 6, 30)
                
                # 1차 필터: 외인 매수 최소금액 & 점수 커트라인 (60 -> 40 완화)
                if foreign_5d >= self.strategy_params['foreign_min'] and score >= 40:
                    processed_data.append({
                        'ticker': ticker,
                        'foreign_net_buy_5d': foreign_5d,
                        'institutional_net_buy_5d': inst_5d,
                        'supply_demand_index': score
                    })
            
            df = pd.DataFrame(processed_data)
            
            if df.empty:
                logger.info("   조건을 만족하는 수급 종목이 없습니다.")
                return pd.DataFrame()
            
            logger.info(f"   기본 수급 필터 통과: {len(df)}개 종목")
            
            # VCP 필터 적용
            vcp_signals = []
            for _, row in df.iterrows():
                ticker = row['ticker']
                # 종목명 찾기 (korean_stocks_list.csv 활용 권장되나 여기선 생략하거나 로드)
                name = str(ticker) # 임시
                
                is_vcp, vcp_info = self.detect_vcp_forming(ticker)
                
                if is_vcp:
                    signal = {
                        'signal_date': datetime.now().strftime('%Y-%m-%d'),
                        'ticker': ticker,
                        'name': name, # 이름은 나중에 매핑 필요할 수 있음
                        'foreign_5d': row['foreign_net_buy_5d'],
                        'inst_5d': row['institutional_net_buy_5d'],
                        'score': row['supply_demand_index'],
                        'contraction_ratio': vcp_info.get('contraction_ratio'),
                        # [FIX] VCP Entry Price는 현재가가 아닌 '돌파 매수점(Recent High)'으로 설정
                        'entry_price': vcp_info.get('recent_high'),
                        'current_price': vcp_info.get('current_price'),
                        'status': 'OPEN',
                        'exit_price': None,
                        'exit_date': None,
                        'return_pct': None,
                        'hold_days': 0
                    }
                    vcp_signals.append(signal)
            
            signals_df = pd.DataFrame(vcp_signals)
            
            # 종목명 보정 (korean_stocks_list.csv가 있다면)
            stocks_path = os.path.join(self.data_dir, 'korean_stocks_list.csv')
            if os.path.exists(stocks_path) and not signals_df.empty:
                try:
                    stocks_info = pd.read_csv(stocks_path, dtype={'ticker': str})
                    stocks_info['ticker'] = stocks_info['ticker'].str.zfill(6)
                    name_map = stocks_info.set_index('ticker')['name'].to_dict()
                    signals_df['name'] = signals_df['ticker'].map(name_map).fillna(signals_df['ticker'])
                except:
                    pass
            
            if not signals_df.empty:
                self._append_to_log(signals_df)
            
            logger.info(f"✅ 오늘 VCP 시그널: {len(signals_df)}개")
            return signals_df
            
        except Exception as e:
            logger.error(f"시그널 스캔 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _append_to_log(self, new_signals: pd.DataFrame):
        """시그널 로그에 추가"""
        if os.path.exists(self.signals_log_path):
            existing = pd.read_csv(self.signals_log_path, encoding='utf-8-sig')
            existing['ticker'] = existing['ticker'].astype(str).str.zfill(6)
            
            # 중복 제거 (같은 날짜 + 같은 티커)
            today = datetime.now().strftime('%Y-%m-%d')
            existing = existing[~((existing['signal_date'] == today) & 
                                  (existing['ticker'].isin(new_signals['ticker'])))]
            
            combined = pd.concat([existing, new_signals], ignore_index=True)
        else:
            combined = new_signals
        
        combined.to_csv(self.signals_log_path, index=False, encoding='utf-8-sig')
        logger.info(f"   📝 시그널 로그 저장: {len(combined)}개")
    
    def update_open_signals(self):
        """열린 시그널 성과 업데이트"""
        if not os.path.exists(self.signals_log_path):
            logger.warning("⚠️ 시그널 로그 파일이 없습니다")
            return
        
        df = pd.read_csv(self.signals_log_path, encoding='utf-8-sig')
        df['ticker'] = df['ticker'].astype(str).str.zfill(6)
        
        open_signals = df[df['status'] == 'OPEN']
        
        if len(open_signals) == 0:
            logger.info("열린 시그널이 없습니다")
            return
        
        price_col = 'current_price' if 'current_price' in self.price_df.columns else 'close'
        updated_count = 0
        
        for idx, row in open_signals.iterrows():
            ticker = row['ticker']
            entry_price = row['entry_price']
            signal_date = pd.to_datetime(row['signal_date'])
            hold_days = (datetime.now() - signal_date).days
            
            ticker_prices = self.price_df[self.price_df['ticker'] == ticker].sort_values('date')
            
            if len(ticker_prices) > 0:
                current_price = ticker_prices.iloc[-1][price_col]
                return_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                
                # 항상 현재가 및 등락률 업데이트
                df.at[idx, 'current_price'] = round(current_price, 0)
                df.at[idx, 'return_pct'] = round(return_pct, 2)
                
                # 청산 조건 체크
                should_close = False
                close_reason = None
                
                if return_pct <= -self.strategy_params['stop_loss_pct']:
                    should_close = True
                    close_reason = "STOP_LOSS"
                elif hold_days >= self.strategy_params['hold_days']:
                    should_close = True
                    close_reason = "TIME_EXIT"
                
                if should_close:
                    df.at[idx, 'status'] = 'CLOSED'
                    df.at[idx, 'exit_price'] = round(current_price, 0)
                    df.at[idx, 'exit_date'] = datetime.now().strftime('%Y-%m-%d')
                    df.at[idx, 'return_pct'] = round(return_pct, 2)
                    df.at[idx, 'hold_days'] = hold_days
                    updated_count += 1
                    logger.info(f"   🔴 {ticker} 청산 ({close_reason}): {return_pct:.2f}%")
        
        df.to_csv(self.signals_log_path, index=False, encoding='utf-8-sig')
        logger.info(f"✅ 시그널 업데이트 완료: {updated_count}개 청산")
    
    def get_performance_report(self) -> Dict:
        """전략 성과 리포트"""
        if not os.path.exists(self.signals_log_path):
            return {"error": "시그널 로그가 없습니다"}
        
        df = pd.read_csv(self.signals_log_path, encoding='utf-8-sig')
        
        closed = df[df['status'] == 'CLOSED']
        open_signals = df[df['status'] == 'OPEN']
        
        if len(closed) == 0:
            return {
                "message": "아직 청산된 시그널이 없습니다",
                "open_signals": len(open_signals),
                "total_signals": len(df)
            }
        
        wins = len(closed[closed['return_pct'] > 0])
        losses = len(closed[closed['return_pct'] <= 0])
        
        # 수익/손실 총합
        total_profit = closed[closed['return_pct'] > 0]['return_pct'].sum()
        total_loss = abs(closed[closed['return_pct'] <= 0]['return_pct'].sum())
        
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        return {
            "period": f"{closed['signal_date'].min()} ~ {closed['exit_date'].max()}",
            "total_signals": len(df),
            "closed_signals": len(closed),
            "open_signals": len(open_signals),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(closed) * 100, 1) if len(closed) > 0 else 0,
            "avg_return": round(closed['return_pct'].mean(), 2),
            "total_return": round(closed['return_pct'].sum(), 2),
            "best_trade": round(closed['return_pct'].max(), 2),
            "worst_trade": round(closed['return_pct'].min(), 2),
            "avg_hold_days": round(closed['hold_days'].mean(), 1),
            "profit_factor": round(profit_factor, 2),
            "strategy_params": self.strategy_params
        }
    
    def calculate_vcp_score(self, vcp_info: Dict) -> float:
        """VCP 신호 강도 점수 (0-20점) - BLUEPRINT 기준"""
        if not vcp_info:
            return 0.0
        
        score = 0.0
        
        # 축소 비율이 낮을수록 고점수
        contraction = vcp_info.get('contraction_ratio', 1.0)
        if contraction <= 0.3:
            score += 10.0
        elif contraction <= 0.5:
            score += 7.0
        elif contraction <= 0.7:
            score += 4.0
        
        # 고점 근처 보너스
        if vcp_info.get('near_high', False):
            score += 5.0
        
        # 상승 추세 보너스
        if vcp_info.get('is_uptrend', False):
            score += 5.0
        
        return score


        return score


    async def analyze_signals_with_ai(self, signals_df: pd.DataFrame) -> pd.DataFrame:
        """시그널 AI 분석 수행 (vcp_ai_analyzer 연동)"""
        if signals_df.empty:
            logger.warning("AI 분석할 시그널이 없습니다")
            return signals_df

        from engine.vcp_ai_analyzer import get_vcp_analyzer
        analyzer = get_vcp_analyzer()
        
        if not analyzer.get_available_providers():
            logger.warning("사용 가능한 AI Provider가 없습니다")
            return signals_df
        
        # [Optimization] AI 비용 절감을 위해 상위 20개 시그널만 선별
        if len(signals_df) > 20:
            logger.info(f"   AI 분석 대상 {len(signals_df)}개 -> 상위 20개로 제한")
            signals_df = signals_df.sort_values(by='score', ascending=False).head(20)
        
        logger.info(f"🤖 AI 분석 시작: {len(signals_df)}개 종목 (TOP 20)")
        
        # DataFrame -> List[Dict] 변환
        stocks_to_analyze = []
        for _, row in signals_df.iterrows():
            stock_data = {
                'ticker': row['ticker'],
                'name': row['name'],
                'current_price': row['entry_price'],
                'vcp_score': row.get('score', 0),
                'contraction_ratio': row.get('contraction_ratio', 0),
                'foreign_5d': row['foreign_5d'],
                'inst_5d': row['inst_5d']
            }
            stocks_to_analyze.append(stock_data)
        
        # Batch 분석 실행
        ai_results = await analyzer.analyze_batch(stocks_to_analyze)
        
        # 결과 병합
        results_list = []
        for idx, row in signals_df.iterrows():
            ticker = row['ticker']
            ai_res = ai_results.get(ticker, {})
            
            # Gemini 결과
            gemini = ai_res.get('gemini_recommendation')
            if gemini:
                row['ai_action'] = gemini.get('action')
                row['ai_confidence'] = gemini.get('confidence')
                row['ai_reason'] = gemini.get('reason')
            else:
                row['ai_action'] = 'N/A'
                row['ai_confidence'] = 0
                row['ai_reason'] = '분석 실패'
                
            results_list.append(row)
            
        logger.info("✅ AI 분석 완료")
        return pd.DataFrame(results_list)


# 편의 함수
def create_tracker(data_dir: str = None) -> SignalTracker:
    """SignalTracker 인스턴스 생성 편의 함수"""
    return SignalTracker(data_dir=data_dir)
