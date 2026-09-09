## 요약

최종 판정은 `CLEAR`입니다. 최초 `tests/build/` 경로의 Git ignore 충돌은 실제 차단 결함이었으나, `tests/build-checks/`로 이동하고 두 파일을 명시적으로 추적해 해소됐습니다. 현재 5개 파일 해시는 갱신된 입력과 모두 일치합니다.

## 분석

- FE 경계가 적절히 분리됐습니다. 기본 Vitest는 파일·단위 스모크만 담당하고, `test:build`가 실제 빌드·라우트·타입 검증을 명시적으로 소유합니다. [package.json](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/package.json:10), [verify-build.mjs](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/tests/build-checks/verify-build.mjs:9)
- 빌드는 `before`에서 한 번만 실행되고, 같은 결과로 성공 문구와 필수 5개 라우트를 검사합니다. 라우트의 마지막 토큰을 정확히 비교하므로 기존의 부분 문자열 검사보다 계약이 강합니다. [verify-build.mjs](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/tests/build-checks/verify-build.mjs:16)
- 기본 Vitest 출력에서 빌드·타입 성공을 주장하지 않고 별도 명령을 안내합니다. 검증 누락 가능성도 README에 명시했습니다. [upgrade-smoke.test.ts](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/tests/smoke/upgrade-smoke.test.ts:176), [README.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/tests/build-checks/README.md:3)
- SQLite 변경은 제품 저장 계약을 건드리지 않습니다. `db_path`를 주면 기본 `data/` 결합을 우회하는 기존 인터페이스를 그대로 사용합니다. [paper_trading.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/services/paper_trading.py:91)
- 변경한 5개 테스트는 각 테스트의 `tmp_path`에 같은 DB를 배치해 재시작 의미를 유지합니다. [test_paper_trading_service.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/services/test_paper_trading_service.py:1418), [test_paper_trading_service.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/services/test_paper_trading_service.py:1860)
- 정리는 서비스의 정확한 DB 경로와 그 경로에서 파생된 `-wal`, `-shm`만 삭제합니다. 공통 연결은 `with` 종료 시 닫히므로 sidecar 제거 전제도 충족합니다. [test_paper_trading_service.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/tests/services/test_paper_trading_service.py:58), [sqlite_utils.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/services/sqlite_utils.py:20)
- 이미 쌓인 원본 `data/` 파일 삭제는 범위 밖으로 남아 있습니다. [TODO.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/TODO.md:1125)

## Root Cause

FE 원인은 상태를 공유하는 `.next` 빌드를 기본 Vitest 내부에서 두 번 실행해 외부 빌드와 충돌시킨 경계 혼합입니다. INFRA 원인은 일부 테스트가 `db_name` 기본 경로를 사용해 저장소 `data/`에 DB를 만들고, 정리가 본체만 제거해 WAL·SHM을 남긴 것입니다. [TODO.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/TODO.md:418), [TODO.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/TODO.md:1119)

## 가장 강한 반론

빌드 검증을 기본 `npm test`에서 분리하면 해당 명령만 실행하는 개발자나 CI가 빌드 회귀를 놓칠 수 있습니다. 다만 이는 요구된 분리 정책이며, 별도 명령과 필수 병행 실행을 명확히 문서화했습니다. 향후 CI가 있다면 두 명령을 순차 필수 단계로 연결하는 것이 운영상 남은 보완점입니다. [README.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/frontend/tests/build-checks/README.md:5)

## Architectural Status

`CLEAR`

검증 근거는 경로 수정 후 빌드 3/3, 동시 Vitest 459/459, 전체 pytest 2279 통과·3 skip, typecheck 0, lint 0 error·194 warning입니다. 현재 5개 소스는 staged 상태이며 새 파일 두 개가 `git ls-files`에 포함되고 `git diff --cached --check`도 통과했습니다. 최초 BLOCK과 수정 이력도 보존됐습니다. [architect-initial-block.md](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/test-isolation-20260909/architect-initial-block.md:3)

---
리더 보충: 위 내용은 독립 리뷰 원문이다. INFRA의 누적 WAL·SHM 원인은 과거 기록이며 현재 AutoClosingSQLiteConnection 상태에서 같은 누적 현상을 재현했다고 주장하지 않는다. 이번 재발 방지 검증은 직접 data 경로 쓰기를 차단하고 정확한 sidecar 정리를 확인한다.
