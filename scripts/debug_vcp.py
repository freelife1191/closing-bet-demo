import os
import pandas as pd
import numpy as np
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def calculate_vcp_score(df: pd.DataFrame) -> dict:
    if len(df) < 20:
        return {'score': 0, 'contraction_ratio': 0, 'reasons': []}
    
    try:
        df = df.sort_index()
        
        # Volatility Contraction
        df['range'] = df['high'] - df['low']
        recent_range = df['range'].tail(5).mean()
        avg_range = df['range'].tail(20).mean()
        contraction_ratio = recent_range / avg_range if avg_range > 0 else 1
        
        # Volume Contraction
        recent_vol = df['volume'].tail(5).mean()
        avg_vol = df['volume'].tail(20).mean()
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
        
        # MA Alignment
        ma5 = df['close'].tail(5).mean()
        ma20 = df['close'].tail(20).mean()
        current_price = df['close'].iloc[-1]
        
        score = 0
        reasons = []
        
        # Scoring logic (same as init_data.py)
        if contraction_ratio < 0.5: score += 40
        elif contraction_ratio < 0.7: score += 30
        elif contraction_ratio < 0.9: score += 15
        
        if vol_ratio < 0.5: score += 30
        elif vol_ratio < 0.7: score += 20
        elif vol_ratio < 0.9: score += 10
        
        if current_price > ma5 > ma20: score += 30
        elif current_price > ma20: score += 15
        
        return {'score': score, 'contraction_ratio': round(contraction_ratio, 2)}
    except:
        return {'score': 0}

def calculate_supply_score(ticker: str, inst_df: pd.DataFrame) -> dict:
    try:
        df = inst_df[inst_df['ticker'].astype(str).str.zfill(6) == ticker].sort_values('date')
        if len(df) < 5:
            return {'score': 0}
        
        recent = df.tail(5)
        foreign_5d = recent['foreign_buy'].sum()
        inst_5d = recent['inst_buy'].sum()
        
        score = 0
        # Scoring logic (same as init_data.py)
        if foreign_5d > 1000000000: score += 40
        elif foreign_5d > 500000000: score += 25
        elif foreign_5d > 0: score += 10
        
        if inst_5d > 500000000: score += 30
        elif inst_5d > 200000000: score += 20
        elif inst_5d > 0: score += 10
        
        consecutive = 0
        for val in reversed(recent['foreign_buy'].values):
            if val > 0: consecutive += 1
            else: break
        score += min(consecutive * 6, 30)
        
        return {'score': score, 'foreign_5d': int(foreign_5d), 'inst_5d': int(inst_5d)}
    except:
        return {'score': 0}

def main():
    print("=== Debugging Closing Bet Logic ===")
    
    prices_file = os.path.join(BASE_DIR, 'data', 'daily_prices.csv')
    inst_file = os.path.join(BASE_DIR, 'data', 'all_institutional_trend_data.csv')
    stocks_file = os.path.join(BASE_DIR, 'data', 'korean_stocks_list.csv')
    
    print(f"Loading data from {BASE_DIR}/data ...")
    
    if not os.path.exists(prices_file):
        print("Error: daily_prices.csv not found")
        return
        
    prices_df = pd.read_csv(prices_file)
    inst_df = pd.read_csv(inst_file)
    stocks_df = pd.read_csv(stocks_file)
    
    print(f"Stocks: {len(stocks_df)}")
    print(f"Price Rows: {len(prices_df)}")
    print(f"Inst Rows: {len(inst_df)}")
    
    # Check data recency
    print(f"Latest Price Date: {prices_df['date'].max()}")
    print(f"Latest Inst Date: {inst_df['date'].max()}")
    
    analyzed_count = 0
    scores = []
    
    for _, row in stocks_df.iterrows():
        ticker = str(row['ticker']).zfill(6)
        name = row['name']
        
        # Filter prices
        ticker_prices = prices_df[prices_df['ticker'].astype(str).str.zfill(6) == ticker].copy()
        if len(ticker_prices) < 20:
            continue
            
        ticker_prices['date'] = pd.to_datetime(ticker_prices['date'])
        ticker_prices = ticker_prices.set_index('date')
        
        vcp = calculate_vcp_score(ticker_prices)
        supply = calculate_supply_score(ticker, inst_df)
        
        # Calculate Volume Ratio
        vol_ratio = 0.0
        if len(ticker_prices) >= 20:
             recent_vol = ticker_prices['volume'].iloc[-1]
             avg_vol = ticker_prices['volume'].tail(20).mean()
             if avg_vol > 0:
                 vol_ratio = recent_vol / avg_vol
        
        total_score = vcp['score'] * 0.6 + supply['score'] * 0.4
        
        scores.append({
            'ticker': ticker,
            'name': name,
            'total': total_score,
            'vcp': vcp['score'],
            'supply': supply['score'],
            'cr': vcp.get('contraction_ratio', 0),
            'vol_ratio': round(vol_ratio, 2)
        })
        
        analyzed_count += 1
        if analyzed_count % 500 == 0:
            print(f"Analyzed {analyzed_count}...")

    df = pd.DataFrame(scores)
    
    print("\n=== Score Distribution ===")
    print(f"Total Analyzed: {len(df)}")
    if df.empty:
        print("No stocks analyzed.")
        return

    print(f"Avg Score: {df['total'].mean():.2f}")
    print(f"Max Score: {df['total'].max():.2f}")
    
    print("\n[Threshold Counts]")
    print(f">= 60: {len(df[df['total'] >= 60])}")
    print(f">= 50: {len(df[df['total'] >= 50])}")
    
    print("\n[Top 10 Stocks]")
    print(df.sort_values('total', ascending=False).head(10)[['name', 'total', 'vcp', 'supply', 'vol_ratio']])
    
    print("\n[Strict Filter Check]")
    # Now that the filter is enabled, we expect 0 candidates if all have vol_ratio < 2.0
    passed_score = df[df['total'] >= 60]
    passed_filter = passed_score[passed_score['vol_ratio'] >= 2.0]
    
    print(f"Candidates with Score >= 60: {len(passed_score)}")
    print(f"Candidates Passing Volume >= 2.0 Filter: {len(passed_filter)}")
    
    if not passed_filter.empty:
         print(passed_filter[['name', 'total', 'vol_ratio']])
    else:
         print("No candidates passed the volume explosion filter.")

if __name__ == "__main__":
    main()
