#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 종가베팅 알림 채널 전송 헬퍼
"""

from __future__ import annotations

import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def _chunk_message(message: str, chunk_size: int = 1900) -> list[str]:
    return [message[i : i + chunk_size] for i in range(0, len(message), chunk_size)] or [""]


def send_discord_message(webhook_url: str, message: str, logger: logging.Logger) -> bool:
    """Discord 웹훅으로 메시지를 발송한다."""
    if not webhook_url:
        logger.warning("[Notifier] Discord 웹훅 URL이 설정되지 않았습니다.")
        return False

    try:
        chunks = _chunk_message(message, chunk_size=1900)
        chunk_count = len(chunks)

        for idx, chunk in enumerate(chunks):
            response = requests.post(
                webhook_url,
                json={"content": chunk},
                timeout=10,
            )
            response.raise_for_status()
            if chunk_count > 1 and idx < chunk_count - 1:
                time.sleep(0.5)

        logger.info("[Notifier] Discord 발송 성공")
        return True
    except Exception as e:
        logger.error(f"[Notifier] Discord 발송 실패: {e}")
        return False


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    message: str,
    logger: logging.Logger,
) -> bool:
    """Telegram 봇으로 메시지를 발송한다."""
    if not bot_token or not chat_id:
        logger.warning("[Notifier] Telegram 설정이 불완전합니다.")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("[Notifier] Telegram 발송 성공")
        return True
    except Exception as e:
        logger.error(f"[Notifier] Telegram 발송 실패: {e}")
        return False


def send_slack_message(webhook_url: str, message: str, logger: logging.Logger) -> bool:
    """Slack 웹훅으로 메시지를 발송한다."""
    if not webhook_url:
        logger.warning("[Notifier] Slack 웹훅 URL이 설정되지 않았습니다.")
        return False

    try:
        response = requests.post(
            webhook_url,
            json={"text": message},
            timeout=10,
        )
        response.raise_for_status()
        logger.info("[Notifier] Slack 발송 성공")
        return True
    except Exception as e:
        logger.error(f"[Notifier] Slack 발송 실패: {e}")
        return False


def send_email_message(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    email_recipients: list[str],
    message: str,
    logger: logging.Logger,
    date_str: str | None = None,
) -> bool:
    """이메일로 메시지를 발송한다."""
    if not smtp_user or not smtp_password or not email_recipients:
        logger.warning("[Notifier] 이메일 설정이 불완전합니다.")
        return False

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = ", ".join(email_recipients)
        msg["Subject"] = f"📊 종가베팅 알림 ({date_str})"

        html_message = message.replace("\n", "<br>")
        msg.attach(MIMEText(f"<pre style='font-family: monospace;'>{html_message}</pre>", "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info("[Notifier] 이메일 발송 성공")
        return True
    except Exception as e:
        logger.error(f"[Notifier] 이메일 발송 실패: {e}")
        return False
