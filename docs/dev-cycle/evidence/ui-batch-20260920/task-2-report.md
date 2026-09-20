# Task 2 구현 보고 — 모달 수명주기 (FE-030·FE-036)

## 범위

- `frontend/src/app/components/Modal.tsx`
- `frontend/src/app/components/ConfirmationModal.tsx`
- `frontend/src/app/components/BuyStockModal.tsx`
- `frontend/src/app/components/SellStockModal.tsx`
- `frontend/src/app/components/PaperTradingModal.tsx`
- `frontend/src/app/components/StockTradeHistoryModal.tsx`
- `frontend/src/app/components/ModalShell.test.tsx`

SettingsModal과 page 파일은 수정하지 않았다. 다른 실행자의 변경도 되돌리지 않았다.

## 구현 결과

- `ModalShell`의 기존 props를 유지하면서 `role?: 'dialog' | 'alertdialog'`와
  `initialFocusRef?: React.RefObject<HTMLElement | null>`를 추가했다.
- 각 셸을 `document.body` 직접 자식인 전체 화면 `[data-modal-layer]` host로 portal한다.
  host는 `fixed inset-0 overflow-visible`이고 transform/filter/clip을 두지 않는다.
- 열린 스택의 맨 위 host에만 `data-modal-active="true"`를 두고 나머지 modal layer와
  body 배경을 `inert` 처리한다. 기존 inert 속성과 body inline overflow 값·priority는
  마지막 모달이 실제 언마운트될 때 복원한다.
- 초깃값은 `initialFocusRef`, 첫 조작 요소, dialog 순서로 정한다. 숨은 조상 아래 요소와
  disabled/hidden/inert 요소는 후보에서 제외하고, `Tab`과 `Shift+Tab`을 활성 dialog 안에서
  순환시킨다. jsdom의 `offsetParent === null`에 의존하지 않는다.
- Escape와 backdrop은 맨 위 모달만 처리한다. 활성 modal layer 안에 tooltip이 열려 있으면
  첫 Escape는 tooltip에 양보한다.
- 닫힐 때는 모달을 연 요소로 초점을 돌린다. 그 요소가 제거됐으면 남은 최상단 모달의 첫
  조작 요소로 안전하게 이동한다. `onClose` 함수만 바뀐 재렌더에서는 초점을 재설정하지 않는다.
- `Modal`의 200ms 닫힘 애니메이션 동안 셸과 focus trap을 유지하고 실제 언마운트 시점에
  초점을 복원한다. reduced-motion에서는 지연을 없앤다.
- `ConfirmationModal`은 `alertdialog`이고 취소 버튼을 초기 초점으로 지정했다.
- owned 모달의 존재하지 않는 `animate-in`/`fade-in`/`zoom-in`/`slide-in`/
  `animate-scale-in`을 실제 전역 `animate-fade-in`과 `motion-reduce:animate-none`, 또는 기존
  transition으로 교체했다.

## TDD 및 검증 증거

- 부모의 격리 RED: `target-modal-red.log/json`, 16 failed / 7 passed. role, portal, inert,
  focus trap·복귀, StrictMode 정리와 수명주기 부재로 실패함을 확인했다.
- 첫 GREEN: `target-modal-green.log`, 22 passed / 2 failed. 두 실패는 jsdom의
  `fireEvent.click`이 실제 브라우저 button click과 달리 trigger에 초점을 주지 않는 테스트
  입력 차이였다. 실브라우저 동작을 모델링하도록 trigger를 focus한 뒤 click하게 분리했다.
- 다음 통합 실행에서 initialFocusRef 지정 검사가 실패했다. portal 전 첫 렌더에서
  `ref.current`의 null 값을 복사해 둔 구현 버그로 확인했고, 요소값이 아니라 ref 객체를
  보존하여 portal commit 뒤 최신 `current`를 읽도록 고쳤다.
- 부모의 격리 GREEN: `target-modal-green3.log`, ModalShell 24/24 passed.
- `git diff --check` 통과.
- 통합 lint는 0 errors / 191 warnings이며, 이번 변경은 기존 기준 190개에서 경고 1개를
  추가했다. `setPortalTarget(document.body)`의 한 번짜리 effect가 그 경고다. 서버 렌더에서는
  `document`를 읽지 않고 null을 유지한 뒤 hydration 이후에만 body portal을 여는 경계다.
  이를 없애기 위한 외부 store/구독 추상화는 이 단순 마운트 전환보다 복잡하고, 서버와 첫
  클라이언트 렌더를 다르게 하면 hydration 불일치 위험이 있으므로 억제 없이 유지한다.
- 구현 실행자는 지시대로 테스트·서버·HTTP를 직접 실행하지 않았다. 부모가 git archive
  격리 사본에서 대상/전체 검증을 소유한다.

## 최신 변경과 남은 게이트

24/24 GREEN 뒤 정적 대조에서 custom CSS인 `animate-fade-in`에 `motion-safe:`를 붙이면 해당
variant가 생성되지 않는 점을 발견했다. 최신 diff는 `animate-fade-in
motion-reduce:animate-none`으로 바로잡았다. 모달 동작 로직은 그대로이며, 부모의 최종 대상
검사와 full Vitest/lint/typecheck/build는 이 최신 diff를 기준으로 다시 확인해야 한다.
