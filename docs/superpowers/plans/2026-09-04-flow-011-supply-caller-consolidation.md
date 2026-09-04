# [FLOW-011] 수급 조회 호출자를 서비스의 교차검증 하나로 모은다 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「`verify=False` 로 먼저 부르고 이상징후면 `verify=True` 로 다시 부른다」를 각자 조립하던 호출자 두 곳을 `verify=True` 한 번 호출로 바꾸고, 같은 판정 헬퍼가 다섯 벌 복제되어 있던 것을 서비스의 공개 함수 하나로 모읍니다.

**Architecture:** `[FLOW-005]` 가 서비스 안의 교체 규칙을 고쳐서 `verify_with_references=True` 가 그 자체로 「이상징후일 때만 참조를 조회한다」는 정책이 되었습니다. 그러므로 호출자가 밖에서 같은 정책을 다시 조립할 이유가 없어졌습니다. 이 계획은 그 조립을 걷어내는 쪽만 다루고, 「이상징후면 자기 pykrx 경로로 빠진다」는 자체 fallback 네 자리는 **의도적으로 손대지 않습니다.** 근거는 아래 §「자체 fallback 을 옮기지 않는 이유」에 있습니다.

**Tech Stack:** Python 3.11, pandas, pykrx, pytest

**Spec:** `docs/dev-cycle/audits/AUDIT-FLOW.md` §2.1, `docs/dev-cycle/TODO.md` 의 `[FLOW-011]`

## Global Constraints

- 티어 T3. 위험 경로 `services/investor_trend_5day_service.py` 에 닿습니다 (`tier-rules.md` §2 「수급 집계」).
- 검증 명령: `source venv/bin/activate && pytest` (프론트엔드를 건드리지 않으므로 vitest 와 tsc 는 회귀 확인용으로만 돌립니다).
- 새 프레임워크나 픽스처 계층을 들이지 않습니다. 기존 `tests/**/test_*_refactor.py` 형식을 따릅니다.
- `data/` 아래 파일을 쓰기 모드로 열지 않습니다. 실측이 필요하면 읽기만 합니다.
- 서비스 모듈은 최상단에서 `engine.*` 을 임포트할 수 없습니다. `engine/collectors.py` 가 이 서비스를 임포트하므로 순환이 됩니다. 필요하면 함수 안에서 가져옵니다.

---

## 지금 상태 — 실측으로 확인한 것

### 여섯 자리 가운데 실제로 도는 것은 넷이다

`engine/collectors.py` 는 `engine/collectors/` 디렉터리와 공존하며, 파일 끝에서 `EnhancedNewsCollector` 와 `NaverFinanceCollector` 만 모듈형으로 덮어씁니다(`engine/collectors.py:2495-2510`). `KRXCollector` 는 덮어쓰지 않습니다. 그래서 실제로 실행되는 경로는 다음과 같습니다.

| 자리 | 성격 | 실행되는가 |
|---|---|---|
| `engine/screener.py:359-372` | 두 번 호출 | 실행된다 |
| `services/kr_market_stock_detail_service.py:231-267` | 두 번 호출 | 실행된다 |
| `engine/collectors.py:1695` (`KRXCollector.get_supply_data`) | 자체 fallback | 실행된다 |
| `engine/collectors/naver_pykrx_mixin.py:452` | 자체 fallback | 실행된다 (모듈형 `NaverFinanceCollector`) |
| `engine/collectors.py:2235` (레거시 `NaverFinanceCollector._get_investor_trend`) | 자체 fallback | **죽었다.** 모듈형이 덮어쓴다 |
| `engine/collectors/krx_local_data_mixin.py:1240` | 자체 fallback | **테스트에서만.** `engine.collectors.krx.KRXCollector` 를 임포트하는 실행 코드가 없다 |

죽은 두 자리를 이번에 지우지 않습니다. 레거시와 모듈형의 이중화 정리는 이 항목의 범위가 아니며, `TODO.md` 에 별도 항목으로 올립니다.

### 자체 fallback 을 옮기지 않는 이유

`TODO.md` 의 `[FLOW-011]` 둘째 체크박스는 「자체 fallback 네 자리의 동작 변화를 재고 옮길지 결정」입니다. 재어 본 결과 **옮기지 않는 것이 맞습니다.**

서비스는 개인 수급을 돌려주지 않습니다. `services/investor_trend_5day_service.py` 전체에 `individual` 도 `retail` 도 없습니다. 반면 자체 fallback 은 pykrx 의 `개인` 열을 읽어 그 값을 채웁니다.

```python
# engine/collectors/naver_pykrx_mixin.py — 서비스 경로
investor_trend.setdefault("individual", 0)      # 늘 0
# 같은 함수의 pykrx fallback 경로
investor_trend["individual"] = int(cached_supply.get("retail_buy_5d", 0))  # 실제 값
```

`engine/collectors.py:1695` 의 `SupplyData` 도 서비스 경로에서는 `retail_buy_5d=0` 이고 pykrx 경로에서만 실제 값입니다. 그러므로 fallback 을 서비스 한 번 호출로 대체하면 이상징후 종목에서 채워지던 개인 수급까지 0 이 됩니다. 리팩토링이 아니라 기능 제거입니다.

다만 이 근거는 절반만 유효하다는 점을 적어 둡니다. 정상 경로에서는 이미 개인 수급이 0 이므로, 같은 필드가 어느 경로를 거쳤느냐에 따라 0 이기도 실값이기도 합니다. 그 일관성 문제 자체는 별개이며 `[INFRA-030]` 에 담았습니다.

그리고 개인 수급이 네 자리 모두의 근거는 아닙니다. `SupplyData` 의 점수 계산은 외인과 기관만 쓰므로, 개인 수급이 실제로 사용자에게 보이는 것은 `investorTrend` 를 화면에 그리는 Naver 경로뿐입니다. 나머지 자리에는 다른 근거가 있습니다. 서비스가 통째로 실패했을 때의 복구 경로라는 점과, `engine/collectors.py:1695` 의 과거 기준일 pykrx 우선 정책입니다. 셋을 합쳐야 네 자리를 남기는 이유가 됩니다.

`engine/collectors.py:1695` 에는 이유가 하나 더 있습니다. `explicit_target_requested`(과거 날짜 명시) 일 때 서비스 결과를 아예 쓰지 않고 pykrx 로 갑니다. 이 분기는 수급 조회 중복과 무관한 별개 정책입니다.

따라서 이번 항목에서 자체 fallback 네 자리에 대해 하는 일은 **판정 헬퍼의 복제를 없애는 것뿐**입니다. 「이상징후면 pykrx 로 빠진다」는 판단 자체는 그대로 둡니다.

### 두 번 호출을 한 번으로 바꾸면 무엇이 달라지는가

CSV 에서 5거래일이 모이지 않으면 `verify=False` 는 `None` 을 돌려줍니다. `_build_trend_map` 이 `len(recent) < 5` 인 종목을 통째로 버리기 때문입니다(`services/investor_trend_5day_service.py:371`). 그러면 `_has_csv_anomaly_flags(None)` 이 `False` 이므로 둘째 호출이 일어나지 않고, 호출자는 값 없이 끝납니다. `verify=True` 한 번은 그 경우 `missing_csv` 를 거쳐 참조로 채웁니다.

「5거래일이 모이지 않는다」는 「CSV 에 종목이 아예 없다」보다 넓습니다. 신규 상장, 거래정지 후 재개, CSV 를 부분적으로만 내려받은 상태가 모두 들어갑니다.

| 상태 | 지금 | 바꾼 뒤 |
|---|---|---|
| CSV 정상 | CSV 값, 참조 조회 없음 | 같음 |
| CSV 이상징후 | 두 번 호출, 참조 값 | 한 번 호출, 참조 값 (비용 같음) |
| CSV 에 5거래일이 없음 | screener 는 점수 0, 상세 서비스는 CSV 직접 읽기 fallback | 참조로 채운 값 |

세 번째 줄이 이번 변경의 실질입니다. 리팩토링이 아니라 동작 개선입니다.

### 네트워크 호출이 늘어나는지 재어 본 결과

`TODO.md` 의 셋째 체크박스입니다. 처음에는 CSV 를 pandas 로 직접 잘라 재었으나 그 셈이 틀렸습니다. `_get_or_build_trend_map` 은 종목별로 최근 다섯 행을 취하므로 날짜 창이 종목마다 다른데, 전역 최근 5거래일로 자르면 다른 값이 나옵니다. 실제 함수를 돌려 다시 재었습니다.

**새 비용과 기존 비용을 나누어 세는 것이 중요합니다.** 이미 플래그가 붙던 종목은 예전 방식도 둘째 호출로 참조를 받아 왔으므로 비용이 달라지지 않습니다. 이번 변경이 새로 만드는 비용은 `missing_csv` 하나뿐입니다.

| target_date | 신규 (`missing_csv`) | 기존 (플래그 있음) |
|---|---|---|
| 최신 (`target_date=None`) | **0** | 20 |
| 2026-02-23 | 57 | 7 |
| 2026-01-15 (CSV 시작일 부근) | **1997** | 0 |

비용의 모양이 비대칭입니다. 자료가 정상이면 정확히 0 이고 자료가 얇아진 순간에만 전 종목으로 튑니다.

`target_date` 가 실제로 넘어가는 경로는 `python scripts/init_data.py vcp-signal <날짜>` 라는 수동 CLI 하나뿐입니다. 스케줄러와 `all` 경로는 `target_date=None` 이라 `_should_use_csv_supply_for_target_date()` 가 거짓이고 Toss 우선 경로로 갑니다.

**결론: 운영 경로에서는 증가가 없습니다.** CSV 시작일 부근을 손으로 지정하면 최대 `max_stocks`(운영 기본값 600) 회의 순차 pykrx 왕복이 붙어 한 번에 3~10분이 됩니다. 예전에는 그 자리에서 전 종목이 0 점이었으므로 정확성과 시간을 맞바꾼 것입니다. 이 위험은 `[FLOW-014]` 로 올립니다.

---

## File Structure

| 파일 | 이번 변경에서 맡는 일 |
|---|---|
| `services/investor_trend_5day_service.py` | 판정 헬퍼 `has_csv_anomaly_flags` 를 공개 함수로 내놓는다. 플래그를 만드는 곳이 판정도 내놓는 것이 옳다 |
| `engine/screener.py` | 두 번 호출을 한 번으로 바꾸고 staticmethod 복제를 지운다 |
| `services/kr_market_stock_detail_service.py` | 두 번 호출을 한 번으로 바꾸고 모듈 함수 복제를 지운다 |
| `engine/collectors.py` | staticmethod 복제를 지우고 서비스 함수를 쓴다. 자체 fallback 의 판단은 그대로 |
| `engine/collectors/krx_local_data_mixin.py` | 같음 |
| `engine/collectors/naver_pykrx_mixin.py` | 같음 |
| `tests/services/test_investor_trend_5day_service.py` | 공개 함수의 판정 경계를 검사한다 |
| `tests/engine/test_screener_supply_unified_service_refactor.py` | 두 번 호출 검사를 한 번 호출 검사로 옮긴다 |
| `tests/services/test_kr_market_stock_detail_service_refactor.py` | 같음 |

---

## Task 1: 판정 헬퍼를 서비스의 공개 함수로 내놓는다

**Files:**
- Modify: `services/investor_trend_5day_service.py` (`__all__` 과 새 함수)
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Produces: `has_csv_anomaly_flags(trend_data: dict[str, Any] | None) -> bool`. `trend_data["quality"]["csv_anomaly_flags"]` 가 비어 있지 않은 리스트일 때만 `True`. `None` 이나 dict 가 아닌 값에는 `False`.

- [ ] **Step 1: 실패하는 검사를 쓴다**

`tests/services/test_investor_trend_5day_service.py` 끝에 붙입니다.

```python
def test_has_csv_anomaly_flags_reads_the_quality_block():
    assert trend_service.has_csv_anomaly_flags(
        {"quality": {"csv_anomaly_flags": ["stale_csv"]}}
    ) is True


def test_has_csv_anomaly_flags_is_false_for_missing_or_empty_flags():
    # None 은 「CSV 에 종목이 없다」는 뜻이지 「이상징후가 있다」는 뜻이 아니다.
    assert trend_service.has_csv_anomaly_flags(None) is False
    assert trend_service.has_csv_anomaly_flags({}) is False
    assert trend_service.has_csv_anomaly_flags({"quality": {}}) is False
    assert trend_service.has_csv_anomaly_flags(
        {"quality": {"csv_anomaly_flags": []}}
    ) is False
    assert trend_service.has_csv_anomaly_flags(
        {"quality": {"csv_anomaly_flags": "stale_csv"}}
    ) is False
```

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -k has_csv_anomaly_flags -v`
Expected: FAIL with `AttributeError: module 'services.investor_trend_5day_service' has no attribute 'has_csv_anomaly_flags'`

- [ ] **Step 3: 함수를 만든다**

`get_investor_trend_5day_for_ticker` 정의 앞에 둡니다.

```python
def has_csv_anomaly_flags(trend_data: dict[str, Any] | None) -> bool:
    """반환된 페이로드에 CSV 이상징후 플래그가 붙어 있는지 판정한다.

    수급 조회 결과를 받아 자기 경로로 빠질지 결정하는 호출자를 위한 것이다.
    같은 판정이 호출자마다 복제되어 있었고, 플래그 종류가 늘 때 한 곳이라도
    빠지면 그 경로만 낡은 기준으로 동작했다.

    None 은 False 다. CSV 에 종목이 없다는 뜻이지 이상징후가 있다는 뜻이 아니다.
    """
    if not isinstance(trend_data, dict):
        return False
    quality = trend_data.get("quality")
    if not isinstance(quality, dict):
        return False
    csv_flags = quality.get("csv_anomaly_flags")
    return isinstance(csv_flags, list) and len(csv_flags) > 0
```

`__all__` 에 이름을 더합니다.

```python
__all__ = [
    "get_investor_trend_5day_for_ticker",
    "has_csv_anomaly_flags",
    "clear_investor_trend_5day_memory_cache",
]
```

- [ ] **Step 4: 통과를 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`
Expected: PASS (기존 17건 + 새 2건)

---

## Task 2: screener 의 두 번 호출을 한 번으로 바꾼다

**Files:**
- Modify: `engine/screener.py:347-355` (staticmethod 제거), `:357-380` (`_calculate_supply_score_csv`)
- Test: `tests/engine/test_screener_supply_unified_service_refactor.py`

**Interfaces:**
- Consumes: Task 1 의 `has_csv_anomaly_flags` — 이 파일에서는 **쓰지 않습니다.** 한 번 호출로 바뀌면 판정할 자리가 없어지기 때문입니다. 임포트를 새로 넣지 않습니다.

- [ ] **Step 1: 검사 셋의 겨냥점을 옮긴다**

`test_calculate_supply_score_csv_uses_unified_5day_service` 와 `test_calculate_supply_score_csv_returns_zero_when_unified_service_has_no_data` 의 단언을 바꿉니다.

```python
    assert captured["verify_with_references"] is True
```

`test_calculate_supply_score_csv_retries_reference_verify_only_on_anomaly` 는 통째로 아래로 바꿉니다. 이름도 바꿉니다. 검사할 대상이 「이상징후일 때만 다시 부른다」에서 「한 번만 부른다」로 옮겨 갔기 때문입니다.

```python
def test_calculate_supply_score_csv_calls_the_service_once(monkeypatch):
    """서비스가 이상징후일 때만 참조를 조회하므로 호출자가 두 번 부를 이유가 없다."""
    screener = object.__new__(SmartMoneyScreener)
    screener._target_datetime = datetime(2026, 2, 24)
    captured_calls: list[dict[str, object]] = []

    def _fake_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        return {
            "foreign": 333,
            "institution": 444,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
            "details": [
                {"netForeignerBuyVolume": 3, "netInstitutionBuyVolume": 4},
            ],
        }

    monkeypatch.setattr(
        "engine.screener.get_investor_trend_5day_for_ticker",
        _fake_trend,
    )

    result = SmartMoneyScreener._calculate_supply_score_csv(screener, "005930")

    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is True
    assert result["foreign_5d"] == 333
    assert result["inst_5d"] == 444
```

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/engine/test_screener_supply_unified_service_refactor.py -v`
Expected: FAIL. 세 건이 `assert False is True` 또는 `assert 2 == 1` 로 떨어진다

- [ ] **Step 3: 구현을 고친다**

`engine/screener.py` 의 `_has_csv_anomaly_flags` staticmethod 아홉 줄을 지우고, `_calculate_supply_score_csv` 를 아래로 바꿉니다.

```python
    def _calculate_supply_score_csv(self, ticker: str) -> Dict:
        """수급 점수 계산 (CSV Fallback - 단일 5일 합산 서비스 사용).

        verify_with_references=True 는 그 자체가 「이상징후일 때만 참조를
        조회한다」는 정책이다. False 로 먼저 불러 플래그를 확인하고 True 로 다시
        부르면 첫 반환값을 버리는 중복 호출이 된다. 그리고 그 방식은 CSV 에
        종목이 아예 없는 경우를 놓친다. 그때 첫 호출이 None 을 돌려주므로 플래그
        판정이 False 가 되어 둘째 호출이 일어나지 않고, 참조로 채울 수 있는
        종목에 점수 0 이 매겨진다.
        """
        trend_data = get_investor_trend_5day_for_ticker(
            ticker=ticker,
            data_dir=os.path.join(BASE_DIR, "data"),
            target_datetime=self._target_datetime,
            verify_with_references=True,
        )
        if not trend_data:
            return {"score": 0, "foreign_1d": 0, "inst_1d": 0}
        return score_supply_from_toss_trend(
            {
                "foreign": trend_data.get("foreign", 0),
                "institution": trend_data.get("institution", 0),
                "details": trend_data.get("details", []),
            }
        )
```

- [ ] **Step 4: 통과를 확인한다**

Run: `source venv/bin/activate && pytest tests/engine/test_screener_supply_unified_service_refactor.py -v`
Expected: PASS (4건)

- [ ] **Step 5: 지운 헬퍼를 부르는 곳이 남지 않았는지 확인한다**

Run: `grep -n "_has_csv_anomaly_flags" engine/screener.py`
Expected: 출력 없음

---

## Task 3: 상세 서비스의 두 번 호출을 한 번으로 바꾼다

**Files:**
- Modify: `services/kr_market_stock_detail_service.py:229-267` (`append_investor_trend_5day`), `:356-363` (모듈 함수 제거)
- Test: `tests/services/test_kr_market_stock_detail_service_refactor.py`

**Interfaces:**
- Consumes: Task 1 의 `has_csv_anomaly_flags` — 이 파일에서도 쓰지 않습니다. 한 번 호출로 바뀌면 판정할 자리가 없어집니다.

- [ ] **Step 1: 검사 둘의 겨냥점을 옮긴다**

`test_append_investor_trend_5day_prefers_unified_service_when_data_dir_provided` 의 마지막 단언을 바꿉니다.

```python
    assert captured_calls[0]["verify_with_references"] is True
```

`test_append_investor_trend_5day_retries_reference_verify_only_on_anomaly` 를 통째로 바꿉니다.

```python
def test_append_investor_trend_5day_calls_the_service_once(monkeypatch, tmp_path):
    """서비스가 이상징후일 때만 참조를 조회하므로 호출자가 두 번 부를 이유가 없다."""
    payload: dict[str, object] = {}
    calls = {"csv": 0}
    captured_calls: list[dict[str, object]] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    def _fake_get_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        return {
            "foreign": 333,
            "institution": 444,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        }

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        _fake_get_trend,
    )

    def _should_not_read_csv(_filename: str) -> pd.DataFrame:
        calls["csv"] += 1
        raise AssertionError("CSV fallback should not be called")

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=_should_not_read_csv,
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=str(tmp_path),
    )

    assert payload["investorTrend5Day"] == {"foreign": 333, "institution": 444}
    assert calls["csv"] == 0
    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is True
```

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_kr_market_stock_detail_service_refactor.py -v`
Expected: FAIL. 두 건이 떨어진다

- [ ] **Step 3: 구현을 고친다**

`append_investor_trend_5day` 안의 서비스 조회 블록을 아래로 바꿉니다. 서비스가 `None` 을 돌려주면 아래의 CSV 직접 읽기 fallback 으로 그대로 흘러갑니다.

```python
    normalized_data_dir = (data_dir or "").strip()
    if normalized_data_dir:
        try:
            # verify_with_references=True 는 그 자체가 「이상징후일 때만 참조를
            # 조회한다」는 정책이다. False 로 먼저 부르고 플래그를 본 뒤 True 로
            # 다시 부르면 첫 반환값을 버리는 중복 호출이 된다.
            trend_data = get_investor_trend_5day_for_ticker(
                ticker=normalized_ticker,
                data_dir=normalized_data_dir,
                verify_with_references=True,
            )
        except Exception as error:
            logger.debug("Unified 5-day trend service failed (%s): %s", normalized_ticker, error)
        else:
            if isinstance(trend_data, dict):
                payload["investorTrend5Day"] = {
                    "foreign": int(trend_data.get("foreign", 0) or 0),
                    "institution": int(trend_data.get("institution", 0) or 0),
                }
                return
```

그리고 `services/kr_market_stock_detail_service.py:356-363` 의 `_has_csv_anomaly_flags` 모듈 함수를 지웁니다.

- [ ] **Step 4: 통과를 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_kr_market_stock_detail_service_refactor.py -v`
Expected: PASS. `test_append_investor_trend_5day_falls_back_to_csv_when_unified_service_has_no_data` 도 그대로 통과한다 (서비스가 `None` 이면 CSV fallback 으로 간다)

- [ ] **Step 5: 지운 헬퍼를 부르는 곳이 남지 않았는지 확인한다**

Run: `grep -n "_has_csv_anomaly_flags" services/kr_market_stock_detail_service.py`
Expected: 출력 없음

---

## Task 4: 자체 fallback 세 자리의 판정 헬퍼 복제를 서비스 함수로 바꾼다

**Files:**
- Modify: `engine/collectors.py:174-181` (staticmethod 제거), `:22-24` (임포트), `:1702-1705`, `:2240`
- Modify: `engine/collectors/krx_local_data_mixin.py:484-491` (staticmethod 제거), `:22-26` (임포트), `:1245`
- Modify: `engine/collectors/naver_pykrx_mixin.py:436-444` (staticmethod 제거), `:15` (임포트), `:457`
- Test: `tests/engine/test_collectors_unified_supply_service_refactor.py` (기존 검사가 그대로 통과하는지 확인)

**Interfaces:**
- Consumes: Task 1 의 `has_csv_anomaly_flags(trend_data) -> bool`

세 파일 모두 「이상징후면 pykrx 로 빠진다」는 판단 자체는 그대로 둡니다. 서비스가 개인 수급을 돌려주지 않으므로 그 fallback 을 없애면 `individual` 과 `retail_buy_5d` 가 사라지기 때문입니다.

- [ ] **Step 1: 임포트를 더한다**

`engine/collectors.py`:

```python
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
    has_csv_anomaly_flags,
)
```

`engine/collectors/krx_local_data_mixin.py`:

```python
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
    has_csv_anomaly_flags,
)
```

`engine/collectors/naver_pykrx_mixin.py`:

```python
from services.investor_trend_5day_service import (
    get_investor_trend_5day_for_ticker,
    has_csv_anomaly_flags,
)
```

- [ ] **Step 2: staticmethod 세 벌을 지우고 호출부를 바꾼다**

`engine/collectors.py:174-181` 의 `_has_csv_anomaly_flags` staticmethod 를 지우고, 두 호출부를 바꿉니다.

```python
# :1702-1705
            if (
                not explicit_target_requested
                and isinstance(trend_data, dict)
                and not has_csv_anomaly_flags(trend_data)
            ):
# :2240
            if isinstance(trend_data, dict) and not has_csv_anomaly_flags(trend_data):
```

`engine/collectors/krx_local_data_mixin.py:484-491` 과 `engine/collectors/naver_pykrx_mixin.py:436-444` 도 같은 방식으로 지우고 각각 한 자리씩 바꿉니다.

```python
            if isinstance(trend_data, dict) and not has_csv_anomaly_flags(trend_data):
```

- [ ] **Step 3: 복제가 남지 않았는지 확인한다**

Run: `grep -rn "_has_csv_anomaly_flags" --include="*.py" . | grep -v venv`
Expected: 출력 없음

- [ ] **Step 4: 순환 임포트가 생기지 않았는지 확인한다**

`services/investor_trend_5day_service.py` 는 `engine.*` 을 최상단에서 임포트하지 않으므로 방향은 그대로 `engine → services` 입니다. 실제로 임포트되는지 확인합니다.

Run: `source venv/bin/activate && python -c "import engine.collectors; import engine.collectors.krx; import engine.collectors.naver; print('ok')"`
Expected: `ok`

- [ ] **Step 5: 관련 검사를 돌린다**

Run: `source venv/bin/activate && pytest tests/engine/test_collectors_unified_supply_service_refactor.py tests/engine/test_collectors_refactor.py tests/engine/test_krx_local_cache_helpers_refactor.py tests/engine/test_naver_collector_refactor.py -v`
Expected: PASS

---

## Task 5: 전체 검증과 정리

**Files:**
- Modify: `docs/dev-cycle/TODO.md` (`[FLOW-011]` 제거, 레거시 이중화 항목 추가)

- [ ] **Step 1: 파이썬 검사 전체를 돌린다**

Run: `source venv/bin/activate && pytest`
Expected: 실패 0건

- [ ] **Step 2: 프론트엔드 회귀를 확인한다**

`frontend/` 를 건드리지 않았으므로 회귀 확인용입니다.

Run: `cd frontend && npx vitest run`
Expected: 실패 0건

- [ ] **Step 3: 변경 규모로 티어를 재판정한다**

Run: `git diff --stat`

위험 경로 `services/investor_trend_5day_service.py` 에 닿았으므로 줄 수와 무관하게 T3 입니다. 하향하지 않습니다.

- [ ] **Step 4: `TODO.md` 에 레거시 이중화 항목을 올린다**

이번 조사에서 드러난 것이며 이 항목의 범위 밖입니다.

```markdown
### [INFRA-019] 레거시 `engine/collectors.py` 와 모듈형 `engine/collectors/` 가 공존해 죽은 코드가 남는다
- 카테고리: 인프라 | 티어: T3 | 근거: `[FLOW-011]` 사이클의 실측
- `engine/collectors.py` 가 `__path__` 를 스스로 지정해 모듈이면서 패키지처럼 동작합니다
  (`:31-34`). 파일 끝(`:2495-2510`)에서 `EnhancedNewsCollector` 와
  `NaverFinanceCollector` 만 모듈형으로 덮어쓰고 `KRXCollector` 는 덮어쓰지 않습니다.
- 그래서 같은 일을 하는 코드가 두 벌 있고 한 벌만 실행됩니다.
  `engine/collectors.py:2225-2310`(레거시 `NaverFinanceCollector._get_investor_trend`)는
  모듈형에 덮여 실행되지 않고, `engine/collectors/krx_local_data_mixin.py:1234-1300`
  (`get_supply_data`)은 `engine.collectors.krx.KRXCollector` 를 임포트하는 실행 코드가
  없어 테스트에서만 돕니다.
- 두 벌이 갈라지면 어느 쪽을 고쳤는지 알 수 없습니다. `[FLOW-011]` 이 판정 헬퍼를
  정리할 때 실행되지 않는 자리까지 함께 고쳐야 했습니다.
- [ ] 어느 구현을 남길지 정하고 나머지를 지움
- [ ] `__path__` 조작을 없앨 수 있는지 확인 (`engine/collectors/__init__.py` 로 대체)
- [ ] 지운 쪽만 검사하던 테스트를 남긴 쪽으로 옮기거나 지움
```

---

## Self-Review

**1. Spec coverage** — `TODO.md` 의 `[FLOW-011]` 체크박스 넷을 짚습니다.

| 체크박스 | 다루는 Task |
|---|---|
| 두 번 호출하는 두 자리를 한 번 호출로 바꾸고 `_has_csv_anomaly_flags` 제거 | Task 2, Task 3 |
| 자체 fallback 네 자리의 동작 변화를 재고 옮길지 결정 | 「자체 fallback 을 옮기지 않는 이유」에서 **옮기지 않는다**로 결정. Task 4 는 판정 헬퍼만 정리 |
| screener 경로의 pykrx 호출 횟수가 늘지 않는지 확인 | 「네트워크 호출이 늘어나는지 재어 본 결과」에서 실측 완료 |
| `_has_csv_anomaly_flags` 복제 다섯 벌 가운데 남은 것을 정리 | Task 1 + Task 4 |

**2. Placeholder scan** — 「적절히 처리한다」류 문구 없음. 모든 코드 단계에 실제 코드가 들어 있습니다.

**3. Type consistency** — Task 1 이 만드는 이름은 `has_csv_anomaly_flags` 이며 Task 4 가 그 이름을 그대로 씁니다. 반환 타입은 `bool` 로 일치합니다. Task 2 와 Task 3 은 이 함수를 쓰지 않으므로 임포트하지 않습니다.

**남는 위험 하나** — Task 2 와 Task 3 이 CSV 에 없는 종목에 대해 참조를 조회하게 됩니다. 오늘 자료로는 도달하지 않는 경로라 화면 QA 로 검사할 수 없습니다. `[FLOW-005]` 와 같은 상황이며, 시나리오 문서에 그 사실을 적고 단위 검사에 위임합니다.


---

## 리뷰 결과 (2026-09-04)

네 차례 리뷰를 순서대로 돌렸습니다. `/ponytail-review` → `feature-dev:code-reviewer` → `/review`(security·performance specialist) → codex 적대적 패스입니다.

### 코드로 반영한 것

| 출처 | 지적 | 반영 |
|---|---|---|
| ponytail-review | 같은 설명이 서비스 독스트링과 두 호출자에 세 벌 있다 | 호출자 쪽 둘을 줄이거나 지움 (-9줄) |
| code-reviewer | `missing_csv` 의 범위가 「CSV 에 종목이 없다」보다 넓다 | 독스트링과 계획 문서의 서술을 고침 |
| code-reviewer | 비용 수치가 잘못된 셈에서 나왔고 잘못된 자리에 붙어 있다 | 실제 함수를 돌려 다시 재고 신규·기존 비용을 나눔 |
| code-reviewer | 상세 서비스의 debug 로그가 사라져 참조 출처를 알 수 없다 | 플래그 목록과 채택 출처를 함께 남기도록 복구 |
| security | `_safe_int` 가 `OverflowError` 를 잡지 않아 신뢰 경계의 검증 장치가 스스로 터진다 | `except` 에 `OverflowError` 추가 + 회귀 검사 |
| codex | 자체 fallback 이 기대는 「`verify=False` 면 참조를 조회하지 않는다」가 서비스 검사로 고정되어 있지 않다 | `test_verify_false_keeps_anomalous_csv_without_touching_references` 추가 |
| codex | fallback 을 남기는 근거가 개인 수급 하나로는 과하다 | 서비스 장애 복구와 과거 기준일 pykrx 우선 정책을 근거에 함께 적음 |

`_safe_int` 의 결함은 실증했습니다. `json.loads('{"v": Infinity}')` 와 `json.loads('{"v": 1e400}')` 가 모두 `inf` 를 돌려주고 `int(float("inf"))` 는 `OverflowError` 를 던집니다. `NaN` 은 `ValueError` 라 이미 잡히고 있었습니다. codex 가 제안한 검사도 회귀 포착력을 실증했습니다. `_resolve_best_payload` 의 조건에서 `verify_with_references and` 를 런타임으로 떼어 내면 참조 조회가 두 번 일어나 검사의 `AssertionError` 가 발동합니다.

### 백로그로 올린 것

- `[FLOW-014]` 자료가 얇은 기준일에서 수급 조회가 종목 수만큼 pykrx 왕복을 낸다 — 이번 변경이 만든 비용. 최신 창에서 Toss 까지 부르면 두 배가 되는 경우와, 요청 처리 경로에 시간 예산이 필요하다는 지적을 함께 담음
- `[INFRA-030]` 레거시 `engine/collectors.py` 와 모듈형 `engine/collectors/` 의 이중화 — 개인 수급이 경로에 따라 0 이기도 실값이기도 한 일관성 문제를 함께 담음
- `[INFRA-031]` 백로그에 같은 ID 를 가진 항목이 여덟 개 있다
- `[FLOW-012]` 에 덧붙임 — `missing_csv` 로 채운 값은 견줄 CSV 가 없어 그 항목의 완화책이 원리상 통하지 않는다. 참조 단독 값에 표식을 둘지와 `_grade_from_score` 경로에 상한을 둘지가 새 체크박스

### 반영하지 않은 것과 그 이유

- **참조 캐시 키에 `data_dir` 이 빠졌다** (performance, 확신도 7) — **보고자가 철회했습니다.** `_reference_cache_token`(`:147-164`)은 `data_dir` 을 pykrx 최신 영업일을 찾는 스냅숏 위치로만 쓰고 `%Y%m%d` 문자열을 돌려줍니다. 실질 키는 `(source, ticker, 날짜)` 이며, 참조 자료는 외부 자료라 `data_dir` 에 의존하지 않습니다. 근거가 하나 더 있습니다. 그 최신 영업일을 담는 `_PYKRX_MARKET_DATE_CACHE`(`:58`)가 오늘 날짜 하나만 키로 삼는 모듈 전역 사전이라, 어느 `data_dir` 이 먼저 값을 채우든 그 뒤로는 프로세스 전체가 같은 날짜를 씁니다. 토큰이 이미 전역입니다. 검사 격리도 막혀 있습니다. `tmp_path` 로 서로 다른 디렉터리를 쓰는 참조 검사들이 매번 `clear_investor_trend_5day_memory_cache()` 를 먼저 부릅니다.
- **`naver_pykrx_mixin.py` 의 async 안 동기 호출** (performance, 확신도 9) — 이번 변경이 만든 것이 아니고 그 자리는 `verify=False` 그대로입니다. 유일한 호출자가 이 코루틴만을 위해 이벤트 루프를 새로 만들고 `gather` 도 없어 막을 다른 태스크가 없습니다.
- **참조 조회 횟수를 세는 검사** (code-reviewer 제안) — `test_get_investor_trend_5day_for_ticker_skips_reference_when_csv_is_normal` 이 참조 조회 함수를 던지는 함수로 바꿔 두어 이미 더 강하게 고정합니다. 종목 수만 늘리면 같은 불변식을 다시 검사할 뿐입니다. `[FLOW-014]` 체크박스로 남겼습니다.
- **`ticker` 가 검증 없이 파일 경로가 된다** (security, 확신도 4) — 도달할 수 없습니다. Flask 의 기본 변환기가 `/` 를 받지 않고 `append_investor_trend_5day` 는 Toss 가 이름을 돌려준 뒤에만 불립니다. 같은 형태가 이미 다른 파일에 있어 이번 변경이 만든 것도 아닙니다. `[FLOW-012]` 에 관찰로만 기록했습니다.

### 검증

pytest 1624 통과 2 스킵, vitest 237 통과(37 파일).
