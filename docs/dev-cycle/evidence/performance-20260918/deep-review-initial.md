## Code Review Summary

**검토 파일:** 14개 SHA 일치
**총 이슈:** 2

### 이슈

[HIGH] (신뢰도 8/10) `services/kr_market_backtest_trade_helpers.py:150` — 새 입력 계약은 `date` 값을 ISO 문자열로만 허용하지만, `services/kr_market_data_cache_sqlite_payload.py:679`의 `pd.read_json()`은 기본 날짜 변환으로 `date` 컬럼을 datetime으로 복원합니다. 메모리 캐시가 비고 SQLite 캐시만 남은 재기동 경로에서 이 값이 거부되어, `services/kr_market_analytics_service.py:387`이 예외를 잡고 실제 종가 성과 대신 기본 `Accumulating` 상태를 반환할 수 있습니다.

Fix: CSV SQLite 역직렬화에서 원본 문자열 타입을 보존하거나 스냅샷 로더에서 ISO 문자열로 복원하십시오. 메모리 초기화·SQLite warm 상태에서 실제 `calculate_jongga_backtest_stats`까지 연결해 판정 상태가 유지되는 회귀를 추가해야 합니다.

[MEDIUM] (신뢰도 10/10) `frontend/src/app/dashboard/kr/page.tsx:127` — 사용자가 양쪽 성과 카드에서 열 수 있는 기준표가 승률을 `익절 / 전체 진입`, 평균을 `익절+손절`로 설명합니다. 실제 계약은 `WIN / (WIN+LOSS)`이며 평균에는 OPEN의 현재 평가수익률도 포함됩니다. 이번 성과 설명 정합화 범위가 해당 소비자를 누락했습니다.

Fix: 승률 분모에서 OPEN 제외를 명시하고, 평균 수익률은 청산 손익과 OPEN 현재 평가수익률을 전체 신호 수로 나눈 값이라고 수정하십시오. 기준표 회귀도 추가해야 합니다.

### 판정

**REQUEST CHANGES**

SQL·경합·셸·LLM 신뢰 경계·상태 소비자에서 다른 신규 문제는 확인되지 않았습니다. 기존 증거는 pytest 2310/3 skip, Vitest 505/71, lint 0 errors, build 3/3, 프로젝트 tsc exit 0입니다. 이 리뷰에서는 지시대로 테스트·LSP·서버·HTTP를 실행하지 않았으며, 필수 브라우저 QA는 별도의 후속 gate로 남습니다.

## 후속 확인 원문

확인했습니다. 현재 판정은 **REQUEST CHANGES**로 유지합니다.

재검토 시 naive datetime64 `date` 허용이 timezone·정렬·NaT 검증을 그대로 유지하는지, warm SQLite 실제 경로 회귀와 기준표 UI 회귀가 두 지적을 직접 고정하는지 확인하겠습니다.
