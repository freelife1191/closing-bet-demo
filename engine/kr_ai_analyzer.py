#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - AI Analyzer (Gemini + GPT)

Refactored to use EnhancedNewsCollector and constants from engine.constants.
Removed duplicate news collection logic and magic numbers.

Created: 2024-12-01
Refactored: 2025-02-11 (Phase 4)
"""
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

try:
    import engine.shared as shared_state
except ImportError:
    pass

from engine.collectors.news import EnhancedNewsCollector
from engine.constants import (
    NEWS_SOURCE_WEIGHTS,
    AI_ANALYSIS,
    NEWS_COLLECTION,
    FILE_PATHS,
)
from engine.models import NewsItem

logger = logging.getLogger(__name__)


# =============================================================================
# Mock Data Templates for AI Analysis
# =============================================================================
@dataclass(frozen=True)
class MockAnalysisTemplates:
    """
    AI 분석 Mock 데이터 템플릿

    실제 API 키가 없을 때 사용하는 풍부한 샘플 데이터.
    """
    INVESTMENT_DRIVERS: tuple = (
        "주력 제품의 수출 호조세 지속 및 글로벌 점유율 확대",
        "신규 수주 공시로 인한 향후 3년치 일감 확보",
        "원자재 가격 하락에 따른 마진율 개선 (OPM +3%p 예상)",
        "정부의 K-칩스법 지원 수혜 예상 (세제 혜택)",
        "외국인 및 기관의 동반 순매수세 지속 (수급 개선)",
        "경쟁사 대비 저평가 매력 부각 (PER 밴드 하단)",
        "차세대 신기술 개발 완료 및 상용화 임박",
    )

    RISK_FACTORS: tuple = (
        "글로벌 경기 둔화 우려에 따른 전방 산업 수요 위축",
        "환율 변동성에 따른 단기 환차손 가능성",
        "단기 급등에 따른 차익 실현 매물 출회 가능성",
        "원자재 가격 반등 시 수익성 훼손 우려",
    )

    HYPOTHESIS_TEMPLATES: tuple = (
        "동사는 {name} 분야의 선도 기업으로, 최근 {driver} 점이 긍정적입니다. "
        "특히 3분기 실적 서프라이즈와 함께 연간 가이던스가 상향 조정된 점이 "
        "주가 상승의 주요 트리거가 될 것으로 판단됩니다. 현재 밸류에이션은 "
        "역사적 저점 수준으로, 중장기적 관점에서 매수 접근이 유효해 보입니다.",

        "{name}의 최근 주가 흐름은 견조하며, 이는 {driver} 때문으로 분석됩니다. "
        "기술적 분석상으로도 VCP 패턴 완성 단계에 진입하여 변동성이 축소되고 있으며, "
        "조만간 상방 돌파 시도가 예상됩니다. 다만 {risk} 점은 유의할 필요가 있어, "
        "분할 매수 전략을 권장합니다.",

        "최근 섹터 내 순환매가 유입되면서 {name} 또한 수혜를 입고 있습니다. "
        "핵심 포인트는 {driver}이며, 이는 내년도 실적 성장을 견인할 강력한 모멘텀입니다. "
        "{risk} 우려가 있으나, 현 주가에는 이미 선반영된 것으로 판단되며 "
        "추가 하락 제한적일 것입니다.",
    )


# =============================================================================
# AI Analysis Strategies (Strategy Pattern)
# =============================================================================
class AIStrategy:
    """AI 분석 전략 기본 클래스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.is_available = bool(api_key)

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """분석 수행 (서브클래스에서 구현)"""
        raise NotImplementedError


class GeminiStrategy(AIStrategy):
    """Gemini 기반 분석 전략"""

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """
        Gemini로 종목 분석

        TODO: 실제 API 키가 있으면 google.generativeai 호출
        현재는 Mock 데이터 반환 (풍부한 샘플)
        """
        if not self.is_available:
            return None

        try:
            import random
            templates = MockAnalysisTemplates()

            driver = random.choice(templates.INVESTMENT_DRIVERS)
            risk = random.choice(templates.RISK_FACTORS)
            hypothesis_template = random.choice(templates.HYPOTHESIS_TEMPLATES)

            hypothesis = hypothesis_template.format(
                name=stock_info.get('name', '동사'),
                driver=driver,
                risk=risk,
            )

            rich_reason = f"""
[핵심 투자 포인트]
• {driver}
• {random.choice(templates.INVESTMENT_DRIVERS)}

[리스크 요인]
• {risk}

[종합 의견]
{hypothesis}
"""

            return {
                'action': 'BUY',
                'confidence': random.randint(
                    AI_ANALYSIS.CONFIDENCE_BUY_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX
                ),
                'reason': rich_reason.strip(),
                'news_sentiment': random.choice(['positive', 'positive', 'neutral'])
            }

        except Exception as e:
            logger.error(f"Gemini 분석 실패: {e}")
            return None


class GPTStrategy(AIStrategy):
    """GPT 기반 분석 전략"""

    def analyze(self, stock_info: Dict, news_items: List[NewsItem]) -> Optional[Dict]:
        """
        GPT로 종목 분석

        TODO: 실제 OpenAI API 호출 구현
        현재는 Mock 데이터 반환
        """
        if not self.is_available:
            return None

        try:
            import random

            return {
                'action': 'BUY',
                'confidence': random.randint(
                    AI_ANALYSIS.CONFIDENCE_MIN,
                    AI_ANALYSIS.CONFIDENCE_MAX
                ),
                'reason': 'VCP 패턴 및 외인 매집 추이 확인',
                'target_price': stock_info['price'] * AI_ANALYSIS.TARGET_PRICE_RATIO,
                'stop_loss': stock_info['price'] * AI_ANALYSIS.STOP_LOSS_RATIO
            }

        except Exception as e:
            logger.error(f"GPT 분석 실패: {e}")
            return None


# =============================================================================
# Recommendation Combiner
# =============================================================================
class RecommendationCombiner:
    """여러 AI의 추천을 통합하는 클래스"""

    @staticmethod
    def combine(gemini_result: Optional[Dict], gpt_result: Optional[Dict]) -> Dict:
        """
        두 AI의 추천 통합

        Strategy:
        1. 둘 다 없음 -> HOLD with 0 confidence
        2. 하나만 있음 -> 해당 결과 반환
        3. 둘 다 있음:
           - 액션이 일치하면 -> 평균 confidence
           - 액션이 다르면 -> 높은 confidence 선택
        """
        if not gemini_result and not gpt_result:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'AI 분석 불가'
            }

        if gemini_result and not gpt_result:
            return gemini_result

        if gpt_result and not gemini_result:
            return gpt_result

        # 둘 다 있는 경우
        if gemini_result['action'] == gpt_result['action']:
            # 일치
            return {
                'action': gemini_result['action'],
                'confidence': (gemini_result['confidence'] + gpt_result['confidence']) / 2,
                'reason': f"{gemini_result['reason']} / {gpt_result['reason']}"
            }
        else:
            # 불일치 - 더 높은 신뢰도 선택
            if gemini_result['confidence'] > gpt_result['confidence']:
                return {
                    'action': gemini_result['action'],
                    'confidence': gemini_result['confidence'],
                    'reason': gemini_result['reason'] + ' (우선권)'
                }
            else:
                return {
                    'action': gpt_result['action'],
                    'confidence': gpt_result['confidence'],
                    'reason': gpt_result['reason'] + ' (우선권)'
                }


# =============================================================================
# Main AI Analyzer
# =============================================================================
class KrAiAnalyzer:
    """
    AI 기반 종목 분석기 (Refactored)

    Changes (Phase 4):
    - News collection delegated to EnhancedNewsCollector
    - AI strategies extracted to separate classes
    - Magic numbers moved to constants.py
    - Recommendation combining extracted to dedicated class
    """

    def __init__(self):
        google_api_key = os.getenv("GOOGLE_API_KEY", "")
        openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # AI 전략 초기화
        self.gemini_strategy = GeminiStrategy(google_api_key)
        self.gpt_strategy = GPTStrategy(openai_api_key)

        # 뉴스 수집기 초기화
        self.news_collector = EnhancedNewsCollector()

        if not self.gemini_strategy.is_available and not self.gpt_strategy.is_available:
            logger.warning("AI API 키가 설정되지 않았습니다.")

    def analyze_stock(
        self,
        ticker: str,
        news_items: Optional[List[Dict]] = None
    ) -> Dict:
        """
        종목 AI 분석

        Args:
            ticker: 종목 코드
            news_items: (Optional) 사전 수집된 뉴스 리스트

        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 1. 종목 정보 조회
            stock_info = self._get_stock_info(ticker)
            if not stock_info:
                return {"error": "종목 정보를 찾을 수 없습니다"}

            # 2. 뉴스 수집 (전달받은 뉴스가 없으면 직접 수집)
            if news_items is None:
                news_list = self._collect_news(ticker, stock_info['name'])
            else:
                # Dict 뉴스를 NewsItem으로 변환
                news_list = self._convert_to_news_items(news_items)

            # 3. Gemini 분석
            gemini_result = self.gemini_strategy.analyze(stock_info, news_list)

            # 4. GPT 분석
            gpt_result = self.gpt_strategy.analyze(stock_info, news_list)

            # 5. 결과 통합
            result = {
                'ticker': ticker,
                'name': stock_info['name'],
                'price': stock_info['price'],
                'change_pct': stock_info['change_pct'],
                'news': [self._news_item_to_dict(n) for n in news_list],
                'gemini_recommendation': gemini_result,
                'gpt_recommendation': gpt_result,
                'final_recommendation': RecommendationCombiner.combine(
                    gemini_result, gpt_result
                ),
                'analyzed_at': datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"종목 분석 실패 ({ticker}): {e}")
            return {"error": str(e)}

    def _get_stock_info(self, ticker: str) -> Optional[Dict]:
        """
        종목 기본 정보 조회 (실제 데이터 우선)

        Args:
            ticker: 종목 코드

        Returns:
            종목 정보 딕셔너리 또는 None
        """
        try:
            import pandas as pd

            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            signals_file = os.path.join(root_dir, FILE_PATHS.DATA_DIR, FILE_PATHS.SIGNALS_LOG)

            if os.path.exists(signals_file):
                df = pd.read_csv(signals_file, dtype={'ticker': str})
                stock_data = df[df['ticker'] == ticker].tail(1)

                if not stock_data.empty:
                    row = stock_data.iloc[0]
                    return {
                        'ticker': ticker,
                        'name': row.get('name', f'종목_{ticker}'),
                        'price': int(row.get('current_price', row.get('entry_price', 0))),
                        'change_pct': float(row.get('return_pct', 0)),
                        'market': row.get('market', 'KOSPI'),
                        'score': float(row.get('score', 0)),
                        'vcp_score': float(row.get('vcp_score', 0)),
                        'contraction_ratio': float(row.get('contraction_ratio', 0)),
                        'foreign_5d': int(row.get('foreign_5d', 0)),
                        'inst_5d': int(row.get('inst_5d', 0))
                    }

            # Fallback (최소 정보)
            return {
                'ticker': ticker,
                'name': self._get_stock_name(ticker),
                'price': 0,
                'change_pct': 0,
                'market': 'KOSPI',
                'score': 0
            }

        except Exception as e:
            logger.error(f"종목 정보 조회 실패 ({ticker}): {e}")
            return None

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회 (fallback)"""
        names = {
            '005930': '삼성전자',
            '000270': '기아',
            '035420': 'NAVER',
            '005380': '현대차',
            '068270': '셀트리온',
        }
        return names.get(ticker, f'종목_{ticker}')

    def _collect_news(self, ticker: str, name: str) -> List[NewsItem]:
        """
        뉴스 수집 (EnhancedNewsCollector 위임)

        Args:
            ticker: 종목 코드
            name: 종목명

        Returns:
            NewsItem 리스트
        """
        import asyncio

        try:
            # 비동기 실행을 위한 이벤트 루프 생성
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            news_items = loop.run_until_complete(
                self.news_collector.get_stock_news(
                    code=ticker,
                    limit=NEWS_COLLECTION.MAX_TOTAL_NEWS,
                    name=name
                )
            )
            loop.close()

            return news_items

        except Exception as e:
            logger.warning(f"뉴스 수집 실패 ({ticker}): {e}")
            return []

    def _convert_to_news_items(self, news_dicts: List[Dict]) -> List[NewsItem]:
        """딕셔너리 뉴스를 NewsItem으로 변환"""
        items = []
        for news_dict in news_dicts:
            try:
                items.append(NewsItem(
                    title=news_dict.get('title', ''),
                    summary=news_dict.get('title', ''),
                    source=news_dict.get('source', ''),
                    url=news_dict.get('url', ''),
                    published_at=datetime.now(),  # Fallback
                    weight=news_dict.get('weight', NEWS_SOURCE_WEIGHTS.DEFAULT)
                ))
            except Exception as e:
                logger.debug(f"뉴스 변환 실패: {e}")
        return items

    def _news_item_to_dict(self, news_item: NewsItem) -> Dict:
        """NewsItem을 딕셔너리로 변환"""
        return {
            'title': news_item.title,
            'source': news_item.source,
            'published_at': news_item.published_at.strftime('%Y.%m.%d') if news_item.published_at else '',
            'url': news_item.url,
            'weight': news_item.weight,
        }

    def analyze_multiple_stocks(
        self,
        tickers: List[str],
        news_map: Optional[Dict] = None
    ) -> Dict:
        """
        여러 종목 분석 (배치)

        Args:
            tickers: 종목 코드 리스트
            news_map: (Optional) 종목별 뉴스 맵 {ticker: news_items}

        Returns:
            분석 결과 딕셔너리
        """
        try:
            results = {
                'signals': [],
                'generated_at': datetime.now().isoformat(),
                'total': len(tickers)
            }

            for ticker in tickers:
                if shared_state.STOP_REQUESTED:
                    logger.warning("[STOP] 사용자 중단 요청으로 AI 분석 중단")
                    raise Exception("사용자 요청 중단")

                # 미리 수집된 뉴스 사용
                news = news_map.get(ticker) if news_map else None
                result = self.analyze_stock(ticker, news_items=news)

                if result and 'error' not in result:
                    results['signals'].append(result)
                else:
                    logger.warning(f"분석 결과 제외됨 ({ticker}): {result}")

            return results

        except Exception as e:
            logger.error(f"배치 분석 실패: {e}")
            return {'error': str(e), 'signals': []}


# =============================================================================
# Convenience Functions (Backward Compatibility)
# =============================================================================
def create_analyzer() -> KrAiAnalyzer:
    """분석기 인스턴스 생성 (Convenience Factory)"""
    return KrAiAnalyzer()
