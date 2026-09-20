# UI follow-up fixture 준비 보고

## 준비된 합성 경계

- 기본 상태는 가짜 관리자와 합성 API다. gateway가 `/api/*`를 fixture로 보내므로 실제 인증과
  원본 3500·5501·live에 닿지 않는다.
- `POST /api/kr/market-gate/update`, `POST /api/kr/refresh`는 실제 작업을 시작하지 않고
  `refresh_mode` 제어값만 따른다: `success`, `error-500`, `html-500`, `timeout`, `forbidden`.
  timeout은 프론트엔드 120초 abort 계약보다 긴 125초 지연이다.
- `POST /api/kr/realtime-prices`는 `price_mode=success|error`로 각각 합성 가격 또는 503을
  돌려준다. 그 밖의 제품 변경 POST/PUT/PATCH/DELETE는 405다.
- 000660 합성 신호에는 새 최상위 `HOLD`(confidence 0, 새 사유), 오래된 `score.BUY`,
  `score_details.SELL`을 함께 넣었다. 요청 로그는 기존처럼 scratch `.qa-ui-batch/requests.jsonl`에
  남는다.

## Python 변환 연결

- `/api/kr/ai-analysis`는 합성 종가 신호를 scratch의
  `_normalize_jongga_signals_for_frontend`와 `_build_ai_signals_from_jongga_results`에 통과시킨
  결과를 반환한다. 순수 변환기만 local import하며 LLM·수집·저장 코드는 호출하지 않는다.
- `fixture_probe.py`는 실제 `_extract_jongga_ai_evaluation`의 최상위 HOLD 선택, 입력 불변,
  `/api/kr/ai-analysis`의 동일 추천 반환, 정규화 후 중첩 옛값 보존을 요구한다. 따라서
  JONGGA-028 우선순위 구현 후 UI와 Python 변환 결과를 한 계약으로 확인한다.

## 검증 상태

- 정적 확인: 각 신규 파일에 `git diff --no-index --check /dev/null <file>`을 실행했고
  whitespace 오류 출력이 없었다.
- 함수 실행·fixture probe·서버 기동은 부모의 격리 scratch QA 소유이므로 이 레인에서는 실행하지 않았다.

부모보완: KR홈 GET4개 및 cumulative 합성표3행 추가. VCP000660에는별도gemini판정을비워 실제Python AI응답fallback이UI에닿게함. 같은종가입력을다른VCP자체분석과혼동하지않고fallback경로만대조. RefreshData는10초timeout, MarketGate강제갱신은기존120초; timeout UI행은RefreshData사용.
