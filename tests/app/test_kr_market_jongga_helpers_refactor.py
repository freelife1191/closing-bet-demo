#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market 종가베팅 정규화·등급 헬퍼 리팩토링 테스트

세 경로로 나뉘어 있던 숫자·티커 변환기를 공통 모듈로 합친 뒤, 어느 경로를 지나든
같은 입력이 같은 값이 되는지 고정한다. 정렬 키와 프론트엔드 정규화는 AUDIT-JONGGA
§5.1 이 지적한 검증 공백을 메운다.
"""

from __future__ import annotations

from app.routes.kr_market_jongga_grade_helpers import (
    _jongga_sort_key,
    _normalize_stock_code,
    _sort_jongga_signals,
)
from app.routes.kr_market_jongga_normalize_helpers import (
    _apply_latest_prices_to_jongga_signals,
    _normalize_jongga_signal_for_frontend,
)
from app.routes.kr_market_signal_common import (
    _normalize_ticker,
    _safe_float,
    _safe_int,
    _safe_optional_float,
)
from services.kr_market_backtest_common import JONGGA_STOP_PCT, JONGGA_TARGET_PCT


def test_numeric_converters_strip_percent_and_won_on_every_path():
    """통합 전에는 경로마다 떼어 내는 기호가 달라 같은 입력이 다른 값이 되었다."""
    assert _safe_float("5%") == 5.0
    assert _safe_float("1,234원") == 1234.0
    assert _safe_float("₩1,234.5%") == 1234.5
    assert _safe_int("$1,234%") == 1234
    assert _safe_int("12,000원") == 12000

    assert _safe_float("bad", default=1.5) == 1.5
    assert _safe_int("bad", default=3) == 3


def test_safe_optional_float_distinguishes_absent_from_zero():
    """수급 값을 여러 키에서 찾을 때 0 을 「없음」으로 오인하면 다음 키를 집는다."""
    assert _safe_optional_float(0) == 0.0
    assert _safe_optional_float("0원") == 0.0
    assert _safe_optional_float(None) is None
    assert _safe_optional_float("") is None
    assert _safe_optional_float("없음") is None


def test_normalize_ticker_returns_empty_string_for_unusable_codes():
    assert _normalize_ticker("5930") == "005930"
    assert _normalize_ticker("A005930") == "005930"
    assert _normalize_ticker("") == ""
    assert _normalize_ticker(None) == ""
    assert _normalize_ticker("종목") == ""

    # 전부 0 인 코드는 국내 시장에 없다. 여섯 자리로 통과시키면 가격 맵에서
    # 결측을 zfill 한 "000000" 키와 매칭되어 남의 가격이 붙는다.
    assert _normalize_ticker("0") == ""
    assert _normalize_ticker("000000") == ""


def test_normalize_stock_code_shares_the_empty_convention():
    """등급 헬퍼가 자리채움 `000000` 을 만들지 않아야 방어 코드가 필요 없어진다."""
    assert _normalize_stock_code({"stock_code": "5930"}) == "005930"
    assert _normalize_stock_code({"ticker": "000660"}) == "000660"
    assert _normalize_stock_code({"code": "005380"}) == "005380"
    assert _normalize_stock_code({}) == ""
    assert _normalize_stock_code({"stock_code": "미상"}) == ""


# Regression: [JONGGA-017] — 영문자가 든 종목코드가 조회 경로에 따라 다른 코드가 되었다
# 근거: docs/dev-cycle/TODO.md [JONGGA-017] (2026-09-03 JONGGA-005 사이클의 /qa NEW-003)
#
# 국내 종목코드는 여섯 자리이고 가운데에 영문자가 온다. 정규화가 숫자만 남기는 바람에
# 아크릴 `0007C0` 이 `000070` 이 되었는데, 그것은 실재하는 다른 종목의 코드다. 이력
# 조회는 정규화를 거치지 않아 원본이 살아 있고 최신 조회만 이 함수를 지나므로, 최신
# 자료에 이런 종목이 들어오는 날 두 경로가 서로 다른 회사를 가리켰다.


def test_normalize_ticker_keeps_letters_that_belong_to_the_code():
    """자료에 실재하는 세 종목이다. 영문자를 버리면 각각 남의 코드가 된다."""
    assert _normalize_ticker("0007C0") == "0007C0"  # 아크릴
    assert _normalize_ticker("0015N0") == "0015N0"  # 아로마티카
    assert _normalize_ticker("0126Z0") == "0126Z0"  # 삼성에피스홀딩스

    # 대소문자가 섞여 들어와도 같은 코드로 모은다.
    assert _normalize_ticker("0007c0") == "0007C0"

    # 앞뒤에 붙는 시장 표시는 코드가 아니다. 여섯 자리만 집어낸다.
    assert _normalize_ticker("005930.KS") == "005930"

    # 여섯 자리를 넘는 값은 앞을 잘라 쓰지 않고 버린다. 자르면 `20260211` 이 `202602`
    # 라는 실재할 수 있는 코드가 되어, 없는 종목이 있는 종목의 자리를 차지한다.
    assert _normalize_ticker("20260211") == ""
    assert _normalize_ticker("2026-02-11") == ""


def test_frontend_normalization_keeps_the_code_history_path_returns():
    """이력 조회는 정규화를 거치지 않는다. 최신 조회가 같은 코드를 내야 두 경로가 맞다."""
    signal = {"stock_code": "0007C0", "stock_name": "아크릴"}

    _normalize_jongga_signal_for_frontend(signal)

    assert signal["stock_code"] == "0007C0"
    assert signal["ticker"] == "0007C0"


def test_price_map_does_not_match_a_different_stock():
    """티커를 키로 쓰는 가격 맵에서 남의 가격이 붙던 자리다."""
    signal = {"stock_code": "0007C0", "entry_price": 1000}

    assert _apply_latest_prices_to_jongga_signals([signal], {"000070": 9999}) == 0
    assert "current_price" not in signal

    assert _apply_latest_prices_to_jongga_signals([signal], {"0007C0": 1200}) == 1
    assert signal["current_price"] == 1200


def test_apply_latest_prices_skips_signals_without_a_usable_ticker():
    signals = [
        {"code": "005930", "entry_price": 1000},
        {"code": "종목명뿐", "entry_price": 1000},
        {"code": "0", "entry_price": 1000},
    ]
    # "000000" 키는 가격 맵을 직렬화할 때 결측 티커가 zfill 되어 생긴다.
    price_map = {"005930": 1100.0, "000000": 9999.0}
    updated = _apply_latest_prices_to_jongga_signals(signals, price_map)

    assert updated == 1
    assert signals[0]["current_price"] == 1100.0
    assert signals[0]["return_pct"] == 10.0
    assert "current_price" not in signals[1]
    assert "current_price" not in signals[2]


def test_jongga_sort_key_ranks_by_grade_then_score():
    assert _jongga_sort_key({"grade": "S", "score": {"total": 10}}) == (3, 10.0)
    assert _jongga_sort_key({"grade": "a", "score": 20}) == (2, 20.0)
    assert _jongga_sort_key({"grade": " b ", "score": 5}) == (1, 5.0)

    # 우선순위 표에 없는 등급은 0 으로 떨어져 S·A·B 뒤에 놓인다.
    assert _jongga_sort_key({"grade": "D", "score": 99}) == (0, 99.0)
    assert _jongga_sort_key({}) == (0, 0.0)
    assert _jongga_sort_key({"grade": "S", "score": "bad"}) == (3, 0)


def test_sort_jongga_signals_puts_higher_grade_first():
    signals = [
        {"grade": "B", "score": 30},
        {"grade": "S", "score": 10},
        {"grade": "A", "score": 20},
        {"grade": "S", "score": 15},
    ]
    _sort_jongga_signals(signals)

    assert [(s["grade"], s["score"]) for s in signals] == [
        ("S", 15),
        ("S", 10),
        ("A", 20),
        ("B", 30),
    ]


def test_normalize_signal_synthesizes_target_and_stop_from_shared_constants():
    signal = {"stock_code": "5930", "stock_name": "삼성전자", "entry_price": "10,000원"}
    _normalize_jongga_signal_for_frontend(signal)

    assert signal["stock_code"] == "005930"
    assert signal["ticker"] == "005930"
    assert signal["name"] == "삼성전자"
    assert signal["target_price"] == round(10000 * (1 + JONGGA_TARGET_PCT))
    assert signal["stop_price"] == round(10000 * (1 - JONGGA_STOP_PCT))


def test_normalize_signal_keeps_valid_stored_exit_prices():
    """저장 목표/손절을 기본 비율로 다시 덮으면 과거 신호의 의도가 바뀐다."""
    signal = {
        "stock_code": "5930",
        "entry_price": 100_000,
        "target_price": 108_000,
        "stop_price": 96_000,
    }

    _normalize_jongga_signal_for_frontend(signal)

    assert signal["target_price"] == 108_000
    assert signal["stop_price"] == 96_000


def test_normalize_signal_replaces_invalid_exit_prices_with_five_and_three_percent_defaults():
    """0·NaN·진입가 반대편 값은 매매 경계가 아니므로 공용 기본값으로 보충해야 한다."""
    signal = {
        "stock_code": "5930",
        "entry_price": 100_000,
        "target_price": "nan",
        "stop_price": 120_000,
    }

    _normalize_jongga_signal_for_frontend(signal)

    assert signal["target_price"] == 105_000
    assert signal["stop_price"] == 97_000


def test_normalize_signal_collapses_placeholder_codes_to_empty_string():
    """자리채움 코드는 원본 모양을 남기지 않고 빈 문자열 하나로 모은다."""
    signal = {"stock_code": "0", "entry_price": 1000}
    _normalize_jongga_signal_for_frontend(signal)

    assert signal["stock_code"] == ""
    assert signal.get("ticker", "") == ""

    # 이미 쓸 수 있는 ticker 가 있으면 그것은 건드리지 않는다.
    kept = {"stock_code": "0", "ticker": "005930", "entry_price": 1000}
    _normalize_jongga_signal_for_frontend(kept)
    assert kept["stock_code"] == "005930"
    assert kept["ticker"] == "005930"


def test_normalize_signal_wraps_scalar_score_and_fills_checklist():
    signal = {"stock_code": "000660", "score": "72", "foreign_5d": "1,000"}
    _normalize_jongga_signal_for_frontend(signal)

    assert signal["score"] == {"total": 72, "base_score": 72, "bonus_score": 0}
    assert signal["checklist"]["supply_positive"] is True
    assert signal["checklist"]["has_news"] is False


def test_normalize_signal_derives_change_pct_when_absent():
    signal = {"stock_code": "005380", "entry_price": 1000, "current_price": 1105}
    _normalize_jongga_signal_for_frontend(signal)
    assert signal["change_pct"] == 10.5

    # return_pct 가 이미 있으면 그것을 그대로 쓴다.
    reused = {"stock_code": "005380", "return_pct": -3.25}
    _normalize_jongga_signal_for_frontend(reused)
    assert reused["change_pct"] == -3.25
