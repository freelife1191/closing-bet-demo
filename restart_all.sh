#!/bin/bash

############################################
# restart_all.sh - Mac/Linux 호환 버전
# Flask(Backend, python3.11) + Next.js(Frontend) 전체 재시작
# pipx, Python deps, node_modules 자동 설치
############################################

# ==== 기본 경로 설정 ====
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# ==== .env 로드 ====
if [ -f .env ]; then
  echo "📄 Loading .env configuration..."
  set -a
  source .env
  set +a
else
  echo "⚠️  .env file not found! (using defaults)"
fi

# ==== 포트 기본값 ====
FRONTEND_PORT=${FRONTEND_PORT:-3500}
FLASK_PORT=${FLASK_PORT:-5501}

echo "🛑 Stopping existing services on ports $FRONTEND_PORT / $FLASK_PORT ..."

# ==== 포트 기준 프로세스 종료 함수 (Mac/Linux 공통) ====
kill_port() {
  local port=$1

  # lsof 우선 (Mac/Linux 공통)
  local pids
  pids=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "   🔪 Killing lsof processes on port $port (PIDs: $pids)..."
    kill -9 $pids 2>/dev/null || true
  fi

  # ss 백업 (Linux)
  if command -v ss >/dev/null 2>&1; then
    pids=$(ss -tulpn 2>/dev/null | grep :$port | awk '{print $7}' | cut -d, -f2 | cut -d= -f2 | sort -u)
    if [ -n "$pids" ]; then
      echo "   🔪 Killing ss processes on port $port (PIDs: $pids)..."
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

kill_port "$FRONTEND_PORT"
kill_port "$FLASK_PORT"

# 패턴으로 백엔드/프론트엔드 프로세스 추가 정리
echo "🧹 Killing remaining backend/frontend processes..."
pkill -f "python3.*flask_app.py" 2>/dev/null || true
pkill -f "flask_app.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true

echo "✅ Cleanup complete."
echo ""

# ==== 로그 디렉토리 ====
mkdir -p logs

# ==== 시스템 감지 ====
IS_MAC=$(uname | grep -i darwin >/dev/null && echo "true" || echo "")
PKG_MGR=""
if [ "$IS_MAC" = "true" ]; then
  PKG_MGR="brew"
else
  PKG_MGR="apt"
fi

############################################
# 1) pipx 및 Flask (pipx) 자동 설치
############################################
echo "🔍 Checking pipx & Flask (pipx)..."

# pipx 설치
if ! command -v pipx >/dev/null 2>&1; then
  echo "   📦 pipx not found. Installing via $PKG_MGR..."
  if [ "$IS_MAC" = "true" ]; then
    if ! command -v brew >/dev/null 2>&1; then
      echo "     🍺 Installing Homebrew first..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
      eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    brew install pipx
  else
    sudo apt update
    sudo apt install -y pipx
  fi
  pipx ensurepath
fi

# PATH 보정
if ! command -v pipx >/dev/null 2>&1 && [ -d "$HOME/.local/bin" ]; then
  export PATH="$HOME/.local/bin:$PATH"
fi

# Flask pipx 설치 확인
PIPX_LIST_OUTPUT="$(pipx list 2>/dev/null || true)"
if echo "$PIPX_LIST_OUTPUT" | grep -qi "package flask"; then
  echo "   ✅ Flask already installed in pipx."
else
  echo "   📦 Installing Flask via pipx..."
  pipx install flask
fi

############################################
# 2) python3.11 전역 의존성 자동 설치
############################################
echo "🔍 Checking Python 3.11 dependencies..."

PY_DEPS=("flask" "flask_cors" "python_dotenv" "pandas" "requests")
for dep in "${PY_DEPS[@]}"; do
  case "$dep" in
    flask_cors) IMPORT_NAME="flask_cors"; PIP_NAME="flask-cors" ;;
    python_dotenv) IMPORT_NAME="dotenv"; PIP_NAME="python-dotenv" ;;
    *) IMPORT_NAME="$dep"; PIP_NAME="$dep" ;;
  esac

  if ! python3.11 -c "import $IMPORT_NAME" 2>/dev/null; then
    echo "   📦 Installing missing dependency: $PIP_NAME ..."
    if [ "$IS_MAC" = "true" ]; then
      python3.11 -m pip install --user "$PIP_NAME"
    else
      python3.11 -m pip install "$PIP_NAME" --break-system-packages
    fi
  else
    echo "   ✅ $PIP_NAME already available."
  fi
done

echo "✅ All Python dependencies ready!"
echo ""

# ==== Frontend deps ====
cd frontend || { echo "❌ frontend dir not found!"; exit 1; }
if [ ! -d "node_modules" ]; then
  echo "📦 Installing node_modules..."
  npm install
fi
cd ..

############################################
# 3) Backend 시작
############################################
echo "🚀 Starting Backend (Flask) on port $FLASK_PORT..."
nohup python3.11 flask_app.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# ==== 4) Frontend 시작 ====
echo "🚀 Starting Frontend (Next.js) on port $FRONTEND_PORT..."
cd frontend
PORT=$FRONTEND_PORT nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"
cd ..

echo ""
echo "🎉 All services started!"
echo "   Backend:  http://localhost:$FLASK_PORT"
echo "   Frontend: http://localhost:$FRONTEND_PORT"
echo "   Logs: tail -f logs/backend.log logs/frontend.log"