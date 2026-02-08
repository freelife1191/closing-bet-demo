# 리팩토링 마이그레이션 가이드

## 개요

이 가이드는 기존 코드를 새로운 리팩토링된 모듈로 마이그레이션하는 방법을 설명합니다.

## 1. Constants 사용법

### Before (매직 넘버)
```python
if stock.trading_value >= 1_000_000_000_000:  # 1조
    return 3
elif stock.trading_value >= 500_000_000_000:   # 5000억
    return 2
```

### After (Constants 사용)
```python
from engine.constants import TRADING_VALUES

if stock.trading_value >= TRADING_VALUES.S_GRADE:
    return 3
elif stock.trading_value >= TRADING_VALUES.A_GRADE:
    return 2
```

## 2. Pandas Utils 사용법

### Before (중복된 NaN 처리)
```python
entry_price = row.get('entry_price')
if pd.isna(entry_price):
    entry_price = None

return_pct = row.get('return_pct')
if pd.isna(return_pct):
    return_pct = None
```

### After (pandas_utils 사용)
```python
from engine.pandas_utils import safe_float

entry_price = safe_float(row.get('entry_price'))
return_pct = safe_float(row.get('return_pct'))
```

## 3. LLM Retry Decorator 사용법

### Before (중복된 재시도 로직)
```python
max_retries = 5
for attempt in range(max_retries):
    try:
        resp = await asyncio.to_thread(call_gemini)
        break
    except Exception as e:
        if "429" in str(e) and attempt < max_retries - 1:
            wait = (2 ** attempt) * 2
            await asyncio.sleep(wait)
            continue
        raise e
```

### After (decorator 사용)
```python
from engine.llm_utils import async_retry_with_backoff

@async_retry_with_backoff(max_retries=5)
async def call_gemini():
    return await asyncio.to_thread(original_call)
```

## 4. Error Handler 사용법

### Before (반복된 try-except)
```python
try:
    df = pd.read_csv(filepath)
except Exception as e:
    logger.error(f"Failed to load: {e}")
    df = pd.DataFrame()
```

### After (decorator 사용)
```python
from engine.error_handler import handle_data_error

@handle_data_error(default_return=pd.DataFrame())
def load_data(filepath):
    return pd.read_csv(filepath)
```

## 5. DataSource Strategy 사용법

### Before (직접 FDR/pykrx/yfinance 호출)
```python
# FDR 시도
try:
    import FinanceDataReader as fdr
    df = fdr.DataReader(symbol, start, end)
except:
    # pykrx 시도
    try:
        from pykrx import stock
        df = stock.get_index_ohlcv_by_date(start, end, symbol)
    except:
        # yfinance 시도
        import yfinance as yf
        df = yf.download(symbol, start=start, end=end)
```

### After (DataSourceManager 사용)
```python
from engine.data_sources import DataSourceManager

manager = DataSourceManager()
df = manager.fetch_index_data(symbol, start_date, end_date)
```

## 6. Phase Classes 사용법

### Before (generator.py의 거대한 메서드)
```python
async def generate(self, target_date, markets, top_n):
    # 230+ lines of mixed logic...
    for market in markets:
        candidates = await self._collector.get_top_gainers(...)
        for stock in candidates:
            # Phase 1 logic mixed in...
            base_data = await self._analyze_base(stock)
            # More mixed logic...
```

### After (Phase classes 사용)
```python
from engine.phases import (
    Phase1Analyzer,
    Phase2NewsCollector,
    Phase3LLMAnalyzer,
    Phase4SignalFinalizer,
    SignalGenerationPipeline
)

# Phase 클래스 초기화
phase1 = Phase1Analyzer(self._collector, self.scorer)
phase2 = Phase2NewsCollector(self._news)
phase3 = Phase3LLMAnalyzer(self.llm_analyzer)
phase4 = Phase4SignalFinalizer(
    self.scorer,
    self.position_sizer,
    self._naver
)

# 파이프라인 실행
pipeline = SignalGenerationPipeline(phase1, phase2, phase3, phase4)
signals = await pipeline.execute(candidates, market_status, target_date)
```

## 7. Import Migration 체크리스트

### 새로 추가할 Imports
```python
from engine.constants import (
    TRADING_VALUES, VCP_THRESHOLDS, SCORING,
    VOLUME, PRICE_CHANGE, FX, MARKET_GATE
)
from engine.pandas_utils import (
    safe_value, safe_int, safe_float, safe_str,
    load_csv_file, load_json_file,
    filter_by_date, filter_by_ticker,
    merge_realtime_prices
)
from engine.llm_utils import (
    async_retry_with_backoff,
    process_batch_with_concurrency,
    extract_json_from_response
)
from engine.exceptions import (
    MarketDataError, LLMAnalysisError,
    is_retryable_error, log_error
)
from engine.error_handler import (
    handle_data_error, handle_llm_error,
    safe_execute, build_error_response
)
from engine.data_sources import (
    DataSourceManager, GlobalDataFetcher,
    FDRSource, PykrxSource, YFinanceSource
)
from engine.phases import (
    Phase1Analyzer, Phase2NewsCollector,
    Phase3LLMAnalyzer, Phase4SignalFinalizer,
    SignalGenerationPipeline
)
```

## 8. 단계적 마이그레이션 순서

### Phase 1: 안전한 유틸리티 먼저 적용
1. `constants.py` - 매직 넘버 대체
2. `pandas_utils.py` - NaN 처리 대체
3. `exceptions.py` - 예외 타입 사용

### Phase 2: 에러 핸들링 개선
1. `error_handler.py` - 에러 핸들러 decorator 적용
2. 데이터 로딩 함수에 `@handle_data_error` 적용

### Phase 3: LLM 로직 개선
1. `llm_utils.py` - retry decorator 적용
2. 배치 처리에 `process_batch_with_concurrency` 적용

### Phase 4: 데이터 소스 추상화
1. `data_sources.py` - DataSourceManager 사용
2. `market_gate.py` - data_sources로 리팩토링

### Phase 5: Phase 클래스 도입
1. `phases.py` - Phase 클래스로 로직 분리
2. `generator.py` - Pipeline으로 교체

## 9. 테스트 확인 사항

각 마이그레이션 후 다음을 확인하세요:

1. [ ] 단위 테스트 통과 (`pytest tests/`)
2. [ ] API 엔드포인트 응답 확인
3. [ ] 로그에 에러 없는지 확인
4. [ ] 기존 기능 동작 확인

## 10. 롤백 계획

문제 발생 시:
```bash
# Git으로 롤백
git checkout HEAD -- engine/market_gate.py
git checkout HEAD -- engine/generator.py

# 또는 새 모듈 삭제
rm engine/constants.py
rm engine/pandas_utils.py
# ... etc
```
