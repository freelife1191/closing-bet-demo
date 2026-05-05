#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Helpers

ADMIN_EMAILS 환경변수 기반 관리자 판별 유틸리티.
"""

from __future__ import annotations

import os


def get_admin_emails() -> list[str]:
    raw = os.environ.get("ADMIN_EMAILS", "")
    return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]


def is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    normalized = str(email).strip().lower()
    if not normalized or normalized == "user@example.com":
        return False
    return normalized in get_admin_emails()
