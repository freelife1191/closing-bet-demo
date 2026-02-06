
from pykrx import stock
from datetime import datetime
import pandas as pd

def check_supply_data():
    today = datetime.now().strftime("%Y%m%d")
    print(f"Checking supply data for {today}...")
    
    try:
        # 삼성전자(005930) 수급 확인
        df = stock.get_market_net_purchases_of_equities_by_ticker(today, today, "005930", "외국인")
        print("\n[Foreigner Net Buy]")
        print(df)
        
        df_inst = stock.get_market_net_purchases_of_equities_by_ticker(today, today, "005930", "기관합계")
        print("\n[Institution Net Buy]")
        print(df_inst)
        
        if df.empty and df_inst.empty:
            print("\n❌ 데이터 없음 (장중 집계 안됨?)")
        else:
            print("\n✅ 데이터 확인됨")
            
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    check_supply_data()
