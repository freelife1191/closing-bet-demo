# Code review — REQUEST CHANGES

검토29파일:실제26/삭제3, frozen SHA 일치. CRITICAL0/HIGH0/MEDIUM2/LOW1.

[MEDIUM] services/kr_market_data_cache_prices.py:47, kr_market_realtime_price_cache.py:390, kr_market_realtime_price_service.py:91: str(ticker).strip()==ticker_key는 공백alias를exact로간주. JSON정렬상공백키가먼저canonical키차단가능, SQLite동률규칙도원문exact비교로명확히할것. raw str(ticker)==ticker_key와회귀필요.

[MEDIUM] useQuota.ts:116, Sidebar.tsx:381, SettingsModal.tsx:501: 세션loading에서disabled→idle→무료10회표시. 승인초기'사용량확인중'계약위반. loading UI pending처리와기본10회부재검사.

[LOW] Sidebar.session.test.tsx:211: A→B/로그아웃은identity만으로도통과. 같은identity연속refresh의역순응답폐기와성공→실패시이전숫자제거검사추가.

명세: FE043/JONGGA030부분충족, FLOW006충족. SQL호환은알려진구형저장경계로한정되고원본DB변경없음.
검증자료: backend2417/3skip, Vitest625/83files, build3,lint0errors184warnings. Reviewer는실행/import/network/LSP하지않았고자료를읽음. browser/initialcommit전상태.
정적검사:새console.log/빈catch/hardcodedsecret없음. 낮은확신도추가지적없음.
