#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Analyzer 프롬프트 빌더.
"""

from __future__ import annotations

from typing import Callable, Dict, List


def build_sentiment_prompt(
    *,
    stock_name: str,
    news_items: List[Dict],
    format_news_for_prompt_fn: Callable[[List[Dict]], str],
) -> str:
    """감성 분석 프롬프트 구성."""
    news_text = format_news_for_prompt_fn(news_items)
    return f"""
당신은 주식 투자 전문가입니다. 주어지는 뉴스들을 분석하여 호재 강도를 평가하세요.

다음은 '{stock_name}' 종목에 대한 최신 뉴스들입니다.
이 뉴스들을 **종합적으로 분석**하여 현재 시점에서의 호재 강도를 0~3점으로 평가하세요.

[뉴스 목록]
{news_text}

[점수 기준]
3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈, 경영권 분쟁 등)
2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
1점: 단순/중립적 소식
0점: 악재 또는 별다른 호재 없음

[출력 형식]
뉴스 3개를 따로 평가하지 말고, **종목 전체에 대한 하나의 평가**를 내리세요.
반드시 아래 포맷의 **단일 JSON 객체**로만 답하세요. (Markdown code block 없이)

Format: {{"score": 2, "reason": "종합적인 요약 이유"}}
"""


def build_batch_prompt(
    *,
    items: List[Dict],
    market_status: Dict | None,
    build_market_context_fn: Callable[[Dict | None], str],
    build_stocks_text_fn: Callable[[List[Dict]], str],
) -> str:
    """배치 분석 프롬프트 구성."""
    market_context = build_market_context_fn(market_status)
    stocks_text = build_stocks_text_fn(items)

    return f"""
{market_context}

다음 종목들을 분석하여 투자 매력도를 평가하세요.
특히 **VCP(변동성 수축 패턴)의 기술적 완성도**를 반드시 평가에 포함해야 합니다.

[입력 데이터]
{stocks_text}

[평가 기준]
0. **VCP 분석 (필수)**:
   - 변동성 수축(Contraction Ratio)이 0.1~0.5 사이로 건전한가?
   - 거래량(Volume)이 급감하며 매물 소화가 잘 되었는가?
   - 이 기술적 지표가 점수에 **가장 큰 영향**을 미쳐야 함.
1. **Score (0-3)**: 뉴스/재료 기반 호재 강도
   - 3점: 확실한 호재 (대규모 수주, 상한가 재료, 어닝 서프라이즈)
   - 2점: 긍정적 호재 (실적 개선, 기대감, 테마 상승)
   - 1점: 단순/중립적 소식
   - 0점: 악재 또는 별다른 호재 없음
2. **Action**: BUY / HOLD / SELL
3. **Confidence**: 확신도 (0-100%)
4. **Reason**: 다음 요소를 종합하여 **3~5줄**로 구체적 근거를 포함하여 작성하세요.
   - 뉴스/재료 분석: 구체적 호재/악재 내용과 산업 영향도
   - VCP 기술적 분석: 수축 비율, 거래량 추이, 패턴 완성도 평가
   - 수급 동향: 외인/기관 매매 추이와 의미
   - 리스크 요인: 단기 과열, 밸류에이션, 업종 리스크 등
   - 매매 전략: 매수 시점, 목표가, 손절 기준 구체적 제시

[출력 형식]
반드시 아래 포맷의 **JSON 배열**로만 답하세요. (Markdown code block 없이)

[
    {{
        "name": "종목명",
        "score": 2,
        "action": "BUY",
        "confidence": 85,
        "reason": "대규모 신규 수주 발표로 강한 호재. 외인/기관 동반 순매수 유입 중. 시가 매수 후 전저점 이탈 시 손절 권장."
    }}
]
"""


def build_summary_prompt(*, signals: List[Dict]) -> str:
    """시장 요약 프롬프트 구성."""
    sorted_signals = sorted(
        signals,
        key=lambda value: value.get("score", {}).get("total", 0),
        reverse=True,
    )
    top_signals = sorted_signals[:30]

    stocks_text = ""
    for signal in top_signals:
        grade = signal.get("grade", "C")
        score = signal.get("score", {}).get("total", 0)
        name = signal.get("stock_name", "")
        reason = signal.get("score", {}).get("llm_reason", "")
        stocks_text += f"- {name} ({grade}급/{score}점): {reason}\n"

    return f"""
당신은 주식 시장 분석 전문가입니다. 오늘 '종가베팅' 알고리즘에 포착된 상위 종목 리스트입니다.
이들을 분석하여 다음 내용을 포함한 3~5줄 내외의 시장 요약 리포트를 작성해주세요.

1. 오늘의 주도 섹터/테마
2. 시장의 전반적인 분위기 (수급 강도 등)
3. 특히 주목할만한 특징

[종목 리스트]
{stocks_text}

[출력 형식]
줄글 형태로 간결하게 요약. (Markdown 사용 가능)
"""

