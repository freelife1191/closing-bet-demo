# NumPy2/pykrx 보안 패키지 Implementation Plan

> 실행: 리더 구현·격리검증, native 독립 계획/코드/구조/보안 리뷰. 사용자가 업그레이드와 검증을 명시했고 승인 판단을 위임했다.

**Goal:** INFRA-018의 쿠키 경계와 NumPy2 호환성 검수를 통과해 업그레이드를 완료한다.
**Architecture:** 공식wheel+검증된최소patch+localversion 고정. 실제공급자통신만대역으로하고실제라이브러리/앱을검사한다.
**Spec:** design.md

## 작업
- [x] 공식1.2.9 소스URL·인증흐름 확인(webio+auth.py 최소patch,실행KRXURL은이미HTTPS),독립 계획검토 ACCEPT. HTTPS KRX URL목록과필요패치확정.
- [x] tests의 독립subprocess로 실제Get/Post preparedrequest 쿠키누출 RED. trustedHTTPS의 인증유지·publicGET/POST cookie없음·globalrefresh미호출·HTTP/위장host/port/userinfo·URL단일평가·인증redirect차단을 검사한다. requests HTTPAdapter만대역,실제외부0. 직접 KRXSession.get/post 외부요청도 검사하며 CookieJar의KRXdomain/path/secure쿠키만 허용된요청에 붙는지 확인한다.
- [x] 이전 차단의 정확한 고수준 stock.get_market_ohlcv_by_date→Naver HTTP를 실제로 실행: domainless 가짜KRX쿠키가 있어도 prepared Cookie/Authorization없음, globalrefresh/authsession 호출0, 실제외부0, XML에서종가71000 반환을 영구subprocess회귀로 고정한다.
- [x] vendor/pykrx/transport.patch와rebuild.py,README,localwheel작성. upstreamSHA/라이선스·METADATA/RECORD정합성·재빌드두번동일SHA확인.
- [x] requirements numpy2.4.6/pykrx1.2.9+cookie.1 (--find-links vendor/pykrx). 깨끗한candidatevenv 표준-rrequirements설치, pipcheck,OSV검증(localversion은upstream1.2.9도조회해누락방지).
- [x] 실제pykrx6API DataFrame계약·NumpyEncoder 지원타입·yfinance/SDK기존회귀·전체pytest/Vitest/type/lint/build. 기존테스트기대값을임의완화하지않는다.
- [x] ponytail→code/architect→security/T3deep 리뷰. 제품 SHA동결/QA행렬/첫커밋.
- [x] UltraQA App 대응으로 쿠키행렬·실제NumPy2backend→실제NextVCP UI/차트오류복구·JSON검수. ego 신규TaskSpace1개,실제OAuth/LLM/시세호출없음.
- [x] 소유프로세스/공간/scratch정리와사용자rootpackageSHA불변. 필수전부통과후INFRA018만archive.

## 검증 초점
인증게이트에서URL을검사한후다시읽어바뀌는TOCTOU, CookieJar의domainless쿠키, 대소문자/port/userinfo유사origin, redirect누출, localwheel의재현성/설치경로, NumPy2값직렬화/프레임형태, 원본실데이터·환경부작용을검사한다.
재개기존UltraQA iteration1/same_failure1에서 수정범위를확장한회차2로잇는다. 실패한N4/N5를삭제하거나optional로바꾸지않는다.
