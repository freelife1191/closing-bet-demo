# INFRA-060 리뷰 기록

- 범위: base cabc0be, 설계/계획 9f32e9a 및 구현 diff. 파일별 내용 SHA-256은 `../evidence/INFRA-060/verified-source-sha256.json`에 기록했다.
- 사용자 승인: 현재 대화 「진행해」. 동일 설계의 구현·회귀 수정은 재승인 없이 수행했다.
- 스킬: brainstorming(architectural 설계), writing-plans(소유자·legacy·cache 전환), TDD(익명 API RED→GREEN), executing-plans, using-git-worktrees(격리; 외부 worktree 소실 후 독립 clone), React/Next 번들 지침(client/session·fetch·error), code-review, security-review, review, UltraQA App 대응.
- 일반 리뷰·보안 레인은 전용 code-reviewer, 아키텍처는 전용 architect를 사용했다. 전용 security-reviewer 역할이 노출되지 않아 code-reviewer에 security-review/OWASP 기준을 전달한 대체 실행이다.

| 단계 | 검토자 | 최초 지적 | 최종 판정 |
|---|---|---|---|
| 계획 critic | infra060_plan_critic | 기존 price_cache 전환/보존 계획 누락 | REJECT → 설계 보완 → OKAY |
| ponytail | infra060_ponytail | chart 기간의 불필요한 부모 상태 lifting | 최초 로딩/동일계정 refresh 분리로 remount 원인 해결, lifting 제거·UI 재확인 |
| 코드·spec·보안 | infra060_code_review | 과거 snapshot, active index, Buy401, 이전계정 거래응답, bulk 오류/문구 | APPROVE, 미해결 0 |
| 아키텍처 | infra060_arch_review | migration/owner 보존 증거 공백·vacuous SQL 검사 | WATCH → 행동/다중프로세스 테스트 보완 → CLEAR |
| 독립 migration 시험 | infra060_migration_tests | 실제 legacy 5표 rollback·경합·재시작·복구 검증 | 5 PASS |
| T3 심층 review | infra060_deep_review | 수동 verify 스크립트 owner 계약 누락 | 수정 후 APPROVE, 미해결 0 |

## 코드·보안 최종 원문 요지

검토 파일/문서 36개. CRITICAL/HIGH/MEDIUM/LOW 각 0. owner SQL 바인딩, legacy 접근 거부, 원자적 migration, 가격 cache 신뢰 경계, 동시 거래, 인증 전 서비스 미접근, private/no-store 확인. OWASP A01·A03·A04·A07의 신규 차단점 없음. 의존성 변경이 없어 네트워크 감사는 수행하지 않았다.

## 아키텍처 최종 근거

과거 snapshot은 A/B를 함께 seed하고 대상 owner cash=50,000/stock=3,000/total=53,000을 확인한다. balance 누락은 history와 valuation 각각 복구한다. migration은 전체 schema/row rollback, 두 spawn 프로세스 경합, 반복 시 provider cache와 legacy 유지, 일부 scoped 표 복구 시 다른 모든 owner 행 보존을 관찰한다. A/B 동시 valuation 결과와 당일 snapshot은 서로 분리된다. 한 칸 snapshot memo는 owner가 다르면 miss로 처리하여 정확성을 지킨다.

## 수정과 검증

최종 pytest 1914 PASS/3 기존 skip(수동 Gemini 2·.env 없음 1), vitest 365 PASS(57 files), type-check PASS. lint mock 이름 오류를 고쳐 0 errors/199 warnings. 첫 전체 baseline에서 실패한 5개 검사는 환경/모킹만 현행화했고 업무 assertion은 유지했다. 실제 임시DB HTTP와 브라우저 QA 증거는 `../qa/INFRA-060.md`에 연결했다.

홈 telemetry·외부 댓글·네트워크·원본 DB 접근 없이 저장소 범위에서 검토했다. 설치된 review의 로컬 critical/informational checklist를 적용하고 결과를 이 문서에 보존한다.

## 심층 review 최종 판정

`Pre-Landing Review: No issues found. APPROVE (confidence 9/10).`

34개 source/test의 승인 범위와 SHA가 일치한다. SQL 값 바인딩, owner PK/WHERE/원자 차감과 같은 transaction의 거래 로그, BEGIN IMMEDIATE migration/rollback/marker/동시 초기화, legacy 가격 비활성 보존, reset의 타 owner/cache 보존, legacy sync 제외를 확인했다. 최초 수동 verify 스크립트 2개 owner 누락은 임시 DB/bare Flask/유효서명/실행 실패 단언으로 고쳤고 두 파일 실제 실행 exit 0을 확인했다.

심층 레인의 ast-grep/LSP MCP는 Transport closed로 실행할 수 없어 정적 검색과 기존 타입/lint 로그로 대체했다. 신규 empty catch/secret/shell/XSS 패턴 없음. 앞선 독립 코드 레인의 LSP/AST 검사 및 root typecheck/lint와 구분해 기록한다. 네트워크 또는 외부 리뷰 댓글은 사용하지 않았다.
