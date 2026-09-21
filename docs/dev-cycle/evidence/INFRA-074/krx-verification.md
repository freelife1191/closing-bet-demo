# INFRA-074 KRX 로그인 방어 검증

## RED

기존 `pykrx==1.2.9+cookie.1`에서 합성 HTML 로그인 응답을 반환하면
`response.json()`의 `JSONDecodeError`가 `KRXSession.refresh()` 밖으로 전파됐다.
리다이렉트 회귀를 추가한 뒤에는 로그인 warmup GET과 POST에
`allow_redirects=False`가 없어서 적대적 307 검사가 실패했다.

## GREEN

`pykrx==1.2.9+cookie.2` 휠은 다음 합성 transport 시나리오를 외부 연결 없이 통과했다.

- 첫 POST: HTML, HTTP 오류, 잘못된 JSON 스키마, `_error_code` 누락, 네트워크 오류, 307
- CD011 재시도 POST: HTML, HTTP 오류, 잘못된 스키마, 네트워크 오류
- warmup GET 307과 네트워크 오류
- CD001 성공과 CD011 뒤 CD001 성공. 두 번째 요청만 `skipDup=Y`

실패마다 이전 인증 상태와 이전·새 CookieJar가 비워지고, `last_error`는
`network_error`, `http_error`, `invalid_json`, `invalid_schema`처럼 비밀 없는 범주만
가진다. 로그인 ID, 암호, 응답 본문, 서버 오류 메시지는 probe 출력에 포함되지 않는다.
로그인 GET·POST 네 요청 모두 `allow_redirects=False`이며 3xx는 HTTP 오류로 끝나므로
307이 암호 POST를 다른 origin으로 재전송하지 않는다.

```text
tests/test_pykrx_login_guard.py                         1 passed
tests/test_pykrx_transport_security.py                  1 passed
tests/engine/test_pykrx_numpy2_contract.py              1 passed
```

## 재현성

공식 upstream SHA256:

```text
e768a64830d21dee46b1a5dd3e9e33112c390d65dbdf931a6bb89ac5a7bea8ea
```

동일한 공식 휠로 두 번 재빌드한 `cookie.2` SHA256:

```text
3648009de4202f6087be7e8eef174a86c3d77eed6d3db60eb9ecf18ac6b8a099
```

원본 `.env`, 계정, 실제 KRX 서버, 실행 중 서비스에는 접근하지 않았다.
