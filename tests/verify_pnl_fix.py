import sys
import os
import time

# Add project root to path
sys.path.append(os.getcwd())

from services.paper_trading import paper_trading

def test_pnl_fix():
    print(">>> Testing Portfolio P&L Fixes")
    
    # 1. Reset Account
    paper_trading.reset_account()
    print("[1] Account Reset. Balance: 100,000,000")
    
    # 2. Buy Stock (10 shares @ 10,000)
    ticker = '005930'
    paper_trading.buy_stock(ticker, 'Samsung', 10000, 10)
    print(f"[2] Bought 10 shares of {ticker} @ 10,000")
    
    # 3. Simulate Deposit (50,000,000)
    res = paper_trading.deposit_cash(50000000)
    print(f"[3] Deposit 50,000,000: {res['message']}")
    
    # [Fix] Clear cache to ensure we test P&L Logic without market price fluctuations
    # This forces current_price = buy_price (10,000), so profit should be 0
    with paper_trading.cache_lock:
        paper_trading.price_cache.clear()
    print("[3.5] Cleared Price Cache for deterministic P&L check")

    # 4. Check Portfolio
    portfolio = paper_trading.get_portfolio_valuation()
    holdings = portfolio['holdings']
    total_asset = portfolio['total_asset_value']
    total_profit = portfolio['total_profit']
    total_principal = portfolio.get('total_principal', 0)
    
    print(f"\n[4] Portfolio State:")
    print(f"    - Total Asset: {total_asset:,} (Expect ~150,000,000)")
    print(f"    - Total Principal: {total_principal:,} (Expect 150,000,000)")
    print(f"    - Total Profit: {total_profit:,} (Expect 0)")
    
    # Verification
    if total_principal != 150000000:
        print("!!! FAIL: Total Principal is incorrect")
    elif total_profit != 0:
        print("!!! FAIL: Total Profit should be 0 immediately after deposit (assuming no price change)")
    else:
        print(">>> SUCCESS: Deposit correctly handled in P&L")

    # 5. Simulate Price Fallback (Stale Price)
    # Clear cache to force fallback
    with paper_trading.cache_lock:
        paper_trading.price_cache.clear()
        
    print("\n[5] Cleared Price Cache to test Stale Flag")
    portfolio_stale = paper_trading.get_portfolio_valuation()
    holding = portfolio_stale['holdings'][0]
    
    print(f"    - Holding {holding['ticker']} Stale Status: {holding.get('is_stale')}")
    
    if holding.get('is_stale') is True:
        print(">>> SUCCESS: Stale price flag detected")
    else:
        print("!!! FAIL: Stale flag missing")

if __name__ == "__main__":
    test_pnl_fix()
