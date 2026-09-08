# UltraQA Report

## Goal and success criteria

- 목표: 로그인한 A/B가 자기 모의계정만 조회·변경하고 legacy 자료와 공용 시세의 신뢰 경계를 보존한다.
- engine: ultraqa | lifecycle: app-adapted | phase: complete | iteration: 1 | same_failure_count: 0
- 승인: 사용자 「진행해」. 로그인 전용·legacy 보존·개인 계정 초기 모의자금 100_000_000.
- 기준: cabc0be, 설계/계획 9f32e9a. critic 최초 REJECT(기존 가격캐시 전환 누락) 후 보완하여 OKAY.
- baseline: 기존 모의투자 관련 pytest 96개 통과(1.53초). HTTP 신규 회귀는 익명 응답 200으로 RED, 인증 경계 후 33개 GREEN.
- 안전: 원본 .env/data와 실제 Next3500·Flask5501/liveURL 요청 금지. 테스트는 독립 clone의 임시 SQLite/mock 시세/bare Flask만 사용한다. 원본 package.json 보존.
- 성공: 아래 필수 시나리오·정적 검사·리뷰·정리 전부 PASS. 최대 5회 또는 같은 실패 3회에서 중단하며 완료 전 TODO 유지.

## Scenario matrix

| ID | 의도/사용자 | Setup | 명령/하네스 | 기대 | 실제 | 수정 | 증거 | 정리 | 필수 |
|---|---|---|---|---|---|---|---|---|---|
| Q1 | 로그인 A/B 계정 | 임시 DB·서명 신원 | 서비스/Flask pytest | 각 1억, A/B 모든 조회·거래·입금·reset 격리 | 통과: A/B 전 연산 격리 | owner SQL/route | qa-pytest-5f60865.log.gz, test_portfolio_owner_boundary.py | tmp DB 자동 정리 | 예 |
| Q2 | 익명·공격자 | 위조/만료/일반 신원 헤더·owner body/query | HTTP 경계 pytest | 8 routes 401·서비스 미접근, 유효서명은 자기 owner만 | 통과: 무서명/위조/만료 401, body/query 사칭 무시 | 인증 decorator | HTTP 경계 회귀와 exactcommit 전체 PASS | bare app context 종료 | 예 |
| Q3 | 기존 사용자 자료 | 구형 DB·기존 price_cache | migration pytest | legacy 내용 보존·접근 차단·active 가격캐시 비움·반복 안전 | 통과: legacy 전 행 보존, 예약 owner 거부, 활성 cache 비움 | atomic migration | migration_safety 5건 포함 128 service PASS | tmp DB 자동 정리 | 예 |
| Q4 | 동시 사용자/중단 | 여러 연결·동시 초기화/매수·실패 주입 | concurrency/rollback pytest | 자금 중복 지급·음수잔고·다른owner변경·부분 migration 없음 | 통과: 두 spawn 초기화·동시 owner valuation·late 실패 rollback | transaction/조건부 SQL | test_paper_trading_migration_safety.py, exactcommit PASS | 프로세스 join·연결 종료 | 예 |
| Q5 | 가격 오염 시도 | 같은 ticker, A의 입력가격, mock provider | cache/valuation pytest | B는 공급자 시세/자기 원가만 사용, reset은 공유cache 보존 | 통과: 체결 입력은 공용cache 미기록·B provider/원가만 평가 | 거래의 공유캐시 쓰기 제거 | test_paper_trading_owner_isolation.py, exactcommit PASS | 외부호출 없음 | 예 |
| Q6 | 로그인 전환/늦은응답 | 익명→A→B, 지연응답·401 | vitest·격리 UI | 로그인 안내, A 자료/응답이 B 화면에 재등장하지 않음 | 통과: Alice120,999,000/Bob99,996,000, 401안내, 늦은 응답 미반영 | UX/session 경계 | final-ui/final-summary.md, deferred 9 PASS | 소유서버·임시route·브라우저 정리 완료 | 예 |
| Q7 | 회귀·불변성 | 독립 clone, 원본 파일 hash | 전체 pytest/vitest/typecheck·diff | 기존 계약 및 원본 data/env/package 보존 | 통과: 정적/동적·source34·원본 package 보존 | 필요한 contract 갱신 | full logs·34 source hashes | 실행 fixture·clone·baseline 정리 완료 | 예 |

## Commands run

- baseline: `python -m pytest tests/services/test_paper_trading_service.py tests/services/test_paper_trading_db_setup_refactor.py tests/services/test_paper_trading_lazy_refactor.py -q` → exit 0, 96 PASS.
- 신규 HTTP RED: `pytest tests/app/test_portfolio_owner_boundary.py --maxfail=2` → exit 1, 예상 401인데 200.
- HTTP GREEN: 같은 전체 파일 → exit 0, 33 PASS.

## Failures found / Fixes applied

- 임시 git worktree가 작업 중 제거되어 독립 clone으로 복구했다. 원본 코드 변경이나 운영 데이터 접근은 없었다.
- 계획 critic 지적에 따라 기존 price_cache의 legacy 보존/활성 캐시 분리와 rollback·동시 초기화 검사를 추가했다.
- 모듈 교체 중 병렬 pytest collection이 실패한 기록은 편집 중 환경 상태이며 제품 결함으로 판정하지 않는다. 소유 worker가 import 가능 상태를 알린 뒤 다시 실행한다.

## Cleanup and rollback

실행용 QA 서버·임시 route·브라우저·임시 SQLite·하네스는 정리했다. 원본 DB migration/서비스 재기동/배포는 수행하지 않았다. 검증 커밋 374d4f6까지 원본 develop에 fast-forward한 뒤 독립 clone·baseline을 제거했다.

## Residual risks

모든 필수 동작과 정리가 통과했고 검증 커밋은 원본 develop에 반영했다. 운영 DB 적용·재기동·배포는 실행하지 않았다. 신원 서명의 경로/메서드 재생 방어는 기존 INFRA-062 범위이며 이번 변경에서 서명 형식을 바꾸지 않는다.

## Evidence

설계·계획, 관련 pytest/vitest 회귀 파일과 최종 실행 기록을 이 문서에 연결한다.

## 정적 검증과 구현 단계 실측 (2026-09-08)

- 전체 pytest: 네트워크 outbound를 sandbox-exec로 차단하고 스케줄러를 끈 독립 clone에서 `python -m pytest -q` → exit 0, **1914 passed, 3 skipped, 26.70s**. skip 내역은 후속 `-rs`로 확정했다: Gemini 수동 통합 2개, 실제 .env가 없는 격리 환경 검사 1개. 이번 owner 시나리오는 skip이 없다.
- 전체 vitest: `frontend`에서 `npx vitest run` → exit 0, **57 files / 365 tests**, Next build smoke 포함. 이후 테스트 mock 함수의 PascalCase 이름만 수정한 관련 11 tests도 통과했다.
- `npm run type-check` → exit 0. `npm run lint`에서 테스트 mock 이름 오류 1개를 고친 뒤 exit 0, warnings 199개. 경고 전체 정리는 이번 범위에 포함하지 않았다.
- 최초 baseline cabc0be 전체는 1854 passed / 5 failed / 3 skipped였다. 수정 전 current도 동일한 5개 실패뿐이었다. Vertex 테스트 구성과 실제 import 위치에 맞춘 모킹으로 외부 의존성을 격리했고 기존 업무 assertion은 유지했다. 보완 후 전체 1914 PASS다.
- HTTP 인증/실DB 통합은 8개 route의 위조·만료·익명 거부와 A/B 입금·매수·bulk·매도·초기화·이력 격리를 검사했다. 정상 응답은 `private, no-store`로 설정했다.
- 독립 migration 안전 테스트 5개는 실제 5개 표의 rollback, spawn 2프로세스 동시 초기화, 반복 전환과 provider cache 유지, 일부 표 복구 시 다른 owner 보존, A/B 동시 valuation을 검증했다.
- 구현 단계 브라우저 실측: [UI 값과 오류 확인](../evidence/INFRA-060/ui-summary.md). 실제 NextAuth 합성 테스트 cookie → 기존 proxy 서명 → bare Flask 검증 → 임시 SQLite를 연결했다. 실제 OAuth·운영 데이터·운영 서버는 사용하지 않았다.
- 브라우저 후 추가된 mutation 세대 guard는 지연 응답이 계정 전환 뒤 새 모달을 닫거나 이전 계정 알림을 표시하지 않는 실컴포넌트 테스트로 확인했다.

## 원인과 수리 내역

1. 계정 owner가 없는 SQL·API → 모든 계정 API의 owner 필수화, 예약 legacy 차단, 8개 HTTP 인증 경계.
2. 과거 거래 입력으로 오염될 수 있는 기존 가격 cache → legacy_price_cache 보존, 활성 cache 분리, provider만 갱신.
3. 재초기화 시 owner/가격 손실 위험 → migration marker·원자적 전환·기존 scoped 표 보존·활성 인덱스 재부착.
4. 과거 단일 snapshot과 누락 balance 복구 공백 → 현재 owner 상태 재평가, retry 안에서 owner 초기화, 행동 회귀.
5. 계정 전환 이후 늦은 조회·거래 응답 → key와 취소/세대 guard, 계정별 UI 상태 초기화.
6. chart refresh remount → 최초 로딩과 동일 owner 갱신을 구분해 3개월 선택 유지. 불필요한 부모 상태 lifting은 제거했다.
7. bulk preflight DB 오류를 업무 실패로 삼키던 경로 → 원래 오류 전파와 전체 실패 메시지 복원. 주문 불가능 시 write context 0회 검증.

### 증거 로그

- [baseline pytest](../evidence/INFRA-060/full-pytest-baseline.log.gz), [보완 전 current pytest](../evidence/INFRA-060/full-pytest-current.log.gz)
- [최종 pytest](../evidence/INFRA-060/full-pytest-final.log.gz), [최종 vitest](../evidence/INFRA-060/full-vitest-final.log.gz)
- [타입 검사](../evidence/INFRA-060/typecheck-final.log.gz), [린트](../evidence/INFRA-060/lint-final.log.gz)

### 적용 불가/경계

- LLM prompt injection·CLI flag/path escape는 이 기능에 LLM·CLI·파일경로 입력이 없어 해당 없음. HTTP owner 사칭과 만료 신원은 Q2로 검증한다.
- 다른 사용자의 파일/런타임 취소는 테스트하지 않는다. 소유한 프로세스와 임시 파일만 정리한다.
- 기존 신원 서명의 경로·메서드 재생 방어는 별도 TODO INFRA-062가 유지한다.

원본 실행 로그는 공백·ANSI를 바꾸지 않고 gzip으로 보존했다. `gzip -dc <파일.log.gz>`로 원문을 확인할 수 있다.

- 심층 review 추가 발견: pytest가 수집하지 않는 `verify_portfolio_api.py`·`verify_pnl_fix.py`의 owner 계약 누락. 삭제하지 않고 tmp DB/bare Flask·실제서명·assertion으로 수정했다. 두 스크립트를 네트워크 차단 상태에서 직접 실행해 각각 exit 0/PASS 확인. 로그는 evidence/INFRA-060의 같은 이름 `.log.gz`에 보존했다.

- 최종 QA 실행 확인 시각: 2026-09-08 15:26 KST, 기준 구현 커밋 `5f60865`. 코드·보안 APPROVE, architecture CLEAR, deep review APPROVE 후 진입했다.

- exactcommit `5f60865` 최종 backend QA: `pytest -q -rs` → exit 0, 1914 passed/3 skipped, 25.23s. skip은 `tests/manual/test_gemini_hang.py` 2개와 `tests/scripts/test_env_value_sh.py:159`(.env 없음) 1개다. 기존 기록의 포괄적인 수동검사 표기를 이 실제 내역으로 정정한다. [원문](../evidence/INFRA-060/qa-pytest-5f60865.log.gz).

- 최종 Q6: [브라우저/실컴포넌트 QA](../evidence/INFRA-060/final-ui/final-summary.md). 늦은 mutation은 브라우저에서 요청을 중단한 시험으로 꾸미지 않고, 같은 커밋의 실제 BuyStockModal deferred 응답 테스트 9개로 검증했다.

- 최종 동적 QA와 실행 fixture cleanup PASS. root에서 source/test SHA34 일치, source diff 0, 원본 HEAD 및 package 해시 불변을 확인했다. 작업 clone 정리 전이므로 이 QA 증거 커밋에서도 TODO는 유지한다.

## 최종 판정

- 필수 시나리오 **7/7 통과**, 미통과 필수 없음. Q6의 브라우저/컴포넌트 세부 시나리오도 7/7 통과했다.
- 최종 코드 기준: `5f60865`; 확정 커밋 QA 증거: `374d4f6`; 설계/계획: `9f32e9a`.
- root가 원본 반영 후 source/test 34개 SHA-256 일치와 기존 package.json 해시 불변을 확인했다.
- 58235/58786 QA listener가 없음을 다시 확인했고, 이번 작업의 독립 clone·baseline·임시 실행 파일을 제거했다. 증거는 저장소에 보존했다.
- 원본 .env/data는 읽거나 바꾸는 작업을 수행하지 않았다. 내용 hash를 확인했다는 의미는 아니다.
- App 대응 실행이며 네이티브 OMX hook 상태를 생성·수정·종료했다고 주장하지 않는다.
- [최종 UI 증거](../evidence/INFRA-060/final-ui/final-summary.md), [보존/정리 결과](../evidence/INFRA-060/integration-preservation.json), [리뷰 판정](../reviews/INFRA-060.md).
- 재개 판정: 완료 가능. 이번 항목만 완료하며 다음 TODO는 시작하지 않는다.

`ULTRAQA COMPLETE: Goal met after 1 cycles`

완료 확인: 2026-09-08 15:39 KST.
