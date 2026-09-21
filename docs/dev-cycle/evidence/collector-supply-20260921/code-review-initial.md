## 코드 리뷰 요약

**검토 범위:** base `63b1db049b1d351a6b66c66d84b6a71845b4601d`, 동결된 29개 경로
**범위 검증:** 29개 SHA가 `review-frozen.json`과 모두 일치
**review-diff SHA-256:** `e1460cb81839910dbc4c7bdacb6f2e4272033f7ab93aea0f4412223de2a3164f`
**review-frozen SHA-256:** `33a0d51073da74ffc2335aa2fd126dc0d2031a07373d0ec35da9bd4732d5c3dd`

**총 이슈:** 2

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 1
- LOW: 1

### 이슈

[MEDIUM, 높은 신뢰도] 개인 수급의 선택 날짜가 캐시 왕복 과정에서 검증되지 않음
파일: `services/investor_trend_5day_service.py:476`, `services/investor_trend_5day_service.py:499`, `services/investor_trend_5day_service.py:505`

`_normalize_external_trend_payload()`가 `details`를 다시 만들면서 날짜를 제거합니다. 이후 개인 수급은 다섯 날짜가 고유하고 최대 날짜가 `latest_date`와 같은지만 확인합니다. 따라서 `details`가 선택한 날짜가 `18,17,16,15,14일`인데 `individual_details`가 `18,17,16,15,13일`인 marker 1 페이로드도 유효한 개인 수급으로 받아들입니다.

이는 명세의 다음 계약을 충족하지 못합니다.

- 선택된 다섯 거래일 밖의 개인 값을 거부
- 정규화된 `details`가 캐시 왕복 후에도 다섯 날짜 문자열을 유지

위험: 손상되거나 서로 어긋난 신규 SQLite 페이로드가 실제 선택 기간과 다른 개인 수급을 정상 값으로 표시할 수 있습니다. 외국인·기관은 보존되지만 개인 값의 기간 정합성이 깨집니다.

수정:

- 참조 공급자 `details`에도 날짜를 넣고 정규화 결과에서 유지합니다.
- 개인 상세 날짜 집합과 선택된 `details` 날짜 집합이 정확히 같은지 확인합니다.
- marker 1 캐시라도 날짜가 없거나 불일치하면 개인만 `None`으로 내립니다.
- 서로 다른 `details`/`individual_details` 날짜 집합과 SQLite 왕복 후 날짜 보존 회귀 검사를 추가합니다.

[LOW, 높은 신뢰도] 변경된 수집기 모듈의 import 순서가 저장소 규칙을 위반함
파일: `engine/collectors/krx.py:7`, `engine/collectors/krx_data_mixin.py:7`, `engine/collectors/krx_local_data_mixin.py:7`, `engine/collectors/naver_pykrx_mixin.py:7`, `services/investor_trend_5day_service.py:12`

표준 라이브러리, 서드파티, 로컬 import가 섞여 있고 그룹 사이 빈 줄도 누락됐습니다. 예를 들어 `naver_pykrx_mixin.py`는 로컬 import가 표준 라이브러리 사이에 놓입니다.

수정: 각 파일을 표준 라이브러리 → pandas 등 서드파티 → `engine`/`services` 로컬 순으로 재배치하고 그룹 사이를 한 줄 띄웁니다.

### 확인된 계약

- 공개 경로와 하위 경로가 동일한 `KRXCollector` 클래스를 노출합니다.
- 이동된 KRX 모듈의 `BASE_DIR`은 세 단계 상위인 저장소 루트를 가리키며 상대·절대 `DATA_DIR` 처리가 보존됩니다.
- 실패 TTL, 동일 키 Future 공유, generation 기반 clear, SQLite 게시 직렬화는 요구한 경합 모델과 일치합니다.
- `max_stocks` cutoff를 준비 전에 확정하고 중복 ticker는 물리 조회만 합치며 후보 결과는 보존합니다.
- UI는 모달을 닫을 때 컴포넌트를 unmount하고 재개방 시 다시 fetch하므로 실제 0과 `자료 없음`, 이후 복구 응답이 이전 숫자에 가려지지 않습니다.
- 새 하드코딩 비밀, 타입 억제, 빈 예외 처리, 실패를 숨기는 신규 우회 경로는 발견하지 못했습니다.

### 검증 증거

보존된 격리 실행 증거를 확인했습니다.

- pytest: `2435 passed, 3 skipped`
- Vitest: `634 passed`
- Next build 검사: `3 passed`
- TypeScript typecheck: PASS
- ESLint: 오류 0, 경고 184
- 성능 중앙값: `36.42초 → 10.08초`, 비율 `0.277`
- 600개 결과 digest 동일, 실제 fetch 600회, 최대 동시성 4
- `git diff --check`: PASS

리뷰 lane 제약에 따라 테스트·컴파일·소스 import 및 LSP 진단은 새로 실행하지 않았습니다. 실제 브라우저의 닫기·재열기 검증은 후속 UltraQA 증거가 아직 남아 있습니다.

### 권고

**REQUEST CHANGES**

날짜 보존과 날짜 집합 일치 검증을 고친 뒤 관련 개인 수급·캐시 회귀 검사를 다시 실행해야 합니다. 낮은 신뢰도의 추가 관찰 사항은 없습니다.
