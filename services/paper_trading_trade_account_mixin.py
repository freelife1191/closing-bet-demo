#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading 거래/계좌 처리 믹스인."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from services.paper_trading_constants import (
    DEFAULT_TRADE_HISTORY_LIMIT,
    INITIAL_CASH_KRW,
    LEGACY_UNASSIGNED_OWNER_ID,
    MAX_DEPOSIT_PER_REQUEST_KRW,
    MAX_HISTORY_LIMIT,
    MAX_TOTAL_DEPOSIT_KRW,
)

logger = logging.getLogger(__name__)


class PaperTradingTradeAccountMixin:
    _SQLITE_SUPPORTS_RETURNING = sqlite3.sqlite_version_info >= (3, 35, 0)

    @staticmethod
    def _validate_owner_id(owner_id: str) -> str:
        normalized = owner_id.strip() if isinstance(owner_id, str) else ""
        if not normalized or normalized == LEGACY_UNASSIGNED_OWNER_ID:
            raise ValueError("A non-legacy owner_id is required")
        return normalized

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return str(ticker).zfill(6)

    @classmethod
    def _ticker_lookup_candidates(cls, ticker: str) -> tuple[str, ...]:
        raw = str(ticker).strip()
        normalized = cls._normalize_ticker(raw)
        return (raw,) if raw == normalized else (raw, normalized)

    @staticmethod
    def _normalize_buy_price(value: object) -> float | None:
        try:
            price = float(value)
        except (TypeError, ValueError):
            return None
        return price if price > 0 else None

    @staticmethod
    def _normalize_buy_quantity(value: object) -> int | None:
        try:
            quantity = int(float(value))
        except (TypeError, ValueError):
            return None
        return quantity if quantity > 0 else None

    @staticmethod
    def _normalize_trade_history_limit(limit: object, *, default: int) -> int:
        try:
            parsed = int(float(limit))
        except (TypeError, ValueError):
            parsed = default
        return min(max(parsed, 1), MAX_HISTORY_LIMIT)

    @staticmethod
    def _ensure_owner_balance(cursor: sqlite3.Cursor, owner_id: str) -> None:
        cursor.execute(
            "INSERT OR IGNORE INTO balance(owner_id, cash, total_deposit) VALUES (?, ?, 0)",
            (owner_id, INITIAL_CASH_KRW),
        )

    def _ensure_owner(self, owner_id: str) -> None:
        def operation() -> None:
            with self.get_context() as conn:
                self._ensure_owner_balance(conn.cursor(), owner_id)
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)

    @classmethod
    def _load_portfolio_positions_map_for_tickers(
        cls,
        *,
        cursor: sqlite3.Cursor,
        tickers: list[str],
        owner_id: str,
    ) -> dict[str, tuple]:
        """대량 주문용 기존 보유 종목 조회 헬퍼를 owner 범위로 유지한다."""
        candidates = sorted({candidate for ticker in tickers for candidate in cls._ticker_lookup_candidates(ticker)})
        if not candidates:
            return {}
        positions: dict[str, tuple] = {}
        for start in range(0, len(candidates), 900):
            chunk = candidates[start:start + 900]
            placeholders = ", ".join("?" for _ in chunk)
            query = f"SELECT ticker, name, avg_price, quantity, total_cost FROM portfolio WHERE owner_id = ? AND ticker IN ({placeholders})"
            parameters: list[Any] = [cls._validate_owner_id(owner_id), *chunk]
            for row in cursor.execute(query, parameters).fetchall():
                positions[str(row[0])] = row
        return positions

    @classmethod
    def _select_portfolio_position_by_ticker(cls, *, cursor: sqlite3.Cursor, ticker: str, owner_id: str):
        candidates = cls._ticker_lookup_candidates(ticker)
        placeholders = ", ".join("?" for _ in candidates)
        cursor.execute(
            f"SELECT ticker, name, avg_price, quantity, total_cost FROM portfolio "
            f"WHERE owner_id = ? AND ticker IN ({placeholders}) "
            "ORDER BY CASE ticker WHEN ? THEN 0 ELSE 1 END LIMIT 1",
            (owner_id, *candidates, candidates[0]),
        )
        return cursor.fetchone()

    def get_balance(self, *, owner_id: str) -> float:
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> float:
            with self.get_read_context() as conn:
                row = conn.execute("SELECT cash FROM balance WHERE owner_id = ?", (owner_id,)).fetchone()
                return row[0] if row else 0
        balance = self._execute_db_operation_with_schema_retry(operation)
        if balance:
            return balance
        self._ensure_owner(owner_id)
        return self._execute_db_operation_with_schema_retry(operation)

    def deposit_cash(self, amount: object, *, owner_id: str) -> dict[str, str]:
        owner_id = self._validate_owner_id(owner_id)
        try:
            normalized_amount = int(float(amount))
        except (TypeError, ValueError):
            return {"status": "error", "message": "Amount must be a positive number"}
        if normalized_amount <= 0:
            return {"status": "error", "message": "Amount must be a positive number"}
        if normalized_amount > MAX_DEPOSIT_PER_REQUEST_KRW:
            return {"status": "error", "message": f"Deposit per request limit exceeded (max: {MAX_DEPOSIT_PER_REQUEST_KRW:,} KRW)"}

        def operation() -> dict[str, str]:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                cursor.execute(
                    "UPDATE balance SET cash = cash + ?, total_deposit = total_deposit + ? "
                    "WHERE owner_id = ? AND total_deposit + ? <= ?",
                    (normalized_amount, normalized_amount, owner_id, normalized_amount, MAX_TOTAL_DEPOSIT_KRW),
                )
                if cursor.rowcount == 0:
                    row = cursor.execute("SELECT total_deposit FROM balance WHERE owner_id = ?", (owner_id,)).fetchone()
                    current = int(float(row[0])) if row else 0
                    return {"status": "error", "message": f"Total deposit limit exceeded (current: {current:,} KRW, max: {MAX_TOTAL_DEPOSIT_KRW:,} KRW)"}
                conn.commit()
            return {"status": "success", "message": f"Deposited {normalized_amount:,} KRW"}
        return self._execute_db_operation_with_schema_retry(operation)

    def update_balance(self, amount: float, operation: str = "add", *, owner_id: str) -> float:
        owner_id = self._validate_owner_id(owner_id)
        def db_operation() -> float:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                sign = "-" if operation == "subtract" else "+"
                if self._SQLITE_SUPPORTS_RETURNING:
                    try:
                        cursor.execute(f"UPDATE balance SET cash = cash {sign} ? WHERE owner_id = ? RETURNING cash", (amount, owner_id))
                        row = cursor.fetchone()
                    except sqlite3.OperationalError as error:
                        if "returning" not in str(error).lower():
                            raise
                        cursor.execute(f"UPDATE balance SET cash = cash {sign} ? WHERE owner_id = ?", (amount, owner_id))
                        row = cursor.execute("SELECT cash FROM balance WHERE owner_id = ?", (owner_id,)).fetchone()
                else:
                    cursor.execute(f"UPDATE balance SET cash = cash {sign} ? WHERE owner_id = ?", (amount, owner_id))
                    row = cursor.execute("SELECT cash FROM balance WHERE owner_id = ?", (owner_id,)).fetchone()
                conn.commit()
                return row[0] if row else 0
        return self._execute_db_operation_with_schema_retry(db_operation)

    def _buy_one(self, *, cursor: sqlite3.Cursor, ticker: str, name: str, price: float, quantity: int, owner_id: str, ensure_owner: bool = True) -> dict[str, str]:
        total_cost = int(price * quantity)
        if ensure_owner:
            self._ensure_owner_balance(cursor, owner_id)
        cursor.execute(
            "UPDATE balance SET cash = cash - ? WHERE owner_id = ? AND cash >= ?",
            (total_cost, owner_id, total_cost),
        )
        if cursor.rowcount != 1:
            row = cursor.execute("SELECT cash FROM balance WHERE owner_id = ?", (owner_id,)).fetchone()
            cash = int(row[0]) if row else 0
            return {"status": "error", "message": f"잔고 부족 (필요: {total_cost:,}원, 보유: {cash:,}원)"}
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO portfolio(owner_id, ticker, name, avg_price, quantity, total_cost, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(owner_id, ticker) DO UPDATE SET name=excluded.name, quantity=portfolio.quantity + excluded.quantity, "
            "total_cost=portfolio.total_cost + excluded.total_cost, avg_price=(portfolio.total_cost + excluded.total_cost) / (portfolio.quantity + excluded.quantity), last_updated=excluded.last_updated",
            (owner_id, ticker, name, price, quantity, total_cost, timestamp),
        )
        cursor.execute(
            "INSERT INTO trade_log(owner_id, action, ticker, name, price, quantity, timestamp, profit, profit_rate) VALUES (?, 'BUY', ?, ?, ?, ?, ?, 0, 0)",
            (owner_id, ticker, name, price, quantity, timestamp),
        )
        return {"status": "success", "message": f"{name} {quantity}주 매수 완료"}

    def buy_stock(self, ticker: str, name: str, price: object, quantity: object, *, owner_id: str) -> dict[str, str]:
        owner_id = self._validate_owner_id(owner_id)
        normalized_price = self._normalize_buy_price(price)
        normalized_quantity = self._normalize_buy_quantity(quantity)
        if normalized_price is None:
            return {"status": "error", "message": "Price must be a positive number"}
        if normalized_quantity is None:
            return {"status": "error", "message": "Quantity must be positive"}
        def operation() -> dict[str, str]:
            with self.get_context() as conn:
                result = self._buy_one(cursor=conn.cursor(), ticker=str(ticker), name=str(name), price=normalized_price, quantity=normalized_quantity, owner_id=owner_id)
                if result["status"] == "success":
                    conn.commit()
                return result
        return self._execute_db_operation_with_schema_retry(operation)

    def buy_stocks_bulk(self, orders: object, *, owner_id: str) -> dict[str, Any]:
        owner_id = self._validate_owner_id(owner_id)
        if not isinstance(orders, list) or not orders:
            return {"status": "error", "message": "No orders provided", "summary": {"total": 0, "success": 0, "failed": 0}, "results": []}
        normalized: list[tuple[str, str, float, int]] = []
        results: list[dict[str, str]] = []
        for item in orders:
            if not isinstance(item, dict):
                results.append({"ticker": "", "name": "", "status": "error", "message": "Invalid order payload"})
                continue
            ticker, name = str(item.get("ticker", "")).strip(), str(item.get("name", "")).strip()
            price, quantity = self._normalize_buy_price(item.get("price")), self._normalize_buy_quantity(item.get("quantity"))
            if not ticker or not name or price is None or quantity is None:
                results.append({"ticker": ticker, "name": name, "status": "error", "message": "Missing or invalid order fields"})
            else:
                normalized.append((ticker, name, price, quantity))
        if normalized:
            def read_cash() -> float | None:
                with self.get_read_context() as conn:
                    row = conn.execute("SELECT cash FROM balance WHERE owner_id=?", (owner_id,)).fetchone()
                    return float(row[0]) if row else None
            available_cash = self._execute_db_operation_with_schema_retry(read_cash)
            projected_cash = INITIAL_CASH_KRW if available_cash is None else available_cash
            preflight_results: list[dict[str, str]] = []
            for ticker, name, price, quantity in normalized:
                cost = int(price * quantity)
                if projected_cash < cost:
                    preflight_results.append({"ticker": ticker, "name": name, "status": "error", "message": f"잔고 부족 (필요: {cost:,}원, 보유: {int(projected_cash):,}원)"})
                else:
                    projected_cash -= cost
            if len(preflight_results) == len(normalized):
                rows = [*results, *preflight_results]
                return {"status": "error", "message": f"일괄 매수 실패 (성공 0건, 실패 {len(rows)}건)", "summary": {"total": len(rows), "success": 0, "failed": len(rows)}, "results": rows}
        def operation() -> list[dict[str, str]]:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                local = list(results)
                for ticker, name, price, quantity in normalized:
                    result = self._buy_one(cursor=cursor, ticker=ticker, name=name, price=price, quantity=quantity, owner_id=owner_id, ensure_owner=False)
                    local.append({"ticker": ticker, "name": name, **result})
                if any(row["status"] == "success" for row in local):
                    conn.commit()
                return local
        try:
            rows = self._execute_db_operation_with_schema_retry(operation)
        except Exception as error:
            logger.error(f"Bulk buy failed: {error}")
            rows = [*results, *[
                {"ticker": ticker, "name": name, "status": "error", "message": str(error)}
                for ticker, name, _price, _quantity in normalized
            ]]
        success = sum(row["status"] == "success" for row in rows)
        message = f"일괄 매수 완료 (성공 {success}건, 실패 {len(rows) - success}건)" if success else f"일괄 매수 실패 (성공 0건, 실패 {len(rows)}건)"
        return {"status": "success" if success else "error", "message": message, "summary": {"total": len(rows), "success": success, "failed": len(rows) - success}, "results": rows}

    def sell_stock(self, ticker: str, price: object, quantity: object, *, owner_id: str) -> dict[str, str]:
        owner_id = self._validate_owner_id(owner_id)
        execution_price, normalized_quantity = self._normalize_buy_price(price), self._normalize_buy_quantity(quantity)
        if execution_price is None:
            return {"status": "error", "message": "Price must be a positive number"}
        if normalized_quantity is None:
            return {"status": "error", "message": "Quantity must be positive"}
        def operation() -> dict[str, str]:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                row = self._select_portfolio_position_by_ticker(cursor=cursor, ticker=ticker, owner_id=owner_id)
                if not row or row[3] < normalized_quantity:
                    return {"status": "error", "message": "Not enough shares to sell"}
                db_ticker, name, avg_price, current_quantity, _ = row
                remaining = current_quantity - normalized_quantity
                if remaining:
                    cursor.execute("UPDATE portfolio SET quantity=?, total_cost=?, last_updated=? WHERE owner_id=? AND ticker=?", (remaining, avg_price * remaining, datetime.now().isoformat(), owner_id, db_ticker))
                else:
                    cursor.execute("DELETE FROM portfolio WHERE owner_id=? AND ticker=?", (owner_id, db_ticker))
                proceeds, cost = int(execution_price * normalized_quantity), int(avg_price * normalized_quantity)
                profit = proceeds - cost
                cursor.execute("INSERT INTO trade_log(owner_id, action, ticker, name, price, quantity, timestamp, profit, profit_rate) VALUES (?, 'SELL', ?, ?, ?, ?, ?, ?, ?)", (owner_id, db_ticker, name, execution_price, normalized_quantity, datetime.now().isoformat(), profit, profit / cost * 100 if cost else 0))
                cursor.execute("UPDATE balance SET cash = cash + ? WHERE owner_id = ?", (proceeds, owner_id))
                conn.commit()
                return {"status": "success", "message": f"{name} {normalized_quantity}주 매도 완료"}
        return self._execute_db_operation_with_schema_retry(operation)

    def get_portfolio(self, *, owner_id: str) -> dict[str, Any]:
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> dict[str, Any]:
            with self.get_read_context() as conn:
                rows = conn.execute(
                    "SELECT p.ticker, p.name, p.avg_price, p.quantity, p.total_cost, p.last_updated, b.cash, b.total_deposit "
                    "FROM balance b LEFT JOIN portfolio p ON p.owner_id = b.owner_id WHERE b.owner_id=?",
                    (owner_id,),
                ).fetchall()
                cash, deposits = (rows[0][6], rows[0][7]) if rows else (0, 0)
                return {"holdings": [{"ticker": row[0], "name": row[1], "avg_price": row[2], "quantity": row[3], "total_cost": row[4], "last_updated": row[5]} for row in rows if row[0] is not None], "cash": cash, "total_asset_value": cash, "total_principal": INITIAL_CASH_KRW + deposits}
        portfolio = self._execute_db_operation_with_schema_retry(operation)
        if portfolio["cash"]:
            return portfolio
        self._ensure_owner(owner_id)
        return self._execute_db_operation_with_schema_retry(operation)

    def _forget_asset_history_snapshot(self, owner_id: str) -> None:
        snapshot = getattr(self, "_last_asset_history_snapshot", None)
        if isinstance(snapshot, dict) and snapshot.get("owner_id") == owner_id:
            self._last_asset_history_snapshot = None

    def reset_account(self, *, owner_id: str) -> bool:
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                self._ensure_owner_balance(cursor, owner_id)
                for table in ("portfolio", "trade_log", "asset_history"):
                    cursor.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
                cursor.execute("UPDATE balance SET cash=?, total_deposit=0 WHERE owner_id=?", (INITIAL_CASH_KRW, owner_id))
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)
        self._forget_asset_history_snapshot(owner_id)
        return True

    def delete_account(self, *, owner_id: str) -> bool:
        """계정 삭제. reset_account 와 달리 balance 행도 남기지 않는다([FE-045]).

        다음 접근이 _ensure_owner 로 새 계좌를 만들므로 삭제 뒤 조회는 초기 잔고를 돌려준다.
        """
        owner_id = self._validate_owner_id(owner_id)
        def operation() -> None:
            with self.get_context() as conn:
                cursor = conn.cursor()
                for table in ("portfolio", "trade_log", "asset_history", "balance"):
                    cursor.execute(f"DELETE FROM {table} WHERE owner_id = ?", (owner_id,))
                conn.commit()
        self._execute_db_operation_with_schema_retry(operation)
        self._forget_asset_history_snapshot(owner_id)
        return True

    def get_trade_history(self, limit: object = DEFAULT_TRADE_HISTORY_LIMIT, ticker: str | None = None, *, owner_id: str) -> dict[str, list[dict[str, Any]]]:
        owner_id = self._validate_owner_id(owner_id)
        limit = self._normalize_trade_history_limit(limit, default=DEFAULT_TRADE_HISTORY_LIMIT)
        candidates = self._ticker_lookup_candidates(ticker) if ticker and str(ticker).strip() else ()
        def operation() -> dict[str, list[dict[str, Any]]]:
            with self.get_read_context() as conn:
                query = "SELECT id, action, ticker, name, price, quantity, timestamp, profit, profit_rate FROM trade_log WHERE owner_id=?"
                params: list[Any] = [owner_id]
                if candidates:
                    query += f" AND ticker IN ({', '.join('?' for _ in candidates)})"
                    params.extend(candidates)
                query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(query, params).fetchall()
                return {"trades": [{"id": row[0], "action": row[1], "ticker": row[2], "name": row[3], "price": row[4], "quantity": row[5], "timestamp": row[6], "profit": row[7], "profit_rate": row[8]} for row in rows]}
        return self._execute_db_operation_with_schema_retry(operation)
