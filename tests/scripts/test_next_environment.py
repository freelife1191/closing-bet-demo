#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-055] Next 실행 자식에게 허용된 환경만 전달하는지 검사한다."""

from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LAUNCHER = _REPO_ROOT / "frontend" / "scripts" / "run-next.js"
_PACKAGE_JSON = _REPO_ROOT / "frontend" / "package.json"
_NEXT_ENV = _REPO_ROOT / "frontend" / "node_modules" / "@next" / "env"
_RESTART_ALL = _REPO_ROOT / "restart_all.sh"
_ENV_VALUE = _REPO_ROOT / "scripts" / "env_value.sh"

_OBSERVED_KEYS = (
    "GOOGLE_CLIENT_ID",
    "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "NEXTAUTH_SECRET",
    "NEXTAUTH_URL",
    "NEXTAUTH_URL_INTERNAL",
    "ADMIN_EMAILS",
    "ADMIN_API_TOKEN",
    "INTERNAL_IDENTITY_SECRET",
    "API_URL",
    "NEXT_PUBLIC_API_URL",
    "NODE_ENV",
    "NODE_OPTIONS",
    "SMTP_PASSWORD",
    "UNKNOWN_BACKEND_SECRET",
    "NEXT_PUBLIC_UNSUPPORTED",
    "PORT",
    "NEXT_TELEMETRY_DISABLED",
)


def _write_stub_next(frontend: Path) -> None:
    """실제 Next 대신 인수·합성 키·SIGTERM만 소유 파일에 기록한다."""
    next_bin = frontend / "node_modules" / "next" / "dist" / "bin"
    next_bin.mkdir(parents=True)
    keys = json.dumps(_OBSERVED_KEYS)
    (next_bin / "next.js").write_text(
        "const fs = require('fs');\n"
        "const path = require('path');\n"
        f"const keys = {keys};\n"
        "const observed = Object.fromEntries(keys.flatMap((key) => "
        "process.env[key] === undefined ? [] : [[key, process.env[key]]]));\n"
        "const output = path.resolve(__dirname, '../../../../observed.json');\n"
        "const write = (extra = {}) => fs.writeFileSync(output, JSON.stringify({argv: process.argv.slice(2), cwd: process.cwd(), env: observed, ...extra}));\n"
        "if (process.argv.includes('--wait-for-term')) {\n"
        "  write({started: true});\n"
        "  const terminate = (signal) => { write({terminated: signal}); process.exit(0); };\n"
        "  process.on('SIGINT', () => terminate('SIGINT'));\n"
        "  process.on('SIGTERM', () => terminate('SIGTERM'));\n"
        "  setInterval(() => {}, 1000);\n"
        "} else {\n"
        "  write();\n"
        "  process.exit(process.argv.includes('--exit-seven') ? 7 : 0);\n"
        "}\n",
        encoding="utf-8",
    )


def _fixture(tmp_path: Path, nested_next_env: bool = False) -> Path:
    """임시 프로젝트에 실제 launcher와 최소 의존성만 둔다."""
    assert _LAUNCHER.is_file(), "[INFRA-055] Next 환경 launcher가 아직 없다"
    frontend = tmp_path / "frontend"
    (frontend / "scripts").mkdir(parents=True)
    shutil.copy2(_LAUNCHER, frontend / "scripts" / "run-next.js")
    _write_stub_next(frontend)
    env_parent = frontend / "node_modules" / "next" / "node_modules" / "@next" if nested_next_env else frontend / "node_modules" / "@next"
    env_parent.mkdir(parents=True)
    os.symlink(_NEXT_ENV, env_parent / "env")
    return frontend


def _run(frontend: Path, command: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """원본 환경을 섞지 않은 합성 환경으로 launcher를 실행한다."""
    synthetic = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(frontend.parent / "home"),
        "LANG": "C",
        "NODE_ENV": "test",
        "NODE_OPTIONS": "--trace-warnings",
        "GOOGLE_CLIENT_ID": "QA_GOOGLE",
        "ADMIN_API_TOKEN": "QA_ADMIN",
        "INTERNAL_IDENTITY_SECRET": "QA_IDENTITY",
        "SMTP_PASSWORD": "QA_SMTP",
        "UNKNOWN_BACKEND_SECRET": "QA_UNKNOWN",
    }
    if env:
        synthetic.update(env)
    return subprocess.run(
        ["node", "scripts/run-next.js", command, *args],
        cwd=frontend,
        env=synthetic,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _observed(frontend: Path) -> dict[str, object]:
    return json.loads((frontend / "observed.json").read_text(encoding="utf-8"))


def _stop_owned_process_group(process: subprocess.Popen[str]) -> None:
    """테스트가 만든 별도 세션만 제한 시간 안에 종료하고 회수한다."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def test_restart_bootstrap_preserves_next_symlink_target_permissions(tmp_path: Path) -> None:
    """[INFRA-055] launcher 전 bootstrap이 .next 링크 대상을 chmod하면 실패한다."""
    project = tmp_path / "project"
    (project / "frontend").mkdir(parents=True)
    (project / "scripts").mkdir()
    shutil.copy2(_ENV_VALUE, project / "scripts" / "env_value.sh")
    target = project / "outside-next"
    target.mkdir(mode=0o755)
    target.chmod(0o755)
    os.symlink("../outside-next", project / "frontend" / ".next")
    bootstrap = _RESTART_ALL.read_text(encoding="utf-8").split("FRONTEND_PORT=", 1)[0]
    (project / "restart-bootstrap.sh").write_text(bootstrap, encoding="utf-8")

    result = subprocess.run(["bash", "restart-bootstrap.sh"], cwd=project, capture_output=True, text=True, timeout=10)

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert (project / "frontend" / ".next").is_symlink()


@pytest.mark.parametrize(("command", "mode", "option"), (("dev", "development", "--turbo"), ("build", "production", "--profile"), ("start", "production", "--keepAliveTimeout=1")))
def test_npm_scripts_filter_environment_and_forward_options(tmp_path: Path, command: str, mode: str, option: str) -> None:
    """[INFRA-055] npm 스크립트가 launcher를 우회하면 합성 백엔드 비밀이 자식에 남는다."""
    frontend = _fixture(tmp_path)
    shutil.copy2(_PACKAGE_JSON, frontend / "package.json")
    (frontend / f".env.{mode}").write_text("NEXT_PUBLIC_API_URL=from-mode\n", encoding="utf-8")
    synthetic = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(frontend.parent / "home"),
        "NODE_ENV": "test",
        "NODE_OPTIONS": "--trace-warnings",
        "ADMIN_API_TOKEN": "QA_ADMIN",
        "INTERNAL_IDENTITY_SECRET": "QA_IDENTITY",
        "SMTP_PASSWORD": "QA_SMTP",
    }

    result = subprocess.run(["npm", "run", command, "--", option], cwd=frontend, env=synthetic, capture_output=True, text=True, timeout=10)

    assert result.returncode == 0, result.stderr
    observed = _observed(frontend)
    assert observed["argv"] == [command, str(frontend), option]
    assert observed["env"]["NODE_ENV"] == mode
    assert observed["env"]["ADMIN_API_TOKEN"] == "QA_ADMIN"
    assert observed["env"]["INTERNAL_IDENTITY_SECRET"] == "QA_IDENTITY"
    assert observed["env"]["NEXT_PUBLIC_API_URL"] == "from-mode"
    assert "SMTP_PASSWORD" not in observed["env"]
    assert "NODE_OPTIONS" not in observed["env"]


def test_launcher_filters_parent_environment_and_uses_fixed_project_directory(tmp_path: Path) -> None:
    """[INFRA-055] 허용하지 않은 부모 비밀 또는 NODE_OPTIONS가 자식에 남으면 실패한다."""
    frontend = _fixture(tmp_path)

    result = _run(frontend, "build", "--profile")

    assert result.returncode == 0, result.stderr
    observed = _observed(frontend)
    assert observed["argv"] == ["build", str(frontend), "--profile"]
    assert observed["cwd"] == str(frontend)
    child_env = observed["env"]
    assert child_env["GOOGLE_CLIENT_ID"] == "QA_GOOGLE"
    assert child_env["ADMIN_API_TOKEN"] == "QA_ADMIN"
    assert child_env["INTERNAL_IDENTITY_SECRET"] == "QA_IDENTITY"
    assert child_env["NODE_ENV"] == "production"
    assert "SMTP_PASSWORD" not in child_env
    assert "UNKNOWN_BACKEND_SECRET" not in child_env
    assert "NODE_OPTIONS" not in child_env
    assert stat.S_IMODE((frontend / ".next").stat().st_mode) == 0o700


def test_launcher_resolves_project_path_from_script_when_called_outside_frontend(tmp_path: Path) -> None:
    """[INFRA-055] 호출자의 cwd가 Next 프로젝트 또는 초기화 cwd를 바꾸면 실패한다."""
    frontend = _fixture(tmp_path)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path / "home"), "NODE_ENV": "test"}

    result = subprocess.run(
        ["node", str(frontend / "scripts" / "run-next.js"), "build"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    observed = _observed(frontend)
    assert observed["argv"] == ["build", str(frontend)]
    assert observed["cwd"] == str(frontend)


def test_launcher_merges_frontend_then_root_files_without_overriding_parent(tmp_path: Path) -> None:
    """[INFRA-055] 파일 순서·확장·인용값이 부모 허용키를 덮거나 비밀을 들이면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend / ".env.production.local").write_text(
        "GOOGLE_CLIENT_ID=file-must-lose\n"
        "NEXTAUTH_URL=https://first.example\n"
        "NEXTAUTH_URL=https://frontend.example\n"
        "NEXTAUTH_URL_INTERNAL=\"https://frontend\\n.internal\"\n"
        "API_URL=$NEXTAUTH_URL/api\n"
        "NEXT_PUBLIC_API_URL=\"literal-$(not-a-command)\"\n",
        encoding="utf-8",
    )
    (frontend.parent / ".env.production").write_text(
        "export NEXT_PUBLIC_GOOGLE_CLIENT_ID=\"root-quoted\"\n"
        "NEXTAUTH_URL_INTERNAL=https://root-must-lose.example\n"
        "SMTP_PASSWORD=must-reject-if-root-were-validated\n",
        encoding="utf-8",
    )

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    child_env = _observed(frontend)["env"]
    assert child_env["GOOGLE_CLIENT_ID"] == "QA_GOOGLE"
    assert child_env["NEXTAUTH_URL"] == "https://frontend.example"
    assert child_env["NEXTAUTH_URL_INTERNAL"] == "https://frontend\n.internal"
    assert child_env["API_URL"] == "https://frontend.example/api"
    assert child_env["NEXT_PUBLIC_API_URL"] == "literal-$(not-a-command)"
    assert child_env["NEXT_PUBLIC_GOOGLE_CLIENT_ID"] == "root-quoted"
    assert "SMTP_PASSWORD" not in child_env


@pytest.mark.parametrize(
    "contents",
    (
        "SMTP_PASSWORD=synthetic-root\nNEXT_PUBLIC_API_URL=$SMTP_PASSWORD\n",
        "SMTP_PASSWORD=synthetic-root\nAPI_URL=$SMTP_PASSWORD\n",
        "API_URL=https://private.example\nNEXT_PUBLIC_API_URL=$API_URL\n",
        "1SECRET=numeric-secret\nNEXT_PUBLIC_API_URL=$1SECRET\n",
        "1SECRET=numeric-secret\nNEXT_PUBLIC_API_URL=${1SECRET}\n",
        "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_GOOGLE_CLIENT_ID\nNEXT_PUBLIC_GOOGLE_CLIENT_ID=$ADMIN_API_TOKEN\n",
        "SMTP_PASSWORD=synthetic-root\nNEXT_PUBLIC_API_URL=${NEXT_PUBLIC_GOOGLE_CLIENT_ID:-$SMTP_PASSWORD}\n",
    ),
)
def test_launcher_rejects_private_references_in_application_env(tmp_path: Path, contents: str) -> None:
    """[INFRA-055] root env의 private 참조가 app/public 키로 확장되면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend.parent / ".env.production").write_text(contents, encoding="utf-8")

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


def test_launcher_rejects_root_public_reference_to_parent_private_value(tmp_path: Path) -> None:
    """[INFRA-055] root public 키가 부모 private 값을 확장해 전달하면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend.parent / ".env.production").write_text("NEXT_PUBLIC_API_URL=$ADMIN_API_TOKEN\n", encoding="utf-8")

    result = _run(frontend, "build", env={"ADMIN_API_TOKEN": "parent-private"})

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


def test_launcher_allows_safe_aliases_and_preserves_escaped_dollar_and_marker_lookalike(tmp_path: Path) -> None:
    """[INFRA-055] 허용 alias와 literal 달러·marker 모양 값까지 바꾸면 실패한다."""
    frontend = _fixture(tmp_path)
    marker_lookalike = "value-\ue000not-a-random-marker\ue001"
    (frontend.parent / ".env.production").write_text(
        "NEXTAUTH_URL=https://safe.example\n"
        "API_URL=$NEXTAUTH_URL/api\n"
        "NEXT_PUBLIC_GOOGLE_CLIENT_ID=public-id\n"
        "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_GOOGLE_CLIENT_ID/public\n"
        "NEXTAUTH_SECRET=" + marker_lookalike + "\n"
        "NEXTAUTH_URL_INTERNAL=\\$()\n",
        encoding="utf-8",
    )

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    child_env = _observed(frontend)["env"]
    assert child_env["API_URL"] == "https://safe.example/api"
    assert child_env["NEXT_PUBLIC_API_URL"] == "public-id/public"
    assert child_env["NEXTAUTH_SECRET"] == marker_lookalike
    assert child_env["NEXTAUTH_URL_INTERNAL"] == "$()"


def test_launcher_replaces_raw_parser_state_before_actual_expansion(tmp_path: Path) -> None:
    """[INFRA-055] raw marker pass 상태가 실제 Next 확장 결과에 남으면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend.parent / ".env.production").write_text(
        "NEXT_PUBLIC_GOOGLE_CLIENT_ID=public-id\n"
        "NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_GOOGLE_CLIENT_ID/actual\n",
        encoding="utf-8",
    )

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    assert _observed(frontend)["env"]["NEXT_PUBLIC_API_URL"] == "public-id/actual"


def test_launcher_unlinks_only_exact_legacy_link_after_preflight(tmp_path: Path) -> None:
    """[INFRA-055] 허용한 낡은 링크만 지우며 root 값은 한 번만 읽어야 한다."""
    frontend = _fixture(tmp_path)
    root_env = frontend.parent / ".env"
    root_env.write_text("NEXTAUTH_SECRET=from-root\n", encoding="utf-8")
    legacy_link = frontend / ".env"
    os.symlink("../.env", legacy_link)

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    assert not legacy_link.exists() and not legacy_link.is_symlink()
    assert _observed(frontend)["env"]["NEXTAUTH_SECRET"] == "from-root"


@pytest.mark.parametrize("kind", ("unrelated-link", "directory"))
def test_launcher_rejects_non_regular_frontend_env_without_mutating_it(tmp_path: Path, kind: str) -> None:
    """[INFRA-055] 링크·비정규 입력을 따라가거나 지우면 실패한다."""
    frontend = _fixture(tmp_path)
    env_file = frontend / ".env.production"
    if kind == "unrelated-link":
        target = frontend.parent / "other.env"
        target.write_text("NEXTAUTH_SECRET=other\n", encoding="utf-8")
        os.symlink("../other.env", env_file)
    else:
        env_file.mkdir()

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert "other" not in result.stderr + result.stdout
    assert env_file.is_symlink() if kind == "unrelated-link" else env_file.is_dir()


def test_launcher_rejects_fifo_frontend_env_before_reading_it(tmp_path: Path) -> None:
    """[INFRA-055] FIFO를 dotenv 파일처럼 열어 기동이 멈추면 실패한다."""
    frontend = _fixture(tmp_path)
    env_file = frontend / ".env.production"
    os.mkfifo(env_file)

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert stat.S_ISFIFO(env_file.lstat().st_mode)


def test_launcher_rejects_dotenv_expansion_error_before_spawning(tmp_path: Path) -> None:
    """[INFRA-055] 순환 확장 오류를 무시하고 Next를 실행하면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend / ".env.production").write_text(
        "NEXTAUTH_URL=$API_URL\nAPI_URL=$NEXTAUTH_URL\n",
        encoding="utf-8",
    )

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


def test_launcher_hides_injected_environment_read_error(tmp_path: Path) -> None:
    """[INFRA-055] 환경 파일 open 실패가 자식 실행이나 오류 내용 노출로 이어지면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend / ".env.production").write_text("NEXTAUTH_SECRET=synthetic\n", encoding="utf-8")
    preload = frontend / "deny-env-open.js"
    preload.write_text(
        "const fs = require('fs');\n"
        "const originalOpen = fs.openSync;\n"
        "fs.openSync = (file, ...args) => {\n"
        "  if (String(file).endsWith('.env.production')) {\n"
        "    const error = new Error('synthetic EACCES');\n"
        "    error.code = 'EACCES';\n"
        "    throw error;\n"
        "  }\n"
        "  return originalOpen(file, ...args);\n"
        "};\n",
        encoding="utf-8",
    )
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path / "home"), "NODE_ENV": "test"}

    result = subprocess.run(
        ["node", "--require", str(preload), "scripts/run-next.js", "build"],
        cwd=frontend,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert "EACCES" not in result.stderr + result.stdout


def test_launcher_rejects_prohibited_frontend_key_without_exposing_value(tmp_path: Path) -> None:
    """[INFRA-055] frontend 파일의 백엔드 키를 Next가 재로딩하면 실패한다."""
    frontend = _fixture(tmp_path)
    env_file = frontend / ".env.production"
    env_file.write_text("SMTP_PASSWORD=never-print-this\n", encoding="utf-8")
    before = env_file.read_bytes()

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert env_file.read_bytes() == before
    assert "never-print-this" not in result.stderr + result.stdout


def test_launcher_repairs_existing_next_permissions_without_deleting_cache(tmp_path: Path) -> None:
    """[INFRA-055] 권한을 좁히면서 기존 Next 캐시를 지우면 실패한다."""
    frontend = _fixture(tmp_path)
    cache = frontend / ".next"
    cache.mkdir()
    retained = cache / "cache.bin"
    retained.write_bytes(b"cache")
    cache.chmod(0o755)

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    assert retained.read_bytes() == b"cache"
    assert stat.S_IMODE(cache.stat().st_mode) == 0o700


@pytest.mark.parametrize("kind", ("symlink", "regular-file"))
def test_launcher_rejects_non_directory_next_before_spawning(tmp_path: Path, kind: str) -> None:
    """[INFRA-055] .next 링크·일반 파일에 쓰거나 지우면 실패한다."""
    frontend = _fixture(tmp_path)
    next_path = frontend / ".next"
    if kind == "symlink":
        target = frontend.parent / "outside-next"
        target.mkdir()
        os.symlink("../outside-next", next_path)
    else:
        next_path.write_bytes(b"preserve")
    before = next_path.read_bytes() if kind == "regular-file" else None

    result = _run(frontend, "build")

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert next_path.is_symlink() if kind == "symlink" else next_path.read_bytes() == before


def test_launcher_propagates_child_exit_status(tmp_path: Path) -> None:
    """[INFRA-055] 자식 Next의 실패를 launcher가 성공으로 바꾸면 실패한다."""
    frontend = _fixture(tmp_path)

    result = _run(frontend, "build", "--exit-seven")

    assert result.returncode == 7
    assert _observed(frontend)["argv"] == ["build", str(frontend), "--exit-seven"]


@pytest.mark.parametrize("options", (("other-project",), ("--port", "3501", "other-project"), ("--",)))
def test_launcher_rejects_extra_positional_before_spawning(tmp_path: Path, options: tuple[str, ...]) -> None:
    """[INFRA-055] 추가 디렉터리를 Next에 넘겨 프로젝트가 바뀔 수 있으면 실패한다."""
    frontend = _fixture(tmp_path)

    result = _run(frontend, "build", *options)

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


@pytest.mark.parametrize(
    "options",
    (("--port", "3501"), ("--port=3501",), ("--hostname", "127.0.0.1"), ("--hostname=127.0.0.1",), ("--keepAliveTimeout=1",)),
)
def test_launcher_forwards_value_options_without_treating_values_as_directories(tmp_path: Path, options: tuple[str, ...]) -> None:
    """[INFRA-055] 값이 필요한 옵션의 값까지 위치 인수로 거부하면 실패한다."""
    frontend = _fixture(tmp_path)

    result = _run(frontend, "build", *options)

    assert result.returncode == 0, result.stderr
    assert _observed(frontend)["argv"] == ["build", str(frontend), *options]


def test_launcher_resolves_next_env_from_nested_next_dependency(tmp_path: Path) -> None:
    """[INFRA-055] hoisted 패키지 가정으로 nested Next 설치가 기동 실패하면 실패한다."""
    frontend = _fixture(tmp_path, nested_next_env=True)

    result = _run(frontend, "build")

    assert result.returncode == 0, result.stderr
    assert _observed(frontend)["argv"] == ["build", str(frontend)]


@pytest.mark.parametrize("option", ("--inspect", "--experimental-build-mode", "--internal-trace"))
def test_launcher_preserves_optional_value_flags_without_a_value(tmp_path: Path, option: str) -> None:
    """선택적 값을 받는 Next 옵션을 필수 값으로 오판하면 실패한다."""
    frontend = _fixture(tmp_path)
    result = _run(frontend, "dev", option)
    assert result.returncode == 0, result.stderr
    assert _observed(frontend)["argv"] == ["dev", str(frontend), option]


@pytest.mark.parametrize("key", ("PORT", "NEXT_TELEMETRY_DISABLED"))
def test_launcher_does_not_import_runtime_values_from_env_files(tmp_path: Path, key: str) -> None:
    """파일의 backend 참조가 실행용 변수로 우회해 자식에 들어가면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend.parent / ".env.production").write_text(
        f"SMTP_PASSWORD=runtime-private\n{key}=$SMTP_PASSWORD\n", encoding="utf-8"
    )
    result = _run(frontend, "build")
    assert result.returncode == 0, result.stderr
    assert key not in _observed(frontend)["env"]


@pytest.mark.parametrize("contents", (
    "NEXT_PUBLIC_GOOGLE_CLIENT_ID=\\$ADMIN_API_TOKEN\nNEXT_PUBLIC_API_URL=$NEXT_PUBLIC_GOOGLE_CLIENT_ID\n",
    "NEXT_PUBLIC_GOOGLE_CLIENT_ID=ADMIN_API_TOKEN\nNEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_GOOGLE_CLIENT_ID}\n",
    "NEXT_PUBLIC_GOOGLE_CLIENT_ID=\\$NEXT_PUBLIC_API_URL\nNEXT_PUBLIC_API_URL=${NEXT_PUBLIC_GOOGLE_CLIENT_ID}_SECRET\nNEXT_PUBLIC_API_URL_SECRET=private-suffix\n",
))
def test_launcher_rejects_dynamic_dollar_construction(tmp_path: Path, contents: str) -> None:
    """이스케이프 해제·치환 뒤 새 private 참조를 합성하면 실패한다."""
    frontend = _fixture(tmp_path)
    (frontend.parent / ".env.production").write_text(contents, encoding="utf-8")
    result = _run(frontend, "build")
    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


@pytest.mark.parametrize("missing", ("O_NOFOLLOW", "O_DIRECTORY"))
def test_launcher_requires_no_follow_platform_support(tmp_path: Path, missing: str) -> None:
    """안전한 파일 열기 플래그가 없을 때 0으로 대체해 진행하면 실패한다."""
    frontend = _fixture(tmp_path)
    preload = frontend / "missing-flag.js"
    preload.write_text(
        "const fs = require('fs'); const Module = require('module');\n"
        "const wrapped = Object.create(fs);\n"
        f"Object.defineProperty(wrapped, 'constants', {{value: {{...fs.constants, {missing}: undefined}}}});\n"
        "const load = Module._load;\n"
        "Module._load = function(name, ...args) { return name === 'fs' ? wrapped : load.call(this, name, ...args); };\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", "--require", str(preload), "scripts/run-next.js", "build"],
        cwd=frontend, env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()


def test_launcher_rejects_next_path_swap_without_chmodding_foreign_target(tmp_path: Path) -> None:
    """[INFRA-055] lstat 뒤 .next 교체가 외부 디렉터리 chmod로 이어지면 실패한다."""
    frontend = _fixture(tmp_path)
    next_directory = frontend / ".next"
    next_directory.mkdir()
    foreign_target = frontend / "outside-next"
    foreign_target.mkdir(mode=0o755)
    foreign_target.chmod(0o755)
    preload = frontend / "swap-next-directory.js"
    preload.write_text(
        "const fs = require('fs');\n"
        "const path = require('path');\n"
        "const nextDirectory = path.join(process.cwd(), '.next');\n"
        "const originalOpen = fs.openSync;\n"
        "const originalChmod = fs.chmodSync;\n"
        "let swapped = false;\n"
        "const swap = () => {\n"
        "  if (swapped) return;\n"
        "  swapped = true;\n"
        "  fs.rmSync(nextDirectory, {recursive: true, force: true});\n"
        "  fs.symlinkSync('outside-next', nextDirectory);\n"
        "};\n"
        "fs.openSync = (file, ...args) => {\n"
        "  const descriptor = originalOpen(file, ...args);\n"
        "  if (path.resolve(String(file)) === nextDirectory) swap();\n"
        "  return descriptor;\n"
        "};\n"
        "fs.chmodSync = (file, ...args) => {\n"
        "  if (path.resolve(String(file)) === nextDirectory) swap();\n"
        "  return originalChmod(file, ...args);\n"
        "};\n",
        encoding="utf-8",
    )
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path / "home"), "NODE_ENV": "test"}

    result = subprocess.run(
        ["node", "--require", str(preload), "scripts/run-next.js", "build"],
        cwd=frontend,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert not (frontend / "observed.json").exists()
    assert stat.S_IMODE(foreign_target.stat().st_mode) == 0o755


@pytest.mark.parametrize("termination", (signal.SIGINT, signal.SIGTERM))
def test_launcher_forwards_termination_to_owned_child(tmp_path: Path, termination: signal.Signals) -> None:
    """[INFRA-055] SIGINT·SIGTERM가 Next 자식에 같은 신호로 전달되지 않으면 실패한다."""
    frontend = _fixture(tmp_path)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path / "home"), "NODE_ENV": "test"}
    process = subprocess.Popen(
        ["node", "scripts/run-next.js", "build", "--wait-for-term"],
        cwd=frontend,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (frontend / "observed.json").exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (frontend / "observed.json").exists()

        process.send_signal(termination)
        process.wait(timeout=5)

        assert process.returncode != 0
        assert _observed(frontend)["terminated"] == termination.name
    finally:
        _stop_owned_process_group(process)
