# KRX·AI 숫자 오류 수정 UltraQA

- 항목: INFRA-072 / JONGGA-038, T3. engine=ultraqa, lifecycle=app-adapted, iteration=1, phase=baseline, same_failure_count=0.
- 기준537470b+frozen.json11경로. 사용자 진행해 승인으로 기존결함수정/실제재분석. 브라우저ego-browser required.
- 테스트는scratch/네트워크차단, 원본data/logs/env접근차단. 실제분석단계만원본환경/실API허용, 알림/거래없음.

| ID | 의도/입력 | 기대 | 실제 | 증거·정리 |
|---|---|---|---|---|
| K1 | 명명/무명/custom index | 종목코드보존, 빈코드오류 | 표적PASS | test_krx_named_index |
| K2 | memory/SQLite손상캐시 | 전체miss후실조회 | 표적PASS | 같은테스트,임시데이터 |
| N1 | 잘못된금액/가격/Unicode/한국수사 | 거부,정상원자재/지원/섹션허용 | 표적PASS | test_jongga_numeric_guard |
| N2 | 오류→정상/오류반복 | 총2회제한,typederror저장차단 | 표적PASS | 같은테스트 |
| N3 | 검증후facts | 현재가·거래대금원값·조억·수급일치 | 표적PASS | 같은테스트 |
| E1 | 실제KRX→전체분석 | 빈코드없음,새검증통과후저장 | 대기 | 원본백업·알림없음 |
| E2 | 브라우저/숫자대조 | 최신결과·오류없음·원자료facts일치 | 대기 | Space종료 |
| C1 | 보존/정리 | 설정/rootpackage보존,임시자원제거 | 대기 | 서비스유지 |

초기RED는숫자guard미구현과KRX명명인덱스/빈코드오류. 첫전체검증의cache테스트fixture는단독mixin에누락된메서드를사용해실패,실제KRXCollector기반fixture로고쳐표적51PASS. 제품기대값완화없음. 전체재검증중.

## 독립 리뷰 보완
- 계획: lexical계약모호 REJECT→섹션마커/Unicode/한국수사/일반단어구분명시 ACCEPT.
- Ponytail: Lean already. Ship.
- Code REQUEST CHANGES: 조사붙임한국수사/외화우회, 불완전reason허용. Architect BLOCK: Phase3 missingclient 조기return우회.
- 지적7개재현 RED→수정후표적58PASS. Phase3의missingclient/불완전청크/일반오류도typederror전파. 기존 정상빈입력만허용한다. 기존no-client/partial청크테스트는바뀐저장보호계약으로수정했으며삭제하거나오류를성공으로완화하지않았다.
- 현재 11개소스/테스트 frozen 갱신. 최종전체검증/재리뷰중.

최종 표적64PASS, 전체2512PASS3skip(기존manual2·env미설정1)55.52초. Vitest641/84files. 코드/구조리뷰차단해소. 최종수량검사는후행수식어와무관하게일치하므로숫자처럼보이는일반단어를보수적으로거부할수있다. 제품의원자료가격/거래대금자체를모델이계산하지않으며,정성판단전체정확성을보장한다고주장하지않는다.
