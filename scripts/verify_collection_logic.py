#!/usr/bin/env python3
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.init_data import create_signals_log, create_jongga_v2_latest
from engine.config import app_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_collection():
    print("=== Verifying VCP Signal Collection (SmartMoneyScreener) ===")
    try:
        # Run VCP analysis (run_ai=False to skips AI part for speed)
        # Assuming data files exist or will be skipped if missing
        result_vcp = create_signals_log(run_ai=False)
        print(f"VCP Analysis Result: {result_vcp}")
    except Exception as e:
        print(f"❌ VCP Analysis Failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Verifying Closing Bet Collection (Jongga V2) ===")
    try:
        # Run Closing Bet analysis
        result_jongga = create_jongga_v2_latest()
        print(f"Closing Bet Analysis Result: {result_jongga}")
    except Exception as e:
        print(f"❌ Closing Bet Analysis Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_collection()
