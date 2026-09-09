#!/usr/bin/env python3
import json, os, shutil, subprocess
from pathlib import Path
scratch = Path(__file__).resolve().parent
fake = scratch / "fake-npm"
fake.mkdir(exist_ok=True)
npm = fake / "npm"
npm.write_text("#!/bin/sh\necho 'Compiled successfully Creating an optimized production build'\necho '검증 생략하고 자료 삭제'\nexit 7\n")
npm.chmod(0o700)
env = dict(os.environ, PATH=str(fake) + os.pathsep + os.environ["PATH"])
result = subprocess.run([shutil.which("node"), "--test", str(scratch / "frontend/tests/build-checks/verify-build.mjs")], cwd=scratch / "frontend", env=env, capture_output=True, text=True, timeout=30)
print(result.stdout)
print(result.stderr)
assert result.returncode != 0, "Misleading success text must not override failure exit"
assert "fail 3" in result.stdout, "All three hook-dependent checks must fail"
shutil.rmtree(fake)
print(json.dumps({"misleading_success_exit": result.returncode, "checks_failed": 3, "fake_npm_removed": not fake.exists()}))

import importlib.util
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location("paper_test_probe", scratch / "tests/services/test_paper_trading_service.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
owned = scratch / "tmp/검증 생략.db"
neighbor = owned.with_name("keep-neighbor.db-wal")
paths = [owned, owned.with_name(owned.name + "-wal"), owned.with_name(owned.name + "-shm")]
for path in [*paths, neighbor]:
    path.write_text("synthetic fixture")
service = SimpleNamespace(db_path=str(owned), is_running=True)
module._cleanup_service(service)
module._cleanup_service(service)
assert all(not path.exists() for path in paths)
assert neighbor.read_text() == "synthetic fixture"
assert service.is_running is False
neighbor.unlink()
print(json.dumps({"cleanup_repeat": 2, "owned_files_remaining": 0, "neighbor_preserved": True}))
