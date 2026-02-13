#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver Finance Collector Module

네이버 금융에서 종목 상세 정보(투자 지표, 재무 정보, 52주 범위 등)를 수집합니다.

Created: 2026-02-11
Refactored from: engine/collectors.py (NaverFinanceCollector class)
"""
import logging
import re
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from engine.collectors.base import BaseCollector, CollectorError

logger = logging.getLogger(__name__)


class NaverFinanceCollector(BaseCollector):
    """
    네이버 금융 상세 정보 수집기

    네이버 금융 웹사이트에서 종목 상세 정보를 수집합니다:
    - 시세 정보 (현재가, 전일가, 시가, 고가, 저가)
    - 52주 최고/최저가
    - 투자 지표 (PER, PBR, ROE 등)
    - 시가총액
    - 투자자 동향
    """

    def __init__(self, config=None):
        """
        Args:
            config: 설정 객체
        """
        super().__init__(config)
        self.headers = self._build_default_headers(
            referer='https://finance.naver.com/'
        )

    # ========================================================================
    # Abstract Method Implementation (not applicable)
    # ========================================================================

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List:
        """NaverFinanceCollector는 상승률 조회를 지원하지 않음"""
        raise NotImplementedError("NaverFinanceCollector does not support get_top_gainers")

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def get_stock_detail_info(self, code: str) -> Optional[Dict]:
        """
        네이버 금융에서 종목 상세 정보 수집

        수집 항목:
        - 시세 정보: 현재가, 전일가, 시가, 고가, 저가
        - 52주 최고/최저가
        - 투자 지표: PER, PBR, ROE 등
        - 시가총액

        Args:
            code: 종목 코드

        Returns:
            상세 정보 딕셔너리 또는 None
        """
        try:
            # import requests  <-- Removed, handled in _request
            from bs4 import BeautifulSoup

            result = self._create_empty_result_dict(code)
            result['code'] = code

            url = f'https://finance.naver.com/item/main.naver?code={code}'
            # response = requests.get(url, headers=self.headers, timeout=10)
            response = self._request(url, headers=self.headers)
            
            if not response or not response.ok:
                logger.warning(f"상세 정보 요청 실패: {code}")
                return None
                
            # response.raise_for_status() <--- _request handles logic, returns Response or None

            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. 종목명 추출
            self._extract_stock_name(soup, result)

            # 2. 시장 구분 (KOSPI/KOSDAQ)
            self._extract_market_info(soup, result)

            # 3. 현재가
            self._extract_current_price(soup, result)

            # 4. 전일가
            self._extract_prev_close(soup, result)

            # 5. 시가, 고가, 저가, 거래량
            self._extract_ohlcv(soup, result)

            # 6. 52주 최고/최저가
            self._extract_52week_range(soup, result)

            # 7. 투자 지표 (PER, PBR)
            self._extract_indicators(soup, result)

            # 8. 시가총액
            self._extract_market_cap(soup, result)

            # 9. pykrx에서 투자자 동향 가져오기
            await self._get_investor_trend(code, result)

            # 10. pykrx에서 기본적인 펀더멘탈 데이터 가져오기
            await self._get_fundamental_data(code, result)

            logger.info(f"상세 정보 수집 완료: {result.get('name', code)} ({code})")
            return result

        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return None
        except Exception as e:
            logger.error(f"상세 정보 수집 실패 ({code}): {e}")
            return None

    async def get_financials(self, code: str) -> Dict:
        """
        재무 정보 수집 (네이버 금융 기업분석)

        Args:
            code: 종목 코드

        Returns:
            재무 정보 딕셔너리
        """
        try:
            # import requests <-- Removed
            from bs4 import BeautifulSoup

            result = {
                'revenue': 0,
                'operatingProfit': 0,
                'netIncome': 0,
            }

            # 네이버 기업분석 페이지
            url = f'https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}'
            # response = requests.get(url, headers=self.headers, timeout=10)
            response = self._request(url, headers=self.headers)

            if response and response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.select('table.gHead01')

                for table in tables:
                    rows = table.select('tr')
                    for row in rows:
                        th = row.select_one('th')
                        tds = row.select('td')

                        if th and tds:
                            label = th.text.strip()

                            if '매출액' in label and tds:
                                try:
                                    result['revenue'] = float(tds[0].text.replace(',', '').strip()) * 100_000_000
                                except:
                                    pass
                            elif '영업이익' in label and tds:
                                try:
                                    result['operatingProfit'] = float(tds[0].text.replace(',', '').strip()) * 100_000_000
                                except:
                                    pass
                            elif ('순이익' in label or '당기순이익' in label) and tds:
                                try:
                                    result['netIncome'] = float(tds[0].text.replace(',', '').strip()) * 100_000_000
                                except:
                                    pass

            return result

        except Exception as e:
            logger.debug(f"재무정보 수집 실패 ({code}): {e}")
            return {'revenue': 0, 'operatingProfit': 0, 'netIncome': 0}

    async def get_themes(self, code: str) -> List[str]:
        """
        네이버 금융에서 종목 관련 테마 태그 수집
        
        예: 원전, SMR, 전력인프라, 반도체 등
        
        Args:
            code: 종목 코드
            
        Returns:
            테마 리스트 (최대 5개)
        """
        try:
            from bs4 import BeautifulSoup
            
            themes = []
            
            # 네이버 금융 종목 메인 페이지에서 테마 태그 추출
            url = f'https://finance.naver.com/item/main.naver?code={code}'
            response = self._request(url, headers=self.headers)
            
            if response and response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 1. 업종/테마 정보 추출
                theme_links = soup.select('div.sub_section th em a, div.sub_section td a')
                for link in theme_links:
                    theme_text = link.text.strip()
                    if theme_text and 2 <= len(theme_text) <= 20:
                        if theme_text not in ['더보기', '차트', '뉴스', '게시판', '종합정보']:
                            themes.append(theme_text)
                            
                # 2. 업종 정보 추출
                sector_el = soup.select_one('div.section.trade_compare em a')
                if sector_el:
                    sector = sector_el.text.strip()
                    if sector and sector not in themes:
                        themes.append(sector)
                        
                # 3. 분류 정보
                category_links = soup.select('div.wrap_company a')
                for link in category_links:
                    text = link.text.strip()
                    if text and text not in ['KOSPI', 'KOSDAQ', '', ' '] and len(text) <= 15:
                        if text not in themes:
                            themes.append(text)
                            
            # 중복 제거 및 최대 5개로 제한
            unique_themes = list(dict.fromkeys(themes))[:5]
            
            if unique_themes:
                logger.info(f"테마 수집 완료: {code} -> {unique_themes}")
                
            return unique_themes
            
        except Exception as e:
            logger.debug(f"테마 수집 실패 ({code}): {e}")
            return []

    def _request(self, url: str, headers: Dict = None, timeout: int = 10, retries: int = 3):
        """
        HTTP 요청 헬퍼 (재시도 로직 포함)
        
        Args:
            url: 요청 URL
            headers: 헤더
            timeout: 타임아웃 (초)
            retries: 재시도 횟수
            
        Returns:
            Response 객체 또는 None
        """
        import requests
        import time
        
        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                
                # 429 Too Many Requests 처리
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                    logger.warning(f"Naver API Rate Limit (429). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
                # 5xx Server Error 처리
                if 500 <= response.status_code < 600:
                    wait_time = (2 ** attempt) * 0.5
                    logger.warning(f"Naver Server Error ({response.status_code}). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                return response
                
            except requests.RequestException as e:
                # Connection Error 등
                if attempt < retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    logger.debug(f"Request failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {retries} attempts: {url}")
                    return None
                    
        return None

    # ========================================================================
    # Private Methods - Extractors
    # ========================================================================

    def _create_empty_result_dict(self, code: str) -> Dict:
        """빈 결과 딕셔너리 생성"""
        return {
            'code': code,
            'market': 'UNKNOWN',
            'name': '',
            'priceInfo': {
                'current': 0,
                'prevClose': 0,
                'open': 0,
                'high': 0,
                'low': 0,
                'change': 0,
                'change_pct': 0,
                'volume': 0,
                'trading_value': 0,
            },
            'yearRange': {
                'high_52w': 0,
                'low_52w': 0,
            },
            'indicators': {
                'marketCap': 0,
                'per': 0,
                'pbr': 0,
                'eps': 0,
                'bps': 0,
                'dividendYield': 0,
            },
            'investorTrend': {
                'foreign': 0,
                'institution': 0,
                'individual': 0,
            },
            'safety': {
                'debtRatio': 0,
                'currentRatio': 0,
            }
        }

    def _extract_stock_name(self, soup, result: Dict) -> None:
        """종목명 추출"""
        name_el = soup.select_one('div.wrap_company h2 a')
        if name_el:
            result['name'] = name_el.text.strip()

    def _extract_market_info(self, soup, result: Dict) -> None:
        """시장 구분 추출 (KOSPI/KOSDAQ)"""
        market_img = soup.select_one('img.kospi, img.kosdaq, img[alt*="코스피"], img[alt*="코스닥"]')
        if market_img:
            alt = market_img.get('alt', '').upper()
            if 'KOSDAQ' in alt or '코스닥' in alt:
                result['market'] = 'KOSDAQ'
            else:
                result['market'] = 'KOSPI'

    def _extract_current_price(self, soup, result: Dict) -> None:
        """현재가 추출"""
        current_price_el = soup.select_one('p.no_today span.blind')
        if current_price_el:
            try:
                result['priceInfo']['current'] = int(current_price_el.text.replace(',', ''))
            except:
                pass

    def _extract_prev_close(self, soup, result: Dict) -> None:
        """전일가 추출"""
        prev_close_el = soup.select_one('td.first span.blind')
        if prev_close_el:
            try:
                result['priceInfo']['prevClose'] = int(prev_close_el.text.replace(',', ''))
            except:
                pass

    def _extract_ohlcv(self, soup, result: Dict) -> None:
        """시가, 고가, 저가, 거래량 추출"""
        no_info_table = soup.select('table.no_info td span.blind')
        if len(no_info_table) >= 4:
            try:
                result['priceInfo']['high'] = int(no_info_table[1].text.replace(',', '')) if no_info_table[1] else 0
                result['priceInfo']['low'] = int(no_info_table[3].text.replace(',', '')) if no_info_table[3] else 0
            except:
                pass

    def _extract_52week_range(self, soup, result: Dict) -> None:
        """52주 최고/최저가 추출"""
        aside_info = soup.select('table.tab_con1 tr')
        for tr in aside_info:
            th = tr.select_one('th')
            td = tr.select_one('td')
            if th and td:
                label = th.text.strip()
                value_el = td.select_one('span.blind')
                if value_el:
                    try:
                        value = int(value_el.text.replace(',', ''))
                        if '52주' in label and '최고' in label:
                            result['yearRange']['high_52w'] = value
                        elif '52주' in label and '최저' in label:
                            result['yearRange']['low_52w'] = value
                    except:
                        pass

    def _extract_indicators(self, soup, result: Dict) -> None:
        """투자 지표 추출 (PER, PBR 등)"""
        per_el = soup.select_one('#_per')
        pbr_el = soup.select_one('#_pbr')

        if per_el:
            try:
                result['indicators']['per'] = float(per_el.text.replace(',', ''))
            except:
                pass
        if pbr_el:
            try:
                result['indicators']['pbr'] = float(pbr_el.text.replace(',', ''))
            except:
                pass

    def _extract_market_cap(self, soup, result: Dict) -> None:
        """시가총액 추출"""
        market_cap_el = soup.select_one('#_market_sum')
        if market_cap_el:
            try:
                # "2,142,543억원" 형태
                cap_text = market_cap_el.text.replace(',', '').replace('억원', '').replace('조', '').strip()
                result['indicators']['marketCap'] = int(float(cap_text) * 100_000_000)  # 억원 -> 원
            except:
                pass

    async def _get_investor_trend(self, code: str, result: Dict) -> None:
        """pykrx를 통해 투자자 동향 수집"""
        try:
            from pykrx import stock

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

            df = stock.get_market_trading_value_by_date(start_date, end_date, code)
            if not df.empty:
                # 최근 5일 합계
                df = df.tail(5)

                foreign_col = '외국인합계' if '외국인합계' in df.columns else '외국인'
                inst_col = '기관합계' if '기관합계' in df.columns else '기관'
                retail_col = '개인' if '개인' in df.columns else None

                if foreign_col in df.columns:
                    result['investorTrend']['foreign'] = int(df[foreign_col].sum())
                if inst_col in df.columns:
                    result['investorTrend']['institution'] = int(df[inst_col].sum())
                if retail_col and retail_col in df.columns:
                    result['investorTrend']['individual'] = int(df[retail_col].sum())
        except Exception as e:
            logger.debug(f"투자자 동향 pykrx 조회 실패: {e}")

    async def _get_fundamental_data(self, code: str, result: Dict) -> None:
        """pykrx를 통해 펀더멘탈 데이터 수집"""
        try:
            from pykrx import stock

            today = datetime.now().strftime('%Y%m%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

            # 최근 영업일의 펀더멘탈 데이터
            for target_date in [today, yesterday]:
                try:
                    df = stock.get_market_fundamental_by_ticker(target_date)
                    if not df.empty and code in df.index:
                        row = df.loc[code]
                        if 'PER' in row:
                            result['indicators']['per'] = float(row['PER']) if result['indicators']['per'] == 0 else result['indicators']['per']
                        if 'PBR' in row:
                            result['indicators']['pbr'] = float(row['PBR']) if result['indicators']['pbr'] == 0 else result['indicators']['pbr']
                        if 'EPS' in row:
                            result['indicators']['eps'] = float(row['EPS'])
                        if 'BPS' in row:
                            result['indicators']['bps'] = float(row['BPS'])
                        if 'DIV' in row:
                            result['indicators']['dividendYield'] = float(row['DIV'])
                        break
                except:
                    continue
        except Exception as e:
            logger.debug(f"펀더멘탈 pykrx 조회 실패: {e}")
