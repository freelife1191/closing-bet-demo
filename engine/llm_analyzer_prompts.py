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


def build_jongga_batch_prompt(
    *,
    items: List[Dict],
    market_status: Dict | None,
    build_market_context_fn: Callable[[Dict | None], str] | None = None,
    build_stocks_text_fn: Callable[[List[Dict]], str] | None = None,
) -> str:
    """closing-bet(종가베팅) 전용 batch 분석 프롬프트.

    - 종가베팅은 VCP 시그널과 별개의 시스템(19점 만점)임을 명시한다.
    - 변동성 수축/Contraction Ratio 평가를 강요하지 않는다.
    - reason은 5개 섹션을 모두 포함하고 250자 이상 작성하도록 강제한다.
    - 응답 스키마는 기존 batch와 동일(name/score/action/confidence/reason)하다.
    """
    from engine.llm_analyzer_formatters import (
        build_jongga_stocks_text,
        build_market_context,
    )

    market_context = (build_market_context_fn or build_market_context)(market_status)
    stocks_text = (build_stocks_text_fn or build_jongga_stocks_text)(items)

    stock_names = [
        str((it.get("stock") or {}).get("stock_name") or (it.get("stock") or {}).get("name") or "")
        for it in items
    ]
    stock_names = [n for n in stock_names if n]
    expected_count = len(stock_names)
    name_list_text = ", ".join(stock_names) if stock_names else "(입력 없음)"

    return f"""
{market_context}

당신은 한국 주식 '종가베팅' 알고리즘의 결과를 검토하는 투자 전문가입니다.
종가베팅 시스템은 VCP(변동성 수축 패턴) 시그널과는 **다른 별개의 알고리즘**이며,
뉴스/거래대금/차트/수급/캔들/기간조정 6개 항목과 가산점으로 구성된 **19점 만점**의 점수 체계를 사용합니다.

각 종목의 매력도를 평가할 때 다음 원칙을 지키세요.
- 종가베팅 점수는 19점 만점이며, 8점 이상부터 강한 신호입니다. 100점 만점이나 다른 척도로 환산해 평가하지 마세요.
- VCP의 변동성 수축 비율(Contraction Ratio)은 종가베팅 입력에 포함되지 않습니다. **언급하지 마세요.**
- 입력 텍스트에 없는 지표를 추측해서 평가하지 마세요. 주어진 점수 분해/뉴스/수급 정보만으로 판단하세요.

[입력 종목]
{stocks_text}

[평가 항목]
1. score (0-3): 뉴스/재료 기반 호재 강도
   - 3: 확실한 호재(대규모 수주, 어닝 서프라이즈, 실적 모멘텀)
   - 2: 긍정적 호재(테마 부각, 실적 개선 기대)
   - 1: 단순/중립적 소식
   - 0: 악재 또는 별다른 호재 없음
2. action: BUY / HOLD / SELL
3. confidence: 0~100 (정수)
4. reason: 다음 5개 섹션을 **모두** 포함하여 **전체 최소 350자 이상**, 각 섹션 **최소 60자 이상**으로 구체적으로 작성하세요.
   각 섹션은 마커(① ② ③ ④ ⑤)와 콜론(:)으로 시작합니다.
   ① 뉴스/재료 분석: 구체적 호재/악재 내용과 산업/테마 영향, 모멘텀 지속성
   ② 거래대금/거래량 평가: 입력의 거래대금·가산점·거래량 비율을 근거로 매수세 강도 해석
   ③ 수급 동향: 외인/기관 5일 합 절대치와 방향성, 매집 강도 해석
   ④ 리스크 요인: 단기 과열도, 변동성, 업종/지수 리스크, 차익 실현 매물 가능성
   ⑤ 매매 전략: 진입(시가·종가·눌림목 중 어느 것), 손절·목표가 기준, 분할/관망 조건 중 최소 1개

[출력 규칙 — 매우 중요]
- 입력으로 주어진 **{expected_count}개 종목 전부**를 빠짐없이 평가하세요. 누락은 허용되지 않습니다.
- 평가 대상 종목명: {name_list_text}
- 응답 JSON 배열의 길이는 정확히 **{expected_count}**이어야 하며, 각 객체의 "name" 필드는 위 종목명 중 하나와 정확히 일치해야 합니다.
- 입력 순서대로 출력하세요. 예시는 1개 객체만 보여주지만 실제 응답에는 {expected_count}개 객체가 필요합니다.
- reason은 한 줄에 모든 섹션을 욱여넣지 말고, 섹션별로 충분한 분석을 담으세요. 350자 미만은 부적합 응답으로 간주됩니다.

[출력 형식]
반드시 아래 포맷의 **JSON 배열**로만 답하세요. (Markdown code block 사용 금지)
아래 예시는 길이/품질의 최소 기준이며, 실제 답변은 이와 비슷하거나 더 풍부해야 합니다.

[
    {{
        "name": "종목명",
        "score": 2,
        "action": "BUY",
        "confidence": 78,
        "reason": "① 뉴스/재료 분석: 대규모 신규 공급계약 발표로 향후 분기 매출 가시성이 확보되었고, 동종 업종 대비 차별화된 수주 모멘텀이 부각되어 시장의 관심이 집중됨. ② 거래대금/거래량 평가: 거래대금 5천억 원과 거래량 가산점 4점이 결합되어 평소 대비 4배 이상의 매수세가 유입되었고, 단순 일일 이벤트가 아닌 시장 관심의 구조적 전환을 시사함. ③ 수급 동향: 외국인 5일 합 +120억, 기관 5일 합 +85억으로 양 주체가 동반 매집 중이며, 외국인 비중이 점진적으로 확대되어 추세 지속성이 강화됨. ④ 리스크 요인: 당일 +15% 급등에 따른 단기 차익 매물 가능성과 업종 인덱스 변동성이 부담이며, 시장 전반 조정 시 변동폭 확대 우려가 있음. ⑤ 매매 전략: 종가 부근 분할 매수 후, 당일 저가를 손절선으로 설정하고 목표가는 직전 고점 직상에서 1차 익절. 변동성 확대 시 관망."
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

