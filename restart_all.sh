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

# (System dependency checks removed in favor of venv)
echo "✅ Environment setup proceeding with venv..."
echo ""

# ==== Frontend deps ====
cd frontend || { echo "❌ frontend dir not found!"; exit 1; }
echo "📦 Installing/Updating frontend dependencies..."
npm install
cd ..

############################################
# 3) Backend 시작 (venv 가상환경 사용)
############################################
echo "🚀 Starting Backend (Flask) on port $FLASK_PORT..."
if [ ! -d "venv" ]; then
  echo "   📦 venv not found. Creating new virtual environment..."
  python3.11 -m venv venv || python3 -m venv venv
fi

echo "   📦 Using venv virtual environment..."
source venv/bin/activate

# venv 내 필수 패키지 확인 및 설치
echo "   📦 Installing/Updating requirements from requirements.txt..."
pip install -r requirements.txt --quiet

nohup python flask_app.py > logs/backend.log 2>&1 &
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