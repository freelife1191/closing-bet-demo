#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-039] Flask 바인딩 기본값 검사."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_READ_HOST = "from config import config; print(config.FLASK_HOST)"


def _read_flask_host(tmp_path: Path, host: str | None) -> str:
    """`.env` 가 없는 디렉터리에서 config 를 새로 읽는다.

    config.py 는 모듈 최상단에서 load_dotenv() 를 부른다. 같은 프로세스 안에서
    importlib.reload 로 다시 읽으면 그 호출이 저장소 루트의 .env 를 다시 채우므로,
    코드의 기본값이 아니라 .env 의 값을 검사하게 된다. cwd 를 빈 임시 디렉터리로
    두면 load_dotenv() 가 읽을 파일이 없어 기본값이 그대로 드러난다.

    같은 문제를 같은 방식으로 푼 자리가 tests/engine/test_config_env_precedence.py 다.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO_ROOT)
    if host is None:
        env.pop("FLASK_HOST", None)
    else:
        env["FLASK_HOST"] = host

    result = subprocess.run(
        [sys.executable, "-c", _READ_HOST],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_default_host_is_loopback(tmp_path: Path):
    # FLASK_HOST 를 적지 않은 배포가 기본으로 안전해야 한다. [INFRA-027] 의 신원
    # 서명은 경로에도 메서드에도 nonce 에도 묶여 있지 않은 120초 bearer 이고, 그것을
    # 받아들이는 근거가 서명이 오가는 구간이 proxy 와 Flask 사이뿐이라는 것이다.
    # 기본값이 0.0.0.0 이면 그 근거가 배포하는 사람의 방화벽 설정에만 남는다.
    assert _read_flask_host(tmp_path, None) == "127.0.0.1"


def test_explicit_host_still_wins(tmp_path: Path):
    # 컨테이너 밖에서 들어오는 배포는 0.0.0.0 이 필요하다. Procfile 이 그 경우다.
    # 좁힌 기본값이 그 경로를 막으면 안 된다.
    assert _read_flask_host(tmp_path, "0.0.0.0") == "0.0.0.0"
