#!/bin/bash

############################################
# restart_all.sh - 최종 버전 (venv 격리 + deps 충돌 해결)
############################################

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# .env 에서 이 스크립트가 쓰는 값만 읽는다. 파일을 통째로 실행하지 않는 이유는
# scripts/env_value.sh 의 주석에 있다. 이 스크립트에는 set -e 가 없으므로 읽기 실패를
# 직접 잡는다. 그러지 않으면 함수가 없는 채로 진행해 조용히 코드 기본값으로 떨어진다.
source "$PROJECT_ROOT/scripts/env_value.sh" || {
  echo "❌ scripts/env_value.sh 를 읽을 수 없다"; exit 1;
}

# Frontend .env 심볼릭 링크 연결 (배포 환경 대응). 이 블록의 메시지가 .env 존재도 알린다
if [ -f .env ]; then
  echo "🔗 Linking .env to frontend/.env..."
  mkdir -p frontend
  ln -sf ../.env frontend/.env
fi

# Turbopack 의 FileSystem Cache 가 프로세스 환경을 직렬화해 frontend/.next 아래에 남긴다.
# 위 심볼릭 링크 때문에 Next 환경에는 백엔드 전용 시크릿까지 올라가므로, 실측하면 .env 의
# 키 열여섯 개가 그 캐시 파일에 평문으로 들어 있고 파일 모드는 umask 를 따라 0644 다
# ([INFRA-053]). 캐시는 실행마다 새로 만들어져 파일 모드를 좁혀 두어도 되돌아가므로,
# 디렉터리 순회를 막아 다른 로컬 계정의 접근을 끊는다. Next 16.1(dev)·16.3(build) 부터
# 이 캐시가 기본으로 켜진다.
mkdir -p frontend/.next
chmod 700 frontend/.next

FRONTEND_PORT=$(env_port FRONTEND_PORT 3500) || exit 1
FLASK_PORT=$(env_port FLASK_PORT 5501) || exit 1
_env_flask_host=$(env_value FLASK_HOST)
FLASK_HOST=${_env_flask_host:-$FLASK_HOST}

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
# 바인딩은 위에서 env_value 로 읽은 FLASK_HOST 를 따르며 기본은 loopback 이다.
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