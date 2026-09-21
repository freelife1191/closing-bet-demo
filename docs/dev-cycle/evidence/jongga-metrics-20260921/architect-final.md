# JONGGA-033/018 architecture review

This is an independent read-only architect review performed by an existing independent agent because the native thread limit prevented a new architect agent. It reviewed the frozen six-file input set in `review-frozen.json`; the final two-file delta hashes match the current files:

- `engine/toss_collector_metric_parsers.py`: `eaf542be3035060dd56507f1a8f04d4ad14ccfa280ea81a73e87dfa5906dacb9`
- `tests/engine/test_toss_collector_parsers_refactor.py`: `b5c943b47da0d3f6c5d2150d1d6de3a1cf2a20e042c16c2df081e30ea795e681`

No source import, test, compile, server, data/environment access, or network request was run by this reviewer.

## Result

`CLEAR` for the final delta.

`_extract_latest_and_quarterly` now assigns a period only when the selected latest row contains a non-`None` value for that same metric. It still trims and bounds a supplied string period (`engine/toss_collector_metric_parsers.py:103-126`). Consequently, a latest row cannot lend its period to a previous row or label the parser's default-zero value when that metric is absent.

`test_financial_period_requires_the_corresponding_metric` locks both cases: a populated revenue value retains `2026Q1`, while `netProfitKrw=None` and a missing `netProfitKrw` both yield no net-income period (`tests/engine/test_toss_collector_parsers_refactor.py:250-255`). This resolves the strongest remaining counterargument to the earlier period-linking design.

The existing frozen path continues to propagate source periods into the detail payload (`services/kr_market_stock_detail_service.py:518-525`) and render invalid or missing periods as `기준 기간 미확인` without annual/TTM inference (`frontend/src/app/dashboard/kr/closing-bet/displayHelpers.ts:79-83`). Historical bonus values above seven remain display-only legacy values; no score or stored total is recomputed (`frontend/src/app/dashboard/kr/closing-bet/page.tsx:2407-2423`).

## Evidence boundary

Earlier recorded green evidence covers the pre-delta target set (`pytarget-green.json`: 22 passed). The final added parser assertion was supplied as a RED regression check, but this reviewer did not run it and found no newer green artifact in the provided evidence directory. That is a validation-record gap, not an architectural defect in the two-line parser condition or its direct regression assertion.

## Architectural status

`CLEAR`

## 리더 증거 위치 보완
architect가찾지못했다는 GREEN은 pytarget-missing-green.log/.json에23passed/exit0,pytest-final.log/.json에2452passed3skipped/exit0으로 존재한다. 리더가 두파일을직접읽고현재소스6SHA와scratch일치까지확인했다. 독립architect의정적CLEAR와별개로증거공백을해소했다.
