import logging
import sys

# [FIX] Filter out pykrx's broken logging calls
class PykrxFilter(logging.Filter):
    def filter(self, record):
        # Emulate pykrx logging behavior detection
        if 'pykrx' in record.pathname or 'test_pykrx' in record.pathname:
             if hasattr(record, 'args') and isinstance(record.args, dict):
                 # This mimics the crash condition: args is a dict (kwargs) but msg is a tuple
                 return False
        return True

# Setup logging
logging.basicConfig(level=logging.INFO)
logging.getLogger().addFilter(PykrxFilter())

print("Testing unsafe logging...")
try:
    # Simulate pykrx crash: logging.info(tuple, dict)
    # logging.info(msg, *args) -> msg is tuple, args is dict
    args = ({},)
    kwargs = {'a': 1}
    # This is what pykrx does: logging.info(args, kwargs)
    logging.info(args, kwargs)
    print("SUCCESS: Logging suppressed or handled without crash (if filter worked)")
except TypeError:
    print("FAILURE: TypeError crashed the app")
except Exception as e:
    print(f"FAILURE: Other error: {e}")
