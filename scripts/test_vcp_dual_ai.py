#!/usr/bin/env python3
import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import app_config
from engine.vcp_ai_analyzer import get_vcp_analyzer

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Force logging to stdout
sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.DEBUG)
logging.getLogger().addHandler(sh)

async def test_perplexity_integration():
    logger.info("🧪 Starting VCP Perplexity Integration Test")
    
    # 1. Configuration Check
    logger.info("1. Checking Configuration...")
    logger.info(f"   VCP_SECOND_PROVIDER: {app_config.VCP_SECOND_PROVIDER}")
    logger.info(f"   PERPLEXITY_API_KEY: {'[SET]' if app_config.PERPLEXITY_API_KEY else '[MISSING]'}")
    logger.info(f"   VCP_PERPLEXITY_MODEL: {app_config.VCP_PERPLEXITY_MODEL}")
    
    if app_config.VCP_SECOND_PROVIDER != 'perplexity':
        logger.warning("⚠️ VCP_SECOND_PROVIDER is not set to 'perplexity'. Forcing it for this test.")
        app_config.VCP_SECOND_PROVIDER = 'perplexity'
        
    if not app_config.PERPLEXITY_API_KEY:
        logger.error("❌ PERPLEXITY_API_KEY is missing. Cannot proceed with real API test.")
        return

    # 2. Analyzer Initialization
    logger.info("\n2. Initializing VCP Analyzer...")
    analyzer = get_vcp_analyzer()
    available_providers = analyzer.get_available_providers()
    logger.info(f"   Available Providers: {available_providers}")
    
    if 'perplexity' not in available_providers:
        # Re-initialize manually if singleton was already created without perplexity
        logger.info("   Re-initializing analyzer to ensure Perplexity client is created...")
        # Hack to force re-init (in real app, restart handles this)
        global _vcp_analyzer
        _vcp_analyzer = None
        # Ensure 'perplexity' is in provider list for init
        analyzer.providers.append('perplexity')
        # Re-create client manually if needed
        from openai import OpenAI
        analyzer.perplexity_client = OpenAI(
            api_key=app_config.PERPLEXITY_API_KEY, 
            base_url="https://api.perplexity.ai"
        )
        logger.info("   Perplexity client manually initialized for test.")

    # 3. Test Analysis
    logger.info("\n3. Testing Analysis (Real API Call)...")
    
    dummy_stock = {
        'current_price': 10000,
        'vcp_score': 9.5,
        'contraction_ratio': 0.5,
        'foreign_5d': 100000,
        'inst_5d': 50000
    }
    stock_name = "테스트전자"
    
    logger.info(f"   Analyzing {stock_name}...")
    try:
        result = await analyzer.analyze_stock(stock_name, dummy_stock)
        
        logger.info("\n4. Analysis Result Code:")
        import json
        logger.info(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result.get('perplexity_recommendation'):
            logger.info("\n✅ SUCCESS: Perplexity recommendation received!")
            rec = result['perplexity_recommendation']
            logger.info(f"   Action: {rec.get('action')}")
            logger.info(f"   Confidence: {rec.get('confidence')}")
            logger.info(f"   Reason: {rec.get('reason')}")
        else:
            logger.error("\n❌ FAILED: Perplexity recommendation is missing.")
            
    except Exception as e:
        logger.error(f"\n❌ ERROR during analysis: {e}")

if __name__ == "__main__":
    asyncio.run(test_perplexity_integration())
