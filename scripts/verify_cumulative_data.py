
import requests
import json
import sys

def verify_data():
    try:
        url = "http://localhost:5501/api/kr/closing-bet/cumulative"
        print(f"Fetching from {url}...")
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return False
            
        data = response.json()
        
        # 1. KPI Validation
        kpi = data.get('kpi', {})
        print("\n[KPI Data]")
        print(json.dumps(kpi, indent=2, ensure_ascii=False))
        
        if kpi['totalSignals'] == 0:
            print("⚠️ Warning: No signals found. Check if 'jongga_v2_results_*.json' exists in data/.")
        else:
            print(f"✅ Total Signals: {kpi['totalSignals']}")
            
        if kpi['profitFactor'] == 0.0 and kpi['totalRoi'] != 0:
             # It's possible to be 0 if gross loss is huge or logic err? 
             # Wait, if gross_loss is 0, we set it to gross_profit.
             print(f"ℹ️ Profit Factor: {kpi['profitFactor']}")

        # 2. Trades Validation
        trades = data.get('trades', [])
        print(f"\n[Trades Data] Count: {len(trades)}")
        
        if not trades:
            print("❌ No trades returned.")
            return False
            
        # Check first trade for structure
        first_trade = trades[0]
        required_keys = ['id', 'date', 'code', 'entry', 'outcome', 'roi', 'priceTrail']
        missing_keys = [k for k in required_keys if k not in first_trade]
        
        if missing_keys:
            print(f"❌ Missing keys in trade object: {missing_keys}")
            return False
            
        print("✅ Trade Object Structure Valid")
        print(f"   Sample: {first_trade['name']} ({first_trade['code']}) - ROI: {first_trade['roi']}%")
        
        # 3. Check for specific Mock Data artifacts
        # Mock data had "삼표시멘트" with ID 1
        mock_names = ["삼표시멘트", "HLB", "알테오젠", "에코프로비엠"]
        
        real_names = [t['name'] for t in trades]
        print(f"   Real Names: {real_names[:5]}...")
        
        # Mock check is a bit loose because real data might actually contain these stocks.
        # But ID structure is different. Mock ID was int, Real ID is string "code-date"
        if isinstance(first_trade['id'], int):
             print(f"❌ Error: Trade ID is integer ({first_trade['id']}). Likely Mock Data.")
             return False
        
        print("✅ Trade IDs are strings (Real Data confirmed)")
        
        return True

    except Exception as e:
        print(f"❌ Script Error: {e}")
        return False

if __name__ == "__main__":
    success = verify_data()
    sys.exit(0 if success else 1)
