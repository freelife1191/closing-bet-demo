#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market VCP 시그널 헬퍼 리팩토링 회귀 테스트
"""

from __future__ import annotations

import app.routes.kr_market_vcp_signal_helpers as vcp_helpers
from engine.vcp_ai_orchestration_helpers import VCP_AI_RECOMMENDATION_FIELDS


def test_sort_and_limit_vcp_signals_uses_runtime_limit_when_not_provided(monkeypatch):
    monkeypatch.setattr(vcp_helpers, "resolve_vcp_signals_to_show", lambda **_kwargs: 1)
    signals = [{"score": 10}, {"score": 30}, {"score": 20}]

    result = vcp_helpers._sort_and_limit_vcp_signals(signals)

    assert len(result) == 1
    assert result[0]["score"] == 30


def test_build_vcp_signal_from_row_keeps_low_score_vcp_row():
    """[VCP-032] 합산 점수가 낮아도 OPEN 이고 is_vcp 면 화면에 노출한다. 점수는 정렬에만 쓴다."""
    row = {
        "ticker": "005930",
        "name": "삼성전자",
        "signal_date": "2026-02-24",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 12.0,
        "is_vcp": True,
    }

    result = vcp_helpers._build_vcp_signal_from_row(row)

    assert result is not None
    assert result["score"] == 12.0


def test_build_vcp_signal_from_row_requires_vcp_pattern():
    row = {
        "ticker": "005930",
        "name": "삼성전자",
        "signal_date": "2026-02-24",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 90.0,
        "vcp_score": 4,
        "is_vcp": False,
    }

    assert vcp_helpers._build_vcp_signal_from_row(row) is None

    row["is_vcp"] = True
    result = vcp_helpers._build_vcp_signal_from_row(row)

    assert result is not None
    assert result["ticker"] == "005930"
    assert result["vcp_score"] == 4
    assert result["is_vcp"] is True


def _vcp_row(**overrides) -> dict:
    row = {
        "ticker": "034730",
        "name": "SK",
        "signal_date": "2026-05-05",
        "market": "KOSPI",
        "status": "OPEN",
        "score": 90.0,
        "vcp_score": 4,
        "is_vcp": True,
        "entry_price": 475_500,
        "current_price": 586_000,
    }
    row.update(overrides)
    return row


def test_exit_prices_follow_entry_price_not_current_price():
    """손절가와 목표가의 기준가는 현재가가 아니라 진입가다.

    신호 발생 뒤 주가가 오른 종목에서 현재가를 기준으로 삼으면 손절가가 진입가
    위에 놓여, 체결되는 순간 이익 실현이 되는 주문이 손실 구간처럼 표시된다.
    """
    result = vcp_helpers._build_vcp_signal_from_row(_vcp_row())

    assert result is not None
    assert result["stop_price"] == round(475_500 * 0.97)
    assert result["target_price"] == round(475_500 * 1.05)


def test_exit_prices_never_invert_against_entry_price():
    """진입가 대비 방향이 뒤집히지 않는다.

    현재가가 진입가보다 크게 높든 낮든 손절가는 진입가 아래, 목표가는 진입가
    위에 놓여야 한다.
    """
    for current_price in (200_000, 475_500, 900_000):
        result = vcp_helpers._build_vcp_signal_from_row(
            _vcp_row(current_price=current_price)
        )

        assert result is not None
        assert result["stop_price"] < result["entry_price"]
        assert result["target_price"] > result["entry_price"]


def test_exit_prices_keep_backend_values_when_present():
    """저장된 값이 있으면 다시 만들지 않고 그대로 내보낸다."""
    result = vcp_helpers._build_vcp_signal_from_row(
        _vcp_row(stop_price=400_000, target_price=520_000)
    )

    assert result is not None
    assert result["stop_price"] == 400_000
    assert result["target_price"] == 520_000


def test_exit_prices_stay_empty_without_entry_price():
    """진입가가 없으면 임의로 만들지 않고 비워 둔다."""
    result = vcp_helpers._build_vcp_signal_from_row(_vcp_row(entry_price=0))

    assert result is not None
    assert result["stop_price"] is None
    assert result["target_price"] is None


def test_exit_prices_fill_only_the_missing_side():
    """한쪽만 저장되어 있으면 비어 있는 쪽만 채운다."""
    only_stop = vcp_helpers._build_vcp_signal_from_row(_vcp_row(stop_price=400_000))
    only_target = vcp_helpers._build_vcp_signal_from_row(_vcp_row(target_price=520_000))

    assert only_stop is not None
    assert only_stop["stop_price"] == 400_000
    assert only_stop["target_price"] == round(475_500 * 1.05)

    assert only_target is not None
    assert only_target["target_price"] == 520_000
    assert only_target["stop_price"] == round(475_500 * 0.97)


def test_exit_prices_survive_unusable_entry_price():
    """진입가가 NaN 이나 무한대여도 한 행이 응답 전체를 무너뜨리지 않는다."""
    for broken in (float("nan"), float("inf"), "inf"):
        result = vcp_helpers._build_vcp_signal_from_row(_vcp_row(entry_price=broken))

        assert result is not None
        assert result["stop_price"] is None
        assert result["target_price"] is None


def test_ai_data_map_pads_ticker_to_six_digits():
    """AI 분석 파일의 종목 코드는 여섯 자리로 맞춰서 키로 삼는다.

    시그널 쪽 ticker 는 _build_vcp_signal_from_row 가 항상 zfill(6) 으로 만든다.
    분석 파일은 JSON 이라 종목 코드가 정수 5930 으로 저장되어 있을 수 있는데,
    그 값을 그대로 키로 쓰면 두 자료가 한 종목도 만나지 못해 AI 추천 열이 통째로
    빈다.
    """
    ai_data_map = vcp_helpers._build_ai_data_map(
        {"signals": [{"ticker": 5930, "gemini_recommendation": {"action": "BUY"}}]}
    )

    assert list(ai_data_map) == ["005930"]


def test_reanalysis_prompt_payload_preserves_zero_and_omits_missing_one_day_supply():
    with_zero = vcp_helpers._build_vcp_stock_payload(
        {"ticker": "5930", "foreign_1d": 0, "inst_1d": -7}
    )
    without_one_day_supply = vcp_helpers._build_vcp_stock_payload({"ticker": "5930"})

    assert with_zero["foreign_1d"] == 0.0
    assert with_zero["inst_1d"] == -7.0
    assert "foreign_1d" not in without_one_day_supply
    assert "inst_1d" not in without_one_day_supply


def test_ai_data_map_drops_entries_without_a_ticker():
    """종목 코드가 없는 항목은 맵에 넣지 않는다.

    zfill(6) 은 빈 문자열도 "000000" 으로 만든다. 그것을 키로 받아 주면 코드가
    빠진 여러 항목이 한 자리에 겹쳐 쌓이고, 마지막 항목의 분석이 그 자리를
    차지한다.
    """
    ai_data_map = vcp_helpers._build_ai_data_map(
        {
            "signals": [
                {"gemini_recommendation": {"action": "BUY"}},
                {"ticker": 0, "gemini_recommendation": {"action": "HOLD"}},
                {"ticker": "034730", "gemini_recommendation": {"action": "BUY"}},
            ]
        }
    )

    assert list(ai_data_map) == ["034730"]


def test_ai_data_map_survives_an_unusable_payload():
    """파일 모양이 어긋나도 빈 맵으로 끝내고 응답을 무너뜨리지 않는다."""
    assert vcp_helpers._build_ai_data_map(None) == {}
    assert vcp_helpers._build_ai_data_map({"signals": ["034730"]}) == {}


def test_legacy_merge_fills_only_the_missing_recommendation():
    """legacy 파일은 비어 있는 자리만 채우고 이미 있는 추천은 건드리지 않는다.

    legacy 는 예전 형식의 분석 파일이라 오늘 것보다 오래된 판정을 담고 있다.
    조건 없이 대입하면 방금 재분석한 추천이 지난 판정으로 되돌아간다.
    """
    today = {"action": "BUY", "confidence": 80, "reason": "오늘 재분석한 사유입니다."}
    legacy = {"action": "HOLD", "confidence": 50, "reason": "지난 분석의 사유입니다."}
    ai_data_map = {"034730": {"ticker": "034730", "gemini_recommendation": today}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {
            "signals": [
                {"ticker": "034730", "gemini_recommendation": legacy,
                 "perplexity_recommendation": legacy}
            ]
        },
    )

    assert ai_data_map["034730"]["gemini_recommendation"] == today
    assert ai_data_map["034730"]["perplexity_recommendation"] == legacy


def test_legacy_merge_does_not_bring_in_new_tickers():
    """legacy 에만 있는 종목은 맵에 들이지 않는다.

    이 함수는 오늘 분석의 빈 필드를 보강하는 자리다. 새 종목까지 받아 주면
    오늘 시그널에 없는 종목의 지난 분석이 응답에 섞인다.
    """
    ai_data_map = {"034730": {"ticker": "034730"}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {"signals": [{"ticker": "005930", "gemini_recommendation": {"action": "BUY"}}]},
    )

    assert list(ai_data_map) == ["034730"]


def test_legacy_merge_fills_the_same_three_provider_fields():
    """[VCP-018] 회귀: 세 프로바이더가 모두 같은 규칙으로 보강된다.

    보강 목록에 gemini 와 perplexity 만 적혀 있던 동안, 지금 자료가 두 번째
    프로바이더로 쓰는 gpt_recommendation 은 legacy 에만 있으면 응답에 닿지 못했다.
    `_merge_ai_data_into_vcp_signals` 는 세 필드를 모두 내보내므로 비대칭은 보강
    함수 한 곳에만 있었다.
    """
    legacy = {"action": "BUY", "confidence": 70, "reason": "지난 분석이 남긴 사유입니다."}
    ai_data_map = {"005930": {"ticker": "005930"}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {
            "signals": [
                {
                    "ticker": "005930",
                    "gemini_recommendation": legacy,
                    "gpt_recommendation": legacy,
                    "perplexity_recommendation": legacy,
                }
            ]
        },
    )

    merged = ai_data_map["005930"]
    assert [merged.get(field) for field in VCP_AI_RECOMMENDATION_FIELDS] == [
        legacy,
        legacy,
        legacy,
    ]


def test_legacy_merge_keeps_a_failed_verdict_instead_of_reaching_for_legacy():
    """[VCP-018] 회귀: 오늘 값이 실패 기록이어도 legacy 로 바꾸지 않는다.

    이 맵은 다음 단계에서 CSV 가 만든 시그널 판정을 덮어쓰는 자리다. 실패 기록을
    legacy 의 정상 판정으로 대체하면 오늘 CSV 의 판정이 지난 달 판정에 밀려난다.
    보강은 비어 있는 자리를 채우는 데까지만 한다.
    """
    failed = {"action": "N/A", "confidence": 0, "reason": "분석 실패"}
    legacy = {"action": "HOLD", "confidence": 55, "reason": "지난 분석이 남긴 사유입니다."}
    ai_data_map = {"005930": {"ticker": "005930", "gpt_recommendation": failed}}

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {"signals": [{"ticker": "005930", "gpt_recommendation": legacy}]},
    )

    assert ai_data_map["005930"]["gpt_recommendation"] == failed


def test_legacy_merge_does_not_push_todays_csv_verdict_out_of_the_signal():
    """[VCP-018] 회귀: 오늘 CSV 가 만든 판정이 legacy 판정에 밀려나지 않는다.

    시그널의 gemini_recommendation 은 `_build_vcp_signal_from_row` 가 CSV 행에서
    만든다. 그러므로 오늘 JSON 의 같은 필드가 실패 기록이어도 시그널 쪽은 정상인
    상태가 성립한다. 보강이 그 실패 기록을 legacy 로 대체하면, 이어지는 병합이
    맵의 값으로 시그널을 덮어써서 오늘 BUY 가 지난 달 SELL 로 바뀐다. 세 단계를
    이어서 태워야 드러나는 경로라 함수 하나만 보는 검사로는 잡히지 않는다.
    """
    row = {
        "ticker": "005930", "name": "삼성전자", "signal_date": "2026-05-05",
        "market": "KOSPI", "status": "OPEN", "score": 82, "vcp_score": 14.0,
        "is_vcp": True, "entry_price": 100000, "current_price": 100000,
        "ai_action": "BUY", "ai_confidence": 80, "ai_reason": "오늘 CSV 가 담은 사유입니다.",
    }
    signals = [vcp_helpers._build_vcp_signal_from_row(row)]
    ai_data_map = vcp_helpers._build_ai_data_map(
        {
            "signals": [
                {
                    "ticker": "005930",
                    "gemini_recommendation": {
                        "action": "N/A", "confidence": 0, "reason": "분석 실패",
                    },
                }
            ]
        }
    )

    vcp_helpers._merge_legacy_ai_fields_into_map(
        ai_data_map,
        {
            "signals": [
                {
                    "ticker": "005930",
                    "gemini_recommendation": {
                        "action": "SELL", "confidence": 40,
                        "reason": "지난 달 분석이 남긴 사유입니다.",
                    },
                }
            ]
        },
    )
    vcp_helpers._merge_ai_data_into_vcp_signals(signals, ai_data_map)

    assert signals[0]["gemini_recommendation"]["action"] == "BUY"
    assert signals[0]["gemini_recommendation"]["reason"] == "오늘 CSV 가 담은 사유입니다."


# [VCP-040] Gemini 가 비면 유효한 다른 프로바이더 추천을 판정으로 쓴다.
_GPT_OK = {"action": "hold", "confidence": "72", "reason": "수급은 긍정적이나 돌파 확인이 필요합니다."}
_GEMINI_OK = {"action": "BUY", "confidence": 68, "reason": "수축 비율과 동반 순매수가 확인됩니다."}


def test_extract_falls_back_to_gpt_when_gemini_is_missing():
    ai_results = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}

    assert vcp_helpers._extract_vcp_ai_recommendation(ai_results, "033530") == (
        True, "HOLD", 72, _GPT_OK["reason"],
    )


def test_extract_prefers_gemini_when_both_are_valid():
    ai_results = {"033530": {"gemini_recommendation": _GEMINI_OK, "gpt_recommendation": _GPT_OK}}

    assert vcp_helpers._extract_vcp_ai_recommendation(ai_results, "033530")[1:3] == ("BUY", 68)


def test_extract_fails_with_missing_confidence_when_every_provider_failed():
    failed = {"action": "N/A", "confidence": 0, "reason": "분석 실패"}
    ai_results = {
        "033530": {
            "gemini_recommendation": None,
            "gpt_recommendation": failed,
            "perplexity_recommendation": None,
        }
    }

    assert vcp_helpers._extract_vcp_ai_recommendation(ai_results, "033530") == (
        False, "N/A", None, "분석 실패",
    )


def test_reanalysis_counts_gpt_fallback_but_keeps_it_out_of_the_gemini_cache_slot():
    import pandas as pd

    signals_df = pd.DataFrame(
        [{"ticker": "033530", "ai_action": "N/A", "ai_confidence": 0, "ai_reason": "분석 실패"}]
    )
    ai_results = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}

    updated, still_failed, recommendations = vcp_helpers._apply_vcp_reanalysis_updates(
        signals_df, [(0, {"ticker": "033530"})], ai_results
    )

    assert (updated, still_failed) == (1, 0)
    assert signals_df.at[0, "ai_action"] == "HOLD"
    # update_vcp_ai_cache_files 가 이 dict 를 gemini_recommendation 칸에 덮어쓴다
    assert recommendations == {}


def _valid_verdict_frame():
    import pandas as pd

    signals_df = pd.DataFrame(
        [{"ticker": "033530", "ai_action": "HOLD", "ai_confidence": 72, "ai_reason": _GPT_OK["reason"]}]
    )
    return signals_df, [(0, signals_df.iloc[0].to_dict())]


def test_auto_reanalysis_keeps_an_existing_valid_verdict_when_the_retry_fails():
    """수집이 쓴 GPT 판정을 Gemini 만 다시 부른 재시도의 실패로 덮지 않는다."""
    signals_df, rows = _valid_verdict_frame()
    retry_failed = {"033530": {"gemini_recommendation": None, "gpt_recommendation": None}}

    result = vcp_helpers._apply_vcp_reanalysis_updates(
        signals_df, rows, retry_failed, keep_valid_verdicts=True
    )

    assert result == (0, 1, {})
    assert (signals_df.at[0, "ai_action"], signals_df.at[0, "ai_confidence"]) == ("HOLD", 72)


def test_forced_reanalysis_still_records_a_failed_retry():
    """강제 모드는 [VCP-039] 계약대로 처리했지만 실패한 행을 실패로 기록한다."""
    signals_df, rows = _valid_verdict_frame()
    retry_failed = {"033530": {"gemini_recommendation": None, "gpt_recommendation": None}}

    vcp_helpers._apply_vcp_reanalysis_updates(signals_df, rows, retry_failed)

    assert signals_df.at[0, "ai_reason"] == "분석 실패"


def _csv_signal(action: str, reason: str) -> dict:
    return vcp_helpers._build_vcp_signal_from_row(
        {
            "ticker": "033530", "name": "SJG세종", "signal_date": "2026-09-21",
            "market": "KOSPI", "status": "OPEN", "score": 42, "vcp_score": 8.0,
            "is_vcp": True, "entry_price": 7550, "current_price": 7550,
            "ai_action": action, "ai_confidence": 72, "ai_reason": reason,
        }
    )


def test_merge_does_not_show_a_gpt_fallback_verdict_under_the_gemini_label():
    signals = [_csv_signal("HOLD", _GPT_OK["reason"])]
    ai_data_map = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}

    vcp_helpers._merge_ai_data_into_vcp_signals(signals, ai_data_map)

    assert signals[0]["gemini_recommendation"] is None
    assert signals[0]["gpt_recommendation"] == _GPT_OK


def test_merge_hides_an_older_gpt_verdict_after_a_forced_second_reanalysis():
    """강제 Second 재분석은 CSV 를 쓰지 않으므로 CSV 의 옛 GPT 판정이 캐시의 새 GPT 와 다르다."""
    signals = [_csv_signal("HOLD", "수집 때 받은 옛 GPT 사유입니다.")]
    ai_data_map = {"033530": {"gemini_recommendation": None, "gpt_recommendation": _GPT_OK}}

    vcp_helpers._merge_ai_data_into_vcp_signals(signals, ai_data_map)

    assert signals[0]["gemini_recommendation"] is None


def test_merge_keeps_the_csv_verdict_when_no_provider_in_the_cache_is_valid():
    signals = [_csv_signal("BUY", _GEMINI_OK["reason"])]
    ai_data_map = {"033530": {"gemini_recommendation": None, "gpt_recommendation": None}}

    vcp_helpers._merge_ai_data_into_vcp_signals(signals, ai_data_map)

    assert signals[0]["gemini_recommendation"]["action"] == "BUY"


def test_extract_reads_legacy_perplexity_only_row():
    # [VCP-046] 2026-02 캐시는 두 번째 판정을 perplexity 칸에만 담았다. 새로 쓰지 않아도 계속 읽는다
    ai_results = {
        "000001": {"perplexity_recommendation": {"action": "HOLD", "confidence": 60, "reason": "과거 캐시 판정"}}
    }

    assert vcp_helpers._extract_vcp_ai_recommendation(ai_results, "000001") == (True, "HOLD", 60, "과거 캐시 판정")


def test_supply_keeps_missing_apart_from_real_zero():
    """[VCP-054] 수급 결측(빈 칸·NaN)은 None, 실제 0 은 0 이다. 0 으로 채우면 화면이 「순매수 0」을 그린다."""
    missing = vcp_helpers._build_vcp_signal_from_row(_vcp_row(foreign_5d=float("nan"), inst_5d=""))
    zero = vcp_helpers._build_vcp_signal_from_row(_vcp_row(foreign_5d=0, inst_5d=-1_500))

    assert missing is not None and zero is not None
    assert missing["foreign_5d"] is None
    assert missing["inst_5d"] is None
    assert zero["foreign_5d"] == 0
    assert zero["inst_5d"] == -1_500
