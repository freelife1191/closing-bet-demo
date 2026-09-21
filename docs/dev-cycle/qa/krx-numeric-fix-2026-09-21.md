# KRX·AI 숫자 오류 수정 UltraQA

- 항목: INFRA-072 / JONGGA-038, T3. engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=complete, same_failure_count=0.
- 기준537470b+frozen.json11경로. 사용자 진행해 승인으로 기존결함수정/실제재분석. 브라우저ego-browser required.
- 테스트는scratch/네트워크차단, 원본data/logs/env접근차단. 실제분석단계만원본환경/실API허용, 알림/거래없음.

| ID | 의도/입력 | 기대 | 실제 | 증거·정리 |
|---|---|---|---|---|
| K1 | 명명/무명/custom index | 종목코드보존, 빈코드오류 | 표적PASS | test_krx_named_index |
| K2 | memory/SQLite손상캐시 | 전체miss후실조회 | 표적PASS | 같은테스트,임시데이터 |
| N1 | 잘못된금액/가격/Unicode/한국수사 | 거부,정상원자재/지원/섹션허용 | 표적PASS | test_jongga_numeric_guard |
| N2 | 오류→정상/오류반복 | 총2회제한,typederror저장차단 | 표적PASS | 같은테스트 |
| N3 | 검증후facts | 현재가·거래대금원값·조억·수급일치 | 표적PASS | 같은테스트 |
| E1 | 실제KRX→전체분석 | 빈코드없음,새검증통과후저장 | PASS: 실제338후보,AI9건,최종8건저장 | live-run.json/live-stages.txt |
| E2 | 브라우저/숫자대조 | 최신결과·오류없음·원자료facts일치 | PASS:8건금액원값/조억원자료일치,브라우저/MCP오류0 | browser.json/png,Space32종료 |
| C1 | 보존/정리 | 설정/rootpackage보존,임시자원제거 | PASS:설정9개/사용자파일보존,소유scratch삭제 | preserved.json/cleanup.json |

초기RED는숫자guard미구현과KRX명명인덱스/빈코드오류. 첫전체검증의cache테스트fixture는단독mixin에누락된메서드를사용해실패,실제KRXCollector기반fixture로고쳐표적51PASS. 제품기대값완화없음. 전체재검증중.

## 독립 리뷰 보완
- 계획: lexical계약모호 REJECT→섹션마커/Unicode/한국수사/일반단어구분명시 ACCEPT.
- Ponytail: Lean already. Ship.
- Code REQUEST CHANGES: 조사붙임한국수사/외화우회, 불완전reason허용. Architect BLOCK: Phase3 missingclient 조기return우회.
- 지적7개재현 RED→수정후표적58PASS. Phase3의missingclient/불완전청크/일반오류도typederror전파. 기존 정상빈입력만허용한다. 기존no-client/partial청크테스트는바뀐저장보호계약으로수정했으며삭제하거나오류를성공으로완화하지않았다.
- 현재 11개소스/테스트 frozen 갱신. 최종전체검증/재리뷰중.

최종 표적64PASS, 전체2512PASS3skip(기존manual2·env미설정1)55.52초. Vitest641/84files. 코드/구조리뷰차단해소. 최종수량검사는후행수식어와무관하게일치하므로숫자처럼보이는일반단어를보수적으로거부할수있다. 제품의원자료가격/거래대금자체를모델이계산하지않으며,정성판단전체정확성을보장한다고주장하지않는다.


## 실제 검증 결과

구현 커밋 `e9577de`를 기존 Gunicorn 워커에 반영하고 실제 KRX 계정으로 `run_screener()`를 실행했다. 기존 결과는 `logs/krx-numeric-before-20260921/`에 백업했다. 알림 wrapper와 매매 기능은 호출하지 않았다.

- 실행147.5초. 정상 종목코드338개 후보를 검사해 AI9건 분석, 최종8개 시그널을 2026-09-21T22:18:44에 저장했다.
- 첫 시장은4건 분석→3건 최종, 두 번째 시장은5건 분석→5건 최종이다. 이전 토스 대체경로의12건과 입력 데이터가 같다고 가정하지 않는다.
- 실제 실행 중 응답 검증 실패1회가 발생했고, 허용된 한 번의 재작성 후 검증을 통과했다. 실패 문장을 그대로 저장하지 않았다.
- 저장된8건 모두 유효한 코드와 원자료 수치 구역이 있으며 거래대금 원값·조/억 표현을 최종 signal의 trading_value와 대조해 일치했다.
- 브라우저에는 CANDIDATES9, FILTERED8, UPDATED와 원자료 수치 구역이 표시됐다. PNG를 직접 열어 확인했다. JS/console/unhandled 오류0, 조회API모두200, Next MCP config/session/compilation 오류0.
- 기존 분석 근거의 잘못된 금액 표현은 회귀 입력으로 거부되는 것을 확인했다. 최신 결과는 검증된 새8건이며 과거 리포트 원본은 변경하지 않았다.
- 임의의 절대 손절/목표 제안을 AI 산문에서 허용하지 않고 기존 PositionSizer/UI 계산값을 참조하게 했다. 미래의 모든 정성 판단이 정확하다고 보장하는 변경은 아니다.

## 정리와 제한

설정 파일과 사용자 root package.json 총9개 해시가 일치한다. scratch와 임시 실행 파일을 제거했고 ego-browser Space32를 finish keep[]로1회 종료했다. 원본 서비스3500/5501은 계속 실행한다. 제품 소스/테스트의 frozen11개 해시가 QA 뒤에도 일치한다.

보수적인 한국어 수량 검사로 수원·공원 등 우연히 수량 문자와 겹치는 문장이 거부될 수 있다. 이런 경우에는 한 번 재작성하고 계속 실패하면 기존 리포트를 보존한다. 이 가용성 비용을 알고 선택했으며 검증 규칙을 비활성화하지 않았다.

Ego Lite 업데이트 알림이 있었으며 현재 검증에는 지장이 없었다. 브라우저 업그레이드는 이번 작업에서 수행하지 않았다.

ULTRAQA COMPLETE: Goal met after 1 cycle. 시나리오8/8 통과. 최종pytest2512/3skip,Vitest641,표적64,실제KRX/AI/브라우저 확인 완료.
