# INFRA-063 리뷰 기록

## 계획 검토

- critic infra063_plan: 최초 REJECT. BadRequest import, 익명/비관리자 × 비JSON/잘못된JSON 교차 검사, HTTP fixture 주입 범위를 반영했다.
- package.json 지적은 clone에 없다는 관찰을 원본에도 없다는 결론으로 확대한 오판이다. 원본 /Users/freelife/vibe/lecture/hodu/closing-bet-demo/package.json은 기존 untracked이며 clone에는 복사하지 않았다. 원본 해시 4ef4b68fea412928af1832150490aaf5817d56c753e20a456f612142deaed3d8을 보존한다. 계획에 절대경로와 차이를 명시했다.
- 기존 발송 오류 노출까지 Q6가 보장하는 것으로 읽히던 모호성을 새 입력거부 오류와 fake identity secret/서명/MAC 범위로 한정했다. 기존500·로그는 INFRA-038/043으로 유지한다.
- 수정 계획 재판정: **OKAY**. 명확성·검증가능성·완전성·범위·T3/UltraQA 기준 통과, 차단 없음.

## 이후 단계

TDD → ponytail → code-reviewer/architect 및 security → deep review → 정적검증 → exact commit UltraQA.

## 구현과 과잉설계

- TDD: 최초12fail/12pass, 확장행렬17fail/12pass. 비JSON/잘못된JSON/falsy는200, truthy비객체는500으로400기대실패. multipart대역 초기오류는 별도로수리했다. impl-red*.log.gz 원문보존.
- root가 construct 카운터를 실제 Messenger생성으로 수정하고 날짜전달 assertion을 추가하도록 요청했다. 대상62PASS, 전체pytest1965PASS/3skip.
- ponytail: **Lean already. Ship.** 원문 evidence/INFRA-063/ponytail.json.
- 검토 입력16개의 SHA는 review-input-sha256.json.
- LSP 도구Transport closed와 Ruff미설치로 Python진단은 AST parse·실제pytest로대체했으며 LSP성공으로보고하지않는다.

## 독립 코드·아키텍처·보안

- code-reviewer infra063_code: **APPROVE**, 0 findings. file별LSP는tsc skipped이므로Python진단통과아님; 실제pytest/AST가17줄경계의판정에충분하다고확인.
- architect infra063_arch: **CLEAR**. parser위치가wrapper밖이어야하는결합은테스트로고정; 실제HTTP는마감필수로유지.
- security-focused code-reviewer infra063_security: **APPROVE**, 0 findings. 수정된security-review스킬로직접호출. npm audit/CVE조회는의존성변경없음/외부네트워크금지로미수행.
- 각 최종응답은 evidence/INFRA-063/code-review.md, architecture-review.md, security-review.md에보존한다.
- root 하네스 negative control에서 JSON unicode escape가 raw marker검사를피하는관측공백을발견했다. JSON을decode한본문도검사하도록고쳐 escaped/plain 양쪽에서누출감지가실패를일으킴을확인했다. 제품결함이아니며 escaped-marker-red/green.json에보존한다.

## 심층 리뷰와 실행 환경 보완

- 최초 deep review: REQUEST CHANGES. 제품차단0, 하네스Next telemetry/분리process정리1건. 원문 deep-review-initial.md.
- Next/JWT child env를allowlist로제한하고 telemetry/trace 업로드를강제비활성화했다. 일회용Next PGID는첫SIGKILL로종료hook을피하고 detached-flush.js PID·_events파일부재를검사한다. root가실행파일명matcher와실제JWT함수의allowlist누락도고쳤다.
- 외부통신deny-all은Node loopback IPC를막는것으로최소probe확인. localhost예외후에도실패생성물상태에서는동일build2건실패. 그생성물만분리하자같은localhost-only정책으로vitest373PASS. 정확한캐시엔트리원인은미특정이며제품소스문제라고단정하지않는다.
- 이전frontendbaseline은telemetry강제비활성화가없었으므로외부통신금지보장근거로쓰지않는다. 실제전송이발생했다는근거도없다. 최종근거는fresh-loopback-vitest-exit.json/로그이며API대역호출0이다.

- 심층 재검토: **APPROVE**, HIGH/P1 해결·제품차단없음. deep-review-final.md에최종응답보존. gstack review는로컬기준5aab1dc diff에적용했고홈telemetry/PR/원격조회는프로젝트대응으로생략했다.

- 실제실행1회차의setuid ps금지를non-setuid pgrep으로수리. 동일sandbox동적processnegativecontrol과그룹정리검사통과후 deep-review-pgrep.md 재검토APPROVE. 실제2회차28/28통과, 제품/test16hash불변.
