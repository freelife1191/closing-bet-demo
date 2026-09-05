# [FLOW-013] SQLite 캐시에서 되살린 수급 항목의 5일치 불변식 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SQLite 스냅숏에서 되살린 수급 항목이 `_build_trend_map` 과 같은 불변식(모든 항목이 5거래일치 `details` 를 갖춘다)을 지키도록 하고, 지키지 못하는 캐시는 통째로 미스 처리해 CSV 에서 다시 만들게 한다.

**Architecture:** `_deserialize_trend_map` 한 함수만 고친다. 지금은 되살릴 수 없는 행을 `continue` 로 건너뛰고 남은 행에 `days: 5` 를 무조건 붙이는데, 이것을 `return None` 으로 바꾸어 「캐시가 온전하면 쓰고, 아니면 CSV 에서 다시 만든다」는 두 갈래만 남긴다. `_get_or_build_trend_map` 이 이미 `cached_map is not None` 일 때만 캐시를 채택하므로 호출부는 손대지 않는다.

**Tech Stack:** Python 3.11, pandas, sqlite3, pytest

**Spec:** `docs/dev-cycle/TODO.md` 의 `[FLOW-013]` 항목. 근거는 `[FLOW-005]` 사이클의 codex 리뷰다.

## Global Constraints

- 대상 파일 `services/investor_trend_5day_service.py` 는 티어 규칙 §2 의 「수급 집계」 위험 경로다. 변경 규모와 무관하게 **T3** 이며 리뷰 세 종(`/ponytail-review` → `feature-dev:code-reviewer` → `/review`)을 순서대로 돌린다.
- 공개 함수 시그니처를 바꾸지 않는다. `_deserialize_trend_map` 의 반환 타입 `dict[str, dict[str, Any]] | None` 을 유지한다.
- 새 상수, 새 헬퍼, 새 설정값을 만들지 않는다. 5거래일이라는 값은 `_build_trend_map` 이 `tail(5)` 와 `len(details) < 5` 로 이미 하드코딩하고 있으므로, 그 값을 상수로 빼는 일은 이번 범위를 넘는다.
- 테스트는 기존 `tests/services/test_investor_trend_5day_service.py` 에 함수로 덧붙인다. 새 프레임워크나 픽스처 계층을 들이지 않는다.

## File Structure

- Modify: `services/investor_trend_5day_service.py` — `_deserialize_trend_map`(`:259-306`) 한 함수. 손상 판정과 로그를 더한다
- Test: `tests/services/test_investor_trend_5day_service.py` — 파일 끝에 회귀 검사 세 건을 덧붙인다

`_serialize_trend_map` 은 건드리지 않는다. 그 함수의 입력은 언제나 `_build_trend_map` 의 산출물이고 그 값은 이미 `int` 이므로 직렬화 도중 `continue` 로 빠지는 경로에 도달할 수 없다. 도달 불가능한 경로에 방어를 넣으면 검사할 수 없는 코드가 남는다.

---

### Task 1: 역직렬화가 5일치 불변식을 강제한다

**Files:**
- Modify: `services/investor_trend_5day_service.py:259-306`
- Test: `tests/services/test_investor_trend_5day_service.py`

**Interfaces:**
- Consumes: `_serialize_trend_map` 이 만드는 페이로드 모양 `{"rows": {ticker: [foreign, institution, [[f, i], ...], latest_date]}}`
- Produces: `_deserialize_trend_map(payload) -> dict | None`. 반환 타입은 그대로이고 `None` 을 돌려주는 조건만 넓어진다. 호출자 `_get_or_build_trend_map`(`:959`)은 변경하지 않는다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def _snapshot_payload(details_rows):
    return {"rows": {"005930": [15, 150, details_rows, "2026-02-24"]}}


def test_deserialize_rejects_a_row_whose_details_are_short():
    four_days = [[5, 50], [4, 40], [3, 30], [2, 20]]

    assert trend_service._deserialize_trend_map(_snapshot_payload(four_days)) is None


def test_deserialize_keeps_a_row_with_five_days():
    five_days = [[5, 50], [4, 40], [3, 30], [2, 20], [1, 10]]

    restored = trend_service._deserialize_trend_map(_snapshot_payload(five_days))

    assert restored is not None
    assert restored["005930"]["days"] == 5
    assert len(restored["005930"]["details"]) == 5


def test_deserialize_rejects_a_malformed_row_instead_of_dropping_it():
    payload = {
        "rows": {
            "005930": [15, 150, [[5, 50], [4, 40], [3, 30], [2, 20], [1, 10]], "2026-02-24"],
            "000660": ["not-a-number", 150, [], ""],
        }
    }

    assert trend_service._deserialize_trend_map(payload) is None
```

세 번째 검사가 이번 변경의 핵심이다. 손상된 행 하나를 조용히 버리면 그 종목은 호출자에게 「CSV 에 없다」와 구분되지 않고, 남은 캐시가 계속 채택되면서 그 종목만 영영 수급 없음으로 나간다.

- [ ] **Step 2: 실패를 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -k deserialize -v`
Expected: 세 건 가운데 `test_deserialize_rejects_a_row_whose_details_are_short` 와 `test_deserialize_rejects_a_malformed_row_instead_of_dropping_it` 이 FAIL 한다. 지금 코드는 짧은 `details` 를 그대로 되살리고 손상된 행은 건너뛴 뒤 나머지를 돌려주기 때문이다.

- [ ] **Step 3: 구현한다**

`_deserialize_trend_map` 의 `continue` 세 곳을 `return None` 으로 바꾸고, `details` 를 다 채운 뒤 길이를 확인하는 분기를 더한다. 독스트링에 불변식과 `None` 의 뜻을 적는다.

```python
def _deserialize_trend_map(payload: dict[str, object]) -> dict[str, dict[str, Any]] | None:
    """SQLite 스냅숏을 되살린다. 5거래일치 불변식을 지키지 못하면 ``None`` 을 돌려준다.

    ``_build_trend_map`` 은 ``details`` 가 다섯 건인 항목만 만든다. 되살릴 때 그
    불변식을 확인하지 않으면 네 건짜리 항목이 ``days: 5`` 를 달고 나가고,
    ``_detect_csv_anomaly_flags`` 가 ``insufficient_days`` 를 붙여 불필요한 참조
    조회를 부르며, ``_score_supply_core`` 의 연속 부호 스트릭이 하루를 잃은 채
    조용히 낮은 점수를 낸다.

    행 하나라도 되살릴 수 없으면 남은 행까지 버리고 ``None`` 을 돌려준다. 그 행만
    건너뛰면 해당 종목은 호출자에게 「CSV 에 종목이 없다」와 구분되지 않는데,
    남은 캐시는 계속 채택되므로 그 종목만 영영 수급 없음으로 나간다. ``None`` 은
    호출자에게 캐시 미스이므로 CSV 에서 다시 만들어진다.
    """
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    trend_map: dict[str, dict[str, Any]] = {}
    for ticker, row_payload in rows_payload.items():
        if not isinstance(row_payload, (list, tuple)) or len(row_payload) < 2:
            logger.warning("Discarding investor trend snapshot: malformed row for %s", ticker)
            return None

        try:
            foreign_5d = int(float(row_payload[0]))
            inst_5d = int(float(row_payload[1]))
        except (TypeError, ValueError):
            logger.warning("Discarding investor trend snapshot: non-numeric total for %s", ticker)
            return None

        details_payload = row_payload[2] if len(row_payload) >= 3 else []
        details: list[dict[str, int]] = []
        if isinstance(details_payload, list):
            for item in details_payload:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    logger.warning("Discarding investor trend snapshot: malformed detail for %s", ticker)
                    return None
                try:
                    foreign_value = int(float(item[0]))
                    inst_value = int(float(item[1]))
                except (TypeError, ValueError):
                    logger.warning("Discarding investor trend snapshot: non-numeric detail for %s", ticker)
                    return None
                details.append(
                    {
                        "netForeignerBuyVolume": foreign_value,
                        "netInstitutionBuyVolume": inst_value,
                    }
                )

        # _build_trend_map 이 다섯 건 미만을 버리므로 되살린 쪽도 같은 불변식을 지킨다.
        if len(details) != 5:
            logger.warning(
                "Discarding investor trend snapshot: %s has %d days, expected 5",
                ticker,
                len(details),
            )
            return None

        latest_date_value = ""
        if len(row_payload) >= 4 and isinstance(row_payload[3], str):
            latest_date_value = row_payload[3]

        ticker_key = str(ticker).zfill(6)
        trend_map[ticker_key] = {
            "foreign": foreign_5d,
            "institution": inst_5d,
            "details": details,
            "days": 5,
            "latest_date": latest_date_value,
        }
    return trend_map
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `source venv/bin/activate && pytest tests/services/test_investor_trend_5day_service.py -v`
Expected: 새 검사 세 건을 포함해 전부 PASS. 기존 검사 가운데
`test_investor_trend_5day_service_reuses_sqlite_snapshot_after_memory_clear` 가 정상 스냅숏의 재사용을 확인하므로, 이 변경이 정상 캐시까지 버리지 않는다는 것이 그 검사로 함께 확인된다.

- [ ] **Step 5: 전체 검증**

Run: `source venv/bin/activate && pytest`
Expected: 1637 통과 2 스킵 (기존 1634 + 새 검사 3)

`frontend/` 를 건드리지 않지만 위험 경로 항목이므로 vitest 도 함께 돌려 회귀가 없음을 확인한다.

Run: `cd frontend && npx vitest run`
Expected: 237 통과

- [ ] **Step 6: 커밋**

커밋은 dev-cycle [3] 검증의 5번에서 시나리오 문서와 함께 만든다. 이 계획 문서와 `docs/dev-cycle/TODO.md` 의 항목 제거도 그 커밋에 담는다.

---

## Self-Review

**1. Spec coverage** — TODO 의 체크박스 세 개를 모두 덮는다. 첫째와 둘째(`details` 가 다섯이 아닌 항목을 버리고 캐시 미스로 처리)는 Step 3 의 `return None` 하나가 동시에 해결한다. 두 동작을 따로 구현할 필요가 없는 이유는 `_get_or_build_trend_map` 이 이미 `None` 을 캐시 미스로 다루기 때문이다. 셋째(회귀 검사)는 Step 1 의 세 검사다.

**2. Placeholder scan** — 없다. Step 3 은 함수 전체를 최종 형태로 적었고, Step 1 은 실행 가능한 테스트 코드를 적었다.

**3. Type consistency** — `_deserialize_trend_map` 의 반환 타입은 그대로다. 되살린 항목의 딕셔너리 키 다섯 개(`foreign`, `institution`, `details`, `days`, `latest_date`)도 `_build_trend_map` 의 것과 같다.

---

## 계획과 구현이 갈린 지점

구현 도중 리뷰가 찾은 것을 반영하면서 Step 3 의 코드가 위에 적힌 것과 세 자리에서
달라졌다. 계획을 사후에 고쳐 맞추는 대신 무엇이 왜 달라졌는지 남긴다.

1. **`except` 절에 `OverflowError` 를 더했다.** `/review` 가 CRITICAL 로 지적했다.
   이 페이로드는 `load_json_payload_from_sqlite` 가 `json.loads` 로 복원하는데 JSON 은
   `Infinity` 를 표현할 수 있고 `int(float("inf"))` 는 `ValueError` 가 아니라
   `OverflowError` 를 던진다. 호출자가 `_deserialize_trend_map` 을 `try` 의 `else:` 절
   안에서 부르므로 그 예외는 잡히지 않고 종목 상세 요청 하나를 통째로 실패시킨다.
   회귀 검사 `test_deserialize_rejects_infinity_from_a_corrupted_snapshot` 를 함께 넣었다.
2. **`isinstance(details_payload, list)` 중첩을 early return 으로 뒤집었다.**
   `/ponytail-review` 의 지적이다. 들여쓰기가 한 단계 줄었다.
3. **로그 접두사를 `Discarding trend snapshot:` 으로 줄였다.** 같은 리뷰의 지적이다.
   모듈 이름이 이미 `investor_trend_5day_service` 이므로 중복이었다.

독스트링도 함께 고쳤다. 계획에 적은 「그 종목만 영영 수급 없음으로 나간다」가 부정확했다.
`_resolve_best_payload` 는 `normalized_csv is None` 이면 참조를 채택하므로, 실제로는 그
종목이 CSV 경로를 잃고 요청마다 pykrx 나 Toss 참조 조회를 타며, 그 참조까지
`_reference_reject_reason` 에 걸려야 수급이 아예 사라진다.
