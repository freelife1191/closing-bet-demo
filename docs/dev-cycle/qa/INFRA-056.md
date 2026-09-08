# UltraQA Report

## 목표·승인·실행 경계

- engine: ultraqa
- lifecycle: app-adapted
- phase: ready
- iteration: 2
- same_failure_count: 0
- active: true
- 승인: 2026-09-08 대화의 INFRA-056 bounded/T3 제안에 사용자 「진행해」.
- baseline: 49f5264. pytest1996 PASS/3skip(수동Gemini2/격리.env없음1), vitest373 PASS/57files.
- browser_applicability: required
- browser_driver: agent-browser
- 실제 진입: /dashboard/kr 관리자 주기 선택 → /api/kr/config/interval POST → 실제 Flask 저장 → 신규 Flask 기동 GET.
- 격리: 독립 develop clone, 가짜 .env/계정/NextAuth, 외부 outbound 차단. 원본 .env/data/3500/5501/라이브 요청·실제수집/LLM/발송/거래/운영재시작 금지.
- 상한: QA최대5회/같은실패3회, 정적480초/브라우저명령60초+kill5초, fixture20분.
- native .omx 상태는 읽거나 쓰지 않는다. 이 문서는 App 대응 실행 상태다.

## 필수 행렬

| ID | 의도·모델 | setup/실행 surface | 기대 | 실제 | 수정 | 증거 | cleanup |
|---|---|---|---|---|---|---|---|
| S-1 | 관리자 정상 저장·재기동 | 실제 UI30→15, Next/Flask 요청, backend process 교체후 reload | POST200, 파일15/0600, 새PID의GET15·UI15 | 미실행 | 경로/잠금 | browser+metrics | own server/clone |
| S-2 | 비관리자·권한철회 | viewer로그인, admin화면열린상태권한철회후 변경 |403,파일/runtime불변,설정컨트롤비노출/권한안내·값복원 | 미실행 | 기존gate유지 | browser+metrics | own cookies |
| S-3 | 저장 실패·복구 | 기존UI15, os.replace ENOSPC 경계대역으로30설정, 대역해제재시도 |500,파일/runtime/UI15유지,재시도200 | 미실행 | 저장후적용 | browser+metrics | fault removed |
| S-4 | 파일/입력 경계 | pytest 실제tmp.env, missing/empty/중복/quoted/export/multiline다른값,invalid범위 |대상키1개/다른값보존,invalid400/쓰기0 | 미실행 | parser재사용 | pytest | tmp_path |
| S-5 | 링크·I/O 경계 | 실제tmp심볼릭링크.env/lock,읽기·replace실패 |링크거부/원본보존/runtime0,실패후재시도성공 | 미실행 | 기존보호재사용 | pytest | tmp_path |
| S-6 | 두 writer·중단복구 | multiprocessing 공통.env저장과주기저장,락보유child종료/재시도 |두변경보존,잠금해제/자식exit확인,동일workerapply순서일치 | 미실행 | 공통잠금 | process probe | owned child |
| S-7 | 격리·비밀·오류·정리 | git추적.env검사,가짜sentinel 로그/API/번들검색,화면snapshot/png열기,console/errors,sourceSHA |비밀노출0,예상실패만,원본package불변/own프로세스·temp제거 | 미실행 | 없음 | safety+cleanup | own scope |

모든 행 필수. HTTP만으로 S-1..3 UI를 대체하지 않는다. UI없는 파일경계/프로세스경합은 pytest/CLI로 직접 실행한다.
잘못된 JSON/Unicode와 경로형입력은 interval정수변환 및범위 검사 경계에서 검증한다. 이 API는 LLM/프롬프트를 처리하지 않으므로 prompt injection은적용불가. 재시도/중단은 S-3/S-6에 포함.
기대된400/403/500은 보존/복구와 함께 판정하며 exit0이나 성공문구만으로 완료하지 않는다.

## 정리와 최종 판정

미실행. 필수행렬·정적검증·리뷰·정리 완료 뒤에만 완료로 기록한다.

## 정적검증·리뷰 진입 증거

- 수정전 경로/중복키 재현 exit1→수정후3조건PASS. inf입력 OverflowError RED→400 GREEN.
- pytest2027 PASS/3skip, 관련83/동결32/오류보강51/최종테스트안전19 PASS. vitest373 PASS/57files(Next build smoke포함), typecheckPASS,lint0errors/기존199warnings. frontend입력동일해시로결과유효확인.
- 독립 code APPROVE/architecture CLEAR/security APPROVE. ponytail3줄삭제, 오류반사 LOW1을보강. T3심층검토의테스트안전대역복원까지완료.
- S-4/S-5 정적동작검사통과. S-6 실제multiprocessing 정상두writer0/0, killowner -15/0, 두값보존과잠금대기PASS.
- 첫process하네스는kill된child의Event를finally에서다시set해sem_wait에멈췄다. parent만종료(exit-15), tracker정리후 해당Event재조작을없애고30초상한을둔재검증은2.45초exit0. architect가제품flock아닌하네스정리교착으로진단했다. 실패원문·OS샘플·구/신하네스보존.
- iteration2는이하네스실패수정후회차. 미해결같은실패0. 실제브라우저는다음단계에서실행한다.
