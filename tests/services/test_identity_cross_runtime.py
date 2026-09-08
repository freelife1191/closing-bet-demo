#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TypeScript signer와 Python verifier 사이의 v2 wire 계약 테스트."""

from __future__ import annotations

import hmac
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "identity_v2_vectors.json"
IDENTITY_SOURCE_PATH = REPO_ROOT / "frontend" / "src" / "lib" / "identity.ts"
TYPESCRIPT_PATH = REPO_ROOT / "frontend" / "node_modules" / "typescript"

sys.path.insert(0, str(REPO_ROOT))

from services.identity_helpers import verify_identity_header


NODE_SIGNER_RUNNER = r"""
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const identitySourcePath = process.argv[1];
const typescriptPath = process.argv[2];
const fixturePath = process.argv[3];
const ts = require(typescriptPath);
const source = fs.readFileSync(identitySourcePath, 'utf8');
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: identitySourcePath,
});
const identityModule = new Module(identitySourcePath, module);
identityModule.filename = identitySourcePath;
identityModule.paths = Module._nodeModulePaths(path.dirname(identitySourcePath));
identityModule._compile(transpiled.outputText, identitySourcePath);

const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const headers = Object.fromEntries(fixture.vectors.map((vector) => [
  vector.id,
  identityModule.exports.signIdentity(
    vector.email,
    fixture.secret,
    vector.expires_at,
    vector.signer_method || vector.method,
    vector.path,
  ),
]));
process.stdout.write(JSON.stringify(headers));
"""


@pytest.fixture(scope="module")
def identity_vectors() -> dict[str, Any]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


@pytest.fixture(scope="module")
def typescript_headers(identity_vectors: dict[str, Any]) -> dict[str, str]:
    """설치된 TypeScript로 실제 signer 모듈을 메모리에서 실행한다."""
    node_env = os.environ.copy()
    node_env.pop("OMX_ROOT", None)
    node_env.pop("STATE_ROOT", None)
    try:
        try:
            result = subprocess.run(
                [
                    "node",
                    "-e",
                    NODE_SIGNER_RUNNER,
                    str(IDENTITY_SOURCE_PATH),
                    str(TYPESCRIPT_PATH),
                    str(FIXTURE_PATH),
                ],
                capture_output=True,
                check=False,
                env=node_env,
                text=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired:
            pytest.fail("TypeScript signer 실행이 20초 안에 끝나지 않았습니다", pytrace=False)
    finally:
        node_env.clear()

    if result.returncode != 0:
        pytest.fail("TypeScript signer subprocess 실행에 실패했습니다", pytrace=False)
    try:
        headers = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail("TypeScript signer가 JSON 결과를 내지 않았습니다", pytrace=False)
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in headers.items()
    ):
        pytest.fail("TypeScript signer 결과 형식이 올바르지 않습니다", pytrace=False)
    expected_ids = {vector["id"] for vector in identity_vectors["vectors"]}
    if set(headers) != expected_ids:
        pytest.fail("TypeScript signer 결과의 vector 집합이 올바르지 않습니다", pytrace=False)
    return headers


def test_fixed_vectors_encode_wire_payload_as_ascii(
    identity_vectors: dict[str, Any],
) -> None:
    valid_payloads = [
        vector["payload"].split(".")
        == [
            "v2",
            vector["encoded_email"],
            str(vector["expires_at"]),
            vector["method"],
            vector["encoded_path"],
        ]
        and vector["payload"].isascii()
        and vector["encoded_path"].isascii()
        and "=" not in vector["encoded_path"]
        for vector in identity_vectors["vectors"]
    ]

    assert all(valid_payloads)


def test_typescript_signer_matches_fixed_known_answers(
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    matches = [
        hmac.compare_digest(typescript_headers[vector["id"]], vector["header"])
        for vector in identity_vectors["vectors"]
    ]

    assert all(matches)


def test_python_verifier_accepts_headers_created_by_typescript(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    accepted = [
        verify_identity_header(
            typescript_headers[vector["id"]],
            now=vector["expires_at"],
            method=vector.get("signer_method", vector["method"]),
            path=vector["path"],
        )
        == vector["email"]
        for vector in identity_vectors["vectors"]
    ]

    assert all(accepted)


def test_python_verifier_rejects_typescript_headers_replayed_with_another_method(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    rejected = [
        verify_identity_header(
            typescript_headers[vector["id"]],
            now=vector["expires_at"],
            method=vector["replay_method"],
            path=vector["path"],
        )
        is None
        for vector in identity_vectors["vectors"]
    ]

    assert all(rejected)


def test_python_verifier_rejects_typescript_headers_replayed_on_another_path(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    rejected = [
        verify_identity_header(
            typescript_headers[vector["id"]],
            now=vector["expires_at"],
            method=vector["method"],
            path=vector["replay_path"],
        )
        is None
        for vector in identity_vectors["vectors"]
    ]

    assert all(rejected)


def test_python_verifier_does_not_decode_percent_sequences_again(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    vector = next(
        item
        for item in identity_vectors["vectors"]
        if item["id"] == "post_unicode_email_percent_literal"
    )
    header = typescript_headers[vector["id"]]

    exact_path_accepted = verify_identity_header(
        header,
        now=vector["expires_at"],
        method=vector["method"],
        path="/api/한글/%2F",
    ) == vector["email"]
    decoded_again_rejected = verify_identity_header(
        header,
        now=vector["expires_at"],
        method=vector["method"],
        path="/api/한글//",
    ) is None

    assert exact_path_accepted and decoded_again_rejected


def test_typescript_signer_distinguishes_trailing_slash(
    typescript_headers: dict[str, str],
) -> None:
    with_slash = typescript_headers["head_tail_with_slash"]
    without_slash = typescript_headers["head_tail_without_slash"]

    assert not hmac.compare_digest(with_slash, without_slash)


def test_python_verifier_rejects_legacy_version_with_v2_counterproof(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    vector = identity_vectors["vectors"][0]

    legacy_rejected = verify_identity_header(
        vector["legacy_header"],
        now=vector["expires_at"],
        method=vector["method"],
        path=vector["path"],
    ) is None
    v2_accepted = verify_identity_header(
        typescript_headers[vector["id"]],
        now=vector["expires_at"],
        method=vector["method"],
        path=vector["path"],
    ) == vector["email"]

    assert legacy_rejected and v2_accepted


def test_python_verifier_rejects_unknown_version_with_v2_counterproof(
    monkeypatch: pytest.MonkeyPatch,
    identity_vectors: dict[str, Any],
    typescript_headers: dict[str, str],
) -> None:
    monkeypatch.setenv("INTERNAL_IDENTITY_SECRET", identity_vectors["secret"])
    vector = identity_vectors["vectors"][0]

    unknown_rejected = verify_identity_header(
        vector["unknown_version_header"],
        now=vector["expires_at"],
        method=vector["method"],
        path=vector["path"],
    ) is None
    v2_accepted = verify_identity_header(
        typescript_headers[vector["id"]],
        now=vector["expires_at"],
        method=vector["method"],
        path=vector["path"],
    ) == vector["email"]

    assert unknown_rejected and v2_accepted
