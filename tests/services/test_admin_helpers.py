#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""관리자 판정이 타입스크립트 쪽과 같은 답을 내는지 잰다([INFRA-042]).

같은 규칙이 services/admin_helpers.py 와 frontend/src/lib/adminEmails.ts 에 두 벌 있다.
한쪽만 고치면 같은 사용자가 한 게이트는 통과하고 다른 게이트는 막힌다. 두 검사가 같은
JSON 을 읽으므로 어느 쪽을 고쳐도 반대쪽이 실패한다.

짝은 frontend/src/lib/adminEmails.test.ts 다.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.admin_helpers import is_admin_email

CASES_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "admin_email_cases.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["why"] for c in CASES])
def test_shared_admin_email_cases(case, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", case["list"])
    # `is` 가 아니라 `==` 를 쓴다. 지금 구현은 `in` 의 결과를 그대로 돌려주어 진짜 bool
    # 이지만, 나중에 truthy 한 비 bool 을 돌려주게 바뀌면 구현이 옳아도 `is` 가 실패한다.
    assert is_admin_email(case["email"]) == case["expected"], case["why"]


def test_case_file_is_not_empty():
    """목록이 비면 위 검사가 0건으로 통과한다. 그 상태를 통과로 보지 않는다."""
    assert len(CASES) >= 10
