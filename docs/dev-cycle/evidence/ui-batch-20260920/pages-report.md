# Task 4 화면 통합 보고

## 범위

- `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
- `frontend/src/app/dashboard/kr/vcp/page.tsx`
- `frontend/src/app/dashboard/data-status/page.tsx`
- 위 세 화면의 인접 회귀 테스트 네 파일

Task 5의 JONGGA-023·026·029·FE-016 표시 작업은 건드리지 않았다.

## RED

실제 페이지 컴포넌트를 렌더하는 회귀 검사를 먼저 추가했다. 부모가 만든 격리 사본
`target-pages-red`에서 2026-09-20에 같은 네 파일을 실행해 **11 failed / 11 passed**를
확인했다. 실패 원인은 다음 구현 누락과 일치했다.

- 종가베팅 선택 상자 다섯 개의 정확한 이름 없음
- 종가베팅 상세·차트와 VCP 상세 오버레이의 `dialog` 역할·portal host 없음
- VCP 행 매수와 두 화면의 비활성 매수 버튼에 `aria-describedby`로 연결된 상시 사유 없음
- 종가베팅 카드 매수와 VCP 행 매수의 종목별 접근 가능한 이름 없음
- 데이터 상태 날짜 입력과 아이콘 전송 버튼의 명시적 이름 없음

구현자는 지시를 잘못 해석해 RED 작성 직후 원본 작업 트리에서도 Vitest를 실행했다. 첫 실행은
17:01:25 KST에 4 files failed, 12 failed / 10 passed였고, 테스트 fixture의 다건 조회를 바로잡은
뒤 17:01:53 KST 개별 실행은 data-status 1 failed / 1 passed, closing FE-024 5 failed / 8 passed,
JONGGA-010 2 failed / 1 passed, VCP FE-013 3 failed / 1 passed였다. 이 실행은 HTTP·서버·원본
data·환경 파일을 건드리지 않았지만, 이후 검증은 모두 부모의 격리 사본에서만 수행하도록
중단했다.

## 구현

- 종가베팅 차트·종목 상세와 VCP 차트/AI 상세 오버레이를 공용 `ModalShell`로 옮겼다.
- 각 대화상자 제목에 고유 ID를 두고 `labelledBy`로 연결했다.
- 페이지 안의 중복 Escape 리스너와 카드의 `stopPropagation` 의존을 제거했다. 공용 셸이
  최상단 Escape, 배경 클릭, 초점과 스크롤 수명을 맡는다.
- 존재하지 않는 `animate-in`, `fade-in`, `zoom-in-95`를 해당 오버레이에서 제거하고 기존
  `animate-fade-in`과 `motion-reduce:animate-none`을 사용했다.
- 종가베팅의 거래대금·상승률·등급·총점·리포트 날짜 선택 상자와 VCP 재분석 모드 선택 상자에
  명시적 이름을 붙였다.
- 종가베팅 카드와 VCP 행 매수 버튼에 종목명이 포함된 이름을 붙였다.
- 비활성 카드·행·일괄 매수 버튼의 구체적 사유를 실제 보이는 문구로 렌더하고
  `aria-describedby`로 연결했다.
- 데이터 상태의 날짜 입력과 아이콘 전송 버튼에 명시적 이름을 붙였다.
- ConfirmationModal의 `alertdialog` 전환 뒤에도 비용 발생 확인 회귀가 유지되도록 기존
  테스트의 조회를 `dialog`와 `alertdialog` 모두 허용하게 좁게 보완했다.
- 통합 Vitest에서 상세 오버레이를 여는 기존 회귀 일곱 파일이 `Modal` 모듈 전체를 가려
  새 named export인 `ModalShell`까지 없애는 문제가 드러났다. 기본 `Modal`만 가리고
  `ModalShell`은 실제 구현을 쓰는 partial mock으로 옮겨 기존 상세 검사 행동을 보존했다.
- JONGGA-037 polling 회귀는 실행 확인창의 계약 변경에 맞춰 `dialog` 조회를
  `alertdialog` 조회로 바꾸되 실행 버튼과 polling 기대값은 그대로 유지했다.
- 새 회귀의 jest-dom matcher 타입은 `@testing-library/jest-dom/vitest`를 테스트에서
  명시적으로 불러오도록 보완했다.
- Tooltip이 닫힌 동안 설명 DOM을 만들지 않는 새 수명주기에 맞춰 JONGGA-022의 설명 회귀
  세 건은 해당 라벨에 실제 hover를 보낸 뒤 `role="tooltip"` 영역에서 기존 기대 문구를
  확인하도록 옮겼다. 설명 문구와 금액 기대값은 바꾸지 않았다.
- VCP 페이지에 남아 있던 33줄짜리 `SimpleTooltip`을 삭제하고 표 머리글·매수 버튼 등
  14개 사용처를 공용 `Tooltip`으로 옮겼다. 종전 기본 배치였던 아래 방향과 오른쪽 정렬,
  짧은 설명용 `sm` 기본 프리셋을 유지하면서 FE-037의 portal·뷰포트 경계 보정을 그대로
  받게 했다.
- `animate-fade-in`의 실제 keyframe이 `translateY`를 포함하므로 이를 portal host에 두면
  내부 fixed 툴팁의 viewport 기준을 바꾼다. 부모 격리 `target-review-red`에서 세 페이지
  회귀가 이 경계를 명확히 실패하는 것을 확인한 뒤, 종가베팅 차트·상세와 VCP 상세 모두
  애니메이션 클래스를 dialog card로 옮겼다. host는 fixed 위치와 z-index·바깥 여백만 가진다.

## 검증 상태

- 부모 격리 사본 RED: 11 failed / 11 passed, 의도한 누락 원인과 일치
- 부모 격리 사본 화면 targeted GREEN: 22 passed / 22
- 부모 격리 통합 build: 3 / 3 통과
- 부모 격리 통합 Vitest: Tooltip 회귀 migration 전 535 passed / 3 failed; migration 반영 후 재검증 대기
- 원본 3500/5501, live, `.env`, `data/`, 인증·LLM·수집·거래·삭제 경로: 접근·실행 없음

디자인 훅이 종가베팅과 데이터 상태 화면의 기존 gradient-text·gray-on-color 위치를 다시
표시했으나 이번 변경 줄이 아니며 승인 범위 밖이라 수정하거나 ignore 설정을 추가하지 않았다.
