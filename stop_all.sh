#!/bin/bash

# 이 저장소가 시작해 기록한 서비스만 종료한다. 포트만 보고 다른 서비스를 죽이지 않는다.

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

finish() {
  local status=$?
  lifecycle_release_lock
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

lifecycle_acquire_lock || exit 1
echo "🛑 관리 대상 서비스 종료: $FRONTEND_PORT / $FLASK_PORT"
# 한 포트가 외부 서비스면 다른 포트만 먼저 내리는 부분 종료를 피한다.
lifecycle_assert_port_is_managed frontend "$FRONTEND_PORT" >/dev/null || exit 1
lifecycle_assert_port_is_managed backend "$FLASK_PORT" >/dev/null || exit 1
stop_managed_services "$FRONTEND_PORT" "$FLASK_PORT" || exit 1

echo "✅ 이 프로젝트가 관리하던 서비스가 종료되었습니다."
