# SDD ledger — plan: docs/dev-cycle/evidence/performance-20260918/plan.md

| Tasks | Interface/preflight | Finding |
|---|---|---|
| 1→2 | D roiByGrade, recentWinRate nullable, recentClosedCount, consecutiveLosses | explicit identical fields |
| 1/3 | existing metrics versus display status/policy | thresholds unchanged; separate files |
| 2/3 | separate Next pages, shared static/browser verification | no source overlap |
| 1 | regression→boundary and KPI→cache version | clear nonempty invalid contract; preserve no data |
| 2 | fake API tests→real UI render | no new component framework |
| 3 | six-state tests→mapping/copy | align legacy mock vocabulary only |
| 4 | source hashes→ordered reviews→QA→archive | repository dev-cycle gates preserved |

Ruling: repository develop workflow and existing original-file preservation govern editing; execution only in sandbox git-archive scratch, not an extra implementation branch. Only parent executes tests and commits. Scoped task quality/spec checks integrate with required ponytail→code-review+architect→T3 review and are not skipped. No user reapproval needed for same-scope repairs.

Task 1: pending plan critic. Baseline checks running in isolated scratch.

Ruling: 사용자 최대 묶음 처리와 AGENTS의 독립 native lane 지시에 따라 고정된 KPI 인터페이스의 독립 파일 3레인을 병렬화한다. SDD의 일반 순차 구현 권고 대신 명시 소유권과 부모 단독 실행·커밋, 필수 독립 리뷰로 충돌을 제어한다. 미판정 계약은 임의로 바꾸지 않고 리더에 보고한다.
Task 1: RED 7fail/1pass 확인, implementation 중.

Task1 구현/부모검증: 신규10pass + 기존인접53pass. 실제누적route24/49/2.04/recent30/연패7·no-closed·empty·page-cache probe PASS. Task2 RED3fail 관측, implementation 진행. Task3는 VCP 전용두tooltip문구를승인범위에서추가하고값/정책그대로.

Task1: implemented, source3files+newtests13PASS, fullpytest2310/3skip.
Task2: implemented, D/total/recent/null/samplecount/page-local filters/StrictMode stale guard/ROIheight. RED→GREEN행동확인, fullVitest505/71.
Task3: implemented, statuses/unknown-ownkey/real policy/landingexpectancy. mockroutePASS.
Review initial: ponytail SHIP(interface제거철회); code-review APPROVE; architect WATCH범위/표본/경합/높이보완. 영향review pending, T3 deep pending.
Last static: build-review2 actual3/3, latesttestonlyhelper축약뒤vitest-final3/lint-final3/typecheck-final3 running. Production14manifest에서PY코드/홈/VCP/랜딩은초기review와동일.
QA: iteration0, no services/browser started; firstcommit notmade. Source14allowed, rootpackagepreserve. Scratch review-input.json.

## 최종 체크포인트
앞선 pending/running은 각 시점 이력이다. T3 warmSQLite 회귀와 안내 공식 수정 후 모든 영향 리뷰 승인. 구현 ef7641c, QA2 툴팁 수정46dd0a6. pytest2314/3skip·Vitest506/71·lint0/190warning·build3/3·tsc0. 사용자 지정 ego-browser로 필수10/10 통과, task.finish 1회·소유서버/scratch 정리 완료. 예상 밖 인증 요청 주체·세션 영향 미확정과 fixture realtime405를 보고서에 기록했다. 최종 문서 검수와 아카이브만 남음.

최종 verifier PASS—APPROVE. 다섯 TODO 완료 아카이브 및 집계 반영. 잔여38건.
