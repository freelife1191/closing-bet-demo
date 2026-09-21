#!/bin/bash

# 이 저장소가 시작한 두 서비스만 안전하게 교체한다. 다른 supervisor나 프로젝트의 포트
# 점유자는 종료하지 않고 원인을 출력한다.

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT" || exit 1

source "$PROJECT_ROOT/scripts/env_value.sh" || {
  echo "❌ scripts/env_value.sh 를 읽을 수 없습니다." >&2
  exit 1
}
source "$PROJECT_ROOT/scripts/service_lifecycle.sh" || {
  echo "❌ scripts/service_lifecycle.sh 를 읽을 수 없습니다." >&2
  exit 1
}
lifecycle_init

FRONTEND_PORT=$(env_port FRONTEND_PORT 3500) || exit 1
FLASK_PORT=$(env_port FLASK_PORT 5501) || exit 1
_env_flask_host=$(env_value FLASK_HOST)
FLASK_HOST=${_env_flask_host:-${FLASK_HOST:-127.0.0.1}}
PROBE_HOST=$FLASK_HOST
case "$PROBE_HOST" in 0.0.0.0|::) PROBE_HOST=127.0.0.1 ;; esac

BACKEND_PID=""
FRONTEND_PID=""

cleanup_started_services() {
  local service pid port
  for service in frontend backend; do
    case "$service" in
      frontend) pid=$FRONTEND_PID; port=$FRONTEND_PORT ;;
      backend) pid=$BACKEND_PID; port=$FLASK_PORT ;;
    esac
    [ -n "$pid" ] || continue
    # 준비 확인 전 실패한 자식도 PID 기록·소유자 검증을 거쳐 종료한다. 이 함수는 이번
    # restart에서 생성한 PID가 있을 때만 호출된다.
    if lifecycle_terminate_started_child "$service" "$pid"; then
      if lifecycle_assert_port_free "$port"; then
        lifecycle_clear_pid "$service"
      else
        echo "⚠️  $service 자식 종료 후에도 포트 $port 가 사용 중입니다. 분리된 자식 또는 실행 관리자를 확인하세요." >&2
      fi
    else
      echo "⚠️  이번 실행의 $service PID $pid 정리를 확인하지 못했습니다. logs/$service.pid와 포트 $port 를 확인하세요." >&2
    fi
  done
}

finish() {
  local status=$?
  if [ "$status" -ne 0 ]; then cleanup_started_services; fi
  lifecycle_release_lock
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

lifecycle_acquire_lock || exit 1
mkdir -p logs || exit 1

# 두 포트를 모두 먼저 검증한다. 하나라도 외부/권한/자동 재시작 프로세스면 기존 서비스를
# 일부만 내리지 않는다.
lifecycle_assert_port_is_managed frontend "$FRONTEND_PORT" >/dev/null || exit 1
lifecycle_assert_port_is_managed backend "$FLASK_PORT" >/dev/null || exit 1

echo "🛑 이 프로젝트가 관리하는 $FRONTEND_PORT/$FLASK_PORT 서비스를 종료합니다..."
stop_managed_services "$FRONTEND_PORT" "$FLASK_PORT" || exit 1

# 공유 venv/node_modules를 바꾸므로 기존 서비스를 내린 뒤 적용한다. 실패하면 성공처럼
# 출력하지 않고 여기서 끝난다.
bash "$PROJECT_ROOT/scripts/sync_dependencies.sh" || {
  echo "❌ 의존성 준비 실패. 서비스를 시작하지 않았습니다." >&2
  exit 1
}

lifecycle_assert_port_free "$FLASK_PORT" || exit 1
lifecycle_assert_port_free "$FRONTEND_PORT" || exit 1
echo "🚀 Backend $FLASK_PORT (Gunicorn)..."
nohup "$PROJECT_ROOT/venv/bin/gunicorn" flask_app:app \
  --bind "${FLASK_HOST}:$FLASK_PORT" --workers 2 --threads 8 --timeout 120 \
  9>&- >> "$PROJECT_ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
lifecycle_write_pid backend "$BACKEND_PID" || exit 1
wait_for_http backend "$FLASK_PORT" "http://$PROBE_HOST:$FLASK_PORT/api/kr/market-gate" "$BACKEND_PID" || exit 1

lifecycle_assert_port_free "$FRONTEND_PORT" || exit 1
echo "🚀 Frontend $FRONTEND_PORT..."
(
  cd "$PROJECT_ROOT/frontend" || exit 1
  export PORT="$FRONTEND_PORT"
  exec nohup node scripts/run-next.js dev
) 9>&- >> "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
lifecycle_write_pid frontend "$FRONTEND_PID" || exit 1
wait_for_http frontend "$FRONTEND_PORT" "http://127.0.0.1:$FRONTEND_PORT/" "$FRONTEND_PID" || exit 1

# 프론트엔드를 기다리는 동안 먼저 준비된 백엔드가 죽었을 수도 있다.
lifecycle_service_ready backend "$FLASK_PORT" "http://$PROBE_HOST:$FLASK_PORT/api/kr/market-gate" "$BACKEND_PID" &&
  lifecycle_service_ready frontend "$FRONTEND_PORT" "http://127.0.0.1:$FRONTEND_PORT/" "$FRONTEND_PID" || {
    echo "❌ 최종 서비스 준비 확인에 실패했습니다. 로그를 확인하세요." >&2
    exit 1
  }
echo "🎉 Ready!"
echo "   Backend:  http://$PROBE_HOST:$FLASK_PORT (PID $BACKEND_PID)"
echo "   Frontend: http://localhost:$FRONTEND_PORT (PID $FRONTEND_PID)"
echo "   Logs: tail -f logs/backend.log logs/frontend.log"
