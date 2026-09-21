# 독립 T3 심층 리뷰

- 최종 코드 리뷰 판정: **APPROVE** — 미해결 지적 0건. 전체 사이클·브라우저 QA 완료 판정과는 구분한다.
- 검토 기준: `63b1db0`, `review-frozen.json`의 29개 경로. 최종 전달 범위 해시: `aee99f0321cee7d56b5cbe8ce07f9ab989ce7cb588f929bb816cae88875f11a3`.
- 방식: Codex App 대응 읽기 전용 리뷰. gstack Pre-Landing Review Checklist의 두 패스를 적용하고 조건부 부작용·자원 회수·값 완전성을 추가 확인했다. native gstack/Claude CLI/LSP를 실행했다는 의미가 아니다.

## 해결한 지적

### P2 — 개인 캐시 손상의 파급 범위: 해결

- 위치: `engine/collectors/krx_local_data_mixin.py:462-468`, 호출 경로 `:509`, `:528`; 소비자는 `engine/collectors/naver_pykrx_mixin.py:471-479` 및 KRX `get_supply_data`다.
- 근거: `individual_schema == 1`일 때 개인 값을 `int(float(...))`로 변환한다. 불리언이나 소수는 검증된 정수 금액으로 바뀐다. 개인 값의 NaN·숫자가 아닌 문자열은 같은 try에 있는 정상 외국인·기관까지 포함한 캐시 전체를 폐기하고, 무한대는 잡히지 않는 `OverflowError`를 전파한다.
- 영향: 손상된 개인 캐시 하나로 허위 개인 금액을 반환하거나 정상 외국인·기관 캐시를 잃고 외부 재조회/전체 수급 fallback으로 진행한다. 상세 서비스의 엄격한 개인 숫자 검증과도 불일치한다. 정상 생산자가 생성한 현재 캐시에서 문제가 발생했다고 주장하는 것은 아니며, 버전 표식이 있는 잘못된 캐시를 읽는 조건의 결함이다.
- 수정 확인: `engine/investor_personal_flow.py`의 `cached_personal_value`를 KRX와 상세 서비스가 함께 사용한다. 정확한 int 버전 표식과 비bool 유한 정수만 보존하고, 개인 검사 실패는 None으로 반환한다. KRX의 외국인·기관 파싱 try와 분리돼 개인 손상이 그 값을 폐기하지 않는다. int형 금액과 정수형 float는 유지한다.
- 검증: 관련 회귀 RED 이후 GREEN 증거가 추가됐고, 최종 import 수정 뒤 개인/패키지/상세/KRX/Naver 검사를 묶은 `pytarget-import-repair.json`의 exit 0을 확인했다. 테스트 본문은 읽지 않고 이름과 실행 요약만 검토했다.
- 신뢰도: **높음** — 변환식과 예외 범위 및 실제 호출자를 직접 읽어 확인했다. 이 리뷰에서는 코드를 실행하지 않았다.

### P1 — 수정 과정의 import 순서 회귀: 해결

중간 범위 `53ca8db9f55464e05c3d2c67e07b964176de121d02552dd8ecb0d01f421723a4`에서 logger 초기화가 logging import보다 먼저 실행되는 오류를 발견했다. 이때 `pytest-deep-final.json` exit 2와 `fixture-deep-final.json` exit 1도 확인했다. 최종 소스는 logging/math import를 logger와 함수보다 먼저 수행한다. 이후 `pytarget-import-repair.json` exit 0 및 `fixture-import-repair.json` exit 0을 확인하여 해결로 판정했다. 이전 GREEN을 재사용하지 않았다. 최초 P2 보고서는 `deep-review-initial.md`에 보존됐다.

## 추가 결함을 확인하지 못한 범위

- 공개 수집기 패키지와 lazy export, 기존 공개 KRX에서 이동한 캐시·상위 등락·CSV/Toss fallback·차트·수급 메서드를 대조했다. 제거한 private 캐시 함수의 제품 호출자도 검색했다. 변경하지 않은 큰 캐시 메서드는 이전 공개 구현과 텍스트 대조했다.
- 개인 수급의 다섯 날짜 완전성, 선택된 외국인·기관 날짜 집합과의 일치, Toss 가격 곱셈의 중복 방지, 구형 참조/상세 캐시의 결측 변환, Naver/KRX/API/UI 소비 경로를 추적했다.
- 과거 스크리닝 cutoff, 가격 부족 후보 제외, 최대 네 후보 준비·조회, ticker 중복 제거, 원래 순서 소비, 정상 CSV의 참조 조회 억제와 실패 결과 재사용을 확인했다.
- 참조 키의 data_dir/provider/ticker/날짜 구분, Future 소유자·대기자, 실패 TTL과 상한, clear 세대 분리, 메모리/SQLite publish 직렬화, executor 종료 경계를 읽었다. 네트워크 중 전역 참조 잠금을 잡지 않는다. SQLite publish 동안의 잠금 및 공급자 전체 deadline 부재는 설계에 명시된 제한이다.
- 이 범위에서 새 SQL 조립·셸 실행·LLM 출력 소비·인증 변경을 찾지 못했다. 기존 async 수집 메서드의 동기 I/O를 새로 해결했다고 평가하지 않았다.

## 증거와 검토 한계

- 테스트/fixture는 이름·변경 통계·증거 요약만 확인했다. fixture 본문과 실제 데이터는 열람하지 않았다. 주 작업이 전달한 이전 Vitest 634, build/typecheck/lint 및 합성 600후보 성능은 이전 단계의 증거다. 최종 소스에 대한 `pytarget-import-repair.json`, `fixture-import-repair.json`, `pytest-import-repair.json`의 exit 0을 직접 확인했다. 주 작업이 전달한 상세 결과는 관련 검사 77 PASS, fixture 6모드 PASS, 전체 pytest 2449 PASS/3 skip이다. 모든 실행은 주 작업의 격리 환경에서 수행됐으며 독립 재실행 결과가 아니다.
- 원본 `.env`, `data/`, 3500/5501, 라이브, 네트워크, LLM, 수집, 설정, 거래, 충전, 삭제에 접근하지 않았다. import/test/compile이나 서브에이전트도 실행하지 않았다.
- 실제 브라우저 오류복구·표시·콘솔 검증은 주 작업의 후속 QA 범위다. 본 보고서만으로 QA 완료 또는 전체 사이클 완료를 주장할 수 없다.
- 최종 변경분을 다시 읽고 동결 목록과 영향받는 경로의 새 검증 요약을 대조했다. 주 작업은 전체 검증 및 브라우저 QA를 마무리한 뒤 사이클 완료를 별도로 판정해야 한다.
