# Architecture / Devil’s Advocate Review

## Summary

v4 기준 차단 이슈는 없습니다. INFRA-019 문서는 실제 30분/17:00 등록 구조와 provider 폴백 조건·허용 목록·논리 슬롯 귀속을 정확히 설명하고, INFRA-029는 네 단계의 기존 실행 순서·반환값 호환·알림 조건·상태 해제를 보존하면서 거짓 전체 완료 로그만 제거합니다.

두 차례 발견한 Medium 문서 불일치(일반 5xx 자동 폴백 단정, Z.ai allowlist 숨은 결합 및 실제 엔진/논리 슬롯 혼동)는 v4에서 모두 해소됐습니다. 런타임과 테스트 소스는 v1 이후 동결 해시가 유지됐습니다.

## Analysis

### 1. 스케줄러 설명은 등록 코드와 일치 — severity: 없음

코드 기본 간격은 30분이며(`engine/config.py:281-286`), bootstrap은 Market Gate 반복 잡과 `CLOSING_SCHEDULE_TIME` 기본 17:00의 closing 잡 두 개만 등록합니다(`services/scheduler.py:192-218`). 별도 `JONGGA_SCHEDULE_TIME` 등록은 없고, 종가 분석은 closing 체인 안에서 호출됩니다(`services/scheduler_jobs.py:118-125`). 수정 문서는 기본 30분과 17:00 체인만 남깁니다(`.env.example:88,186-187`, `README.md:104-106,1451-1454,1481-1484`).

`run_market_gate_sync`는 개장일 여부만 확인하고 장중 시각을 제한하지 않으므로(`services/scheduler_jobs.py:154-166`), README의 “개장일 주기 동기화, 장중 시간대만으로 제한하지 않음” 표현도 정확합니다(`README.md:1463-1469`).

### 2. 네 단계 결과 집계가 승인된 호환 계약을 보존 — severity: 없음

실행 순서는 일별 주가 → 기관/외인 수급 → VCP → 종가베팅이며(`services/scheduler_jobs.py:101-119`), 종가 결과가 truthy일 때만 기존 알림 호출을 유지합니다(`services/scheduler_jobs.py:121-125`). 실패 목록은 앞 세 단계를 `is False`로만 판정하고 종가 단계는 기존 truthiness를 사용합니다(`services/scheduler_jobs.py:127-136`). 따라서 앞 세 단계의 `None` 호환은 유지되고 종가의 `False`/`None`은 실패입니다.

부분 실패면 실패 단계 순서를 보존해 error 로그를 남기고, 모두 성공했을 때만 전체 완료를 기록합니다(`services/scheduler_jobs.py:137-143`). 예외는 완료 로그에 도달하지 않고 outer error 경로로 이동하며, `finally`가 세 runtime 상태를 모두 해제합니다(`services/scheduler_jobs.py:144-151`). 회귀 테스트는 단일 단계 실패·종가 False/None(`tests/services/test_scheduler_jobs_refactor.py:149-202`), 복합 실패와 알림 선행 순서(`tests/services/test_scheduler_jobs_refactor.py:205-235`), 앞 세 단계 None 호환(`tests/services/test_scheduler_jobs_refactor.py:238-258`), 수집/알림 예외와 상태 해제(`tests/services/test_scheduler_jobs_refactor.py:261-299`)를 고정합니다.

### 3. provider 설명과 실제 폴백 경계가 일치 — severity: 없음

Perplexity는 429·503을 직접 전환하고(`engine/vcp_ai_analyzer.py:699-722`), 그 밖에는 quota/auth로 분류된 오류만 폴백하며 일반 non-200·파싱 실패·통신 예외는 `None`입니다(`engine/vcp_ai_analyzer.py:724-799`; 분류 규칙 `engine/vcp_ai_analyzer_helpers.py:786-824`). 폴백 허용 목록은 `VCP_AI_PROVIDERS`에서 Z.ai→GPT 순서로 구성되고, 실제 초기화된 클라이언트만 호출합니다(`engine/vcp_ai_analyzer.py:1158-1230`). GPT→Z.ai도 `zai` allowlist 멤버십과 클라이언트 초기화를 모두 요구합니다(`engine/vcp_ai_analyzer.py:1232-1256`). Perplexity 키가 없으면 허용된 GPT로 보조 슬롯을 바꾸며, 실행 불가 조합은 `None`으로 확정합니다(`engine/vcp_ai_provider_init_helpers.py:113-141,144-157`).

v4 문서는 `zai`가 활성·폴백 허용 목록에 포함돼야 함을 명시하고 기본값 자체는 보존합니다(`.env.example:109-116`, `README.md:94-101`). 상세 설명은 정확한 전환 조건, 일반 실패의 비보장, 키 누락 시 GPT 선택, 현재 예시가 폴백을 허용하지 않는다는 점과 구체적 opt-in 목록까지 밝힙니다(`README.md:556`). 랜딩 문구도 “설정에 따라”, “전환 조건”, “사용 가능한 모델”로 범위를 제한합니다(`frontend/src/app/page.tsx:247-261`).

### 4. 숨은 provenance 결합을 문서에서 정확히 드러냄 — severity: 없음

오케스트레이터는 task 생성 시 논리 슬롯을 `gpt` 또는 `perplexity`로 고정하고, 내부 폴백 반환값도 그 슬롯 키에 저장합니다(`engine/vcp_ai_orchestration_helpers.py:34-52,58-68`). `apply_ai_results` 역시 실제 호출 엔진이 아니라 recommendation 슬롯 우선순위로 `ai_provider`를 정합니다(`engine/signal_tracker_ai_helpers.py:85-98,124-146`). v4 README는 Perplexity 내부 Z.ai/GPT 결과가 `perplexity_recommendation`, GPT 내부 Z.ai 결과가 `gpt_recommendation`에 남고 `ai_provider`는 실제 fallback 엔진을 보장하지 않는다고 명시합니다(`README.md:554-555`). 승인 범위 밖의 provenance 기능을 추가하지 않으면서 현재 계약을 정직하게 설명한 선택입니다.

### 5. Devil’s advocate / strongest counterargument — non-blocking

가장 강한 반론은 결과 집계를 알림 뒤에 두면 알림 예외가 앞 단계의 부분 실패 요약을 가리고, 알림 함수 자체가 내부 발송 예외를 삼키므로 scheduler가 실제 전달 성공을 알 수 없다는 점입니다. 실제 알림 함수는 내부 예외를 기록한 뒤 반환합니다(`scripts/init_data.py:2500-2510`). 그러나 이번 승인 범위는 기존 알림 조건과 호출 순서를 유지하고 전달 성공 판정은 확대하지 않는 것이며(`docs/superpowers/plans/2026-09-09-scheduler-truthfulness.md:32-45`), scheduler 문구도 “발송 완료”에서 “알림 처리 종료”로 좁혔습니다(`services/scheduler_jobs.py:121-125`). 호출 자체가 throw하면 전체 완료가 기록되지 않고 finally 정리가 실행됩니다(`services/scheduler_jobs.py:144-151`). 따라서 이 한계는 별도 관측성 개선 후보이지 이번 변경의 blocker가 아닙니다.

## Root Cause

기존 문제의 근본 원인은 두 종류의 상태를 하나의 성공 표현으로 압축한 데 있습니다. scheduler는 네 단계 반환값을 모으지 않은 채 전체 완료를 기록했고, 문서는 설정 provider 슬롯·실제 fallback 엔진·allowlist/클라이언트 가용성을 구분하지 않았습니다. v4는 런타임 계약을 바꾸지 않고 단계 결과를 명시적으로 집계하며, 문서에서 스케줄 등록·폴백 트리거·허용 목록·논리 슬롯을 각각 구분했습니다.

## Recommendations

1. 현재 v4를 동적 QA 단계로 진행 — effort: 낮음 — impact: 높음. 추가 코드 수정은 필요 없습니다.
2. 실제 fallback 엔진 provenance나 알림 전달 결과가 운영 요구가 되면 별도 TODO로 설계 — effort: 중간 — impact: 관측성 향상. 현 인터페이스와 UI 슬롯 의미를 바꾸므로 이번 승인 범위에는 포함하지 않습니다.

## Architectural Status

`CLEAR`

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| 현재 계약 보존 + 정직한 문서/로그 | 작은 diff, 호출 순서·알림 조건·호환성 유지, 회귀 위험 낮음 | `ai_provider`가 실제 fallback 엔진을 식별하지 못하고 알림 전달 성공도 구조화하지 않음 |
| 구조화된 단계 결과/provenance/알림 상태 도입 | 운영 관측성과 자동화 판정 향상 | 반환 인터페이스·저장 스키마·UI 의미·테스트 범위가 확대되어 승인 범위를 벗어남 |

## Validation

- targeted scheduler: `16 passed` (`../evidence/green-scheduler.log:1-2`).
- full pytest: `2258 passed, 3 skipped` (`../evidence/final-pytest.log:33`).
- full Vitest 및 실제 build: `424 passed`, build 성공 (`../evidence/final-vitest.log:1164-1168,1183-1186`).
- typecheck exit 0 (`../evidence/final-typecheck.json:1-11`; 로그 `final-typecheck.log:1-2`).
- lint exit 0, 기존 warning 201개 (`../evidence/final-lint.json:1-11`; `final-lint.log:371-372`).
- Python AST 2 files parse, 실제 secret 값 미열람 (`../evidence/static-analysis.json:1-13`). Python LSP 검증은 주장하지 않습니다.
- v4 freeze: `../evidence/review-input-v4.json:3-11`의 모든 SHA256이 현 파일과 일치했고 `git diff --check`가 통과했습니다. v2~v4는 문서만 바뀌었고 runtime/tests/frontend 해시는 그대로라 전체 suite를 재실행하지 않았습니다.
- 동적 QA는 별도 후속 게이트이며 이 architecture review의 통과 주장에 포함하지 않습니다.

## References

- `services/scheduler.py:192-218` — 실제 등록 잡 두 개와 기본 17:00.
- `services/scheduler_jobs.py:101-151` — 네 단계 실행·알림·부분 실패/성공·finally.
- `tests/services/test_scheduler_jobs_refactor.py:149-299` — 실패/호환/예외 회귀 계약.
- `engine/vcp_ai_analyzer.py:699-799` — Perplexity 전환 조건과 비폴백 경계.
- `engine/vcp_ai_analyzer.py:1158-1256` — provider allowlist 및 Z.ai→GPT/GPT→Z.ai 폴백.
- `engine/vcp_ai_orchestration_helpers.py:34-68` — 논리 provider 슬롯 고정.
- `engine/signal_tracker_ai_helpers.py:85-146` — 슬롯 기반 `ai_provider` 선택.
- `README.md:94-101,551-556` — v4의 실제 설정/폴백/슬롯 설명.
- `.env.example:109-116,186-187` — provider allowlist와 scheduler 정본 예시.
