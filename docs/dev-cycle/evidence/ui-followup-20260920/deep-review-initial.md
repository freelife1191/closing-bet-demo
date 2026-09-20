Pre-Landing Review: 1 issue (0 critical, 1 informational)

[INFORMATIONAL] frontend/src/lib/api.ts:31,49 — fetchAPI가 응답 헤더 직후 timeout을 해제하고 response.json()을 await하지 않아 JSON 본문이 정체되면 FE-031 갱신과 매수 가격 조회가 무기한 대기합니다.

Fix: 31행의 조기 clearTimeout을 제거하고 return await response.json()으로 본문 완료까지 타이머를 유지하세요. 헤더는 반환됐지만 json()이 정체되는 회귀 검사도 추가해야 합니다.

Verdict: REQUEST CHANGES

파일별 LSP는 transport 종료로 실행 불가했고 동결 SHA의 typecheck 0·lint 0 errors 증거로 대체했습니다. 브라우저 QA 성공은 아직 판정하지 않았습니다.
