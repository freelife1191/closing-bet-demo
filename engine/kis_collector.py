#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Korea Investment & Securities (KIS) Collector
"""
import logging
import requests
import json
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from services.kr_market_data_cache_service import (
    atomic_write_text,
    load_json_payload_from_path,
)

logger = logging.getLogger(__name__)

class KisCollector:
    """한국투자증권 Open API 수집기"""
    
    BASE_URLS = {
        'real': "https://openapi.koreainvestment.com:9443",
        'virtual': "https://openapivts.koreainvestment.com:29443"
    }
    
    def __init__(self, config=None):
        self.config = config
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_no = os.getenv("KIS_ACCOUNT_NO")
        self.mode = os.getenv("KIS_MODE", "virtual")
        self.base_url = self.BASE_URLS.get(self.mode, self.BASE_URLS['virtual'])
        
        self.token_file = os.path.join(os.path.dirname(__file__), f".kis_token_{self.mode}.json")
        self.access_token = None
        self.token_expired_at = None
        
        self.session = requests.Session()
        self._load_token_from_file()
        
    def _load_token_from_file(self):
        """저장된 토큰 로드"""
        if os.path.exists(self.token_file):
            try:
                data = load_json_payload_from_path(self.token_file)
                if not isinstance(data, dict):
                    return
                self.access_token = data.get("access_token")
                expired_at_str = data.get("expired_at")
                if expired_at_str:
                    self.token_expired_at = datetime.fromisoformat(expired_at_str)
                logger.info("Loaded KIS token from file")
            except Exception as e:
                logger.warning(f"Failed to load KIS token file: {e}")

    def _save_token_to_file(self):
        """토큰 정보를 파일에 저장"""
        try:
            payload = {
                "access_token": self.access_token,
                "expired_at": self.token_expired_at.isoformat() if self.token_expired_at else None,
            }
            atomic_write_text(
                self.token_file,
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        except Exception as e:
            logger.warning(f"Failed to save KIS token file: {e}")

    def _is_token_valid(self) -> bool:
        """액세스 토큰 유효성 확인"""
        if not self.access_token or not self.token_expired_at:
            return False
        # 만료 1시간 전까지는 유효한 것으로 간주
        return datetime.now() < self.token_expired_at

    def get_access_token(self) -> bool:
        """액세스 토큰 발급/갱신"""
        if self._is_token_valid():
            return True
            
        if not self.app_key or not self.app_secret:
            return False
            
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }
        
        try:
            res = self.session.post(url, headers=headers, data=json.dumps(body))
            if res.status_code == 200:
                data = res.json()
                self.access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 86400))
                self.token_expired_at = datetime.now().replace(microsecond=0) + timedelta(seconds=expires_in)
                self._save_token_to_file()
                logger.info("KIS API Access Token issued and saved")
                return True
            else:
                logger.error(f"KIS Token Error: {res.status_code} - {res.text}")
                return False
        except Exception as e:
            logger.error(f"KIS Token Exception: {e}")
            return False

    def get_investor_trend_intraday(self, code: str) -> Optional[Dict]:
        """
        장중 투자자 매매동향 가집계 조회
        주요 응답: 외국인/기관 잠정 매수/매도 수량
        """
        if not self.get_access_token():
            return None
            
        # [주의] 이 API는 특정 시간에만 업데이트됨 (09:30, 11:20, 13:20 등)
        # TR_ID: HHDFS76200200 (종목별 투자자 가집계)
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor"
        
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010900", # 주식현재가 투자자별매매 (확정치 위주이나 당일 실시간성 일부 제공)
        }
        
        # 실제 장중 가집계 TR_ID는 다를 수 있음. KIS 포털 확인 결과:
        # FHKST01010900: 투자자별 매매동향 (일별)
        # FHKST01010100: 현재가 상세 (여기에 가집계가 포함되기도 함)
        
        # 장중 가집계 전용 TR (시간대별 가집계): HHDFS76200200
        # 하지만 범용적으로 사용되는 FHKST01010900 (종목별 투자자)를 먼저 시도
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", # 주식 
            "FID_INPUT_ISCD": code
        }
        
        try:
            res = self.session.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json()
                output = data.get("output", [])
                if not output:
                    return None
                
                # 가장 최근(오늘) 데이터
                latest = output[0]
                
                # 수량 데이터 (전일 대비 순매수량 등)
                return {
                    'code': code,
                    'date': latest.get('stck_bsop_date'),
                    'foreign': int(latest.get('ntby_qty', 0)), # 외국인 순매수량
                    'institution': int(latest.get('stck_prpr', 0)), # 필드 확인 필요
                    'raw': latest
                }
            else:
                logger.warning(f"KIS API Failed: {res.status_code} - {res.text}")
                return None
        except Exception as e:
            logger.error(f"KIS API Exception: {e}")
            return None

    def get_market_investor_trend(self, market_code: str = "0001") -> Optional[Dict]:
        """
        시장(KOSPI: 0001, KOSDAQ: 1001) 전체 수급 잠정치 조회
        Market Gate 점수 계산에 직접 활용 가능
        """
        if not self.get_access_token():
            return None
            
        # TR_ID: FHKST03010900 (투자자별 매매동향 - 시장전체)
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-investor-market-trend"
        
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010900",
        }
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "U", # 지수
            "FID_INPUT_ISCD": market_code
        }
        
        try:
            res = self.session.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json()
                output = data.get("output", [])
                if not output:
                    return None
                
                latest = output[0]
                return {
                    'market': 'KOSPI' if market_code == "0001" else 'KOSDAQ',
                    'date': latest.get('stck_bsop_date'),
                    'individual_buy': int(latest.get('prsn_ntby_qty', 0)), # 개인 순매수
                    'foreign_buy': int(latest.get('frgn_ntby_qty', 0)),    # 외국인 순매수
                    'inst_buy': int(latest.get('asst_ntby_qty', 0)),      # 기관 순매수
                    'raw': latest
                }
            return None
        except Exception as e:
            logger.error(f"KIS Market Trend Error: {e}")
            return None

# 간단 테스트 코드
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    collector = KisCollector()
    if collector.get_access_token():
        print("Token Success")
        # 삼성전자 테스트
        # res = collector.get_investor_trend_intraday("005930")
        # print(res)
