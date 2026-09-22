#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""재시작 수명주기가 다른 서비스나 실패한 기동을 성공으로 숨기지 않는지, 그리고 편입한 운영
설정(systemd 유닛·Caddyfile·.gitignore)이 사고를 부른 설정으로 되돌아가지 않는지 검사한다."""

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
    """운영 유닛 파일이 포트 경쟁·잠금 삭제·무한 재시작을 다시 만들지 않는다.

    서버본과 같아야 하므로 로그 위치(U4)는 단언하지 않는다. 근거는 유닛 파일의 [U4 미채택] 주석에 있다.
    """
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
        # Interval 과 Burst 중 어느 쪽이든 0 이면 systemd 가 상한을 끈다. 0 은 단위 접미사
        # (0s·0sec·0min)를 붙여도 0 이고, infinity 도 같은 뜻이다.
        assert not [
            line
            for line in directives
            if re.fullmatch(r"StartLimitIntervalSec=\s*(0+\s*[a-z]*|infinity)", line.strip())
        ], unit.name
        bursts = [
            int(m.group(1))
            for line in directives
            if (m := re.fullmatch(r"StartLimitBurst=\s*(\d+)", line.strip()))
        ]
        assert bursts and min(bursts) >= 1, (unit.name, bursts)
    backend = [
        line
        for line in (ROOT / "deploy" / "systemd" / "closing-bet-backend.service")
        .read_text(encoding="utf-8")
        .splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert [line for line in backend if "--bind 127.0.0.1:" in line]
    assert not [line for line in backend if "0.0.0.0" in line]


def test_repository_caddyfile_compresses_sets_security_headers_and_hides_port_80() -> None:
    """운영 Caddy 설정이 압축·보안 헤더를 유지하고 80 포트 기본 페이지를 노출하지 않는다."""
    text = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    directives = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert [line for line in directives if line.startswith("encode ")]
    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ):
        assert [line for line in directives if line.startswith(header)], header
    # 스니펫에만 있고 사이트 블록이 가져다 쓰지 않으면 위 두 단언은 의미가 없다.
    assert "import common" in directives
    # 80 포트 기본 페이지는 404 로만 닫고, 정적 파일 서빙은 이 설정 어디에도 두지 않는다.
    assert ":80 {" in directives
    assert "respond 404" in directives
    assert not [line for line in directives if line.startswith("file_server")]
    # Next 만 프록시한다. Flask(5501)로 가는 두 번째 reverse_proxy 가 생기면 loopback 계약이 깨진다.
    assert [line for line in directives if line.startswith("reverse_proxy")] == [
        "reverse_proxy localhost:3500"
    ]


def test_gitignore_hides_macos_appledouble_and_ds_store_files() -> None:
    """secrets/ 는 무시되어도 같은 자리의 ._secrets 는 무시되지 않아 git add . 로 올라갈 수 있었다."""
    for path in ("closingbet/._secrets", "frontend/._env", ".DS_Store"):
        result = subprocess.run(
            ["git", "check-ignore", "-v", path], cwd=ROOT, capture_output=True, text=True
        )
        # 전역 excludesFile 이나 .git/info/exclude 에 걸린 것은 이 저장소의 보장이 아니다.
        assert result.stdout.startswith(".gitignore:"), (path, result.stdout, result.stderr)
