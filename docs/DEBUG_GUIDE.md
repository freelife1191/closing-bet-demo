## ✅ 해결 방법 (절대적 순서)

### 1단계: Python 버전 확인 (Python 3.11 필수)

```bash
# 터미널에서 Python 버전 확인
python --version

# 다음과 같아야 함:
# Python 3.11.x (예: 3.11.7)

# 만약 3.10 이하라면 업그레이드 필수!
```

### 2단계: 가상환경 생성 (절대 필수)

```bash
# 프로젝트 디렉토리로 이동
cd /Users/freelife/vibe/lecture/hodu/closing-bet-v2

# 기존 가상환경 삭제 (초기화)
rm -rf venv

# Python 3.11 가상환경 생성
python3.11 -m venv venv
```

### 3단계: 가상환경 활성화 (절대 필수)

```bash
# macOS/Linux
source venv/bin/activate

# Windows
# venv\Scripts\activate
```

**확인 방법**: 터미널 프롬프트 끝에 `(venv)`가 뜨나요? 예: `(closing-bet-v2) venv`
만약 뜨지 않는다면 활성화가 안 된 것입니다.

### 4단계: 의존성 설치 (가장 중요!)

#### 🚀 방법 A: `requirements.txt` 사용 (강력 추천)

`requirements.txt` 파일에는 프로젝트 실행에 필요한 모든 패키지와 최소 버전이 정의되어 있습니다. 이 파일을 사용하여 설치하는 것이 가장 안전하고 빠릅니다.

```bash
# requirements.txt에 정의된 모든 패키지 설치 (한 줄 명령어)
pip install -r requirements.txt
```

**장점**:
1. **버전 호환성 보장**: `requirements.txt`에 `flask>=3.0.0`과 같이 버전 제약이 있어 충돌을 방지합니다.
2. **누락 방지**: 수동으로 `pip install pandas numpy pykrx`를 입력할 때 하나를 잊어버리기 쉽습니다. `requirements.txt`는 모든 의존성을 포함합니다.
3. **비동기 지원**: `aiohttp`, `aiofiles` 등 종가베팅 V2 엔진에 필수적인 비동기 패키지도 자동 설치됩니다.

**설치 완료 확인**:
```bash
# Python 실행 (가상환경 활성화 상태)
python

# 전체 임포트 테스트 (requirements.txt에 있는 패키지만 체크)
>>> import flask
>>> import pykrx
>>> import pandas
>>> import numpy
>>> import yfinance
>>> import google.generativeai
>>> import openai
>>> import aiohttp
>>> import aiofiles
>>> import requests
>>> from dotenv import load_dotenv
>>> print("✅ All imports OK!")
```

성공하면 `✅ All imports OK!`가 출력됩니다.

#### 📝 방법 B: 수동 설치 (디버깅용, 선택사항)

`pip install -r requirements.txt`가 실패하거나, 특정 패키지만 설치하고 싶을 때 사용하세요. **주의**: 방법 A(`requirements.txt` 사용)이 훨씬 안전합니다.

**1단계: 핵심 프레임워크**
```bash
pip install flask flask-cors python-dotenv
```

**2단계: 데이터 소스 (가장 중요)**
```bash
pip install pandas numpy pykrx yfinance
```

**3단계: AI 분석 (API 키 필요)**
```bash
pip install google-generativeai openai
```

**4단계: 비동기 엔진 (엔진 V2 필수)**
```bash
pip install aiohttp aiofiles
```

**5단계: 유틸리티**
```bash
pip install requests beautifulsoup4 lxml-html-clean tqdm
```

### 5단계: .env 파일 설정 (필수)

```bash
# .env.example 파일 복사
cp .env.example .env

# .env 파일 편집
nano .env
```

**.env 파일 내용**:
```bash
GOOGLE_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
FLASK_DEBUG=true
FLASK_PORT=5501
```

---

## 🚨 증상 2: Blueprint Import Error

### 문제
`ImportError: cannot import name 'some_blueprint' from 'app.routes'`

### 해결 방법
1. `app/__init__.py` 파일에서 Blueprint 등록 확인
2. `app/routes/` 디렉토리에 해당 파일 존재 여부 확인

---

## 🛠 가상환경 트러블슈팅 (Venv Troubleshooting)

### 문제 1: `externally-managed-environment` 오류
```
error: externally-managed-environment
× This environment is externally managed
```

**원인**: macOS Sequoia 이상 또는 Homebrew Python에서 시스템 Python을 보호

**해결 방법**:
```bash
# 반드시 가상환경 내에서 pip 사용
source venv/bin/activate
pip install -r requirements.txt  # 가상환경 내이므로 OK
```

### 문제 2: `pip: command not found`
**해결 방법**:
```bash
# 가상환경 활성화 확인
source venv/bin/activate

# pip3 사용
pip3 install -r requirements.txt

# 또는 python -m pip 사용
python -m pip install -r requirements.txt
```

### 문제 3: `No module named 'venv'`
**원인**: Python이 venv 모듈 없이 설치됨

**해결 방법 (macOS)**:
```bash
brew install python@3.11
python3.11 -m venv venv
```

### 문제 4: 가상환경 활성화 후에도 시스템 Python 사용됨
**확인 방법**:
```bash
which python
# 결과가 /usr/bin/python 또는 /opt/homebrew/bin/python이면 가상환경 X
# 결과가 .../venv/bin/python이면 가상환경 활성화됨
```

**해결 방법**:
```bash
# 새 터미널 열기 후 다시 활성화
source /Users/freelife/vibe/lecture/hodu/closing-bet-v2/venv/bin/activate
```

### 문제 5: 패키지 설치 후에도 import 실패
**원인**: 가상환경 비활성화 상태 또는 다른 Python 버전 사용

**해결 방법**:
```bash
# 1. 가상환경 활성화 확인
source venv/bin/activate

# 2. 설치된 패키지 확인
pip list | grep flask  # flask가 보이는지 확인

# 3. Python 버전 확인
python --version  # 3.11.x 여야 함
```

### 🔄 초기화 전체 명령어 (All-in-One Reset)
```bash
cd /Users/freelife/vibe/lecture/hodu/closing-bet-v2
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import flask; import pykrx; print('✅ OK')"
```
