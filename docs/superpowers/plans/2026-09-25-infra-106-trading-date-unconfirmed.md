# [INFRA-106] 개장일 확인 실패를 WARNING 으로 남기고 stale 검증은 판정을 보류한다 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `get_last_trading_date` 가 지수 조회로 개장일을 확인하지 못한 사실을 WARNING 으로 남기고, 관리자 수동 갱신의 stale 검증이 확인되지 않은 기대 날짜(휴장일일 수 있음)로 정상 파일을 실패 처리하지 않게 한다.

**Architecture:** `scripts/init_data.py` 의 `get_last_trading_date` 에 선택 인자 `strict=False` 를 둔다. 지수 결과가 비었거나, pykrx 가 없거나, 조회가 예외를 던지면 WARNING 을 남기고, `strict=True` 면 `RuntimeError` 를 던지며 아니면 종전처럼 주말 처리만 한 날짜를 돌려준다. `services/common_update_pipeline_steps.py` 의 `_resolve_expected_trading_date_str` 만 `strict=True` 로 부른다. 그 함수의 기존 `except Exception: return None` 이 기대 날짜를 `None` 으로 만들고, `_validate_latest_date_not_stale` 은 기대 날짜가 없으면 이미 통과시킨다.

**Tech Stack:** Python 3.11, pytest

**Spec:** 대화 설계(2026-09-25 10:29 승인, 「WARNING 승격 + stale 검증만 판정 보류」), `docs/dev-cycle/TODO.md` `[INFRA-106]` 설계 승인 줄

## Global Constraints

- 수집기 두 곳(`create_daily_prices` `:939`, `create_institutional_trend` `:1182`)은 인자를 바꾸지 않는다. 확인 실패 때 종전처럼 주말 처리 날짜로 수집한다. 휴장일 0원 저장은 `[INFRA-090]` 이 막는다.
- 성공 경로의 로그(「마지막 개장일 확인」 DEBUG)와 반환값은 바뀌지 않는다.
- 16시 이전 전날 당김과 주말 처리는 바뀌지 않는다.
- 테스트는 `sys.modules` 에 가짜 `pykrx` 를 넣어 네트워크·KRX 로그인 없이 돈다. 원본 `data/` 에 쓰지 않는다.
- 운영 반영은 gunicorn 워커를 모두 재기동해야 한다(장 중 금지).

## Review Focus

- `strict=True` 의 예외는 `_resolve_expected_trading_date_str` 의 기존 `except Exception` 이 받는다. 다른 호출자는 `strict` 를 넘기지 않으므로 예외가 새지 않는다.
- 판정 보류는 날짜 비교 하나만 건너뛴다. 종전 `_validate_latest_date_not_stale` 은 첫 줄에서 기대 날짜가 없으면 파일 없음·읽기 실패·날짜 열 없음 검사까지 건너뛰었다. 종전에는 그 길에 거의 닿지 않았지만 strict 뒤에는 KRX 미인증·점검 때마다 닿아, 수급 파일 없이도 VCP 게이트(`institutional_trend_ok`)를 통과할 수 있었다. 그래서 기대 날짜 확인을 날짜 비교 바로 앞으로 옮기고 「stale check skipped」 WARNING 을 남긴다(코드 리뷰 지적 1·3 반영).
- `pykrx 미설치` 는 이미 WARNING 이다. `strict=True` 면 이 경우도 확인 실패로 본다.
- 테스트 스텁 두 개(`tests/services/test_common_update_pipeline_steps_refactor.py:84`, `:121`)가 `strict` 인자를 받지 못하면 `TypeError` 가 `None` 으로 삼켜져 기존 stale 테스트가 거짓 통과가 아니라 실패로 드러난다. 스텁에 `**_kwargs` 를 더한다.

## 알려진 한계

1. 확인 실패 때 수동 갱신은 stale 이어도 성공으로 끝난다. 실패 원인은 WARNING 로그로만 보인다. 승인한 「판정 보류」의 비용이다.
2. 지수 조회가 성공하지만 KRX 가 당일 지수를 아직 확정하지 않은 경우(직전 거래일을 돌려줌)는 이 범위가 아니다.

---

### Task 1: 확인 실패 WARNING 과 strict 인자, stale 검증의 판정 보류

**Files:**
- Modify: `scripts/init_data.py` (`get_last_trading_date`)
- Modify: `services/common_update_pipeline_steps.py` (`_resolve_expected_trading_date_str`, `_validate_latest_date_not_stale` 의 기대 날짜 확인 위치)
- Test: `tests/scripts/test_init_data_vcp_scheduler.py`, `tests/services/test_common_update_pipeline_steps_refactor.py`

- [ ] **Step 1: 실패하는 테스트**

```python
# tests/scripts/test_init_data_vcp_scheduler.py
@pytest.mark.parametrize("fail", ["empty", "raise"])
def test_get_last_trading_date_warns_and_strict_raises_when_unconfirmed(monkeypatch, caplog, fail):
    # [INFRA-106] 지수 조회가 비거나 실패하면 WARNING 을 남기고 주말 처리 날짜를 돌려준다. strict 면 예외
    def _ohlcv(*_a, **_k):
        if fail == "raise":
            raise KeyError("지수명")
        return pd.DataFrame()

    fake = types.ModuleType("pykrx")
    fake.stock = types.SimpleNamespace(get_index_ohlcv_by_date=_ohlcv)
    monkeypatch.setitem(sys.modules, "pykrx", fake)
    ref = datetime.datetime(2026, 9, 27)  # 일요일 → 금요일 09-25

    with caplog.at_level("WARNING"):
        assert init_data.get_last_trading_date(reference_date=ref)[0] == "20260925"
    assert any(r.levelname == "WARNING" for r in caplog.records)
    with pytest.raises(RuntimeError):
        init_data.get_last_trading_date(reference_date=ref, strict=True)

# tests/services/test_common_update_pipeline_steps_refactor.py
def test_run_daily_prices_step_skips_stale_check_when_trading_date_unconfirmed(tmp_path, monkeypatch):
    # [INFRA-106] 개장일을 확인하지 못하면(strict 예외) 기대 날짜 없이 통과한다
    # 파일 마지막 날짜 03-03, 가짜 get_last_trading_date 는 strict=True 면 RuntimeError, 아니면 03-04
    # statuses == [("Daily Prices", "running"), ("Daily Prices", "done")]
```

- [ ] **Step 2: 실패 확인** — `venv/bin/python -m pytest -q -p no:cacheprovider tests/scripts/test_init_data_vcp_scheduler.py tests/services/test_common_update_pipeline_steps_refactor.py -k "unconfirmed"` → 두 테스트 FAIL(`strict` 없음, stale 로 error)

- [ ] **Step 3: 구현**

```python
def get_last_trading_date(reference_date=None, strict=False):
    ...
        else:
            log(f"pykrx 지수 데이터 없음, 개장일 미확인. 주말 처리 날짜 사용: {target_date.strftime('%Y%m%d')}", "WARNING")
    except ImportError:
        log("pykrx 미설치 - 개장일 미확인. 주말 처리만 적용", "WARNING")
    except Exception as e:
        log(f"개장일 확인 실패 (pykrx): {e}. 주말 처리만 적용합니다.", "WARNING")

    if strict:
        raise RuntimeError("마지막 개장일을 확인하지 못했습니다")
    return target_date.strftime('%Y%m%d'), target_date
```

```python
        last_trading_date_str, _ = get_last_trading_date(
            reference_date=_resolve_reference_datetime(target_date),
            strict=True,  # [INFRA-106] 미확인 날짜(휴장일일 수 있음)로 stale 판정하지 않는다
        )
```

기존 스텁 두 개의 시그니처를 `(reference_date=None, **_kwargs)` 로 바꾼다.

- [ ] **Step 4: 통과 확인** — 같은 명령 PASS, 두 파일 전체 PASS

- [ ] **Step 5: 전체** — `venv/bin/python -m pytest -q -p no:cacheprovider` exit 0
