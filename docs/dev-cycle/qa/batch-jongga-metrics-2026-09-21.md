# UltraQA Report

- 항목: JONGGA-033·018; 승인:2026-09-21 사용자「승인」(직전 bounded 설계).
- engine: ultraqa; lifecycle: app-adapted; phase: baseline; iteration:1; same_failure_count:0.
- browser_applicability: required; browser_driver: ego-browser (사용자 지정 우선).
- 진입: http://127.0.0.1:57950/dashboard/kr/closing-bet (gateway→Next57951/API합성fixture57952).
- 소유scratch와시각: evidence/jongga-metrics-20260921/review-input.json. 원본.env/data/3500/5501/live 접근금지.
- UI와 Toss parser/detail service/cache는 실제코드. 외부 공급자만 합성. 실제종목회계기간/실서버 검증 아님.
- EPS는 미확인, 재무기간은 값과같은행만 연결. 기존점수·등급·원본파일 보존. 모든행 필수.

| ID | 의도/모델 | setup·명령/하네스 | 기대 | 실제·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| Q1 | 공급자 기간 누락·객체·긴값 | pytest parser→detail, Vitest raw/processed | 짝이 맞는 기간만 전달,오류없이 미확인 | 미실행 | scratch | 예 |
| Q2 | EPS/순이익 부호가 다른 정상조회 | ego known 모달·PER tooltip | EPS-266,순이익26억,2026Q1/2025,EPS미확인,음수PER설명 | 미실행 | space | 예 |
| Q3 | 구형 SQLite캐시/손상 기간 | ego legacy/invalid 실제parser·service | 재무3개기간미확인,EPS보존,연간추정없음 | 미실행 | fixture | 예 |
| Q4 | 과거점수/현행점수 비교 | ego known9/legacy8/invalid7 카드·tooltip | +9/+8 과거값·총점16/15보존,+7/7·총점14,세부상한오해없음 | 미실행 | space | 예 |
| Q5 | 조회실패후복구 | 같은page모달닫고error503→known재열기 | 오류표시후값복구,페이지오류없음 | 미실행 | fixture | 예 |
| Q6 | 인접기능회귀·거짓성공방지 | 전체pytest/Vitest/typecheck/lint/build·Next진단 | 실제종료코드0,skip/경고별도계수,리뷰통과 | 미실행 | ownprocess | 예 |
| Q7 | dirty파일/격리/정리 | hash대조·요청기록·PID/cwd/port검사 | package불변,원본접근0,소유자원정리 | 미실행 | allowned | 예 |

정상·누락·손상·stale cache·재시도·dirty·timeout/exit/부분로그를 포함한다.
LLM/prompt 실행기·사용자파일경로·취소명령을 다루지 않아 injection 지시실행/경로이탈/CLI취소는 적용불가.
실제자격증명·거래·설정저장·수집은 금지하고 합성provider로 대체한다.
각명령timeout은 run_check.py, 최대5cycle/동일실패3회. 실패시원인기록후제한재시도.

## 결과
필수7행 미실행. baseline 진행중. cleanup 미완료. 완료주장없음.
