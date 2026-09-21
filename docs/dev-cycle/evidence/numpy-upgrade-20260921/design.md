# NumPy 2 / pykrx 동반 승격 설계

INFRA-018, brainstorming bounded이나 메이저의존성변경으로T3 계획·독립검토 적용.
사용자는 남은연관TODO 연속진행 및 승인판단을위임했다. 이설계/계획은리더가검토·결정한다.
현재실행Python3.11.16, 요구는NumPy2상한과제거된np.float_참조를함께해소하는것이다.

## 결정

numpy2.0.0은최소하한이나초기릴리스이고, Python3.11지원2.x유지버전2.4.6을선택한다. pykrx는NumPy2를허용하는최소1.2.7로한정한다.
다른직접의존성은현재핀유지. np.float_은이미함께있는np.float64의별칭이므로그참조만삭제한다.
새추상화/호환shim을만들지않는다. 원본venv를변경하거나원본서비스를재기동하지않는다.
격리venv에설치하고호환성/전체pytest로검증하며, 실제KRX로그인/시세외부조회는실행하지않는다.

## 근거

- https://pypi.org/pypi/pykrx/1.2.3/json : numpy<2
- https://pypi.org/pypi/pykrx/1.2.7/json : numpy>=2
- https://pypi.org/pypi/numpy/2.4.6/json : Python3.11 호환선택
- https://numpy.org/doc/stable/release/2.0.0-notes.html : np.float_ 제거, np.float64 사용

독립dependency-expert조사에더해실제설치시version/Requires-Python/Requires-Dist와pip check로확인한다.
소수점/int promotion/ABI/pykrx응답형태가위험이다. 새환경전체pytest와진짜pykrx의전송경계대역을통과시키고제공처접속검증과구분한다.

## 완료

requirements.txt의numpy/pykrx두핀·주석과공용encoder1참조수정,회귀검사.
NumPy2격리환경전체pytest·Vitest·type/lint/build 및 UltraQA(실제backend JSON→NextUI)와독립리뷰를통과해야완료.
원본.env/data/logs/3500/5501/live, 실제LLM/수집/거래/설정저장/원본삭제금지. 의존성다운로드만공식PyPI로허용.
실제PaaS배포나원본venv업데이트는수행하지않는다.
