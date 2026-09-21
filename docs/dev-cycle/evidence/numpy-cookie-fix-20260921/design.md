# INFRA-018 NumPy2와 pykrx 통신 경계 수정

사용자 요청: 쿠키 문제 설명 후에도 «업그레이드하고 검증해». 앞선 승인 판단 위임이 유지되며, 단순 보류를 반복하지 않고 최소 수정 배포본을 검토한다.
brainstorming architectural: 원격 의존성에 작은 보안 수정을 적용한 로컬 wheel을 표준 설치 경로에 포함한다. T3.

## 의도와 결정
NumPy2.4.6/pykrx1.2.9 기반으로 시세·JSON·화면 계약을 유지한다. 원래1.2.9의 publicNaver 요청은 KRX Cookie를 전달하므로 그대로 설치하지 않는다.
공식 wheel을 SHA256으로 검증한 뒤 webio와 auth.KRXSession.get/post의 인증 세션 선택을 정확한 HTTPS KRX origin으로 제한한다. 인증된 요청은 redirect를 자동 추종하지 않아 rawCookie/세션cookie가 타출처로 전파되는 경로를 닫는다. public GET/POST는 별도 요청 세션을 사용한다. 요청 URL은 한 번만 읽어 검사와 전송 사이 불일치를 막는다.
KRXSession.get_headers의 수동 Cookie 생성도 제거하고 실제 로그인 세션의 CookieJar domain/path/secure 정책에 맡긴다. webio는 KRXSession.get/post를 통해 인증 요청을 보낸다. 직접 외부 get/post도 새로운 요청 세션으로 분리하며 Cookie/Authorization/Proxy-Authorization 커스텀 헤더는 공개 요청에서 제외한다. 수동으로 requests.Session 원객체를 직접 조작하는 외부 코드는 보장 범위가 아니다.

## 선택한 배포 방식
런타임 monkeypatch는 진입점마다 적용누락·순서문제가 있어 제외한다. 대규모 vendor fork 대신 공식1.2.9 wheel에 작은 추적가능 patch와 localversion `1.2.9+cookie.1`을 부여한다.
vendor/pykrx에는 패치, 재빌드스크립트, MIT출처/갱신README와 수정wheel을 보관한다. requirements의 --find-links와 exactpin으로 표준설치에 연결한다. 재빌드는 공식sourcewheel SHA e768a64830d21dee46b1a5dd3e9e33112c390d65dbdf931a6bb89ac5a7bea8ea를 먼저 검증하고 patch·METADATA·RECORD를 갱신한다. wheel을 두번 만들어 결과SHA 일치를 검증한다. 앱설치시에 재빌드/네트워크패치를 실행하지 않는다.

## 안전·호환성
- KRX 인증은 https://data.krx.co.kr(:443)에만 전달한다. HTTP/다른port/userinfo/유사도메인에는 global session을 조회하지 않는다.
- 공식 upstream의 KrxFutureIo GET/KrxWebIo POST 실행URL은 이미 HTTPS임을 확인했다. URL변경은 필요없다. 공개조회 API·응답형태·메서드/params/data 계약은 보존한다.
- 인증 redirect는 fail-closed이며, 실제 공급자가 redirect를 요구하는 경우 별도 검토가 필요하다. 인증 없는 public redirect에는 KRX 세션을 애초에 연결하지 않는다.
- 원본 .env/data/logs/3500/5501/live/venv/node_modules 미접속·미변경. 공식wheel 다운로드만허용, 검증환경에서 외부망차단. 가짜cookie·가짜HTTP응답만사용.
- 기존 INFRA070 보안요구사항과 UI lock은 유지한다. 모든감사0,전체tests,실제NumPy2API계약,ego브라우저QA가완료조건이다.
