# Closing-Bet-Demo 리팩토링 계획

**작성일**: 2026-02-11
**상태**: 진행 중

---

## 1. 코드 분석 요약

### 1.1 주요 지표

| 파일 | 라인 수 | 클래스 수 | 문제점 | 우선순위 |
|------|---------|-----------|--------|----------|
| `market_gate.py` | 1,036 | 2 | `_get_global_data()` 397줄, `analyze()` 123줄 | **CRITICAL** |
| `generator.py` | 850 | 1 | `SignalGenerator` 508줄, `_create_final_signal()` 59줄 | **HIGH** |
| `collectors.py` | 1,005 | 3 | `KRXCollector` 431줄, 중복 로직 | **HIGH** |
| `data_sources.py` | 786 | 6 | `fetch_stock_price()` 120줄 | **MEDIUM** |
| `scorer.py` | 406 | 1 | `determine_grade()` 111줄 | **MEDIUM** |

### 1.2 발견된 Code Smells

#### Critical (즉시 조치 필요)

1. **Long Method** (`market_gate.py::_get_global_data()`)
   - 397줄, 복잡도: 매우 높음
   - FDR → pykrx → yfinance 폴백 로직 중복
   - 시계열 데이터 처리, NaN 처리, 타임존 처리가 혼재

2. **SRP 위반** (`market_gate.py::MarketGate`)
   - 데이터 수집 + 기술적 분석 + 시장 상태 판단을 한 클래스에서 처리
   - 1,004줄짜리 단일 클래스

3. **Magic Numbers** (전역)
   - 환율 임계값 (1420, 1450, 1480)이 코드에 하드코딩
   - 거래량 임계값, 점수 컷오프 등分散

#### High (조기 조치 권장)

4. **Duplicate Code** (`collectors.py`)
   - `_load_from_local_csv()` 122줄: CSV 로딩 로직 중복
   - NaN 처리가 여러 곳에서 반복

5. **Long Method** (`generator.py::_create_final_signal()`)
   - 59줄, 점수 계산 → 등급 판정 → 포지션 계산 → Signal 생성

6. **Tight Coupling** (`generator.py`)
   - SignalGenerator가 KRXCollector, NewsCollector, LLMAnalyzer, Scorer, PositionSizer를 직접 생성

#### Medium

7. **Primitive Obsession** (전역)
   - 환율, 점수, 등급을 원시값으로 처리
   - Value Object 패턴 적용 필요

8. **Feature Envy** (`scorer.py::determine_grade()`)
   - Stock, Score, Supply 등 다른 객체 데이터를 과도하게 사용

---

## 2. 리팩토링 전략

### 2.1 Phase 1: `market_gate.py` 리팩토링 (CRITICAL)

**목표**: 1,036줄 → 500줄 이하로 축소

#### 2.1.1 `GlobalDataFetcher` 클래스 추출 (이미 존재 활용)

- 이미 `engine/data_sources.py`에 `GlobalDataFetcher`가 존재
- `market_gate.py`의 `_get_global_data()`를 이것으로 대체

**기대 효과**:
- 397줄 → 50줄 이상 축소
- 데이터 소스 패턴 일관성 확보

#### 2.1.2 `MarketAnalyzer` 클래스 분리

```python
# Before: MarketGate 하나가 모든 것을 담당
class MarketGate:
    def analyze(self):
        # 1. 데이터 로드
        # 2. 기술적 분석
        # 3. 시장 상태 판단
        # 4. 결과 반환

# After: 책임 분리
class MarketDataProvider:      # 데이터 로드 담당
class TechnicalAnalyzer:       # 기술적 지표 계산
class MarketStatusEvaluator:   # 시장 상태 판정
class MarketGate:              # Orchestrator (Facade)
```

#### 2.1.3 `SectorAnalyzer` 클래스 추출

- `_get_sector_data()`를 별도 클래스로 분리
- 섹터 ETF 데이터 수집 및 섹터 강약 분석 담당

### 2.2 Phase 2: `generator.py` 리팩토링 (HIGH)

**목표**: 850줄 → 500줄 이하로 축소

#### 2.2.1 `phases.py` 적용 (이미 존재)

- 이미 `engine/phases.py`에 4-phase 파이프라인이 존재
- `SignalGenerator`가 이를 활용하도록 수정

```python
# phases.py에 이미 정의됨
class Phase1Analyzer:    # Base analysis
class Phase2NewsCollector:  # News collection
class Phase3LLMAnalyzer:    # Batch LLM analysis
class Phase4SignalFinalizer:  # Signal creation
class SignalGenerationPipeline:  # Orchestrator
```

#### 2.2.2 의존성 주입 적용

```python
# Before: 직접 생성
class SignalGenerator:
    def __init__(self):
        self.scorer = Scorer()
        self.llm_analyzer = LLMAnalyzer()
        # ...

# After: 주입 받기
class SignalGenerator:
    def __init__(
        self,
        scorer: Scorer,
        llm_analyzer: LLMAnalyzer,
        collector: BaseCollector,
        # ...
    ):
        self.scorer = scorer
        self.llm_analyzer = llm_analyzer
        # ...
```

### 2.3 Phase 3: 나머지 파일 리팩토링 (MEDIUM)

#### 2.3.1 `collectors.py` 리팩토링

- CSV 로딩 로직을 `pandas_utils.py`로 이동
- NaN 처리 통합

#### 2.3.2 `scorer.py` 리팩토링

- `determine_grade()` 메서드를 GradeCalculator 클래스로 분리
- 등급별 로직을 전략 패턴으로 적용

---

## 3. TDD 접근 방식

### 3.1 테스트 우선 작성

각 리팩토링 단계마다:
1. **기존 동작을 캡처하는 테스트 작성**
2. **테스트가 통과하는지 확인**
3. **리팩토링 수행**
4. **테스트가 여전히 통과하는지 확인**

### 3.2 테스트 커버리지 목표

- **단위 테스트**: 80% 이상
- **통합 테스트**: 핵심 흐름 커버
- **회귀 테스트**: 기존 기능 보호

---

## 4. 일정 계획

| 단계 | 작업 | 예상 시간 | 우선순위 |
|------|------|-----------|----------|
| 1 | `market_gate.py` 테스트 작성 | 2시간 | CRITICAL |
| 2 | `market_gate.py` 리팩토링 (GlobalDataFetcher 적용) | 3시간 | CRITICAL |
| 3 | `market_gate.py` 클래스 분리 | 4시간 | CRITICAL |
| 4 | `generator.py` 테스트 작성 | 2시간 | HIGH |
| 5 | `generator.py` phases.py 적용 | 3시간 | HIGH |
| 6 | `generator.py` 의존성 주입 | 2시간 | HIGH |
| 7 | 나머지 파일 리팩토링 | 4시간 | MEDIUM |
| 8 | 전체 테스트 및 검증 | 2시간 | HIGH |

**총 예상 시간**: 약 22시간

---

## 5. 성공 지표

### 5.1 코드 품질 메트릭

| 메트릭 | Before | After | 목표 |
|--------|--------|-------|------|
| `market_gate.py` 라인 수 | 1,036 | <500 | -50% |
| `generator.py` 라인 수 | 850 | <500 | -40% |
| 최대 메서드 길이 | 397 | <50 | -87% |
| 최대 클래스 크기 | 1,004 | <300 | -70% |
| 테스트 커버리지 | ~30% | >80% | +50% |
| Cyclomatic 복잡도 | >25 | <10 | -60% |

### 5.2 SOLID 준수

- [ ] **SRP**: 각 클래스가 단일 책임만 담당
- [ ] **OCP**: 확장에는 열려있고, 수정에는 닫혀있음
- [ ] **LSP**: 상속 관계가 올바르게 설계됨
- [ ] **ISP**: 인터페이스가 적절히 분리됨
- [ ] **DIP**: 고수준 모듈이 저수준 모듈에 의존하지 않음

---

## 6. 리스크 관리

### 6.1 잠재적 리스크

1. **기능 회귀**: 리팩토링 중 기존 기능이 깨질 수 있음
   - **완화책**: TDD로 리팩토링 전 테스트 작성

2. **API 변경**: 공개 인터페이스가 변경될 수 있음
   - **완화책**: Adapter 패턴으로 호환성 유지

3. **성능 저하**: 추상화 계층이 추가될 수 있음
   - **완화책**: 벤치마크 테스트로 성능 모니터링

### 6.2 롤백 계획

- 각 Phase마다 git commit으로 체크포인트 생성
- 문제 발생 시 즉시 이전 단계로 롤백

---

## 7. 참고 자료

- `docs/reference/PART_01.md` - 전체 아키텍처
- `docs/reference/PART_07.md` - Market Gate 로직
- `engine/constants.py` - 상수 정의 (이미 리팩토링 완료)
- `engine/phases.py` - 시그널 생성 파이프라인 (이미 리팩토링 완료)
- `engine/data_sources.py` - 데이터 소스 패턴 (이미 리팩토링 완료)
