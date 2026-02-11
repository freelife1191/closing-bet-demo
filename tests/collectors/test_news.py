#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for News Collector Module

news.py 모듈의 EnhancedNewsCollector 클래스를 테스트합니다.

Created: 2026-02-11
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from engine.collectors.news import EnhancedNewsCollector
from engine.models import NewsItem


class TestEnhancedNewsCollector:
    """EnhancedNewsCollector 클래스 테스트"""

    @pytest.fixture
    def collector(self):
        """테스트용 EnhancedNewsCollector 인스턴스"""
        return EnhancedNewsCollector(config=None)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, collector):
        """초기화 테스트"""
        assert collector is not None
        assert collector.config is None
        assert hasattr(collector, 'headers')
        assert 'User-Agent' in collector.headers

    def test_major_sources_initialization(self, collector):
        """주요 언론사 가중치 초기화 테스트"""
        assert hasattr(collector, 'MAJOR_SOURCES')
        assert "한국경제" in collector.MAJOR_SOURCES
        assert "매일경제" in collector.MAJOR_SOURCES
        assert collector.MAJOR_SOURCES["한국경제"] == 0.9

    def test_platform_reliability_initialization(self, collector):
        """플랫폼 신뢰도 초기화 테스트"""
        assert hasattr(collector, 'PLATFORM_RELIABILITY')
        assert "finance" in collector.PLATFORM_RELIABILITY
        assert "search_naver" in collector.PLATFORM_RELIABILITY
        assert "search_daum" in collector.PLATFORM_RELIABILITY
        assert collector.PLATFORM_RELIABILITY["finance"] == 0.9

    # ========================================================================
    # get_stock_news Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_stock_news_not_implemented(self, collector):
        """get_top_gainers는 지원하지 않음 테스트"""
        with pytest.raises(NotImplementedError, match="does not support get_top_gainers"):
            await collector.get_top_gainers("KOSPI", 10)

    @pytest.mark.asyncio
    async def test_get_stock_news_with_limit(self, collector):
        """limit 파라미터로 뉴스 수집 테스트"""
        mock_news_list = [
            NewsItem(
                title=f"뉴스 {i}",
                summary=f"요약 {i}",
                source="한국경제",
                url=f"https://example.com/news/{i}",
                published_at=datetime.now(),
                weight=0.9
            )
            for i in range(10)
        ]

        with patch.object(collector, '_fetch_naver_finance_news', return_value=[]):
            with patch.object(collector, '_fetch_naver_search_news', return_value=[]):
                with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                    # 모든 소스가 빈 리스트를 반환하면 빈 결과
                    result = await collector.get_stock_news("005930", 5)
                    assert result == []

    @pytest.mark.asyncio
    async def test_get_stock_news_uses_name_parameter(self, collector):
        """name 파라미터 사용 테스트"""
        with patch.object(collector, '_get_stock_name', return_value="테스트종목"):
            with patch.object(collector, '_fetch_naver_finance_news', return_value=[]):
                with patch.object(collector, '_fetch_naver_search_news', return_value=[]):
                    with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                        result = await collector.get_stock_news("005930", 5)
                        assert isinstance(result, list)

    # ========================================================================
    # _get_weight Tests
    # ========================================================================

    def test_get_weight_major_source(self, collector):
        """주요 언론사 가중치 계산 테스트"""
        weight = collector._get_weight("한국경제", platform='finance')
        # Publisher Weight (0.9) * Platform Reliability (0.9) = 0.81
        assert weight == 0.81

    def test_get_weight_minor_source(self, collector):
        """일반 언론사 가중치 계산 테스트"""
        weight = collector._get_weight("소방언론", platform='finance')
        # Default Publisher Weight (0.7) * Platform Reliability (0.9) = 0.63
        assert weight == 0.63

    def test_get_weight_different_platforms(self, collector):
        """다른 플랫폼 신뢰도 테스트"""
        major_weight = collector._get_weight("한국경제", platform='finance')
        naver_search_weight = collector._get_weight("한국경제", platform='search_naver')
        daum_search_weight = collector._get_weight("한국경제", platform='search_daum')

        # finance > search_naver > search_daum
        assert major_weight >= naver_search_weight >= daum_search_weight

    def test_get_weight_rounding(self, collector):
        """가중치 반올림 테스트"""
        weight = collector._get_weight("한국경제", platform='search_naver')
        # 0.9 * 0.85 = 0.765
        assert weight == round(0.9 * 0.85, 2)

    # ========================================================================
    # _get_stock_name Tests
    # ========================================================================

    def test_get_stock_name_known_ticker(self, collector):
        """알려진 종목 코드 이름 조회 테스트"""
        name = collector._get_stock_name("005930")
        assert name == "삼성전자"

    def test_get_stock_name_unknown_ticker(self, collector):
        """알려지지 않은 종목 코드 이름 조회 테스트"""
        name = collector._get_stock_name("999999")
        assert name == "알 수 없는 종목"


# ========================================================================
# Mock Fetcher Tests
# ========================================================================

class TestNewsCollectorFetchers:
    """뉴스 수집 메서드 테스트"""

    @pytest.fixture
    def collector(self):
        return EnhancedNewsCollector()

    @pytest.mark.asyncio
    async def test_fetch_naver_finance_news_success(self, collector):
        """네이버 금융 뉴스 성공 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.text = """
        <html>
            <table class="type5">
                <tr>
                    <td class="title"><a href="/news/123">테스트 뉴스</a></td>
                    <td class="info">한국경제</td>
                </tr>
            </table>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_table = Mock()
                mock_row = Mock()
                mock_title_el = Mock()
                mock_source_el = Mock()

                mock_title_el.text = "테스트 뉴스"
                mock_title_el.get = Mock(return_value="/news/123")

                mock_source_el.text = "한국경제"

                type(mock_row).select_one = Mock(side_effect=lambda x: {
                    'td.title a': mock_title_el,
                    'td.info': mock_source_el,
                }.get(x))

                mock_table.select = Mock(return_value=[mock_row])
                mock_soup.select_one = Mock(return_value=mock_table)
                mock_bs.return_value = mock_soup

                seen_titles = set()
                result = collector._fetch_naver_finance_news("005930", 5, seen_titles)

                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_fetch_naver_finance_news_http_error(self, collector):
        """HTTP 오류 시 네이버 금융 뉴스 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = False

        with patch('requests.get', return_value=mock_response):
            seen_titles = set()
            result = collector._fetch_naver_finance_news("005930", 5, seen_titles)

            # HTTP 오류 시 빈 리스트 반환
            assert result == []

    @pytest.mark.asyncio
    async def test_fetch_naver_search_news_with_duplicate_title(self, collector):
        """중복 제목 필터링 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_item = Mock()
                mock_title_el = Mock()

                mock_title_el.get = Mock(return_value="title")
                mock_title_el.text = "중복 제목"

                mock_item.select_one = Mock(return_value=mock_title_el)

                mock_soup.select = Mock(return_value=[mock_item, mock_item])  # 동일 아이템 2개
                mock_bs.return_value = mock_soup

                seen_titles = {"중복 제목"}  # 이미 본 제목
                result = collector._fetch_naver_search_news("삼성전자", 5, seen_titles)

                # 중복 제목은 필터링되어야 함
                assert len(result) <= 1

    @pytest.mark.asyncio
    async def test_fetch_daum_search_news_respects_limit(self, collector):
        """limit 존중 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                # 10개의 아이템 생성
                mock_items = []
                for i in range(10):
                    mock_item = Mock()
                    mock_link = Mock()
                    mock_link.text = f"뉴스 {i}"
                    mock_link.get = Mock(return_value=f"https://daum.net/news/{i}")
                    mock_item.select_one = Mock(return_value=mock_link)
                    mock_items.append(mock_item)

                mock_soup = Mock()
                mock_soup.select = Mock(return_value=mock_items)
                mock_bs.return_value = mock_soup

                seen_titles = set()
                result = collector._fetch_daum_search_news("테스트종목", 3, seen_titles)

                # limit = 3이므로 최대 3개 반환
                assert len(result) <= 3


# ========================================================================
# Parametrized Tests
# ========================================================================

class TestNewsCollectorParametrized:
    """매개변수화된 테스트"""

    @pytest.fixture
    def collector(self):
        return EnhancedNewsCollector()

    @pytest.mark.parametrize("source,expected_weight", [
        ("한국경제", 0.9),
        ("매일경제", 0.9),
        ("머니투데이", 0.85),
        ("서울경제", 0.85),
        ("연합뉴스", 0.85),
        ("뉴스1", 0.8),
        ("파이낸셜뉴스", 0.8),
        ("아시아경제", 0.8),
        ("헤럴드경제", 0.8),
    ])
    def test_major_sources_weights(self, collector, source, expected_weight):
        """주요 언론사 가중치 테스트"""
        assert source in collector.MAJOR_SOURCES
        assert collector.MAJOR_SOURCES[source] == expected_weight

    @pytest.mark.parametrize("platform,expected_reliability", [
        ("finance", 0.9),
        ("search_naver", 0.85),
        ("search_daum", 0.8),
    ])
    def test_platform_reliability(self, collector, platform, expected_reliability):
        """플랫폼 신뢰도 테스트"""
        assert collector.PLATFORM_RELIABILITY[platform] == expected_reliability

    @pytest.mark.parametrize("code,expected_name", [
        ("005930", "삼성전자"),
        ("000270", "기아"),
        ("035420", "NAVER"),
        ("005380", "현대차"),
        ("015760", "한화사이언스"),
    ])
    def test_get_stock_name_mapping(self, collector, code, expected_name):
        """종목 코드별 이름 매핑 테스트"""
        assert collector._get_stock_name(code) == expected_name

    @pytest.mark.parametrize("ticker", [
        "999999",
        "000000",
        "ABCDEF",
    ])
    def test_get_stock_name_unknown_fallback(self, collector, ticker):
        """알 수 없는 종목 코드 fallback 테스트"""
        assert collector._get_stock_name(ticker) == "알 수 없는 종목"


# ========================================================================
# Edge Cases Tests
# ========================================================================

class TestNewsCollectorEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def collector(self):
        return EnhancedNewsCollector()

    @pytest.mark.asyncio
    async def test_get_stock_news_with_zero_limit(self, collector):
        """limit = 0으로 뉴스 수집 테스트"""
        with patch.object(collector, '_fetch_naver_finance_news', return_value=[]):
            with patch.object(collector, '_fetch_naver_search_news', return_value=[]):
                with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                    result = await collector.get_stock_news("005930", 0)
                    assert result == []

    @pytest.mark.asyncio
    async def test_get_stock_news_with_empty_code(self, collector):
        """빈 코드로 뉴스 수집 테스트"""
        with patch.object(collector, '_fetch_naver_finance_news', return_value=[]):
            with patch.object(collector, '_fetch_naver_search_news', return_value=[]):
                with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                    result = await collector.get_stock_news("", 5)
                    assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_stock_news_import_error(self, collector):
        """requests/BeautifulSoup ImportError 테스트"""
        with patch('builtins.__import__', side_effect=ImportError):
            result = await collector.get_stock_news("005930", 5)
            # ImportError 시 빈 리스트 반환
            assert result == []

    @pytest.mark.asyncio
    async def test_get_stock_news_general_exception(self, collector):
        """일반 예외 발생 테스트"""
        with patch.object(collector, '_fetch_naver_finance_news', side_effect=Exception("Network Error")):
            # 예외가 로그되고 계속 진행되어야 함
            with patch.object(collector, '_fetch_naver_search_news', return_value=[]):
                with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                    result = await collector.get_stock_news("005930", 5)
                    assert isinstance(result, list)

    def test_get_weight_with_empty_source(self, collector):
        """빈 소스명으로 가중치 계산 테스트"""
        weight = collector._get_weight("", platform='search_naver')
        # 기본값 사용
        assert 0.0 <= weight <= 1.0

    def test_get_weight_with_unknown_platform(self, collector):
        """알 수 없는 플랫폼으로 가중치 계산 테스트"""
        weight = collector._get_weight("한국경제", platform='unknown_platform')
        # 알 수 없는 플랫폼은 기본값 0.8 사용
        assert weight == 0.9 * 0.8  # Publisher * Default Platform


# ========================================================================
# Integration Tests
# ========================================================================

class TestNewsCollectorIntegration:
    """통합 테스트"""

    @pytest.fixture
    def collector(self):
        return EnhancedNewsCollector()

    @pytest.mark.asyncio
    async def test_full_news_collection_workflow(self, collector):
        """전체 뉴스 수집 워크플로우 테스트"""
        # 각 소스별 mock 뉴스 생성
        def create_mock_news(source_name, platform_name):
            return [
                NewsItem(
                    title=f"{source_name} 뉴스 {i}",
                    summary=f"{source_name} 요약 {i}",
                    source=source_name,
                    url=f"https://{platform_name}.com/{i}",
                    published_at=datetime.now(),
                    weight=collector._get_weight(source_name, platform_name)
                )
                for i in range(5)
            ]

        naver_finance_news = create_mock_news("한국경제", "finance")
        naver_search_news = create_mock_news("매일경제", "search_naver")
        daum_search_news = create_mock_news("연합뉴스", "search_daum")

        with patch.object(collector, '_fetch_naver_finance_news', return_value=naver_finance_news):
            with patch.object(collector, '_fetch_naver_search_news', return_value=naver_search_news):
                with patch.object(collector, '_fetch_daum_search_news', return_value=daum_search_news):
                    result = await collector.get_stock_news("005930", 10)

                    # 결과가 가중치순으로 정렬되어야 함
                    assert len(result) <= 10

                    # 가중치 검증 (한국경제 finance가 가장 높음)
                    if result:
                        assert all(isinstance(item, NewsItem) for item in result)
                        # 첫 번째 아이템의 가중치는 가장 높아야 함
                        first_weight = result[0].weight
                        for item in result[1:]:
                            assert item.weight <= first_weight

    @pytest.mark.asyncio
    async def test_news_deduplication_across_sources(self, collector):
        """소스 간 뉴스 중복 제거 테스트"""
        duplicate_news = NewsItem(
            title="중복 뉴스",
            summary="중복 요약",
            source="한국경제",
            url="https://example.com/1",
            published_at=datetime.now(),
            weight=0.9
        )

        with patch.object(collector, '_fetch_naver_finance_news', return_value=[duplicate_news]):
            with patch.object(collector, '_fetch_naver_search_news', return_value=[duplicate_news]):
                with patch.object(collector, '_fetch_daum_search_news', return_value=[]):
                    result = await collector.get_stock_news("005930", 10)

                    # 중복 제거되어야 함
                    count = sum(1 for item in result if item.title == "중복 뉴스")
                    assert count <= 1
