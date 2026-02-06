# 🐛 문제 해결 가이드 (Troubleshooting)

자주 발생하는 문제와 해결 방법입니다.

## 데이터 파일 오류

### `FileNotFoundError: data/daily_prices.csv`
- **원인**: 초기 데이터가 생성되지 않았습니다.
- **해결**:
  ```bash
  python scripts/init_data.py
  ```

### `KOSPI 지수가 2650으로 고정되어 나옵니다`
- **원인**: 실시간 데이터 수집에 실패하여 기본 샘플 값이 출력되는 경우입니다.
- **해결**:
  1. 인터넷 연결 확인.
  2. `requirements.txt`의 `yfinance`, `pykrx` 패키지가 최신 버전인지 확인.
  3. `python scripts/init_data.py`를 다시 실행해서 실시간 데이터를 받아오는지 로그 확인.

## 서버 오류

### `Port 5501 is already in use`
- **원인**: 이미 백엔드 서버가 실행 중입니다.
- **해결**:
  ```bash
  # 포트를 사용하는 프로세스 종료 (macOS/Linux)
  lsof -ti:5501 | xargs kill -9
  ```

### `ModuleNotFoundError: No module named ...`
- **원인**: 가상환경이 활성화되지 않았거나 패키지가 설치되지 않았습니다.
- **해결**:
  ```bash
  source venv/bin/activate
  pip install -r requirements.txt
  ```

## API 오류

### API가 404를 반환함
- **원인**: URL 경로가 잘못되었거나 백엔드 라우트 설정 문제.
- **해결**:
  - `http://localhost:5501/api/kr/...` 경로가 맞는지 확인.
  - 브라우저 개발자 도구(F12) > Network 탭에서 요청 URL 확인.
