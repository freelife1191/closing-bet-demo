#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jongga notification duplicate guard.

동일한 종가베팅 결과 payload가 여러 실행 경로에서 처리되더라도
알림은 한 번만 발송되도록 파일 기반 claim 상태를 관리한다.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


STATE_FILENAME = "jongga_notification_sent.json"
LOCK_FILENAME = "jongga_notification_sent.lock"
STALE_SENDING_MINUTES = 30

_VOLATILE_KEYS = {
    "analysis_timestamp",
    "created_at",
    "generated_at",
    "last_updated",
    "processing_time_ms",
    "signal_time",
    "timestamp",
    "updated_at",
}

_STABLE_SIGNAL_KEYS = {
    "change_pct",
    "current_price",
    "entry_price",
    "grade",
    "market",
    "score_total",
    "stock_code",
    "stock_name",
    "stop_price",
    "target_price",
    "trading_value",
    "volume_ratio",
}


def build_jongga_notification_key(
    date_str: str | None,
    signals: list[dict[str, Any]] | None,
    notification_type: str = "signals",
) -> str:
    """날짜와 의미 있는 신호 payload로 중복 방지 키를 만든다."""
    normalized_payload = {
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "notification_type": notification_type,
        "signals": _normalize_signals(signals or []),
    }
    payload_json = json.dumps(
        normalized_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()[:24]
    return f"{normalized_payload['date']}:{notification_type}:{digest}"


def claim_jongga_notification_send(
    data_dir: str,
    date_str: str | None,
    signals: list[dict[str, Any]] | None,
    notification_type: str = "signals",
    now: datetime | None = None,
) -> tuple[bool, str]:
    """
    알림 발송 권한을 원자적으로 claim한다.

    Returns:
        (claimed, key): claimed가 False면 이미 동일 payload가 발송 중이거나 발송 완료된 상태다.
    """
    current_time = now or datetime.now()
    key = build_jongga_notification_key(date_str, signals, notification_type)
    os.makedirs(data_dir, exist_ok=True)

    with _locked_state(data_dir) as state:
        records = state.setdefault("records", {})
        existing = records.get(key)
        if existing and not _is_stale_sending(existing, current_time):
            return False, key

        records[key] = {
            "status": "sending",
            "date": date_str or current_time.strftime("%Y-%m-%d"),
            "notification_type": notification_type,
            "claimed_at": current_time.isoformat(timespec="seconds"),
        }
        _write_state(data_dir, state)
        return True, key


def mark_jongga_notification_sent(
    data_dir: str,
    key: str,
    now: datetime | None = None,
) -> None:
    """claim된 알림을 발송 완료로 표시한다."""
    current_time = now or datetime.now()
    os.makedirs(data_dir, exist_ok=True)

    with _locked_state(data_dir) as state:
        records = state.setdefault("records", {})
        record = records.setdefault(key, {})
        record["status"] = "sent"
        record["sent_at"] = current_time.isoformat(timespec="seconds")
        _write_state(data_dir, state)


def release_jongga_notification_claim(data_dir: str, key: str) -> None:
    """발송 예외가 발생한 claim을 제거해 다음 실행에서 재시도할 수 있게 한다."""
    if not key:
        return

    with _locked_state(data_dir) as state:
        records = state.setdefault("records", {})
        record = records.get(key)
        if record and record.get("status") == "sending":
            records.pop(key, None)
            _write_state(data_dir, state)


def _normalize_signals(signals: list[dict[str, Any]]) -> list[Any]:
    normalized = [_normalize_signal(signal) for signal in signals]
    return sorted(
        normalized,
        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str),
    )


def _normalize_signal(signal: dict[str, Any]) -> Any:
    if not isinstance(signal, dict):
        return _normalize_value(signal)

    stock_code = signal.get("stock_code") or signal.get("ticker")
    stock_name = signal.get("stock_name") or signal.get("name")
    if not stock_code and not stock_name:
        return _normalize_value(signal)

    score = signal.get("score") or {}
    score_total = score.get("total") if isinstance(score, dict) else None
    target_price = signal.get("target_price")
    if target_price in (None, 0):
        target_price = signal.get("target_price_1")

    stable_signal = {
        "change_pct": signal.get("change_pct"),
        "current_price": signal.get("current_price"),
        "entry_price": signal.get("entry_price"),
        "grade": signal.get("grade"),
        "market": signal.get("market"),
        "score_total": score_total,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "stop_price": signal.get("stop_price"),
        "target_price": target_price,
        "trading_value": signal.get("trading_value"),
        "volume_ratio": signal.get("volume_ratio"),
    }
    return {
        key: _normalize_value(value)
        for key, value in stable_signal.items()
        if key in _STABLE_SIGNAL_KEYS and value is not None
    }


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(raw_value)
            for key, raw_value in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in _VOLATILE_KEYS
        }

    if isinstance(value, list):
        return [_normalize_value(item) for item in value]

    return value


def _is_stale_sending(record: dict[str, Any], now: datetime) -> bool:
    if record.get("status") == "sent":
        return False

    if record.get("status") != "sending":
        return False

    claimed_at = record.get("claimed_at")
    if not claimed_at:
        return False

    try:
        claimed_datetime = datetime.fromisoformat(claimed_at)
    except ValueError:
        return False

    return now - claimed_datetime > timedelta(minutes=STALE_SENDING_MINUTES)


@contextmanager
def _locked_state(data_dir: str) -> Iterator[dict[str, Any]]:
    os.makedirs(data_dir, exist_ok=True)
    lock_path = os.path.join(data_dir, LOCK_FILENAME)
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.lockf(lock_file, fcntl.LOCK_EX)
        try:
            yield _read_state(data_dir)
        finally:
            if fcntl is not None:
                fcntl.lockf(lock_file, fcntl.LOCK_UN)


def _read_state(data_dir: str) -> dict[str, Any]:
    state_path = os.path.join(data_dir, STATE_FILENAME)
    if not os.path.exists(state_path):
        return {"version": 1, "records": {}}

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "records": {}}

    if not isinstance(state, dict):
        return {"version": 1, "records": {}}

    state.setdefault("version", 1)
    state.setdefault("records", {})
    return state


def _write_state(data_dir: str, state: dict[str, Any]) -> None:
    state_path = os.path.join(data_dir, STATE_FILENAME)
    tmp_path = f"{state_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, state_path)
