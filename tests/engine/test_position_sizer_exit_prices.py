#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""종가베팅 생성 가격의 공용 기본값 회귀 검사."""

from engine.config import SignalConfig
from engine.models import Grade
from engine.position_sizer import PositionSizer
from services import kr_market_backtest_common


def test_shared_exit_price_defaults_drive_generation_and_missing_backtest_values():
    """공용 기본값이 달라지면 생성 가격과 누락된 계산 경계가 함께 깨져야 한다."""
    config = SignalConfig()
    position = PositionSizer(config.capital, config).calculate(100_000, Grade.S)

    assert (position.target_price, position.stop_price) == (105_000, 97_000)
    assert kr_market_backtest_common.resolve_jongga_exit_prices(100_000) == (105_000, 97_000)


def test_position_sizer_uses_custom_exit_widths_on_normal_and_exception_paths(monkeypatch):
    """예외 폴백이 고정 5/-3으로 돌아가면 사용자 설정 생성 가격과 갈라진다."""
    config = SignalConfig(take_profit_pct=0.08, stop_loss_pct=0.04)
    sizer = PositionSizer(config.capital, config)

    normal = sizer.calculate(100_000, Grade.S)
    monkeypatch.setattr(sizer, "_get_r_multiplier", lambda _grade: (_ for _ in ()).throw(RuntimeError("forced")))
    fallback = sizer.calculate(100_000, Grade.S)

    assert (normal.target_price, normal.stop_price) == (108_000, 96_000)
    assert (fallback.target_price, fallback.stop_price) == (108_000, 96_000)


def test_resolve_exit_prices_preserves_valid_values_and_repairs_each_invalid_side():
    """한쪽만 잘못돼도 반대쪽의 저장 가격을 잃으면 안 된다."""
    assert kr_market_backtest_common.resolve_jongga_exit_prices(100, 101, 97) == (101, 97)
    assert kr_market_backtest_common.resolve_jongga_exit_prices(100, 100, 97) == (105, 97)
    assert kr_market_backtest_common.resolve_jongga_exit_prices(100, 108, float("inf")) == (108, 97)
