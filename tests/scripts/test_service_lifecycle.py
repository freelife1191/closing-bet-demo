#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""재시작 수명주기가 다른 서비스나 실패한 기동을 성공으로 숨기지 않는지 검사한다."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def _fixture(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    (project / "frontend").mkdir()
    for source in ("restart_all.sh", "stop_all.sh"):
        shutil.copy2(ROOT / source, project / source)
    for source in ("env_value.sh", "service_lifecycle.sh"):
        shutil.copy2(ROOT / "scripts" / source, project / "scripts" / source)
    (project / ".env").write_text("FLASK_PORT=5501\nFRONTEND_PORT=3500\n", encoding="utf-8")
    return project


def _command(project: Path, name: str, body: str) -> None:
    command = project / "bin" / name
    command.parent.mkdir(exist_ok=True)
    command.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    command.chmod(0o700)


def test_restart_stops_verified_services_before_mutating_shared_dependencies() -> None:
    """실행 중인 프로세스가 읽는 공유 의존성을 먼저 바꾸지 않는다."""
    restart = (ROOT / "restart_all.sh").read_text(encoding="utf-8")

    assert restart.index("stop_managed_services") < restart.index("sync_dependencies.sh")


def test_restart_never_reports_ready_before_backend_and_frontend_probes_pass() -> None:
    """포트 bind 실패를 Ready로 오인하지 않는다."""
    restart = (ROOT / "restart_all.sh").read_text(encoding="utf-8")

    assert restart.index("wait_for_http") < restart.index('echo "🎉 Ready!"')
    assert "cleanup_started_services" in restart


def test_stop_refuses_unmanaged_listener_without_claiming_success(tmp_path: Path) -> None:
    """PID 기록이 없는 외부 포트 점유자를 죽이거나 성공으로 출력하지 않는다."""
    project = _fixture(tmp_path)
    _command(
        project,
        "lsof",
        "import sys\nif '-t' in ''.join(sys.argv[1:]): print('4242')\nsys.exit(0)\n",
    )
    _command(project, "kill", "import pathlib,sys\npathlib.Path('kill-called').write_text(' '.join(sys.argv[1:]))\n")

    env = {"PATH": f"{project / 'bin'}:{os.environ['PATH']}", "HOME": str(tmp_path / "home")}
    result = subprocess.run(
        ["bash", "stop_all.sh"], cwd=project, env=env, capture_output=True, text=True, timeout=10
    )

    assert result.returncode != 0
    assert "관리 대상이 아닙니다" in result.stderr
    assert "All services stopped" not in result.stdout
    assert not (project / "kill-called").exists()


def test_documented_entrypoints_are_executable() -> None:
    for name in ("restart_all.sh", "stop_all.sh"):
        assert os.access(ROOT / name, os.X_OK), name


def test_process_command_trims_ps_padding_before_matching(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; ps() { printf "next-server (v16.3.5)  \n"; }; lifecycle_service_command_matches frontend "$(lifecycle_pid_command 123)"',
         "test", str(ROOT / "scripts/service_lifecycle.sh")],
        cwd=tmp_path, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr


def test_restart_and_stop_propagate_supervisor_refusal_without_success_message(
    tmp_path: Path,
) -> None:
    """실행 관리자가 쥔 포트에서 두 진입점 모두 성공 문구 없이 비영점으로 끝난다."""
    project = _fixture(tmp_path)
    _command(
        project,
        "lsof",
        "import sys\nif '-t' in ''.join(sys.argv[1:]): print('4242')\nsys.exit(0)\n",
    )
    proc = project / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "cgroup").write_text(
        "0::/user.slice/user-1000.slice/session-6873.scope\n", encoding="utf-8"
    )
    (proc / "4242").mkdir()
    (proc / "4242" / "cgroup").write_text(
        "0::/user.slice/user-1000.slice/user@1000.service/app.slice/closing-bet-frontend.service\n",
        encoding="utf-8",
    )
    env = {
        "PATH": f"{project / 'bin'}:{os.environ['PATH']}",
        "HOME": str(tmp_path / "home"),
        "LIFECYCLE_PROC_DIR": str(proc),
    }

    for entrypoint in ("restart_all.sh", "stop_all.sh"):
        result = subprocess.run(
            ["bash", entrypoint], cwd=project, env=env, capture_output=True, text=True, timeout=30
        )

        assert result.returncode != 0, entrypoint
        assert "closing-bet-frontend.service" in result.stderr, entrypoint
        assert "systemctl --user restart closing-bet-frontend.service" in result.stderr, entrypoint
        assert "🎉 Ready!" not in result.stdout, entrypoint
        assert "종료되었습니다" not in result.stdout, entrypoint


def test_repository_systemd_units_drop_the_settings_that_caused_the_restart_loop() -> None:
    """운영 유닛 파일이 포트 경쟁·잠금 삭제·로그 혼입·무한 재시작을 다시 만들지 않는다."""
    units = sorted((ROOT / "deploy" / "systemd").glob("*.service"))

    assert [unit.name for unit in units] == [
        "closing-bet-backend.service",
        "closing-bet-frontend.service",
    ]
    for unit in units:
        text = unit.read_text(encoding="utf-8")
        # 설명 주석이 아니라 실제로 systemd 가 읽는 설정 줄만 본다.
        directives = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        assert not [line for line in directives if line.startswith("ExecStartPre=")], unit.name
        assert not [line for line in directives if re.search(r"rm\s+-f.*scheduler\.lock", line)], unit.name
        assert not [line for line in directives if "ln -sf" in line], unit.name
        assert not [line for line in directives if "append:" in line], unit.name
        assert "StandardOutput=journal" in directives, unit.name
        assert "StandardError=journal" in directives, unit.name
        # 상한이 사실상 없는 두 표기를 모두 막는다.
        assert not [
            line
            for line in directives
            if re.fullmatch(r"StartLimitIntervalSec=(0|infinity)", line.strip())
        ], unit.name
        assert [line for line in directives if line.startswith("StartLimitBurst=")], unit.name
    backend = [
        line
        for line in (ROOT / "deploy" / "systemd" / "closing-bet-backend.service")
        .read_text(encoding="utf-8")
        .splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert [line for line in backend if "--bind 127.0.0.1:" in line]
    assert not [line for line in backend if "0.0.0.0" in line]
