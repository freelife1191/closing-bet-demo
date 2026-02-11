#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Messenger (Refactored)

메신저 알림 발송 클래스 (Discord, Telegram, Email)
포맷팅 로직은 messenger_formatters.py로 분리되었습니다.

Created: 2024-12-01
Refactored: 2025-02-11 (Phase 4)
"""
import os
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from typing import Optional, List

from engine.messenger_formatters import (
    MessageData,
    MessageDataBuilder,
    TelegramFormatter,
    DiscordFormatter,
    EmailFormatter,
)

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================
class MessengerConfig:
    """메신저 설정"""

    def __init__(self):
        # 환경변수 로드
        channels_str = os.getenv('NOTIFICATION_CHANNELS', 'discord')
        self.channels = [c.strip().lower() for c in channels_str.split(',')]

        self.disabled = os.getenv('NOTIFICATION_ENABLED', 'true').lower() != 'true'

        # Discord Config
        self.discord_url = os.getenv('DISCORD_WEBHOOK_URL')

        # Telegram Config
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Email Config
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = self._safe_int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_recipients = [
            e.strip() for e in os.getenv('EMAIL_RECIPIENTS', '').split(',')
            if e.strip()
        ]

        # 개인 설정 확인
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
        except:
            return 587


# =============================================================================
# Senders (Strategy Pattern for Message Sending)
# =============================================================================
class MessageSender:
    """메시지 발송 기본 클래스"""

    def __init__(self, config: MessengerConfig):
        self.config = config

    def send(self, data: MessageData) -> bool:
        """메시지 발송 (서브클래스에서 구현)"""
        raise NotImplementedError


class TelegramSender(MessageSender):
    """텔레그램 발송기"""

    def __init__(self, config: MessengerConfig):
        super().__init__(config)
        self.formatter = TelegramFormatter()

    def send(self, data: MessageData) -> bool:
        """텔레그램 메시지 발송"""
        if not self.config.telegram_token or not self.config.telegram_chat_id:
            logger.warning("Telegram 설정이 누락되어 발송을 건너뜁니다.")
            return False

        try:
            # 포맷팅
            message_text = self.formatter.format(data)

            # 발송
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
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
        """디스코드 메시지 발송"""
        if not self.config.discord_url:
            logger.warning("Discord 설정이 누락되어 발송을 건너뜁니다.")
            return False

        try:
            # 포맷팅
            payload = self.formatter.format(data)

            # 발송
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
        """이메일 발송"""
        if not self.config.smtp_user or not self.config.smtp_password:
            logger.warning("SMTP 설정이 누락되어 발송을 건너뜁니다.")
            return False

        if not self.config.email_recipients:
            logger.warning("수신자 이메일(EMAIL_RECIPIENTS)이 설정되지 않았습니다.")
            return False

        try:
            # 포맷팅
            html_body = self.formatter.format(data)

            # 이메일 구성
            msg = MIMEMultipart()
            msg['From'] = self.config.smtp_user
            msg['To'] = ", ".join(self.config.email_recipients)
            msg['Subject'] = data.title
            msg.attach(MIMEText(html_body, 'html'))

            # 발송
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logger.info(f"이메일 발송 성공: {', '.join(self.config.email_recipients)}")
            return True

        except Exception as e:
            logger.error(f"이메일 발송 중 오류: {e}")
            return False


# =============================================================================
# Main Messenger Class
# =============================================================================
class Messenger:
    """
    메신저 알림 발송 클래스 (Refactored)

    Changes (Phase 4):
    - Formatting logic extracted to messenger_formatters.py
    - Sender classes extracted (TelegramSender, DiscordSender, EmailSender)
    - Configuration extracted to MessengerConfig
    - Reduced from 455 lines to ~200 lines
    """

    def __init__(self, config: Optional[MessengerConfig] = None):
        """
        초기화

        Args:
            config: (Optional) MessengerConfig 인스턴스
        """
        self.config = config or MessengerConfig()

        # 발송기 초기화
        self.senders = {
            'telegram': TelegramSender(self.config),
            'discord': DiscordSender(self.config),
            'email': EmailSender(self.config),
        }

    def send_screener_result(self, result) -> None:
        """
        스크리너 결과 발송

        Args:
            result: ScreeningResult 객체
        """
        if self.config.disabled:
            logger.info("메신저 알림이 비활성화되어 있습니다.")
            return

        # Skip if no signals found (prevent empty notification spam)
        signals = getattr(result, 'signals', [])
        if not signals or len(signals) == 0:
            logger.info("[Notification] 발송할 시그널 없음 (0개) - 알림 스킵")
            return

        try:
            # 메시지 데이터 빌드
            message_data = MessageDataBuilder.build(result)

            # 활성화된 채널에 발송
            sent_count = 0
            for channel in self.config.channels:
                if channel in self.senders:
                    if self.senders[channel].send(message_data):
                        sent_count += 1

            if sent_count == 0:
                logger.warning("메신저 알림을 발송할 채널이 없습니다.")

        except Exception as e:
            logger.error(f"메신저 알림 발송 중 전체 오류: {e}")

    def send_custom_message(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None
    ) -> None:
        """
        커스텀 메시지 발송

        Args:
            title: 메시지 제목
            message: 메시지 내용
            channels: (Optional) 발송할 채널 리스트 (기본: 설정된 전체 채널)
        """
        if self.config.disabled:
            logger.info("메신저 알림이 비활성화되어 있습니다.")
            return

        target_channels = channels or self.config.channels

        for channel in target_channels:
            if channel == 'telegram':
                self._send_telegram_custom(title, message)
            elif channel == 'discord':
                self._send_discord_custom(title, message)

    def _send_telegram_custom(self, title: str, message: str) -> None:
        """텔레그램 커스텀 메시지 발송"""
        if not self.config.telegram_token or not self.config.telegram_chat_id:
            return

        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": f"<b>{title}</b>\n\n{message}",
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            requests.post(url, json=payload)
            logger.info("Telegram 커스텀 알림 발송 성공")
        except Exception as e:
            logger.error(f"Telegram 커스텀 발송 중 오류: {e}")

    def _send_discord_custom(self, title: str, message: str) -> None:
        """디스코드 커스텀 메시지 발송"""
        if not self.config.discord_url:
            return

        try:
            payload = {
                "username": "Closing Bet Bot",
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": 0x00ff00,
                }]
            }
            requests.post(self.config.discord_url, json=payload)
            logger.info("Discord 커스텀 알림 발송 성공")
        except Exception as e:
            logger.error(f"Discord 커스텀 발송 중 오류: {e}")


# =============================================================================
# Convenience Functions
# =============================================================================
def create_messenger(config: Optional[MessengerConfig] = None) -> Messenger:
    """
    Messenger 인스턴스 생성 (Convenience Factory)

    Args:
        config: (Optional) MessengerConfig 인스턴스

    Returns:
        Messenger 인스턴스
    """
    return Messenger(config)
