## 코드 리뷰 요약

**Files Reviewed:** 38
**Total Issues:** 0

### By Severity
- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0
- LOW: 0

### 재검토 결과
이전 지적은 모두 해소됐습니다.

- 매수·매도·모의투자 모달의 닫기 버튼 4곳에 접근 가능한 이름이 추가됐고, 실제 모달 렌더 회귀가 보강됐습니다.
- Tooltip 닫기 유예가 300ms로 늘었으며, 200ms 이동 후 팝업 진입과 Escape 즉시 닫기를 검증합니다.
- 모달 스택 순서가 inline z-index의 단일 정본으로 관리됩니다.
- 모달 host에는 `transform: none`, `filter: none`이 적용되고 애니메이션은 dialog 카드로 이동했습니다.
- 비대화형 Tooltip 자식만 wrapper가 키보드 초점을 받고, 기존 버튼에는 중복 tab stop이 생기지 않습니다.
- 마스킹 값의 DOM 비노출과 미편집 payload 보존 계약도 유지됩니다.
- 실패를 숨기는 fallback이나 신규 보안 문제는 확인되지 않았습니다.

검증 증거:
- Source manifest: 38개, 원본·격리 사본 SHA 일치
- Vitest: 546/546 통과
- Tooltip targeted: 16/16 통과
- Build: 3/3 통과
- Typecheck: 통과
- Lint: 0 errors
- `git diff --check`: 통과

브라우저 QA는 코드 리뷰 이후 필수 단계로 남아 있으며 현재 코드 리뷰 판정을 막는 정적 결함은 없습니다.

### Recommendation
**APPROVE**

## 마지막 layout-effect 영향 원문

**APPROVE 유지.**

`registerModal`만 `useLayoutEffect`로 옮겨 DOM 커밋 후 페인트 전에 z-index·inert·초점을 동기화합니다. 포털 대상은 기존 `useEffect`에서만 설정되므로 SSR 중 DOM 접근도 발생하지 않습니다. 해시 검증도 38개 파일 모두 일치합니다.
