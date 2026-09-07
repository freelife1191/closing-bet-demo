#!/bin/bash

############################################
# restart_all.sh - 최종 버전 (venv 격리 + deps 충돌 해결)
############################################

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# .env 로드
[ -f .env ] && { echo "📄 .env loaded"; set -a; source .env; set +a; }

# Frontend .env 심볼릭 링크 연결 (배포 환경 대응)
if [ -f .env ]; then
  echo "🔗 Linking .env to frontend/.env..."
  mkdir -p frontend
  ln -sf ../.env frontend/.env
fi

FRONTEND_PORT=${FRONTEND_PORT:-3500}
FLASK_PORT=${FLASK_PORT:-5501}

echo "🛑 Stopping $FRONTEND_PORT/$FLASK_PORT..."

kill_port() {
  local port=$1
  pids=$(lsof -ti :$port 2>/dev/null || true)
  [ -n "$pids" ] && { echo "   🔪 $port ($pids)"; kill -9 $pids 2>/dev/null; }
  command -v ss >/dev/null 2>&1 && {
    pids=$(ss -tulpn 2>/dev/null | grep :$port | awk '{print $7}' | cut -d, -f2 | cut -d= -f2 | sort -u)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  }
}

kill_port $FRONTEND_PORT; kill_port $FLASK_PORT
pkill -f "flask_app.py" "next dev" "npm.*dev" 2>/dev/null || true
mkdir -p logs

echo "🔧 Python deps setup (isolated venv)..."

# 1. 시스템 기본 deps (충돌 최소)
SYS_DEPS=("flask" "flask-cors" "python-dotenv")
for dep in "${SYS_DEPS[@]}"; do
  # 패키지명에서 하이픈을 언더스코어로 변환 (flask-cors → flask_cors, python-dotenv → dotenv)
  import_name=$(echo "$dep" | sed 's/-/_/g' | sed 's/python_dotenv/dotenv/')
  ! python3.11 -c "import $import_name" 2>/dev/null && {
    echo "   📦 System $dep"
    python3.11 -m pip install --break-system-packages --no-deps --quiet "$dep"
  }
done

# 2. venv 격리 환경 (전체 deps)
[ ! -d venv ] && {
  echo "📦 Creating venv..."
  python3.11 -m venv venv
}

source venv/bin/activate
pip install --upgrade pip --quiet >/dev/null

echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt --quiet
deactivate

echo "✅ Python ready!"

# Frontend
[ -d frontend ] || { echo "❌ frontend/ missing!"; exit 1; }
cd frontend
[ ! -d node_modules ] && { echo "📦 npm install..."; npm ci --quiet; }
cd ..

# Backend (venv 실행)
echo "🚀 Backend $FLASK_PORT (Gunicorn)..."
# Cleanup stale lock file
rm -f services/scheduler.lock

source venv/bin/activate
# Use Gunicorn as in Procfile
# 바인딩은 11행에서 source 한 .env 의 FLASK_HOST 를 따르며 기본은 loopback 이다.
nohup gunicorn flask_app:app --bind "${FLASK_HOST:-127.0.0.1}:$FLASK_PORT" --workers 2 --threads 8 --timeout 120 > logs/backend.log 2>&1 &
deactivate
BACKEND_PID=$!

# Frontend
cd frontend
echo "🚀 Frontend $FRONTEND_PORT..."
# Filter noisy logs (NextAuth polling, 404s, etc.) using line-buffered grep
# Note: Using unbuffer or check if Next.js detects pipe. 
# We use grep -vE to filter multiple patterns.
PORT=$FRONTEND_PORT nohup npm run dev 2>&1 | grep --line-buffered -vE "GET /api/auth/session|com.chrome.devtools.json|_not-found|wait - compiling" > ../logs/frontend.log &
FRONTEND_PID=$!
cd ..

echo "🎉 Ready!"
echo "   Backend:  http://localhost:$FLASK_PORT (PID $BACKEND_PID)"
echo "   Frontend: http://localhost:$FRONTEND_PORT (PID $FRONTEND_PID)"
echo "   Logs: tail -f logs/backend.log logs/frontend.log"