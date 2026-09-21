## 요약

이전 `WATCH`는 해소됐습니다. 가격 동기화의 시작뿐 아니라 실패·종료 후 복구까지 scheduler leader가 소유하며, 날짜 검증도 파일 접근 전 경계에서 닫혔습니다.

## 분석

### 가격 동기화 복구 — CLEAR

- leader bootstrap이 즉시 `_ensure_paper_trading_sync()`를 호출하고, 같은 helper를 `paper_price_sync` 태그로 분당 등록합니다. 재부트스트랩 시 기존 태그를 지워 중복 잡도 방지합니다. `services/scheduler.py:192-233`
- `start_background_sync()`는 실행 중이면 즉시 반환하고, 프로세스 간 sync 락도 유지합니다. `services/paper_trading.py:509-556`
- 가격 루프가 종료되면 `is_running=False`, `bg_thread=None`, sync 락 해제를 수행하므로 다음 분 tick이 실제로 재기동할 수 있습니다. `services/paper_trading.py:680-696`
- disabled/락 경합 워커는 bootstrap에 진입하지 않으며, 직접 획득과 retry 승계만 같은 복구 잡을 등록합니다. `services/scheduler.py:244-264`, `services/scheduler.py:314-329`
- 최초 실패 후 분당 잡 재호출, 반복 bootstrap의 실제 가격 thread 1개, 기존 잡·loop 유지가 회귀로 고정됐습니다. `tests/services/test_scheduler_refactor.py:348-430`

추가 mutex를 넣지 않은 판단도 현재 호출 그래프에서는 타당합니다. 즉시 호출은 scheduler loop 시작 전이고, 이후 job은 단일 scheduler thread의 순차 `run_pending()` 경로입니다. 제품 singleton도 자동 시작을 끈 상태입니다. `services/scheduler.py:202-240`, `services/scheduler.py:307-311`, `services/paper_trading.py:789-798`

### 날짜 파일 경계 — CLEAR

- `None`만 최신 파일로 허용하고, 날짜는 ASCII 숫자의 `YYYYMMDD` 또는 `YYYY-MM-DD`만 받습니다. `datetime.strptime`가 실제 달력 유효성도 검사합니다. `services/kr_market_market_gate_validity.py:16-23`
- 라우트는 resolver의 `ValueError`를 파일 로드보다 앞에서 400으로 변환합니다. 따라서 traversal·잘못된 날짜·빈 문자열이 loader에 도달하지 않습니다. `app/routes/kr_market_system_http_routes.py:59-69`
- 관리자 POST와 기존 update dependency는 변경되지 않았습니다. `app/routes/kr_market_system_http_routes.py:100-117`
- invalid 입력의 load 0회와 윤년·두 정상 형식이 회귀로 고정됐습니다. `tests/app/test_kr_market_system_http_routes_refactor.py:157-168`, `tests/services/test_kr_market_market_gate_service_refactor.py:21-24`, `tests/services/test_kr_market_market_gate_service_refactor.py:202-203`

## 근본 원인 해소

이전 문제는 가격 sync의 **시작 소유권만** leader로 옮기고 **복구 소유권**을 옮기지 않은 것이었습니다. 분당 leader job이 같은 멱등 start 경계를 재확인하면서 소유권과 복구 책임이 일치하게 됐습니다.

## 권고

1. **문서 표현만 정리 — 낮은 노력**
   `CLAUDE.md:306`은 아직 scheduler가 “잡 두 개”를 등록한다고 적습니다. 실제로는 업무 잡 두 개와 `paper_price_sync` 복구 잡 하나입니다. 동작상 문제는 없지만 운영 문서를 맞추는 편이 좋습니다.

2. **동시 호출 표면이 추가될 때 mutex 재검토**
   현재 구조에는 필요하지 않습니다. 향후 scheduler 외 제품 경로가 `start_background_sync()`를 동시에 호출하게 될 때만 service-level 직렬화를 다시 검토하면 됩니다.

## Architectural Status

`CLEAR`

차단 또는 비차단 아키텍처 결함이 남아 있지 않습니다. `CLAUDE.md`의 잡 개수 표현은 문서 정합성 수준입니다.

## 트레이드오프

| 선택 | 장점 | 비용 |
|---|---|---|
| 분당 leader health job | GET 부수효과 없이 1분 이내 자동 복구 | 매분 멱등 상태 확인 1회 |
| 별도 감시 스레드 | 더 짧은 복구 간격 가능 | 새 lifecycle·동시성 표면이 생김 |
| 현재 선택 | 기존 scheduler와 sync 락 재사용, 최소 구조 | 최악 복구 지연 약 1분 |

## 검증 상태

최종 동결 해시와 현재 대상 파일은 모두 일치했고 `package.json` SHA도 보존됐습니다. 제약에 따라 명령을 재실행하지 않고 저장 증거를 검토했습니다.

- 보완 대상: `54 passed` — `docs/dev-cycle/evidence/infra-read-boundaries-20260921/pytarget-review-fixes.log:1-2`
- 최종 pytest: `2444 passed, 3 skipped` — `docs/dev-cycle/evidence/infra-read-boundaries-20260921/pytest-review-final.log:35-38`
- 변경 없는 프론트 동결본: Vitest `640 passed`, typecheck exit 0 — `docs/dev-cycle/evidence/infra-read-boundaries-20260921/vitest.log:2080-2083`, `docs/dev-cycle/evidence/infra-read-boundaries-20260921/typecheck.json:1-15`
