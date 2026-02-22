#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 자산 히스토리 처리 믹스인.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class PaperTradingHistoryMixin:
    def _asset_history_snapshot_changed(
        self,
        *,
        date: str,
        total_asset: int,
        cash: int,
        stock_value: int,
    ) -> bool:
        """동일 일자/동일 값 중복 기록을 방지하기 위한 변경 감지."""
        last_snapshot = getattr(self, "_last_asset_history_snapshot", None)
        if not isinstance(last_snapshot, dict):
            return True

        return not (
            last_snapshot.get("date") == date
            and int(last_snapshot.get("total_asset", -1)) == int(total_asset)
            and int(last_snapshot.get("cash", -1)) == int(cash)
            and int(last_snapshot.get("stock_value", -1)) == int(stock_value)
        )

    def _set_last_asset_history_snapshot(
        self,
        *,
        date: str,
        total_asset: int,
        cash: int,
        stock_value: int,
    ) -> None:
        self._last_asset_history_snapshot = {
            "date": date,
            "total_asset": int(total_asset),
            "cash": int(cash),
            "stock_value": int(stock_value),
        }

    def _upsert_asset_history_row(
        self,
        *,
        cursor,
        cash: int,
        current_stock_value: int,
    ) -> dict[str, int | str] | None:
        """주어진 cursor에 자산 히스토리를 upsert한다. 변경 스냅샷을 반환한다."""
        total_asset = int(cash) + int(current_stock_value)
        today = datetime.now().strftime('%Y-%m-%d')
        if not self._asset_history_snapshot_changed(
            date=today,
            total_asset=total_asset,
            cash=int(cash),
            stock_value=int(current_stock_value),
        ):
            return None

        # 하루에 하나의 기록만 남김 (UPDATE or INSERT)
        cursor.execute(
            '''
            INSERT INTO asset_history (date, total_asset, cash, stock_value, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_asset = excluded.total_asset,
                cash = excluded.cash,
                stock_value = excluded.stock_value,
                timestamp = excluded.timestamp
        ''',
            (today, total_asset, int(cash), int(current_stock_value), datetime.now().isoformat()),
        )

        return {
            "date": today,
            "total_asset": int(total_asset),
            "cash": int(cash),
            "stock_value": int(current_stock_value),
        }

    def _record_asset_history_with_cash_value(self, *, cash: int, current_stock_value: int) -> None:
        """현재 현금/주식 평가값으로 자산 히스토리를 upsert한다."""
        with self.get_context() as conn:
            cursor = conn.cursor()
            snapshot = self._upsert_asset_history_row(
                cursor=cursor,
                cash=int(cash),
                current_stock_value=int(current_stock_value),
            )
            if snapshot:
                conn.commit()
                self._set_last_asset_history_snapshot(
                    date=str(snapshot["date"]),
                    total_asset=int(snapshot["total_asset"]),
                    cash=int(snapshot["cash"]),
                    stock_value=int(snapshot["stock_value"]),
                )

    def record_asset_history_with_cash(self, *, cash: int, current_stock_value: int) -> None:
        """외부에서 이미 계산한 cash 값을 재사용해 히스토리를 기록한다."""
        try:
            self._record_asset_history_with_cash_value(
                cash=int(cash),
                current_stock_value=int(current_stock_value),
            )
        except Exception as e:
            logger.error(f"Failed to record asset history with cash: {e}")

    def record_asset_history(self, current_stock_value):
        """Record daily asset history snapshot"""
        try:
            with self.get_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT cash FROM balance WHERE id = 1')
                balance_row = cursor.fetchone()
                cash = int(balance_row[0]) if balance_row else 0
                snapshot = self._upsert_asset_history_row(
                    cursor=cursor,
                    cash=int(cash),
                    current_stock_value=int(current_stock_value),
                )
                if snapshot:
                    conn.commit()
                    self._set_last_asset_history_snapshot(
                        date=str(snapshot["date"]),
                        total_asset=int(snapshot["total_asset"]),
                        cash=int(snapshot["cash"]),
                        stock_value=int(snapshot["stock_value"]),
                    )
        except Exception as e:
            logger.error(f"Failed to record asset history: {e}")

    def get_asset_history(self, limit=30):
        """Get asset history for chart"""
        with self.get_context() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Fetch latest N records (DESC), then sort by date (ASC) for chart
            cursor.execute(
                '''
                SELECT date, total_asset, cash, stock_value
                FROM asset_history
                ORDER BY date DESC
                LIMIT ?
            ''',
                (limit,),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            rows.reverse()  # Sort by date ASC for chart

            # [Fix] If history is scarce (< 2 points), return dummy data for chart rendering
            if len(rows) < 2:
                # Calculate current total asset dynamically for better dummy data
                cursor.execute('SELECT cash FROM balance WHERE id = 1')
                balance_row = cursor.fetchone()
                current_cash = int(balance_row['cash']) if balance_row else 0

                # Calculate current stock value from portfolio
                cursor.execute('SELECT quantity, avg_price, ticker FROM portfolio')
                portfolio_rows = cursor.fetchall()

                with self.cache_lock:
                    prices = self.price_cache
                current_stock_val = self._calculate_stock_value_from_rows(portfolio_rows, prices)

                current_total = current_cash + current_stock_val
                return self._build_dummy_asset_history(
                    current_total=current_total,
                    current_cash=current_cash,
                    current_stock_val=current_stock_val,
                )

            return rows
