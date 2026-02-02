### 1.3 Python 의존성 설치

**가장 쉬운 방법 (추천)**: `requirements.txt` 파일에 정의된 모든 패키지를 한 번에 설치합니다.

```bash
# requirements.txt에 있는 모든 패키지 설치
pip install -r requirements.txt
```

**참고**: `requirements.txt` 파일은 다음 패키지들을 포함하고 있습니다:
- Flask, Flask-CORS, python-dotenv
- pykrx, yfinance, pandas, numpy
- google-generativeai, openai
- aiohttp, aiofiles
- requests, beautifulsoup4, lxml, tqdm

---

## ⚠️ 왜 수동 설치 대신 requirements.txt를 써야 할까요?

### 1. 버전 호환성 보장
`requirements.txt`는 각 패키지의 정확한 최소 버전을 지정합니다 (예: `pandas>=2.1.0`). 수동으로 `pip install pandas`만 하면 시스템에 설치된 버전에 따라 호환성 문제가 발생할 수 있습니다.

### 2. 업데이트 용이성
프로젝트가 업데이트될 때 `requirements.txt`만 수정하면 모든 사용자가 동일한 환경에서 실행될 수 있습니다.

### 3. 미누락 의존성 방지
이 프로젝트는 비동기 엔진(Engine V2)을 사용하므로 `aiohttp`, `aiofiles` 등의 비동기 라이브러리가 필수입니다. 이것들은 수동으로 설치하기 쉽게 빠뜨릴 수 있습니다.

---

## (선택사항) 수동 설치 방법

**주의**: 아래 방법은 `requirements.txt`의 내용을 직접 입력하는 것과 동일합니다. 대부분의 경우 `pip install -r requirements.txt` 한 줄로 해결됩니다.

### 1단계: 핵심 프레임워크
```bash
pip install flask flask-cors python-dotenv
```

### 2단계: 데이터 소스
```bash
pip install pandas numpy pykrx yfinance
```

### 3단계: AI 분석
```bash
pip install google-generativeai openai
```

### 4단계: 비동기 지원
```bash
pip install aiohttp aiofiles
```

### 5단계: 유틸리티
```bash
pip install requests beautifulsoup4 lxml-html-clean tqdm
```

### 6단계: 시각화 (선택사항)
```bash
pip install plotly
```

**요약**: 문제가 발생하면 `pip install -r requirements.txt`를 먼저 시도해 보세요. 그 다음 단계별로 나누어 설치하는 것을 고려하세요.
