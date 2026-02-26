#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Trading 자산 히스토리 처리 믹스인.
"""

from __future__ import annotations

import logging
from datetime import datetime

from services.paper_trading_constants import (
    DEFAULT_ASSET_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
)

logger = logging.getLogger(__name__)


class PaperTradingHistoryMixin:
    @staticmethod
    def _normalize_asset_history_limit(limit: object, *, default: int) -> int:
        try:
            parsed = int(float(limit))
        except (TypeError, ValueError):
            parsed = int(default)
        return min(max(parsed, 1), int(MAX_HISTORY_LIMIT))

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
        cash: float,
        current_stock_value: float,
    ) -> dict[str, float | str] | None:
        """주어진 cursor에 자산 히스토리를 upsert한다. 변경 스냅샷을 반환한다."""
        total_asset = cash + current_stock_value
        today = datetime.now().strftime('%Y-%m-%d')
        if not self._asset_history_snapshot_changed(
            date=today,
            total_asset=int(total_asset),
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
            WHERE
                asset_history.total_asset != excluded.total_asset
                OR asset_history.cash != excluded.cash
                OR asset_history.stock_value != excluded.stock_value
        ''',
            (today, total_asset, cash, current_stock_value, datetime.now().isoformat()),
        )
        if int(getattr(cursor, "rowcount", 0) or 0) <= 0:
            return None

        return {
            "date": today,
            "total_asset": total_asset,
            "cash": cash,
            "stock_value": current_stock_value,
        }

    def _record_asset_history_with_cash_value(self, *, cash: float, current_stock_value: float) -> None:
        """현재 현금/주식 평가값으로 자산 히스토리를 upsert한다."""
        normalized_cash = cash
        normalized_stock_value = current_stock_value
        total_asset = normalized_cash + normalized_stock_value
        today = datetime.now().strftime('%Y-%m-%d')
        if not self._asset_history_snapshot_changed(
            date=today,
            total_asset=int(total_asset),
            cash=int(normalized_cash),
            stock_value=int(normalized_stock_value),
        ):
            return

        def _operation():
            with self.get_context() as conn:
                cursor = conn.cursor()
                snapshot = self._upsert_asset_history_row(
                    cursor=cursor,
                    cash=normalized_cash,
                    current_stock_value=normalized_stock_value,
                )
                if snapshot:
                    conn.commit()
                    self._set_last_asset_history_snapshot(
                        date=str(snapshot["date"]),
                        total_asset=int(float(snapshot["total_asset"])),
                        cash=int(float(snapshot["cash"])),
                        stock_value=int(float(snapshot["stock_value"])),
                    )

        self._execute_db_operation_with_schema_retry(_operation)

    def record_asset_history_with_cash(self, *, cash: float, current_stock_value: float) -> None:
        """외부에서 이미 계산한 cash 값을 재사용해 히스토리를 기록한다."""
        try:
            self._record_asset_history_with_cash_value(
                cash=cash,
                current_stock_value=current_stock_value,
            )
        except Exception as e:
            logger.error(f"Failed to record asset history with cash: {e}")

    def record_asset_history(self, current_stock_value):
        """Record daily asset history snapshot"""
        try:
            normalized_stock_value = current_stock_value

            # 중복 가능성이 높은 경우(read-only)로 먼저 확인해 write 컨텍스트를 생략한다.
            today = datetime.now().strftime('%Y-%m-%d')
            last_snapshot = getattr(self, "_last_asset_history_snapshot", None)
            should_check_duplicate_with_read_context = (
                isinstance(last_snapshot, dict)
                and str(last_snapshot.get("date", "")) == today
                and int(last_snapshot.get("stock_value", -1)) == int(normalized_stock_value)
            )

            if should_check_duplicate_with_read_context:
                def _load_cash():
                    with self.get_read_context() as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT cash FROM balance WHERE id = 1')
                        balance_row = cursor.fetchone()
                        return balance_row[0] if balance_row else 0

                cash_snapshot = self._execute_db_operation_with_schema_retry(_load_cash)
                total_asset_snapshot = cash_snapshot + normalized_stock_value
                if not self._asset_history_snapshot_changed(
                    date=today,
                    total_asset=int(total_asset_snapshot),
                    cash=int(cash_snapshot),
                    stock_value=int(normalized_stock_value),
                ):
                    return

            def _operation():
                with self.get_context() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT cash FROM balance WHERE id = 1')
                    balance_row = cursor.fetchone()
                    cash = float(balance_row[0]) if balance_row else 0.0
                    snapshot = self._upsert_asset_history_row(
                        cursor=cursor,
                        cash=cash,
                        current_stock_value=normalized_stock_value,
                    )
                    if snapshot:
                        conn.commit()
                        self._set_last_asset_history_snapshot(
                            date=str(snapshot["date"]),
                            total_asset=int(float(snapshot["total_asset"])),
                            cash=int(float(snapshot["cash"])),
                            stock_value=int(float(snapshot["stock_value"])),
                        )

            self._execute_db_operation_with_schema_retry(_operation)
        except Exception as e:
            logger.error(f"Failed to record asset history: {e}")

    def get_asset_history(self, limit=DEFAULT_ASSET_HISTORY_LIMIT):
        """Get asset history for chart"""
        normalized_limit = self._normalize_asset_history_limit(
            limit,
            default=DEFAULT_ASSET_HISTORY_LIMIT,
        )

        def _operation():
            with self.get_read_context() as conn:
                cursor = conn.cursor()
                # Fetch latest N records (DESC), then sort by date (ASC) for chart
                cursor.execute(
                    '''
                    SELECT date, total_asset, cash, stock_value
                    FROM asset_history
                    ORDER BY date DESC
                    LIMIT ?
                ''',
                    (normalized_limit,),
                )
                rows = [
                    {
                        'date': row[0],
                        'total_asset': row[1],
                        'cash': row[2],
                        'stock_value': row[3],
                    }
                    for row in cursor.fetchall()
                ]
                rows.reverse()  # Sort by date ASC for chart

                # [Fix] If history is scarce (< 2 points), return dummy data for chart rendering
                if len(rows) < 2:
                    # 오늘자 스냅샷이 1건이라면 이미 최신 평가값이므로
                    # 추가 balance/portfolio 조회 없이 바로 더미 차트를 생성한다.
                    if rows:
                        latest_row = rows[-1]
                        today = datetime.now().strftime('%Y-%m-%d')
                        if str(latest_row.get('date', '')) == today:
                            current_cash = float(latest_row.get('cash') or 0)
                            current_stock_val = float(latest_row.get('stock_value') or 0)
                            try:
                                current_total = float(latest_row.get('total_asset'))
                            except (TypeError, ValueError):
                                current_total = current_cash + current_stock_val
                            return self._build_dummy_asset_history(
                                current_total=current_total,
                                current_cash=current_cash,
                                current_stock_val=current_stock_val,
                            )

                    with self.cache_lock:
                        prices = dict(self.price_cache)

                    # 가격 캐시가 비어 있으면 DB 집계로 즉시 계산해 파이썬 루프/객체 생성을 줄인다.
                    if not prices:
                        cursor.execute(
                            '''
                            SELECT
                                b.cash AS cash,
                                (
                                    SELECT COALESCE(SUM(p.quantity * p.avg_price), 0)
                                    FROM portfolio p
                                ) AS stock_value
                            FROM balance b
                            WHERE b.id = 1
                            '''
                        )
                        aggregate_row = cursor.fetchone()
                        if aggregate_row:
                            current_cash = float(aggregate_row[0] or 0)
                            current_stock_val = float(aggregate_row[1] or 0)
                        else:
                            current_cash = 0.0
                            current_stock_val = 0.0
                    else:
                        cursor.execute(
                            '''
                            SELECT
                                p.ticker,
                                p.quantity,
                                p.avg_price,
                                b.cash AS cash
                            FROM balance b
                            LEFT JOIN portfolio p ON 1 = 1
                            WHERE b.id = 1
                            '''
                        )
                        portfolio_with_balance_rows = cursor.fetchall()

                        if portfolio_with_balance_rows:
                            first_row = portfolio_with_balance_rows[0]
                            current_cash = float(first_row[3] or 0)
                        else:
                            current_cash = 0.0

                        portfolio_rows = [
                            {
                                'ticker': row[0],
                                'quantity': row[1],
                                'avg_price': row[2],
                            }
                            for row in portfolio_with_balance_rows
                            if row[0] is not None
                        ]
                        current_stock_val = self._calculate_stock_value_from_rows(portfolio_rows, prices)

                    current_total = current_cash + current_stock_val
                    return self._build_dummy_asset_history(
                        current_total=current_total,
                        current_cash=current_cash,
                        current_stock_val=current_stock_val,
                    )

                return rows

        return self._execute_db_operation_with_schema_retry(_operation)
