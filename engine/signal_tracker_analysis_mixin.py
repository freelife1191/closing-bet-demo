#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker 분석/리포트 믹스인.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, Tuple

import pandas as pd

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
    get_file_signature as _get_file_signature,
    load_csv_with_signature_cache as _load_csv_with_signature_cache,
)
from engine.signal_tracker_log_helpers import (
    append_signals_log,
    normalize_new_signals_for_log,
    update_open_signals_frame,
)
from engine.signal_tracker_supply_helpers import build_supply_score_frame


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
PERFORMANCE_DEFAULTS: dict[str, Any] = {
    "status": "OPEN",
    "return_pct": 0.0,
    "signal_date": "",
    "exit_date": "",
    "hold_days": 0,
}


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

    def _build_supply_score_frame(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """최근 5일 수급 집계 및 점수 프레임을 생성한다."""
        return build_supply_score_frame(
            raw_df,
            foreign_min=self.strategy_params["foreign_min"],
            count_consecutive_positive=self._count_consecutive_positive,
            logger=logger,
        )

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
            return
        signature = _get_file_signature(signals_log_path)
        if signature is None:
            _SIGNALS_LOG_SOURCE_CACHE.pop(signals_log_path, None)
            return
        normalized = frame.copy()
        if "_ticker_padded" in normalized.columns:
            normalized = normalized.drop(columns=["_ticker_padded"])
        _SIGNALS_LOG_SOURCE_CACHE[signals_log_path] = (signature, normalized)

    @staticmethod
    def _normalize_performance_frame(df: pd.DataFrame) -> pd.DataFrame:
        """리포트 계산 필수 컬럼을 보정한다."""
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame(columns=PERFORMANCE_SOURCE_COLUMNS)

        normalized = df.copy()
        for column, default_value in PERFORMANCE_DEFAULTS.items():
            if column not in normalized.columns:
                normalized[column] = default_value

        normalized["return_pct"] = pd.to_numeric(normalized["return_pct"], errors="coerce").fillna(0.0)
        normalized["hold_days"] = pd.to_numeric(normalized["hold_days"], errors="coerce").fillna(0).astype(int)
        normalized["status"] = normalized["status"].fillna("OPEN").astype(str)
        return normalized

    def scan_today_signals(self) -> pd.DataFrame:
        """오늘의 시그널 스캔."""
        logger.info("🔍 오늘의 시그널 스캔 시작...")

        inst_path = os.path.join(self.data_dir, "all_institutional_trend_data.csv")
        if not os.path.exists(inst_path):
            logger.error("❌ 수급 데이터 파일이 없습니다")
            return pd.DataFrame()

        try:
            raw_df = self._load_supply_source_frame(inst_path)
            scored_df = self._build_supply_score_frame(raw_df)
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
                    }
                )

            signals_df = pd.DataFrame(vcp_signals)
            if signals_df.empty:
                logger.info("✅ 오늘 VCP 시그널: 0개")
                return signals_df

            if self._stock_name_map:
                signals_df["name"] = signals_df["ticker"].map(self._stock_name_map).fillna(signals_df["ticker"])

            self._append_to_log(signals_df)
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
            working_new.to_csv(self.signals_log_path, index=False, encoding="utf-8-sig")
            self._refresh_signals_log_source_cache(self.signals_log_path, working_new)
            logger.info(f"   📝 시그널 로그 저장: {len(working_new)}개")
            return

        existing = self._load_signals_log_source_frame(self.signals_log_path)

        # Fast path: 오늘 중복 티커가 없고 컬럼이 기존 스키마에 포함되면 append 모드로 저장.
        can_fast_append = (
            not existing.empty
            and "signal_date" in existing.columns
            and "ticker" in existing.columns
            and "signal_date" in working_new.columns
            and "ticker" in working_new.columns
            and set(working_new.columns).issubset(set(existing.columns))
        )
        if can_fast_append:
            existing_today_tickers = set(
                existing.loc[existing["signal_date"] == today, "ticker"].astype(str).str.zfill(6)
            )
            incoming_today_tickers = set(
                working_new.loc[working_new["signal_date"] == today, "ticker"].astype(str).str.zfill(6)
            )
            if existing_today_tickers.isdisjoint(incoming_today_tickers):
                append_frame = working_new.copy()
                for column in existing.columns:
                    if column not in append_frame.columns:
                        append_frame[column] = None
                append_frame = append_frame[list(existing.columns)]
                append_frame.to_csv(
                    self.signals_log_path,
                    mode="a",
                    header=False,
                    index=False,
                    encoding="utf-8",
                )
                refreshed = pd.concat([existing, append_frame], ignore_index=True)
                self._refresh_signals_log_source_cache(self.signals_log_path, refreshed)
                logger.info(f"   📝 시그널 로그 append 저장: +{len(append_frame)}개")
                return

        combined = append_signals_log(
            signals_log_path=self.signals_log_path,
            new_signals=working_new,
            today=today,
            existing_signals=existing,
        )

        combined.to_csv(self.signals_log_path, index=False, encoding="utf-8-sig")
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

        updated_df.to_csv(self.signals_log_path, index=False, encoding="utf-8-sig")
        self._refresh_signals_log_source_cache(self.signals_log_path, updated_df)
        logger.info(f"✅ 시그널 업데이트 완료: {len(closed_logs)}개 청산")

    def get_performance_report(self) -> Dict:
        """전략 성과 리포트."""
        if not os.path.exists(self.signals_log_path):
            return {"error": "시그널 로그가 없습니다"}

        df = self._normalize_performance_frame(
            self._load_performance_source_frame(self.signals_log_path)
        )

        closed = df[df["status"] == "CLOSED"]
        open_signals = df[df["status"] == "OPEN"]

        if len(closed) == 0:
            return {
                "message": "아직 청산된 시그널이 없습니다",
                "open_signals": len(open_signals),
                "total_signals": len(df),
            }

        wins = len(closed[closed["return_pct"] > 0])
        losses = len(closed[closed["return_pct"] <= 0])

        total_profit = closed[closed["return_pct"] > 0]["return_pct"].sum()
        total_loss = abs(closed[closed["return_pct"] <= 0]["return_pct"].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

        return {
            "period": f"{closed['signal_date'].min()} ~ {closed['exit_date'].max()}",
            "total_signals": len(df),
            "closed_signals": len(closed),
            "open_signals": len(open_signals),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(closed) * 100, 1) if len(closed) > 0 else 0,
            "avg_return": round(closed["return_pct"].mean(), 2),
            "total_return": round(closed["return_pct"].sum(), 2),
            "best_trade": round(closed["return_pct"].max(), 2),
            "worst_trade": round(closed["return_pct"].min(), 2),
            "avg_hold_days": round(closed["hold_days"].mean(), 1),
            "profit_factor": round(profit_factor, 2),
            "strategy_params": self.strategy_params,
        }

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

        if len(signals_df) > 20:
            logger.info(f"   AI 분석 대상 {len(signals_df)}개 -> 상위 20개로 제한")
            signals_df = cap_ai_target_signals(signals_df, limit=20)

        logger.info(f"🤖 AI 분석 시작: {len(signals_df)}개 종목 (TOP 20)")

        stocks_to_analyze = build_ai_batch_payload(signals_df)

        ai_results = await analyzer.analyze_batch(stocks_to_analyze)

        logger.info("✅ AI 분석 완료")
        return apply_ai_results(signals_df, ai_results)
