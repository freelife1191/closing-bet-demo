#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 종가베팅 알림 서비스 모듈
Discord, Telegram, Slack, Email로 분석 결과를 발송합니다.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.notifier_channels import (
    send_discord_message,
    send_email_message,
    send_slack_message,
    send_telegram_message,
)
from services.notifier_formatters import format_jongga_message

logger = logging.getLogger(__name__)


class NotificationService:
    """메신저 알림 서비스 퍼사드"""

    def __init__(self) -> None:
        self.enabled = os.getenv("NOTIFICATION_ENABLED", "false").lower() == "true"
        self.channels = [
            channel.strip()
            for channel in os.getenv("NOTIFICATION_CHANNELS", "").split(",")
            if channel.strip()
        ]

        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")

        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.email_recipients = [
            recipient.strip()
            for recipient in os.getenv("EMAIL_RECIPIENTS", "").split(",")
            if recipient.strip()
        ]

    def format_jongga_message(
        self,
        signals: list[dict[str, Any]],
        date_str: str | None = None,
    ) -> str:
        """종가베팅 분석 결과를 메시지 포맷으로 변환한다."""
        return format_jongga_message(signals=signals, date_str=date_str)

    def send_all(
        self,
        signals: list[dict[str, Any]],
        date_str: str | None = None,
    ) -> dict[str, bool]:
        """설정된 모든 채널로 알림을 발송한다."""
        if not self.enabled:
            logger.info("[Notifier] 알림이 비활성화되어 있습니다.")
            return {}

        if not signals:
            logger.info("[Notifier] 발송할 신호가 없습니다.")
            return {}

        message = self.format_jongga_message(signals, date_str)
        results: dict[str, bool] = {}
        for raw_channel in self.channels:
            channel = raw_channel.lower()
            try:
                if channel == "discord":
                    results["discord"] = self.send_discord(message)
                elif channel == "telegram":
                    results["telegram"] = self.send_telegram(message)
                elif channel == "slack":
                    results["slack"] = self.send_slack(message)
                elif channel == "email":
                    results["email"] = self.send_email(message, date_str)
                else:
                    logger.warning(f"[Notifier] 알 수 없는 채널: {channel}")
            except Exception as e:
                logger.error(f"[Notifier] {channel} 발송 실패: {e}")
                results[channel] = False

        return results

    def send_discord(self, message: str) -> bool:
        """Discord 웹훅으로 메시지를 발송한다."""
        return send_discord_message(
            webhook_url=self.discord_webhook_url,
            message=message,
            logger=logger,
        )

    def send_telegram(self, message: str) -> bool:
        """Telegram 봇으로 메시지를 발송한다."""
        return send_telegram_message(
            bot_token=self.telegram_bot_token,
            chat_id=self.telegram_chat_id,
            message=message,
            logger=logger,
        )

    def send_slack(self, message: str) -> bool:
        """Slack 웹훅으로 메시지를 발송한다."""
        return send_slack_message(
            webhook_url=self.slack_webhook_url,
            message=message,
            logger=logger,
        )

    def send_email(self, message: str, date_str: str | None = None) -> bool:
        """이메일로 메시지를 발송한다."""
        return send_email_message(
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_user=self.smtp_user,
            smtp_password=self.smtp_password,
            email_recipients=self.email_recipients,
            message=message,
            logger=logger,
            date_str=date_str,
        )


def send_jongga_notification(
    signals: list[dict[str, Any]],
    date_str: str | None = None,
) -> dict[str, bool]:
    """종가베팅 알림 발송 편의 함수."""
    notifier = NotificationService()
    return notifier.send_all(signals, date_str)
