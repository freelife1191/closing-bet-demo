# UltraQA Report

## Goal and success criteria

- 목표: dev-cycle/dev-workflow가 기존 웹 UI와 연결된 backend 변경도 agent-browser 실측에 연결하고, 실제 data-status 발송 흐름으로 검증한다.
- 사용자 요청: skill-creator로 누락 원인 확인·규정 보완·agent-browser 실측 수행.
- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 2 | active: false | same_failure_count: 0
- browser_applicability: required | browser_driver: agent-browser
- 기준 앱 소스: 366d5f9. 업무 코드 변경 없이 독립 clone의 실제 Next 화면·실제 Flask message route 사용. 조회 데이터와 외부 Messenger만 대역.
- 안전: 원본3500/5501/live·실제.env/data·실제OAuth/발송/LLM/설정/거래 조작 금지. 전용 namespace/session·가짜JWT·임시 저장소 사용.
- 상한: CLI60초/상태대기30초/전체서버20분, 최대5cycles·같은실패3회. 필수미통과시완료금지. native OMX 상태변경없음.

## Scenario matrix

| ID | 의도/모델 | setup/command | 기대 | 실제 | 수정 | 증거 | cleanup | 필수 |
|---|---|---|---|---|---|---|---|---|
| B1 | 워크플로 소비자 | 독립 agent가 backend-only 웹/API, pure CLI, browser unavailable 의뢰 판정 | 웹은브라우저필수,CLI근거제외,도구없음BLOCKED | 통과: 웹필수·CLI제외근거·도구불가BLOCKED | 규정 연결 | forward-test | 읽기전용 | 예 |
| B2 | 관리자 취소 | 실제 페이지 open/snapshot·발송버튼·취소 | 확인모달표시후취소,POST0·발송0 | 통과: 확인모달취소후POST0/발송0 | 없음 | snapshot/요청 | 전용세션 | 예 |
| B3 | 관리자 정상발송 | 다시발송·확인 | 실제POST JSON null날짜→200,성공모달·대역발송1 | 통과: JSON null날짜·200·성공모달·발송1 | 없음 | 화면/서버기록/이미지 | 임시guard | 예 |
| B4 | 중복 방지 | 같은 화면에서재확인 | 이미발송문구,추가발송0 | 통과: 중복안내·200·발송1유지 | 없음 | 화면/서버기록 | 임시guard | 예 |
| B5 | 권한 회수 | fixture관리자권한회수후기존화면에서확인 | 실제403·실패모달,추가발송0 | 통과: 실제403·실패모달·발송1유지 | 없음 | 화면/서버기록 | 가짜계정 | 예 |
| B6 | 비관리자 | 다른전용session 가짜일반계정으로페이지접속 | 파일카드보임·발송버튼없음 | 통과: QA Viewer 표시·발송버튼0 | 없음 | snapshot/이미지 | 전용세션 | 예 |
| B7 | 실행 증거/정리 | console/errors·스크린샷열람·namespace close·서버종료·hash | 예측외오류0·시각확인·다른작업불변·소유잔재0 | 통과: 정상종료·이미지5개확인·namespace/profile/clone정리완료 | 없음 | 로그/이미지/보존기록 | clone/profile삭제 | 예 |

## Commands run

agent-browser skills get core 및 core --full로 설치 버전의 사용법을 확인했다. 실제 실행 명령·URL·session은 실행 결과에 기록한다.

## Failures found / Fixes applied

기존 규정의 UI 코드 변경 중심 판정, HTTP 하네스 대체 허용, Codex browse 연결과 공유 세션/원본 포트 안내를 수정했다. INFRA-063의 과거 기록은 HTTP 검증으로 보존하고 이번 후속 브라우저 검증과 구분한다.

## Cleanup and rollback

완료. 두 실행의 임시 서버·전용 browser namespace/profile·가짜 쿠키·fixture·clone을 정리했고 원본 package.json 해시와 앱 코드 불변을 확인했다. cleanup-preservation.json에 근거를 남겼다.

## Residual risks

실제 OAuth·운영 데이터·외부 메시지 전달은 검증 범위가 아니다. 이 시험은 기존 앱 UI와 API 경계 연결을 검증하며 전체 앱 전수 검사는 아니다.

## 실제 브라우저 실행 결과

- 최종 namespace: devcycle-browser-4jfnvrme-r2, sessions: admin/viewer. 실제 URL은 http://localhost:64847/dashboard/data-status, 앱 소스 기준366d5f9.
- 설치된 agent-browser0.31.1·Chrome for Testing151로 실제 Next 페이지의 버튼을 snapshot 참조로 클릭했다. 매 상태 변화 뒤 wait/snapshot을 수행했고 스크린샷5개를 모두 열어 확인했다.
- 실제 브라우저 요청: POST /api/kr/jongga-v2/message, application/json, {"target_date":null}. 정상/중복/권한 회수 응답은200/200/403. 외부 발송 대역의 최종 횟수는1이다.
- 실제 코드: Next 화면·이벤트 핸들러·세션 처리·proxy/HMAC·Flask 관리자/JSON 경계·중복 guard·성공/실패 모달. 대역: 가짜 로그인 JWT, 조회용 GET·파일 로더·파일명/결과 구성 fixture, 외부 Messenger. 검증 대상인 UI 요청 생성과 서버 인증/JSON 경계·중복 guard는 대역으로 바꾸지 않았다. 메시지 POST 응답을 브라우저에서 mock하지 않았다.
- 일반 계정은 실제 세션에 QA Viewer가 표시되고 발송 버튼은0개였다. 페이지 오류0, console error는 의도한403의 Failed to send message 한 건뿐이었다. 이 오류로 표시된 개발용1 Issue 배지도 숨기지 않았다.
- 브라우저는 전용 profile·허용 도메인·외부 요청을403으로 거부하는 로컬 proxy와 배경 통신 억제 옵션을 사용했다. 원본3500/5501은 브라우저 route로 차단했다. Next/Flask는 외부 outbound를 막고 localhost IPC만 허용한 Seatbelt에서 실행했다.
- 최종 UI runner exit0, Next/Flask fixture exit0, proxy exit0, 두 browser close 성공. 실제 OAuth나 운영 채널 전달을 테스트한 것은 아니다.

## 준비 실패와 재검수

- 외부 Seatbelt로 Chrome까지 감싼 첫 시작에서 CDP channel closed가 발생했다. 해당 namespace의 offline/quick doctor는 설치 정상으로 판정했다. 브라우저에는 도메인 제한과 차단 proxy를 적용했다.
- about:blank는 도메인 제한에서 hostname 오류가 났으며, 명령별 실행 옵션 누락은 browser 재생성을 일으켰다. 허용된 실제 URL과 매번 동일한 profile/proxy/domain/args로 고정했다. close 직후의 socket 연결 오류도 scoped doctor로 확인하고 같은 전용 세션을 복구했다.
- 수동1회차 기능은 통과했지만, 준비 지연으로 서버20분 수명 제한이 만료되어 fixture가 exit1을 반환했다. finally 정리는 성공했으나 정상 종료로 표시하지 않았다.
- 시나리오를 agent-browser CLI 순서로 자동화해 새 가짜 guard·전용namespace로2회차를 실행하고, 마지막 검사 직후 browser/server를 닫았다. 기능5개와 정상 종료를 모두 재확인했다. 원문 실패 로그도 보존했다.

## Evidence

[실행 결과](../evidence/browser-measurement-20260908/ui-results-r2.json), [브라우저 요청](../evidence/browser-measurement-20260908/network-r2.txt), [시각 확인](../evidence/browser-measurement-20260908/visual-checks.json), [CLI 원문](../evidence/browser-measurement-20260908/browser-commands.jsonl.gz), [정책 소비자 검증](../evidence/browser-measurement-20260908/forward-test.json).

[확인 모달](../evidence/browser-measurement-20260908/confirm.png) · [정상 발송](../evidence/browser-measurement-20260908/success.png) · [중복](../evidence/browser-measurement-20260908/duplicate.png) · [권한 회수](../evidence/browser-measurement-20260908/revoked.png) · [일반 사용자](../evidence/browser-measurement-20260908/viewer.png).

스킬 형식 검사 통과. TODO80개를 대조했으며 티어 기준은 변하지 않아 티어 수정은 없다. 새 QA 적용 판정은 각 라운드에서 실제 호출부로 수행한다. 글로벌 UltraQA/agent-browser 스킬을 복제·수정하지 않고 프로젝트 정본에서 연결했다.

- 독립 문서 검수는 기존 세션/원본 MCP 포트/driver 분기/감사 예시의4개 잔여 충돌을 지적했다. 모두 수정한 재검토는 APPROVE다. policy-review.json에 근거를 보존했다. Markdown LSP는 Transport closed였으며 스킬 형식 검사·실제 소비자 판정·브라우저 실측으로 검증했다.

## 최종 판정

- 필수7/7 통과: 정책 소비자 판정1개, 실제 브라우저 사용자 흐름5개, 증거·정리1개.
- 최종 재실측에서 UI runner·Next/Flask fixture·차단 proxy 모두 exit0. 정상·중복·권한 회수 POST는200/200/403, 외부 발송 대역은1회.
- 스크린샷5개를 직접 열어 확인했고, 두 namespace의 살아 있는 daemon/Chrome과 임시 서버 listener가 없음을 확인했다. 프로필·쿠키·실행 하네스·clone을 제거했다.
- 새 규정은 저장소의 Codex 스킬 링크가 참조하는 정본에 반영했다. 기존 INFRA-063 완료 기록을 브라우저 실측으로 바꾸지 않았으며 이번 보고서가 별도 후속 증거다.
- 실제 OAuth, 운영 데이터, 분석/메시지 포맷 엔진, 메시지 채널 수신, 전체 대시보드/쿼터 화면의 정확성은 이 시험 범위가 아니다.

`ULTRAQA COMPLETE: Goal met after 2 cycles`

최종 문서 검수 APPROVE. QA 양식의 예시 URL도 소유한 격리 포트로 바꾸어 현재 지침에 원본 서비스 접속 기본값을 남기지 않았다.
