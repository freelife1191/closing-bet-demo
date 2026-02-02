#!/bin/bash
# ==============================================================================
# KR Market Package - 올인원 설정 스크립트 (One-Click Setup)
# ==============================================================================
# 
# 이 스크립트는 다음을 자동으로 수행합니다:
# 1. Python 3.11 설치 확인
# 2. 가상환경(venv) 생성 및 활성화
# 3. 의존성 설치 (requirements.txt)
# 4. .env 파일 생성 (API 키 입력 필요)
# 5. 데이터 초기화 (init_data.py)
# 6. 서버 실행 테스트
#
# 사용법:
#   chmod +x scripts/init_all.sh
#   ./scripts/init_all.sh
# ==============================================================================

set -e  # 에러 발생 시 즉시 중단

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 현재 작업 디렉토리 확인
if [ ! -f "flask_app.py" ]; then
    log_error "flask_app.py 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에서 실행해주세요."
    exit 1
fi

PROJECT_DIR=$(pwd)
log_info "프로젝트 디렉토리: $PROJECT_DIR"

# 2. Python 3.11 버전 확인
log_info "Python 3.11 버전 확인 중..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')

if [[ $PYTHON_VERSION == 3.11.* ]]; then
    log_success "Python 3.11 확인됨: $PYTHON_VERSION"
else
    log_warning "Python 3.11 확인 필요함. 현재 버전: $PYTHON_VERSION"
    log_warning "Homebrew 또는 pyenv를 사용하여 Python 3.11을 설치하세요."
    read -p "계속 진행하시겠습니까? (y/n) " -n 1 -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "설치를 중단합니다."
        exit 1
    fi
fi

# 3. 가상환경(venv) 확인 및 생성
if [ -d "venv" ]; then
    log_warning "venv 디렉토리가 이미 존재합니다."
    read -p "기존 venv를 삭제하고 다시 생성하시겠습니까? (y/n) " -n 1 -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "기존 venv 삭제 중..."
        rm -rf venv
    else
        log_info "기존 venv를 사용합니다."
    fi
fi

if [ ! -d "venv" ]; then
    log_info "가상환경(venv) 생성 중..."
    python3.11 -m venv venv
    log_success "가상환경(venv) 생성 완료"
fi

# 4. 가상환경 활성화
log_info "가상환경 활성화 중..."
source venv/bin/activate
log_success "가상환경 활성화 완료: $(which python)"

# 5. 의존성 설치
log_info "의존성 설치 중 (requirements.txt)..."
pip install -r requirements.txt
log_success "의존성 설치 완료"

# 6. .env 파일 확인
if [ ! -f ".env" ]; then
    log_warning ".env 파일이 존재하지 않습니다."
    if [ -f ".env.example" ]; then
        log_info ".env.example 파일을 복사하여 .env 생성 중..."
        cp .env.example .env
        log_success ".env 파일 생성 완료 (템플릿 사용)"
        log_warning "!!! 중요: .env 파일에 API 키를 입력해야 합니다 !!!"
        log_warning "에디터를 엽니다: nano .env (또는 code .env)"
        read -p "에디터를 열어 .env 파일을 수정한 후 엔터를 누르세요..."
        nano .env
    else
        log_error ".env.example 파일도 존재하지 않습니다. 수동으로 .env 파일을 생성해주세요."
        exit 1
    fi
else
    log_success ".env 파일 확인 완료"
fi

# 7. 데이터 디렉토리 생성
log_info "데이터 디렉토리 생성 중 (data/, logs/)..."
mkdir -p data logs
log_success "데이터 디렉토리 생성 완료"

# 8. 데이터 초기화 스크립트 실행
if [ -f "scripts/init_data.py" ]; then
    log_info "데이터 초기화 스크립트 실행 중 (scripts/init_data.py)..."
    python3 scripts/init_data.py
    log_success "데이터 초기화 완료"
else
    log_error "scripts/init_data.py 파일을 찾을 수 없습니다."
    exit 1
fi

# 9. Flask 앱 임포트 테스트
log_info "Flask 앱 임포트 테스트 중..."
python3 -c "
try:
    from app import create_app
    app = create_app()
    print('OK')
except ImportError as e:
    print(f'ERROR: {e}')
    exit(1)
"
if [ $? -eq 0 ]; then
    log_success "Flask 앱 임포트 테스트 성공"
else
    log_error "Flask 앱 임포트 테스트 실패. DEBUG_GUIDE.md를 참조하세요."
    exit 1
fi

# 10. 요약 및 다음 단계 안내
echo ""
echo "================================================================================"
log_success "🎉 모든 설정 및 데이터 초기화가 완료되었습니다!"
echo "================================================================================"
echo ""
log_info "다음 단계:"
echo "1. 백엔드 서버 실행:"
echo "   python3 flask_app.py"
echo ""
echo "2. 브라우저 접속:"
echo "   백엔드 API: http://localhost:5001"
echo "   헬스체크: http://localhost:5001/health"
echo ""
log_info "참고:"
echo "   - 상세 설치 가이드: EXECUTION_GUIDE.md"
echo "   - 문제 해결: DEBUG_GUIDE.md"
echo "   - 전체 문서: README.md"
echo ""
