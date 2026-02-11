#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for Naver Finance Collector Module

naver.py 모듈의 NaverFinanceCollector 클래스를 테스트합니다.

Created: 2026-02-11
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from engine.collectors.naver import NaverFinanceCollector


class TestNaverFinanceCollector:
    """NaverFinanceCollector 클래스 테스트"""

    @pytest.fixture
    def collector(self):
        """테스트용 NaverFinanceCollector 인스턴스"""
        return NaverFinanceCollector(config=None)

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, collector):
        """초기화 테스트"""
        assert collector is not None
        assert collector.config is None
        assert hasattr(collector, 'headers')
        assert 'User-Agent' in collector.headers
        assert collector.headers.get('Referer') == 'https://finance.naver.com/'

    # ========================================================================
    # get_top_gainers Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_top_gainers_not_implemented(self, collector):
        """get_top_gainers는 지원하지 않음 테스트"""
        with pytest.raises(NotImplementedError, match="does not support get_top_gainers"):
            await collector.get_top_gainers("KOSPI", 10)

    # ========================================================================
    # get_stock_detail_info Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_stock_detail_info_success(self, collector):
        """성공적인 종목 상세 정보 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()

        # HTML 응답 mock
        mock_response.text = """
        <html>
            <div class="wrap_company">
                <h2><a>삼성전자</a></h2>
            </div>
            <img class="kospi" alt="KOSPI">
            <p class="no_today">
                <span class="blind">80000</span>
            </p>
            <td class="first">
                <span class="blind">79500</span>
            </td>
            <table class="no_info">
                <td><span class="blind">80500</span></td>
                <td><span class="blind">79000</span></td>
            </table>
            <table class="tab_con1">
                <tr>
                    <th>52주 최고</th>
                    <td><span class="blind">90000</span></td>
                </tr>
                <tr>
                    <th>52주 최저</th>
                    <td><span class="blind">70000</span></td>
                </tr>
            </table>
            <span id="_per">15.5</span>
            <span id="_pbr">1.2</span>
            <span id="_market_sum">250조원</span>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = MagicMock()
                mock_soup.select_one = Mock(side_effect=self._mock_select_one_detail)
                mock_soup.select = Mock(return_value=[])
                mock_bs.return_value = mock_soup

                with patch.object(collector, '_get_investor_trend'):
                    with patch.object(collector, '_get_fundamental_data'):
                        result = await collector.get_stock_detail_info("005930")

                        assert result is not None
                        assert result['code'] == "005930"
                        assert 'name' in result
                        assert 'market' in result
                        assert 'priceInfo' in result
                        assert 'yearRange' in result
                        assert 'indicators' in result

    @pytest.mark.asyncio
    async def test_get_stock_detail_info_import_error(self, collector):
        """ImportError 시 종목 상세 정보 수집 테스트"""
        with patch('builtins.__import__', side_effect=ImportError):
            result = await collector.get_stock_detail_info("005930")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_stock_detail_info_http_error(self, collector):
        """HTTP 오류 시 종목 상세 정보 수집 테스트"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=Exception("HTTP Error"))

        with patch('requests.get', return_value=mock_response):
            result = await collector.get_stock_detail_info("005930")
            assert result is None

    # ========================================================================
    # get_financials Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_financials_success(self, collector):
        """성공적인 재무 정보 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        mock_response.text = """
        <html>
            <table class="gHead01">
                <tr>
                    <th>매출액</th>
                    <td>100,000</td>
                </tr>
                <tr>
                    <th>영업이익</th>
                    <td>10,000</td>
                </tr>
                <tr>
                    <th>당기순이익</th>
                    <td>5,000</td>
                </tr>
            </table>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_table = Mock()

                def create_row(label, value):
                    mock_row = Mock()
                    mock_th = Mock()
                    mock_th.text = label
                    mock_tds = [Mock()]
                    mock_tds[0].text = value
                    type(mock_row).select_one = Mock(side_effect=lambda x, th=mock_th, tds=mock_tds: (
                        mock_th if x == 'th' else mock_tds
                    ).get(x, mock_tds[0] if x == 'td' else None))
                    return mock_row

                mock_table.select = Mock(return_value=[
                    create_row("매출액", "10,000"),
                    create_row("영업이익", "5,000"),
                    create_row("당기순이익", "2,500"),
                ])
                mock_soup.select = Mock(return_value=[mock_table])
                mock_bs.return_value = mock_soup

                result = await collector.get_financials("005930")

                assert result is not None
                assert 'revenue' in result
                assert 'operatingProfit' in result
                assert 'netIncome' in result

    @pytest.mark.asyncio
    async def test_get_financials_exception(self, collector):
        """예외 발생 시 재무 정보 수집 테스트"""
        with patch('requests.get', side_effect=Exception("Network Error")):
            result = await collector.get_financials("005930")
            # 예외 발생 시 기본값 반환
            assert result is not None
            assert result['revenue'] == 0
            assert result['operatingProfit'] == 0
            assert result['netIncome'] == 0

    # ========================================================================
    # get_themes Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_themes_success(self, collector):
        """성공적인 테마 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        mock_response.text = """
        <html>
            <div class="sub_section">
                <th><em><a>반도체</a></em></th>
                <td><a>AI</a></td>
            </div>
            <div class="section trade_compare">
                <em><a>전자부품</a></em>
            </div>
            <div class="wrap_company">
                <a>KOSPI</a>
                <a>첨단소재</a>
            </div>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()

                # Mock select calls
                def mock_select(selector):
                    if 'th em a' in selector or 'td a' in selector:
                        mock_links = []
                        for text in ['반도체', 'AI']:
                            mock_a = Mock()
                            mock_a.text = text.strip()
                            mock_links.append(mock_a)
                        return mock_links
                    elif 'em a' in selector:
                        mock_a = Mock()
                        mock_a.text = "전자부품"
                        return [mock_a]
                    elif 'a' in selector:
                        mock_links = []
                        for text in ['KOSPI', '첨단소재']:
                            mock_a = Mock()
                            mock_a.text = text.strip()
                            mock_links.append(mock_a)
                        return mock_links
                    return []

                mock_soup.select = mock_select
                mock_bs.return_value = mock_soup

                result = await collector.get_themes("005930")

                assert isinstance(result, list)
                # KOSPI 필터링됨
                assert 'KOSPI' not in result

    @pytest.mark.asyncio
    async def test_get_themes_limit_to_5(self, collector):
        """테마 최대 5개 제한 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        # 10개의 테마 생성
        themes_text = " ".join([f"<a>테마{i}</a>" for i in range(10)])
        mock_response.text = f"<html><div class='sub_section'>{themes_text}</div></html>"

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()

                mock_links = []
                for i in range(10):
                    mock_a = Mock()
                    mock_a.text = f"테마{i}"
                    mock_links.append(mock_a)

                mock_soup.select = Mock(return_value=mock_links)
                mock_bs.return_value = mock_soup

                result = await collector.get_themes("005930")

                # 최대 5개로 제한
                assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_get_themes_filters_excluded(self, collector):
        """제외할 테마 필터링 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        excluded_themes = ['더보기', '차트', '뉴스', '게시판', '종합정보']
        themes_text = " ".join([f"<a>{theme}</a>" for theme in excluded_themes])
        mock_response.text = f"<html><div class='sub_section'>{themes_text}</div></html>"

        with patch('requests.get', return_value=mock_response):
            # Use actual BeautifulSoup instead of mocking
            result = await collector.get_themes("005930")

            # 제외된 테마는 없어야 함
            for theme in excluded_themes:
                assert theme not in result

    # ========================================================================
    # Helper Methods Tests
    # ========================================================================

    def test_create_empty_result_dict(self, collector):
        """빈 결과 딕셔너리 생성 테스트"""
        result = collector._create_empty_result_dict("005930")

        assert result['code'] == "005930"
        assert result['market'] == 'UNKNOWN'
        assert result['name'] == ''
        assert 'priceInfo' in result
        assert 'yearRange' in result
        assert 'indicators' in result
        assert 'investorTrend' in result
        assert 'safety' in result

        # 중첩 구조 검증
        assert 'current' in result['priceInfo']
        assert 'high_52w' in result['yearRange']
        assert 'per' in result['indicators']
        assert 'foreign' in result['investorTrend']
        assert 'debtRatio' in result['safety']

    # ========================================================================
    # Mock Helper
    # ========================================================================

    def _mock_select_one_detail(self, selector):
        """select_one 메서드 mock 헬퍼"""
        mock_map = {
            'div.wrap_company h2 a': self._create_mock_element(text="삼성전자"),
            'img.kospi': self._create_mock_element(alt="KOSPI"),
            'img.kosdaq, img[alt*="코스피"], img[alt*="코스닥"]': self._create_mock_element(alt="KOSPI"),
            'p.no_today span.blind': self._create_mock_element(text="80000"),
            'td.first span.blind': self._create_mock_element(text="79500"),
            'table.no_info td span.blind': self._create_mock_element(text="80500"),
            '#_per': self._create_mock_element(text="15.5"),
            '#_pbr': self._create_mock_element(text="1.2"),
            '#_market_sum': self._create_mock_element(text="250"),
        }
        return mock_map.get(selector)

    def _create_mock_element(self, text=None, alt=None):
        """Mock 엘리먼트 생성 헬퍼"""
        mock_el = Mock()
        if text:
            mock_el.text = text
        if alt:
            mock_el.get = Mock(return_value=alt)
        return mock_el


# ========================================================================
# Parametrized Tests
# ========================================================================

class TestNaverFinanceCollectorParametrized:
    """매개변수화된 테스트"""

    @pytest.fixture
    def collector(self):
        return NaverFinanceCollector()

    @pytest.mark.parametrize("code,expected_initial_values", [
        ("005930", {
            'code': "005930",
            'market': 'UNKNOWN',
            'name': '',
        }),
        ("000270", {
            'code': "000270",
            'market': 'UNKNOWN',
            'name': '',
        }),
    ])
    @pytest.mark.asyncio
    async def test_get_stock_detail_info_initial_values(
        self, collector, code, expected_initial_values
    ):
        """종목 상세 정보 초기값 테스트"""
        result = collector._create_empty_result_dict(code)

        for key, value in expected_initial_values.items():
            assert result[key] == value

    @pytest.mark.asyncio
    async def test_get_financials_various_error_scenarios(self, collector):
        """다양한 에러 시나리오에서 재무 정보 수집 테스트"""
        error_scenarios = [
            ImportError("requests missing"),
            Exception("Timeout"),
            ValueError("Parse error"),
        ]

        for error in error_scenarios:
            with patch('requests.get', side_effect=error):
                result = await collector.get_financials("005930")
                # 모든 에러 시나리오에서 기본값 반환
                assert result['revenue'] == 0
                assert result['operatingProfit'] == 0
                assert result['netIncome'] == 0


# ========================================================================
# Edge Cases Tests
# ========================================================================

class TestNaverFinanceCollectorEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.fixture
    def collector(self):
        return NaverFinanceCollector()

    @pytest.mark.asyncio
    async def test_get_stock_detail_info_with_empty_response(self, collector):
        """빈 응답으로 종목 상세 정보 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.text = ""

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_soup.select_one = Mock(return_value=None)
                mock_soup.select = Mock(return_value=[])
                mock_bs.return_value = mock_soup

                with patch.object(collector, '_get_investor_trend'):
                    with patch.object(collector, '_get_fundamental_data'):
                        result = await collector.get_stock_detail_info("005930")

                        # 빈 응답이어도 구조는 반환되어야 함
                        assert result is not None
                        assert result['code'] == "005930"

    @pytest.mark.asyncio
    async def test_get_themes_with_empty_html(self, collector):
        """빈 HTML로 테마 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.text = "<html></html>"

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_soup.select = Mock(return_value=[])
                mock_bs.return_value = mock_soup

                result = await collector.get_themes("005930")

                # 빈 HTML이어도 빈 리스트 반환
                assert result == []

    @pytest.mark.asyncio
    async def test_get_themes_with_http_error(self, collector):
        """HTTP 오류 시 테마 수집 테스트"""
        with patch('requests.get', side_effect=Exception("HTTP Error")):
            result = await collector.get_themes("005930")
            # HTTP 오류 시 빈 리스트 반환
            assert result == []

    @pytest.mark.asyncio
    async def test_get_financials_with_invalid_number_format(self, collector):
        """무효한 숫자 형식으로 재무 정보 수집 테스트"""
        mock_response = Mock()
        mock_response.ok = True

        mock_response.text = """
        <html>
            <table class="gHead01">
                <tr>
                    <th>매출액</th>
                    <td>invalid_number</td>
                </tr>
            </table>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = Mock()
                mock_table = Mock()

                mock_row = Mock()
                mock_th = Mock()
                mock_th.text = "매출액"
                mock_tds = [Mock()]
                mock_tds[0].text = "invalid_number"

                type(mock_row).select_one = Mock(return_value=mock_th)
                mock_row.select = Mock(return_value=mock_tds)
                mock_table.select = Mock(return_value=[mock_row])
                mock_soup.select = Mock(return_value=[mock_table])
                mock_bs.return_value = mock_soup

                result = await collector.get_financials("005930")

                # 파싱 실패 시 기본값 유지
                assert result['revenue'] == 0


# ========================================================================
# Integration Tests
# ========================================================================

class TestNaverFinanceCollectorIntegration:
    """통합 테스트"""

    @pytest.fixture
    def collector(self):
        return NaverFinanceCollector()

    @pytest.mark.asyncio
    async def test_full_detail_collection_workflow(self, collector):
        """전체 상세 정보 수집 워크플로우 테스트"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.raise_for_status = Mock()

        mock_response.text = """
        <html>
            <div class="wrap_company"><h2><a>테스트종목</a></h2></div>
            <img class="kospi" alt="KOSPI">
            <p class="no_today"><span class="blind">50000</span></p>
        </html>
        """

        with patch('requests.get', return_value=mock_response):
            with patch('bs4.BeautifulSoup') as mock_bs:
                mock_soup = MagicMock()
                mock_soup.select_one = Mock(side_effect=self._integration_mock_select)
                mock_soup.select = Mock(return_value=[])
                mock_bs.return_value = mock_soup

                with patch.object(collector, '_get_investor_trend'):
                    with patch.object(collector, '_get_fundamental_data'):
                        result = await collector.get_stock_detail_info("999999")

                        # 모든 필드가 채워져야 함
                        assert result['code'] == "999999"
                        assert result['name'] == "테스트종목"
                        assert result['market'] in ['KOSPI', 'KOSDAQ', 'UNKNOWN']

    def _integration_mock_select(self, selector):
        """통합 테스트용 select mock"""
        mock_map = {
            'div.wrap_company h2 a': self._create_mock_el(text="테스트종목"),
            'img.kospi': self._create_mock_el(alt="KOSPI"),
            'p.no_today span.blind': self._create_mock_el(text="50000"),
        }
        return mock_map.get(selector)

    def _create_mock_el(self, text=None, alt=None):
        """Mock 엘리먼트 생성"""
        mock_el = Mock()
        if text:
            mock_el.text = text
        if alt:
            mock_el.get = Mock(return_value=alt)
        return mock_el
