판정: CUT — 2건, net -12 lines possible.

BuyStockModal.tsx:L56-57,L67,L84,L103-114: shrink: loadingPrice와 priceLookupFinished가 같은 비동기 생명주기를 중복 표현합니다. loadingPrice = !priceLookupFinished && fetchedPrice === null로 파생해 상태와 setter를 제거하세요. 예상 -3줄.

closing-bet/page.tsx:L232-237, page.regression-jongga-followup.test.tsx:L85-89: native: focus 가능한 overflow-x-auto 영역은 브라우저가 화살표 키 스크롤을 제공합니다. 수동 scrollBy(160) 핸들러와 구현 미러 테스트를 삭제하고 focusability·설명 연결 회귀만 유지하세요. 예상 -9줄.

검증 근거:
- manifest 16/16 SHA 일치
- git diff --check 통과
- 부모 제공: pytest2320/3skip, Vitest582/80files, lint0err/191warn, build clean-cache3/3, typecheck0, fixturePASS
- LSP transport unavailable 기록, 격리 tsc0이 별도근거
- JONGGA031 entry_price+signal_date 보완 전 스냅샷판정이며작은diff후속재검토필요

리뷰어는읽기전용으로원문을회신했고부모가보존. 최초manifest는후속sync로갱신됐으므로초기CUT을최종PASS근거로재사용하지않는다. 최종재검토에서manifest동결사본과파일별SHA를보존한다.
