# INFRA-055 리뷰

## 계획

- critic infra055_plan: REJECT — NODE_ENV 강제 규칙, Next 고정경로 전달, .next 생성/권한/보존을 결정적으로 명시할 것.
- 세 지적 모두 계획에 반영, 재검토 **OKAY**. 원문은 evidence에 보존한다.

## 정적검사에서 발견한 실행기 확장자 문제

- lint 최초 exit2: 설치된 eslint-config-next의 files glob이 cjs를 제외해 전역 react-hooks 규칙의 plugin을 찾지 못했다.
- 수정: package가 CommonJS인 기존관례에 맞춰 run-next.js로 변경. ESLint 규칙을 끄거나 검사에서 제외하지 않는다. 계획 최초 OKAY의 입력hash는 변경전명칭을 보존하며, 확장자수정은 같은동작범위의실행보완이다.

## Ponytail / Task1 검토

- infra055_lean 최초 REQUEST CHANGES. HIGH: restart_all.sh의중복chmod가.next링크대상을변경; 블록제거와회귀추가. MEDIUM: envexample머리의옛링크설명갱신, signaltest실패finally정리, read/FIFO/parser실패증거추가.
- 불필요한cache권한처리를삭제해launcher가단일소유. root문서수정,executor가나머지보완후재검토한다.

- Ponytail 재검토 infra055_lean: **APPROVE / Lean already**, 최초4건모두해소. 직접targeted21PASS,JS LSP0진단(Python은tsc skipped),syntax/diff0. 원문회신과입력SHA를보존한다.

## 실제CLI 검증에서 발견한 대역 불일치

- 실제 npm build -- unexpected-directory는 exit0으로 고정프로젝트를빌드한다. stub은스스로exit2를반환해실제Next의추가positional무시를가렸다. extra-directory-red.json/log에실제명령과기대1/관측0을보존했다.
- 명세의추가디렉터리거부를launcher자체에서검증하도록보완한뒤실제CLI재검증한다. 현재필수미해결로첫커밋/QA진입전이다.

## 독립 코드·아키텍처·보안 검토 1차

- code infra055_code: REQUEST CHANGES (MEDIUM1), 실제Next가무시하는extra positional을stub가거부하여명세누락을가림.
- architecture infra055_arch: BLOCK (같은미구현), WATCH: @next/env hoisting결합.
- security infra055_security: 합성race에서.next symlink외부target0755→0700변경재현. 파일descriptor권한변경으로수정한다.
- 위세가지같은범위의마지막fixwave후독립재검토한다. 첫커밋/실측QA는그뒤에진행한다.

- security 최초 REQUEST CHANGES: MEDIUM1 reference-basedsecret smuggling(root backend/private→public), LOW1 .next swaprace. 직접합성재현됨. rawreference검사후실확장하는2pass로보완; 표준parser재사용,새dependency/Nodefloor없음. `.next`fd와CLI거부수정은이미30개targeted테스트통과했으며보안수정후함께재검토한다.

## v10 최종 판정

- 독립 code: APPROVE / 0 issues. architecture: CLEAR. security: APPROVE / 0 unresolved. 각 원문 gzip과 review-input-v10.json 7개 SHA를 증거로 보존했다.
- 루트 심층 리뷰: APPROVE. gstack review 체크리스트로 승인 기준97113d4 대비 diff를 검토했다. 실제 CLI 대역 불일치, 숫자·재귀·escaped dollar 우회, dotenv runtime 우회를 재현·수정한 뒤 50개 회귀 테스트로 고정했다. 외부 CLI의 독립 판정으로 표기하지 않는다.
- 최종 ponytail delta는 루트가 직접 검토: 기존 @next/env 재사용, 종속성 추가 없음, 중복 cache chmod 제거. 2-pass는 원문과 실제 확장 결과를 모두 검증해야 하는 재현된 우회에 필요하다. 기존 독립 Lean already 이후 보안 보완을 같은 기준으로 검토했다.
- 실제 추가 위치 인수 거부 exit1, 선택값 옵션의 bare --help exit0. pytest2077 PASS/3skip, Vitest373 PASS/57files, lint0errors/204warnings(기존199+CommonJS5), typecheck0. 보안 lane의 fresh MCP Transport closed는 코드 lane의 exact v10 LSP0/AST0 증거로 보완했다.
- 홈 telemetry·remote PR·실제 env/data·원본 runtime 작업과 외부 CVE/npm audit는 수행하지 않았다. 종속성 변경은 없다.
