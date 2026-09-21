# UltraQA Report

- 항목: JONGGA-033·018; 승인:2026-09-21 사용자「승인」(직전 bounded 설계).
- engine: ultraqa; lifecycle: app-adapted; phase: complete; iteration:3; same_failure_count:0.
- browser_applicability: required; browser_driver: ego-browser (사용자 지정 우선).
- 진입: http://127.0.0.1:57950/dashboard/kr/closing-bet (gateway→Next57951/API합성fixture57952).
- 소유scratch와시각: evidence/jongga-metrics-20260921/review-input.json. 원본.env/data/3500/5501/live 접근금지.
- UI와 Toss parser/detail service/cache는 실제코드. 외부 공급자만 합성. 실제종목회계기간/실서버 검증 아님.
- EPS는 미확인, 재무기간은 값과같은행만 연결. 기존점수·등급·원본파일 보존. 모든행 필수.

| ID | 의도/모델 | setup·명령/하네스 | 기대 | 실제·수정·증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|
| Q1 | 공급자 기간 누락·객체·긴값 | pytest parser→detail, Vitest raw/processed | 짝이 맞는 기간만 전달,오류없이 미확인 | 통과 — parser/detail23·전체2452,Vitest raw/processed 회귀; 값없는기간 RED1→GREEN | 제거완료 | 예 |
| Q2 | EPS/순이익 부호가 다른 정상조회 | ego known 모달·PER tooltip | EPS-266,순이익26억,2026Q1/2025,EPS미확인,음수PER설명 | 통과 — ego-known.json·ego-detail-known.png: -266/26억·2026Q1/2025·PER툴팁 | finish완료 | 예 |
| Q3 | 구형 SQLite캐시/손상 기간 | ego legacy/invalid 실제parser·service | 재무3개기간미확인,EPS보존,연간추정없음 | 통과 — ego-legacy/invalid.json: 기간3개미확인·값보존·구형SQLite경유 | 제거완료 | 예 |
| Q4 | 과거점수/현행점수 비교 | ego known9/legacy8/invalid7 카드·tooltip | +9/+8 과거값·총점16/15보존,+7/7·총점14,세부상한오해없음 | 통과 — ego-matrix.json: 9/16·8/15·7/14,카드3PNG·tooltip실측 | finish완료 | 예 |
| Q5 | 조회실패후복구 | 같은page모달닫고error503→known재열기 | 오류표시후값복구,페이지오류없음 | 통과 — ego-recovery.json: 503→200·동일timeOrigin·오류배열0 | 제거완료 | 예 |
| Q6 | 인접기능회귀·거짓성공방지 | 전체pytest/Vitest/typecheck/lint/build·Next진단 | 실제종료코드0,skip/경고별도계수,리뷰통과 | 실패 → 고침 — harness준비/observer실패보완; 최종2452/640·Next진단오류0 | 종료완료 | 예 |
| Q7 | dirty파일/격리/정리 | hash대조·요청기록·PID/cwd/port검사 | package불변,원본접근0,소유자원정리 | 통과 — cleanup.json·ego-finish.json·request-audit.json·6SHA일치 | 정리완료 | 예 |

정상·누락·손상·stale cache·재시도·dirty·timeout/exit/부분로그를 포함한다.
LLM/prompt 실행기·사용자파일경로·취소명령을 다루지 않아 injection 지시실행/경로이탈/CLI취소는 적용불가.
실제자격증명·거래·설정저장·수집은 금지하고 합성provider로 대체한다.
각명령timeout은 run_check.py, 최대5cycle/동일실패3회. 실패시원인기록후제한재시도.

## 결과
필수7/7통과. 미통과없음. cleanup완료. ULTRAQA COMPLETE: Goal met after 3 cycles

## 실행·리뷰·근거
- 구현기준9c69e9a,6파일frozen SHA a5044e74b6669239aa63c3ff7ab6fc7d758db80f55270b5f7ab77206298e2172.
- pytest2452 passed/3skipped(수동Gemini2,실제.env부재1); Vitest640/83files;typecheck0;lint0errors/184warnings;build검사3/3.
- 각명령argv/timeout/exit는evidence/jongga-metrics-20260921/*.json. raw로그는*.log.gz와raw-index.json으로원본보존.
- ponytail독립SHIP,추가한줄delta는threadlimit으로리더대체검토;code-review최종APPROVE,architect최종CLEAR(기존독립agent역할프롬프트적용).
- 낮은확신리뷰도반영: 해당지표누락/None이면기간제거. RED1→23target/2452전체PASS.
- App대응실행이며native OMX상태수명주기는실행하지않음. ego-driver는사용자지정.
- QA초기서버준비실패9건502/observerundefined실패와복구를qa-failures.md에보존. 성공으로숨기지않음.
- 최종UI검증은실제Next페이지·실제Tossparser/detail/cache,외부공급자합성.실제수집/LLM/원본data는접근하지않음.
- 최종gatewayAPI48기록중20036,준비중gateway실패9,의도5033. 최종행렬예상외오류0.
- page observer는설치후상호작용범위만. 초기탐색은Next의get_errors/get_compilation_issues로별도검증.
- 최종PNG8개직접열람:카드known/legacy/invalid,detail3개,recovery2개.
- Space18 finish1회완료. fixture48546→50901,Next48607,gateway48660 소유cwd/PGID확인후종료.57950/51/52닫힘.
- scratch제거,root/scratch/9c69e9a6파일해시일치,기존root package.json해시보존.

## 한계
EPS의실제회계기간/해당종목부호불일치원인은확정하지않았다. 승인설계대로미확인상태를명시한다.
기간없는구형캐시도추정하지않으며캐시삭제/원본재계산은없다. 보너스>7만구분하며역사적생성버전을추정하지않는다.
데스크톱변경영역검증이며전체앱·모바일디자인검사가아니다.
