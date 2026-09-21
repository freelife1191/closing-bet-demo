# INFRA-018 인코더 선행 수정 계획

사용자: 남은 라운드 연속 진행과 승인 판단 위임, 이어서 «진행해».
brainstorming bounded; 기존 T3 의존성 라운드의 일부만 재개한다. 전체 완료 기준과 N4/N5 필수 조건은 바꾸지 않는다.

## 설계와 결정
공식 pykrx 1.2.9도 Cookie 경계 결함이 남고 지원 hook으로 해결되지 않는다.
커스텀 wheel, vendor fork, 전역 monkeypatch 대신 기존 numpy1.26.4/pykrx1.2.3 핀을 유지한다.
독립적으로 가능한 np.float_ 별칭 참조 제거만 적용한다. np.float64가 이미 포함돼 기존 동작은 동일하다.
원본 venv/.env/data/logs/3500/5501/live는 실행·변경하지 않는다. 부모 소유 scratch에서 네트워크 차단 검증한다.

## 구현 계획
- [x] 신규 tests/test_numpy_encoder_compat.py: 실제 JSON roundtrip으로 float16/32/64, int64, bool, ndarray, date/datetime을 검증한다.
- [x] 같은 검사를 monkeypatch.delattr(np, "float_", raising=False) 조건에서도 실행한다. 별칭 부재가 날짜·배열·bool·float32 직렬화를 깨는지 확인하는 회귀다. 객체 TypeError도 유지한다.
- [x] 원본 encoder로 별칭 부재 케이스 실패를 확인한 후 numpy_json_encoder.py의 np.float_ 한 참조만 제거한다.
- [x] requirements.txt 두 핀은 유지하고 오래된 주석만 인코더 선행 수정과 남은 pykrx 상한/쿠키 차단 상황으로 정정한다.
- [x] 격리 환경 표적 테스트, 전체 pytest/Vitest, type/lint 실행. 소유 scratch만 정리한다.
- [x] 순차 ponytail/code/deep 리뷰. TODO np.float_ 체크만 갱신하고 QA에 부분검증과 N4실패/N5차단 유지 기록.
- [x] 부분 구현 커밋만 남긴다. 전체 완료 아카이브·TODO 제거·NumPy2 전환 성공 주장 금지.

## 검증 제한
실제 NumPy2 환경의 전체 테스트와 브라우저 N5를 이번 baseline 테스트로 대체하지 않는다.
별칭 삭제 테스트는 제거된 API 조건의 회귀이며, 실제 NumPy2 설치 검증이라는 뜻이 아니다.
비정상객체 TypeError/숫자 및 날짜 실제값 보존이 관찰 계약이다. 수집·쿠키·인증·시세 API 미호출.
