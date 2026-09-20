# JONGGA-024·028·031 구현 보고

## 변경

- `app/routes/kr_market_jongga_ai_payload_helpers.py`
  - AI 평가를 최상위 `ai_evaluation` → `score.ai_evaluation` →
    `score_details.ai_evaluation` 순으로 읽는다.
  - 각 후보에서 유효 action 또는 비어 있지 않은 문자열 사유를 처음 만난 위치에서 고른다.
    action이 잘못됐지만 사유가 있으면 HOLD로 정규화하며, 사유 없는 유효 action만
    `score.llm_reason`으로 보충한다. confidence `0`은 그대로 보존한다.
  - action·reason·legacy reason의 숫자·객체·배열은 유효 문자열로 바꾸지 않는다.
- `frontend/src/app/dashboard/kr/closing-bet/displayHelpers.ts`, `page.tsx`
  - 카드의 배지와 본문이 같은 판정 원천을 사용한다. 실제 차트는 700px 원본 폭을 유지한
    가로 스크롤 영역으로 열며, 화살표 키로도 스크롤할 수 있다. 고정 SVG 미니 polyline은
    제거하고 접근 가능한 차트 열기 버튼으로 바꿨다.
- `frontend/src/app/components/BuyStockModal.tsx`
  - 가격 조회 진행·성공·실패/값 없음 상태를 구분한다. 조회 성공도 실시간성 보장이 아님을
    밝히고, 폴백은 출처를 단정하지 않는 “저장된 가격”으로 표시한다.
- `frontend/src/app/dashboard/kr/closing-bet/page.tsx`
  - 카드의 신호일 종가 타일은 `current_price`가 아니라 유효한 `entry_price`만 표시하고,
    `signal_date`를 라벨에 함께 적는다. `current_price`를 쓰는 매수·일괄 매수·기존 계산 경로는
    변경하지 않았다.

## legacy-only 예외

- Python AI 분석 응답은 기존 호환 계약대로 `score.llm_reason`만 있으면 HOLD 추천을 만든다.
- 카드 화면은 기존 `page.jongga-004.test.tsx` 계약대로 legacy 본문만으로 새 추천을 만들지
  않는다. 이때 본문은 계속 표시하고 배지·확신도는 AI 분석 대기/미산출로 남긴다.
- 명시 AI 후보가 있으나 사유가 비었을 때만 카드도 legacy 본문을 보충한다.

## 회귀 범위

- `tests/app/test_jongga_followup_contract.py`
  - 상충 top/score/details, reason-only, bare string, confidence 0, non-string malformed 후보를
    확인한다.
- `frontend/src/app/dashboard/kr/closing-bet/displayHelpers.jongga-followup.test.ts`
  - 화면 우선순위와 legacy-only 비추천을 확인한다.
- `frontend/src/app/dashboard/kr/closing-bet/page.regression-jongga-followup.test.tsx`
  - 카드 본문/배지 원천, 700px 스크롤, 키보드 스크롤, 이미지 실패 외부 링크를 확인한다.
- `frontend/src/app/components/BuyStockModal.jongga-followup.test.tsx`
  - 시세 조회 pending → success/empty/reject 문구를 확인한다.
- 기존 `page.regression-jongga-021.test.tsx`, `page.regression-fe-024.test.tsx`는 차트 열기
  버튼의 접근 가능한 이름을 사용하도록 locator를 갱신했다.
- `page.regression-jongga-015.test.tsx`, `page.regression-jongga-followup.test.tsx`는 신호일
  종가 타일의 `entry_price`·날짜를 카드 안에서 좁혀 확인한다. 매수가/시스템 기준가에도 같은
  금액이 나타날 수 있으므로 전역 금액 문자열은 준비 조건이나 타일 판정에 쓰지 않는다.
- `page.regression-jongga-021.test.tsx`, `page.regression-jongga-037.test.tsx`,
  `page.regression-fe-024.test.tsx`는 가격 표시값 대신 종목 heading으로 데이터 준비를 기다린다.
  이는 polling·ARIA·차트 검사의 대상 동작을 바꾸지 않고, 가격 표기의 의미 변경으로 생긴
  불안정한 준비 조건만 제거한다.
- `page.regression-jongga-023.test.tsx`는 동적 `YYYY-MM-DD 종가` 라벨에서 기존 tooltip의
  신호일 기준 설명을 확인한다.

## 검증

- 부모 격리 하네스: `pytest` → `2320 passed, 3 skipped`.
- 부모 격리 하네스: `npx vitest run` → `582 passed, 80 files`.
- 부모 격리 하네스: type-check exit 0, lint 0 errors/191 warnings, build 3/3 PASS.
- 이 레인은 원본에서 테스트·HTTP 요청·서버 기동을 실행하지 않았다. 새 파일과 변경 파일의
  whitespace 정적 검사는 오류 출력이 없었다.
- JONGGA-031 보완 뒤 review2의 가격 문자열 기반 기대가 29건 깨졌고, 위 locator 이전으로
  review3은 `within` import 누락 3건만 남았다. 부모가 import를 보완해 전체 재실행 중이며,
  이 레인은 그 외 제품·테스트 파일을 추가 수정하지 않았다.

## malformed AI 출력 경계 보완

- 독립 architect 검토에서 `action=BUY`와 객체형 `reason`이 함께 오면 Python이 원본 dict를
  펼쳐 객체를 그대로 반환하는 결함을 확인했다. `reason.trim()`을 가정하는 화면/소비자에
  런타임 오류가 날 수 있는 경계였다.
- Python 추출기는 action·reason·confidence·model 네 필드만 새 dict에 넣는다. reason과
  model은 문자열만 허용하고, confidence는 bool을 제외한 유한 number·string·null만 허용한다.
  추가 provider metadata는 소비하지 않는다.
- 화면 helper도 `NaN`·`Infinity`·`-Infinity` confidence를 출력 전에 버린다. Python의 매우 큰
  정수는 `sys.float_info.max` 범위를 먼저 확인해 `math.isfinite`의 `OverflowError` 없이
  제외한다. 이는 점수 상한이 아니라 JavaScript number로 표현할 수 없는 입력의 경계다.
- 회귀는 action/reason 객체·배열, confidence 객체·bool·NaN·±Infinity·±10^400, model 객체와
  유효한 0·finite number·string·null을 함께 확인한다.

## 최종 검증 근거

- 부모 격리 target: Python AI 출력 계약 `10 passed`.
- 부모 격리 target: 화면 helper 계약 `5 passed`.
- 부모 격리 전체: `pytest` → `2324 passed, 3 skipped`; `npx vitest run` → `593 passed`.
- 독립 code review `APPROVE`, architect `CLEAR` 뒤 T3 deep review로 전달했다.
