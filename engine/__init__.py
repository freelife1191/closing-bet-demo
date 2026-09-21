#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine Package
"""
from .models import *
from .config import config, app_config
from .scorer import Scorer
from .position_sizer import PositionSizer
try:
    from .llm_analyzer import LLMAnalyzer
except ImportError:
    LLMAnalyzer = None
    print("Warning: LLMAnalyzer could not be imported (missing dependencies?)")
def __getattr__(name: str):
    # Leaf utilities can be imported while services are still initializing.
    if name in {"KRXCollector", "EnhancedNewsCollector"}:
        from . import collectors
        value = getattr(collectors, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'models', 'config', 'scorer', 'position_sizer', 'llm_analyzer', 'collectors',
    'config', 'app_config', 'Scorer', 'PositionSizer', 'LLMAnalyzer',
    'KRXCollector', 'EnhancedNewsCollector'
]
