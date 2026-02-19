#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


KIT_ROOT = Path(__file__).resolve().parents[2]


def load_validator_module() -> ModuleType:
    module_path = KIT_ROOT / "scripts" / "video" / "validate_script_terminology.py"
    assert module_path.exists(), "validator script missing"

    spec = importlib.util.spec_from_file_location("validate_script_terminology", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_validator_exposes_main_entrypoint() -> None:
    module = load_validator_module()
    assert hasattr(module, "main")
    assert hasattr(module, "validate_fragments")


def test_validator_reports_brand_forbidden_and_ui_term_rules() -> None:
    module = load_validator_module()

    fragments = [
        {"scene_id": "S01", "field": "narration_ko", "text": "첫 장면에서는 KR 마켓 패키지를 소개합니다."},
        {"scene_id": "S03", "field": "narration_ko", "text": "이 장면은 분석에 출발점인 마켓 게이를 소개합니다."},
        {"scene_id": "S03", "field": "must_show_ui", "text": "마켓 게이트 상태"},
    ]

    findings = module.validate_fragments(
        fragments=fragments,
        required_brand="Smart Money Bot",
        forbidden_phrases=["마켓 게이"],
        ui_alias_map={"마켓 게이트": "Market Gate"},
    )

    rule_ids = {item["rule_id"] for item in findings}
    assert "brand_name_exact" in rule_ids
    assert "forbidden_phrase" in rule_ids
    assert "ui_term_exact" in rule_ids


def test_validator_reports_missing_required_terms() -> None:
    module = load_validator_module()

    findings = module.validate_fragments(
        fragments=[{"scene_id": "S01", "field": "narration_ko", "text": "시나리오 소개 문장"}],
        required_brand="Smart Money Bot",
        forbidden_phrases=[],
        ui_alias_map={},
        required_terms=["Market Gate", "VCP"],
    )
    rule_ids = {item["rule_id"] for item in findings}

    assert "required_term_exact" in rule_ids


def test_validator_writes_report_with_scene_and_rule_metadata(tmp_path: Path) -> None:
    module = load_validator_module()

    report_json = tmp_path / "term_validation_manifest.json"
    report_md = tmp_path / "term_validation_manifest.md"
    findings = [
        {
            "severity": "ERROR",
            "rule_id": "forbidden_phrase",
            "scene_id": "S03",
            "offending_text": "마켓 게이",
            "expected": "Market Gate",
            "suggestion": "영어 원문 사용",
        }
    ]

    module.write_report(report_json, report_md, findings)
    payload = json.loads(report_json.read_text(encoding="utf-8"))

    assert payload["status"] == "fail"
    assert payload["summary"]["errorCount"] == 1
    assert payload["findings"][0]["scene_id"] == "S03"
    assert report_md.exists()
