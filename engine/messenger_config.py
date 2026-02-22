#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Messenger Config
"""

import logging
import os


logger = logging.getLogger(__name__)


class MessengerConfig:
    """메신저 설정"""

    def __init__(self):
        channels_str = os.getenv("NOTIFICATION_CHANNELS", "discord")
        self.channels = [c.strip().lower() for c in channels_str.split(",")]

        self.disabled = os.getenv("NOTIFICATION_ENABLED", "true").lower() != "true"

        # Discord Config
        self.discord_url = os.getenv("DISCORD_WEBHOOK_URL")

        # Telegram Config
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # Email Config
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = self._safe_int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_recipients = [
            e.strip() for e in os.getenv("EMAIL_RECIPIENTS", "").split(",") if e.strip()
        ]

        if not any([self.telegram_token, self.discord_url, self.smtp_user]):
            logger.warning(
                "[Messenger] 개인 알림 설정이 감지되지 않았습니다. "
                "알림 발송이 동작하지 않을 수 있습니다."
            )

    @staticmethod
    def _safe_int(val: str) -> int:
        """안전한 정수 변환"""
        try:
            return int(val)
        except (TypeError, ValueError):
            return 587


__all__ = ["MessengerConfig"]
