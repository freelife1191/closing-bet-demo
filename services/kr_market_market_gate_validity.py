#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Gate validity/normalization 서비스
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
import logging


def resolve_market_gate_filename(target_date: str | None) -> str:
    """요청 날짜를 market_gate 파일명으로 변환한다."""
    if not target_date:
        return "market_gate.json"

    target_date = str(target_date).strip()
    if not target_date:
        return "market_gate.json"

    try:
        if "-" in target_date:
            return f"market_gate_{datetime.strptime(target_date, '%Y-%m-%d').strftime('%Y%m%d')}.json"
    except ValueError:
        pass

    return f"market_gate_{target_date.replace('-', '')}.json"


def _is_market_gate_data_structurally_valid(gate_data: dict[str, Any]) -> bool:
    if not gate_data:
        return False
    return (
        gate_data.get("status") != "분석 대기 (Neutral)"
        or bool(gate_data.get("sectors"))
        or gate_data.get("total_score", 50) != 50
    )


def _is_recent_market_gate_analysis(gate_data: dict[str, Any], now: datetime) -> bool:
    timestamp = gate_data.get("timestamp")
    if not timestamp:
        return False
    try:
        last_update = datetime.fromisoformat(timestamp)
    except ValueError:
        return False
    return (now - last_update).total_seconds() < 1800


def evaluate_market_gate_validity(
    gate_data: dict[str, Any],
    target_date: str | None,
    now: datetime | None = None,
) -> tuple[bool, bool]:
    """
    Market Gate 유효성/갱신 필요 여부를 반환한다.
    반환값: (is_valid, needs_update)
    """
    current_time = now or datetime.now()
    is_valid = _is_market_gate_data_structurally_valid(gate_data)
    needs_update = False

    if not gate_data or target_date or not is_valid:
        return is_valid, needs_update
    if current_time.weekday() >= 5:
        return is_valid, needs_update
    if current_time.hour < 9:
        return is_valid, needs_update
    if _is_recent_market_gate_analysis(gate_data, current_time):
        return is_valid, needs_update

    dataset_date = gate_data.get("dataset_date", "")
    if dataset_date != current_time.strftime("%Y-%m-%d"):
        needs_update = True
    return is_valid, needs_update


def apply_market_gate_snapshot_fallback(
    gate_data: dict[str, Any],
    is_valid: bool,
    target_date: str | None,
    load_json_file: Callable[[str], dict[str, Any]],
    logger: logging.Logger,
) -> tuple[dict[str, Any], bool]:
    """실시간 요청에서 gate 데이터가 부실할 때 jongga_v2 snapshot으로 보완한다."""
    if target_date or is_valid:
        return gate_data, is_valid

    try:
        snapshot = load_json_file("jongga_v2_latest.json")
    except Exception as e:
        logger.warning(f"Market Gate Fallback 실패: {e}")
        return gate_data, is_valid

    if not snapshot or "market_status" not in snapshot:
        return gate_data, is_valid

    snap_status = snapshot.get("market_status") or {}
    if not (snap_status.get("sectors") and len(snap_status["sectors"]) > 0):
        return gate_data, is_valid

    logger.info("[Market Gate] 실시간 데이터 부실 또는 구버전 -> 종가베팅 스냅샷으로 대체 (UI용)")
    if "dataset_date" not in snap_status:
        snap_status["dataset_date"] = snapshot.get("date")
    return snap_status, True


def build_market_gate_initializing_payload(now: datetime | None = None) -> dict[str, Any]:
    """백그라운드 분석 중 응답 payload."""
    timestamp = (now or datetime.now()).isoformat()
    return {
        "score": 50,
        "label": "Initializing...",
        "status": "initializing",
        "is_gate_open": True,
        "kospi_close": 0,
        "kospi_change_pct": 0,
        "kosdaq_close": 0,
        "kosdaq_change_pct": 0,
        "updated_at": timestamp,
        "message": "데이터 분석 중... 잠시만 기다려주세요.",
    }


def build_market_gate_empty_payload(now: datetime | None = None) -> dict[str, Any]:
    """데이터가 완전히 없을 때 기본 payload."""
    timestamp = (now or datetime.now()).isoformat()
    return {
        "score": 50,
        "label": "Neutral",
        "status": "YELLOW",
        "is_gate_open": True,
        "kospi_close": 0,
        "kospi_change_pct": 0,
        "kosdaq_close": 0,
        "kosdaq_change_pct": 0,
        "updated_at": timestamp,
        "message": "데이터 없음",
    }


def normalize_market_gate_payload(gate_data: dict[str, Any]) -> dict[str, Any]:
    """프론트엔드에서 기대하는 Market Gate 필드를 보완한다."""
    if "score" not in gate_data and "total_score" in gate_data:
        gate_data["score"] = gate_data["total_score"]

    if "label" not in gate_data:
        color = gate_data.get("color", gate_data.get("status", "GRAY"))
        label_map = {"GREEN": "Bullish", "YELLOW": "Neutral", "RED": "Bearish"}
        gate_data["label"] = label_map.get(color, "Neutral")

    if "indices" in gate_data:
        indices = gate_data["indices"]
        if "kospi" in indices:
            gate_data["kospi_close"] = indices["kospi"].get("value", 0)
            gate_data["kospi_change_pct"] = indices["kospi"].get("change_pct", 0)
        if "kosdaq" in indices:
            gate_data["kosdaq_close"] = indices["kosdaq"].get("value", 0)
            gate_data["kosdaq_change_pct"] = indices["kosdaq"].get("change_pct", 0)
    elif "metrics" in gate_data:
        metrics = gate_data["metrics"]
        if "kospi_close" not in gate_data:
            gate_data["kospi_close"] = metrics.get("kospi", 0)
        if "kosdaq_close" not in gate_data:
            gate_data["kosdaq_close"] = metrics.get("kosdaq", 0)

    return gate_data
