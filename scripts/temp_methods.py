    def _fetch_stock_history(self, ticker: str) -> str:
        """daily_prices.csv에서 최근 5일 주가 조회"""
        try:
            import pandas as pd
            path = DATA_DIR / "daily_prices.csv"
            if not path.exists(): return ""
            
            # Efficient reading: using chunks probably overkill for 3MB but good practice.
            # actually 3MB is small enough to load. check cache? NO, just load for now.
            df = pd.read_csv(path, dtype={'ticker': str})
            df['date'] = pd.to_datetime(df['date'])
            target = df[df['ticker'] == ticker].sort_values('date', ascending=False).head(5)
            
            if target.empty: return "주가 데이터 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['date'].strftime('%Y-%m-%d')
                lines.append(f"- {d}: 종가 {row['close']:,.0f} | 거래량 {row['volume']:,.0f} | 등락 {(row['close'] - row['open']):+,.0f}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Price fetch error for {ticker}: {e}")
            return "데이터 조회 실패"

    def _fetch_institutional_trend(self, ticker: str) -> str:
        """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
        try:
            import pandas as pd
            path = DATA_DIR / "all_institutional_trend_data.csv"
            if not path.exists(): return ""
            
            df = pd.read_csv(path, dtype={'ticker': str})
            df['date'] = pd.to_datetime(df['date'])
            target = df[df['ticker'] == ticker].sort_values('date', ascending=False).head(5)
            
            if target.empty: return "수급 데이터 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['date'].strftime('%Y-%m-%d')
                fb = row['foreign_buy']
                inst = row['inst_buy']
                lines.append(f"- {d}: 외인 {fb:+,.0f} | 기관 {inst:+,.0f}")
            return "\n".join(lines)
        except Exception as e:
            return "데이터 조회 실패"

    def _fetch_signal_history(self, ticker: str) -> str:
        """signals_log.csv에서 VCP 시그널 이력 조회"""
        try:
            import pandas as pd
            path = DATA_DIR / "signals_log.csv"
            if not path.exists(): return ""
            
            df = pd.read_csv(path, dtype={'ticker': str})
            target = df[df['ticker'] == ticker].sort_values('signal_date', ascending=False)
            
            if target.empty: return "과거 VCP 포착 이력 없음"
            
            lines = []
            for _, row in target.iterrows():
                d = row['signal_date']
                s = row['score']
                lines.append(f"- {d}: {s}점 VCP 포착")
            return "\n".join(lines)
        except Exception as e:
            return "조회 실패"

    def _format_stock_context(self, name: str, ticker: str) -> str:
        """종목 관련 모든 데이터 통합"""
        price_txt = self._fetch_stock_history(ticker)
        trend_txt = self._fetch_institutional_trend(ticker)
        signal_txt = self._fetch_signal_history(ticker)
        
        return f"""
## [종목 상세 데이터: {name} ({ticker})]
### 1. 최근 주가 (5일)
{price_txt}

### 2. 수급 현황 (5일)
{trend_txt}

### 3. VCP 시그널 이력
{signal_txt}
"""

    def _detect_stock_query(self, message: str) -> Optional[str]:
        """종목 관련 질문 감지 및 상세 정보 반환 (전체 종목 대상)"""
        # 1. Watchlist 우선 검색 (Context Optimization)
        # (This is handled in chat method but helpful to do full lookup here too if specifically asked)
        
        detected_name = None
        detected_ticker = None
        
        # 이름/코드 매핑 사용
        for name, ticker in self.stock_map.items():
            if name in message:
                detected_name = name
                detected_ticker = ticker
                break
        
        if not detected_ticker:
            for ticker, name in self.ticker_map.items():
                if ticker in message:
                    detected_name = name
                    detected_ticker = ticker
                    break
        
        if detected_name and detected_ticker:
            logger.info(f"Detected stock query: {detected_name}")
            return self._format_stock_context(detected_name, detected_ticker)
            
        return None
