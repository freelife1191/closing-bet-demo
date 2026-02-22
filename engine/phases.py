#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Signal Generation Phases

Backwards-compatible facade that re-exports phase classes.
"""

from engine.phases_analysis import Phase1Analyzer, Phase4SignalFinalizer
from engine.phases_base import BasePhase
from engine.phases_news_llm import Phase2NewsCollector, Phase3LLMAnalyzer
from engine.phases_pipeline import SignalGenerationPipeline

__all__ = [
    'BasePhase',
    'Phase1Analyzer',
    'Phase2NewsCollector',
    'Phase3LLMAnalyzer',
    'Phase4SignalFinalizer',
    'SignalGenerationPipeline',
]
