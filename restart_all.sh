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

# Next launcher가 frontend와 루트 .env를 제한된 자식 환경으로 읽고, 낡은 정확한 링크만
# preflight 뒤 제거한다. .next의 생성·권한 검증도 launcher만 소유한다.

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
pkill -f "flask_app.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true
mkdir -p logs

# 잠금 파일/설치 상태가 바뀌면 갱신하고, 설치·검증 실패 시 기동하지 않는다.
bash "$PROJECT_ROOT/scripts/sync_dependencies.sh" || {
  echo "❌ 의존성 준비 실패. 서비스를 시작하지 않습니다." >&2
  exit 1
}

# Backend (venv 실행)
echo "🚀 Backend $FLASK_PORT (Gunicorn)..."
# Cleanup stale lock file
rm -f services/scheduler.lock

# Use Gunicorn as in Procfile
# 바인딩은 위에서 env_value 로 읽은 FLASK_HOST 를 따르며 기본은 loopback 이다.
nohup "$PROJECT_ROOT/venv/bin/gunicorn" flask_app:app --bind "${FLASK_HOST:-127.0.0.1}:$FLASK_PORT" --workers 2 --threads 8 --timeout 120 > logs/backend.log 2>&1 &
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
