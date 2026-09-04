# [INFRA-006] init_data 임포트 경로 통일 실행 계획

> **에이전트 작업자에게:** 이 계획은 `dev-cycle` 사이클 안에서 인라인으로 실행합니다.
> 서브에이전트 분배(`superpowers:subagent-driven-development`)는 쓰지 않습니다. 이 저장소의
> 사이클 규약이 리뷰 순서와 커밋 분할을 이미 정하고 있어서 두 절차가 충돌하기 때문입니다.
> 단계는 체크박스(`- [ ]`)로 표시합니다.

**목표:** `scripts/init_data.py` 가 `init_data` 와 `scripts.init_data` 라는 두 모듈 객체로
메모리에 동시에 올라가는 상태를 없애고, 그 파일이 들고 있던 `NumpyEncoder` 사본을 공용
구현으로 대체합니다.

**접근 방식:** `sys.path` 에 `scripts` 디렉터리를 주입하던 세 곳을 걷어내고 모든 호출자가
`scripts` 패키지 경로로만 이 모듈에 닿게 합니다. 주입이 사라지면 최상위 이름 `init_data` 로는
아예 임포트할 수 없게 되므로 이중 로드의 원인이 구조적으로 제거됩니다. 그 결과로 죽는
`project_root` 전달 체인 다섯 자리도 함께 걷어냅니다.

**기술 스택:** Python 3.11, pytest, Flask 블루프린트, `numpy_json_encoder` 공용 모듈

**근거 문서:** `docs/dev-cycle/audits/AUDIT-INFRA.md` §1.2 와 §2.1

**티어:** T3. `scripts/init_data.py` 와 `services/scheduler_jobs.py` 가 모두
`tier-rules.md` §2 의 「스케줄러와 데이터 적재」 목록에 있습니다. 줄 수와 무관하게 T3 입니다.

## 전역 제약

- 임포트 형태는 `from scripts import init_data` 를 기본으로 씁니다. 이미 저장소의 다섯 곳이
  그 형태이고, `tests/app/test_common_update_service.py` 등의 대역 주입이
  `types.ModuleType("scripts")` 에 `init_data` 속성을 붙이는 방식이라 이 형태에만 걸립니다.
  대역 주입이 걸리지 않는 자리에서는 `from scripts.init_data import <이름>` 도 허용합니다.
  두 형태 모두 `sys.modules["scripts.init_data"]` 하나만 만들므로 이중 로드가 없습니다.
- `init_data` 임포트는 **함수 안 지연 임포트를 유지합니다.** 이 모듈은 `pykrx` 와 `yfinance`
  를 끌어오고 임포트 시점에 `socket.setdefaulttimeout(30)` 같은 부작용을 실행합니다.
  최상위로 올리면 스케줄러 모듈을 읽기만 해도 그 부작용이 발생합니다.
- `scripts/__init__.py` 를 **만들지 않습니다.** 근거는 아래 「방식 확정」에 적었습니다.
- 커밋 메시지 끝에 다음 두 줄을 붙입니다.

      Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
      Claude-Session: https://claude.ai/code/session_018BpBasN8thvGk5msXuhHUh

## 방식 확정 — `__init__.py` 추가가 아니라 `sys.path` 주입 제거

백로그 항목의 첫 체크박스가 두 방식 가운데 하나를 고르라고 요구합니다. **주입 제거를
고릅니다.**

`scripts/__init__.py` 를 만들어도 이중 로드는 그대로 남습니다. `sys.path` 에 `scripts`
디렉터리가 들어 있는 한 `import init_data` 는 여전히 성공하고, 파이썬은 그것을
`scripts.init_data` 와 별개의 모듈로 취급합니다. `__init__.py` 는 `scripts` 를 네임스페이스
패키지에서 정규 패키지로 바꿀 뿐이고, 최상위 이름으로 같은 파일을 다시 여는 경로를 막지
않습니다. 실제로 막는 것은 디렉터리를 `sys.path` 에 넣지 않는 것입니다.

주입을 제거하면 `import init_data` 는 `ModuleNotFoundError` 로 실패하게 되므로, 회귀가
조용히 되살아나지 않고 즉시 드러납니다.

## 파일 구조

| 파일 | 하는 일 | 이번 변경 |
|---|---|---|
| `services/scheduler_jobs.py` | 스케줄러가 부르는 잡 본체 | `importlib` 경로를 패키지 경로로 교체. 캐시 전역 제거 |
| `services/kr_market_route_service.py` | 라우트가 쓰는 서비스 조합 | `sys.path` 주입 제거, `project_root` 인자 제거 |
| `app/routes/kr_market_system_http_routes.py` | 시스템 라우트 등록 | `project_root=` 전달 제거 |
| `app/routes/kr_market_dependency_builders.py` | 라우트 의존성 딕셔너리 조립 | `project_root_getter` 제거 |
| `app/routes/kr_market_route_registry.py` | 라우트 그룹 등록 | `project_root_getter` 제거 |
| `app/routes/kr_market.py` | 블루프린트 진입점 | `project_root_getter` 인자 제거 |
| `scripts/init_data.py` | 데이터 적재 스크립트 | `NumpyEncoder` 사본 삭제, 공용 구현 import |
| `tests/test_grading_logic.py` | 등급 판정 검사 | `sys.path` 주입 제거 |
| `tests/app/test_kr_market_helpers_contract.py` | 라우트 서비스 계약 검사 | 임시 디렉터리 로드 검사를 대역 주입 검사로 교체 |
| `tests/scripts/test_init_data_module_contract.py` | **신규** | 임포트 규약과 인코더 회귀 검사 |

## 작업 1: 최상위 `init_data` 임포트를 금지하는 회귀 검사

이 검사를 먼저 만듭니다. 지금은 실패해야 하고, 작업 2~4 를 마치면 통과합니다. 이후에 누군가
`sys.path` 주입을 되살리면 이 검사가 막습니다.

**파일**
- 생성: `tests/scripts/test_init_data_module_contract.py`

**인터페이스**
- 제공: 없음. 검사 전용 파일입니다.

- [ ] **1단계: 실패하는 검사를 쓴다**

`sys.modules` 를 런타임에 들여다보는 방식은 쓰지 않습니다. pytest 전체 실행에서는 앞선
테스트가 이미 `init_data` 를 올려 두었을 수 있어 실행 순서에 따라 결과가 흔들립니다. 대신
소스를 AST 로 읽어 임포트문 자체를 검사합니다. 순서에 흔들리지 않고, 문자열 매칭과 달리
주석이나 문자열 안의 `init_data` 를 오탐하지 않습니다.

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_data 모듈 규약 회귀 테스트.

이 파일이 지키는 것은 두 가지다.

1. `scripts/init_data.py` 가 `init_data` 와 `scripts.init_data` 두 이름으로 동시에
   메모리에 올라가지 않는다. 최상위 이름으로 임포트하는 코드가 하나도 없으면 그 상태가
   구조적으로 불가능해진다.
2. 그 파일이 자기 `NumpyEncoder` 사본을 다시 만들지 않는다.
"""

from __future__ import annotations

import ast
import json
import pathlib
from datetime import date, datetime

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "venv", "node_modules", "__pycache__", "frontend", "data", "logs"}


def _python_sources() -> list[pathlib.Path]:
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    ]


def _top_level_init_data_imports(path: pathlib.Path) -> list[str]:
    """`import init_data` 또는 `from init_data import ...` 를 찾아 위치를 돌려준다."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "init_data" for alias in node.names):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module == "init_data":
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return found


def test_no_module_imports_init_data_as_top_level_name():
    offenders = [item for path in _python_sources() for item in _top_level_init_data_imports(path)]

    assert offenders == [], (
        "init_data 를 최상위 이름으로 임포트하면 scripts.init_data 와 별개의 모듈이 "
        f"메모리에 올라간다. scripts 패키지 경로로 바꿔야 한다: {offenders}"
    )


def test_init_data_uses_shared_numpy_encoder_with_datetime_support():
    from scripts import init_data
    import numpy_json_encoder

    assert init_data.NumpyEncoder is numpy_json_encoder.NumpyEncoder

    payload = {
        "generated_at": datetime(2026, 9, 4, 17, 0),
        "trade_date": date(2026, 9, 4),
        "score": np.int64(15),
    }
    dumped = json.loads(json.dumps(payload, ensure_ascii=False, cls=init_data.NumpyEncoder))

    assert dumped == {
        "generated_at": "2026-09-04T17:00:00",
        "trade_date": "2026-09-04",
        "score": 15,
    }
```

- [ ] **2단계: 검사를 돌려 실패를 확인한다**

실행: `source venv/bin/activate && pytest tests/scripts/test_init_data_module_contract.py -v`

기대: 두 검사가 모두 실패합니다. 앞의 것은 `services/scheduler_jobs.py`,
`services/kr_market_route_service.py`, `tests/test_grading_logic.py` 세 자리를 offenders 로
보고합니다. 뒤의 것은 `init_data.NumpyEncoder is numpy_json_encoder.NumpyEncoder` 가
거짓이어서 실패합니다.

**실패 내용을 실제로 읽고 넘어갑니다.** 세 자리가 아니라 그보다 적게 나오면 조사가 빠뜨린
곳이 있다는 뜻이므로, 작업 2 로 넘어가기 전에 목록을 다시 맞춥니다.

## 작업 2: 스케줄러 잡의 임포트 경로 교체

**파일**
- 수정: `services/scheduler_jobs.py:11-42`

**인터페이스**
- 제공: `_load_init_data_functions() -> dict[str, Callable[..., Any]]`. 키 다섯 개는
  그대로입니다. `create_signals_log`, `create_jongga_v2_latest`, `create_daily_prices`,
  `create_institutional_trend`, `send_jongga_notification`.
  `tests/services/test_scheduler_jobs_refactor.py` 가 이 함수를 통째로 대역으로 바꿔치기하므로
  시그니처와 반환 형태를 바꾸면 검사 네 건이 깨집니다.

- [ ] **1단계: 함수 본체를 교체한다**

바꾸기 전:

```python
_INIT_DATA_FUNCTIONS_CACHE: dict[str, Callable[..., Any]] | None = None


def _load_init_data_functions() -> dict[str, Callable[..., Any]]:
    """scripts/init_data.py의 진입 함수를 지연 로드한다."""
    global _INIT_DATA_FUNCTIONS_CACHE
    if _INIT_DATA_FUNCTIONS_CACHE is not None:
        return _INIT_DATA_FUNCTIONS_CACHE

    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    init_data = importlib.import_module("init_data")
    _INIT_DATA_FUNCTIONS_CACHE = {
        "create_signals_log": getattr(init_data, "create_signals_log"),
        "create_jongga_v2_latest": getattr(init_data, "create_jongga_v2_latest"),
        "create_daily_prices": getattr(init_data, "create_daily_prices"),
        "create_institutional_trend": getattr(init_data, "create_institutional_trend"),
        "send_jongga_notification": getattr(init_data, "send_jongga_notification"),
    }
    return _INIT_DATA_FUNCTIONS_CACHE
```

바꾼 뒤:

```python
def _load_init_data_functions() -> dict[str, Callable[..., Any]]:
    """scripts/init_data.py의 진입 함수를 지연 로드한다."""
    from scripts import init_data

    return {
        "create_signals_log": init_data.create_signals_log,
        "create_jongga_v2_latest": init_data.create_jongga_v2_latest,
        "create_daily_prices": init_data.create_daily_prices,
        "create_institutional_trend": init_data.create_institutional_trend,
        "send_jongga_notification": init_data.send_jongga_notification,
    }
```

`_INIT_DATA_FUNCTIONS_CACHE` 를 함께 지웁니다. 이 전역이 아끼려던 것은 모듈 로드 비용인데
파이썬이 `sys.modules` 로 이미 캐시하므로 남는 것은 딕셔너리 다섯 줄을 다시 만드는 비용뿐이고,
이 함수는 하루에 몇 번만 불립니다. 전역 가변 상태를 없애면 테스트 사이에 상태가 새는 경로도
함께 사라집니다.

- [ ] **2단계: 쓰이지 않게 된 임포트를 지운다**

`importlib`, `os`, `sys` 세 줄을 지웁니다. 이 파일의 나머지 어디에서도 쓰이지 않는 것을
확인했습니다(32·33·34·36번 줄이 유일한 사용처였습니다).

```python
import logging
from datetime import datetime
from typing import Any, Callable
```

- [ ] **3단계: 스케줄러 검사를 돌린다**

실행: `source venv/bin/activate && pytest tests/services/test_scheduler_jobs_refactor.py -v`

기대: 4건 통과. 이 검사들은 `_load_init_data_functions` 를 대역으로 바꾸므로 실제 모듈을
읽지 않습니다. 여기서 실패하면 반환 딕셔너리의 키 이름이 어긋난 것입니다.

## 작업 3: 라우트 서비스의 `sys.path` 주입과 죽은 `project_root` 체인 제거

`project_root` 는 오직 `sys.path` 주입에만 쓰이던 인자입니다. 주입을 없애면 그 인자와, 그것을
전달하기 위해 다섯 자리에 놓여 있던 `project_root_getter` 배선이 전부 죽습니다. 죽은 배선을
남기면 다음 사람이 「이 값이 어디에 쓰이지」를 다시 추적하게 되므로 같은 커밋에서 걷어냅니다.

**파일**
- 수정: `services/kr_market_route_service.py:12`, `:132-147`, `:150-183`
- 수정: `app/routes/kr_market_system_http_routes.py:144-152`
- 수정: `app/routes/kr_market_dependency_builders.py:128`, `:147`
- 수정: `app/routes/kr_market_route_registry.py:169`, `:188`
- 수정: `app/routes/kr_market.py:274-284`

**인터페이스**
- 제공: `run_user_gemini_reanalysis(target_dates: list[str], api_key: str | None) -> dict[str, Any]`
  (`project_root` 가 빠집니다)
- 제공: `execute_user_gemini_reanalysis_request(user_api_key, user_email, req_data,
  usage_tracker, logger, run_reanalysis_func=None) -> tuple[int, dict[str, Any]]`
  (`project_root` 가 빠집니다)
- 제공: `build_system_route_deps(...)` 의 반환 딕셔너리에서 `project_root_getter` 키가
  사라집니다.

- [ ] **1단계: 서비스 함수 두 개를 고친다**

`services/kr_market_route_service.py` 의 `run_user_gemini_reanalysis` 를 이렇게 바꿉니다.

```python
def run_user_gemini_reanalysis(
    target_dates: list[str],
    api_key: str | None,
) -> dict[str, Any]:
    """사용자 키 기반 Gemini 재분석을 실행한다."""
    from scripts import init_data

    result = init_data.create_kr_ai_analysis_with_key(target_dates or None, api_key=api_key)
    if isinstance(result, dict):
        return result
    return {"count": 0}
```

`execute_user_gemini_reanalysis_request` 에서 `project_root: str` 매개변수를 지우고,
`reanalysis_runner(...)` 호출에서 `project_root=project_root,` 줄을 지웁니다.

`import os` 를 지웁니다. 이 파일에서 `os` 를 쓰던 곳은 138번 줄 하나뿐이었습니다. `sys` 는
71~72번 줄의 `_reload_engine_submodules` 가 계속 쓰므로 남깁니다.

- [ ] **2단계: 전달 체인 네 자리를 지운다**

- `app/routes/kr_market_system_http_routes.py`: `execute_user_gemini_reanalysis_request` 호출에서
  `project_root=deps["project_root_getter"](),` 한 줄을 지웁니다.
- `app/routes/kr_market_dependency_builders.py`: 매개변수 `project_root_getter: Callable[[], str],`
  와 반환 딕셔너리의 `"project_root_getter": project_root_getter,` 를 지웁니다.
- `app/routes/kr_market_route_registry.py`: 매개변수 `project_root_getter: Callable[[], str],` 와
  `build_system_route_deps(...)` 에 넘기는 `project_root_getter=project_root_getter,` 를 지웁니다.
- `app/routes/kr_market.py`: `register_system_and_execution_route_groups(...)` 호출에서
  `project_root_getter=lambda: os.path.dirname(...)` 한 줄을 지웁니다. **`import os` 는
  남깁니다.** 이 파일의 116·177·223·303번 줄이 계속 씁니다.

- [ ] **3단계: 계약 검사를 대역 주입 방식으로 다시 쓴다**

`tests/app/test_kr_market_helpers_contract.py:801` 의
`test_route_service_run_user_gemini_reanalysis_imports_scripts_module` 는 임시 디렉터리에
가짜 `init_data.py` 파일을 만들고 그것이 `sys.path` 를 통해 로드되는지 검사합니다. 즉
**지금 없애려는 동작 자체를 고정하는 검사**입니다. 지우지 말고, 같은 함수가 `scripts` 패키지
경로로 모듈을 찾는지 검사하도록 바꿉니다. 대역 주입 형태는 같은 저장소의
`tests/app/test_common_update_service.py:25-31` 을 따릅니다.

```python
def test_route_service_run_user_gemini_reanalysis_uses_scripts_package(monkeypatch):
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.init_data = types.SimpleNamespace(
        create_kr_ai_analysis_with_key=lambda target_dates=None, api_key=None: {
            "count": len(target_dates or []),
            "has_key": bool(api_key),
        }
    )
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)

    result = route_service.run_user_gemini_reanalysis(
        target_dates=["2026-02-20", "2026-02-21"],
        api_key="user-key",
    )

    assert result["count"] == 2
    assert result["has_key"] is True
```

- [ ] **4단계: `project_root_getter` 를 넘기던 검사 세 건을 고친다**

`project_root_getter=` 또는 `"project_root_getter":` 를 넘기는 줄을 지웁니다. 세 자리입니다.

- `tests/app/test_kr_market_system_http_routes_refactor.py:55` 의 대역 람다 시그니처에서
  `project_root` 를 빼고, 61번 줄의 `"project_root_getter": lambda: "/tmp",` 를 지웁니다.
- `tests/app/test_kr_market_route_registry_refactor.py:100` 의
  `project_root_getter=lambda: "/tmp/project",` 를 지웁니다.
- `tests/app/test_kr_market_dependency_builders.py:95` 의
  `project_root_getter=lambda: ".",` 를 지웁니다.

- [ ] **5단계: 라우트 검사를 돌린다**

실행: `source venv/bin/activate && pytest tests/app/ -v -q`

기대: 전부 통과. `TypeError: unexpected keyword argument 'project_root'` 가 남아 있으면
체인 가운데 한 자리를 빠뜨린 것입니다.

## 작업 4: 남은 임포트 자리와 `NumpyEncoder` 사본 정리

**파일**
- 수정: `tests/test_grading_logic.py:1-9`
- 수정: `scripts/init_data.py:53-65`

- [ ] **1단계: 등급 판정 검사의 경로 주입을 없앤다**

바꾸기 전:

```python
import unittest
import sys
import os

# Add scripts directory to path to import init_data
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from init_data import assign_grade
```

바꾼 뒤:

```python
import unittest

from scripts.init_data import assign_grade
```

- [ ] **2단계: `NumpyEncoder` 사본을 공용 구현으로 바꾼다**

`scripts/init_data.py` 의 54~65번 줄을 지웁니다.

```python
# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)
```

그 자리에 공용 구현을 들여옵니다.

```python
from numpy_json_encoder import NumpyEncoder
```

이 임포트를 놓을 위치가 중요합니다. `numpy_json_encoder` 는 저장소 루트에 있는 최상위
모듈이고, `scripts/init_data.py` 는 78번 줄에서야 `sys.path.insert(0, BASE_DIR)` 로 루트를
경로에 넣습니다. 따라서 **그 줄 뒤에 놓습니다.** `from engine.config import config, app_config`
바로 앞자리가 같은 조건을 만족하는 자리입니다.

`cls=NumpyEncoder` 를 넘기는 다섯 자리(730, 1785, 1790, 1978, 2680번 줄)는 이름이 그대로이므로
고치지 않습니다. 이름만 같고 실체가 바뀌는 형태라서, 작업 1 의 `is` 단언이 그 교체를 검사합니다.

- [ ] **3단계: 신규 회귀 검사가 통과하는지 확인한다**

실행: `source venv/bin/activate && pytest tests/scripts/test_init_data_module_contract.py tests/test_grading_logic.py -v`

기대: 작업 1 에서 실패했던 두 검사가 이제 통과합니다. 등급 판정 검사 7건도 통과합니다.

## 작업 5: 전체 검증

- [ ] **1단계: pytest 전체를 돌린다**

실행: `source venv/bin/activate && pytest -q`

기대: 직전 사이클 기준선인 1605 통과 2 스킵에 신규 2건을 더한 수치. 스킵 수는 그대로여야
합니다.

- [ ] **2단계: 프론트엔드 검사를 돌린다**

실행: `cd frontend && npx vitest run`

기대: 37파일 237건 통과. 이번 변경은 `frontend/` 를 건드리지 않으므로 값이 달라지면 안 됩니다.

- [ ] **3단계: 이중 로드가 실제로 사라졌는지 실행 중인 앱에서 확인한다**

정적 검사는 소스에 그런 임포트가 없다는 것까지만 보장합니다. 앱이 실제로 뜬 상태에서 두 이름이
동시에 올라가지 않는지는 따로 봐야 합니다. 백엔드를 재기동한 뒤 확인합니다.

```bash
./restart_all.sh
curl -s http://localhost:5501/api/kr/data-status > /dev/null
```

그다음 `logs/backend.log` 에서 임포트 오류가 없는지 확인합니다. `ModuleNotFoundError:
No module named 'init_data'` 가 보이면 걷어내지 못한 자리가 남아 있다는 뜻입니다.

- [ ] **4단계: 리뷰를 순서대로 돌린다**

T3 이므로 `/ponytail-review` → `feature-dev:code-reviewer` → `/review` 순서입니다. 순서를
바꾸지 않습니다.

- [ ] **5단계: QA 2단계를 거친다**

실행 코드가 바뀌므로 `tier-rules.md` §1-1 의 QA 2단계를 거칩니다. 이 변경은 화면의 값을
바꾸지 않지만, 스케줄러 경로와 사용자 Gemini 재분석 경로가 살아 있는지는 화면에서 확인해야
합니다. 실측 대상 화면은 `http://localhost:3500/dashboard/kr` 입니다.

**비용이 드는 조작은 시나리오에 넣지 않습니다.** 특히 이번 변경이 지나가는 경로 가운데
`POST /api/kr/reanalyze-gemini` 는 실제 Gemini 호출을 일으키므로 누르지 않습니다. 그 경로가
살아 있는지는 라우트가 등록되었는지와 파이썬 검사로 확인합니다.

## 자체 점검

**항목 대조.** 백로그 `[INFRA-006]` 의 체크박스 여덟 개를 모두 덮는지 확인했습니다.

| 체크박스 | 덮는 작업 |
|---|---|
| 방식 확정 | 「방식 확정」 절 |
| `scheduler_jobs.py:32-36` 통일 | 작업 2 |
| `kr_market_route_service.py:142` 와 `test_grading_logic.py:9` 정리 | 작업 3, 작업 4 |
| `sys.modules` 이중 등재 확인 테스트 | 작업 1 (정적 검사로 대체) |
| `NumpyEncoder` 사본 삭제 | 작업 4 |
| `cls=NumpyEncoder` 다섯 곳 확인 | 작업 4 2단계 + 작업 1 의 `is` 단언 |
| `datetime` payload 저장 테스트 | 작업 1 |
| pytest 전체 통과 | 작업 5 |

**한 가지를 원안과 다르게 합니다.** 네 번째 체크박스는 `sys.modules` 에 두 이름이 동시에
올라가지 않음을 런타임에 확인하라고 적혀 있으나, pytest 전체 실행에서는 앞선 테스트가 남긴
`sys.modules` 상태에 결과가 좌우되어 검사가 흔들립니다. 소스에 최상위 임포트가 하나도 없으면
그 상태가 애초에 만들어질 수 없으므로 정적 검사가 더 강한 보장입니다. 이 판단을 아카이브
메모에 남깁니다.

**타입 일관성.** `_load_init_data_functions` 의 반환 타입
`dict[str, Callable[..., Any]]` 은 그대로입니다. `run_user_gemini_reanalysis` 와
`execute_user_gemini_reanalysis_request` 는 매개변수 하나씩만 줄고 반환 타입은 그대로입니다.
