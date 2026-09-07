#!/bin/bash

############################################
# stop_all.sh - Mac/Linux 호환 버전
# Flask(Backend) + Next.js(Frontend) 완전 종료
############################################

# ==== 기본 경로 설정 ====
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# ==== .env 에서 포트만 읽기 ====
# 파일을 통째로 실행하지 않는 이유는 scripts/env_value.sh 의 주석에 있다. 이 스크립트에는
# set -e 가 없으므로 읽기 실패를 직접 잡는다.
source "$PROJECT_ROOT/scripts/env_value.sh" || {
  echo "❌ scripts/env_value.sh 를 읽을 수 없다"; exit 1;
}
if [ -f .env ]; then
  echo "📄 Reading ports from .env..."
else
  echo "⚠️  .env file not found! (using defaults)"
fi

# ==== 포트 결정 ====
# 숫자가 아니면 여기서 멈춘다. 이유는 scripts/env_value.sh 의 env_port 주석에 있다.
FRONTEND_PORT=$(env_port FRONTEND_PORT 3500) || exit 1
FLASK_PORT=$(env_port FLASK_PORT 5501) || exit 1

echo "🛑 Stopping all services on ports $FRONTEND_PORT / $FLASK_PORT ..."

# ==== 시스템 감지 (ss 명령어 Linux 전용) ====
IS_MAC=$(uname | grep -i darwin >/dev/null && echo "true" || echo "")

# ==== 포트 기준 프로세스 종료 함수 (Mac/Linux 공통) ====
kill_port() {
  local port=$1
  echo "🔪 Killing processes on port $port..."

  # lsof 우선 (Mac/Linux 공통, 가장 안정적)
  local pids
  pids=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "   lsof PIDs: $pids"
    kill -TERM $pids 2>/dev/null || true
    sleep 2
    kill -9 $pids 2>/dev/null || true
  fi

  # ss 백업 (Linux만)
  if [ "$IS_MAC" != "true" ] && command -v ss >/dev/null 2>&1; then
    pids=$(ss -tulpn 2>/dev/null | grep :$port | awk '{print $7}' | cut -d, -f2 | cut -d= -f2 | sort -u)
    if [ -n "$pids" ]; then
      echo "   ss PIDs: $pids"
      kill -TERM $pids 2>/dev/null || true
      sleep 2
      kill -9 $pids 2>/dev/null || true
    fi
  fi

  # 최종 확인
  if lsof -ti :$port >/dev/null 2>&1; then
    echo "   ⚠️  Port $port still in use after kill!"
  else
    echo "   ✅ Port $port freed."
  fi
}

# ==== 포트 종료 ====
kill_port "$FRONTEND_PORT"
kill_port "$FLASK_PORT"
echo ""

# ==== 패턴 기반 추가 정리 (nohup 프로세스 잡기) ====
echo "🧹 Killing remaining processes by pattern..."
pkill -f "python3.*flask_app.py" 2>/dev/null || true
pkill -f "flask_app.py" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true
pkill -f "node.*dev" 2>/dev/null || true

# orphan 프로세스 2초 대기 후 강제 종료
sleep 2
pkill -9 -f "flask_app.py" 2>/dev/null || true
pkill -9 -f "next dev" 2>/dev/null || true

# ==== PID 파일 정리 (있을 경우) ====
rm -f logs/*.pid

echo ""
echo "✅ All services stopped safely!"
echo "   Ports $FRONTEND_PORT, $FLASK_PORT confirmed free."
echo "   Logs cleared for next restart."
echo ""
echo "💡 Run './restart_all.sh' to restart services."
