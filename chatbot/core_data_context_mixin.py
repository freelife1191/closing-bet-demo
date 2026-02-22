#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRStockChatbot 데이터/컨텍스트/페이로드 통합 믹스인.
"""

from __future__ import annotations

from .core_data_access_mixin import CoreDataAccessMixin
from .core_intent_context_mixin import CoreIntentContextMixin
from .core_payload_mixin import CorePayloadMixin


class CoreDataContextMixin(
    CoreDataAccessMixin,
    CoreIntentContextMixin,
    CorePayloadMixin,
):
    """`KRStockChatbot`의 데이터 접근/의도 컨텍스트/페이로드 구성 통합 믹스인."""

