# 🛠️ 상세 설치 가이드 (Installation Guide)

이 문서는 KR Market Package의 상세 설치 방법 및 환경 설정을 다룹니다.

## 1. 사전 요구사항 (Prerequisites)

- **OS**: macOS, Linux, or Windows (WSL 권장)
- **Python**: 3.11 이상 (3.11.7 권장)
- **Node.js**: 18.0 이상 (프론트엔드용)

## 2. Python 가상환경 설정

### macOS / Linux
```bash
# Python 3.11 확인
python3.11 --version

# 가상환경 생성
python3.11 -m venv venv

# 가상환경 활성화
source venv/bin/activate
```

### Windows
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\activate
```

## 3. 의존성 설치 (Dependencies)

`requirements.txt`를 사용하여 모든 Python 패키지를 설치합니다.

```bash
pip install -r requirements.txt
```

> **Tip**: 설치 중 에러 발생 시 `pip install --upgrade pip`를 먼저 실행하세요.

## 4. 환경 변수 설정 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력하세요.

```ini
# Server Config
FLASK_DEBUG=true
FLASK_PORT=5501

# AI API Keys (선택 사항 - 뉴스 분석용)
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```

파일을 만든 뒤 모드를 좁힙니다. API 키와 SMTP 비밀번호가 들어가는 파일이라 기본 모드로
두면 같은 호스트의 모든 로컬 계정이 읽습니다.

```bash
chmod 600 .env
```

## 5. 데이터 초기화 (필수)

서버 실행 전, 초기 데이터를 생성해야 합니다.

```bash
python scripts/init_data.py
```
위 명령어를 실행하면 `data/` 디렉토리에 필요한 CSV 및 JSON 파일들이 생성됩니다.

## 6. 서버 실행

### 백엔드 (Flask)
```bash
python flask_app.py
```
- 주소: `http://localhost:5501`

### 프론트엔드 (Next.js)
```bash
cd frontend
npm install
npm run dev
```
- 주소: `http://localhost:3500`
