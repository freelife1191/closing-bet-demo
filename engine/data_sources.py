#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Data Source Strategy Pattern

데이터 소스 추상화를 위한 전략 패턴 구현
FDR, pykrx, yfinance 등 다양한 데이터 소스를 통일된 인터페이스로 사용합니다.
"""
import logging
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# Base Strategy
# =============================================================================
class DataSourceStrategy(ABC):
    """
    데이터 소스 전략 기본 클래스

    모든 데이터 소스는 이 인터페이스를 구현해야 합니다.
    """

    @abstractmethod
    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        지수 데이터 조회

        Args:
            symbol: 지수 심변
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (None이면 오늘)

        Returns:
            DataFrame with columns: date, close, open, high, low, volume
        """
        pass

    @abstractmethod
    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        종목 데이터 조회

        Args:
            ticker: 티커 코드
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            DataFrame with columns: date, close, open, high, low, volume
        """
        pass

    @abstractmethod
    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7
    ) -> pd.DataFrame:
        """
        환율 데이터 조회

        Args:
            pair: 통화 쌍 (예: "USD/KRW")
            days: 조회 일수

        Returns:
            DataFrame with columns: date, close
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        데이터 소스 사용 가능 여부 확인

        Returns:
            사용 가능하면 True
        """
        pass

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrame 정규화 (컬럼명 통일)

        Args:
            df: 원본 DataFrame

        Returns:
            정규화된 DataFrame
        """
        if df.empty:
            return df

        # 컬럼명 소문자 변환
        df.columns = [c.lower() for c in df.columns]

        # 날짜 컬럼 정규화
        date_cols = ['date', '날짜', 'index', 'datetime']
        for col in date_cols:
            if col in df.columns and 'date' not in df.columns:
                df.rename(columns={col: 'date'}, inplace=True)
                break

        # 종가 컬럼 정규화
        if '종가' in df.columns and 'close' not in df.columns:
            df.rename(columns={'종가': 'close'}, inplace=True)
        elif 'close' not in df.columns and 'adj close' in df.columns:
            df.rename(columns={'adj close': 'close'}, inplace=True)

        return df


# =============================================================================
# FinanceDataReader Strategy
# =============================================================================
class FDRSource(DataSourceStrategy):
    """
    FinanceDataReader 데이터 소스

    한국 시장 데이터에 최적화되어 있으며 신뢰도가 높음
    """

    def __init__(self):
        self._available = False
        self._fdr = None
        self._check_availability()

    def _check_availability(self):
        """FinanceDataReader 사용 가능 여부 확인"""
        try:
            import FinanceDataReader as fdr
            self._fdr = fdr
            self._available = True
            logger.debug("FinanceDataReader is available")
        except ImportError:
            self._available = False
            logger.debug("FinanceDataReader not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """지수 데이터 조회 (FDR)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            df = self._fdr.DataReader(symbol, start_date, end_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close', 'open', 'high', 'low', 'volume']]
        except Exception as e:
            logger.debug(f"FDR index fetch failed for {symbol}: {e}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """종목 데이터 조회 (FDR)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            df = self._fdr.DataReader(ticker, start_date, end_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close', 'open', 'high', 'low', 'volume']]
        except Exception as e:
            logger.debug(f"FDR stock fetch failed for {ticker}: {e}")

        return pd.DataFrame()

    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7
    ) -> pd.DataFrame:
        """환율 데이터 조회 (FDR)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            df = self._fdr.DataReader(pair, start_date)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close']]
        except Exception as e:
            logger.debug(f"FDR FX fetch failed for {pair}: {e}")

        return pd.DataFrame()


# =============================================================================
# pykrx Strategy
# =============================================================================
class PykrxSource(DataSourceStrategy):
    """
    pykrx 데이터 소스

    KRX 공식 데이터 제공, 한국 시장 전용
    """

    def __init__(self):
        self._available = False
        self._stock = None
        self._check_availability()

    def _check_availability(self):
        """pykrx 사용 가능 여부 확인"""
        try:
            from pykrx import stock
            self._stock = stock
            self._available = True
            logger.debug("pykrx is available")
        except ImportError:
            self._available = False
            logger.debug("pykrx not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """지수 데이터 조회 (pykrx)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            # pykrx uses YYYYMMDD format
            start_str = start_date.replace('-', '')
            end_str = end_date.replace('-', '') if end_date else datetime.now().strftime("%Y%m%d")

            # Map symbol to pykrx code
            code_map = {'KS11': '1001', 'KQ11': '2001'}  # KOSPI, KOSDAQ
            ticker_code = code_map.get(symbol, symbol)

            df = self._stock.get_index_ohlcv_by_date(start_str, end_str, ticker_code)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close', 'open', 'high', 'low', 'volume']]
        except Exception as e:
            logger.debug(f"pykrx index fetch failed for {symbol}: {e}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """종목 데이터 조회 (pykrx)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            start_str = start_date.replace('-', '')
            end_str = end_date.replace('-', '') if end_date else datetime.now().strftime("%Y%m%d")

            df = self._stock.get_market_ohlcv_by_date(start_str, end_str, ticker)
            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close', 'open', 'high', 'low', 'volume']]
        except Exception as e:
            logger.debug(f"pykrx stock fetch failed for {ticker}: {e}")

        return pd.DataFrame()

    def fetch_fx_rate(self, pair: str = "USD/KRW", days: int = 7) -> pd.DataFrame:
        """pykrx는 환율 데이터를 지원하지 않음"""
        return pd.DataFrame()


# =============================================================================
# yfinance Strategy
# =============================================================================
class YFinanceSource(DataSourceStrategy):
    """
    yfinance 데이터 소스

    글로벌 지수, 원자재, 크립토 데이터에 사용
    """

    def __init__(self):
        self._available = False
        self._yf = None
        self._check_availability()

    def _check_availability(self):
        """yfinance 사용 가능 여부 확인"""
        try:
            import yfinance as yf
            self._yf = yf
            self._available = True
            logger.debug("yfinance is available")
        except ImportError:
            self._available = False
            logger.debug("yfinance not installed")

    def is_available(self) -> bool:
        return self._available

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """지수 데이터 조회 (yfinance)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            # Use download method
            df = self._yf.download(
                symbol,
                start=start_date,
                end=end_date,
                progress=False,
                threads=False
            )

            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close', 'open', 'high', 'low', 'volume']]
        except Exception as e:
            logger.debug(f"yfinance index fetch failed for {symbol}: {e}")

        return pd.DataFrame()

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """종목 데이터 조회 (yfinance)"""
        return self.fetch_index_data(ticker, start_date, end_date)

    def fetch_fx_rate(
        self,
        pair: str = "USDKRW=X",
        days: int = 7
    ) -> pd.DataFrame:
        """환율 데이터 조회 (yfinance)"""
        if not self.is_available():
            return pd.DataFrame()

        try:
            # Map pair to yfinance symbol
            symbol_map = {"USD/KRW": "USDKRW=X"}
            symbol = symbol_map.get(pair, pair)

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            df = self._yf.download(
                symbol,
                start=start_date,
                progress=False,
                threads=False
            )

            if not df.empty:
                df = df.reset_index()
                df = self.normalize_dataframe(df)
                return df[['date', 'close']]
        except Exception as e:
            logger.debug(f"yfinance FX fetch failed for {pair}: {e}")

        return pd.DataFrame()


# =============================================================================
# Data Source Manager (Fallback Chain)
# =============================================================================
class DataSourceManager:
    """
    데이터 소스 매니저

    여러 데이터 소스를 순차적으로 시도하는 폴백 체인을 구현합니다.
    """

    def __init__(self, sources: List[DataSourceStrategy] = None):
        """
        Args:
            sources: 데이터 소스 리스트 (우선순위 순)
        """
        if sources is None:
            # Default priority: FDR > pykrx > yfinance
            sources = [
                FDRSource(),
                PykrxSource(),
                YFinanceSource()
            ]
        self.sources = sources

    def fetch_with_fallback(
        self,
        fetch_method: str,
        *args,
        **kwargs
    ) -> pd.DataFrame:
        """
        폴백 체인을 통해 데이터 조회

        Args:
            fetch_method: 호출할 메서드명 ('fetch_index_data', 'fetch_stock_data', 'fetch_fx_rate')
            *args: 위치 인자
            **kwargs: 키워드 인자

        Returns:
            DataFrame (모든 소스 실패 시 빈 DataFrame)
        """
        for source in self.sources:
            if not source.is_available():
                continue

            try:
                method = getattr(source, fetch_method, None)
                if method:
                    df = method(*args, **kwargs)
                    if not df.empty:
                        logger.debug(f"Data fetched from {source.__class__.__name__}")
                        return df
            except Exception as e:
                logger.debug(f"{source.__class__.__name__} failed: {e}")
                continue

        logger.warning(f"All data sources failed for {fetch_method}")
        return pd.DataFrame()

    def fetch_index_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """지수 데이터 조회 (폴백 포함)"""
        return self.fetch_with_fallback('fetch_index_data', symbol, start_date, end_date)

    def fetch_stock_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str = None
    ) -> pd.DataFrame:
        """종목 데이터 조회 (폴백 포함)"""
        return self.fetch_with_fallback('fetch_stock_data', ticker, start_date, end_date)

    def fetch_fx_rate(
        self,
        pair: str = "USD/KRW",
        days: int = 7
    ) -> pd.DataFrame:
        """환율 데이터 조회 (폴백 포함)"""
        return self.fetch_with_fallback('fetch_fx_rate', pair, days)

    def get_latest_fx_rate(self, pair: str = "USD/KRW", default: float = 1350.0) -> float:
        """
        최신 환율 조회

        Args:
            pair: 통화 쌍
            default: 실패 시 기본값

        Returns:
            최신 환율
        """
        df = self.fetch_fx_rate(pair)
        if not df.empty:
            latest = df.iloc[-1]['close']
            try:
                return float(latest)
            except (ValueError, TypeError):
                pass

        return default


# =============================================================================
# Global Data Fetcher (Composite)
# =============================================================================
class GlobalDataFetcher:
    """
    글로벌 데이터 수집기

    지수, 원자재, 크립토 등 다양한 글로벌 데이터를 수집합니다.
    """

    def __init__(self, manager: DataSourceManager = None):
        self.manager = manager or DataSourceManager()

    def fetch_all_indices(
        self,
        start_date: str,
        end_date: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        주요 지수 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        indices = {
            'sp500': '^GSPC',
            'nasdaq': '^IXIC',
            'kospi': '^KS11',
            'kosdaq': '^KQ11'
        }

        result = {}
        for key, symbol in indices.items():
            df = self.manager.fetch_index_data(symbol, start_date, end_date)
            if not df.empty and len(df) >= 2:
                latest = float(df.iloc[-1]['close'])
                prev = float(df.iloc[-2]['close'])
                change = ((latest - prev) / prev) * 100 if prev > 0 else 0.0
                result[key] = {'value': latest, 'change_pct': round(change, 2)}

        return result

    def fetch_commodities(
        self,
        start_date: str,
        end_date: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        원자재 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        commodities = {
            'gold': 'GC=F',
            'silver': 'SI=F'
        }

        result = {}
        for key, symbol in commodities.items():
            df = self.manager.fetch_index_data(symbol, start_date, end_date)
            if not df.empty and len(df) >= 2:
                latest = float(df.iloc[-1]['close'])
                prev = float(df.iloc[-2]['close'])
                change = ((latest - prev) / prev) * 100 if prev > 0 else 0.0
                result[key] = {'value': latest, 'change_pct': round(change, 2)}

        return result

    def fetch_crypto(
        self,
        start_date: str,
        end_date: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        크립토 데이터 수집

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            {key: {'value': float, 'change_pct': float}} 형태의 dict
        """
        crypto = {
            'btc': 'BTC-USD',
            'eth': 'ETH-USD',
            'xrp': 'XRP-USD'
        }

        result = {}
        for key, symbol in crypto.items():
            df = self.manager.fetch_index_data(symbol, start_date, end_date)
            if not df.empty and len(df) >= 2:
                latest = float(df.iloc[-1]['close'])
                prev = float(df.iloc[-2]['close'])
                change = ((latest - prev) / prev) * 100 if prev > 0 else 0.0
                result[key] = {'value': latest, 'change_pct': round(change, 2)}

        return result
