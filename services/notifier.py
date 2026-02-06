"""
AI 종가베팅 알림 서비스 모듈
Discord, Telegram, Slack, Email로 분석 결과를 발송합니다.
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter

import requests

logger = logging.getLogger(__name__)


class NotificationService:
    """메신저 알림 서비스"""
    
    def __init__(self):
        self.enabled = os.getenv('NOTIFICATION_ENABLED', 'false').lower() == 'true'
        self.channels = [ch.strip() for ch in os.getenv('NOTIFICATION_CHANNELS', '').split(',') if ch.strip()]
        
        # Discord
        self.discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL', '')
        
        # Telegram
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # Slack
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL', '')
        
        # Email
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.email_recipients = [e.strip() for e in os.getenv('EMAIL_RECIPIENTS', '').split(',') if e.strip()]
    
    def format_jongga_message(self, signals: List[Dict], date_str: Optional[str] = None) -> str:
        """
        종가베팅 분석 결과를 메시지 포맷으로 변환
        
        Args:
            signals: 분석된 시그널 리스트
            date_str: 날짜 문자열 (없으면 오늘 날짜)
        
        Returns:
            포맷팅된 메시지 문자열
        """
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # [수정] D등급 제외 (메시지 길이 최적화 및 저품질 신호 필터링)
        # 원본 개수 저장
        total_raw_count = len(signals)
        signals = [s for s in signals if str(s.get('grade', 'D')).upper() != 'D']
        filtered_count = total_raw_count - len(signals)

        # [수정] 정렬 로직 추가: 등급순(S->A->B->C) -> 점수순(내림차순)
        grade_priority = {'S': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4}
        signals.sort(key=lambda x: (
            grade_priority.get(str(x.get('grade', 'D')).upper(), 99),
            -float(x.get('score', {}).get('total', 0) if isinstance(x.get('score'), dict) else x.get('total_score', 0))
        ))
                
        # 등급 분포 계산
        grades = [s.get('grade', 'D') for s in signals]
        grade_counts = Counter(grades)
        grade_dist = ' | '.join([f"{g}:{c}" for g, c in sorted(grade_counts.items())])
        
        # 헤더
        lines = [
            f"📊 종가베팅 ({date_str})",
            "",
            f"✅ 선별된 신호: {len(signals)}개 (D등급 {filtered_count}개 제외)",
            f"📊 등급 분포: {grade_dist}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "📋 Top Signals:",
        ]
        
        # 시그널 목록
        for i, sig in enumerate(signals, 1):
            name = sig.get('name', sig.get('stock_name', ''))
            code = sig.get('code', sig.get('stock_code', sig.get('ticker', '')))
            grade = sig.get('grade', 'D')
            
            # 점수 추출
            score_data = sig.get('score', {})
            if isinstance(score_data, dict):
                total_score = score_data.get('total', 0)
            else:
                total_score = sig.get('total_score', 0)
            
            # 가격 정보
            entry_price = int(sig.get('entry_price', sig.get('buy_price', 0)))
            target_price = int(sig.get('target_price_1', entry_price * 1.05 if entry_price else 0))
            stop_loss = int(sig.get('stop_loss', entry_price * 0.97 if entry_price else 0))
            
            # 상세 정보 (score_details에서 추출)
            score_details = sig.get('score_details', {})
            rise_pct = score_details.get('rise_pct', sig.get('change_pct', 0))
            volume_ratio = score_details.get('volume_ratio', 0)
            trading_value = sig.get('trading_value', 0)
            foreign_5d = score_details.get('foreign_net_buy', 0)
            inst_5d = score_details.get('inst_net_buy', 0)
            
            # 거래대금 포맷팅 (조/억 단위)
            if trading_value >= 1_000_000_000_000:
                trading_str = f"{trading_value / 1_000_000_000_000:.1f}조"
            elif trading_value >= 100_000_000:
                trading_str = f"{trading_value // 100_000_000}억"
            else:
                trading_str = f"{trading_value // 10_000}만"
            
            # 외인/기관 포맷팅 (억 단위)
            def format_supply(val):
                if val == 0:
                    return "0"
                sign = "+" if val > 0 else ""
                if abs(val) >= 100_000_000:
                    return f"{sign}{val // 100_000_000}억"
                else:
                    return f"{sign}{val // 10_000}만"
            
            foreign_str = format_supply(foreign_5d)
            inst_str = format_supply(inst_5d)
            
            market = sig.get('market')
            market_type = f"[{market}] " if market else ""
            lines.append(f"{i}. {market_type}{name} ({code}) - {grade}등급 {total_score}점")
            lines.append(f"   📈 상승: {rise_pct:+.1f}% | 거래배수: {volume_ratio:.1f}x | 대금: {trading_str}")
            lines.append(f"   🏦 외인(5일): {foreign_str} | 기관(5일): {inst_str}")
            
            # AI 분석 결과 추가
            ai_eval = sig.get('ai_evaluation', {})
            if ai_eval and ai_eval.get('action'):
                action = ai_eval.get('action')
                reason = ai_eval.get('reason', '')
                if len(reason) > 80:
                    reason = reason[:77] + "..."
                lines.append(f"   🤖 AI: {action} - {reason}")

            lines.append(f"   💰 진입: ₩{entry_price:,} | 목표: ₩{target_price:,} | 손절: ₩{stop_loss:,}")
            lines.append("")
        
        # 푸터
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다."
        ])
        
        return '\n'.join(lines)
    
    def send_all(self, signals: List[Dict], date_str: Optional[str] = None) -> Dict[str, bool]:
        """
        설정된 모든 채널로 알림 발송
        
        Args:
            signals: 분석된 시그널 리스트
            date_str: 날짜 문자열
        
        Returns:
            채널별 발송 성공 여부
        """
        if not self.enabled:
            logger.info("[Notifier] 알림이 비활성화되어 있습니다.")
            return {}
        
        if not signals:
            logger.info("[Notifier] 발송할 신호가 없습니다.")
            return {}
        
        message = self.format_jongga_message(signals, date_str)
        results = {}
        
        for channel in self.channels:
            channel = channel.lower()
            try:
                if channel == 'discord':
                    results['discord'] = self.send_discord(message)
                elif channel == 'telegram':
                    results['telegram'] = self.send_telegram(message)
                elif channel == 'slack':
                    results['slack'] = self.send_slack(message)
                elif channel == 'email':
                    results['email'] = self.send_email(message, date_str)
                else:
                    logger.warning(f"[Notifier] 알 수 없는 채널: {channel}")
            except Exception as e:
                logger.error(f"[Notifier] {channel} 발송 실패: {e}")
                results[channel] = False
        
        return results
    
    def send_discord(self, message: str) -> bool:
        """Discord 웹훅으로 메시지 발송"""
        if not self.discord_webhook_url:
            logger.warning("[Notifier] Discord 웹훅 URL이 설정되지 않았습니다.")
            return False
        
        try:
            # 2000자 제한 처리 (안전하게 1900자로 분할)
            import time
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            
            for chunk in chunks:
                payload = {"content": chunk}
                response = requests.post(
                    self.discord_webhook_url,
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                # Rate Limit 방지를 위한 짧은 대기
                if len(chunks) > 1:
                    time.sleep(0.5)
            
            logger.info("[Notifier] Discord 발송 성공")
            return True
        except Exception as e:
            logger.error(f"[Notifier] Discord 발송 실패: {e}")
            return False
    
    def send_telegram(self, message: str) -> bool:
        """Telegram 봇으로 메시지 발송"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("[Notifier] Telegram 설정이 불완전합니다.")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("[Notifier] Telegram 발송 성공")
            return True
        except Exception as e:
            logger.error(f"[Notifier] Telegram 발송 실패: {e}")
            return False
    
    def send_slack(self, message: str) -> bool:
        """Slack 웹훅으로 메시지 발송"""
        if not self.slack_webhook_url:
            logger.warning("[Notifier] Slack 웹훅 URL이 설정되지 않았습니다.")
            return False
        
        try:
            payload = {"text": message}
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("[Notifier] Slack 발송 성공")
            return True
        except Exception as e:
            logger.error(f"[Notifier] Slack 발송 실패: {e}")
            return False
    
    def send_email(self, message: str, date_str: Optional[str] = None) -> bool:
        """이메일로 메시지 발송"""
        if not self.smtp_user or not self.smtp_password or not self.email_recipients:
            logger.warning("[Notifier] 이메일 설정이 불완전합니다.")
            return False
        
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = ', '.join(self.email_recipients)
            msg['Subject'] = f"📊 종가베팅 알림 ({date_str})"
            
            # 메시지 본문을 HTML로 변환 (줄바꿈 유지)
            html_message = message.replace('\n', '<br>')
            msg.attach(MIMEText(f"<pre style='font-family: monospace;'>{html_message}</pre>", 'html'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info("[Notifier] 이메일 발송 성공")
            return True
        except Exception as e:
            logger.error(f"[Notifier] 이메일 발송 실패: {e}")
            return False


# 편의 함수
def send_jongga_notification(signals: List[Dict], date_str: Optional[str] = None) -> Dict[str, bool]:
    """
    종가베팅 알림 발송 (편의 함수)
    
    Args:
        signals: 분석된 시그널 리스트
        date_str: 날짜 문자열
    
    Returns:
        채널별 발송 성공 여부
    """
    notifier = NotificationService()
    return notifier.send_all(signals, date_str)
