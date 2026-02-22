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

