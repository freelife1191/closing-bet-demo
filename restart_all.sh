#!/bin/bash

############################################
# restart_all.sh - Mac/Linux 호환 + Flask 에러 완전 해결 버전
############################################

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# .env 로드
if [ -f .env ]; then
  echo "📄 Loading .env..."
  set -a; source .env; set +a
fi

FRONTEND_PORT=${FRONTEND_PORT:-3500}
FLASK_PORT=${FLASK_PORT:-5501}

echo "🛑 Stopping services on $FRONTEND_PORT/$FLASK_PORT..."

kill_port() {
  local port=$1
  pids=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "   🔪 Killing port $port (PIDs: $pids)..."
    kill -9 $pids 2>/dev/null || true
  fi
  if command -v ss >/dev/null 2>&1; then
    pids=$(ss -tulpn 2>/dev/null | grep :$port | awk '{print $7}' | cut -d, -f2 | cut -d= -f2 | sort -u)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}

kill_port "$FRONTEND_PORT"; kill_port "$FLASK_PORT"
pkill -f "flask_app.py" -f "next dev" -f "npm.*dev" 2>/dev/null || true

echo "✅ Cleanup complete."
mkdir -p logs

# 시스템 deps 강제 설치 (Flask 에러 완전 해결!)
echo "🔧 Force-installing ALL Python 3.11 deps (system-wide)..."
SYS_DEPS=("flask" "flask-cors" "python-dotenv" "pandas" "requests" "google-generativeai" "schedule" "yfinance" "pykrx" "apscheduler")
for dep in "${SYS_DEPS[@]}"; do
  echo "   📦 $dep..."
  python3.11 -m pip install --break-system-packages --force-reinstall --quiet "$dep"
done

# venv 자동 생성/관리
if [ ! -d "venv" ]; then
  echo "📦 Creating venv..."
  python3.11 -m venv venv
  source venv/bin/activate && pip install --quiet "${SYS_DEPS[@]}" "google-generativeai" "yfinance" "pykrx" "apscheduler"
fi

echo "✅ Python ready!"

# Frontend
cd frontend 2>/dev/null || { echo "❌ frontend/ missing!"; exit 1; }
[ ! -d "node_modules" ] && echo "📦 npm install..." && npm install
cd ..

# Backend 시작 (venv 우선)
echo "🚀 Backend on $FLASK_PORT..."
if [ -d "venv" ]; then
  source venv/bin/activate
  nohup python flask_app.py > logs/backend.log 2>&1 &
else
  nohup python3.11 flask_app.py > logs/backend.log 2>&1 &
fi
BACKEND_PID=$!

# Frontend 시작
cd frontend
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo "🎉 Started!"
echo "   Backend: http://localhost:$FLASK_PORT (PID $BACKEND_PID)"
echo "   Frontend: http://localhost:$FRONTEND_PORT (PID $FRONTEND_PID)"
echo "   Logs: tail -f logs/backend.log logs/frontend.log"