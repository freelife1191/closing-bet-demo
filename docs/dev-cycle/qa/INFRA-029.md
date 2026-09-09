# UltraQA Report

# INFRA-029

engine: ultraqa
lifecycle: app-adapted
phase: complete
iteration: 1
same_failure_count: 0
active: false
cleanup: complete
browser_applicability: not-applicable
browser_driver: none

기준: 승인된 scheduler-truthfulness 계획. INFRA-029는 내부 배치의 로그만 변경하며 API/상태 반환은 변경하지 않는다. 웹 진입 변경은 INFRA-019 행에서 실제 랜딩으로 확인한다.

안전 경계: 원본3500/5501/live/.env값/data쓰기/실제LLM·수집·발송·거래·설정·삭제 금지. 신규 namespace만 사용. 5 cycles 또는 같은 실패3회 상한. baseline pytest2249/3skip, Vitest424/59files.

| ID | 의도·모델 | setup | command/harness | 기대 신호 | 실제 결과 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 정상 운영자 | 실제 run_daily_closing_analysis/run_jongga; 외부 적재/발송만 대역 | qa/scheduler_probe.py chain | 네 단계 → 알림 → 전체 완료, 상태 finally 해제 | PASS — 실제 체인 네단계→알림→성공, finally해제 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-chain-result.json normal | 정리 완료 | yes |
| S2 | 부분실패/거짓 성공 | 주가/수급/VCP/종가 단일 실패 및 복합 실패 | qa/scheduler_probe.py chain | 전체 완료 로그 없음, 실패 단계 나열, 종가 성공이면 앞 실패와 무관하게 기존 알림조건 유지 | PASS — 단일4/복합실패에전체성공없음, 단계나열 및알림조건보존 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-chain-result.json prices/inst/vcp/jongga/all-false | 정리 완료 | yes |
| S3 | 예외/오염 로그 | 각 단계·발송 예외; Unicode·skip QA 같은 문자열은 데이터 | qa/scheduler_probe.py chain | 에러 로그, 전체 성공 없음, 이후단계 기존 중단 계약, finally 해제; 문자열을 실행하지 않음 | PASS — 다섯외부경계예외, Unicode/지시문같은문자열은로그자료만, 상태해제 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-chain-result.json exception-* | 정리 완료 | yes |
| S4 | 재실행/낡은 상태 | 실패 뒤 정상 재실행; None 호환 | qa/scheduler_probe.py chain | 이전 실패가 새 성공에 섞이지 않음; 앞 세단계 None 기존 성공호환, 종가결과False 알림미호출 | PASS — 앞3None호환 및 실패후정상재실행 성공, 종가False/None미통과계약은단위검사보강 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-chain-result.json legacy-none/resume-normal + green-scheduler.log.gz | 정리 완료 | yes |
| S5 | 정리/프로세스 경계 | 명령 timeout60초/고유 fixture | 하네스 종료 및 ownership cleanup | exit0과 자체 기대검사 모두통과; 소유프로세스 종료, 원본불변 | PASS — 60초이내exit0/자체단언pass, 실행프로세스종료; clone 통합·제거 완료 | 제품 수정 없음 | evidence/scheduler-truthfulness-2026-09-09/qa-chain.json + runtime-cleanup.json + cleanup.json | 정리 완료 | yes |

비적용: 새 JSON·경로·플래그 파서가 없으므로 malformed JSON/경로이탈 제품 행은 없음. UI에는 외부 텍스트 입력 없음. 모델 출력 실행 경계 변경 없음. 명령 timeout 및 테스트 flake는 실행 로그로 별도 판정한다.

source_commit: 3853de87b3f62018fbbb7d6466379d0a40158bea
검증 URL: http://127.0.0.1:57272/
namespace: devcycle-scheduler-ta7kuvwh

## 실제 실행과 제한

첫 커밋3853de8의 불변 소스에서 iteration1 수행. agent-browser 실제 Next페이지, 독립 subprocess 실제스케줄/체인 실행. 하네스 원본과 명령별 종료코드/timeout/로그를 증거 폴더에 보존했다. 필수5/5의 동작은 통과했고 런타임/namespace/profile을 정리했다. clone 통합·제거와 원본 파일 보존까지 확인했다.

브라우저: GET24건, 본문/자산/세션 정상. 외부font는안전설정상차단했고 favicon.ico는기존404라 아이콘자산성공을주장하지않는다. 콘솔warning/error0, 페이지error0, Next compilation/runtime0. 스크린샷7개를실제로열었고 잘못된스크롤1개는통과증거에서제외했다. viewport변경뒤ref갱신과textContent.trim 누락을하네스오류로고쳐재관측했다. 제품코드수정/검증기대완화없음.

범위 밖: 랜딩의 종가+9/-5·15일보유/기대수익 예시는JONGGA-036에 별도등록. 이번S3는탭전환과인접요소유지검사이며모든전략수치정합성을통과시킨것이아니다.

ULTRAQA COMPLETE: Goal met after 1 cycles

완료 확인: 2026-09-09 15:13 KST. 필수 5/5 통과. `../evidence/scheduler-truthfulness-2026-09-09/cleanup.json` 및 `integration.json` 참조.
