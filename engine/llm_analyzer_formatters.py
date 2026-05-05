#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 포맷팅/텍스트 구성 헬퍼.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def format_news_for_prompt(news_items: List[Dict]) -> str:
    """프롬프트용 뉴스 텍스트 포맷팅."""
    news_text = ""
    for index, news in enumerate(news_items, 1):
        title = news.get("title", "")
        summary = news.get("summary", "")[:200]
        news_text += f"[{index}] 제목: {title}\n내용: {summary}\n\n"
    return news_text


def build_market_context(market_status: Dict | None) -> str:
    """시장 컨텍스트 구성."""
    if not market_status:
        return ""

    return f"""
[시장 상황]
- 상태: {market_status.get('status', 'Unknown')}
- 점수: {market_status.get('total_score', 0)}/100
- KOSPI: {market_status.get('kospi_close', 0)} ({market_status.get('kospi_change', 0)}%)
"""


def extract_stock_info(stock: Dict[str, Any] | Any) -> Tuple[str, str, float, float, float]:
    """Stock 정보 추출."""
    if isinstance(stock, dict):
        stock_name = stock.get("stock_name") or stock.get("name", "Unknown")
        stock_code = stock.get("stock_code") or stock.get("code", "")
        close = stock.get("current_price", 0)
        change_pct = stock.get("change_pct", 0)
        trading_value = stock.get("trading_value", 0)
    else:
        stock_name = getattr(stock, "name", "Unknown")
        stock_code = getattr(stock, "code", "")
        close = getattr(stock, "close", 0)
        change_pct = getattr(stock, "change_pct", 0)
        trading_value = getattr(stock, "trading_value", 0)

    return stock_name, stock_code, close, change_pct, trading_value


def extract_vcp_info(stock: Dict[str, Any] | Any) -> Tuple[float, float]:
    """VCP 정보 추출."""
    vcp_score = 0
    contraction_ratio = 1.0

    if isinstance(stock, dict):
        if "vcp_score" in stock:
            vcp_score = stock["vcp_score"]
            contraction_ratio = stock.get("contraction_ratio", 1.0)
        else:
            score = stock.get("score", 0)
            if hasattr(score, "total"):
                vcp_score = getattr(stock, "vcp_score", 0)
            elif isinstance(score, dict):
                vcp_score = score.get("total", 0)
            else:
                vcp_score = score

            if "contraction_ratio" in stock:
                contraction_ratio = stock["contraction_ratio"]
    else:
        if hasattr(stock, "vcp_score"):
            vcp_score = getattr(stock, "vcp_score", 0)
            contraction_ratio = getattr(stock, "contraction_ratio", 1.0)
        else:
            vcp_score = 0
            contraction_ratio = getattr(stock, "contraction_ratio", 1.0)

    return vcp_score, contraction_ratio


def _format_change_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "0.00%"


def _format_trading_value_eok(value: Any) -> str:
    """거래대금을 '억원' 단위 정수 콤마 포맷으로 변환."""
    try:
        eok = int(round(float(value) / 1e8))
    except (TypeError, ValueError):
        eok = 0
    return f"{eok:,}억원"


def _resolve_jongga_supply_text(item: Dict[str, Any]) -> str:
    """jongga용 외인/기관 5일 합 텍스트 추출.

    item['supply']가 dict나 객체로 주어지면 우선 사용하고,
    없으면 stock['score_details']의 foreign_net_buy / inst_net_buy로 폴백한다.
    """
    supply = item.get("supply")
    foreign = inst = None

    if isinstance(supply, dict):
        foreign = supply.get("foreign_buy_5d")
        inst = supply.get("inst_buy_5d")
    elif supply is not None:
        foreign = getattr(supply, "foreign_buy_5d", None)
        inst = getattr(supply, "inst_buy_5d", None)

    stock = item.get("stock") or {}
    if isinstance(stock, dict):
        details = stock.get("score_details") or {}
        if foreign is None:
            foreign = details.get("foreign_net_buy")
        if inst is None:
            inst = details.get("inst_net_buy")

    if foreign is None and inst is None:
        return "외인/기관 5일 수급 정보 없음"

    foreign = int(foreign or 0)
    inst = int(inst or 0)
    return f"외인 5일합: {foreign:,}원, 기관 5일합: {inst:,}원"


def _extract_jongga_score_breakdown(stock: Dict[str, Any]) -> Tuple[int, Dict[str, int], Dict[str, int]]:
    """closing-bet 시그널 dict에서 (총점, 분해 점수, 가산점 분해) 추출."""
    score = stock.get("score") if isinstance(stock, dict) else None
    if not isinstance(score, dict):
        score = {}
    total = int(score.get("total", 0) or 0)
    breakdown = {
        "news": int(score.get("news", 0) or 0),
        "volume": int(score.get("volume", 0) or 0),
        "chart": int(score.get("chart", 0) or 0),
        "candle": int(score.get("candle", 0) or 0),
        "timing": int(score.get("timing", 0) or 0),
        "supply": int(score.get("supply", 0) or 0),
    }

    details = stock.get("score_details") if isinstance(stock, dict) else None
    if not isinstance(details, dict):
        details = {}
    bonus_breakdown = details.get("bonus_breakdown") or {}
    bonus = {
        "volume": int(bonus_breakdown.get("volume", 0) or 0),
        "candle": int(bonus_breakdown.get("candle", 0) or 0),
        "limit_up": int(bonus_breakdown.get("limit_up", 0) or 0),
    }
    return total, breakdown, bonus


def build_jongga_stocks_text(items: List[Dict]) -> str:
    """closing-bet(종가베팅) 전용 종목 텍스트.

    - VCP 점수/수축 비율 등 잘못된 메타데이터를 노출하지 않는다.
    - 종가베팅 19점 만점 점수 분해와 가산점, 수급 정보를 포함한다.
    - 등락률/거래대금을 사람이 읽기 좋은 형식으로 정돈한다.
    """
    parts: List[str] = []
    for item in items:
        stock = item.get("stock")
        if not stock:
            continue

        stock_name, stock_code, close, change_pct, trading_value = extract_stock_info(stock)
        change_text = _format_change_pct(change_pct)
        trading_text = _format_trading_value_eok(trading_value)
        total, breakdown, bonus = _extract_jongga_score_breakdown(stock if isinstance(stock, dict) else {})

        news_list = item.get("news") or []
        news_lines: List[str] = []
        for index, news in enumerate(news_list[:3], 1):
            if isinstance(news, dict):
                title = news.get("title", "")
                weight = float(news.get("weight", 1.0) or 1.0)
            else:
                title = getattr(news, "title", "")
                weight = float(getattr(news, "weight", 1.0) or 1.0)
            prefix = "[주요] " if weight >= 1.2 else ""
            news_lines.append(f"  {index}. {prefix}{title}")
        news_text = "\n".join(news_lines) if news_lines else "  (관련 뉴스 없음)"

        supply_text = _resolve_jongga_supply_text(item)
        bonus_total = sum(bonus.values())

        block = (
            f"\n=== {stock_name} ({stock_code}) ===\n"
            f"[가격/거래]\n"
            f"- 현재가: {int(close or 0):,}원 (등락: {change_text})\n"
            f"- 거래대금: {trading_text}\n"
            f"\n"
            f"[종가베팅 점수: {total} / 19점]\n"
            f"- 뉴스 {breakdown['news']}/3, 거래대금 {breakdown['volume']}/3, "
            f"차트 {breakdown['chart']}/2, 수급 {breakdown['supply']}/2, "
            f"캔들 {breakdown['candle']}/1, 조정 {breakdown['timing']}/1\n"
            f"- 가산점 {bonus_total}/7 "
            f"(거래량급증 {bonus['volume']}, 장대양봉 {bonus['candle']}, 상한가 {bonus['limit_up']})\n"
            f"\n"
            f"[수급]\n"
            f"- {supply_text}\n"
            f"\n"
            f"[최신 뉴스]\n"
            f"{news_text}\n"
        )
        parts.append(block)

    return "".join(parts)


def build_stocks_text(items: List[Dict]) -> str:
    """배치 프롬프트용 종목 텍스트 구성."""
    stocks_text = ""

    for item in items:
        stock = item.get("stock")
        if not stock:
            continue

        news_list = item.get("news", [])
        supply = item.get("supply")

        news_text = ""
        for index, news in enumerate(news_list[:3], 1):
            weight = getattr(news, "weight", 1.0)
            if isinstance(news, dict):
                weight = news.get("weight", 1.0)
                title = news.get("title", "")
            else:
                title = news.title

            prefix = "[주요] " if weight >= 1.2 else ""
            news_text += f"  {index}. {prefix}{title}\n"

        if supply:
            supply_text = (
                f"외인 5일합: {supply.foreign_buy_5d:,}, "
                f"기관 5일합: {supply.inst_buy_5d:,}"
            )
        else:
            supply_text = "N/A"

        stock_name, stock_code, close, change_pct, trading_value = extract_stock_info(stock)
        vcp_score, contraction_ratio = extract_vcp_info(stock)

        stocks_text += f"""
=== {stock_name} ({stock_code}) ===
[기술적/수급 지표]
- 현재가: {close:,}원 (등락: {change_pct}%)
- **VCP 점수: {vcp_score}점**
- **수축 비율: {contraction_ratio} (낮을수록 좋음)**
- 거래대금: {trading_value // 100000000}억원
- 수급: {supply_text}

[최신 뉴스]
{news_text}
"""

    return stocks_text

