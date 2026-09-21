# UltraQA Report

## 목표·범위

VCP-005/INFRA-008 실제 fallback/현재 MarketGate 경로 보존과 VCP-022 confidence 부분 수정.
engine: ultraqa; lifecycle: app-adapted; phase: baseline-complete; iteration: 1; same_failure_count: 0.
원본 .env/data/logs·3500/5501/live 및 실제 LLM/수집/거래/삭제 접근 금지. scratch OS sandbox만 실행.
사용자가 브라우저를 ego-browser로 지정. browser_applicability: required; browser_driver: ego-browser.
실제 Next VCP 화면 + 합성 API fixture(실제 parse_json_response 사용); 실제 모델/원본 저장파일은 검증하지 않음.

## 필수 행렬

| ID | 의도/사용자 모델 | setup·조작/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | required |
|---|---|---|---|---|---|---|---|---|
| V1 | 정상 사용자·세 provider | 합성75% recommendation→상세 각 탭 click | 세 탭75%, 실제사유 동일 | 미실행 | 없음 | 예정 | 대기 | yes |
| V2 | 누락/비수치/Infinity | parser 회귀 및 합성invalid→각 탭 | None/미산출, 배치 예외없음 | 미실행 | 없음 | 예정 | 대기 | yes |
| V3 | 실제0 | 합성0→각 탭 | 세 탭0%, 미산출과 구분 | 미실행 | 없음 | 예정 | 대기 | yes |
| V4 | raw cache·stale 후보 | 병합값없음+원시추천invalid→각 탭 | 미산출, 원시후보에서도0조작없음 | 미실행 | 없음 | 예정 | 대기 | yes |
| V5 | 실패/재시도 | fixture 차트503→정상200, 모달 재열기 | 실패안내 후 차트복구 | 미실행 | 없음 | 예정 | 대기 | yes |
| V6 | provider 실패·모델 전환 | 실제 analyzer fake transport tests | echo최대2회/repair/fallback/provider제약 보존 | 미실행 | 없음 | 예정 | 대기 | yes |
| V7 | 현재 엔진 진입 | 실제 MarketGate/grade/init_data tests | 실제 경로 통과; 옛등급7tests 삭제분 별도계수 | 미실행 | 없음 | 예정 | 대기 | yes |
| V8 | dirty/오도된성공/정리 | command exit/로그·SHA·package·ports·Space 검증 | 필수통과·실패원문보존·소유흔적정리 | 미실행 | 없음 | 예정 | 대기 | yes |

prompt injection/권한모드 전환은 이번 변경이 처리하지 않으므로 적용불가. 입력 문자열은 비신뢰 자료이며 실행하지 않음.
정체는 명령 timeout120~300초/소유PGID 종료. 최대5cycles/동일실패3회. skip을 통과로 세지 않음.
VCP-022 역사 자료/모의 노출 요구는 이 confidence 부분 검증으로 완료되지 않는다.

## Baseline

기존 관련90tests 통과. confidence RED8실패/36통과, status signature RED1실패: 새계약 미구현으로 예상실패.
최종 pytest2465/3skip, Vitest640/83files, typecheck/build exit0, lint0errors/184기존warnings. 브라우저 미실행, 완료 불가.

검증 URL: http://127.0.0.1:57960/dashboard/kr/vcp; Next57961; fixture57962. Space20/p1, 사용자 연속 라운드 전용.
