#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""서비스 수명주기의 경합·재기동·준비 판정을 격리 환경에서 검증한다."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE_HELPER = ROOT / "scripts" / "service_lifecycle.sh"


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project with spaces"
    (project / "logs").mkdir(parents=True)
    return project


def _run_helper(
    project: Path,
    body: str,
    *,
    env: dict[str, str] | None = None,
    timeout: float = 5,
) -> subprocess.CompletedProcess[str]:
    shell = """
PROJECT_ROOT=$1
source "$2"
lifecycle_init
""" + body
    return subprocess.run(
        ["bash", "-c", shell, "lifecycle-test", str(project), str(LIFECYCLE_HELPER)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _write_executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o700)


def _wait_for_path(path: Path, timeout: float = 2) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.01)
    return path.exists()


def _terminate_owned_process(pid_file: Path, expected_command: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=1,
        ).stdout
        if str(expected_command) not in command:
            return
        os.kill(pid, signal.SIGTERM)
    except (PermissionError, ProcessLookupError, subprocess.TimeoutExpired, ValueError):
        return


def test_ss_returns_every_visible_listener_pid(tmp_path: Path) -> None:
    """여러 리스너 PID 중 하나만 보고 포트가 해제됐다고 오판하지 않는다."""
    project = _project(tmp_path)
    bin_dir = project / "bin"
    _write_executable(bin_dir / "lsof", "#!/bin/sh\nexit 0\n")
    _write_executable(
        bin_dir / "ss",
        """#!/bin/sh
case " $* " in
  *" -ltnp "*)
    echo 'LISTEN 0 2048 0.0.0.0:5501 0.0.0.0:* users:(("gunicorn",pid=22,fd=5),("gunicorn",pid=11,fd=5),("gunicorn",pid=22,fd=6))'
    ;;
esac
""",
    )
    env = {"PATH": f"{bin_dir}:{os.defpath}"}

    result = _run_helper(project, "lifecycle_port_pids 5501\n", env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["11", "22"]


def test_ss_hidden_listener_pid_returns_unknown_status(tmp_path: Path) -> None:
    """권한 때문에 PID가 숨은 리스너를 빈 포트로 처리하지 않는다."""
    project = _project(tmp_path)
    bin_dir = project / "bin"
    _write_executable(bin_dir / "lsof", "#!/bin/sh\nexit 0\n")
    _write_executable(
        bin_dir / "ss",
        """#!/bin/sh
echo 'LISTEN 0 2048 0.0.0.0:5501 0.0.0.0:*'
""",
    )
    env = {"PATH": f"{bin_dir}:{os.defpath}"}

    result = _run_helper(project, "lifecycle_port_pids 5501\n", env=env)

    assert result.returncode == 2
    assert result.stdout == ""


def test_frontend_signature_rejects_other_app_next_maintenance_command(tmp_path: Path) -> None:
    """같은 프로젝트의 다른 Next 관련 명령을 프론트 서비스로 오인하지 않는다."""
    project = _project(tmp_path)

    result = _run_helper(
        project,
        "lifecycle_service_command_matches frontend 'node other_app/next maintenance'\n",
    )

    assert result.returncode != 0


def test_concurrent_lifecycle_lock_rejects_second_operation(tmp_path: Path) -> None:
    """동시에 실행한 두 번째 start/stop 작업이 임계 구역에 들어가지 않는다."""
    project = _project(tmp_path)
    ready = project / "holder-ready"
    release = project / "release-holder"
    holder_shell = """
PROJECT_ROOT=$1
source "$2"
lifecycle_init
lifecycle_acquire_lock || exit 10
: > "$3"
while [ ! -e "$4" ]; do sleep 0.02; done
lifecycle_release_lock
"""
    holder = subprocess.Popen(
        [
            "bash",
            "-c",
            holder_shell,
            "lifecycle-holder",
            str(project),
            str(LIFECYCLE_HELPER),
            str(ready),
            str(release),
        ],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert _wait_for_path(ready), holder.communicate(timeout=1)

        contender = _run_helper(project, "lifecycle_acquire_lock\n")

        assert contender.returncode != 0
        assert "진행 중" in contender.stderr
        assert holder.poll() is None
    finally:
        release.touch()
        holder.communicate(timeout=3)


def test_lifecycle_lock_recovers_after_owner_exits_without_release(tmp_path: Path) -> None:
    """비정상 종료한 이전 작업의 잠금이 다음 정상 작업을 영구 차단하지 않는다."""
    project = _project(tmp_path)
    abandoned = _run_helper(project, "lifecycle_acquire_lock\n")
    assert abandoned.returncode == 0, abandoned.stderr

    recovered = _run_helper(
        project,
        "lifecycle_acquire_lock || exit 20\nlifecycle_release_lock\n",
    )

    assert recovered.returncode == 0, recovered.stderr


def test_http_200_from_foreign_listener_never_marks_service_ready(tmp_path: Path) -> None:
    """다른 프로세스의 HTTP 200을 새 자식의 준비 완료로 인정하지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
LIFECYCLE_READY_WAIT_SECONDS=1
kill() { return 0; }
sleep() { return 0; }
lifecycle_service_owns_port() { return 1; }
lifecycle_http_ok() { return 0; }
wait_for_http backend 5501 http://127.0.0.1:5501/api/kr/market-gate 7001
""",
    )

    assert result.returncode != 0
    assert "준비 확인 실패" in result.stderr


def test_stop_refuses_to_kill_listener_that_respawns_with_new_pid(tmp_path: Path) -> None:
    """정상 종료 중 supervisor가 만든 새 PID에는 강제 종료 신호를 보내지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
kill() {
  [ "$1" = -0 ] && return 0
  printf '%s\n' "$*" >> "$PROJECT_ROOT/kill-calls"
  return 0
}
lifecycle_assert_port_is_managed() { printf '100\n'; }
lifecycle_read_pid() { printf '100\n'; }
lifecycle_wait_for_port_free() { return 1; }
lifecycle_port_pids() { printf '200\n'; }
lifecycle_pid_matches_service() { return 0; }
lifecycle_pid_start_token() { printf 'token-a\n'; }
lifecycle_record_matches_process() { return 0; }
lifecycle_terminate_recorded_process() { kill -TERM 100; return 0; }
stop_managed_service backend 5501
""",
    )

    assert result.returncode != 0
    assert "새 PID 200" in result.stderr
    assert (project / "kill-calls").read_text(encoding="utf-8").splitlines() == ["-TERM 100"]


def test_managed_port_rejects_same_project_listener_outside_recorded_process_tree(
    tmp_path: Path,
) -> None:
    """같은 경로·명령처럼 보여도 기록 master 계보 밖의 리스너는 관리 대상으로 삼지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
lifecycle_port_pids() { printf '100\n200\n'; }
lifecycle_read_pid() { printf '100\n'; }
kill() { return 0; }
lifecycle_pid_matches_service() { return 0; }
lifecycle_record_matches_process() { return 0; }
lifecycle_pid_descends_from() { [ "$1" = 100 ] && [ "$2" = 100 ]; }
lifecycle_assert_port_is_managed backend 5501
""",
    )

    assert result.returncode != 0
    assert "200" in result.stderr


def test_force_kill_refuses_pid_reused_after_term_signal(tmp_path: Path) -> None:
    """TERM 대기 중 기록 PID가 재사용되면 새 프로세스에 KILL을 보내지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
kill() {
  [ "$1" = -0 ] && return 0
  printf '%s\n' "$*" >> "$PROJECT_ROOT/kill-calls"
  return 0
}
lifecycle_port_pids() { printf '100\n'; }
lifecycle_read_pid() { printf '100\n'; }
lifecycle_pid_matches_service() { return 0; }
lifecycle_pid_descends_from() { return 0; }
lifecycle_record_matches_process() { return 0; }
lifecycle_pid_start_token() {
  if [ -e "$PROJECT_ROOT/token-read" ]; then printf 'token-b\n'; return 0; fi
  : > "$PROJECT_ROOT/token-read"
  printf 'token-a\n'
  return 0
}
lifecycle_wait_for_port_free() { return 1; }
lifecycle_terminate_recorded_process() { kill -TERM 100; return 0; }
stop_managed_service backend 5501
""",
    )

    assert result.returncode != 0
    assert (project / "kill-calls").read_text(encoding="utf-8").splitlines() == ["-TERM 100"]


def test_stop_does_not_succeed_when_port_is_free_but_master_is_still_alive(
    tmp_path: Path,
) -> None:
    """포트가 먼저 비어도 기록 master의 실제 종료를 확인하기 전에는 성공하지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
lifecycle_assert_port_is_managed() { printf '100\n'; }
lifecycle_read_pid() { printf '100\n'; }
lifecycle_pid_start_token() { printf 'token-a\n'; }
lifecycle_record_matches_process() { return 0; }
lifecycle_terminate_recorded_process() { return 1; }
lifecycle_wait_for_port_free() { return 0; }
lifecycle_clear_pid() { : > "$PROJECT_ROOT/pid-cleared"; }
stop_managed_service backend 5501
""",
    )

    assert result.returncode != 0
    assert "종료를 확인하지 못했습니다" in result.stderr
    assert not (project / "pid-cleared").exists()


def test_stop_keeps_pid_record_when_port_is_taken_after_known_child_exits(
    tmp_path: Path,
) -> None:
    """초기 빈 포트를 종료 직후 다른 프로세스가 점유하면 PID 기록을 지우지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
lifecycle_assert_port_is_managed() { return 0; }
lifecycle_terminate_recorded_process() { : > "$PROJECT_ROOT/port-taken"; return 0; }
lifecycle_assert_port_free() { [ ! -e "$PROJECT_ROOT/port-taken" ]; }
lifecycle_clear_pid() { : > "$PROJECT_ROOT/pid-cleared"; }
stop_managed_service backend 5501
""",
    )

    assert result.returncode != 0
    assert not (project / "pid-cleared").exists()


def test_wait_for_http_fails_before_probe_when_child_already_exited(tmp_path: Path) -> None:
    """기동 자식이 죽었으면 외부 HTTP 응답을 확인하지 않고 즉시 실패한다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
LIFECYCLE_READY_WAIT_SECONDS=5
kill() { return 1; }
lifecycle_service_owns_port() { : > "$PROJECT_ROOT/unexpected-probe"; return 0; }
lifecycle_http_ok() { : > "$PROJECT_ROOT/unexpected-probe"; return 0; }
wait_for_http backend 5501 http://127.0.0.1:5501/api/kr/market-gate 7002
""",
    )

    assert result.returncode != 0
    assert "준비 전에 종료" in result.stderr
    assert not (project / "unexpected-probe").exists()


def test_completed_job_with_reused_live_pid_never_receives_term(tmp_path: Path) -> None:
    """완료된 job의 옛 PID가 살아 보이더라도 현재 자식이 아니면 TERM을 보내지 않는다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
true &
completed_pid=$!
wait "$completed_pid"
lifecycle_pid_alive() { return 0; }
kill() { : > "$PROJECT_ROOT/kill-called"; return 0; }
lifecycle_terminate_started_child backend "$completed_pid"
""",
    )

    assert result.returncode == 0
    assert not (project / "kill-called").exists()


def test_dependency_sync_reoccupied_port_prevents_backend_spawn(tmp_path: Path) -> None:
    """의존성 동기화 중 포트가 다시 점유되면 백엔드를 시작하지 않는다."""
    project = _project(tmp_path)
    (project / "scripts").mkdir()
    (project / "frontend").mkdir()
    (project / "venv" / "bin").mkdir(parents=True)
    shutil.copy2(ROOT / "restart_all.sh", project / "restart_all.sh")
    shutil.copy2(ROOT / "scripts" / "env_value.sh", project / "scripts" / "env_value.sh")
    helper_text = LIFECYCLE_HELPER.read_text(encoding="utf-8")
    helper_text += """

lifecycle_acquire_lock() { return 0; }
lifecycle_release_lock() { return 0; }
lifecycle_assert_port_is_managed() { return 0; }
stop_managed_services() { return 0; }
lifecycle_assert_port_free() {
  echo "foreign listener after sync" >&2
  return 1
}
"""
    (project / "scripts" / "service_lifecycle.sh").write_text(helper_text, encoding="utf-8")
    _write_executable(
        project / "scripts" / "sync_dependencies.sh",
        "#!/bin/sh\n: > sync-called\n",
    )
    _write_executable(
        project / "venv" / "bin" / "gunicorn",
        "#!/bin/sh\n: > backend-invoked\n",
    )
    (project / ".env").write_text(
        "FLASK_PORT=45101\nFRONTEND_PORT=45102\nFLASK_HOST=127.0.0.1\n",
        encoding="utf-8",
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "PYTHON_DOTENV_DISABLED": "1",
    }

    result = subprocess.run(
        ["bash", "restart_all.sh"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode != 0
    assert (project / "sync-called").exists()
    assert not (project / "backend-invoked").exists()
    assert "Ready!" not in result.stdout


def test_pid_record_write_failure_terminates_the_spawned_backend_child(tmp_path: Path) -> None:
    """백엔드 PID 기록 실패 시에도 이번 restart가 만든 실제 자식을 종료한다."""
    project = _project(tmp_path)
    (project / "scripts").mkdir()
    (project / "frontend").mkdir()
    (project / "venv" / "bin").mkdir(parents=True)
    shutil.copy2(ROOT / "restart_all.sh", project / "restart_all.sh")
    shutil.copy2(ROOT / "scripts" / "env_value.sh", project / "scripts" / "env_value.sh")
    helper_text = LIFECYCLE_HELPER.read_text(encoding="utf-8")
    helper_text += """

lifecycle_acquire_lock() { return 0; }
lifecycle_release_lock() { return 0; }
lifecycle_assert_port_is_managed() { return 0; }
lifecycle_assert_port_free() { return 0; }
stop_managed_services() { return 0; }
lifecycle_write_pid() {
  local waited=0
  while [ ! -f "$PROJECT_ROOT/logs/fake-backend.pid" ] && [ "$waited" -lt 100 ]; do
    sleep 0.01
    waited=$((waited + 1))
  done
  return 1
}
"""
    (project / "scripts" / "service_lifecycle.sh").write_text(helper_text, encoding="utf-8")
    _write_executable(project / "scripts" / "sync_dependencies.sh", "#!/bin/sh\nexit 0\n")
    _write_executable(
        project / "venv" / "bin" / "gunicorn",
        """#!/bin/bash
printf '%s\n' "$$" > logs/fake-backend.pid
trap ': > logs/fake-backend-stopped; exit 0' TERM
while :; do :; done
""",
    )
    (project / ".env").write_text(
        "FLASK_PORT=45101\nFRONTEND_PORT=45102\nFLASK_HOST=127.0.0.1\n",
        encoding="utf-8",
    )
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "PYTHON_DOTENV_DISABLED": "1",
        "LIFECYCLE_TERM_WAIT_SECONDS": "1",
        "LIFECYCLE_KILL_WAIT_SECONDS": "1",
    }

    try:
        result = subprocess.run(
            ["bash", "restart_all.sh"],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode != 0
        assert "Ready!" not in result.stdout
        assert _wait_for_path(project / "logs" / "fake-backend-stopped")
        assert not (project / "logs" / "backend.pid").exists()
    finally:
        _terminate_owned_process(
            project / "logs" / "fake-backend.pid",
            project / "venv" / "bin" / "gunicorn",
        )


def test_backend_dying_during_frontend_startup_prevents_final_ready(tmp_path: Path) -> None:
    """프론트 준비 중 백엔드가 죽으면 최종 재검사에서 Ready를 거부하고 자식을 정리한다."""
    project = _project(tmp_path)
    (project / "scripts").mkdir()
    (project / "frontend" / "scripts").mkdir(parents=True)
    (project / "venv" / "bin").mkdir(parents=True)
    shutil.copy2(ROOT / "restart_all.sh", project / "restart_all.sh")
    shutil.copy2(ROOT / "scripts" / "env_value.sh", project / "scripts" / "env_value.sh")
    helper_text = LIFECYCLE_HELPER.read_text(encoding="utf-8")
    helper_text += """

lifecycle_acquire_lock() { return 0; }
lifecycle_release_lock() { return 0; }
lifecycle_assert_port_is_managed() { return 0; }
lifecycle_assert_port_free() { return 0; }
stop_managed_services() { return 0; }
lifecycle_pid_matches_service() { return 0; }
lifecycle_service_owns_port() { return 0; }
lifecycle_http_ok() { return 0; }
wait_for_http() {
  local marker="$PROJECT_ROOT/logs/fake-$1.pid" waited=0
  while [ ! -f "$marker" ] && [ "$waited" -lt 100 ]; do
    sleep 0.01
    waited=$((waited + 1))
  done
  [ -f "$marker" ]
}
"""
    (project / "scripts" / "service_lifecycle.sh").write_text(helper_text, encoding="utf-8")
    _write_executable(project / "scripts" / "sync_dependencies.sh", "#!/bin/sh\nexit 0\n")
    _write_executable(
        project / "venv" / "bin" / "gunicorn",
        """#!/bin/bash
printf '%s\n' "$$" > logs/fake-backend.pid
trap ': > logs/fake-backend-stopped; exit 0' TERM
while :; do :; done
""",
    )
    _write_executable(
        project / "bin" / "node",
        """#!/bin/bash
backend=$(sed -n '1p' ../logs/fake-backend.pid)
command=$(ps -p "$backend" -o command= 2>/dev/null)
case "$command" in
  *"/venv/bin/gunicorn"*) kill -TERM "$backend" ;;
  *) exit 20 ;;
esac
waited=0
while [ ! -f ../logs/fake-backend-stopped ] && [ "$waited" -lt 100 ]; do
  sleep 0.01
  waited=$((waited + 1))
done
[ -f ../logs/fake-backend-stopped ] || exit 21
waited=0
while kill -0 "$backend" 2>/dev/null; do
  state=$(ps -p "$backend" -o stat= 2>/dev/null | tr -d '[:space:]')
  case "$state" in Z*|'') break ;; esac
  [ "$waited" -lt 100 ] || exit 22
  sleep 0.01
  waited=$((waited + 1))
done
printf '%s\n' "$$" > ../logs/fake-frontend.pid
trap ': > ../logs/fake-frontend-stopped; exit 0' TERM
while :; do :; done
""",
    )
    (project / ".env").write_text(
        "FLASK_PORT=45101\nFRONTEND_PORT=45102\nFLASK_HOST=127.0.0.1\n",
        encoding="utf-8",
    )
    env = {
        "PATH": f"{project / 'bin'}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "PYTHON_DOTENV_DISABLED": "1",
        "LIFECYCLE_TERM_WAIT_SECONDS": "1",
        "LIFECYCLE_KILL_WAIT_SECONDS": "1",
    }

    try:
        result = subprocess.run(
            ["bash", "restart_all.sh"],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=8,
        )

        assert result.returncode != 0
        assert "최종 서비스 준비 확인에 실패" in result.stderr
        assert "Ready!" not in result.stdout
        assert _wait_for_path(project / "logs" / "fake-backend-stopped")
        assert _wait_for_path(project / "logs" / "fake-frontend-stopped")
        assert not (project / "logs" / "backend.pid").exists()
        assert not (project / "logs" / "frontend.pid").exists()
    finally:
        _terminate_owned_process(
            project / "logs" / "fake-backend.pid",
            project / "venv" / "bin" / "gunicorn",
        )
        _terminate_owned_process(
            project / "logs" / "fake-frontend.pid",
            project / "bin" / "node",
        )


def test_failed_frontend_startup_cleans_up_own_children_after_port_becomes_foreign(
    tmp_path: Path,
) -> None:
    """프론트 기동 실패 뒤 포트 소유권이 바뀌어도 이번 restart의 두 자식을 종료한다."""
    project = _project(tmp_path)
    (project / "scripts").mkdir()
    (project / "frontend" / "scripts").mkdir(parents=True)
    (project / "venv" / "bin").mkdir(parents=True)
    for source in ("restart_all.sh",):
        shutil.copy2(ROOT / source, project / source)
    shutil.copy2(ROOT / "scripts" / "env_value.sh", project / "scripts" / "env_value.sh")
    helper_text = LIFECYCLE_HELPER.read_text(encoding="utf-8")
    helper_text += """

lifecycle_acquire_lock() { return 0; }
lifecycle_release_lock() { return 0; }
lifecycle_assert_port_free() { return 0; }
lifecycle_assert_port_is_managed() {
  local count=0
  [ -f "$PROJECT_ROOT/assert-count" ] && count=$(sed -n '1p' "$PROJECT_ROOT/assert-count")
  count=$((count + 1))
  printf '%s\n' "$count" > "$PROJECT_ROOT/assert-count"
  [ "$count" -le 2 ]
}
stop_managed_services() { return 0; }
lifecycle_pid_matches_service() { return 0; }
wait_for_http() {
  local service=$1 marker="$PROJECT_ROOT/logs/fake-$1.pid" waited=0
  while [ ! -f "$marker" ] && [ "$waited" -lt 100 ]; do
    sleep 0.01
    waited=$((waited + 1))
  done
  [ -f "$marker" ] || return 1
  [ "$service" = backend ]
}
"""
    (project / "scripts" / "service_lifecycle.sh").write_text(helper_text, encoding="utf-8")
    _write_executable(project / "scripts" / "sync_dependencies.sh", "#!/bin/sh\nexit 0\n")
    def child_script(name: str, prelude: str = "") -> str:
        return f"""#!/bin/bash
{prelude}printf '%s\\n' "$$" > "logs/fake-{name}.pid"
trap ': > "logs/fake-{name}-stopped"; exit 0' TERM
while :; do sleep 0.1; done
"""

    _write_executable(
        project / "venv" / "bin" / "gunicorn",
        child_script("backend"),
    )
    _write_executable(
        project / "bin" / "node",
        child_script("frontend", "cd ..\n"),
    )
    (project / ".env").write_text(
        "FLASK_PORT=45101\nFRONTEND_PORT=45102\nFLASK_HOST=127.0.0.1\n",
        encoding="utf-8",
    )
    env = {
        "PATH": f"{project / 'bin'}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
    }

    try:
        result = subprocess.run(
            ["bash", "restart_all.sh"],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode != 0
        assert "Ready!" not in result.stdout
        assert _wait_for_path(project / "logs" / "fake-backend-stopped"), (
            result.stdout,
            result.stderr,
        )
        assert _wait_for_path(project / "logs" / "fake-frontend-stopped"), (
            result.stdout,
            result.stderr,
        )
        assert not (project / "logs" / "backend.pid").exists()
        assert not (project / "logs" / "frontend.pid").exists()
    finally:
        _terminate_owned_process(
            project / "logs" / "fake-backend.pid",
            project / "venv" / "bin" / "gunicorn",
        )
        _terminate_owned_process(
            project / "logs" / "fake-frontend.pid",
            project / "bin" / "node",
        )


def test_legacy_adoption_records_a_matching_pid(tmp_path: Path) -> None:
    """소유자·경로·명령이 같은 기존 점유자는 관리 대상으로 전환한다."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
lifecycle_pid_matches_service() { return 0; }
lifecycle_pid_start_token() { printf 'Mon Sep 22 00:00:00 2026\\n'; }
lifecycle_legacy_master_pid backend 4242
""",
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout.strip() == "4242"
    assert "관리 대상으로 전환했습니다" in result.stderr
    assert (project / "logs" / "backend.pid").read_text(encoding="utf-8").startswith("4242|")


def test_pid_alive_returns_unknown_when_ps_state_is_blank(tmp_path: Path) -> None:
    """kill -0 이 성공해도 ps 가 상태를 돌려주지 않으면 종료(1)가 아니라 알 수 없음(2)이다([INFRA-077])."""
    project = _project(tmp_path)
    bin_dir = project / "bin"
    _write_executable(bin_dir / "ps", "#!/bin/sh\nexit 0\n")
    env = {"PATH": f"{bin_dir}:{os.defpath}"}

    result = _run_helper(project, "lifecycle_pid_alive $$\n", env=env)

    assert result.returncode == 2, result.stdout


def test_terminate_reports_term_to_kill_escalation(tmp_path: Path) -> None:
    """TERM 대기가 만료되면 KILL 로 올리기 전에 stderr 에 한 줄 남긴다([INFRA-077])."""
    project = _project(tmp_path)
    result = _run_helper(
        project,
        """
lifecycle_read_pid() { printf '100\n'; }
lifecycle_pid_alive() { return 0; }
lifecycle_pid_matches_service() { return 0; }
lifecycle_record_matches_process() { return 0; }
lifecycle_signal_process() { printf '%s %s\n' "$1" "$2" >> "$PROJECT_ROOT/signals"; }
lifecycle_wait_for_exit() {
  [ -e "$PROJECT_ROOT/term-waited" ] && return 0
  : > "$PROJECT_ROOT/term-waited"
  return 1
}
lifecycle_terminate_recorded_process frontend
""",
    )

    assert result.returncode == 0, result.stderr
    assert (project / "signals").read_text(encoding="utf-8").splitlines() == ["TERM 100", "KILL 100"]
    assert "⚠️  frontend PID 100" in result.stderr
    assert "KILL" in result.stderr


def test_terminate_started_child_fails_fast_when_ps_is_blank(tmp_path: Path) -> None:
    """ps 가 비어 생사를 알 수 없으면 살아 있는 자식을 wait 로 기다리지 않고 바로 실패한다([INFRA-077])."""
    project = _project(tmp_path)
    bin_dir = project / "bin"
    _write_executable(bin_dir / "ps", "#!/bin/sh\nexit 0\n")
    env = {"PATH": f"{bin_dir}:{os.defpath}"}

    started = time.monotonic()
    result = _run_helper(
        project,
        """
sleep 3 &
child=$!
lifecycle_terminate_started_child backend "$child"
code=$?
kill -KILL "$child" 2>/dev/null
wait "$child" 2>/dev/null
exit "$code"
""",
        env=env,
        timeout=10,
    )

    assert result.returncode != 0
    assert time.monotonic() - started < 2
