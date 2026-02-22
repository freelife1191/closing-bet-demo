#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR AI Analyzer 데이터 접근/변환 서비스
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from engine.constants import FILE_PATHS, NEWS_COLLECTION, NEWS_SOURCE_WEIGHTS
from engine.models import NewsItem
from engine.kr_ai_stock_info_cache import (
    clear_stock_info_cache as _clear_stock_info_cache_impl,
    load_cached_stock_info as _load_cached_stock_info_impl,
    resolve_stock_info_cache_db_path as _resolve_stock_info_cache_db_path_impl,
    save_cached_stock_info as _save_cached_stock_info_impl,
)
from services.kr_market_data_cache_service import load_csv_file


logger = logging.getLogger(__name__)


def _resolve_news_collector_class():
    """리팩토링 중인 collectors 구조(모듈/패키지 공존)에서 안전하게 클래스를 해석한다."""
    try:
        from engine.collectors.news import EnhancedNewsCollector as collector_class

        return collector_class
    except Exception:
        pass

    try:
        from engine.collectors import EnhancedNewsCollector as collector_class

        return collector_class
    except Exception:
        return None


_ENHANCED_NEWS_COLLECTOR_CLASS = _resolve_news_collector_class()


LATEST_SIGNAL_USECOLS = [
    "ticker",
    "name",
    "current_price",
    "entry_price",
    "return_pct",
    "market",
    "score",
    "vcp_score",
    "contraction_ratio",
    "foreign_5d",
    "inst_5d",
]
_LATEST_SIGNAL_INDEX_CACHE_LOCK = threading.Lock()
_LATEST_SIGNAL_INDEX_CACHE: dict[str, tuple[tuple[int, int], dict[str, dict[str, object]]]] = {}

def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _resolve_stock_info_cache_db_path(signals_file: str) -> str:
    return _resolve_stock_info_cache_db_path_impl(signals_file)


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def _to_int(value: object, default: int = 0) -> int:
    parsed = _to_float(value, float(default))
    try:
        return int(parsed)
    except (TypeError, ValueError, OverflowError):
        return default


def clear_kr_ai_stock_info_cache() -> None:
    _clear_stock_info_cache_impl()
    with _LATEST_SIGNAL_INDEX_CACHE_LOCK:
        _LATEST_SIGNAL_INDEX_CACHE.clear()


class KrAiDataService:
    """KR AI Analyzer 데이터 로딩/뉴스 변환 책임을 담당한다."""

    def __init__(self, news_collector: Optional[Any] = None):
        self.news_collector = news_collector or self._create_default_news_collector()

    @staticmethod
    def _create_default_news_collector() -> Any:
        """기본 뉴스 수집기 인스턴스를 생성한다."""
        collector_class = _ENHANCED_NEWS_COLLECTOR_CLASS
        if collector_class is None:
            raise ImportError("EnhancedNewsCollector import failed")

        try:
            return collector_class()
        except TypeError:
            # legacy collectors.py 구현은 config 인자를 필수로 받는다.
            return collector_class(None)

    @staticmethod
    def _load_latest_signal_row(signals_file: str, ticker: str) -> Optional[pd.Series]:
        """signals_log에서 티커 최신 행 1개만 로드/반환한다."""
        ticker_padded = str(ticker).zfill(6)
        latest_index = KrAiDataService._load_latest_signal_index(signals_file)
        row_payload = latest_index.get(ticker_padded)
        if row_payload is None:
            return None
        return pd.Series(dict(row_payload))

    @staticmethod
    def _load_latest_signal_index(signals_file: str) -> dict[str, dict[str, object]]:
        """signals_log 최신 행 인덱스(ticker -> row)를 시그니처 기반으로 재사용한다."""
        signals_path = os.path.abspath(signals_file)
        file_signature = _file_signature(signals_path)
        if file_signature is None:
            with _LATEST_SIGNAL_INDEX_CACHE_LOCK:
                _LATEST_SIGNAL_INDEX_CACHE.pop(signals_path, None)
            return {}

        with _LATEST_SIGNAL_INDEX_CACHE_LOCK:
            cached = _LATEST_SIGNAL_INDEX_CACHE.get(signals_path)
            if cached and cached[0] == file_signature:
                return cached[1]

        source_df = KrAiDataService._load_latest_signal_source_frame(
            signals_file=signals_path,
            file_signature=file_signature,
        )
        latest_index = KrAiDataService._build_latest_signal_index(source_df)

        with _LATEST_SIGNAL_INDEX_CACHE_LOCK:
            _LATEST_SIGNAL_INDEX_CACHE[signals_path] = (file_signature, latest_index)
        return latest_index

    @staticmethod
    def _load_latest_signal_source_frame(
        *,
        signals_file: str,
        file_signature: tuple[int, int],
    ) -> pd.DataFrame:
        """latest ticker 인덱스 생성을 위한 source 프레임을 로드한다."""
        data_dir = os.path.dirname(signals_file)
        filename = os.path.basename(signals_file)

        if filename:
            try:
                return load_csv_file(
                    data_dir,
                    filename,
                    deep_copy=False,
                    usecols=LATEST_SIGNAL_USECOLS,
                    signature=file_signature,
                )
            except Exception:
                try:
                    return load_csv_file(
                        data_dir,
                        filename,
                        deep_copy=False,
                        signature=file_signature,
                    )
                except Exception:
                    pass

        try:
            return pd.read_csv(
                signals_file,
                dtype={"ticker": str},
                usecols=LATEST_SIGNAL_USECOLS,
                low_memory=False,
            )
        except ValueError:
            return pd.read_csv(signals_file, dtype={"ticker": str}, low_memory=False)

    @staticmethod
    def _build_latest_signal_index(df: pd.DataFrame) -> dict[str, dict[str, object]]:
        """DataFrame에서 ticker별 최신 1행 인덱스를 구성한다."""
        if df.empty or "ticker" not in df.columns:
            return {}

        normalized = df.copy()
        normalized["ticker"] = normalized["ticker"].astype(str).str.zfill(6)
        latest_rows = normalized.groupby("ticker", sort=False).tail(1)

        latest_index: dict[str, dict[str, object]] = {}
        for row in latest_rows.to_dict(orient="records"):
            ticker_key = str(row.get("ticker", "")).zfill(6)
            if ticker_key:
                latest_index[ticker_key] = row
        return latest_index

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """
        종목 기본 정보 조회 (실제 데이터 우선)

        Args:
            ticker: 종목 코드

        Returns:
            종목 정보 딕셔너리 또는 None
        """
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            signals_file = os.path.join(root_dir, FILE_PATHS.DATA_DIR, FILE_PATHS.SIGNALS_LOG)
            ticker_key = str(ticker)

            if os.path.exists(signals_file):
                signature = _file_signature(signals_file)
                if signature is not None:
                    cached = _load_cached_stock_info_impl(
                        signals_file=signals_file,
                        ticker=ticker_key,
                        signature=signature,
                        logger=logger,
                        resolve_db_path_fn=_resolve_stock_info_cache_db_path,
                    )
                    if cached is not None:
                        return cached

                row = self._load_latest_signal_row(signals_file, ticker)
                if row is not None:
                    current_price = _to_int(row.get("current_price"), 0)
                    entry_price = _to_int(row.get("entry_price"), 0)
                    info: dict[str, object] = {
                        "ticker": ticker_key,
                        "name": row.get("name", f"종목_{ticker}"),
                        "price": current_price if current_price > 0 else entry_price,
                        "change_pct": _to_float(row.get("return_pct"), 0.0),
                        "market": row.get("market", "KOSPI"),
                        "score": _to_float(row.get("score"), 0.0),
                        "vcp_score": _to_float(row.get("vcp_score"), 0.0),
                        "contraction_ratio": _to_float(row.get("contraction_ratio"), 0.0),
                        "foreign_5d": _to_int(row.get("foreign_5d"), 0),
                        "inst_5d": _to_int(row.get("inst_5d"), 0),
                    }
                    if signature is not None:
                        _save_cached_stock_info_impl(
                            signals_file=signals_file,
                            ticker=ticker_key,
                            signature=signature,
                            payload=info,
                            logger=logger,
                            resolve_db_path_fn=_resolve_stock_info_cache_db_path,
                        )
                    return info

                default_info: dict[str, object] = {
                    "ticker": ticker_key,
                    "name": self.get_stock_name(ticker_key),
                    "price": 0,
                    "change_pct": 0,
                    "market": "KOSPI",
                    "score": 0,
                }
                if signature is not None:
                    _save_cached_stock_info_impl(
                        signals_file=signals_file,
                        ticker=ticker_key,
                        signature=signature,
                        payload=default_info,
                        logger=logger,
                        resolve_db_path_fn=_resolve_stock_info_cache_db_path,
                    )
                return default_info

            return {
                "ticker": ticker_key,
                "name": self.get_stock_name(ticker),
                "price": 0,
                "change_pct": 0,
                "market": "KOSPI",
                "score": 0,
            }

        except Exception as e:
            logger.error(f"종목 정보 조회 실패 ({ticker}): {e}")
            return None

    @staticmethod
    def get_stock_name(ticker: str) -> str:
        """종목명 조회 (fallback)."""
        names = {
            "005930": "삼성전자",
            "000270": "기아",
            "035420": "NAVER",
            "005380": "현대차",
            "068270": "셀트리온",
        }
        return names.get(ticker, f"종목_{ticker}")

    def collect_news(self, ticker: str, name: str) -> List[NewsItem]:
        """
        뉴스 수집 (EnhancedNewsCollector 위임).

        동기 API 환경을 위해 내부적으로 별도 이벤트 루프를 생성/정리한다.
        """
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            news_items = loop.run_until_complete(
                self.news_collector.get_stock_news(
                    code=ticker,
                    limit=NEWS_COLLECTION.MAX_TOTAL_NEWS,
                    name=name,
                )
            )
            return news_items

        except Exception as e:
            logger.warning(f"뉴스 수집 실패 ({ticker}): {e}")
            return []
        finally:
            if loop is not None:
                loop.close()
            asyncio.set_event_loop(None)

    @staticmethod
    def convert_to_news_items(news_dicts: List[Dict]) -> List[NewsItem]:
        """딕셔너리 뉴스를 NewsItem으로 변환."""
        items = []
        for news_dict in news_dicts:
            try:
                items.append(
                    NewsItem(
                        title=news_dict.get("title", ""),
                        summary=news_dict.get("title", ""),
                        source=news_dict.get("source", ""),
                        url=news_dict.get("url", ""),
                        published_at=datetime.now(),  # Fallback
                        weight=news_dict.get("weight", NEWS_SOURCE_WEIGHTS.DEFAULT),
                    )
                )
            except Exception as e:
                logger.debug(f"뉴스 변환 실패: {e}")
        return items

    @staticmethod
    def news_item_to_dict(news_item: NewsItem) -> Dict:
        """NewsItem을 딕셔너리로 변환."""
        return {
            "title": news_item.title,
            "source": news_item.source,
            "published_at": (
                news_item.published_at.strftime("%Y.%m.%d")
                if news_item.published_at
                else ""
            ),
            "url": news_item.url,
            "weight": news_item.weight,
        }


__all__ = ["KrAiDataService"]
