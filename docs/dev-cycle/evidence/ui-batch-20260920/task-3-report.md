# Task 3 보고 — Tooltip 경계 (FE-037)

## 변경 파일

- `frontend/src/app/components/Tooltip.tsx`
- `frontend/src/app/components/Tooltip.test.tsx`

## 구현 결과

- 기존 `children`, `content`, `className`, `position`, `align`, `as`, `size` 인터페이스를 유지했다.
- 툴팁은 hover 또는 focus 때만 DOM에 만들고, 열린 동안에만 trigger와 팝업 크기를 잰다.
- 팝업은 viewport 기준 fixed 좌표를 사용한다. 요청한 위·아래 방향에 공간이 부족하면 반대편으로 뒤집고, 좌우와 상하를 8px viewport 여백 안으로 제한한다.
- scroll과 window resize 때 위치를 다시 계산한다. 지원 환경에서는 `ResizeObserver`로 trigger, 내용, 글꼴 등에 따른 열린 팝업의 크기 변화도 같은 계산 경로로 반영한다.
- 팝업 최대 너비와 높이를 viewport 안으로 제한하고 긴 내용은 세로 스크롤로 읽을 수 있게 했다.
- 모달 안에서는 trigger와 가장 가까운 `[data-modal-layer][data-modal-active="true"]`에 portal한다. 모달 밖에서는 `document.body`에 portal하며, 비활성 modal layer에서는 열지 않고 열린 뒤 비활성화되면 닫는다.
- portal 경계를 건너 팝업으로 포인터를 옮겨도 유지하고, 팝업을 벗어나면 닫는다. portal 이벤트가 React 트리를 따라 wrapper로 전파될 때 DOM 밖의 target을 trigger로 오인하지 않게 막았다.
- focus로 열 수 있고 trigger의 기존 `aria-describedby`를 보존하면서 툴팁 ID를 연결한다. Escape로 닫으며 wrapper에 `tabIndex`를 추가하지 않는다.
- 언마운트와 닫힘 때 timer, scroll, resize, Escape, modal attribute observer, resize observer를 정리한다.
- 새 의존성, 타입 억제, lint 억제를 추가하지 않았다.

## TDD와 검증 증거

- RED: production 변경 전에 회귀 테스트를 작성했다. 부모의 격리 실행 `target-tooltip-red`에서 13건 실패를 확인했다. 실패 이유는 기존 컴포넌트에 열린 `role="tooltip"`, 위치 측정, portal, 접근성 동작이 없었기 때문이다.
- GREEN 1: 부모의 격리 실행에서 11건 통과, 2건 실패를 확인했다. fixed 검증을 Tailwind 클래스와 실측 좌표로 분리했고, portal hover 이벤트가 wrapper를 다시 여는 실제 결함을 수정했다.
- GREEN 2: 부모의 격리 실행에서 Tooltip 회귀 13/13 통과를 확인했다.
- 작업 지시에 따라 구현 에이전트는 명령과 테스트를 직접 실행하지 않았다. 전체 타입 검사, lint, 통합 테스트와 브라우저 실측은 부모가 소유한다.

## 적용한 지침

- `superpowers:test-driven-development`와 `writing-good-tests.md`
- `vercel-react-best-practices`
- Next.js 번들 문서 `01-app/01-getting-started/05-server-and-client-components.md`
- 계획의 ModalShell host 계약: body 직접 자식 fixed viewport host, overflow visible, transform/filter 없음, 최상단만 `data-modal-active="true"`

## 부모 통합 확인 항목

- 전체 type-check와 lint에서 동적 `span`/`div` ref 및 portal 이벤트 타입 확인
- 실제 375px 화면의 첫 줄·좌우 edge와 활성 modal 안에서 위치, clipping, hover/focus, 긴 내용 스크롤 확인
- ModalShell의 `[data-modal-layer]` host가 fixed full viewport, overflow visible, transform/filter 없음 계약을 만족하는지 함께 확인
