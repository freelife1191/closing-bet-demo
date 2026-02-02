#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Toss Securities Collector (토스증권 데이터 수집기)
"""
import logging
import requests
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TossCollector:
    """토스증권 API를 통한 주식 상세 정보 수집기"""
    
    BASE_URL = "https://wts-info-api.tossinvest.com/api"
    
    def __init__(self, config=None):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://tossinvest.com/',
            'Origin': 'https://tossinvest.com'
        })
    
    def _format_code(self, code: str) -> str:
        """종목코드를 토스증권 형식으로 변환 (010120 -> A010120)"""
        if not code.startswith('A'):
            return f"A{code}"
        return code
    
    def _safe_request(self, url: str, method: str = 'GET', json_data: dict = None) -> Optional[Dict]:
        """안전한 API 요청"""
        try:
            if method.upper() == 'POST':
                response = self.session.post(url, json=json_data or {}, timeout=10)
            else:
                response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"FAILED: {url} [{response.status_code}]")  # DEBUG PRINT
                logger.warning(f"토스증권 API 요청 실패: {url} - {response.status_code}")
                return None
        except Exception as e:
            print(f"ERROR: {url} [{e}]") # DEBUG PRINT
            logger.error(f"토스증권 API 오류: {url} - {e}")
            return None
    
    def get_stock_info(self, code: str) -> Optional[Dict]:
        """기본 종목 정보 (마켓, 상장일 등)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v2/stock-infos/{toss_code}"
        data = self._safe_request(url)
        
        if not data:
            return None
        
        # result 래퍼 처리
        result = data.get('result', data)
        market_info = result.get('market', {})
        
        return {
            'code': code,
            'name': result.get('name', ''),
            'market': market_info.get('displayName', 'UNKNOWN'),  # 코스피, 코스닥
            'market_code': market_info.get('code', ''),  # KSP, KSQ
            'sector': result.get('sector', ''),
            'logo_url': result.get('logoImageUrl', ''),
        }
    
    def get_price_details(self, code: str) -> Optional[Dict]:
        """가격 상세 정보 (현재가, 1일/52주 범위)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v3/stock-prices/details?productCodes={toss_code}"
        data = self._safe_request(url)
        
        if not data:
            return None
        
        # result 래퍼 처리
        # v3 API는 단일 조회 시 개체, 다건 조회 시 리스트 반환 가능성 있음
        result_obj = data.get('result', data)
        price_data = {}
        
        if isinstance(result_obj, list):
            if len(result_obj) > 0:
                price_data = result_obj[0]
            else:
                return None
        elif isinstance(result_obj, dict):
            price_data = result_obj
        else:
            return None
        
        return {
            'current': price_data.get('close', 0),
            'prev_close': price_data.get('base', 0),
            'open': price_data.get('open', 0),
            'high': price_data.get('high', 0),
            'low': price_data.get('low', 0),
            'volume': price_data.get('volume', 0),
            'trading_value': price_data.get('value', 0),
            'high_52w': price_data.get('high52w', 0),
            'low_52w': price_data.get('low52w', 0),
            'market_cap': price_data.get('marketCap', 0),
            'upper_limit': price_data.get('upperLimit', 0),
            'lower_limit': price_data.get('lowerLimit', 0),
        }
    
    def get_investment_indicators(self, code: str) -> Optional[Dict]:
        """투자 지표 (PER, PBR, ROE, PSR, 배당수익률, 시가총액)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v1/stock-detail/ui/wts/{toss_code}/investment-indicators"
        data = self._safe_request(url)
        
        if not data:
            return None
        
        # result 래퍼 처리
        result = data.get('result', data)
        sections = result.get('indicatorSections', [])
        
        indicators = {
            'per': 0,
            'pbr': 0,
            'psr': 0,
            'roe': 0,
            'eps': 0,
            'bps': 0,
            'dividend_yield': 0,
        }
        
        for section in sections:
            section_data = section.get('data', {})
            section_name = section.get('sectionName', '')
            
            if section_name == '가치평가':
                # PER, PBR, PSR - "62.9배" -> 62.9
                per_str = section_data.get('displayPer', '0')
                pbr_str = section_data.get('displayPbr', '0')
                psr_str = section_data.get('displayPsr', '0')
                
                try:
                    indicators['per'] = float(per_str.replace('배', '').strip()) if per_str else 0
                except: indicators['per'] = 0
                try:
                    indicators['pbr'] = float(pbr_str.replace('배', '').strip()) if pbr_str else 0
                except: indicators['pbr'] = 0
                try:
                    indicators['psr'] = float(psr_str.replace('배', '').strip()) if psr_str else 0
                except: indicators['psr'] = 0
                
            elif section_name == '수익':
                indicators['eps'] = section_data.get('epsKrw', 0)
                indicators['bps'] = section_data.get('bpsKrw', 0)
                # ROE - "14.0%" -> 14.0
                roe_str = section_data.get('roe', '0')
                try:
                    indicators['roe'] = float(roe_str.replace('%', '').strip()) if roe_str else 0
                except: indicators['roe'] = 0
                
            elif section_name == '배당':
                indicators['dividend_yield'] = section_data.get('dividendYieldRatio', 0) * 100  # 0.0051 -> 0.51%
        
        return indicators
    
    def get_investor_trend(self, code: str, days: int = 5) -> Optional[Dict]:
        """투자자 동향 (개인, 외국인, 기관)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v1/stock-infos/trade/trend/trading-trend?productCode={toss_code}&size={days}"
        data = self._safe_request(url)
        
        if not data:
            return None
            
        result = data.get('result', {})
        # v1 API 구조: result -> body 리스트
        trends = result.get('body', [])
        if not trends:
             # 혹시 모를 구버전 호환
             trends = data.get('trends', [])
        
        # 합계 계산
        foreign_sum = sum(t.get('netForeignerBuyVolume', 0) for t in trends)
        institution_sum = sum(t.get('netInstitutionBuyVolume', 0) for t in trends)
        individual_sum = sum(t.get('netIndividualsBuyVolume', 0) for t in trends)
        
        return {
            'foreign': foreign_sum,
            'institution': institution_sum,
            'individual': individual_sum,
            'days': days,
        }
    
    def get_financials(self, code: str) -> Optional[Dict]:
        """재무 정보 (매출, 영업이익, 순이익)"""
        toss_code = self._format_code(code)
        
        # 매출/순이익 (POST)
        revenue_url = f"{self.BASE_URL}/v2/stock-infos/revenue-and-net-profit/{toss_code}"
        revenue_data = self._safe_request(revenue_url, method='POST', json_data={})
        
        # 영업이익 (POST)
        operating_url = f"{self.BASE_URL}/v2/stock-infos/operating-income/{toss_code}"
        operating_data = self._safe_request(operating_url, method='POST', json_data={})
        
        result = {
            'revenue': 0,
            'operating_profit': 0,
            'net_income': 0,
            'revenue_quarterly': [],
            'operating_quarterly': [],
            'net_income_quarterly': [],
        }
        
        if revenue_data:
            result_data = revenue_data.get('result', {})
            # table 리스트 (분기별 데이터)
            table = result_data.get('table', [])
            
            # 최신 데이터 (리스트의 마지막이 최신)
            if table:
                latest = table[-1]
                result['revenue'] = latest.get('revenueKrw', 0)
                result['net_income'] = latest.get('netProfitKrw', 0)
                
                # 분기 데이터 매핑 (Display용)
                # 최근 4개 분기
                result['revenue_quarterly'] = [
                    {'period': q.get('period'), 'value': q.get('revenueKrw', 0)}
                    for q in table[-4:]
                ]
                result['net_income_quarterly'] = [
                    {'period': q.get('period'), 'value': q.get('netProfitKrw', 0)}
                    for q in table[-4:]
                ]
        
        if operating_data:
            result_data = operating_data.get('result', {})
            table = result_data.get('table', [])
            
            if table:
                latest = table[-1]
                result['operating_profit'] = latest.get('operatingIncomeKrw', 0)
                
                result['operating_quarterly'] = [
                    {'period': q.get('period'), 'value': q.get('operatingIncomeKrw', 0)}
                    for q in table[-4:]
                ]
        
        return result
    
    def get_stability(self, code: str) -> Optional[Dict]:
        """안정성 지표 (부채비율, 유동비율, 이자보상비율)"""
        toss_code = self._format_code(code)
        url = f"{self.BASE_URL}/v2/stock-infos/stability/{toss_code}"
        data = self._safe_request(url, method='POST', json_data={})
        
        if not data:
            return None
            
        result = data.get('result', data)
        
        return {
            'debt_ratio': result.get('liabilityRatio', 0),  # debtRatio -> liabilityRatio
            'current_ratio': result.get('currentRatio', 0),
            'interest_coverage': result.get('interestCoverageRatio', 0),
        }
    
    def get_full_stock_detail(self, code: str) -> Dict:
        """
        종목의 모든 상세 정보를 한번에 수집
        
        Returns:
            {
                'code': str,
                'name': str,
                'market': str,
                'price': {...},
                'indicators': {...},
                'investor_trend': {...},
                'financials': {...},
                'stability': {...},
            }
        """
        result = {
            'code': code,
            'name': '',
            'market': 'UNKNOWN',
            'fetched_at': datetime.now().isoformat(),
        }
        
        # 기본 정보
        info = self.get_stock_info(code)
        if info:
            result['name'] = info.get('name', '')
            result['market'] = info.get('market', 'UNKNOWN')
            result['sector'] = info.get('sector', '')
        
        # 가격 정보
        result['price'] = self.get_price_details(code) or {}
        
        # 투자 지표
        result['indicators'] = self.get_investment_indicators(code) or {}
        
        # 투자자 동향
        result['investor_trend'] = self.get_investor_trend(code) or {}
        
        # 재무 정보
        result['financials'] = self.get_financials(code) or {}
        
        # 안정성 지표
        result['stability'] = self.get_stability(code) or {}
        
        return result


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    collector = TossCollector()
    
    # 한미반도체 테스트 (042700)
    print("=== 한미반도체 (A042700) 진단 시작 ===")
    result = collector.get_full_stock_detail("042700")
    
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
