
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

try:
    from app import create_app
    from services.paper_trading import paper_trading
except ImportError:
    # Fallback setup if partial env
    from flask import Flask
    app = Flask(__name__)

# Try full app setup
try:
    # Mocking or simplified app setup if full create_app is complex
    # But usually we want to import the real one
    from flask_app import app # Assuming flask_app.py has the 'app' instance
except ImportError:
     print("Could not import app from flask_app.py, constructing minimal context")
     # Manual setup logic if needed, but preferable to use existing app
     pass

# To be safe, let's use the PaperTradingService directly for SETUP and then call the route function logic
# Or rely on the fact that we can call get_portfolio_data() if we set up a request context

def test_api():
    print("Initializing App Context...")
    # Setup dummy holdings if empty
    paper_trading.reset_account()
    paper_trading.buy_stock('005380', '현대차', 491500, 100)
    paper_trading.buy_stock('45226K', '한화갤러리아우', 9970, 200)
    paper_trading.buy_stock('452260', '한화갤러리아', 1907, 200)

    with app.test_client() as client:
        print("Calling /api/portfolio endpoint...")
        response = client.get('/api/portfolio')
        
        if response.status_code == 200:
            data = response.get_json()
            print("\nResponse Status: 200 OK")
            print("Debug Error:", data.get('debug_error'))
            
            holdings = data.get('holdings', [])
            print(f"\nHoldings: {len(holdings)}")
            for h in holdings:
                print(f"[{h['ticker']}] {h['name']} | Avg: {h['avg_price']} | Cur: {h['current_price']} | Profit: {h['profit_rate']}%")
        else:
            print(f"Error {response.status_code}: {response.data.decode('utf-8')}")

if __name__ == "__main__":
    test_api()
