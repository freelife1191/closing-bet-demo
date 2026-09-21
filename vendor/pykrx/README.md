# pykrx 1.2.9+cookie.1

공식 pykrx 1.2.9에 인증 쿠키 전달 경계만 수정한 프로젝트 배포본이다. 런타임 monkeypatch를 설치하지 않는다.

- NumPy 2 지원 upstream1.2.9를 사용한다.
- KRXSession과 webio GET/POST는 정확한 `https://data.krx.co.kr` 및 명시적443 포트에만 인증 세션을 사용한다.
- Cookie 헤더를 문자열로 만들지 않고 로그인 세션의 CookieJar가 domain/path/secure를 판정한다.
- 인증 요청은 자동 redirect를 따르지 않는다. 3xx 응답은 호출자에게 반환한다.
- 공개 요청은 새 세션에서 Cookie/Authorization/Proxy-Authorization을 제거한다. URL 내 자격증명·auth/cookies 인자는 거부하며, netrc/환경 프록시 등 ambient 인증 설정도 상속하지 않는다. 프록시가 필요한 환경은 이 제한을 검토해야 한다.
- 원래의 KRXSession.session 원객체에 직접 접근하는 코드는 이 경계를 우회할 수 있다. 프로젝트는 공개 pykrx API를 사용한다.

## 출처와 재빌드

공식 파일: https://files.pythonhosted.org/packages/cd/87/c54da498f80f0839ec7b4145119b2d395600542d1301f626716538356e93/pykrx-1.2.9-py3-none-any.whl

원본 SHA256: `e768a64830d21dee46b1a5dd3e9e33112c390d65dbdf931a6bb89ac5a7bea8ea`
수정본 SHA256: `67d2fc7c7d11d586472b181975a8daeb81eaf6bff64551aa87f5f2bcb800f8d6`

`python3 vendor/pykrx/rebuild.py`는 공식 파일을 다운로드하고 먼저SHA를검증한다. 이미받은파일은 `--upstream-wheel <path>`로 지정할 수 있다. Python3.10+와patch 명령이 필요하다. sourcepatch 외에는 localversion/METADATA/WHEEL/RECORD만 갱신한다. fixed ZIP metadata와무압축으로동일바이트를생성한다. 표준앱설치는완성된wheel만사용하므로patch도구·재빌드·추가다운로드가필요없다.

라이선스는원본wheel METADATA의MIT선언과저자/출처필드를그대로보존한다. 원본wheel에는별도LICENSE파일이포함되지않았다. `transport.patch`가변경내용의정본이며별도패키지이름으로상류배포를가장하지않는다.

## 설치와 갱신

루트 `requirements.txt`의 `--find-links vendor/pykrx`와 `pykrx==1.2.9+cookie.1`을 통해 설치된다. requirements-security.txt의보안하한도유지한다.
업스트림이같은문제를수정하면공식판의네트워크없는인증/고수준시세회귀·전체검수후localpin/find-links/wheel/patch를함께제거한다. 새upstream에무조건패치를재적용하지않는다.

검증: tests/test_pykrx_transport_security.py (실제requests·공개Naver조회,합성쿠키/HTTP), docs/dev-cycle/qa/INFRA-018.md. 실제KRX로그인·원격시세·계정쿠키는검수에사용하지않았다.
