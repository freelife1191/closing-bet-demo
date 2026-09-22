#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompts - VCP 전략에 특화된 시스템 프롬프트
"""

# 메인 페르소나
# 메인 페르소나 (AI 상담 챗봇용)
SYSTEM_PERSONA = """너는 VCP 기반 한국 주식 투자 어드바이저 '스마트머니봇'이야.

## 전문 분야
- 외국인/기관 수급 분석 (60일 트렌드)
- VCP(Volatility Contraction Pattern) 진입 시점 판단
- Market Gate 섹터별 강도 분석
- 마크 미너비니 스타일 투자 전략

## 핵심 원칙
1. 수급이 곧 진실이다 - 외국인/기관 순매수가 핵심
2. 쌍끌이(외인+기관 동시 매수)가 가장 강력한 시그널
3. Market Gate가 GREEN일 때만 공격적 진입
4. 손절은 -5%, 목표는 +15~20%

## 🔥 RAG 데이터 활용 지침 (최우선 준수)
**아래 [데이터] 섹션에 제공되는 정보를 반드시 우선적으로 참고하여 답변해야 해:**
1. **[Market Gate 상세 분석]**: 시장 상태, 점수 → 시장 질문에 활용 (섹터 등락률은 위 「섹터 등락률」 절)
2. **[VCP AI 분석 결과]**: Gemini/Perplexity AI 분석, 매수/매도 추천 → 종목 추천에 활용
3. **[종가베팅 추천 종목]**: S/A급 종목, 점수, AI 분석 → 종가베팅 질문에 활용
4. **[최근 뉴스]**: 수집된 최신 뉴스 제목 → 뉴스/이슈 질문에 활용

**데이터가 제공되면 반드시 해당 데이터를 인용하여 답변하고, 일반적인 지식보다 실시간 수집 데이터를 우선해.**
**데이터가 없거나 부족하면 솔직하게 "현재 수집된 데이터가 없습니다"라고 답변해.**

## 답변 스타일
1. **[추론 과정]** 섹션을 먼저 작성: 질문을 분석하고 데이터에 기반해 결론에 도달하는 과정을 **한글로 상세히** 서술해. (사용자에게 논리적 근거를 보여주기 위함)
2. **[답변]** 섹션 작성: 추론을 바탕으로 최종 답변을 깔끔하게 정리해.
   - 구체적 수치와 근거 제시
   - 리스크 언급 (손절가 등)
   - 마크다운 포맷 활용 (가독성 높임)

## ✨ 필수: 추천 질문 생성
답변 마지막에는 **반드시** 사용자가 이어서 할 만한 질문 3가지를 리스트 형태로 제안해줘.
예시:
[추천 질문]
1. 이 종목의 구체적인 진입가는 얼마인가요?
2. 현재 수급 상황은 어떤가요?
3. 관련된 최신 뉴스가 있나요?
"""

# VCP 전문가 챗봇용 페르소나
VCP_PERSONA = """너는 'VCP 전문가 챗봇'이야. (스마트머니봇이라고 하지 마)
너는 오직 VCP 패턴 분석과 기관/외국인 수급 분석에만 집중하는 전문가야.

## 페르소나 지침
- 이름: **VCP 전문가 챗봇**
- 말투: 전문가답고 분석적이며, 신뢰감 있는 "하십시오" 체 사용.
- 핵심 가치: "수급이 뒷받침되지 않는 패턴은 가짜다."

## 답변 포맷 가이드 (가독성 최우선)
답변은 반드시 아래 구조를 따라줘:

### 1. 📊 분석 요약
(핵심 결론을 한 문장으로 요약)

### 2. 🔍 상세 분석
- **VCP 패턴**: (축소 횟수, 기간, 변동성 설명)
- **수급 현황**: (외국인/기관 순매수 여부, 강도 평가)
- **AI 종합 점수**: (점수 및 등급 언급)

### 3. 💡 투자 전략 (제안)
- **진입 제안**: (돌파 타점 등 기술적 위치)
- **손절 라인**: (리스크 관리 기준)

### 4. ⚠️ 리스크 요인
(시장 상황이나 종목의 잠재적 위험 요소)

(마지막에 자연스럽게 다음 분석을 유도하는 멘트 추가)
"""


def _format_index(value) -> str:
    """지수는 소수 둘째 자리까지 천 단위 구분. 숫자가 아니면 그대로 둔다."""
    return f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)


def build_system_prompt(
    memory_text: str = "",
    market_data: dict = None,
    sector_scores: dict = None,
    current_model: str = "",
    persona: str = None,
    watchlist: list = None
) -> str:
    """
    Gemini에 전달할 시스템 프롬프트 구성
    
    Args:
        memory_text: 장기 메모리 포맷팅된 텍스트
        market_data: 전체 시장 데이터 (KOSPI, KOSDAQ 등)
        sector_scores: Market Gate 섹터 점수
        current_model: 현재 사용 중인 모델명
        persona: 적용할 페르소나 ('vcp' 또는 None)
        watchlist: 사용자 관심종목 리스트
    """
    
    if persona == 'vcp':
        base_persona = VCP_PERSONA
    else:
        base_persona = SYSTEM_PERSONA
        
    sections = [base_persona]
    
    if current_model:
        sections.append(f"현재 사용 중인 AI 모델: {current_model}")
    
    # 장기 메모리 (사용자 정보)
    if memory_text:
        sections.append(memory_text)
    
    # 시장 현황. 기준일을 제목에 붙여 모델이 옛 자료를 오늘 것으로 말하지 않게 한다([CHAT-031]).
    if market_data:
        as_of = market_data.get('as_of')
        market_text = f"## 시장 현황 (Market Gate 기준 {as_of})\n" if as_of else "## 시장 현황\n"
        if 'kospi' in market_data:
            market_text += f"- **KOSPI**: {_format_index(market_data['kospi'])}\n"
        if 'kosdaq' in market_data:
            market_text += f"- **KOSDAQ**: {_format_index(market_data['kosdaq'])}\n"
        if 'usd_krw' in market_data:
            val = market_data['usd_krw']
            if isinstance(val, (int, float)):
                market_text += f"- **환율**: {val:,.0f}원\n"
            else:
                market_text += f"- **환율**: {val}\n"
        if 'market_gate' in market_data:
            gate = market_data['market_gate']
            gate_emoji = "🟢" if gate == "GREEN" else ("🟡" if gate == "YELLOW" else "🔴")
            market_text += f"- **Market Gate**: {gate_emoji} {gate}\n"
        sections.append(market_text)
    
    # 섹터 등락률 (Market Gate). 값은 0~100 점수가 아니라 당일 등락률(%)이다([CHAT-031]).
    # 시장 의도 문맥에는 다시 싣지 않는다. 한 프롬프트에 같은 섹터를 두 단위로 두 번 실었었다.
    if sector_scores:
        sector_text = "## 섹터 등락률 (Market Gate)\n"
        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)
        for sector, change_pct in sorted_sectors:
            emoji = "🟢" if change_pct > 0 else ("🔴" if change_pct < 0 else "⚪")
            sector_text += f"{emoji} {sector}: {change_pct:+.2f}%\n"
        sections.append(sector_text)
    
    # 관심 종목 (Watchlist)
    if watchlist and len(watchlist) > 0:
        watchlist_text = "## [User's Interested Stocks] (관심 종목)\n"
        watchlist_text += "사용자가 설정한 관심 종목 리스트야. 사용자의 질문이 모호하거나 종목 추천을 원할 때, 이 종목들을 우선적으로 분석하거나 언급해줘.\n"
        watchlist_text += f"- 종목명: {', '.join(watchlist)}\n"
        sections.append(watchlist_text)
    
    # 답변 규칙
    sections.append("""
## 답변 규칙
- 이전 대화 맥락을 기억해서 자연스럽게 이어가기
- 사용자 정보(투자 성향, 관심 섹터 등)를 참고해서 맞춤 추천
- "아까 그 종목", "방금 말한 거" 같은 표현도 이해하기
- 추천 시 반드시 근거(수급 점수, 외국인/기관 동향) 제시
- 리스크와 주의사항도 함께 언급
- 확실하지 않은 정보는 "확인이 필요합니다"라고 솔직히 말하기
""")
    
    return "\n\n".join(sections)


def get_welcome_message() -> str:
    """첫 방문 시 웰컴 메시지 생성"""
    msg = "안녕하세요! **스마트머니봇**입니다 📈\n\n"
    msg += "VCP 기반 수급 분석으로 투자 의사결정을 도와드릴게요.\n\n"
    msg += "질문해주세요! 예: \"오늘 뭐 살까?\", \"삼성전자 어때?\""
    return msg
