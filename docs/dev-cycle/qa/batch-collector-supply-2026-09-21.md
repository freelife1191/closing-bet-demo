# UltraQA Report

대상: INFRA-030 / FLOW-014. engine=ultraqa, lifecycle=app-adapted.
phase=ready, iteration=0, same_failure_count=0, cleanup=pending.
브라우저: required, 사용자 지정 ego-browser. 기존 종목 상세 UI의 데이터 계약 변경이므로 필수.
기준: base63b1db0에서 변경, 제품·계획 해시는 evidence/collector-supply-20260921/review-frozen.json.
첫 구현 커밋은 리뷰 통과 후 기록하며 아직 브라우저 실측을 시작하지 않았다.

## 목표와 경계

공개 수집기 단일화와 과거 날짜 동작을 보존하고, 개인 값0/자료없음과 조회 경합·성능 개선을
실제 수정 코드에서 확인한다. 필수9행·baseline·정리 모두 통과해야 완료한다.
최대5cycle/같은실패3회에서 미완료로 중단한다. fixture/명령 timeout은 실행 JSON에 남긴다.
원본3500/5501/live, 실제 .env/data, 실제 인증/LLM/수집/설정저장/계좌변경/삭제는 제외한다.
scratch의 원시 합성 공급자 → 실제 parser/service/SQLite → 합성 HTTP → 실제 Next UI를 검사한다.
시장 API 성능이나 운영 인증을 검증했다고 보고하지 않는다.

## 필수 행렬

| ID | 의도·사용자/오류 모델 | 설정·실행 | 기대 | 실제·증거 | 수정·정리 |
|---|---|---|---|---|---|
| Q1 | 운영 호출자·import 순서 변경 | package/subprocess 및 KRX 날짜/캐시 회귀 | 동일 클래스·동일 날짜/결과·설정 경로 | preflight55 + 추가 import, 최종 확인 대기 | root lazy export, 소유 임시자료 정리 |
| Q2 | 정상/불완전/비유한 개인 수급 | 실제 Toss/pykrx/CSV 정규화·fixture probe | 0,+1억,-1억,None 구분; 누락은 역산하지 않음 | fixture-preflight6모드 일치, 최종 대조 대기 | 개인 helper, synthetic data |
| Q3 | 구형/신형 캐시 | 실제 reference/collector/상세 SQLite roundtrip | 구형0은None, 검증된 새0은0 | 회귀·fixture-preflight 통과, 최종 대조 대기 | marker decode, 원본 저장소 미변경 |
| Q4 | 중복 요청·중단·stale 작업 | Event/Future/가상clock 경합 검사 | 같은key1회,60초재시도,clear 전 작업 publish0회 | batch-first 및 batch-extended 로그 | 세대/TTL, 대기자·소유작업 회수 |
| Q5 | 대량 경계·중복 티커 | cutoff/가격부족/VCP false/순차-배치 대조 | 범위밖조회0회, 결과와 순서 동일 | batch-extended15검사, 최종 대조 대기 | pandas 준비는 호출스레드 |
| Q6 | 느린 공급자 | 600건×50ms, 순차3회/배치3회, 실제 cache 포함 | 동일600결과·최대4·중앙값50%이하 | 35.673345→9.883845초, 비율0.277065, bench-final.log | 각 subprocess60초, 소유 임시경로 제거 |
| Q7 | 실제 UI 정상·자료없음 | ego: 상세 모달 0/+1억/-1억/누락/invalid/legacy | API와 개인 행 표시 일치, 새콘솔예외 없음 | 미실행 | 새 Space 하나, 이미지 직접 열람 |
| Q8 | 조회 실패 후 복구 | ego: 닫기→fixture503→재열기→정상→재열기 | 실패 문구 후 정상값, 페이지 reload 없음 | 미실행 | 같은 모달 인스턴스 자동갱신으로 주장하지 않음 |
| Q9 | 오해 가능한 성공·잔재·dirty 파일 | Next진단/로그종료코드/SHA/포트/PID/Space검증 | 필수오류0·소유서비스종료·원본packageSHA유지 | 미실행 | hook/OMX 상태 미활성·미조작 |

## 정적 검증과 개발 중 실패

baseline pytest2422/3skip, Vitest629. 현재 pytest2449/3skip, Vitest634/83파일,
build3/3, typecheck0, lint0오류184경고. 각 명령 원문·시각·종료코드는 evidence 경로 JSON/log에 있다.
skip3은 수동 Gemini2건과 실제 .env 없는 환경1건이다. 필수 행 통과로 세지 않는다.

개발 RED: 공개/하위 KRX identity1실패 → 단일화; import 순환 collection오류 → root지연노출;
개인 정규화/legacy0 5실패 → nullable/marker; TTL/clear/data_dir 3실패 → 공유 캐시;
batch API/cutoff2실패 → 제한된 병렬화; UI null/zero2실패 → 구분표시.
옛0표시 검사 정정 시 selector 이름을 잘못 골라 한 단언이 남았으며, 원문 오류를 확인해 수정했다.
테스트 기대 변경은 승인한0/None계약에 한정하며 외국인/기관 값과 점수 단언은 유지했다.
제거된 private 테스트24개는 retired-tests.md에 이유와 대체 계약을 남겼다.

## 알려진 한계

최초 서로 다른 종목 N개의 공급자 요청은 N개일 수 있다. 단축 수치는 합성 지연 하네스이며
실제 시장 응답 속도가 아니다. 개별 HTTP 조회에 전체 deadline을 새로 보장하지 않는다.
review 도구는 native 독립 레인과 T3 체크리스트의 App 대응이며 외부 gstack/Claude CLI
런타임·홈 기록·텔레메트리는 실행하지 않는다.

## 최종 판정

미완료. 코드 APPROVE / 구조 CLEAR / T3 APPROVE, 최종29경로동결 aee99f...와 실행scratch 일치. 필수 브라우저 행·정리 확인 후 완료 판정한다.

추가 보완: 날짜 집합 불일치 RED2, 상세소수 RED2, KRX개인캐시 RED5를 실제 재현해 수정했다. 공통 decoder 정리 중 import logger 순서가 잘못되어 collection55오류/fixture실패가 났으며 원문 보존 후 수정, 마지막 전체2449/3skip과fixture를 다시 통과했다.
