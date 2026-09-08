# INFRA-060 최종 격리 UI QA

대상은 임시 bare Flask `127.0.0.1:58235`, Next `127.0.0.1:58786`, 임시 SQLite와 합성 NextAuth JWT뿐이다. 원본 환경·데이터·포트 3500/5501·라이브 URL은 사용하지 않았다. 브라우저 세션은 `infra060-ui`이며 외부 HTTPS route를 abort했다.

| 시나리오 | 기대 | 관측 | 결과 |
| --- | --- | --- | --- |
| 익명 | 로그인 안내, 거래 자료·주문 UI 없음 | 안내 문구만 표시, 포트폴리오 요청 없음 | 통과 |
| Alice | Alice 보유·이력만 표시 | `Alice QA / 005930 / 1주`, 매수 이력 1건, 기존 예수금 `119,999,000원` | 통과 |
| 동일 계정 refresh | 3개월 선택 유지 | fixture에 `1,000,000원` 추가 충전 뒤 `120,999,000원`, 3개월 선택 유지 | 통과 |
| Bob 전환 | Alice 자료 없음, Bob 자료만 표시 | `Bob QA / 000660 / 2주 / 99,996,000원`, DOM `hasAlice:false` | 통과 |
| 인증 세션 401 | 로그인 안내·주문 UI 제거 | 임시 backend가 `GET /api/portfolio`에 401을 반환했고 안내 문구만 표시 | 통과 |
| 늦은 mutation 응답 | A 응답이 B UI를 닫거나 알리지 않음 | 실제 `BuyStockModal` deferred A→B→A성공 회귀와 account guard 회귀 9개 통과 | 통과 |
| Next runtime | 오류·컴파일 이슈 없음 | 활성 browser session MCP SSE에서 `configErrors: []`, `sessionErrors: []`, `issues: []` | 통과 |

증거: `anonymous.png`, `alice-holdings.png`, `alice-history.png`, `alice-after-refresh-3m.png`, `bob-holdings.png`, `authenticated-401.png`, `browser-requests.json`, `late-mutation-deferred.log.gz`, `get-errors.sse.gz`, `get-compilation-issues.sse.gz`.

정리 완료: 58235/58786의 소유 프로세스와 `infra060-ui` browser session을 종료했다. 임시 qa page/route, QA_FORCE_PORTFOLIO_401 하네스 분기, 임시 SQLite와 PID/포트 메타데이터, checkout QA 준비 디렉터리는 제거하고 파일은 휴지통으로 옮겼다. 제품 source manifest 34개를 다시 해시해 mismatch 0건을 확인했다.
