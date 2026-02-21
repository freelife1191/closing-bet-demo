#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 추천 질문 생성 프롬프트 템플릿
"""

from typing import Optional


def build_daily_suggestions_prompt(
    persona: Optional[str],
    market_summary: str,
    vcp_text: str,
    news_text: str,
    watchlist_text: str,
    jongga_text: str = "",
) -> str:
    """페르소나별 일일 추천 질문 프롬프트 생성."""
    if persona == "vcp":
        prompt = f"""
너는 'VCP(변동성 축소 패턴) 주식 투자 전문가' AI야.
현재 시장 데이터, VCP 분석 결과, 수급 현황을 심도 있게 분석해서, 전문 트레이더가 관심을 가질 만한 **핵심 질문 5가지**를 제안해줘.
일반적인 시장 질문보다는 '차트 패턴', '수급', '매수 타점', '리스크 관리'에 초점을 맞춰야 해.

## 현재 시장 상황
- Market Gate: {market_summary}
- VCP 추천주 분석:
{vcp_text[:800]}...
- 주요 뉴스:
{news_text[:300]}...
{watchlist_text}
"""
    else:
        prompt = f"""
너는 친절하고 명확한 '한국 주식 투자 어드바이저' AI야.
현재 시장 흐름, 주요 뉴스, 종가베팅 데이터, 관심 종목의 상태를 종합해서, 일반 투자자가 가장 궁금해할 만한 **핵심 질문 5가지**를 제안해줘.
'시장 전망', '뉴스 분석', '종목 상담', '종가베팅 전략' 등 균형 잡힌 주제로 구성해줘.

## 현재 시장 상황
- Market Gate: {market_summary}
- VCP 추천주 분석:
{vcp_text[:500]}...
{jongga_text}
- 주요 뉴스:
{news_text[:500]}...
{watchlist_text}
"""

    prompt += """
## 요청 사항
1. JSON 포맷으로 반환해줘.
2. 각 항목은 `title`(버튼용 짧은 제목), `prompt`(실제 질문 내용), `desc`(설명), `icon`(FontAwesome 클래스)을 포함해야 해.
3. 총 5개 생성.
4. 예시:
[
  {{ "title": "시장 급락 대응", "prompt": "오늘 코스닥 급락의 주 원인과 향후 대응 전략은?", "desc": "시장 하락 원인 분석", "icon": "fas fa-chart-line" }},
  {{ "title": "VCP 종목 추천", "prompt": "오늘 포착된 VCP 종목 중 가장 점수가 높은 종목 상세 분석해줘", "desc": "AI 선정 베스트 종목", "icon": "fas fa-search-dollar" }}
]
"""
    return prompt

