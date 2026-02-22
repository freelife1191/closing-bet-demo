#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Messenger Senders
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from engine.messenger_config import MessengerConfig
from engine.messenger_formatters import (
    DiscordFormatter,
    EmailFormatter,
    MessageData,
    TelegramFormatter,
)


logger = logging.getLogger(__name__)


class MessageSender:
    """메시지 발송 기본 클래스"""

    def __init__(self, config: MessengerConfig):
        self.config = config

    def send(self, data: MessageData) -> bool:
        raise NotImplementedError


class TelegramSender(MessageSender):
    """텔레그램 발송기"""

    def __init__(self, config: MessengerConfig):
        super().__init__(config)
        self.formatter = TelegramFormatter()

    def send(self, data: MessageData) -> bool:
        if not self.config.telegram_token or not self.config.telegram_chat_id:
            logger.warning("Telegram 설정이 누락되어 발송을 건너뜁니다.")
            return False

        try:
            message_text = self.formatter.format(data)
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }

            resp = requests.post(url, json=payload)
            if not resp.ok:
                logger.error(f"Telegram 발송 실패 결과: {resp.text}")
                return False

            logger.info("Telegram 알림 발송 성공")
            return True
        except Exception as e:
            logger.error(f"Telegram 발송 중 오류: {e}")
            return False


class DiscordSender(MessageSender):
    """디스코드 발송기"""

    def __init__(self, config: MessengerConfig):
        super().__init__(config)
        self.formatter = DiscordFormatter()

    def send(self, data: MessageData) -> bool:
        if not self.config.discord_url:
            logger.warning("Discord 설정이 누락되어 발송을 건너뜁니다.")
            return False

        try:
            payload = self.formatter.format(data)
            resp = requests.post(self.config.discord_url, json=payload)
            if not resp.ok:
                logger.error(f"Discord 발송 실패 결과: {resp.text}")
                return False

            logger.info("Discord 알림 발송 성공")
            return True
        except Exception as e:
            logger.error(f"Discord 발송 중 오류: {e}")
            return False


class EmailSender(MessageSender):
    """이메일 발송기"""

    def __init__(self, config: MessengerConfig):
        super().__init__(config)
        self.formatter = EmailFormatter()

    def send(self, data: MessageData) -> bool:
        if not self.config.smtp_user or not self.config.smtp_password:
            logger.warning("SMTP 설정이 누락되어 발송을 건너뜁니다.")
            return False

        if not self.config.email_recipients:
            logger.warning("수신자 이메일(EMAIL_RECIPIENTS)이 설정되지 않았습니다.")
            return False

        try:
            html_body = self.formatter.format(data)

            msg = MIMEMultipart()
            msg["From"] = self.config.smtp_user
            msg["To"] = ", ".join(self.config.email_recipients)
            msg["Subject"] = data.title
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logger.info(f"이메일 발송 성공: {', '.join(self.config.email_recipients)}")
            return True
        except Exception as e:
            logger.error(f"이메일 발송 중 오류: {e}")
            return False


__all__ = [
    "MessageSender",
    "TelegramSender",
    "DiscordSender",
    "EmailSender",
]
