# Task 5 종목 표시 보고

## 범위

- `frontend/src/app/dashboard/kr/formatMarketAmount.ts`
- `frontend/src/app/dashboard/kr/closing-bet/displayHelpers.ts`
- `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
- `frontend/src/app/dashboard/kr/vcp/page.tsx`
- 위 경계의 인접 회귀 테스트

AI 판정·점수·신호 계산, API, 인증, 실제 거래 정책은 바꾸지 않았다.

## RED

부모 격리 사본 `display-red`에서 구현 전 회귀를 실행해 **8 failed / 19 passed**와
`formatMarketAmount` 모듈 부재 1 suite를 확인했다. 실패는 다음 승인 범위와 일치했다.

- 필터 결과 0과 원자료 없음이 같은 영어 빈 상태로 표시됨
- 필터를 적용하면 리포트 전체 테마가 사라짐
- 거래량·종가·거래대금 툴팁의 기준 시점이 신호일과 어긋남
- HOLD 카드의 확신도 라벨과 배지 행이 1280px 경계에서 줄바꿈됨
- 종가베팅·VCP 모바일 제어행의 wrap·폭·날짜 최소폭 없음
- 조 단위 억 해상도와 VCP/종가베팅 반올림을 함께 보장하는 공용 포맷 없음

## 구현

- 공용 `formatMarketAmount`를 추가했다. 조 단위는 `1조 2400억`처럼 억 단위까지 보존하고,
  억·만 단위는 반올림하며 음수는 절댓값과 같은 경계를 쓴다.
- 0은 VCP에서 `0`, 종가베팅의 값 없음 자리에서는 `-`로 유지하도록 호출부가 두 번째
  표기 인자를 넘긴다. `undefined`·`null`·`NaN`·무한대는 `-`로 표시한다.
- 종가베팅의 `formatBigNumber`와 VCP의 `formatFlow`를 제거하고 두 화면이 공용 포맷을 쓴다.
  기존 수치 회귀는 삭제하지 않고 새 함수와 승인된 조 단위 기대값으로 옮겼다.
- VCP `foreign_5d`·`inst_5d`는 수급 점수 경계가 200억·500억 원 단위로 판정하고
  (`engine/screener_scoring_helpers.py`), 서비스 회귀도 600억·250억 값을 사용한다. 상세 요약에
  남아 있던 `주` 접미사를 `원`으로 고치고 실제 금액 문자열을 회귀에 추가했다.
- 종가베팅은 D등급 안전장치를 포함한 실제 표시 배열을 따로 만들고, 필터 결과 0과 원자료
  없음을 각각 한국어로 안내한다.
- 리뷰에서 D등급 원자료만 있는 리포트가 원자료 없음으로 오인되는 경계를 발견했다.
  `reportSignals → D등급 제외 eligibleSignals → 사용자 필터 displaySignals` 순서를 명시하고,
  원자료 0·D-only·비D 원자료의 필터 결과 0을 세 문구로 나눴다. D-only는 갱신 실패가 아니라
  안전 기준 제외와 다른 날짜 확인을 안내하며, 활성 거래대금 필터가 있어도 이 원인을 유지한다.
- 상단 CANDIDATES/FILTERED 묶음에 `엔진 단계`를 표시하고, 활성 필터 요약은
  `표시 N / 리포트 전체 N`으로 구분했다.
- TRENDING THEMES는 화면 필터 전 전체 리포트 signals에서 계산한다.
- 카드의 상승률·거래량 배수·종가·거래대금 설명을 모두 신호가 나온 거래일 기준으로 맞췄다.
- HOLD 카드의 배지 행은 wrap을 허용하고 `확신도` 라벨 자체는 `whitespace-nowrap`으로 묶었다.
- 종가베팅 제어행은 모바일에서 전체 폭과 wrap을 사용하며, 두 긴 버튼은 줄바꿈하지 않고
  리포트 날짜 선택 상자는 `min-w-[10rem]`을 가진다.
- VCP 제어행은 모바일에서 `self-stretch`와 wrap을 사용하고 과거 날짜 버튼은
  `min-w-[7rem]`, 비활성 사유는 `break-words`를 적용했다.
- 종가베팅 상세 수급에서 0을 값 없음 `-`로 바꾼 뒤 기존 `>= 0` 접두사가 `+-`를 만들던
  결합 오류를 고쳤다. 외국인·기관·개인 모두 양수에만 `+`, 음수는 `-`, 0·누락은 중립색의
  `-`를 표시한다. 기존 양수·음수 문자열 회귀와 새 0·누락 실제 렌더 회귀가 세 방향을 고정한다.

## 검증 상태

- 구현 전 부모 격리 RED: 8 failed / 19 passed + 공용 helper 모듈 부재 1 suite
- 구현 후 targeted·전체 Vitest, typecheck, lint, build: 부모 격리 검증 대기
- 원본 테스트·HTTP·3500/5501·live·`.env`·`data/`·LLM·인증·수집·거래·삭제: 실행·접근 없음

## 부모 검증 결과와 보고 정정

- 대상42/42, 전체Vitest558/74파일, build3/3, typecheck exit0.
- lint는 검사항목수 74/74가 아니라 **0 errors / 192 warnings**다. 구현자의 최종메시지에서 Vitest 파일수를 lint 수치로 잘못 적었으며 원시 lint-display.log를 기준으로 바로잡는다.
- VCP상세 설명의'주'는금액계약과틀려'원'으로정정. engine/screener_scoring_helpers.py의금액임계값과기존engine회귀가근거. 관련assert는사본구코드1fail2pass→새코드3pass.
- 현재code/architect영향리뷰중,QA2미실행. 위의 대기는 구현자 보고 시점의 기록이다.
