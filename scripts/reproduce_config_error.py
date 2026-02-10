
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.generator import SignalGenerator

def test_config_init():
    print("Testing SignalGenerator initialization without arguments...")
    try:
        generator = SignalGenerator() # Should use default config
        if generator.config is None:
            print("FAIL: generator.config is None")
        else:
            print(f"SUCCESS: generator.config type: {type(generator.config)}")
            print(f"USE_TOSS_DATA: {getattr(generator.config, 'USE_TOSS_DATA', 'Not Found')}")
            
    except Exception as e:
        print(f"ERROR during initialization: {e}")

if __name__ == "__main__":
    test_config_init()
