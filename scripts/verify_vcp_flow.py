import sys
import os
import logging
from datetime import datetime

# Setup paths
sys.path.append(os.getcwd())

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VCP_VERIFY")

# Apply Pykrx Logging Fix (Crucial)
class PykrxFilter(logging.Filter):
    def filter(self, record):
        if 'pykrx' in record.pathname and 'util.py' in record.pathname:
            return False
        return True
logging.getLogger().addFilter(PykrxFilter())

try:
    from scripts import init_data
    from engine.config import app_config
    
    logger.info("1. Starting VCP Flow Verification...")
    
    # 1. Skip heavy data collection if possible, strictly test Filtering & AI
    # But user complained about data processing.
    # Let's try to run with target_date='20260131' (Saturday? No, 2026-01-30 Friday)
    # Today is 2026-02-02.
    target_date = datetime.now().strftime('%Y%m%d')
    logger.info(f"Target Date: {target_date}")
    
    # 2. Run Screener Logic
    # We call create_daily_prices first? It might take long.
    # Let's check if we can just run create_signals_log if data exists.
    # But if data is stale, we get 0 signals.
    # Let's try running create_signals_log directly first.
    
    logger.info("2. Running create_signals_log (Dry Run)...")
    # Assuming daily prices might satisfy some locally.
    
    # Force run_ai=True
    result = init_data.create_signals_log(target_date=target_date, run_ai=True)
    
    if result is None:
        logger.error("create_signals_log returned None!")
    elif isinstance(result, list) and not result: # Empty list
         logger.warning("No signals detected.")
    elif hasattr(result, 'empty') and result.empty: # Empty DataFrame
         logger.warning("No signals detected (Empty DataFrame).")
    else:
        logger.info(f"SUCCESS: Signals detected! Count: {len(result)}")
        logger.info(f"Sample: {result.iloc[0] if hasattr(result, 'iloc') else result[0]}")

except Exception as e:
    logger.error(f"CRITICAL FAILURE: {e}")
    import traceback
    traceback.print_exc()
