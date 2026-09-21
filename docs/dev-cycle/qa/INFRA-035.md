# UltraQA Report — INFRA-035

- QA 엔진(engine): Codex UltraQA
- lifecycle: app-adapted | phase: complete | iteration: 1 | same_failure_count: 0
- baseline: pytest 2279/3 skip, Vitest 459/67, Node build 3/0 skip, tsc 0, lint 0 errors/194 warnings 통과. 검증 소스 해시: ../evidence/test-isolation-20260909/review-input.json
- browser_applicability: not-applicable | browser_driver: none
- 호출부 근거: 수정은 npm/Node 검증 명령과 pytest DB fixture만 사용. 제품 UI·API·저장 계약 변경 없음.
- UltraQA Report: [묶음 범위 및 증거](../evidence/test-isolation-20260909/scope.md)
- 안전: 원본3500/5501/라이브·.env·data 쓰기 금지. 비밀 없는 scratch와 네트워크 차단 sandbox 사용.
- 목표: 기본 테스트와 빌드의 충돌 제거, 빌드/타입 검증 보존, 테스트 DB의 원본 경로 쓰기 방지.
- 중단: 같은 실패3회/최대5cycle. 명령 timeout60~300초, 소유 프로세스만 정리.

## 필수 행렬

| ID | 의도·사용자/공격자 | setup·명령 | 기대 신호 | 실제·결과 | 수정·증거 | cleanup |
|---|---|---|---|---|---|---|
| S-1 | 정상 개발자, 인접 회귀 | npm run test:build | 실제 빌드1회, 필수5경로, 타입 검사, Node3검사 exit0 | 실제 빌드1회·Node3/3·skip0·exit0 — 통과 | build-qa1.log.gz | 완료 |
| S-2 | 동시 작업/반복 실행 | 같은 scratch에서 npm run test:build와 npx vitest run 동시 실행2회 | 빌드3검사와 Vitest459개 각각exit0, 중복빌드 충돌 없음 | 동시2회 각각 빌드3/3·Vitest459/459·exit0; 겹침7.337초/6.408초 — 통과 | concurrency.json, build-qa1/qa2.log.gz, vitest-qa1/qa2.log.gz | 완료 |
| S-3 | 성공문구로 위장한 실패 | 임시 npm 대역이 성공문구 출력 후exit7, 실제 Node검증 실행 | 검증exit비0, 성공으로 오인 안함 | 가짜npm exit7 → 실제Node exit1·검사3개실패; 적대적문구는자료로취급 — 통과 | probe.log.gz | 완료 |
| S-4 | DB 쓰기 경로 회귀 | scratch data 쓰기 차단 상태에서 pytest tests/services/test_paper_trading_service.py | 86개 통과, data DB/WAL/SHM 생성0 | data쓰기차단 상태86/86·exit0, 파일목록불변; DB/WAL/SHM정리2회 후이웃파일보존 — 통과 | target.log.gz, target-data-result.json, probe.log.gz | 완료 |
| S-5 | dirty 원본/정리 | 원본 사용자package 해시·data WAL/SHM 이름해시 전후 대조, scratch프로세스 검사 | 불변, 소유프로세스0, scratch 제거 | 원본package·소스해시불변, 원본sidecar27396개 이름해시불변, 소유프로세스0·scratch삭제 — 통과 | cleanup.json | 완료 |

모든 행 required=예. CLI에 사용자 JSON/프롬프트/권한상태 입력을 받는 경로가 없어 해당 적대적 분류는 적용 불가.
기존 data 누적 파일 삭제는 INFRA-035의 별도 미결 항목으로 보존하며 이번 검증 성공으로 삭제 결정을 대체하지 않음.

## 실행 결과

- 필수 통과: 5/5. 미통과 없음. cleanup 완료.
- ULTRAQA COMPLETE: Goal met after 1 cycles

- QA 기준 커밋: `38fab479911e6ebde198841959e0d6c4e0c49fc3`. scratch 5개 파일 SHA 일치 확인.

## 명령·수정·잔여 범위

- 실행 완료: 2026-09-09 20:51 KST. 명령·timeout·종료 코드·실행 구간은 `../evidence/test-isolation-20260909/*.json`에 보존.
- `npx vitest run`: 459 passed / 67 files. `npm run test:build`: Node 3 passed / 0 skipped, 실제 빌드1회와 타입 검사. 두 명령 동시 실행을2회 수행해 각각exit0 확인.
- 전체 `pytest -q`: 2279 passed / 3 skipped. skip은 기존 수동2개와 시크릿 없는 격리 환경의 .env 대조1개.
- lint: 0 errors / 194 warnings. tsc: exit0. Python AST/Node 문법검사 통과. Python 전용 LSP는 사용할 수 없어 성공으로 세지 않음.
- 최초 기존 스모크의 동시 빌드 실패(exit1, Another next build process is already running)를 baseline.log.gz에 보존. 09-08의 과거 간헐 실패까지 같은 원인이라고 단정하지 않음.
- 리뷰에서 새 build 폴더가 ignore 대상인 결함을 발견해 build-checks로 변경. 최초 architect BLOCK과 최종 CLEAR 원문을 모두 보존. ponytail 재검토 SHIP, code-reviewer APPROVE.
- 이후 소스 변경 없음. QA 과정 제품 수정/반복 실패 없음. 명시한2회 동시 실행은 iteration1 안의 제한된 재현 검증.
- 실제 화면·API를 바꾸지 않는 테스트 CLI 범위이므로 agent-browser 적용 불가. 원본서비스 접속·시크릿복사·LLM호출·OMX상태조작 없음.
- INFRA-035의 누적 파일 정리 여부는 미결. 재발 방지 범위의 필수검증은 통과했으나 해당 TODO 전체 완료로 간주하지 않음.
- 원문 .log는 .log.gz로 손실 없이 압축. Windows checkout 호환을 위해 증거 파일 이름의 콜론은 하이픈으로 교체했으며 JSON stage 값은 실제 호출 그대로 보존.

## 2026-09-21 남은 처리 방침 확정

사용자의 승인 판단 위임에 따라 원본 누적 DB/WAL/SHM을 **보존**하기로 결정했다. 삭제·이동·재분류하지 않았고 현재 개수도 조사하지 않았다. 결정과 독립 문서 검토는 `evidence/test-isolation-retention-20260921/decision.md`에 있다. 과거 문서의 미결 표시는 당시 상태이며 이번 결정으로 해소한다.

기존 재발 방지 구현 이후 ticker 정규화 수정이 있으므로 전체 파일 불변을 주장하지 않는다. 현재 tmp 경로/연결 정리 구조를 검토했고 2026-09-21 원본 data 쓰기 차단 격리 pytest2448/3skip도 통과했다. 이번 후속은 문서 결정뿐이라 UI 실측 적용 대상은 아니다. 완료는 처리 방침 확정이며 원본 누적 파일 정리를 뜻하지 않는다.
