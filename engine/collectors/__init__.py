#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수집기의 단일 공개 진입점."""
from engine.collectors.krx import KRXCollector
from engine.collectors.naver import NaverFinanceCollector
from engine.collectors.news import EnhancedNewsCollector

__all__ = ["KRXCollector", "NaverFinanceCollector", "EnhancedNewsCollector"]
