# 준비 진단

- CHAT-015 통합 렌더 검사의 default import가 실제 named export와 달라 실패. named import로 고친 뒤 1/1 통과. 제품 실패 아님.
- 하네스 초안은 Python 들여쓰기 오류와 누락된 입력 분기·로그·정리 검사가 있었다. 실행 전 부모가 확인하고 과거 검증된 launcher 원문으로 교체, fixture의 정상 JSON/long SSE/parser/헤더 digest 기록을 보완했다. 에이전트의 static PASS 주장을 재사용하지 않는다. 원문 initial-*.gz 보존.

- QA iteration1: 정상 JSON/신규세션은 통과. 합성 SSE의 첫 청크25초 대기 실패. direct API는 즉시3frames, Next proxy gzip은3초간10bytes만 수신하고 종료후 전체본문이 표시됐다. fixture Cache-Control no-store가 실제 backend의 no-cache,no-transform 계약(app/routes/kr_market_chatbot_http_routes.py:220-221)을 빠뜨려 Next 압축 버퍼링 발생. no-transform/X-Accel-Buffering:no로 fixture만 수정. 첫 중단 클릭은 이미종료되어 stale ref실패(제품실패아님). 브라우저·소유서버 정리후 iteration2재시도.

- QA iteration2: SSE 첫청크/중단/중복차단/세션B보존/모바일중단 및 FE038 header digest3개일치 통과. CHAT015 parser-state에서 h3=[빈문자열,본문제목] 확인. ThinkingProcess.normalizeOrderedListMarkdown의 두번째전처리가 추론제목을 다시분리. 실제h3통합RED 후 line-wise제목제외로 보완, iteration3 재검수 예정. 제품 범위안 필수실패로유지.

- 후속리뷰: 추론제목 보완에서 한 줄 안의 새 개행을 다음 orderedMarker 단계로 다시분리하지 않는지 조사. spaced `1) 첫째 2) 둘째` 통과는 공백없는 `1)첫째 2)둘째` 계약의 증거가 아니므로 정확한 입력으로 추가검증.

- 공백없는1)추가통합검사는RED재현되지않았다(exit0). 이를제품결함으로보고하지않는다. 최종수정은 제목제외변환뒤기존줄별marker정규화순서를그대로유지하며 const로새lint경고제거. 최종target5/5, type0, lintquiet0.
