#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX Collector Module

KRX(한국거래소) 데이터를 수집하는 클래스입니다.
pykrx 라이브러리를 사용하여 상승률 상위 종목, 차트 데이터, 수급 데이터를 조회합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (KRXCollector class)
"""
import logging
import os
import pandas as pd
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from engine.collectors.base import BaseCollector, CollectorError, DataSourceUnavailableError
from engine.models import StockData, ChartData, SupplyData

logger = logging.getLogger(__name__)


class KRXCollector(BaseCollector):
    """
    KRX 데이터 수집기

    pykrx 라이브러리를 사용하여 한국 주식 시장 데이터를 수집합니다.
    """

    # 경고 로그 중복 출력 방지 플래그
    _market_date_warning_shown = False

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체
        """
        super().__init__(config)

    # ========================================================================
    # Abstract Method Implementation
    # ========================================================================

    async def get_top_gainers(
        self,
        market: str,
        top_n: int,
        target_date: str = None
    ) -> List[StockData]:
        """
        상승률 상위 종목 조회 (pykrx 실데이터 + 로컬 CSV Fallback)

        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 데이터 조회 (YYYYMMDD 형식)

        Returns:
            StockData 리스트
        """
        # 1. pykrx 실시간 데이터 시도
        try:
            from pykrx import stock

            # 테스트 모드: 특정 날짜 지정 시 해당 날짜 사용
            if target_date:
                target_date_str = target_date  # YYYYMMDD 형식
                logger.info(f"[테스트 모드] 지정 날짜 기준 조회: {target_date_str}")
            else:
                # 가장 최근 장 마감 날짜 계산
                target_date_str = self._get_latest_market_date()

            logger.info(f"목표 날짜: {target_date_str}")

            df = None

            # 목표 날짜부터 최대 7일 전까지 시도 (공휴일 대응)
            base_date = datetime.strptime(target_date_str, '%Y%m%d')
            for days_ago in range(7):
                try:
                    check_date = (base_date - timedelta(days=days_ago)).strftime('%Y%m%d')
                    df = stock.get_market_ohlcv_by_ticker(check_date, market=market)
                    if not df.empty:
                        logger.info(f"pykrx 데이터 로드 성공: {check_date}")
                        break
                except Exception as e:
                    continue

            if df is not None and not df.empty:
                return self._process_ohlcv_dataframe(df, market, top_n)

        except ImportError:
            logger.warning("pykrx 미설치 - CSV fallback 사용")
        except Exception as e:
            logger.warning(f"pykrx 실시간 데이터 수집 실패: {e}")

        # 2. Fallback: 로컬 daily_prices.csv 사용
        logger.info(f"Fallback: 로컬 daily_prices.csv 사용 ({market}) Target={target_date}")
        return self._load_from_local_csv(market, top_n, target_date)

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _process_ohlcv_dataframe(
        self,
        df: pd.DataFrame,
        market: str,
        top_n: int
    ) -> List[StockData]:
        """
        pykrx DataFrame을 StockData 리스트로 변환

        Args:
            df: pykrx OHLCV DataFrame
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수

        Returns:
            StockData 리스트
        """
        from pykrx import stock

        # 필터링
        mask_price = df['종가'] >= 1000
        mask_vol = df['거래대금'] >= 1_000_000_000
        mask_rise = df['등락률'] > 0

        filtered_df = df[mask_price & mask_vol & mask_rise].copy()
        filtered_df = filtered_df.sort_values(by='등락률', ascending=False)
        top_df = filtered_df.head(top_n)

        results = []
        for code, row in top_df.iterrows():
            try:
                name = stock.get_market_ticker_name(code)
                results.append(StockData(
                    code=code,
                    name=name,
                    market=market,
                    sector=self._get_sector(code),
                    close=int(row['종가']),
                    change_pct=float(row['등락률']),
                    trading_value=float(row['거래대금']),
                    volume=int(row['거래량']),
                    marcap=int(row['시가총액']) if '시가총액' in row else 0,
                    high_52w=0,
                    low_52w=0
                ))
            except Exception as e:
                logger.error(f"종목 데이터 변환 실패 ({code}): {e}")
                continue

        return results

    def _load_from_local_csv(
        self,
        market: str,
        top_n: int,
        target_date: str = None
    ) -> List[StockData]:
        """
        로컬 daily_prices.csv에서 상승률 상위 종목 로드

        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 조회

        Returns:
            StockData 리스트
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_path = os.path.join(base_dir, 'data', 'daily_prices.csv')
        stocks_path = os.path.join(base_dir, 'data', 'korean_stocks_list.csv')

        if not os.path.exists(csv_path):
            logger.error(f"daily_prices.csv 파일 없음: {csv_path}")
            return []

        try:
            df = pd.read_csv(csv_path)

            # 종목 목록에서 마켓 정보 가져오기
            stocks_df = pd.read_csv(stocks_path) if os.path.exists(stocks_path) else pd.DataFrame()
            market_map = {}
            if not stocks_df.empty and 'ticker' in stocks_df.columns and 'market' in stocks_df.columns:
                for _, row in stocks_df.iterrows():
                    market_map[str(row['ticker']).zfill(6)] = row['market']

            # 날짜 필터링
            df['date'] = pd.to_datetime(df['date'])

            if target_date:
                # target_date는 YYYYMMDD 또는 YYYY-MM-DD
                if len(str(target_date)) == 8:
                    dt = datetime.strptime(str(target_date), "%Y%m%d")
                else:
                    dt = pd.to_datetime(target_date)

                # 해당 날짜 데이터 검색
                latest_df = df[df['date'].dt.date == dt.date()].copy()
                if latest_df.empty:
                    logger.warning(f"로컬 CSV에 {target_date} 데이터 없음. 최신 날짜로 대체 시도.")
                    latest_date = df['date'].max()
                    latest_df = df[df['date'] == latest_date].copy()
            else:
                latest_date = df['date'].max()
                latest_df = df[df['date'] == latest_date].copy()

            logger.info(f"로컬 데이터 날짜: {latest_df['date'].max()}")

            # 마켓 필터링
            latest_df['ticker'] = latest_df['ticker'].astype(str).str.zfill(6)
            latest_df['market_actual'] = latest_df['ticker'].map(market_map)

            logger.info(f"Market Map Size: {len(market_map)}")
            logger.info(f"Before Market Filter: {len(latest_df)} rows")

            latest_df = latest_df[latest_df['market_actual'] == market]
            logger.info(f"After Market Filter ({market}): {len(latest_df)} rows")

            # 등락률 계산
            if 'change_pct' not in latest_df.columns:
                if 'open' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['change_pct'] = ((latest_df['close'] - latest_df['open']) / latest_df['open'] * 100).fillna(0)
                else:
                    latest_df['change_pct'] = 0

            # 거래대금 계산 (0인 경우 재계산)
            if 'trading_value' not in latest_df.columns:
                if 'volume' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['trading_value'] = latest_df['volume'] * latest_df['close']
                else:
                    latest_df['trading_value'] = 0
            else:
                # 0 또는 NaN인 값 재계산
                latest_df['trading_value'] = latest_df['trading_value'].fillna(0).astype(float)
                mask_zero = latest_df['trading_value'] <= 0

                if mask_zero.any():
                    logger.debug(f"Recalculating 0/NaN trading_value for {mask_zero.sum()} rows")
                    latest_df.loc[mask_zero, 'trading_value'] = latest_df.loc[mask_zero, 'volume'] * latest_df.loc[mask_zero, 'close']

            # 필터링
            mask_price = latest_df['close'] >= 1000
            mask_vol = latest_df['trading_value'] >= 1_000_000_000
            mask_rise = latest_df['change_pct'] > 0

            logger.info(f"TopGainers Filter ({market}): Rise={mask_rise.sum()}, ValidVol={mask_vol.sum()}")

            filtered_df = latest_df[mask_price & mask_vol & mask_rise].copy()
            filtered_df = filtered_df.sort_values(by='change_pct', ascending=False)
            top_df = filtered_df.head(top_n)

            # 종목명 매핑
            name_map = {}
            if not stocks_df.empty:
                for _, row in stocks_df.iterrows():
                    name_map[str(row['ticker']).zfill(6)] = row['name']

            results = []
            for _, row in top_df.iterrows():
                ticker = str(row['ticker']).zfill(6)
                results.append(StockData(
                    code=ticker,
                    name=name_map.get(ticker, ticker),
                    market=market,
                    sector='',
                    close=int(row['close']),
                    change_pct=float(row['change_pct']),
                    trading_value=float(row['trading_value']),
                    volume=int(row.get('volume', 0)),
                    marcap=0,
                    high_52w=0,
                    low_52w=0
                ))

            logger.info(f"로컬 CSV에서 {len(results)}개 종목 로드 완료 ({market})")
            if len(results) == 0:
                logger.warning(f"로컬 CSV 로드 결과가 0개입니다. 파일 내용을 확인하세요.")
            else:
                # 상위 5개 로그 출력
                for i, s in enumerate(results[:5]):
                    logger.info(f"  [{i+1}] {s.name}: {s.change_pct}%")

            return results

        except Exception as e:
            logger.error(f"로컬 CSV 로드 실패: {e}")
            return []

    async def get_stock_detail(self, code: str) -> Optional[Dict]:
        """
        종목 상세 정보 조회 (pykrx -> CSV fallback)

        Args:
            code: 종목 코드

        Returns:
            종목 상세 정보 딕셔너리
        """
        # 1. 기본 정보 구성
        name = self._get_stock_name(code)
        
        # 2. 52주 신고/신저가 조회 (Local CSV 활용)
        high_52w = 0
        low_52w = 0
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            csv_path = os.path.join(base_dir, 'data', 'daily_prices.csv')
            
            if os.path.exists(csv_path):
                # 효율성을 위해 전체를 읽지 않고 최적화할 수 있으나, 여기서는 단순 구현
                # 실전에서는 DB나 인덱싱된 파일을 사용하는 것이 좋음
                df = pd.read_csv(csv_path)
                df['ticker'] = df['ticker'].astype(str).str.zfill(6)
                stock_df = df[df['ticker'] == code].copy()
                
                if not stock_df.empty:
                    # 최근 1년 데이터 필터링
                    stock_df['date'] = pd.to_datetime(stock_df['date'])
                    latest_date = stock_df['date'].max()
                    one_year_ago = latest_date - timedelta(days=365)
                    year_df = stock_df[stock_df['date'] >= one_year_ago]
                    
                    if not year_df.empty:
                        high_52w = int(year_df['high'].max())
                        low_52w = int(year_df['low'].min())
        except Exception as e:
            logger.warning(f"52주 신고/신저가 계산 실패 (CSV): {e}")

        return {
            'code': code,
            'name': name,
            'high_52w': high_52w if high_52w > 0 else 0,
            'low_52w': low_52w if low_52w > 0 else 0
        }

    async def get_chart_data(self, code: str, days: int) -> Optional[ChartData]:
        """
        차트 데이터 조회 (pykrx -> CSV fallback)

        Args:
            code: 종목 코드
            days: 조회할 일수

        Returns:
            ChartData 객체 또는 None
        """
        # 1. pykrx 시도
        try:
            from pykrx import stock
            end_date_str = self._get_latest_market_date()
            end_date = datetime.strptime(end_date_str, "%Y%m%d")
            start_date = end_date - timedelta(days=int(days * 1.6) + 10)
            start_date_str = start_date.strftime("%Y%m%d")

            df = stock.get_market_ohlcv_by_date(start_date_str, end_date_str, code)

            if not df.empty:
                df = df.tail(days)
                return ChartData(
                    dates=[d.date() for d in df.index],
                    opens=df['시가'].tolist(),
                    highs=df['고가'].tolist(),
                    lows=df['저가'].tolist(),
                    closes=df['종가'].tolist(),
                    volumes=df['거래량'].tolist()
                )
        except Exception as e:
            logger.warning(f"pykrx 차트 조회 실패 ({code}): {e}")

        # 2. CSV Fallback
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            csv_path = os.path.join(base_dir, 'data', 'daily_prices.csv')
            
            if not os.path.exists(csv_path):
                return None

            df = pd.read_csv(csv_path)
            df['ticker'] = df['ticker'].astype(str).str.zfill(6)
            df['date'] = pd.to_datetime(df['date'])
            
            # 해당 종목 데이터 필터링
            stock_df = df[df['ticker'] == code].sort_values('date')
            
            if stock_df.empty:
                return None
                
            # 최근 N일 데이터
            stock_df = stock_df.tail(days)
            
            return ChartData(
                dates=[d.date() for d in stock_df['date']],
                opens=stock_df['open'].tolist(),
                highs=stock_df['high'].tolist(),
                lows=stock_df['low'].tolist(),
                closes=stock_df['close'].tolist(),
                volumes=stock_df['volume'].tolist()
            )

        except Exception as e:
            logger.error(f"차트 데이터 CSV 조회 실패 ({code}): {e}")
            return None

    async def get_supply_data(self, code: str) -> Optional[SupplyData]:
        """
        수급 데이터 조회 (pykrx -> CSV fallback)

        Args:
            code: 종목 코드

        Returns:
            SupplyData 객체 또는 None
        """
        # 1. pykrx 시도
        try:
            from pykrx import stock
            end_date = self._get_latest_market_date()
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime('%Y%m%d')
            
            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            
            if not df.empty:
                df = df.tail(5)
                # 컬럼명 처리 (버전 호환)
                foreign_col = next((c for c in df.columns if '외국인' in c), None)
                inst_col = next((c for c in df.columns if '기관' in c), None)
                retail_col = next((c for c in df.columns if '개인' in c), None)

                return SupplyData(
                    foreign_buy_5d=int(df[foreign_col].sum()) if foreign_col else 0,
                    inst_buy_5d=int(df[inst_col].sum()) if inst_col else 0,
                    retail_buy_5d=int(df[retail_col].sum()) if retail_col else 0
                )
        except Exception as e:
            logger.warning(f"pykrx 수급 조회 실패 ({code}): {e}")

        # 2. CSV Fallback (all_institutional_trend_data.csv)
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            csv_path = os.path.join(base_dir, 'data', 'all_institutional_trend_data.csv')
            
            if not os.path.exists(csv_path):
                return SupplyData(0, 0, 0)

            df = pd.read_csv(csv_path)
            df['ticker'] = df['ticker'].astype(str).str.zfill(6)
            df['date'] = pd.to_datetime(df['date'])
            
            stock_df = df[df['ticker'] == code].sort_values('date')
            
            if stock_df.empty:
                 return SupplyData(0, 0, 0)
                 
            # 최근 5일
            recent_df = stock_df.tail(5)
            
            return SupplyData(
                foreign_buy_5d=int(recent_df['foreign_buy'].sum()),
                inst_buy_5d=int(recent_df['inst_buy'].sum()),
                retail_buy_5d=0  # CSV에 개인 데이터가 없으면 0 처리
            )

        except Exception as e:
            logger.error(f"수급 데이터 CSV 조회 실패 ({code}): {e}")
            return None

    def _get_stock_name(self, ticker: str) -> str:
        """
        종목명 조회 (pykrx 사용)

        Args:
            ticker: 종목 코드

        Returns:
            종목명
        """
        try:
            from pykrx import stock
            name = stock.get_market_ticker_name(ticker)
            if name:
                return name
        except Exception as e:
            logger.debug(f"종목명 조회 실패 ({ticker}): {e}")

        # Fallback: Common Major Stocks
        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
            '068270': '셀트리온', '052190': '삼성에스디에스',
            '011200': 'HMM', '096770': 'SK이노베이션', '066570': 'LG전자',
            '056080': '유진로봇'
        }
        return names.get(ticker, '알 수 없는 종목')

    def _get_sector(self, ticker: str) -> str:
        """
        섹터 조회

        Args:
            ticker: 종목 코드

        Returns:
            섹터명
        """
        try:
            from pykrx import stock
            # pykrx에는 섹터 조회 함수가 시점별로 다름
            # 여기서는 간단히 하드코딩 유지하거나 확장
            pass
        except:
            pass

        sectors = {
            '005930': '반도체', '000270': '자동차', '035420': '인터넷',
            '005380': '자동차', '015760': '반도체', '068270': '헬스케어',
            '052190': '반도체', '011200': '해운', '096770': '통신',
            '066570': '2차전지',
            '056080': '로봇'
        }
        return sectors.get(ticker, '기타')
