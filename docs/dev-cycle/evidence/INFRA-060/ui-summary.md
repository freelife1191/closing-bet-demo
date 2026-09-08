# INFRA-060 격리 UI 실측

- 대상: Next `127.0.0.1:58786`, bare Flask fixture `58235`만 사용했다.
- 익명: `qa-session?user=none` 뒤 모의투자 로그인 안내가 표시되고 포트폴리오 요청은 없었다.
- Alice: `Alice QA / 005930 / 1주 / 99,999,000원`과 매수 이력을 확인했다.
- Alice fixture에서 차트 기간을 3개월로 선택한 뒤 1천만 원 충전했다. 갱신 뒤 `109,999,000원`과 선택된 3개월 버튼을 확인했다.
- Bob: 전환 뒤 `Bob QA / 000660 / 2주 / 99,996,000원`만 보이고 Alice QA는 없었다. Alice 충전은 Bob 잔고에 영향을 주지 않았다.
- Ponytail 수정 뒤 Alice fixture에서 추가로 1천만 원을 충전했다. 최종 `119,999,000원`과 선택된 3개월 버튼을 다시 확인했다.
- Browser console에는 HMR/React DevTools 정보 외 오류가 없었다. `/_next/mcp`의 일반 GET은 406으로, MCP 전용 Accept 협상이 필요함을 확인했다.
- 활성 browser session에서 `get_errors` JSON-RPC를 POST한 SSE 응답은 `configErrors: []`, `sessionErrors: []`였다. 원문은 `ui/next-get-errors.sse.gz`에 저장했다.

스크린샷: `anonymous.png`, `alice-holdings.png`, `alice-history.png`, `alice-after-deposit-3m.png`, `alice-after-second-deposit-3m.png`, `bob-holdings.png`.
