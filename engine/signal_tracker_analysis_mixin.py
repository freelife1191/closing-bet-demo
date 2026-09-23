#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 분석/리포트 믹스인.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Tuple

import pandas as pd

from engine.screening_runtime import resolve_vcp_signals_to_show
from engine.signal_tracker_ai_helpers import (
    apply_ai_results,
    build_ai_batch_payload,
    cap_ai_target_signals,
)
from engine.signal_tracker_analysis_source_cache import (
    CSV_SOURCE_SQLITE_READY as _CSV_SOURCE_SQLITE_READY,
    PERFORMANCE_SOURCE_CACHE as _PERFORMANCE_SOURCE_CACHE,
    SIGNALS_LOG_SOURCE_CACHE as _SIGNALS_LOG_SOURCE_CACHE,
    SUPPLY_SOURCE_CACHE as _SUPPLY_SOURCE_CACHE,
    get_file_signature as _get_source_file_signature,
    load_csv_with_signature_cache as _load_csv_with_signature_cache,
    refresh_csv_signature_cache_snapshot as _refresh_csv_signature_cache_snapshot,
)
from engine.signal_tracker_log_helpers import (
    append_signals_log,
    normalize_new_signals_for_log,
    update_open_signals_frame,
)
from engine.signal_tracker_supply_helpers import build_supply_score_frame
from services.kr_market_data_cache_sqlite_payload import (
    load_csv_payload_from_sqlite as _load_csv_payload_from_sqlite,
    save_csv_payload_to_sqlite as _save_csv_payload_to_sqlite,
)
from services.kr_market_vcp_reanalysis_service import write_vcp_signals_csv_atomic


logger = logging.getLogger(__name__)

SUPPLY_SOURCE_COLUMNS = {"ticker", "date", "foreign_buy", "inst_buy"}
PERFORMANCE_SOURCE_COLUMNS = [
    "status",
    "return_pct",
    "signal_date",
    "exit_date",
    "hold_days",
]
PERFORMANCE_SOURCE_COLUMN_SET = set(PERFORMANCE_SOURCE_COLUMNS)
_SUPPLY_SCORE_FRAME_CACHE_LOCK = threading.Lock()
_SUPPLY_SCORE_FRAME_CACHE: OrderedDict[
    tuple[str, tuple[int, int, int], float],
    pd.DataFrame,
] = OrderedDict()
_SUPPLY_SCORE_FRAME_CACHE_MAX_ENTRIES = 32
_SUPPLY_SCORE_FRAME_SQLITE_MAX_ROWS = 256
_SUPPLY_SCORE_FRAME_SQLITE_CACHE_KEY_SUFFIX = "::signal_tracker_supply_score_frame"


def _supply_score_frame_sqlite_cache_key(source_path: str, foreign_min: float) -> str:
    normalized_path = os.path.abspath(source_path)
    return f"{normalized_path}{_SUPPLY_SCORE_FRAME_SQLITE_CACHE_KEY_SUFFIX}::{foreign_min:.6f}"


def _set_bounded_supply_score_frame_cache_entry(
    key: tuple[str, tuple[int, int, int], float],
    frame: pd.DataFrame,
) -> None:
    _SUPPLY_SCORE_FRAME_CACHE[key] = frame
    _SUPPLY_SCORE_FRAME_CACHE.move_to_end(key)
    normalized_max_entries = max(1, int(_SUPPLY_SCORE_FRAME_CACHE_MAX_ENTRIES))
    while len(_SUPPLY_SCORE_FRAME_CACHE) > normalized_max_entries:
        _SUPPLY_SCORE_FRAME_CACHE.popitem(last=False)


class SignalTrackerAnalysisMixin:
    """SignalTracker의 분석/리포트 동작을 제공하는 믹스인."""

    def detect_vcp_forming(self, ticker: str) -> Tuple[bool, Dict]:
        """VCP 형성 초기 감지 (로컬 데이터 사용)."""
        try:
            ticker_prices = self._get_ticker_prices(ticker)
            if ticker_prices.empty or len(ticker_prices) < 20:
                return False, {}

            recent = ticker_prices.tail(20)
            columns = self._resolve_price_columns(recent)
            if columns is None:
                return False, {}
            price_col, high_col, low_col = columns

            first_half = recent.head(10)
            second_half = recent.tail(10)

            range_first = first_half[high_col].max() - first_half[low_col].min()
            range_second = second_half[high_col].max() - second_half[low_col].min()
            if pd.isna(range_first) or range_first == 0:
                return False, {}

            contraction = float(range_second / range_first)
            current_price = float(recent.iloc[-1][price_col])
            recent_high = float(recent[price_col].max())
            if recent_high <= 0:
                return False, {}

            near_high = current_price >= recent_high * self.strategy_params["near_high_pct"]
            contracting = contraction <= self.strategy_params["contraction_max"]
            is_vcp = near_high and contracting

            first_price = float(recent.iloc[0][price_col])
            return is_vcp, {
                "contraction_ratio": round(contraction, 3),
                "price_from_high_pct": round((recent_high - current_price) / recent_high * 100, 2),
                "current_price": round(current_price, 0),
                "recent_high": round(recent_high, 0),
                "near_high": near_high,
                "is_uptrend": current_price > first_price * 0.98,
            }

        except Exception as error:
            logger.warning(f"⚠️ {ticker} VCP 감지 실패: {error}")
            return False, {}

    def _build_supply_score_frame(
        self,
        raw_df: pd.DataFrame,
        *,
        source_path: str | None = None,
        source_signature: tuple[int, int, int] | None = None,
    ) -> pd.DataFrame:
        """최근 5일 수급 집계 및 점수 프레임을 생성한다."""
        foreign_min = float(self.strategy_params["foreign_min"])
        normalized_source_path = os.path.abspath(source_path) if source_path else None
        cache_key: tuple[str, tuple[int, int, int], float] | None = None
        if normalized_source_path and isinstance(source_signature, tuple) and len(source_signature) == 3:
            try:
                normalized_signature = (
                    int(source_signature[0]),
                    int(source_signature[1]),
                    int(source_signature[2]),
                )
                cache_key = (normalized_source_path, normalized_signature, float(foreign_min))
            except (TypeError, ValueError):
                cache_key = None

        if cache_key is not None:
            with _SUPPLY_SCORE_FRAME_CACHE_LOCK:
                cached = _SUPPLY_SCORE_FRAME_CACHE.get(cache_key)
                if isinstance(cached, pd.DataFrame):
                    _SUPPLY_SCORE_FRAME_CACHE.move_to_end(cache_key)
                    return cached

            sqlite_cache_key = _supply_score_frame_sqlite_cache_key(
                normalized_source_path,
                foreign_min,
            )
            sqlite_signature = (int(cache_key[1][1]), int(cache_key[1][2]))
            sqlite_cached = _load_csv_payload_from_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                usecols=None,
                logger=logger,
            )
            if isinstance(sqlite_cached, pd.DataFrame):
                with _SUPPLY_SCORE_FRAME_CACHE_LOCK:
                    _set_bounded_supply_score_frame_cache_entry(cache_key, sqlite_cached)
                return sqlite_cached

        built = build_supply_score_frame(
            raw_df,
            foreign_min=foreign_min,
            count_consecutive_positive=self._count_consecutive_positive,
            logger=logger,
        )
        if cache_key is not None:
            with _SUPPLY_SCORE_FRAME_CACHE_LOCK:
                _set_bounded_supply_score_frame_cache_entry(cache_key, built)
            sqlite_cache_key = _supply_score_frame_sqlite_cache_key(
                normalized_source_path,
                foreign_min,
            )
            sqlite_signature = (int(cache_key[1][1]), int(cache_key[1][2]))
            _save_csv_payload_to_sqlite(
                filepath=sqlite_cache_key,
                signature=sqlite_signature,
                usecols=None,
                payload=built,
                max_rows=_SUPPLY_SCORE_FRAME_SQLITE_MAX_ROWS,
                logger=logger,
            )
        return built

    @staticmethod
    def _load_supply_source_frame(inst_path: str) -> pd.DataFrame:
        """수급 점수 계산에 필요한 최소 컬럼만 로드한다."""
        return _load_csv_with_signature_cache(
            path=inst_path,
            usecols_filter=SUPPLY_SOURCE_COLUMNS,
            cache=_SUPPLY_SOURCE_CACHE,
            sqlite_cache_kind="supply_source",
        )

    @staticmethod
    def _load_performance_source_frame(signals_log_path: str) -> pd.DataFrame:
        """성과 리포트 계산에 필요한 최소 컬럼만 로드한다."""
        return _load_csv_with_signature_cache(
            path=signals_log_path,
            usecols_filter=PERFORMANCE_SOURCE_COLUMN_SET,
            cache=_PERFORMANCE_SOURCE_CACHE,
            sqlite_cache_kind="performance_source",
        )

    @staticmethod
    def _load_signals_log_source_frame(signals_log_path: str) -> pd.DataFrame:
        """시그널 로그 업데이트에 필요한 원본 프레임을 전체 컬럼으로 로드한다."""
        if not os.path.exists(signals_log_path):
            return pd.DataFrame()
        return _load_csv_with_signature_cache(
            path=signals_log_path,
            usecols_filter=None,
            cache=_SIGNALS_LOG_SOURCE_CACHE,
            sqlite_cache_kind="signals_log_update",
            dtype={"ticker": str},
        )

    @staticmethod
    def _refresh_signals_log_source_cache(signals_log_path: str, frame: pd.DataFrame) -> None:
        """signals_log 저장 직후 메모리 source cache를 최신 스냅샷으로 갱신한다."""
        if not isinstance(frame, pd.DataFrame):
            _SIGNALS_LOG_SOURCE_CACHE.pop(signals_log_path, None)
            _PERFORMANCE_SOURCE_CACHE.pop(signals_log_path, None)
            return
        normalized = frame.copy()
        if "_ticker_padded" in normalized.columns:
            normalized = normalized.drop(columns=["_ticker_padded"])

        signature = _refresh_csv_signature_cache_snapshot(
            path=signals_log_path,
            frame=normalized,
            cache=_SIGNALS_LOG_SOURCE_CACHE,
            sqlite_cache_kind="signals_log_update",
            usecols_filter=None,
        )
        if signature is None:
            _SIGNALS_LOG_SOURCE_CACHE.pop(signals_log_path, None)
            _PERFORMANCE_SOURCE_CACHE.pop(signals_log_path, None)
            return

        _refresh_csv_signature_cache_snapshot(
            path=signals_log_path,
            frame=normalized,
            cache=_PERFORMANCE_SOURCE_CACHE,
            sqlite_cache_kind="performance_source",
            usecols_filter=PERFORMANCE_SOURCE_COLUMN_SET,
        )

    def scan_today_signals(self) -> pd.DataFrame:
        """오늘의 시그널 스캔."""
        logger.info("🔍 오늘의 시그널 스캔 시작...")

        inst_path = os.path.join(self.data_dir, "all_institutional_trend_data.csv")
        if not os.path.exists(inst_path):
            logger.error("❌ 수급 데이터 파일이 없습니다")
            return pd.DataFrame()

        try:
            raw_df = self._load_supply_source_frame(inst_path)
            source_signature = _get_source_file_signature(os.path.abspath(inst_path))
            scored_df = self._build_supply_score_frame(
                raw_df,
                source_path=inst_path,
                source_signature=source_signature,
            )
            if scored_df.empty:
                logger.info("   조건을 만족하는 수급 종목이 없습니다.")
                return pd.DataFrame()

            logger.info(f"   기본 수급 필터 통과: {len(scored_df)}개 종목")

            vcp_signals: list[dict[str, Any]] = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            for row in scored_df.itertuples(index=False):
                ticker = str(row.ticker)
                is_vcp, vcp_info = self.detect_vcp_forming(ticker)
                if not is_vcp:
                    continue

                vcp_signals.append(
                    {
                        "signal_date": today_str,
                        "ticker": ticker,
                        "name": ticker,
                        "foreign_5d": row.foreign_net_buy_5d,
                        "inst_5d": row.institutional_net_buy_5d,
                        "score": row.supply_demand_index,
                        "contraction_ratio": vcp_info.get("contraction_ratio"),
                        "entry_price": vcp_info.get("recent_high"),
                        "current_price": vcp_info.get("current_price"),
                        "status": "OPEN",
                        "exit_price": None,
                        "exit_date": None,
                        "return_pct": None,
                        "hold_days": 0,
                        "vcp_score": self.calculate_vcp_score(vcp_info),
                        # 화면은 is_vcp 가 참인 행만 보인다(_is_vcp_signal_row). 판정은 위에서 통과했다.
                        "is_vcp": True,
                    }
                )

            signals_df = pd.DataFrame(vcp_signals)
            if signals_df.empty:
                logger.info("✅ 오늘 VCP 시그널: 0개")
                return signals_df

            if self._stock_name_map:
                signals_df["name"] = signals_df["ticker"].map(self._stock_name_map).fillna(signals_df["ticker"])

            # 저장은 호출자가 AI 분석 뒤에 한다(run.py 메뉴 2 의 저장 질문)
            logger.info(f"✅ 오늘 VCP 시그널: {len(signals_df)}개")
            return signals_df

        except Exception as error:
            logger.error(f"시그널 스캔 중 오류: {error}")
            return pd.DataFrame()

    def _append_to_log(self, new_signals: pd.DataFrame):
        """시그널 로그에 추가."""
        today = datetime.now().strftime("%Y-%m-%d")
        working_new = normalize_new_signals_for_log(new_signals)
        if working_new.empty:
            logger.info("   📝 시그널 로그 저장: 0개 (추가 없음)")
            return

        if not os.path.exists(self.signals_log_path):
            write_vcp_signals_csv_atomic(working_new, self.signals_log_path)
            self._refresh_signals_log_source_cache(self.signals_log_path, working_new)
            logger.info(f"   📝 시그널 로그 저장: {len(working_new)}개")
            return

        existing = self._load_signals_log_source_frame(self.signals_log_path)

        combined = append_signals_log(
            signals_log_path=self.signals_log_path,
            new_signals=working_new,
            today=today,
            existing_signals=existing,
        )

        write_vcp_signals_csv_atomic(combined, self.signals_log_path)
        self._refresh_signals_log_source_cache(self.signals_log_path, combined)
        logger.info(f"   📝 시그널 로그 저장: {len(combined)}개")

    def update_open_signals(self):
        """열린 시그널 성과 업데이트."""
        if not os.path.exists(self.signals_log_path):
            logger.warning("⚠️ 시그널 로그 파일이 없습니다")
            return

        df = self._load_signals_log_source_frame(self.signals_log_path)
        if df.empty or "status" not in df.columns:
            return

        if not (df["status"] == "OPEN").any():
            logger.info("열린 시그널이 없습니다")
            return

        now = datetime.now()
        updated_df, closed_logs = update_open_signals_frame(
            df=df,
            latest_price_map=self._latest_price_map,
            stop_loss_pct=self.strategy_params["stop_loss_pct"],
            hold_days_limit=self.strategy_params["hold_days"],
            now=now,
        )

        for closed_row in closed_logs.itertuples(index=False):
            logger.info(
                f"   🔴 {closed_row.ticker} 청산 ({closed_row.close_reason}): {closed_row.return_pct:.2f}%"
            )

        if updated_df.equals(df):
            logger.info("✅ 시그널 업데이트 완료: 변경 없음")
            return

        write_vcp_signals_csv_atomic(updated_df, self.signals_log_path)
        self._refresh_signals_log_source_cache(self.signals_log_path, updated_df)
        logger.info(f"✅ 시그널 업데이트 완료: {len(closed_logs)}개 청산")

    def calculate_vcp_score(self, vcp_info: Dict) -> float:
        """VCP 신호 강도 점수 (0-20점) - BLUEPRINT 기준."""
        if not vcp_info:
            return 0.0

        score = 0.0
        contraction = vcp_info.get("contraction_ratio", 1.0)
        if contraction <= 0.3:
            score += 10.0
        elif contraction <= 0.5:
            score += 7.0
        elif contraction <= 0.7:
            score += 4.0

        if vcp_info.get("near_high", False):
            score += 5.0
        if vcp_info.get("is_uptrend", False):
            score += 5.0
        return score

    async def analyze_signals_with_ai(self, signals_df: pd.DataFrame) -> pd.DataFrame:
        """시그널 AI 분석 수행 (vcp_ai_analyzer 연동)."""
        if signals_df.empty:
            logger.warning("AI 분석할 시그널이 없습니다")
            return signals_df

        from engine.vcp_ai_analyzer import get_vcp_analyzer

        analyzer = get_vcp_analyzer()
        if not analyzer.get_available_providers():
            logger.warning("사용 가능한 AI Provider가 없습니다")
            return signals_df

        ai_target_limit = resolve_vcp_signals_to_show(default=20, minimum=1)

        if len(signals_df) > ai_target_limit:
            logger.info(
                f"   AI 분석 대상 {len(signals_df)}개 -> 상위 {ai_target_limit}개로 제한"
            )
            signals_df = cap_ai_target_signals(signals_df, limit=ai_target_limit)

        logger.info(f"🤖 AI 분석 시작: {len(signals_df)}개 종목 (TOP {ai_target_limit})")

        stocks_to_analyze = build_ai_batch_payload(signals_df)

        ai_results = await analyzer.analyze_batch(stocks_to_analyze)

        logger.info("✅ AI 분석 완료")
        return apply_ai_results(signals_df, ai_results)
