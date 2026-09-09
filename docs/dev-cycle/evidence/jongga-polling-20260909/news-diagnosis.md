# INFRA-069 원인 및 보완

독립 진단: scheduler_round_scope (읽기 전용). 제품 뉴스 정렬 변경 없음.
get_stock_news는 fetcher 전에 클래스 메모리 및 SQLite 캐시를 조회한다. 첫 두 테스트는 fetcher만 monkeypatch하므로 캐시 hit 시 모의 입력을 건너뛴다. 초기 전체 실행에서 실제 뉴스가 반환되어 1실패/2280통과/2skip.

수정: 수집/정렬·일부 소스 실패를 검사하는 첫 두 테스트에만 _load_cached_news_items→None, _save_cached_news_items→no-op. 기대값은 그대로 유지. tmp_path 기반 별도 캐시 검사 유지. 원본 캐시 삭제/초기화 없음.

검증: 대상 모듈 8통과. 전체 재검증 결과 별도 기록. 테스트 전용 변경이므로 dev-cycle tier-rules §1-1의 브라우저 QA 제외에 해당한다. 종가 제품 변경은 별도 필수 웹 QA를 수행한다.
