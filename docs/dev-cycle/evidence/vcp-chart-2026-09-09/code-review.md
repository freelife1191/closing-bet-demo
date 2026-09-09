## Code Review Summary

> 새 dedicated code-reviewer 역할 생성이 스레드 한도로 실패해, 기존 native agent가
> `/Users/freelife/.codex/prompts/code-reviewer.md`를 직접 읽고 역할 지침을 대체 수행했다.

**Files Reviewed:** 5
**Base:** `96a0f72d74c9b24e3f1f2c8a5b5af6533e313b4f`
**Input integrity:** `review-input.json`의 5개 SHA-256과 현재 입력이 모두 일치함
**Total Issues:** 2

### By Severity

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 1
- LOW: 1

### Stage 1 — Spec Compliance

- VCP-012: 요청 순번을 성공 응답과 `finally`의 로딩 종료에 함께 적용하고, 닫기·새 종목·기간 전환이 이전 요청을 무효화한다. 승인된 요청 세대 계약을 충족한다.
- FE-018: 모바일에서 모달 전체를 세로 스크롤시키고 차트·토글·정보 막대·AI 패널을 문서 흐름에 쌓는다. 375×812의 실제 겹침 여부는 예정된 브라우저 실측 판정이 필요하다.
- VCP-014: 1M/3M/6M/1Y 버튼이 기존 `period` API 계약을 사용하고 과거 기준일을 유지한다. 연속 관측 날짜의 달력 간격이 7일을 초과할 때만 안내하며, 자료 수집·백엔드·신호 판정은 건드리지 않았다.
- 승인 범위 밖의 호환 경로, 데이터 보충, 새 의존성은 추가되지 않았다.

### Stage 2 — Issues

[MEDIUM] 현재 차트 조회 실패를 정상적인 빈 자료로 표시함
**Confidence:** 높음
**File:** `frontend/src/app/dashboard/kr/vcp/page.tsx:924`
**Issue:** `openChart`가 현재 요청 시작 시 `chartData`를 비운 뒤, 실패하면 `console.error`만 남기고 오류 상태를 기록하지 않는다(`:937`). `finally`가 로딩을 끝내면 화면은 같은 빈 배열을 근거로 `No chart data available.`을 렌더링한다(`:1707`). 따라서 1M/3M/6M/1Y 조회의 네트워크·HTTP·파싱 실패가 성공한 빈 응답으로 보인다. 이는 실패를 조용한 기본값으로 바꾸는 경로라 code-reviewer root-cause guard에 걸린다.
**Impact:** 사용자는 기간에 자료가 없다고 오인하고 재시도나 장애 판단을 할 수 없다. 기간 전환이 추가되면서 이 경로의 노출 빈도도 커진다.
**Fix:** `chartError` 상태를 두고 현재 세대의 요청을 시작할 때만 초기화한다. `catch`에서도 `requestId === chartRequest.current`인 경우에만 명시적인 조회 실패 상태를 기록하고, 렌더링은 `chartLoading` → `chartError` → `chartData.length` 순서로 나눈다. 현재 요청 거부는 실패 문구를 보이고, 이전 세대 거부는 새 화면과 로딩을 바꾸지 않는 회귀 검사를 추가한다.

[LOW] 날짜 간격 계산과 화면 표시의 연결 분기가 회귀 검사에 없음
**Confidence:** 높음
**File:** `frontend/src/app/dashboard/kr/vcp/page.tsx:1680`
**Issue:** `chartUtils.test.ts`는 `findChartDateGaps` 계산만 검증한다. 실제 페이지가 `chartDateGaps.length > 0`일 때 `<details>`를 표시하고 7일 이하일 때 숨기는 연결은 `page.regression-vcp-010.test.tsx`에서 확인하지 않는다. 현재 `CHART_ROWS` 자체가 15일 간격이라 추가 fixture 없이도 이 배선을 고정할 수 있다.
**Impact:** helper가 맞아도 import·memo·조건부 JSX가 제거되거나 잘못 연결되면 단위 검사는 계속 통과한다. 실제 브라우저 QA가 보완하지만 회귀 방지는 남지 않는다.
**Fix:** 상세를 연 뒤 `관측 자료의 날짜 간격 7일 초과: 1구간`과 양 끝 날짜를 확인하고, 7일 이하 응답에서는 summary가 없음을 확인하는 페이지 회귀 검사를 추가한다.

### Security / Performance / Maintainability

- 하드코딩된 비밀, HTML 주입, `dangerouslySetInnerHTML`, 외부 URL 구성은 추가되지 않았다. 서버 날짜 문자열은 React 텍스트 노드로 렌더링되어 이 diff에 XSS 경로는 없다.
- 날짜 간격 계산은 차트 응답이 바뀔 때만 `useMemo`로 실행되는 O(n) 순회이며, 최대 1년 차트 범위에서 성능 우려가 없다.
- 요청 순번 방식은 `AbortController` 지원을 API 전반에 추가하지 않고 동일 컴포넌트의 상태 쓰기만 보호하므로 현재 범위에서 유지보수 가능한 최소 수정이다.

### Diagnostics

- LSP 탐색 원문: `LSP_UNAVAILABLE: typescript-language-server executable not found in PATH or frontend/node_modules/.bin`
- LSP 대체 증거: 입력 기록의 전체 `typecheck exit 0`, `lint 0 errors / 기존 warnings 202`, `vitest 415 pass / 58 files`; ponytail 수정 뒤 VCP 대상 49건 재통과.
- 이 리뷰에서는 테스트를 재실행하지 않았다.
- `git diff --check <base> -- <5 files>`: exit 0.

### Recommendation

**REQUEST CHANGES**

승인된 세 기능의 핵심 구현은 맞지만, 현재 요청 실패를 정상 빈 자료로 바꾸는 MEDIUM 문제는 root-cause guard에 따라 첫 커밋 전에 고쳐야 한다. LOW 회귀 검사는 같은 수정의 페이지 테스트에 함께 넣는 것이 적절하다.
