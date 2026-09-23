#!/bin/bash
# restart_all.sh 와 stop_all.sh 가 공유하는, 이 저장소가 시작한 서비스의 수명주기 도우미다.
# 다른 실행 관리자나 다른 프로젝트의 포트 점유자를 추측해서 종료하지 않는다.

LIFECYCLE_TERM_WAIT_SECONDS=${LIFECYCLE_TERM_WAIT_SECONDS:-8}
LIFECYCLE_KILL_WAIT_SECONDS=${LIFECYCLE_KILL_WAIT_SECONDS:-3}
LIFECYCLE_READY_WAIT_SECONDS=${LIFECYCLE_READY_WAIT_SECONDS:-60}

lifecycle_init() {
  : "${PROJECT_ROOT:?PROJECT_ROOT must be set before loading service_lifecycle.sh}"
  LIFECYCLE_LOG_DIR="$PROJECT_ROOT/logs"
  LIFECYCLE_LOCK_FILE="$LIFECYCLE_LOG_DIR/.service-lifecycle.lock"
}

lifecycle_pid_file() {
  printf '%s/%s.pid\n' "$LIFECYCLE_LOG_DIR" "$1"
}

lifecycle_port_pids() {
  local port=$1 raw pid listeners
  raw=""

  if command -v lsof >/dev/null 2>&1; then
    raw=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  fi
  if [ -z "$raw" ] && command -v ss >/dev/null 2>&1; then
    raw=$(ss -H -ltnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9][0-9]*' | cut -d= -f2 | sort -u)
    listeners=$(ss -H -ltn "sport = :$port" 2>/dev/null || true)
    if [ -z "$raw" ] && [ -n "$listeners" ]; then
      return 2
    fi
  fi
  if [ -z "$raw" ] && ! command -v lsof >/dev/null 2>&1 && ! command -v ss >/dev/null 2>&1; then
    return 2
  fi

  for pid in $raw; do
    case "$pid" in
      *[!0-9]*|'') return 2 ;;
      *) printf '%s\n' "$pid" ;;
    esac
  done
}

# 실행 관리자를 추측해 안내하지 않는다. 누가 포트를 쥐고 있는지는 점유자의 실제 계보에
# 드러나므로 그대로 출력한다. 부모 한 단계만 보면 점유자가 고아가 된 뒤에는 PID 1 밖에
# 보이지 않으므로 조상을 PID 1 까지 따라간다.
lifecycle_print_pid_genealogy() {
  local pid=$1 indent="" prefix="" depth=0
  case "$pid" in ''|*[!0-9]*) return 0 ;; esac
  while [ "$depth" -lt 8 ]; do
    ps -o pid,ppid,pgid,lstart,command -p "$pid" 2>/dev/null | sed "1d;s|^|$prefix|" >&2
    [ "$pid" = 1 ] && return 0
    pid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d '[:space:]')
    case "$pid" in ''|0|*[!0-9]*) return 0 ;; esac
    indent="$indent  "
    prefix="$indent└─ "
    depth=$((depth + 1))
  done
}

lifecycle_assert_port_free() {
  local port=$1 pids pid
  pids=$(lifecycle_port_pids "$port") || {
    echo "❌ 포트 $port 상태를 확인할 수 없어 기동하지 않습니다." >&2
    return 1
  }
  if [ -n "$pids" ]; then
    echo "❌ 포트 $port 를 PID $pids 가 다시 사용 중입니다. 중복 기동하지 않습니다." >&2
    for pid in $pids; do lifecycle_print_pid_genealogy "$pid"; done
    return 1
  fi
}

lifecycle_pid_owner() {
  ps -p "$1" -o user= 2>/dev/null | tr -d '[:space:]'
}

lifecycle_pid_cwd() {
  local pid=$1 cwd
  if [ -r "/proc/$pid/cwd" ]; then
    readlink "/proc/$pid/cwd" 2>/dev/null && return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)
    [ -n "$cwd" ] && { printf '%s\n' "$cwd"; return 0; }
  fi
  if command -v pwdx >/dev/null 2>&1; then
    pwdx "$pid" 2>/dev/null | sed 's/^[^:]*: //' && return 0
  fi
  return 1
}

lifecycle_pid_command() {
  ps -p "$1" -o command= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

lifecycle_service_command_matches() {
  local service=$1 command=$2
  case "$service" in
    backend)
      case "$command" in
        *"/venv/bin/gunicorn flask_app:app"|*"/venv/bin/gunicorn flask_app:app "*|"gunicorn: master [flask_app:app]"|"gunicorn: worker [flask_app:app]") return 0 ;;
      esac ;;
    frontend)
      # 운영은 run-next.js start 로 뜬다([INFRA-076]). build 는 서버가 아니므로 받지 않는다. 실측 트리에
      # 닿는 것은 래퍼 `node scripts/run-next.js <dev|start>` 와 `next-server (v…)` 둘이고, 나머지 변형은
      # process.title 을 바꾸지 못하는 플랫폼의 보험으로 dev 줄과 대칭이다. 죽은 패턴으로 보고 지우지 않는다.
      case "$command" in
        *"node scripts/run-next.js dev"|*"node scripts/run-next.js dev "*|*"node scripts/run-next.js start"|*"node scripts/run-next.js start "*|*"node $PROJECT_ROOT/frontend/scripts/run-next.js dev"|*"node $PROJECT_ROOT/frontend/scripts/run-next.js start"|"next-server (v"*")"|*"/node_modules/next/dist/bin/next dev"*|*"/node_modules/.bin/next dev"*|*"/node_modules/next/dist/bin/next start"*|*"/node_modules/.bin/next start"*) return 0 ;;
      esac ;;
  esac
  return 1
}

lifecycle_pid_matches_service() {
  local service=$1 pid=$2 owner cwd command current_user
  current_user=$(id -un)
  owner=$(lifecycle_pid_owner "$pid")
  if [ -z "$owner" ] || [ "$owner" != "$current_user" ]; then
    echo "❌ $service PID $pid 는 현재 사용자($current_user)가 소유하지 않습니다." >&2
    return 1
  fi
  cwd=$(lifecycle_pid_cwd "$pid") || {
    echo "❌ $service PID $pid 의 작업 경로를 확인할 수 없습니다." >&2
    return 1
  }
  if { [ "$service" = backend ] && [ "$cwd" != "$PROJECT_ROOT" ]; } ||
     { [ "$service" = frontend ] && [ "$cwd" != "$PROJECT_ROOT/frontend" ]; }; then
    echo "❌ $service PID $pid 의 작업 경로가 예상 프로젝트 경로와 다릅니다." >&2
    return 1
  fi
  command=$(lifecycle_pid_command "$pid")
  if ! lifecycle_service_command_matches "$service" "$command"; then
    echo "❌ $service PID $pid 의 실행 명령이 예상 서비스와 다릅니다." >&2
    return 1
  fi
}

lifecycle_read_pid() {
  local file record
  file=$(lifecycle_pid_file "$1")
  [ -f "$file" ] || return 1
  IFS= read -r record < "$file" || return 1
  case "$record" in
    *'|'*) record=${record%%|*} ;;
  esac
  case "$record" in *[!0-9]*|'') return 1 ;; esac
  printf '%s\n' "$record"
}

lifecycle_pid_start_token() {
  ps -p "$1" -o lstart= 2>/dev/null | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

lifecycle_recorded_start_token() {
  local file record
  file=$(lifecycle_pid_file "$1")
  [ -f "$file" ] || return 1
  IFS= read -r record < "$file" || return 1
  case "$record" in *'|'*) printf '%s\n' "${record#*|}" ;; *) return 1 ;; esac
}

lifecycle_write_pid() {
  local token
  token=$(lifecycle_pid_start_token "$2")
  [ -n "$token" ] || return 1
  mkdir -p "$LIFECYCLE_LOG_DIR" || return 1
  printf '%s|%s\n' "$2" "$token" > "$(lifecycle_pid_file "$1")"
}

lifecycle_clear_pid() {
  rm -f "$(lifecycle_pid_file "$1")"
}

lifecycle_acquire_lock() {
  mkdir -p "$LIFECYCLE_LOG_DIR" || return 1
  # flock은 열린 파일 기술에 귀속된다. Python 종료 후에도 셸의 FD 9가 잠금을
  # 유지하며, 셸이 비정상 종료되어도 커널이 해제하므로 stale PID 정리가 필요 없다.
  exec 9>"$LIFECYCLE_LOCK_FILE" || return 1
  if ! python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null; then
    exec 9>&-
    echo "❌ 다른 start/stop 작업이 진행 중이거나 잠금을 획득할 수 없습니다." >&2
    return 1
  fi
  LIFECYCLE_LOCK_ACQUIRED=1
}

lifecycle_release_lock() {
  [ "${LIFECYCLE_LOCK_ACQUIRED:-0}" = 1 ] || return 0
  exec 9>&-
  LIFECYCLE_LOCK_ACQUIRED=0
}

# SIGKILL 은 핸들러가 돌지 않아 자식에게 전달되지 않는다. master 만 죽이면 중간
# 노드(next dev)가 고아로 남고 그 손자가 포트를 계속 쥔다. lifecycle_exec_detached
# 로 띄운 서비스는 기록 PID 가 자기 프로세스 그룹의 리더이므로, 그때만 그룹 전체에
# 보내 체인을 한 번에 정리한다. 입양한 프로세스처럼 그룹 리더가 아니거나 이 셸과
# 같은 그룹이면 종전대로 해당 PID 에만 보낸다.
lifecycle_signal_process() {
  local signal=$1 pid=$2 pgid self_pgid
  pgid=$(ps -p "$pid" -o pgid= 2>/dev/null | tr -d '[:space:]')
  self_pgid=$(ps -p $$ -o pgid= 2>/dev/null | tr -d '[:space:]')
  if [ "$pgid" = "$pid" ] && [ "$pgid" != "$self_pgid" ]; then
    kill -"$signal" -- "-$pid" 2>/dev/null && return 0
  fi
  kill -"$signal" "$pid" 2>/dev/null
}

lifecycle_pid_in_list() {
  local wanted=$1 pid
  shift
  for pid in "$@"; do [ "$pid" = "$wanted" ] && return 0; done
  return 1
}

lifecycle_record_matches_process() {
  local service=$1 pid=$2 recorded_token current_token
  recorded_token=$(lifecycle_recorded_start_token "$service") || return 1
  current_token=$(lifecycle_pid_start_token "$pid")
  [ -n "$current_token" ] && [ "$recorded_token" = "$current_token" ]
}

lifecycle_legacy_master_pid() {
  local service=$1 pid candidate master=""
  shift
  for pid in "$@"; do
    lifecycle_pid_matches_service "$service" "$pid" || return 1
  done
  for candidate in "$@"; do
    master=$candidate
    for pid in "$@"; do
      [ "$pid" = "$candidate" ] && continue
      if ! lifecycle_pid_descends_from "$pid" "$candidate"; then
        master=""
        break
      fi
    done
    [ -n "$master" ] && break
  done
  [ -n "$master" ] || {
    echo "❌ $service 의 기존 리스너에서 하나의 시작 프로세스를 찾을 수 없습니다." >&2
    return 1
  }
  lifecycle_write_pid "$service" "$master" || return 1
  echo "ℹ️  기존 $service PID $master 를 같은 사용자·프로젝트·명령으로 확인해 관리 대상으로 전환했습니다." >&2
  printf '%s\n' "$master"
}

lifecycle_pid_descends_from() {
  local child=$1 ancestor=$2 parent
  while [ "$child" != "$ancestor" ]; do
    parent=$(ps -p "$child" -o ppid= 2>/dev/null | tr -d '[:space:]')
    case "$parent" in *[!0-9]*|'') return 1 ;; esac
    [ "$parent" = 1 ] && return 1
    child=$parent
  done
}

lifecycle_assert_port_is_managed() {
  local service=$1 port=$2 recorded pid pids status
  pids=$(lifecycle_port_pids "$port")
  status=$?
  if [ "$status" -eq 2 ]; then
    echo "❌ 포트 $port 의 점유 PID를 확인할 권한이 없습니다. root 권한이나 실행 관리자 상태를 확인하세요." >&2
    return 1
  fi
  [ -n "$pids" ] || return 0
  recorded=$(lifecycle_read_pid "$service") || {
    lifecycle_legacy_master_pid "$service" $pids >/dev/null || {
      echo "❌ 포트 $port 는 PID $pids 가 사용 중이지만 이 스크립트의 관리 대상이 아닙니다. 자동 종료하지 않았습니다." >&2
      for pid in $pids; do lifecycle_print_pid_genealogy "$pid"; done
      return 1
    }
    recorded=$(lifecycle_read_pid "$service") || return 1
  }
  if ! kill -0 "$recorded" 2>/dev/null; then
    echo "❌ $service 기록 PID $recorded 는 사라졌지만 포트 $port 는 계속 사용 중입니다. 아래 점유자를 중지한 뒤 다시 실행하세요." >&2
    for pid in $pids; do lifecycle_print_pid_genealogy "$pid"; done
    return 1
  fi
  lifecycle_pid_matches_service "$service" "$recorded" || return 1
  if ! lifecycle_record_matches_process "$service" "$recorded"; then
    echo "❌ $service 기록 PID $recorded 가 다른 프로세스로 재사용되었습니다. 자동 종료하지 않았습니다." >&2
    return 1
  fi
  for pid in $pids; do
    lifecycle_pid_matches_service "$service" "$pid" || return 1
    lifecycle_pid_descends_from "$pid" "$recorded" || {
      echo "❌ 포트 $port 의 PID $pid 가 기록된 $service 프로세스의 자식이 아닙니다." >&2
      return 1
    }
  done
  printf '%s\n' "$pids"
}

lifecycle_wait_for_port_free() {
  local port=$1 seconds=$2 waited=0 pids
  while [ "$waited" -lt "$seconds" ]; do
    pids=$(lifecycle_port_pids "$port")
    [ "$?" -eq 2 ] && return 1
    [ -z "$pids" ] && return 0
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

lifecycle_pid_alive() {
  local state
  kill -0 "$1" 2>/dev/null || return 1
  state=$(ps -p "$1" -o stat= 2>/dev/null | tr -d '[:space:]')
  # ps 가 비면 kill -0 과 ps 사이에 사라진 프로세스다. 살아 있다고 보면 시작 식별자 대조가 빈 값으로 실패한다.
  # 다만 ps 자체가 막힌 환경과 구분할 수 없으므로 2 로 돌려주고, wait 로 막힐 수 있는 호출자만 그 값을 가른다.
  [ -n "$state" ] || return 2
  # 아직 부모가 회수하지 않은 zombie는 이미 실행을 마친 프로세스다.
  [[ "$state" != Z* ]]
}

lifecycle_wait_for_exit() {
  local service=$1 pid=$2 seconds=$3 deadline
  deadline=$((SECONDS + seconds))
  while lifecycle_pid_alive "$pid"; do
    lifecycle_record_matches_process "$service" "$pid" || return 1
    [ "$SECONDS" -lt "$deadline" ] || return 1
    sleep 0.1
  done
}

lifecycle_active_job() {
  local active pid
  # 파이프라인의 subshell에서는 Bash job table이 비어 있으므로 먼저 읽는다.
  active=$(jobs -pr; jobs -ps)
  for pid in $active; do [ "$pid" = "$1" ] && return 0; done
  return 1
}

lifecycle_terminate_started_child() {
  local service=$1 pid=$2 deadline token parent
  # PID 파일 기록 자체가 실패해도 이번 셸의 실제 background job은 정리한다.
  # 파일이나 포트 조회 결과가 아니라 셸 job table로 직접 자식임을 확인한다.
  lifecycle_active_job "$pid" || return 0
  lifecycle_pid_alive "$pid"
  # 생사를 알 수 없는(2) 자식을 wait 로 기다리면 ps 가 막힌 환경에서 끝나지 않으므로 바로 실패한다.
  case $? in 0) ;; 1) wait "$pid" 2>/dev/null; return 0 ;; *) return 1 ;; esac
  parent=$(ps -p "$pid" -o ppid= | tr -d '[:space:]')
  [ "$parent" = "$$" ] || return 1
  lifecycle_pid_matches_service "$service" "$pid" || return 1
  token=$(lifecycle_pid_start_token "$pid")
  [ -n "$token" ] || return 1
  lifecycle_active_job "$pid" || return 0
  lifecycle_signal_process TERM "$pid" || return 1
  deadline=$((SECONDS + LIFECYCLE_TERM_WAIT_SECONDS))
  while lifecycle_pid_alive "$pid" && [ "$SECONDS" -lt "$deadline" ]; do sleep 0.1; done
  if lifecycle_pid_alive "$pid"; then
    lifecycle_active_job "$pid" || return 1
    [ "$(lifecycle_pid_start_token "$pid")" = "$token" ] || return 1
    lifecycle_pid_matches_service "$service" "$pid" || return 1
    lifecycle_signal_process KILL "$pid" || return 1
    deadline=$((SECONDS + LIFECYCLE_KILL_WAIT_SECONDS))
    while lifecycle_pid_alive "$pid" && [ "$SECONDS" -lt "$deadline" ]; do sleep 0.1; done
  fi
  lifecycle_pid_alive "$pid" && return 1
  wait "$pid" 2>/dev/null
  return 0
}

lifecycle_terminate_recorded_process() {
  local service=$1 master
  master=$(lifecycle_read_pid "$service") || return 0
  lifecycle_pid_alive "$master" || return 0
  lifecycle_pid_matches_service "$service" "$master" || return 1
  lifecycle_record_matches_process "$service" "$master" || return 1
  lifecycle_signal_process TERM "$master" || return 1
  lifecycle_wait_for_exit "$service" "$master" "$LIFECYCLE_TERM_WAIT_SECONDS" && return 0
  lifecycle_pid_alive "$master" || return 0
  lifecycle_pid_matches_service "$service" "$master" || return 1
  lifecycle_record_matches_process "$service" "$master" || return 1
  echo "⚠️  $service PID $master 가 TERM 뒤 ${LIFECYCLE_TERM_WAIT_SECONDS}초 안에 멈추지 않아 KILL 로 올립니다." >&2
  lifecycle_signal_process KILL "$master" || return 1
  lifecycle_wait_for_exit "$service" "$master" "$LIFECYCLE_KILL_WAIT_SECONDS"
}

stop_managed_service() {
  local service=$1 port=$2 master pids remaining pid token entry
  local identities=()
  pids=$(lifecycle_assert_port_is_managed "$service" "$port") || return 1
  if [ -z "$pids" ]; then
    lifecycle_terminate_recorded_process "$service" || return 1
    lifecycle_assert_port_free "$port" || return 1
    lifecycle_clear_pid "$service"
    return 0
  fi
  master=$(lifecycle_read_pid "$service") || return 1
  for pid in $pids; do
    token=$(lifecycle_pid_start_token "$pid")
    [ -n "$token" ] || return 1
    identities+=("$pid|$token")
  done
  lifecycle_record_matches_process "$service" "$master" || return 1
  echo "🛑 $service PID $master 를 정상 종료합니다..."
  lifecycle_terminate_recorded_process "$service" || {
    echo "❌ $service PID $master 의 종료를 확인하지 못했습니다." >&2
    return 1
  }
  if lifecycle_wait_for_port_free "$port" "$LIFECYCLE_TERM_WAIT_SECONDS"; then
    lifecycle_clear_pid "$service"
    return 0
  fi

  remaining=$(lifecycle_port_pids "$port")
  if [ "$?" -ne 0 ]; then
    echo "❌ 종료 뒤 포트 $port 상태를 확인할 수 없습니다." >&2
    return 1
  fi
  for pid in $remaining; do
    if ! lifecycle_pid_in_list "$pid" $pids; then
      echo "❌ $service 종료 뒤 새 PID $pid 가 포트 $port 를 다시 점유했습니다. 아래 점유자를 중지한 뒤 다시 실행하세요." >&2
      lifecycle_print_pid_genealogy "$pid"
      return 1
    fi
    lifecycle_pid_matches_service "$service" "$pid" || return 1
  done
  echo "⚠️  $service 가 정상 종료 시간 안에 멈추지 않아, 이 스크립트가 시작한 기존 PID만 강제 종료합니다." >&2
  for pid in $remaining; do
    token=""
    for entry in "${identities[@]}"; do
      [ "${entry%%|*}" = "$pid" ] && token=${entry#*|}
    done
    if [ -z "$token" ] || [ "$(lifecycle_pid_start_token "$pid")" != "$token" ]; then
      echo "❌ PID $pid 의 시작 식별자가 바뀌어 강제 종료하지 않습니다." >&2
      return 1
    fi
    kill -KILL "$pid" 2>/dev/null || return 1
  done
  if ! lifecycle_wait_for_port_free "$port" "$LIFECYCLE_KILL_WAIT_SECONDS"; then
    echo "❌ 포트 $port 가 계속 사용 중입니다. 자동 재시작 관리자 또는 권한을 확인하세요." >&2
    return 1
  fi
  lifecycle_clear_pid "$service"
}

stop_managed_services() {
  stop_managed_service frontend "$1" || return 1
  stop_managed_service backend "$2" || return 1
}

lifecycle_service_owns_port() {
  local service=$1 port=$2 expected_pid=$3 pid parent pids status
  pids=$(lifecycle_port_pids "$port")
  status=$?
  [ "$status" -eq 0 ] || return 1
  [ -n "$pids" ] || return 1
  for pid in $pids; do
    lifecycle_pid_matches_service "$service" "$pid" || return 1
    lifecycle_pid_descends_from "$pid" "$expected_pid" || return 1
  done
}

lifecycle_http_ok() {
  local service=$1 url=$2
  [ -x "$PROJECT_ROOT/venv/bin/python" ] || return 1
  "$PROJECT_ROOT/venv/bin/python" - "$service" "$url" <<'PYTHON' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[2], timeout=2) as response:
    if not 200 <= response.status < 300:
        raise RuntimeError(response.status)
    if sys.argv[1] == "backend":
        if response.geturl() != sys.argv[2] or not isinstance(json.loads(response.read(262_144)), dict):
            raise RuntimeError("market gate response is not a direct JSON object")
PYTHON
}

lifecycle_service_ready() {
  local service=$1 port=$2 url=$3 child_pid=$4
  lifecycle_pid_alive "$child_pid" &&
    lifecycle_record_matches_process "$service" "$child_pid" &&
    lifecycle_service_owns_port "$service" "$port" "$child_pid" &&
    lifecycle_http_ok "$service" "$url"
}

# 기동 실패의 사유(포트 충돌, import 오류 등)는 서비스 로그에만 남는다. 화면에는
# "준비 전에 종료되었습니다" 만 보여 사용자가 원인을 따로 찾아야 했으므로 함께 낸다.
lifecycle_tail_service_log() {
  local log="$LIFECYCLE_LOG_DIR/$1.log"
  [ -r "$log" ] || return 0
  echo "── logs/$1.log 마지막 15줄 ──" >&2
  tail -n 15 "$log" >&2
}

wait_for_http() {
  local service=$1 port=$2 url=$3 child_pid=$4 deadline
  deadline=$(( $(date +%s) + LIFECYCLE_READY_WAIT_SECONDS ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if ! kill -0 "$child_pid" 2>/dev/null; then
      echo "❌ $service 프로세스(PID $child_pid)가 준비 전에 종료되었습니다." >&2
      lifecycle_tail_service_log "$service"
      return 1
    fi
    if lifecycle_service_ready "$service" "$port" "$url" "$child_pid"; then
      return 0
    fi
    sleep 1
  done
  echo "❌ $service 준비 확인 실패: $url" >&2
  lifecycle_tail_service_log "$service"
  return 1
}

# 새 세션으로 분리해 실행한다. nohup 만으로는 부족하다. gunicorn 은 자체 SIGHUP
# 핸들러를 등록해 nohup 이 설정한 무시 상태를 덮어쓰고, HUP 을 종료가 아니라 워커
# reload 로 처리하므로 master 가 고아로 살아남아 포트를 계속 점유한다.
# execvp 는 PID 를 유지하므로 호출한 셸이 잡은 $! 는 그대로 대상 프로세스다.
lifecycle_exec_detached() {
  exec python3 -c 'import os, sys
try:
    os.setsid()
except OSError:
    pass
os.execvp(sys.argv[1], sys.argv[1:])' "$@"
}
