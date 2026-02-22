#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine - Messenger (Facade)

메신저 알림 발송 클래스 (Discord, Telegram, Email)
- 설정: messenger_config.py
- 채널 발송기: messenger_senders.py
- 레거시 payload 변환: messenger_legacy_payload.py
- 포맷팅: messenger_formatters.py
"""

import logging
from typing import List, Optional

import requests
from dotenv import load_dotenv

from engine.messenger_config import MessengerConfig
from engine.messenger_formatters import MessageDataBuilder
from engine.messenger_legacy_payload import (
    _to_float as _legacy_to_float,
    _to_int as _legacy_to_int,
    build_message_data_from_payload,
)
from engine.messenger_senders import (
    DiscordSender,
    EmailSender,
    MessageSender,
    TelegramSender,
)


load_dotenv()
logger = logging.getLogger(__name__)


class Messenger:
    """
    메신저 알림 발송 클래스.

    기존 public interface 하위호환을 유지한다.
    """

    def __init__(self, config: Optional[MessengerConfig] = None):
        self.config = config or MessengerConfig()
        self.senders: dict[str, MessageSender] = {
            "telegram": TelegramSender(self.config),
            "discord": DiscordSender(self.config),
            "email": EmailSender(self.config),
        }

    @property
    def discord_url(self) -> str | None:
        """기존 코드 호환용 Discord URL 접근자."""
        return self.config.discord_url

    @property
    def telegram_token(self) -> str | None:
        """기존 코드 호환용 Telegram token 접근자."""
        return self.config.telegram_token

    @property
    def telegram_chat_id(self) -> str | None:
        """기존 코드 호환용 Telegram chat_id 접근자."""
        return self.config.telegram_chat_id

    @property
    def smtp_user(self) -> str | None:
        """기존 코드 호환용 SMTP user 접근자."""
        return self.config.smtp_user

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        """호환 payload의 숫자 필드를 안전하게 정수 변환한다."""
        return _legacy_to_int(value, default)

    @staticmethod
    def _to_float(value, default: float = 0.0) -> float:
        """호환 payload의 숫자 필드를 안전하게 실수 변환한다."""
        return _legacy_to_float(value, default)

    def _build_message_data_from_payload(self, payload: dict):
        """기존 dict 기반 payload를 MessageData로 변환한다."""
        return build_message_data_from_payload(payload)

    def _send_telegram(self, payload: dict) -> None:
        """기존 코드 호환용 텔레그램 발송 메서드."""
        data = self._build_message_data_from_payload(payload)
        sender = self.senders.get("telegram")
        if sender:
            sender.send(data)

    def _send_discord(self, payload: dict) -> None:
        """기존 코드 호환용 디스코드 발송 메서드."""
        data = self._build_message_data_from_payload(payload)
        sender = self.senders.get("discord")
        if sender:
            sender.send(data)

    def _send_email(self, payload: dict) -> None:
        """기존 코드 호환용 이메일 발송 메서드."""
        data = self._build_message_data_from_payload(payload)
        sender = self.senders.get("email")
        if sender:
            sender.send(data)

    def send_screener_result(self, result) -> None:
        """
        스크리너 결과 발송

        Args:
            result: ScreeningResult 객체
        """
        if self.config.disabled:
            logger.info("메신저 알림이 비활성화되어 있습니다.")
            return

        signals = getattr(result, "signals", [])
        if not signals or len(signals) == 0:
            logger.info("[Notification] 발송할 시그널 없음 (0개) - 알림 스킵")
            return

        try:
            message_data = MessageDataBuilder.build(result)

            sent_count = 0
            for channel in self.config.channels:
                if channel in self.senders and self.senders[channel].send(message_data):
                    sent_count += 1

            if sent_count == 0:
                logger.warning("메신저 알림을 발송할 채널이 없습니다.")

        except Exception as e:
            logger.error(f"메신저 알림 발송 중 전체 오류: {e}")

    def send_custom_message(
        self,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
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
            if channel == "telegram":
                self._send_telegram_custom(title, message)
            elif channel == "discord":
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
                "disable_web_page_preview": True,
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
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": 0x00FF00,
                    }
                ],
            }
            requests.post(self.config.discord_url, json=payload)
            logger.info("Discord 커스텀 알림 발송 성공")
        except Exception as e:
            logger.error(f"Discord 커스텀 발송 중 오류: {e}")


def create_messenger(config: Optional[MessengerConfig] = None) -> Messenger:
    """
    Messenger 인스턴스 생성 (Convenience Factory)

    Args:
        config: (Optional) MessengerConfig 인스턴스

    Returns:
        Messenger 인스턴스
    """
    return Messenger(config)


__all__ = [
    "MessengerConfig",
    "MessageSender",
    "TelegramSender",
    "DiscordSender",
    "EmailSender",
    "Messenger",
    "create_messenger",
]
