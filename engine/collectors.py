#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Collectors (데이터 수집기)
"""
import logging
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
from engine.models import StockData, ChartData, NewsItem, SupplyData

logger = logging.getLogger(__name__)


class KRXCollector:
    """KRX 데이터 수집기"""


    # 경고 로그 중복 출력 방지 플래그
    _market_date_warning_shown = False

    def __init__(self, config):
        self.config = config

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _get_latest_market_date(self) -> str:
        """
        가장 최근 장 마감 날짜 반환
        - 주말(토/일): 금요일 날짜 반환
        - 금요일이 휴일인 경우: pykrx를 통해 실제 마지막 개장일 확인
        - 평일 장 마감 전(~15:30): 전일 날짜 반환
        - 평일 장 마감 후(15:30~): 당일 날짜 반환
        """
        now = datetime.now()
        weekday = now.weekday()  # 0=월, 1=화, ..., 5=토, 6=일
        
        # 장 마감 시간 (15:30)
        market_close_hour = 15
        market_close_minute = 30
        
        if weekday == 5:  # 토요일 -> 금요일
            target = now - timedelta(days=1)
        elif weekday == 6:  # 일요일 -> 금요일
            target = now - timedelta(days=2)
        elif now.hour < market_close_hour or (now.hour == market_close_hour and now.minute < market_close_minute):
            # 평일 장 마감 전 -> 전일 데이터 (주말 건너뛰기)
            if weekday == 0:  # 월요일 아침 -> 금요일
                target = now - timedelta(days=3)
            else:
                target = now - timedelta(days=1)
        else:
            # 평일 장 마감 후 -> 당일 데이터
            target = now
        
        # pykrx를 통해 실제 개장일 확인 (휴일 대응)
        try:
            from pykrx import stock
            
            # 최근 10일간 거래일 조회 (휴일 연속 대비)
            start_check = (target - timedelta(days=10)).strftime('%Y%m%d')
            end_check = target.strftime('%Y%m%d')
            
            # KOSPI 지수의 OHLCV로 개장일 확인
            kospi_data = stock.get_index_ohlcv_by_date(start_check, end_check, "1001")
            
            if not kospi_data.empty:
                # 마지막 거래일을 가져옴
                last_trading_date = kospi_data.index[-1]
                last_trading_date_str = last_trading_date.strftime('%Y%m%d')
                return last_trading_date_str
            
        except ImportError:
            if not self._market_date_warning_shown:
                logger.warning("pykrx 미설치 - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True
        except Exception as e:
            if not self._market_date_warning_shown:
                logger.warning(f"개장일 확인 실패: {e} - 주말 처리만 적용")
                KRXCollector._market_date_warning_shown = True
        
        # 폴백: 주말 처리만 된 날짜 반환
        return target.strftime('%Y%m%d')

    async def get_top_gainers(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """
        상승률 상위 종목 조회 (pykrx 실데이터 + 로컬 CSV Fallback)
        Args:
            market: 'KOSPI' or 'KOSDAQ'
            top_n: 조회할 종목 수
            target_date: (Optional) 특정 날짜 기준 데이터 조회 (YYYYMMDD 형식, 테스트용)
        """
        
        # 1. pykrx 실시간 데이터 시도
        try:
            from pykrx import stock
            import pandas as pd
            
            # 테스트 모드: 특정 날짜 지정 시 해당 날짜 사용
            if target_date:
                target_date_str = target_date  # YYYYMMDD 형식
                logger.info(f"[테스트 모드] 지정 날짜 기준 조회: {target_date_str}")
            else:
                # 가장 최근 장 마감 날짜 계산
                target_date_str = self._get_latest_market_date()
                
            logger.info(f"목표 날짜: {target_date_str}")
            
            df = None
            
            # 목표 날짜부터 최대 7일 전까지 시도 (공휴일 대응)
            base_date = datetime.strptime(target_date_str, '%Y%m%d')
            for days_ago in range(7):
                try:
                    check_date = (base_date - timedelta(days=days_ago)).strftime('%Y%m%d')
                    df = stock.get_market_ohlcv_by_ticker(check_date, market=market)
                    if not df.empty:
                        logger.info(f"pykrx 데이터 로드 성공: {check_date}")
                        break
                except Exception as e:
                    continue
            
            if df is not None and not df.empty:
                return self._process_ohlcv_dataframe(df, market, top_n)
                
        except Exception as e:
            logger.warning(f"pykrx 실시간 데이터 수집 실패: {e}")
        
        # 2. Fallback: 로컬 daily_prices.csv 사용
        logger.info(f"Fallback: 로컬 daily_prices.csv 사용 ({market}) Target={target_date}")
        return self._load_from_local_csv(market, top_n, target_date)
    
    def _process_ohlcv_dataframe(self, df, market: str, top_n: int) -> List[StockData]:
        """pykrx DataFrame을 StockData 리스트로 변환"""
        from pykrx import stock
        
        # 필터링
        mask_price = df['종가'] >= 1000
        mask_vol = df['거래대금'] >= 1_000_000_000
        mask_rise = df['등락률'] > 0
        
        filtered_df = df[mask_price & mask_vol & mask_rise].copy()
        filtered_df = filtered_df.sort_values(by='등락률', ascending=False)
        top_df = filtered_df.head(top_n)
        
        results = []
        for code, row in top_df.iterrows():
            try:
                name = stock.get_market_ticker_name(code)
                results.append(StockData(
                    code=code,
                    name=name,
                    market=market,
                    sector=self._get_sector(code),
                    close=int(row['종가']),
                    change_pct=float(row['등락률']),
                    trading_value=float(row['거래대금']),
                    volume=int(row['거래량']),
                    marcap=int(row['시가총액']) if '시가총액' in row else 0,
                    high_52w=0,
                    low_52w=0
                ))
            except Exception as e:
                logger.error(f"종목 데이터 변환 실패 ({code}): {e}")
                continue
        return results
    
    def _load_from_local_csv(self, market: str, top_n: int, target_date: str = None) -> List[StockData]:
        """로컬 daily_prices.csv에서 상승률 상위 종목 로드"""
        import pandas as pd
        import os
        
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'daily_prices.csv')
        stocks_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'korean_stocks_list.csv')
        
        if not os.path.exists(csv_path):
            logger.error(f"daily_prices.csv 파일 없음: {csv_path}")
            return []
        
        try:
            df = pd.read_csv(csv_path)
            # logger.info(f"CSV Loaded: {len(df)} rows. Columns: {df.columns.tolist()}")
            
            # 종목 목록에서 마켓 정보 가져오기
            stocks_df = pd.read_csv(stocks_path) if os.path.exists(stocks_path) else pd.DataFrame()
            market_map = {}
            if not stocks_df.empty and 'ticker' in stocks_df.columns and 'market' in stocks_df.columns:
                for _, row in stocks_df.iterrows():
                    market_map[str(row['ticker']).zfill(6)] = row['market']
            
            # 날짜 필터링
            df['date'] = pd.to_datetime(df['date'])
            
            if target_date:
                # target_date는 YYYYMMDD 또는 YYYY-MM-DD
                if len(str(target_date)) == 8:
                    dt = datetime.strptime(str(target_date), "%Y%m%d")
                else:
                    dt = pd.to_datetime(target_date)
                
                # 해당 날짜 데이터 검색
                latest_df = df[df['date'].dt.date == dt.date()].copy()
                if latest_df.empty:
                    logger.warning(f"로컬 CSV에 {target_date} 데이터 없음. 최신 날짜로 대체 시도.")
                    latest_date = df['date'].max()
                    latest_df = df[df['date'] == latest_date].copy()
            else:
                latest_date = df['date'].max()
                latest_df = df[df['date'] == latest_date].copy()
            
            logger.info(f"로컬 데이터 날짜: {latest_df['date'].max()}")
            
            # 마켓 필터링
            latest_df['ticker'] = latest_df['ticker'].astype(str).str.zfill(6)
            latest_df['market_actual'] = latest_df['ticker'].map(market_map)
            
            logger.info(f"Market Map Size: {len(market_map)}")
            logger.info(f"Before Market Filter: {len(latest_df)} rows")
            
            latest_df = latest_df[latest_df['market_actual'] == market]
            logger.info(f"After Market Filter ({market}): {len(latest_df)} rows")
            
            # 등락률 계산
            if 'change_pct' not in latest_df.columns:
                if 'open' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['change_pct'] = ((latest_df['close'] - latest_df['open']) / latest_df['open'] * 100).fillna(0)
                else:
                    latest_df['change_pct'] = 0
            
            # 거래대금 계산 (0인 경우 재계산)
            if 'trading_value' not in latest_df.columns:
                if 'volume' in latest_df.columns and 'close' in latest_df.columns:
                    latest_df['trading_value'] = latest_df['volume'] * latest_df['close']
                else:
                    latest_df['trading_value'] = 0
            else:
                 # 0 또는 NaN인 값 재계산
                 latest_df['trading_value'] = latest_df['trading_value'].fillna(0).astype(float)
                 mask_zero = latest_df['trading_value'] <= 0
                 
                 if mask_zero.any():
                     logger.debug(f"Recalculating 0/NaN trading_value for {mask_zero.sum()} rows")
                     latest_df.loc[mask_zero, 'trading_value'] = latest_df.loc[mask_zero, 'volume'] * latest_df.loc[mask_zero, 'close']
            
            # 필터링
            mask_price = latest_df['close'] >= 1000
            mask_vol = latest_df['trading_value'] >= 1_000_000_000
            mask_rise = latest_df['change_pct'] > 0
            
            logger.info(f"TopGainers Filter ({market}): Rise={mask_rise.sum()}, ValidVol={mask_vol.sum()}")
            
            filtered_df = latest_df[mask_price & mask_vol & mask_rise].copy()
            filtered_df = filtered_df.sort_values(by='change_pct', ascending=False)
            top_df = filtered_df.head(top_n)
            
            # 종목명 매핑
            name_map = {}
            if not stocks_df.empty:
                for _, row in stocks_df.iterrows():
                    name_map[str(row['ticker']).zfill(6)] = row['name']
            
            results = []
            for _, row in top_df.iterrows():
                ticker = str(row['ticker']).zfill(6)
                results.append(StockData(
                    code=ticker,
                    name=name_map.get(ticker, ticker),
                    market=market,
                    sector='',
                    close=int(row['close']),
                    change_pct=float(row['change_pct']),
                    trading_value=float(row['trading_value']),
                    volume=int(row.get('volume', 0)),
                    marcap=0,
                    high_52w=0,
                    low_52w=0
                ))
            
            logger.info(f"로컬 CSV에서 {len(results)}개 종목 로드 완료 ({market})")
            if len(results) == 0:
                logger.warning(f"로컬 CSV 로드 결과가 0개입니다. 파일 내용을 확인하세요. (df shape: {df.shape if 'df' in locals() else 'N/A'})")
            else:
                 # 상위 5개 로그 출력
                for i, s in enumerate(results[:5]):
                    logger.info(f"  [{i+1}] {s.name}: {s.change_pct}%")
            return results
            
        except Exception as e:
            logger.error(f"로컬 CSV 로드 실패: {e}")
            return []

    async def get_stock_detail(self, code: str) -> Optional[Dict]:
        """종목 상세 정보 조회"""
        try:
            return {
                'code': code,
                'name': self._get_stock_name(code),
                'high_52w': 150000,
                'low_52w': 50000
            }
        except Exception as e:
            logger.error(f"종목 상세 조회 실패 ({code}): {e}")
            return None

    async def get_chart_data(self, code: str, days: int) -> Optional[ChartData]:
        """차트 데이터 조회"""
        try:
            # logger.info(f"Chart data generation for {code} (FIX_V2)") # 디버그용 로그
            import random

            # 실제 데이터 조회 (pykrx)
            from pykrx import stock
            
            # 종료일: 최신 장 마감일
            end_date_str = self._get_latest_market_date()
            end_date = datetime.strptime(end_date_str, "%Y%m%d")
            
            # 시작일: 휴일 고려하여 넉넉하게 계산 (약 1.6배)
            start_date = end_date - timedelta(days=int(days * 1.6) + 10)
            start_date_str = start_date.strftime("%Y%m%d")
            
            df = stock.get_market_ohlcv_by_date(start_date_str, end_date_str, code)
            
            if df.empty:
                return None
                
            # 최근 N일 데이터만 사용
            df = df.tail(days)
            
            dates = [d.date() for d in df.index]
            opens = df['시가'].tolist()
            highs = df['고가'].tolist()
            lows = df['저가'].tolist()
            closes = df['종가'].tolist()
            volumes = df['거래량'].tolist()

            return ChartData(
                dates=dates,
                opens=opens,
                highs=highs,
                lows=lows,
                closes=closes,
                volumes=volumes
            )

        except Exception as e:
            logger.error(f"차트 데이터 조회 실패 ({code}): {e}")
            return None

    async def get_supply_data(self, code: str) -> Optional[SupplyData]:
        """수급 데이터 조회 - pykrx 실제 데이터"""
        try:
            from pykrx import stock
            from datetime import datetime, timedelta
            
            # 최근 5일간 수급 데이터 조회
            # 최근 5일간 수급 데이터 조회
            # 날짜 로직 개선: 주말/휴일 고려
            end_date = self._get_latest_market_date()
            end_dt = datetime.strptime(end_date, "%Y%m%d")
            start_date = (end_dt - timedelta(days=10)).strftime('%Y%m%d')
            
            try:
                df = stock.get_market_trading_value_by_date(start_date, end_date, code)
                
                if df.empty:
                    # 데이터 없으면 기본값 반환
                    return SupplyData(
                        foreign_buy_5d=0,
                        inst_buy_5d=0,
                        retail_buy_5d=0
                    )
                
                # 최근 5일 데이터만 사용
                df = df.tail(5)
                
                # 컬럼명: 기관합계, 외국인합계, 개인 등
                # pykrx 버전에 따라 컬럼명이 다를 수 있음
                foreign_col = '외국인합계' if '외국인합계' in df.columns else '외국인'
                inst_col = '기관합계' if '기관합계' in df.columns else '기관'
                retail_col = '개인' if '개인' in df.columns else '개인합계'
                
                foreign_5d = int(df[foreign_col].sum()) if foreign_col in df.columns else 0
                inst_5d = int(df[inst_col].sum()) if inst_col in df.columns else 0
                retail_5d = int(df[retail_col].sum()) if retail_col in df.columns else 0
                
                return SupplyData(
                    foreign_buy_5d=foreign_5d,
                    inst_buy_5d=inst_5d,
                    retail_buy_5d=retail_5d
                )
                
            except Exception as e:
                logger.warning(f"pykrx 수급 조회 실패 ({code}): {e}")
                return SupplyData(
                    foreign_buy_5d=0,
                    inst_buy_5d=0,
                    retail_buy_5d=0
                )
                
        except Exception as e:
            logger.error(f"수급 데이터 조회 실패 ({code}): {e}")
            return None

    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회"""
        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
            '068270': '셀트리온', '052190': '삼성에스디에스',
            '011200': 'HMM', '096770': 'SK이노베이션', '066570': 'LG전자'
        }
        return names.get(ticker, '알 수 없는 종목')

    def _get_sector(self, ticker: str) -> str:
        """섹터 조회"""
        sectors = {
            '005930': '반도체', '000270': '자동차', '035420': '인터넷',
            '005380': '자동차', '015760': '반도체', '068270': '헬스케어',
            '052190': '반도체', '011200': '해운', '096770': '통신',
            '066570': '2차전지'
        }
        return sectors.get(ticker, '기타')

class EnhancedNewsCollector:
    """향상된 뉴스 수집기 - 네이버 금융 크롤링 + 네이버 뉴스 검색"""

    # 주요 언론사 가중치 (PART_07.md 기준)
    MAJOR_SOURCES = {
        "한국경제": 0.9,
        "매일경제": 0.9,
        "머니투데이": 0.85,
        "서울경제": 0.85,
        "이데일리": 0.85,
        "연합뉴스": 0.85,
        "뉴스1": 0.8,
        "파이낸셜뉴스": 0.8,
        "아시아경제": 0.8,
        "헤럴드경제": 0.8,
    }

    def __init__(self, config):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://finance.naver.com/',
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    # 플랫폼별 신뢰도 (AIAnalysis.md 기준)
    PLATFORM_RELIABILITY = {
        "finance": 0.9,  # 네이버 금융 크롤링
        "search_naver": 0.85,  # 네이버 뉴스 검색
        "search_daum": 0.8,   # 다음 뉴스 검색
    }

    def _get_weight(self, source: str, platform: str = 'search_naver') -> float:
        """
        언론사 가중치 + 플랫폼 신뢰도 기반 최종 점수 반환 
        Formula: Publisher Weight * Platform Reliability
        """
        publisher_weight = 0.7 # 기본값
        for major_source, weight in self.MAJOR_SOURCES.items():
            if major_source in source:
                publisher_weight = weight
                break
        
        platform_score = self.PLATFORM_RELIABILITY.get(platform, 0.8)
        
        # 소수점 2자리 반올림
        return round(publisher_weight * platform_score, 2)

    async def get_stock_news(self, code: str, limit: int, name: str = None) -> List[NewsItem]:
        """종목 뉴스 수집 - 다중 소스 통합 (네이버 금융, 네이버 검색, 다음 검색)"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            stock_name = name or self._get_stock_name(code)
            all_news = []
            seen_titles = set()
            
            # 수집 목록 (각 소스별 최대 수집 개수 - limit보다 넉넉하게)
            SOURCE_LIMIT = limit * 2 
            
            # 1. 네이버 금융 종목 뉴스 페이지 (iframe 내부 URL 사용)
            # /item/news_news.naver는 프레임일 뿐이고, 실제 데이터는 /item/news_news.naver에 있음
            try:
                url = f'https://finance.naver.com/item/news_news.naver?code={code}'
                # 네이버 금융 뉴스 요청 시 Referer를 해당 종목 메인으로 설정
                headers_finance = self.headers.copy()
                headers_finance['Referer'] = f'https://finance.naver.com/item/news.naver?code={code}'
                
                response = requests.get(url, headers=headers_finance, timeout=5)
                
                if response.ok:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 뉴스 제목 클래스: .tit 또는 .title
                    # 보통 네이버 금융 뉴스 리스트는 div.news_section 또는 table 구조임
                    # /item/news_news.naver 구조: table.type5 사용 (맞음)
                    news_table = soup.select_one('table.type5')
                    
                    if news_table:
                        for row in news_table.select('tr'):
                            # 제목: td.title > a
                            title_el = row.select_one('td.title a')
                            if not title_el: continue
                            
                            title = title_el.text.strip()
                            if not title or title in seen_titles: continue
                            
                            news_url = title_el.get('href', '')
                            if news_url and not news_url.startswith('http'):
                                news_url = f'https://finance.naver.com{news_url}'
                                
                            # 언론사: td.info
                            source_el = row.select_one('td.info')
                            source = source_el.text.strip() if source_el else '네이버금융'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title,
                                source=source,
                                url=news_url,
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            if len(all_news) >= SOURCE_LIMIT: break
                            
            except Exception as e:
                logger.debug(f"네이버 금융 뉴스 수집 실패: {e}")

            # 2. 네이버 뉴스 검색 (키워드)
            if stock_name:
                try:
                    search_url = f'https://search.naver.com/search.naver?where=news&query={stock_name}&sort=1'
                    response = requests.get(search_url, headers=self.headers, timeout=5)
                    
                    if response.ok:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # Selectors often change, try multiple common patterns
                        # div.news_area, div.news_wrap, li.bx, div.news_contents
                        items = soup.select('div.news_wrap') or soup.select('li.bx') or soup.select('div.news_area') or soup.select('div.news_contents')
                        
                        count = 0
                        for item in items:
                            title_el = item.select_one('a.news_tit')
                            if not title_el: continue
                            
                            title = title_el.get('title') or title_el.text.strip()
                            if not title or title in seen_titles: continue
                            
                            # 언론사: a.info.press, span.info.press, div.info_group > a.press
                            source_el = item.select_one('a.info.press') or item.select_one('span.info.press') or item.select_one('a.press')
                            source = source_el.text.strip().replace('언론사 선정', '') if source_el else '네이버검색'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title, # 요약은 추후 LLM이 처리하거나 본문 수집 시
                                source=source,
                                url=title_el.get('href', ''),
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            count += 1
                            if count >= SOURCE_LIMIT: break
                            
                except Exception as e:
                    logger.debug(f"네이버 뉴스 검색 실패: {e}")

            # 3. 다음 뉴스 검색
            if stock_name:
                try:
                    daum_url = f'https://search.daum.net/search?w=news&q={stock_name}&sort=recency'
                    response = requests.get(daum_url, headers=self.headers, timeout=5)
                    
                    if response.ok:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # c-item-content, item-bundle-mid
                        items = soup.select('div.c-item-content') or soup.select('ul.list_news > li') or soup.select('div.item-bundle-mid')
                        
                        count = 0
                        for item in items:
                            link = item.select_one('a.item-title') or item.select_one('a.f_link_b') or item.select_one('a.tit_main')
                            if not link: continue
                            
                            title = link.text.strip()
                            if not title or title in seen_titles: continue
                            
                            source_el = item.select_one('span.txt_info') or item.select_one('a.txt_info') or item.select_one('span.f_nb')
                            source = source_el.text.strip() if source_el else '다음검색'
                            
                            seen_titles.add(title)
                            all_news.append(NewsItem(
                                title=title,
                                summary=title,
                                source=source,
                                url=link.get('href', ''),
                                published_at=datetime.now(),
                                weight=self._get_weight(source)
                            ))
                            count += 1
                            if count >= SOURCE_LIMIT: break
                            
                except Exception as e:
                    logger.debug(f"다음 뉴스 검색 실패: {e}")
            
            if not all_news:
                return []
                
            # 통합 정렬 (1순위: 가중치, 2순위: 원래 순서-최신순)
            # stable sort이므로 weight로만 정렬하면 같은 weight 내에서는 최신순 유지됨 (각 소스가 최신순이라 가정)
            sorted_news = sorted(all_news, key=lambda x: x.weight, reverse=True)
            
            final_news = sorted_news[:limit]
            
                
            # 로그 출력 (디버깅용)
            sources_summary = [f"{n.source}({n.weight})" for n in final_news]
            logger.info(f"뉴스 수집 완료: {stock_name} -> {len(final_news)}개 [{', '.join(sources_summary[:3])}...]")
            
            return final_news
            
        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return []
        except Exception as e:
            logger.error(f"뉴스 수집 전체 실패 ({code}): {e}")
            return []
    def _get_stock_name(self, ticker: str) -> str:
        """종목명 조회"""
        names = {
            '005930': '삼성전자', '000270': '기아', '035420': 'NAVER',
            '005380': '현대차', '015760': '한화사이언스',
        }
        return names.get(ticker, '알 수 없는 종목')


class NaverFinanceCollector:
    """네이버 금융 상세 정보 수집기 - 투자지표, 재무정보, 52주 범위 등"""

    def __init__(self, config=None):
        self.config = config
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://finance.naver.com/',
        }

    async def get_stock_detail_info(self, code: str) -> Optional[Dict]:
        """
        네이버 금융에서 종목 상세 정보 수집
        - 시세 정보: 현재가, 전일가, 시가, 고가, 저가
        - 52주 최고/최저가
        - 투자 지표: PER, PBR, ROE 등
        - 시가총액
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            import re

            result = {
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

            # 1. 네이버 금융 메인 페이지에서 기본 정보 수집
            url = f'https://finance.naver.com/item/main.naver?code={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')

            # 종목명 추출
            name_el = soup.select_one('div.wrap_company h2 a')
            if name_el:
                result['name'] = name_el.text.strip()

            # 시장 구분 (KOSPI/KOSDAQ)
            market_img = soup.select_one('img.kospi, img.kosdaq, img[alt*="코스피"], img[alt*="코스닥"]')
            if market_img:
                alt = market_img.get('alt', '').upper()
                if 'KOSDAQ' in alt or '코스닥' in alt:
                    result['market'] = 'KOSDAQ'
                else:
                    result['market'] = 'KOSPI'

            # 현재가
            current_price_el = soup.select_one('p.no_today span.blind')
            if current_price_el:
                try:
                    result['priceInfo']['current'] = int(current_price_el.text.replace(',', ''))
                except:
                    pass

            # 전일가
            prev_close_el = soup.select_one('td.first span.blind')
            if prev_close_el:
                try:
                    result['priceInfo']['prevClose'] = int(prev_close_el.text.replace(',', ''))
                except:
                    pass

            # 시가, 고가, 저가, 거래량 (table.no_info에서)
            no_info_table = soup.select('table.no_info td span.blind')
            if len(no_info_table) >= 4:
                try:
                    result['priceInfo']['high'] = int(no_info_table[1].text.replace(',', '')) if no_info_table[1] else 0
                    result['priceInfo']['low'] = int(no_info_table[3].text.replace(',', '')) if no_info_table[3] else 0
                except:
                    pass

            # 52주 최고/최저가 (우측 박스)
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

            # 투자 지표 (PER, PBR 등)
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

            # 시가총액
            market_cap_el = soup.select_one('#_market_sum')
            if market_cap_el:
                try:
                    # "2,142,543억원" 형태
                    cap_text = market_cap_el.text.replace(',', '').replace('억원', '').replace('조', '').strip()
                    result['indicators']['marketCap'] = int(float(cap_text) * 100000000)  # 억원 -> 원
                except:
                    pass

            # 2. pykrx에서 투자자 동향 가져오기 (옵션)
            try:
                await self._get_investor_trend(code, result)
            except Exception as e:
                logger.debug(f"투자자 동향 조회 실패 ({code}): {e}")

            # 3. pykrx에서 기본적인 펀더멘탈 데이터 가져오기
            try:
                await self._get_fundamental_data(code, result)
            except Exception as e:
                logger.debug(f"펀더멘탈 데이터 조회 실패 ({code}): {e}")

            logger.info(f"상세 정보 수집 완료: {result['name']} ({code})")
            return result

        except ImportError as e:
            logger.error(f"requests/BeautifulSoup 미설치: {e}")
            return None
        except Exception as e:
            logger.error(f"상세 정보 수집 실패 ({code}): {e}")
            return None

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

    async def get_financials(self, code: str) -> Dict:
        """재무 정보 수집 (네이버 금융 기업분석)"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            result = {
                'revenue': 0,
                'operatingProfit': 0,
                'netIncome': 0,
            }

            # 네이버 기업분석 페이지
            url = f'https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 재무제표 테이블에서 매출, 영업이익, 순이익 추출
                # (페이지 구조에 따라 셀렉터 조정 필요)
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
                                    result['revenue'] = float(tds[0].text.replace(',', '').strip()) * 100000000
                                except:
                                    pass
                            elif '영업이익' in label and tds:
                                try:
                                    result['operatingProfit'] = float(tds[0].text.replace(',', '').strip()) * 100000000
                                except:
                                    pass
                            elif '순이익' in label or '당기순이익' in label and tds:
                                try:
                                    result['netIncome'] = float(tds[0].text.replace(',', '').strip()) * 100000000
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
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            
            themes = []
            
            # 네이버 금융 종목 메인 페이지에서 테마 태그 추출
            url = f'https://finance.naver.com/item/main.naver?code={code}'
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.ok:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 1. 업종/테마 정보 추출 (div.sub_section 내 테마 링크)
                theme_links = soup.select('div.sub_section th em a, div.sub_section td a')
                for link in theme_links:
                    theme_text = link.text.strip()
                    if theme_text and len(theme_text) >= 2 and len(theme_text) <= 20:
                        # 일반적인 메뉴 링크 제외
                        if theme_text not in ['더보기', '차트', '뉴스', '게시판', '종합정보']:
                            themes.append(theme_text)
                
                # 2. 업종 정보 추출
                sector_el = soup.select_one('div.section.trade_compare em a')
                if sector_el:
                    sector = sector_el.text.strip()
                    if sector and sector not in themes:
                        themes.append(sector)
                
                # 3. 분류 정보 (KOSPI/KOSDAQ 제외)
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
