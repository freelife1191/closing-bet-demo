#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_data 모듈 규약 회귀 테스트.

이 파일이 지키는 것은 두 가지다.

1. `scripts/init_data.py` 가 `init_data` 와 `scripts.init_data` 두 이름으로 동시에
   메모리에 올라가지 않는다. 최상위 이름으로 임포트하는 코드가 하나도 없으면 그 상태가
   구조적으로 불가능해진다. `sys.modules` 를 런타임에 들여다보는 방식은 쓰지 않는다.
   pytest 전체 실행에서는 앞선 테스트가 남긴 상태에 결과가 좌우되기 때문이다.
2. 그 파일이 자기 `NumpyEncoder` 사본을 다시 만들지 않는다. 사본에는 datetime 분기가
   없어서 같은 payload 가 저장 경로에 따라 성공하기도 실패하기도 했다.
"""

from __future__ import annotations

import ast
import json
import pathlib
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    ".git", ".tox", ".venv", "__pycache__", "backup", "build", "data", "dist",
    "frontend", "logs", "node_modules", "secrets", "venv",
}


def _python_sources() -> list[pathlib.Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    ]


def _top_level_module_names(node: ast.AST) -> list[str]:
    """이 노드가 최상위 이름으로 여는 모듈 이름을 돌려준다."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if "." not in alias.name]
    if isinstance(node, ast.ImportFrom):
        if node.level == 0 and node.module and "." not in node.module:
            return [node.module]
    return []


def _imports_init_data_as_top_level(node: ast.AST) -> bool:
    """`import init_data`, `from init_data import ...`, `import_module("init_data")` 를 가린다."""
    if "init_data" in _top_level_module_names(node):
        return True
    if isinstance(node, ast.Call):
        # import_module("init_data") 와 __import__("init_data") 는 임포트문이 아니라
        # 호출이라 따로 가린다. 이름을 키워드로 넘기는 형태도 함께 본다.
        callee = node.func
        name = callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, "id", None)
        if name not in {"import_module", "__import__"}:
            return False
        given = node.args[:1] + [kw.value for kw in node.keywords if kw.arg == "name"]
        return any(
            isinstance(arg, ast.Constant) and arg.value == "init_data" for arg in given
        )
    return False


def _top_level_init_data_imports(path: pathlib.Path) -> list[str]:
    """이 파일에서 init_data 를 최상위 이름으로 여는 자리를 찾아 위치를 돌려준다."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    return [
        f"{path.relative_to(ROOT)}:{node.lineno}"
        for node in ast.walk(tree)
        if _imports_init_data_as_top_level(node)
    ]


def test_no_module_imports_init_data_as_top_level_name():
    offenders = [item for path in _python_sources() for item in _top_level_init_data_imports(path)]

    assert offenders == [], (
        "init_data 를 최상위 이름으로 임포트하면 scripts.init_data 와 별개의 모듈이 "
        f"메모리에 올라간다. scripts 패키지 경로로 바꿔야 한다: {offenders}"
    )


def test_init_data_uses_shared_numpy_encoder_with_datetime_support():
    import numpy_json_encoder
    from scripts import init_data

    assert init_data.NumpyEncoder is numpy_json_encoder.NumpyEncoder

    # 실패했던 실제 입력은 DataFrame 에서 뽑은 값이라 표준 datetime 이 아니라
    # pandas Timestamp 였다. 그 형태를 함께 고정한다.
    payload = {
        "generated_at": datetime(2026, 9, 4, 17, 0),
        "recorded_at": pd.Timestamp("2026-09-04 17:00"),
        "score": np.int64(15),
    }
    dumped = json.loads(json.dumps(payload, ensure_ascii=False, cls=init_data.NumpyEncoder))

    assert dumped == {
        "generated_at": "2026-09-04T17:00:00",
        "recorded_at": "2026-09-04T17:00:00",
        "score": 15,
    }


def test_init_data_imports_engine_modules_through_engine_package():
    """`scripts/init_data.py` 가 engine 아래 모듈을 최상위 이름으로 열지 않는다.

    `create_kr_ai_analysis_with_key` 만 `from kr_ai_analyzer import KrAiAnalyzer` 로 열고
    있었다. 그 이름은 `engine/` 아래에만 있고 `engine` 디렉터리를 `sys.path` 에 넣는 곳이
    저장소에 없어서, 이 함수는 호출될 때마다 ModuleNotFoundError 로 끝났다. 넓은
    `except Exception` 이 그 예외를 삼켰기 때문에 임포트 실패가 분석 실패처럼 보였다.

    저장소 루트에도 같은 이름의 모듈이 있는 경우(`config`)는 최상위 임포트가 정상이므로
    비교 대상에서 뺀다.
    """
    engine_only = {
        module.stem
        for module in (ROOT / "engine").glob("*.py")
        if module.stem != "__init__" and not (ROOT / f"{module.stem}.py").exists()
    }
    tree = ast.parse((ROOT / "scripts" / "init_data.py").read_text(encoding="utf-8"))

    offenders = [
        f"scripts/init_data.py:{node.lineno}: {name}"
        for node in ast.walk(tree)
        for name in _top_level_module_names(node)
        if name in engine_only
    ]

    assert offenders == [], (
        "engine 아래에만 있는 모듈을 최상위 이름으로 열면 ModuleNotFoundError 로 끝난다. "
        f"engine 패키지 경로로 열어야 한다: {offenders}"
    )


def test_scheduler_entry_points_exist_on_init_data():
    """스케줄러가 이름으로 꺼내는 다섯 함수가 실제 모듈에 있다.

    `_load_init_data_functions` 는 문자열 키로 함수를 담아 돌려주므로, 이름이 어긋나도
    임포트 시점에는 드러나지 않고 스케줄이 실제로 도는 시점의 AttributeError 로 미뤄진다.
    대역을 쓰는 검사들은 그 어긋남을 볼 수 없어서 이 검사만 실제 모듈을 상대로 확인한다.
    """
    from services.scheduler_jobs import _load_init_data_functions

    functions = _load_init_data_functions()

    assert sorted(functions) == [
        "create_daily_prices",
        "create_institutional_trend",
        "create_jongga_v2_latest",
        "create_signals_log",
        "send_jongga_notification",
    ]
    assert all(callable(function) for function in functions.values())
