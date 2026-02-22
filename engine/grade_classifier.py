#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grade Classifier Facade Module
"""

from __future__ import annotations

from engine.config import SignalConfig
from engine.grade_decider import GradeClassifier
from engine.grade_filter_validator import FilterResult, FilterValidator


def create_filter_validator(config: SignalConfig = None) -> FilterValidator:
    """FilterValidator 인스턴스 생성 (Convenience Factory)."""
    return FilterValidator(config)


def create_grade_classifier(config: SignalConfig = None) -> GradeClassifier:
    """GradeClassifier 인스턴스 생성 (Convenience Factory)."""
    return GradeClassifier(config)


__all__ = [
    "FilterResult",
    "FilterValidator",
    "GradeClassifier",
    "create_filter_validator",
    "create_grade_classifier",
]

