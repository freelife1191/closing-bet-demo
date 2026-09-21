## 코드 리뷰 요약

**검토 파일:** 동결 범위 29개
**총 이슈:** 1

### 심각도

- CRITICAL: 0
- HIGH: 1
- MEDIUM: 0
- LOW: 0

### 발견 사항

[HIGH] 공개 Market Gate GET에서 경로 탐색을 통한 임의 JSON 조회 가능
파일: [kr_market_market_gate_validity.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/services/kr_market_market_gate_validity.py:30)

`target_date`가 형식 검증 없이 파일명에 합쳐집니다. 예를 들어 `../../../data/<name>`은 `market_gate_../../../data/<name>.json`이 되고, [kr_market_system_http_routes.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/app/routes/kr_market_system_http_routes.py:64)에서 공개 GET이 이를 로드합니다. 로더는 [kr_market_data_cache_core.py](/Users/freelife/vibe/lecture/hodu/closing-bet-demo/services/kr_market_data_cache_core.py:357)에서 `abspath(join(data_dir, filename))`만 적용하므로 경로를 `data/` 안에 가두지 않습니다. 결과가 객체형 JSON이면 응답에 그대로 포함됩니다.

이 결함은 이번 diff에서 새로 도입되지는 않았지만, INFRA-047이 정의하는 공개 조회 경계에 직접 포함됩니다. 저장소의 `data/`가 사용자 자료를 포함하므로 정보 노출 위험이 있어 병합 차단으로 판단합니다.

수정 방법:

- `target_date`를 `YYYY-MM-DD` 또는 `YYYYMMDD`로 엄격하게 전체 일치 검증합니다.
- 잘못된 값은 파일 로더를 호출하기 전에 400으로 거부합니다.
- 방어적으로 최종 경로가 `data/`의 실제 경로 아래인지 확인합니다.
- `../../../data/...` 입력에서 로더가 호출되지 않는 회귀 테스트를 추가합니다.

### 명세 준수 결과

나머지 요구사항은 구현되어 있습니다.

- 세 감사 지점이 `X-Forwarded-For` 대신 `remote_addr`를 사용합니다.
- portfolio GET과 lazy singleton 생성이 가격 동기화를 시작하지 않습니다.
- 동기화 시작이 scheduler lock 획득 후 bootstrap에만 배치됐습니다.
- 비리더 워커가 조회마다 공유 SQLite 가격 캐시를 다시 읽습니다.
- Market Gate GET 자동 갱신과 관련 상태·도우미·배선이 제거됐습니다.
- Procfile 삭제와 프론트엔드 주석 변경이 계획 범위와 일치합니다.
- 실패를 숨기는 새 우회 경로는 발견하지 못했습니다. 스케줄러의 가격 동기화 시작 실패 후 기존 잡을 유지하는 예외 처리는 명세에 명시된 제한적 장애 격리입니다.

### 검증 증거

- 동결된 29개 파일 해시 모두 실제 작업 트리와 일치
- `git diff --check`: 통과
- TSX LSP/TypeScript 진단: 오류 0
- Python 파일 진단 도구: 보고된 진단 0이지만 Python 분석 백엔드 없이 실행된 결과라 신뢰 범위가 제한됨
- AST 검사: 새 `console.log`, 빈 catch/except, 하드코딩 시크릿 없음
- 보관된 실행 증거:
  - 대상 pytest: 132 통과
  - 전체 pytest: 2,441 통과, 3 제외
  - Vitest: 640 통과
  - 타입 검사: 통과
  - lint: 오류 0, 기존 경고 184
  - 빌드: 3개 검사 통과

명시된 제한에 따라 테스트와 제품 코드는 직접 실행하지 않았으며, 동결된 실제 로그를 검증했습니다. 아키텍처 평가는 별도 lane 범위입니다.

### 권고

**REQUEST CHANGES**

공개 GET의 경로 탐색을 차단하고 회귀 테스트를 추가한 뒤 재검토해야 합니다.
