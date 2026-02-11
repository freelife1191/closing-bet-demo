import json
import numpy as np
from datetime import date, datetime

class NumpyEncoder(json.JSONEncoder):
    """
    Numpy 데이터 타입과 Date/Time 객체를 JSON으로 직렬화하기 위한 인코더
    """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.bool_,)):
            return bool(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(NumpyEncoder, self).default(obj)
