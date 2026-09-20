# FE-031 갱신 실패 회귀 보고

## 범위

- `frontend/src/app/dashboard/kr/page.tsx`
  - Market Gate 갱신의 일반 오류를 화면 `role="alert"`로 표시한다.
  - Refresh Data 요청을 기존 `fetchAPI`로 보내 기본 10초 timeout, HTTP/비JSON 본문, 네트워크 오류 계약을 재사용한다.
  - Refresh Data의 403은 기존 권한 회수와 `권한 없음` 모달을 유지한다.
  - 재시도 시작 시 오류를 비우고, 실패 후 두 갱신 버튼의 스피너가 끝난다.
  - 아이콘만 있던 Market Gate 버튼에 `aria-label="Market Gate 새로고침"`을 부여했다.
- `frontend/src/app/dashboard/kr/page.regression-fe-031.test.tsx`
  - 일반 오류, HTTP 500/HTML 500/네트워크/10초 timeout, 재시도 성공, 403 권한 회수를 회귀로 고정했다.

`frontend/src/lib/api.ts`는 수정하지 않았다. 기본 10초 timeout 계약은 기존 `api.test.ts`가 유지한다.

## 격리 검증

- 유효 RED: `target-refresh-valid-red.json` — 격리 사본에서 새 FE-031 테스트 7개가 모두 실패했다(exit 1). 기준 소스로 `page.tsx`만 되돌린 뒤 `role="alert"` 부재와 Refresh Data의 공용 `fetchAPI` 미호출을 확인했다.
- 유효 GREEN: `target-refresh-valid-green.json` — 격리 사본에서 `page.regression-fe-031.test.tsx` 7개와 기존 `page.regression-infra-059.test.tsx` 6개, 총 13개가 통과했다(exit 0, 1.81초).
- 정적 검사: 변경 파일 대상 `git diff --check` 통과.

원본에서 테스트, 서버 실행, HTTP 요청은 하지 않았다.

## 초기 선택자 편차

처음에는 Refresh Data 버튼을 정확한 접근성 이름 `Refresh Data`로 찾았다. 실제 접근성 이름에는 보조 텍스트 `Last: ...`가 함께 포함되어 7개가 모두 진입 전에 실패했다. 이 실패는 제품 동작을 검증하지 못하므로 유효 RED로 쓰지 않았다. 선택자를 `/Refresh Data/`로만 고친 뒤 소스를 되돌려 유효 RED를 다시 확인했고, 기대 오류와 권한 동작 단언은 약화하지 않았다.

## BuyStockModal timeout 보완

- `frontend/src/app/components/BuyStockModal.tsx`
  - 원시 `fetch` 대신 `fetchAPI<unknown>`로 시세 POST를 보낸다. 따라서 기본 10초 timeout과 HTTP 오류 계약을 그대로 쓴다.
  - 응답을 `Record<string, unknown>` 경계에서 확인하고, `prices[ticker]`를 우선하되 legacy 평면 응답도 읽는다.
  - 양수 유한 숫자만 조회 가격으로 승인한다. 0, 음수, `NaN`, 무한대, 문자열은 저장된 `current_price`·`entry_price`·`price` 순서의 기존 fallback으로 돌아간다.
- `BuyStockModal.jongga-followup.test.tsx`는 부분 actual import로 실제 `fetchAPI`를 사용해 HTTP 500, 실제 AbortController timeout, 중첩/평면 정상 응답, 무효 가격 fallback을 확인한다. `BuyStockModal.test.tsx`와 `ModalShell.test.tsx`도 같은 방식으로 기존 포트폴리오·주문·모달 테스트의 API 모킹 의도를 보존했다.

격리 유효 RED `target-buy-timeout-valid-red.json`은 공용 요청 signal 부재, 10초 abort 부재, 음수·문자열 가격 수용으로 4건 실패/8건 통과(exit 1)를 확인했다. 최종 GREEN `target-buy-timeout-green2.json`은 관련 세 파일 47건이 통과했다(exit 0, 1.53초). 첫 GREEN 시도(`target-buy-timeout-green.json`)는 fake timer와 `findByText`의 0ms 대기가 충돌해 timeout 테스트 자체가 5초 제한에 걸렸으므로 제품 검증으로 쓰지 않았다. 동기 렌더 후 즉시 pending 상태를 확인하고 10초를 진행하도록 바꾼 뒤 `Request timed out`과 fallback 수렴을 실제로 확인했다.
