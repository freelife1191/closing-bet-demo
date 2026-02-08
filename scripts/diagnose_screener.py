import os
import pandas as pd
import numpy as np
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.screener import SmartMoneyScreener

def main():
    print("=== Diagnosing Production Screener Logic ===")
    
    screener = SmartMoneyScreener()
    screener._load_data()
    
    if screener.stocks_df is None:
        print("Failed to load data.")
        return

    print(f"Total Stocks: {len(screener.stocks_df)}")
    
    results = []
    
    # We will manually iterate and store ALL results, not just > 50, to see the distribution
    for _, stock_row in screener.stocks_df.iterrows():
        stock_dict = {
            'ticker': str(stock_row['ticker']).zfill(6),
            'name': stock_row['name'],
            'market': stock_row.get('market', 'UNKNOWN')
        }
        
        try:
            # We use the internal method _analyze_stock
            result = screener._analyze_stock(stock_dict)
            if result:
                results.append(result)
        except Exception as e:
            continue
            
    df = pd.DataFrame(results)
    
    if df.empty:
        print("No results returned from _analyze_stock.")
        return
        
    print(f"\nAnalyzed {len(df)} stocks successfully.")
    print(f"Max Score: {df['score'].max()}")
    print(f"Min Score: {df['score'].min()}")
    print(f"Avg Score: {df['score'].mean():.2f}")
    
    print("\n[Score Distribution]")
    print(f"Score >= 50: {len(df[df['score'] >= 50])}")
    print(f"Score >= 40: {len(df[df['score'] >= 40])}")
    print(f"Score >= 30: {len(df[df['score'] >= 30])}")
    print(f"Score >= 20: {len(df[df['score'] >= 20])}")
    
    print("\n[Top 10 by Score]")
    top_10 = df.sort_values('score', ascending=False).head(10)
    for _, row in top_10.iterrows():
        print(f"{row['name']} ({row['ticker']}): Score {row['score']} | Supply(F:{row['foreign_net_5d'] // 100000000}억, I:{row['inst_net_5d'] // 100000000}억) | VCP CR:{row['contraction_ratio']}")

if __name__ == "__main__":
    main()
