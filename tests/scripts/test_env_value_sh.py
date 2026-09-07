#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[INFRA-049] 기동 스크립트가 .env 를 셸로 실행하지 않는지 검사한다."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_VALUE_SH = _REPO_ROOT / "scripts" / "env_value.sh"

# 셸에서 명령이 시작될 수 있는 자리만 앵커로 삼는다. 행 앞만 묶으면 걷어낸 옛 코드를
# 놓친다. `[ -f .env ] && { echo "..."; set -a; source .env; set +a; }` 한 줄에서는
# source 와 set -a 가 모두 행 중간에 있기 때문이다. 오류 메시지 안의 「아니다. .env 의」
# 같은 문장이 걸리지 않는 것도 이 앵커 덕분이다.
_CMD_START = r"(?:^|[;&|(){}]|&&|\|\|)\s*"
_SOURCES_ENV = re.compile(_CMD_START + r"(?:source|\.)\s+\S*\.env\b", re.M)
_EXPORTS_ALL = re.compile(_CMD_START + r"set\s+(?:-a\b|-o\s+allexport\b)", re.M)


def _code_only(text: str) -> str:
    """주석을 걷어낸다. env_value.sh 의 주석이 옛 방식을 설명하며 같은 문구를 담는다."""
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _run(cwd: Path, snippet: str, *args: str, env: dict | None = None):
    """env_value.sh 를 source 한 bash 에서 snippet 을 돌린다."""
    return subprocess.run(
        ["bash", "-c", f'source "{_ENV_VALUE_SH}"; {snippet}', "_", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _env_value(cwd: Path, key: str) -> str:
    result = _run(cwd, 'env_value "$1"', key)
    assert result.returncode == 0, result.stderr
    return result.stdout.rstrip("\n")


def test_env_value_does_not_execute_shell_syntax(tmp_path: Path):
    """[INFRA-049] 값 안의 명령 치환·백틱·세미콜론·공백이 실행되지 않는다.

    `set -a; source .env` 는 대입의 오른쪽을 평가하므로 이 넷이 모두 명령이 되었다.
    설정 화면으로 저장할 수 있는 열두 키의 값이 그대로 이 자리에 온다.
    """
    (tmp_path / ".env").write_text(
        "SMTP_HOST=x$(touch pwned_subst)\n"
        "SMTP_USER=y`touch pwned_backtick`\n"
        "SMTP_PASSWORD=z; touch pwned_semi\n"
        "TELEGRAM_CHAT_ID=w touch pwned_space\n",
        encoding="utf-8",
    )

    assert _env_value(tmp_path, "SMTP_HOST") == "x$(touch pwned_subst)"
    assert _env_value(tmp_path, "SMTP_USER") == "y`touch pwned_backtick`"
    assert _env_value(tmp_path, "SMTP_PASSWORD") == "z; touch pwned_semi"
    assert _env_value(tmp_path, "TELEGRAM_CHAT_ID") == "w touch pwned_space"
    # 값이 리터럴로 돌아오는 것과 명령이 돌지 않은 것은 다른 보장이다. 둘 다 잰다.
    assert sorted(p.name for p in tmp_path.glob("pwned_*")) == []


def test_env_value_does_not_strip_quotes_or_inline_comments(tmp_path: Path):
    """[INFRA-049] 이 함수는 dotenv 가 아니다. 벗기지 않는 것을 명시해 둔다.

    `source` 와 python-dotenv 는 따옴표와 인라인 주석을 벗기지만 이 함수는 벗기지
    않는다. 지금 세 키가 그 모양이 아니라서 문제가 없을 뿐이다. 이 저장소의 `.env` 는
    159줄 가운데 21줄이 `KEY=값  # 설명` 모양이므로 언젠가 그 모양이 될 수 있다.
    포트는 env_port 가 막고, 나머지는 이 검사가 한계를 드러낸다.
    """
    (tmp_path / ".env").write_text(
        'QUOTED="5501"\n'
        "COMMENTED=5501 # 백엔드 포트\n"
        "export EXPORTED=ok\n",
        encoding="utf-8",
    )

    assert _env_value(tmp_path, "QUOTED") == '"5501"'
    assert _env_value(tmp_path, "COMMENTED") == "5501 # 백엔드 포트"
    assert _env_value(tmp_path, "EXPORTED") == ""


def test_env_value_takes_last_duplicate(tmp_path: Path):
    """[INFRA-049] 중복 줄에서 나중 것이 이긴다.

    bash 의 source, python-dotenv 의 dotenv_values, @next/env 가 모두 그렇게 읽는다.
    `tail -1` 이 사라지면 세 파서와 어긋나므로 여기서 잡는다.
    """
    (tmp_path / ".env").write_text("FLASK_PORT=1111\nFLASK_PORT=2222\n", encoding="utf-8")

    assert _env_value(tmp_path, "FLASK_PORT") == "2222"


def test_env_value_is_empty_without_env_file(tmp_path: Path):
    """[INFRA-049] .env 가 없으면 빈 값을 주고, 호출자의 기본값이 걸린다."""
    assert _env_value(tmp_path, "FLASK_PORT") == ""


def test_env_port_rejects_non_numeric_value(tmp_path: Path):
    """[INFRA-049] 포트가 숫자가 아니면 기동을 멈춘다.

    stop_all.sh 38행의 `lsof -ti :$port` 는 값을 인용하지 않는다. 값이
    `5501 # 백엔드 포트` 가 되면 단어 분리로 lsof 가 아무것도 못 찾고, 58행의 최종
    확인까지 함께 실패해 포트가 살아 있는데 「✅ Port freed」를 출력한다. 그 조용한
    거짓 성공을 여기서 막는다.
    """
    (tmp_path / ".env").write_text("FLASK_PORT=5501 # 백엔드 포트\n", encoding="utf-8")

    result = _run(tmp_path, 'env_port "$1" "$2"', "FLASK_PORT", "5501")
    assert result.returncode != 0
    assert result.stdout == ""
    assert "FLASK_PORT" in result.stderr


def test_env_port_prefers_env_file_then_inherited_then_default(tmp_path: Path):
    """[INFRA-049] `.env` > 상속 > 기본값 순서가 현행 source 방식과 같다.

    거부만 재면 전부 거부하는 코드도 위 검사를 통과하므로 통과 경로를 함께 잰다.
    `set -a; source .env` 는 `.env` 에 키가 없을 때 아무것도 덮어쓰지 않으므로 호출자가
    export 한 값이 살아남는다. `VAR=$(env_value VAR)` 로 무조건 덮어쓰면 그 순서가
    조용히 깨지므로 세 경우를 모두 잰다.
    """
    inherited = {"PATH": "/usr/bin:/bin", "FRONTEND_PORT": "4000"}
    bare = {"PATH": "/usr/bin:/bin"}
    call = ('env_port "$1" "$2"', "FRONTEND_PORT", "9999")

    # (1) .env 에 있으면 .env 가 이긴다
    (tmp_path / ".env").write_text("FRONTEND_PORT=3500\n", encoding="utf-8")
    result = _run(tmp_path, *call, env=inherited)
    assert result.stdout == "3500", result.stderr

    # (2) .env 에 없으면 상속받은 값이 산다
    (tmp_path / ".env").write_text("OTHER=x\n", encoding="utf-8")
    result = _run(tmp_path, *call, env=inherited)
    assert result.stdout == "4000", result.stderr

    # (3) 둘 다 없으면 코드 기본값
    result = _run(tmp_path, *call, env=bare)
    assert result.stdout == "9999", result.stderr


def test_env_value_matches_dotenv_for_startup_keys():
    """[INFRA-049] 저장소의 실제 .env 에서 세 키가 python-dotenv 와 같은 값이다.

    이 검사만 실제 .env 를 읽는다. 값은 비교만 하고 출력하지 않는다. 두 스크립트가
    쓰는 값이 Flask·Next 가 읽는 값과 갈리면 바인딩 주소가 서로 달라진다. 위의
    한계 검사가 보여 주듯 이 일치는 값의 모양에 달려 있으므로 실제 파일로 잰다.
    """
    from dotenv import dotenv_values

    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        pytest.skip(".env 가 없는 환경")

    # dotenv_values 의 반환값을 이름 붙은 지역 변수로 붙들지 않는다. `pytest -l` 은 실패
    # 시 지역 변수를 덤프하므로 .env 의 모든 키와 값이 출력에 실린다. 임시 객체는 덤프
    # 대상이 아니다. 키가 셋뿐이라 세 번 파싱해도 값이 무시할 만하다.
    for key in ("FLASK_PORT", "FRONTEND_PORT", "FLASK_HOST"):
        # 두 값을 직접 비교하는 어서트를 쓰면 실패할 때 pytest 가 양쪽 값을 출력에
        # 그대로 남긴다. 불리언 하나만 단언해 그 경로를 막는다.
        same = _env_value(_REPO_ROOT, key) == (dotenv_values(env_path).get(key) or "")
        assert same, f"{key} 가 python-dotenv 와 다른 값을 준다 (값은 출력하지 않는다)"



def test_startup_scripts_do_not_source_env():
    """[INFRA-049] 기동 스크립트가 .env 를 셸로 실행하지 않는다.

    함수를 만들어 두어도 옛 줄이 남아 있으면 아무것도 달라지지 않는다. 되살아나는
    것을 막는 자리가 여기다. 부분 문자열 대신 정규식을 쓰는 이유는 `. .env` 와
    `source "$PROJECT_ROOT/.env"` 도 같은 일을 하기 때문이다. env_value.sh 자신도
    검사 대상에 넣는다. 그 파일의 주석이 옛 방식을 설명하면서 같은 문구를 담지만,
    정규식이 행 앞을 묶으므로 주석 줄에는 걸리지 않는다.
    """
    for name in ("restart_all.sh", "stop_all.sh", "scripts/env_value.sh"):
        code = _code_only((_REPO_ROOT / name).read_text(encoding="utf-8"))
        assert not _SOURCES_ENV.search(code), f"{name} 이 .env 를 source 한다"
        assert not _EXPORTS_ALL.search(code), f"{name} 에 .env 를 export 하던 자리가 남아 있다"


def test_regression_regex_catches_the_line_it_replaced():
    r"""[INFRA-049] 회귀 검사가 자기가 걷어낸 바로 그 표기를 잡는지 잰다.

    처음 쓴 정규식은 행 앞만 묶어서, 옛 `restart_all.sh:11` 의 한 줄 형태를 놓쳤다.
    검사가 통과하면서도 아무것도 막지 못하는 상태였다. 보안 리뷰가 실측으로 찾았다.
    잡지 못하는 표기(`eval "$(cat .env)"`, 변수 경유 `source "$ENV_FILE"`)는 아래에
    적어 둔다. 후자까지 잡으려면 `\S+` 로 넓혀야 하는데 그러면 이 항목이 새로 넣은
    `source "$PROJECT_ROOT/scripts/env_value.sh"` 자신이 걸린다.
    """
    caught = (
        '[ -f .env ] && { echo "x"; set -a; source .env; set +a; }',  # 옛 restart_all.sh
        "set -a\nsource .env\nset +a",  # 옛 stop_all.sh
        "set -o allexport\n. ./.env\nset +o allexport",
        'source "$PROJECT_ROOT/.env"',
        ". .env",
        "[ -f .env ] && source .env",
    )
    for text in caught:
        code = _code_only(text)
        assert _SOURCES_ENV.search(code) or _EXPORTS_ALL.search(code), f"놓친다: {text!r}"

    # 오탐이 없어야 하는 표기. 이번 변경이 실제로 담고 있는 줄들이다.
    clean = (
        'echo "❌ $1 의 값이 숫자가 아니다. .env 의 해당 줄을 확인하라" >&2',
        'source "$PROJECT_ROOT/scripts/env_value.sh"',
        "source venv/bin/activate",
        "ln -sf ../.env frontend/.env",
        '[ -f .env ] || return 0',
        'sed -n "s/^$1=//p" .env | tail -1',
    )
    for text in clean:
        code = _code_only(text)
        assert not _SOURCES_ENV.search(code) and not _EXPORTS_ALL.search(code), f"오탐: {text!r}"


def test_env_value_rejects_key_names_with_shell_metacharacters(tmp_path: Path):
    """[INFRA-049] 키 이름이 sed 코드와 간접 확장 이름으로 들어가는 자리를 막는다.

    GNU sed 의 `s///e` 는 치환 결과를 셸에 넘기고, bash 의 간접 확장은 이름 안의 배열
    첨자를 산술 평가한다. 후자는 이 머신의 bash 3.2 와 5.x 양쪽에서 실제로 명령이
    실행되는 것을 확인했다. 호출자가 리터럴 세 개만 넘기는 지금은 닿지 않지만, 이
    항목이 고치는 결함이 바로 그 성격이다.
    """
    (tmp_path / ".env").write_text("FLASK_PORT=5501\n", encoding="utf-8")

    for fn in ("env_value", "env_port"):
        result = _run(tmp_path, f'{fn} "$1" 5501', "a[$(touch pwned_key)]")
        assert result.returncode != 0, f"{fn} 이 잘못된 키를 받아들인다"
    assert not (tmp_path / "pwned_key").exists()

    # 전부 거부하는 코드도 위를 통과하므로 정상 키가 지나가는 것을 함께 잰다.
    assert _env_value(tmp_path, "FLASK_PORT") == "5501"
