#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""재시작 수명주기가 다른 서비스나 실패한 기동을 성공으로 숨기지 않는지, Next 실행 모드가
의도한 순서로만 기동하는지, 그리고 편입한 운영 설정(Caddyfile·.gitignore)이 사고를 부른
설정으로 되돌아가지 않는지 검사한다."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest


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


def test_restart_binds_gunicorn_to_loopback_unless_env_overrides() -> None:
    """운영 기동 경로가 스크립트뿐이므로 --bind 의 기본값이 loopback 계약의 마지막 방어선이다."""
    restart = (ROOT / "restart_all.sh").read_text(encoding="utf-8")

    assert 'FLASK_HOST=${_env_flask_host:-${FLASK_HOST:-127.0.0.1}}' in restart
    assert '--bind "${FLASK_HOST}:$FLASK_PORT"' in restart


def test_restart_disables_gunicorn_keep_alive_behind_next_proxy() -> None:
    """Next 프록시의 연결 풀은 유휴 제한이 없어 gunicorn 이 keep-alive 로 닫는 순간의 소켓을 재사용해 500 을 낸다."""
    restart = (ROOT / "restart_all.sh").read_text(encoding="utf-8")

    # 주석 줄에도 같은 문자열이 있으므로 gunicorn 명령 줄 자체를 본다
    assert "--timeout 120 --keep-alive 0 \\\n" in restart


def test_restart_never_reports_ready_before_backend_and_frontend_probes_pass() -> None:
    """포트 bind 실패를 Ready로 오인하지 않는다."""
    restart = (ROOT / "restart_all.sh").read_text(encoding="utf-8")

    assert restart.index("wait_for_http") < restart.index('echo "🎉 Ready!"')
    assert "cleanup_started_services" in restart


@pytest.mark.parametrize("entrypoint", ["stop_all.sh", "restart_all.sh"])
def test_entrypoints_refuse_unmanaged_listener_without_claiming_success(
    tmp_path: Path, entrypoint: str
) -> None:
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
        ["bash", entrypoint], cwd=project, env=env, capture_output=True, text=True, timeout=10
    )

    assert result.returncode != 0
    assert "관리 대상이 아닙니다" in result.stderr
    assert "종료되었습니다" not in result.stdout
    assert "🎉 Ready!" not in result.stdout
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


def _restart_fixture(tmp_path: Path, env: str, *, build_status: int = 0) -> Path:
    """실제 restart_all.sh 를 가짜 gunicorn·node 와 stub 된 포트·준비 검사로 끝까지 돌린다."""
    project = _fixture(tmp_path)
    (project / "frontend" / "scripts").mkdir()
    (project / "logs").mkdir()
    (project / ".env").write_text(f"FLASK_PORT=45101\nFRONTEND_PORT=45102\n{env}", encoding="utf-8")
    helper = project / "scripts" / "service_lifecycle.sh"
    helper.write_text(
        helper.read_text(encoding="utf-8")
        + """
lifecycle_acquire_lock() { return 0; }
lifecycle_release_lock() { return 0; }
lifecycle_assert_port_is_managed() { return 0; }
lifecycle_assert_port_free() { return 0; }
stop_managed_services() { : > "$PROJECT_ROOT/stop-called"; }
# 가짜 자식이 자기 PID 표식을 쓸 때까지 기다린다. 즉시 통과시키면 자식이 첫 줄을 실행하기 전에
# 스크립트가 끝나 기록이 비어 보인다.
wait_for_http() {
  local marker="$PROJECT_ROOT/logs/fake-$1.pid" waited=0
  while [ ! -f "$marker" ] && [ "$waited" -lt 300 ]; do sleep 0.01; waited=$((waited + 1)); done
  [ -f "$marker" ]
}
lifecycle_service_ready() { return 0; }
""",
        encoding="utf-8",
    )
    sync = project / "scripts" / "sync_dependencies.sh"
    sync.write_text("#!/bin/sh\n: > sync-called\n", encoding="utf-8")
    sync.chmod(0o700)
    # 두 가짜 자식은 PID 기록이 시작 시각 토큰을 읽을 수 있도록 잠시 살아 있다가 스스로 끝난다.
    # 포트를 쥐지 않으므로 정리 루프가 필요 없다.
    stay_alive = (
        "import os, pathlib, sys, time\n"
        f"root = pathlib.Path({str(project)!r})\n"
        "{record}"
        "(root / 'logs' / 'fake-{name}.pid').write_text(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    _command(
        project,
        "node",
        stay_alive.format(
            name="frontend",
            record=(
                "(root / 'node-calls').open('a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                f"if sys.argv[2] == 'build': sys.exit({build_status})\n"
            ),
        ),
    )
    gunicorn = project / "venv" / "bin" / "gunicorn"
    gunicorn.parent.mkdir(parents=True)
    gunicorn.write_text(
        f"#!{sys.executable}\n" + stay_alive.format(name="backend", record="(root / 'backend-invoked').touch()\n"),
        encoding="utf-8",
    )
    gunicorn.chmod(0o700)
    return project


def _run_restart(project: Path, **extra_env: str) -> subprocess.CompletedProcess[str]:
    env = {"PATH": f"{project / 'bin'}:{os.environ['PATH']}", "HOME": str(project.parent / "home"), **extra_env}
    return subprocess.run(
        ["bash", "restart_all.sh"], cwd=project, env=env, capture_output=True, text=True, timeout=20
    )


def _node_calls(project: Path) -> list[str]:
    calls = project / "node-calls"
    return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


@pytest.mark.parametrize("env", ["", "NEXT_MODE=dev\n"])
def test_restart_runs_next_dev_without_a_build_when_mode_is_unset_or_dev(tmp_path: Path, env: str) -> None:
    """macOS 개발 경로는 키 없이 종전과 같이 dev 서버를 띄운다."""
    project = _restart_fixture(tmp_path, env)

    result = _run_restart(project)

    assert result.returncode == 0, result.stderr
    assert _node_calls(project) == ["scripts/run-next.js dev"]
    assert "🎉 Ready!" in result.stdout


def test_restart_narrows_logs_dir_to_the_server_account(tmp_path: Path) -> None:
    """backend.log 에 구독자 이메일이 남는다. 로그 파일은 0644 로 만들어지므로 디렉터리가 막는다."""
    project = _restart_fixture(tmp_path, "")
    (project / "logs").chmod(0o755)

    result = _run_restart(project)

    assert result.returncode == 0, result.stderr
    assert (project / "logs").stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("env, shell_env", [("NEXT_MODE=prod\n", {}), ("", {"NEXT_MODE": "prod"})])
def test_restart_builds_then_starts_next_in_prod_mode(tmp_path: Path, env: str, shell_env: dict[str, str]) -> None:
    """운영은 production 빌드로 돈다. .env 가 우선하고 없으면 환경 변수를 읽는다."""
    project = _restart_fixture(tmp_path, env)

    result = _run_restart(project, **shell_env)

    assert result.returncode == 0, result.stderr
    assert _node_calls(project) == ["scripts/run-next.js build", "scripts/run-next.js start"]
    frontend_pid = (project / "logs" / "fake-frontend.pid").read_text(encoding="utf-8")
    assert (project / "logs" / "frontend.pid").read_text(encoding="utf-8").startswith(f"{frontend_pid}|")
    assert "🎉 Ready!" in result.stdout


def test_restart_rejects_unknown_next_mode_before_stopping_anything(tmp_path: Path) -> None:
    """오타 하나가 운영 서비스를 내리지 않도록 잠금·종료 전에 거부한다."""
    project = _restart_fixture(tmp_path, "NEXT_MODE=production\n")

    result = _run_restart(project)

    assert result.returncode != 0
    assert "dev" in result.stderr and "prod" in result.stderr
    assert not (project / "stop-called").exists()
    assert not (project / "sync-called").exists()
    assert _node_calls(project) == []
    assert "🎉 Ready!" not in result.stdout


def test_restart_starts_nothing_when_the_production_build_fails(tmp_path: Path) -> None:
    """빌드가 깨지면 start 도 gunicorn 도 부르지 않고 성공 문구 없이 비영점으로 끝난다."""
    project = _restart_fixture(tmp_path, "NEXT_MODE=prod\n", build_status=7)

    result = _run_restart(project)

    assert result.returncode != 0
    assert _node_calls(project) == ["scripts/run-next.js build"]
    assert not (project / "backend-invoked").exists()
    assert not (project / "logs" / "backend.pid").exists()
    assert not (project / "logs" / "frontend.pid").exists()
    assert "🎉 Ready!" not in result.stdout
    assert "빌드" in result.stderr


@pytest.mark.parametrize(
    "command, expected",
    [
        ("node scripts/run-next.js start", 0),
        ("node scripts/run-next.js dev", 0),
        ("next-server (v16.3.5)", 0),
        # 빌드는 서버가 아니다. 서비스로 인정하면 stop_all.sh 가 진행 중인 빌드를 죽인다.
        ("node scripts/run-next.js build", 1),
    ],
)
def test_frontend_signature_accepts_start_wrapper_but_not_build(tmp_path: Path, command: str, expected: int) -> None:
    result = subprocess.run(
        ["bash", "-c", 'PROJECT_ROOT=$PWD; source "$1"; lifecycle_service_command_matches frontend "$2"',
         "test", str(ROOT / "scripts/service_lifecycle.sh"), command],
        cwd=tmp_path, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == expected, result.stderr


def test_code_and_scripts_never_name_the_production_domain() -> None:
    """공개 URL 의 출처는 .env 의 NEXTAUTH_URL 하나다. 도메인이 코드에 박히면 서버를 옮길 때 조용히 어긋난다."""
    demo = re.search(r"\*\*Live Demo\*\*: https://([^/\s]+)", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    assert demo, "CLAUDE.md 의 Live Demo 줄에서 운영 도메인을 읽지 못했다"
    targets = [
        ROOT / "restart_all.sh",
        ROOT / "stop_all.sh",
        ROOT / "frontend" / "next.config.js",
        *(ROOT / "scripts").glob("*.sh"),
        *(ROOT / "frontend" / "scripts").glob("*.js"),
        *(ROOT / "frontend" / "src").rglob("*.ts"),
        *(ROOT / "frontend" / "src").rglob("*.tsx"),
    ]
    offenders = [
        str(path.relative_to(ROOT)) for path in targets if demo.group(1) in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
