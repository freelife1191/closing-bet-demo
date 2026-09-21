# INFRA-018 대안 검토

2026-09-21, 독립 dependency-expert의 공개 공식 소스 조사. 실제 쿠키·KRX/Naver API는 사용하지 않았다.

- pykrx 1.2.9 Get/Post는 URL 출처에 관계없이 전역 KRXSession의 명시 Cookie를 전달한다.
- v1.2.3 Get은 requests.get을 직접 사용했다. Naver는 여전히 HTTP 공개 GET이다.
- webio.set_session은 현재 get_session의 반환 경로를 바꾸지 못한다. auth 세션 초기화는 재인증과 KRX 인증 기능에 영향을 주므로 안전한 해결이 아니다.
- 해결하려면 패키지 통신 계층이 인증 대상 출처를 제한하고 나머지는 독립 공개 요청으로 보내야 한다. 정확한 호스트·TLS·리다이렉트·cookie jar 검증도 필요하다.
- 공식 지원 hook이 없어 자체 수정 wheel/vendor fork/전역 monkeypatch 또는 업스트림 릴리스가 필요하다. 교육용 프로젝트에서 NumPy 승격만을 위해 별도 배포 패키지를 유지하지 않기로 판단했다. 변경 권한 부족이 아닌 유지 비용·안전 경계에 따른 기술 결정이다.
- np.float_ 제거는 독립적으로 유효하다. np.float64가 이미 처리 대상이어서 기존 NumPy1 동작을 바꾸지 않고 제거된 API 의존만 없앤다.

## 공식 근거
- https://github.com/sharebook-kr/pykrx/blob/v1.2.3/pykrx/website/comm/webio.py
- https://github.com/sharebook-kr/pykrx/blob/v1.2.9/pykrx/website/comm/webio.py
- https://github.com/sharebook-kr/pykrx/blob/v1.2.9/pykrx/website/comm/auth.py
- https://github.com/sharebook-kr/pykrx/blob/v1.2.9/pykrx/website/naver/core.py
- https://github.com/numpy/numpy/blob/v2.0.0/doc/source/numpy_2_0_migration_guide.rst
