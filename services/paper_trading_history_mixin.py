#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading 자산 히스토리 처리 믹스인."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from services.paper_trading_constants import DEFAULT_ASSET_HISTORY_LIMIT, MAX_ASSET_HISTORY_LIMIT

logger = logging.getLogger(__name__)


class PaperTradingHistoryMixin:
    @staticmethod
    def _normalize_asset_history_limit(limit: object, *, default: int) -> int:
        try:
            parsed = int(float(limit))
        except (TypeError, ValueError):
            parsed = default
        return min(max(parsed, 1), MAX_ASSET_HISTORY_LIMIT)

    def _last_snapshot_for_owner(self, owner_id: str) -> dict[str, int | str] | None:
        snapshot = getattr(self, "_last_asset_history_snapshot", None)
        if isinstance(snapshot, dict) and snapshot.get("owner_id") == owner_id:
            return snapshot
        return None

    def _set_last_asset_history_snapshot(
        self,
        *,
        date: str,
        total_asset: int,
        cash: int,
        stock_value: int,
        owner_id: str,
    ) -> None:
        self._last_asset_history_snapshot = {
            "owner_id": self._validate_owner_id(owner_id),
            "date": date,
            "total_asset": int(total_asset),
            "cash": int(cash),
            "stock_value": int(stock_value),
        }

    def _record_asset_history_with_cash_value(self, *, cash: float, current_stock_value: float, owner_id: str) -> None:
        owner_id = self._validate_owner_id(owner_id)
        today = datetime.now().strftime("%Y-%m-%d")
        total_asset = cash + current_stock_value
        cached = self._last_snapshot_for_owner(owner_id)
        if cached and all(cached.get(key) == value for key, value in {"date": today, "total_asset": int(total_asset), "cash": int(cash), "stock_value": int(current_stock_value)}.items()):
            return
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                cursor.execute(
                    "INSERT INTO asset_history(owner_id, date, total_asset, cash, stock_value, timestamp) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(owner_id, date) DO UPDATE SET total_asset=excluded.total_asset, cash=excluded.cash, stock_value=excluded.stock_value, timestamp=excluded.timestamp",
                    (owner_id, today, total_asset, cash, current_stock_value, datetime.now().isoformat()),
                )
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)
        self._set_last_asset_history_snapshot(date=today, total_asset=int(total_asset), cash=int(cash), stock_value=int(current_stock_value), owner_id=owner_id)

    def record_asset_history_with_cash(self, *, cash: float, current_stock_value: float, owner_id: str) -> None:
        try:
            self._record_asset_history_with_cash_value(cash=cash, current_stock_value=current_stock_value, owner_id=owner_id)
        except Exception as error:
            logger.error(f"Failed to record asset history with cash: {error}")

    def record_asset_history(self, current_stock_value: float, *, owner_id: str) -> None:
        owner_id = self._validate_owner_id(owner_id)
        today = datetime.now().strftime("%Y-%m-%d")
        cached = self._last_snapshot_for_owner(owner_id)
        if cached and cached.get("date") == today and cached.get("stock_value") == int(current_stock_value):
            return
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                row = cursor.execute("SELECT cash FROM balance WHERE owner_id=?", (owner_id,)).fetchone()
                cash = float(row[0]) if row else 0
                total_asset = cash + current_stock_value
                cursor.execute(
                    "INSERT INTO asset_history(owner_id, date, total_asset, cash, stock_value, timestamp) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(owner_id, date) DO UPDATE SET total_asset=excluded.total_asset, cash=excluded.cash, stock_value=excluded.stock_value, timestamp=excluded.timestamp",
                    (owner_id, today, total_asset, cash, current_stock_value, datetime.now().isoformat()),
                )
                conn.commit()
                self._set_last_asset_history_snapshot(date=today, total_asset=int(total_asset), cash=int(cash), stock_value=int(current_stock_value), owner_id=owner_id)
        self._execute_db_operation_with_schema_retry(operation)

    def get_asset_history(self, limit: object = DEFAULT_ASSET_HISTORY_LIMIT, days: int | None = None, *, owner_id: str) -> list[dict[str, Any]]:
        owner_id = self._validate_owner_id(owner_id)
        def owner_exists_operation():
            with self.get_read_context() as conn:
                return conn.execute("SELECT 1 FROM balance WHERE owner_id=?", (owner_id,)).fetchone()
        owner_exists = self._execute_db_operation_with_schema_retry(owner_exists_operation)
        if owner_exists is None:
            self._ensure_owner(owner_id)
        limit = self._normalize_asset_history_limit(limit, default=DEFAULT_ASSET_HISTORY_LIMIT)
        def operation() -> list[dict[str, Any]]:
            with self.get_read_context() as conn:
                query = "SELECT date, total_asset, cash, stock_value FROM asset_history WHERE owner_id=?"
                params: list[Any] = [owner_id]
                if days is not None:
                    try:
                        parsed = int(days)
                    except (TypeError, ValueError):
                        parsed = 0
                    if parsed > 0:
                        query += " AND date >= date('now', ?)"
                        params.append(f"-{parsed} day")
                query += " ORDER BY date DESC LIMIT ?"
                params.append(limit)
                rows = [{"date": row[0], "total_asset": row[1], "cash": row[2], "stock_value": row[3]} for row in conn.execute(query, params).fetchall()]
                rows.reverse()
                if len(rows) >= 2:
                    return rows
                if rows and rows[-1]["date"] == datetime.now().strftime("%Y-%m-%d"):
                    latest = rows[-1]
                    return self._build_dummy_asset_history(current_total=float(latest["total_asset"]), current_cash=float(latest["cash"]), current_stock_val=float(latest["stock_value"]))
                balance = conn.execute("SELECT cash FROM balance WHERE owner_id=?", (owner_id,)).fetchone()
                cash = float(balance[0]) if balance else 0
                holdings = conn.execute("SELECT ticker, quantity, avg_price FROM portfolio WHERE owner_id=?", (owner_id,)).fetchall()
                with self.cache_lock:
                    prices = dict(self.price_cache)
                stock_value = self._calculate_stock_value_from_rows([{"ticker": row[0], "quantity": row[1], "avg_price": row[2]} for row in holdings], prices)
                return self._build_dummy_asset_history(current_total=cash + stock_value, current_cash=cash, current_stock_val=stock_value)
        return self._execute_db_operation_with_schema_retry(operation)
