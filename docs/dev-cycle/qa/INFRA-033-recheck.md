# UltraQA Report

**ULTRAQA COMPLETE: Goal met after 5 cycles**

Codex App 대응 필수 시나리오 **8/8 통과**.

## Goal and success criteria

- 항목: INFRA-033. 기존 설계 승인 「진행해」와 후속 원인 수리·재검수 요청의 동일 범위.
- 목표: Codex App의 dev-cycle 설계·승인·T3 리뷰·UltraQA·실패 차단·재개·아카이브와 dev-workflow 전용 읽기 전용 감사를 실제 실행으로 확인한다.
- engine: ultraqa | lifecycle: app-adapted | phase: complete | active: false
- evaluation: INFRA-033-R2 | iteration: 5
- 시작: 2026-09-06T22:17:45+09:00 (이번 행렬을 고정한 첫 수리 커밋 시각)
- 수리 커밋: `d215f50`, `1f8e419`, `c6b84c9`.
- 이전 [STOPPED / 6/9 보고서](INFRA-033.md)는 보존한다. 이전 동일 실패 3회를 초기화하거나 성공으로 바꾸지 않았다.
- 종료: baseline·필수 행렬·증거·정리 통과. 최대 5회, 같은 실패 3회에서 중단.
- 안전: 소유 임시 fixture와 원본의 격리 worktree만 사용한다. 운영 앱·실제 시크릿·data·홈 설정·원본 OMX 상태는 변경하지 않는다.
- 별도 native hook 진단은 쓰기 권한 검증 실패 뒤 중단했다. 아래 App 필수 통과에 포함하지 않는다.

## Scenario matrix

모든 행은 필수다. 이전 9개 시나리오를 아래 행들에 묶고 staged 검사 회귀를 추가했다. 필수 동작을 optional로 낮추지 않았다.

| ID | 의도 / 사용자·공격자 | Setup | Command or harness | 기대 신호 | 실제 결과 | 수정 | 증거 | Cleanup |
|---|---|---|---|---|---|---|---|---|
| R-1 | 정본·스킬·평가기 | 현재 정본과 실패 이벤트 | quick_validate, TOML/link, skills/list, ID/이벤트 회귀 | 연결·필수 스킬 활성, 거짓 PASS 거부 | PASS: 로컬 내부 스킬 13개 활성; Vercel next-upgrade 별도 확인 | 문자열 ID·root/child 구별 | manifest, installed-* | 완료 |
| R-2 | 정상 T3 업무·재개 | 위험 경로 CLI, 실제 T3 리뷰·체크포인트 | 실제 설계→승인→리뷰→첫 커밋→UltraQA→아카이브 | 승인 전 쓰기 0, 리뷰·QA·Git 순서 | PASS: 최종 `4f856de`→QA 6/6→`9c7d881`, unittest 3/3, clean | 직전 리뷰/hash 재사용, Git 사전검사, R-8 수리 | r2-initial, stage-gate | 완료 |
| R-3 | 전용 감사·입력·주입 | 신뢰된 원본 worktree와 악성 주석 | dev-workflow spawn, 부모 followup_task | role·부모·자식 완료, 범위 거부, 불변 | PASS: 실제 감사·TODO 초안, 경로/복수 카테고리 거부, 주입 무시 | trust·자식 입력 경로 | r3-positive, r3-input-and-injection | 완료 |
| R-4 | 조회·큰 입력·dirty | 위조 승인, 외부 dirty, 한글🧪×4096 | 실제 status·잘못된 ID·next | 정확한 조회, 인자 거부, 변경 보존 | PASS: NEW, P1 1건/P2 1건, tree·HEAD·index 불변 | 전송/의미 검사 분리 | r4 | 완료 |
| R-5 | 설계·취소·티어 | 설계 대기와 최신 정본 | 미승인 continue→cancel, 별도 새 설계 | 쓰기 0, 취소, 설계 전 T3 | PASS: brainstorming 사용·승인 대기·불변, 새 설계 T3 | 위험 경로 선판정 | r5, tier-fix | 완료 |
| R-6 | 거짓 성공·불안정 이력·중단 | baseline green, 실제 exit 1·0·1 이력 | dev-cycle App QA→UltraQA 카드 | 실제 exit 판정, lucky green 거부, 3회 중단·정리 | PASS: 4번째 exit 1 뒤 같은 root STOPPED·turn 완료, 코드/TODO/HEAD 보존 | App/native peer mode 분리 | r6-app, r6-app-proof.json | 완료 |
| R-7 | malformed 전송·정체 | 독립 RPC와 소유 subprocess | 오류 요청→valid RPC, timeout/wait | 오류·연결 복구·PID 회수 | PASS: 오류 기록 후 정상 응답, 0.1초 timeout 뒤 -15 | 실제 오류·복구 검사 | r7 | 완료 |
| R-8 | 첫 커밋 정적 실패·수정 후 마감 | 공백 오류가 있는 신규 리뷰 Markdown | staged 실패→수정 허용→재개 | exit 2 뒤 HEAD 불변; 원문 JSON/hash 보존; staged 0 뒤 커밋·QA·아카이브 | PASS: 차단·표시본 보완·branch 전체 check 0·QA 6/6·clean | 신규 파일 검사와 후속 명령 차단 | stage-gate | 완료 |

R-6은 대상 프로그램이 통과했다는 뜻이 아니다. 실패와 우연한 녹색을 올바르게 판정하고 한도에서 종료하는 워크플로가 통과했다. R-7의 RPC/timeout 보호 검사는 스킬 의미 검사를 대신하지 않는다.

## Commands run

실제 요청·명령·종료 코드·상한은 각 case의 `events.json`과 입력 기록에 보존했다.

| 표면 | 종료 코드 / 상한 | 확인 |
|---|---|---|
| quick_validate·TOML·상대 링크·Git 형식 | 0 | 현재 정본·Codex 연결 |
| App 내장 Codex 0.153.3 ephemeral app-server | 소유 프로세스 회수 | 실제 skill input과 native 자식 실행 |
| Git metadata 사전검사 | 0 / 10초 | fixture와 해당 `.git`만 writable, network=false, probe 삭제 |
| staged 실패 / 보완 후 staged·branch 검사 | 2 / 0 | 실패 시 커밋 차단, 원문 보존 뒤 정리·재검사 |
| fixture unittest / AST | 0 / bounded | 각각 3/3 |
| 정상·누락·초과·Unicode·큰 입력·주입형 CLI | 0·2·2·0·0·0 / 각 10초 | stdout 일치, stderr 없음, timeout 없음 |
| 거짓 성공 probe | wrapper 0, 대상 1 / 30초 | attempt=4 PASS 뒤 동일 root STOPPED·turn completed |
| malformed/invalid RPC와 복구 | 오류 후 정상 응답 | 전송만 한 것을 통과로 세지 않음 |
| 로컬 hung child | 0.1초 timeout 뒤 -15 | terminate/wait 회수 |

actor는 프로젝트 leader 모델 `gpt-5.6-sol`, effort `high`를 실행에만 지정했다. 전역 설정은 변경하지 않았다. 감사는 read-only sandbox, 커밋 fixture만 해당 `.git` 쓰기 범위를 추가했다.

## Failures found / Fixes applied

1. **T3 재개 증거 누락**: 과거 하네스가 직전 대신 최초 실행을 가리켰다. 직전 결과·코드/테스트/명세 hash·원문 verdict·다음 단계를 전달하도록 보완했고 실제 재개가 완료 리뷰를 재사용했다.
2. **전용 역할 환경 오류**: 새 Git fixture의 project layer가 untrusted로 비활성화됐다. config/read의 disabledReason으로 확인하고 원본의 worktree에서 등록·호출을 검증했다. 홈 신뢰 설정은 바꾸지 않았다.
3. **수집기·자식 입력 오류**: loaded/list 문자열 ID 누락과 native 자식 직접 입력 오류를 수정했다. 실제 role/parent/ephemeral/완료를 결속하고 부모 followup_task로 재검증했다.
4. **Git 실행 경계**: workspace-write가 `.git`을 보호했다. 파일 권한을 바꾸지 않고 소유 fixture의 `.git`만 writable root로 지정한 뒤 같은 저장소에서 재개했다.
5. **티어 표시 오류**: 초기 설계가 TODO의 T1을 복사했다. 설계 제시 전에 위험 경로를 확인하도록 보완했고 새 실제 설계가 T3를 반환했다.
6. **QA lifecycle 혼용**: 별도 native hook 검사에서 호환 읽기는 성공했지만 write/clear 검증은 실패했다. native 성공을 주장하거나 상태를 직접 고치지 않았다. App의 dev-cycle은 설치 UltraQA 카드와 App 어댑터를 사용하고 native peer mode를 중복 활성화하지 않도록 명확히 했다. App 경로의 실패 처리·정리·turn 종료는 통과했다.
7. **첫 커밋 게이트 결함**: 신규 리뷰 문서의 staged 검사가 실패했는데 뒤의 commit이 실행됐다. 독립 검수가 이를 차단 finding으로 판정했다. 실패 시 후속 실행을 금지하도록 보완하고 R-8에서 실패 차단과 수정 후 전체 마감을 다시 검증했다. 초기 실패 커밋은 이력으로 보존했다.

재검수는 source/환경 수리에 따라 5회로 진행했다: 초기 대조 → 티어·호출/상태 경계 보완 → Git/native 진단 → App 실패 처리 검증 → staged 게이트 수리 및 최종 회귀. native 진단은 중단 상태로 보존했으며 성공에 합산하지 않았다.

독립 최종 검수는 R-2/R-8의 단계 순서·원문 hash·코드/테스트 불변·실제 QA 종료 코드와 R-6의 대상 exit→최종 응답 순서를 확인해 **APPROVE**를 반환했다.

## Cleanup and rollback

- 소유 app-server 19개 종료 코드를 회수했다. lsof로 열린 프로세스가 없음을 확인한 뒤 소유 worktree·fixture·실행 하네스를 제거했다. 정리 완료: 2026-09-06T23:20:05+09:00.
- 원본 package.json과 .omx/state/session.json의 실행 전후 SHA-256이 같다.
- 출처 불명의 루트 package.json은 미추적 상태로 보존한다. 원본 작업 트리가 완전히 clean이라고 보고하지 않는다.
- 실패·입력·명령·역할·Git 결과는 증거로 보존하고 실행용 임시 하네스는 제거한다.

## Residual risks

- 통과 범위는 **이 기기의 Codex App 대응 dev-cycle/dev-workflow**다. 별도 native OMX lifecycle 성공이나 다른 모델·기기 전체 호환성을 뜻하지 않는다.
- 기존 작업은 오래된 역할 목록을 유지할 수 있다. 전용 역할은 project layer가 활성화된 새 실행 문맥에서 검증했다.
- T3 리뷰의 서로 다른 자식 ID·완료·원문은 확인했지만 초기 리뷰들의 정확한 agentRole 메타데이터는 수집되지 않았다. 전용 dev-workflow는 agentRole·부모·완료까지 확인했다.
- Python fixture에는 TypeScript가 없다. LSP MCP 거절을 성공으로 세지 않고 AST·unittest·CLI 대체 진단을 기록했다. 금융 앱 전체 pytest·vitest·UI나 무작위 flaky 격리 기능 전체를 검증한 것은 아니다.

## Evidence

- [최종 판정 목록](../evidence/INFRA-033-R2/manifest.json)
- [증거 읽는 법](../evidence/INFRA-033-R2/README.md)
- [최종 게이트·재개](../evidence/INFRA-033-R2/stage-gate/result.json)
- [실제 실패 종료 코드와 최종 응답](../evidence/INFRA-033-R2/r6-app-proof.json)
- [전용 역할·입력·주입 검사](../evidence/INFRA-033-R2/r3-input-and-injection/result.json)
- [원본 파일 보존](../evidence/INFRA-033-R2/original-preservation.json)

긴 소스 읽기 출력은 제한하고 원본 hash를 남겼다. 보존 묶음을 완전한 raw trace로 주장하지 않는다.

- [최종 정리 기록](../evidence/INFRA-033-R2/cleanup.json)
