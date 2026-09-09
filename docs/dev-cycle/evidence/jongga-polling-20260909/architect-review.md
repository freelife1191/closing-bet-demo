## Summary

JONGGA-037/JONGGA-032/INFRA-069 범위는 현재 diff와 요구사항에 부합하며, lifecycle·timer cleanup·늦은 응답 무효화·캐시 격리가 모두 명시적으로 연결되어 있습니다. Architect 판정은 `CLEAR`입니다. 별도 미확인 blocker는 발견되지 않았습니다.

## Analysis

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.tsx:1678-1719`
  - polling interval, safety timeout, generation, active request를 각각 ref로 소유합니다.
  - unmount 시 `isMountedRef=false` 후 `stopPolling()`을 호출해 interval/timeout을 모두 해제하고 generation을 증가시킵니다.
  - `stopPolling()`은 현재 실행 중인 요청 자체를 취소하지 않지만, generation 검사가 응답 적용을 차단하므로 AbortController 없이도 stale response를 무효화합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.tsx:1721-1774`
  - 새 polling 세대를 시작하기 전에 이전 세대를 정리합니다.
  - interval callback은 `pollingRequestActiveRef`로 중복 in-flight 요청을 막습니다.
  - 응답 후 `isCurrentPolling()`을 다시 확인하므로 완료·timeout·unmount 이후 `setState`/`onRefresh`가 실행되지 않습니다.
  - `is_running`과 `isRunning` 양쪽 API 응답 필드를 지원합니다.
  - 완료 응답은 현재 polling 세대가 판정하며, `stopPolling()`, `setUpdating(false)`, 메시지 초기화, `onRefresh()`가 한 경로로 이어집니다.
  - `finally`의 active flag 해제도 현재 세대일 때만 수행해 이전 요청이 새 polling 세대 상태를 건드리지 않습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet/page.tsx:1805-1827`
  - run POST 성공 후 polling을 시작합니다.
  - 409도 이미 실행 중인 작업의 상태를 확인하도록 동일한 polling으로 진입합니다.
  - 비-409 실패는 polling을 시작하지 않고 버튼 상태와 메시지를 되돌립니다.
  - POST 응답이 늦게 도착한 뒤 unmount되면 `pollStatus()`가 `isMountedRef`에서 즉시 반환하므로 새 timer가 생성되지 않습니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet/page.regression-jongga-037.test.tsx:82-151`
  - 완료 응답 후 버튼 상태가 `UPDATED`로 바뀌고 latest 재조회가 한 번 발생하며 이후 status polling이 중단되는 계약을 검증합니다.
  - 409 → running → completed 순서도 검증합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet/page.regression-jongga-037.test.tsx:153-230`
  - safety timeout 뒤 늦은 status 응답이 화면을 되살리거나 polling을 재개하지 않는지 검사합니다.
  - unmount 뒤 늦은 status 응답이 latest 재조회와 다음 polling을 만들지 않는지 검사합니다.
  - run POST 응답 자체가 늦어도 unmount 이후 polling이 시작되지 않는지 검사합니다.
  - `vi.getTimerCount() === 0`으로 interval/timeout 누수를 직접 고정합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_news_collector_refactor.py:31-66`
  - `_load_cached_news_items`와 `_save_cached_news_items`를 테스트마다 no-op으로 monkeypatch합니다.
  - 뉴스 병합/정렬 및 source failure 테스트가 메모리·SQLite 캐시를 읽거나 쓰지 않는다는 INFRA-069 기대를 보장합니다.

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/jongga-polling-20260909/review-input.json`
  - base `b503549`
  - 대상은 production 1개, frontend 회귀 테스트 1개, news collector 테스트 1개입니다.
  - 요구사항은 완료 응답 재조회, 완료/timeout/unmount cleanup 및 late response invalidation, cache isolation입니다.

- 제공된 검증 증거
  - targeted 15 passed
  - 전체 pytest 2281 passed, 2 skipped
  - type-check exit 0
  - lint errors 0, warnings 200
  - 위 결과는 요청된 lifecycle 및 cache isolation 경로를 통과한 근거입니다.

## Root Cause

기존 문제는 polling timer가 React state `updating`의 이전 렌더 값에 의존하고, interval/timeout/request 응답의 수명이 하나의 명시적 세대에 묶이지 않았다는 점입니다. 그 결과 완료 후 재조회 누락, unmount 뒤 늦은 응답의 상태 갱신, timer 잔류 가능성이 있었습니다.

현재 구현은 polling generation과 mounted guard를 결합해 요청 취소 없이도 응답 적용을 논리적으로 무효화합니다. active request guard는 같은 세대에서 중복 polling만 막고, 완료·timeout·unmount의 정리 경로는 공통 `stopPolling()`으로 수렴합니다.

## Strongest Counterargument

`fetchAPI` 요청을 AbortController로 실제 취소하지 않으므로 네트워크 요청이 계속 살아 있을 수 있다는 반론은 가능합니다. 그러나 요구사항은 늦은 응답의 UI 재활성화와 timer 재생성 방지이며, 현재 generation/mounted 검사가 그 side effect를 차단합니다. 실제 요청 취소까지 요구하려면 fetchAPI 계약과 abort signal 전파를 별도 범위로 확장해야 하며, 현재 승인 범위의 필수 조건은 아닙니다.

## Recommendations

1. `CLEAR`: 현재 범위 그대로 통합 가능합니다.
2. AbortController 도입은 현 diff의 lifecycle 계약을 강화할 수 있지만 fetchAPI 호출 계약 변경이 필요하므로 별도 작업으로 분리하는 편이 안전합니다.
3. `lint`의 warning 200건은 오류가 아니며 이번 변경의 blocker로 판단할 근거가 없습니다.

## Architectural Status

`CLEAR`

## File Hashes

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.tsx`
  `4cb5256c46fab18f2a519e1a57cee326c18ce4e57582a1f4fe63c5ab56c609d3`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-037.test.tsx`
  `891a2ee863f70b7d1910bf9bc7300b59d1d0c78aa0c056f501d1c05766c0d7f9`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_news_collector_refactor.py`
  `c5d0d74127545ce6188cc8ac9e7c0b0321d996664e6405e4f6f923038c30645c`

## References

- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/jongga-polling-20260909/review-input.json`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.tsx:1678-1774`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.tsx:1805-1827`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-037.test.tsx:82-230`
- `/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/engine/test_news_collector_refactor.py:31-66`
