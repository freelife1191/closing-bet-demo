import os
import requests
import json
from datetime import datetime
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class Messenger:
    """메신저 알림 발송 클래스 (Discord & Telegram)"""
    
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
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_recipients = [e.strip() for e in os.getenv('EMAIL_RECIPIENTS', '').split(',') if e.strip()]

    def send_screener_result(self, result):
        """스크리너 결과 발송"""
        if self.disabled:
            logger.info("메신저 알림이 비활성화되어 있습니다.")
            return

        try:
            message_data = self._generate_message_data(result)
            
            # Discord 발송
            if 'discord' in self.channels and self.discord_url:
                self._send_discord(message_data)
                
            # Telegram 발송
            if 'telegram' in self.channels and self.telegram_token and self.telegram_chat_id:
                self._send_telegram(message_data)
            
            # Email 발송
            if 'email' in self.channels and self.smtp_user and self.email_recipients:
                self._send_email(message_data)
                
        except Exception as e:
            logger.error(f"메신저 알림 발송 중 전체 오류: {e}")

    def _generate_message_data(self, result):
        """메시지 데이터 구조 생성"""
        date_str = result.date.strftime('%Y-%m-%d')
        
        # Market Status
        market_stats = result.market_status or {}
        gate_status = market_stats.get('status', 'Unknown')
        gate_score = market_stats.get('total_score', 0)
        
        # Signal Items
        signals = []
        for i, s in enumerate(result.signals, 1):
            grade = getattr(s.grade, 'value', s.grade)
            market_icon = "🔵" if s.market == "KOSPI" else "🟡"
            
            # 수급 데이터 (score_details가 있다면 사용, 없으면 0)
            details = s.score_details or {}
            f_buy = details.get('foreign_buy_5d', 0)
            i_buy = details.get('inst_buy_5d', 0)
            
            # AI Reason
            ai_reason = s.score.llm_reason if s.score and s.score.llm_reason else "AI 분석 대기중"

            signals.append({
                "index": i,
                "name": s.stock_name,
                "code": s.stock_code,
                "market": s.market,
                "market_icon": market_icon,
                "grade": grade,
                "score": s.score.total if s.score else 0,
                "change_pct": s.change_pct,
                "volume_ratio": s.volume_ratio or 0.0,
                "trading_value": s.trading_value,
                "f_buy": f_buy,
                "i_buy": i_buy,
                "entry": s.entry_price,
                "target": s.target_price,
                "stop": s.stop_price,
                "ai_reason": ai_reason
            })
            
        return {
            "title": f"📊 종가베팅 ({date_str})",
            "summary_title": f"✅ 총 {len(signals)}개 신호 생성",
            "summary_desc": f"📊 등급 분포: {result.by_grade}",
            "gate_info": f"Market Gate: {gate_status} ({gate_score}점)",
            "signals": signals,
            "timestamp": datetime.now().isoformat()
        }

    def _format_money(self, val):
        """금액 포맷팅 (억/만 단위)"""
        val = int(val)
        if abs(val) >= 100000000:
            return f"{val/100000000:+.1f}억"
        elif abs(val) >= 10000:
            return f"{val/10000:+.0f}만"
        return f"{val:+}"

    def _send_telegram(self, data):
        """텔레그램 메시지 발송"""
        try:
            # Telegram Message Limit: 4096 chars
            MAX_LENGTH = 4000  # 여유분 확보
            
            header_lines = [
                f"<b>{data['title']}</b>",
                f"{data['gate_info']}",
                f"{data['summary_title']}",
                f"{data['summary_desc']}",
                "-" * 25,
                "📋 <b>전체 신호:</b>"
            ]
            header_text = "\n".join(header_lines)
            
            footer = "\n\n⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다."
            
            # 현재 길이 계산 (Header + Footer + 줄바꿈 여유분)
            current_len = len(header_text) + len(footer) + 50 
            
            body_lines = []
            truncated = False
            
            # data['signals']는 이미 등급순(S->A->B) 정렬되어 있다고 가정 (generator.py에서 정렬됨)
            for s in data['signals']:
                f_buy_str = self._format_money(s['f_buy'])
                i_buy_str = self._format_money(s['i_buy'])
                tv_str = f"{s['trading_value']/100000000:.1f}억"
                
                # 상세 정보
                # 상세 정보 (가독성을 위해 종목 간 개행 추가)
                item_text = (
                    f"\n\n{s['index']}. {s['market_icon']} <b>{s['name']} ({s['code']})</b> - {s['grade']}등급 {s['score']}점\n"
                    f"   📈 상승: {s['change_pct']:+.1f}% | 배수: {s['volume_ratio']:.1f}x | 대금: {tv_str}\n"
                    f"   🏦 외인(5일): {f_buy_str} | 기관(5일): {i_buy_str}\n"
                    f"   💰 진입: ₩{s['entry']:,} | 목표: ₩{s['target']:,} | 손절: ₩{s['stop']:,}\n"
                    f"   🤖 <i>{s['ai_reason'][:60]}...</i>"
                )
                
                # 길이 체크
                if current_len + len(item_text) > MAX_LENGTH:
                    truncated = True
                    break
                    
                body_lines.append(item_text)
                current_len += len(item_text)
            
            if truncated:
                body_lines.append("\n\n✂️ <b>(메시지 길이 제한으로 하위 등급 종목은 생략되었습니다)</b>")
            
            # 신호가 없을 경우 메시지 추가
            if not body_lines:
                body_lines.append("\n\n🚫 <b>오늘 조건에 부합하는 추천 종목이 없습니다.</b>\n내일의 기회를 기다려보세요! 🍀")
            
            full_text = header_text + "".join(body_lines) + footer
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id, 
                "text": full_text, 
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            resp = requests.post(url, json=payload)
            if not resp.ok:
                logger.error(f"Telegram 발송 실패 결과: {resp.text}")
            else:
                logger.info("Telegram 알림 발송 성공")
                
        except Exception as e:
            logger.error(f"Telegram 발송 중 오류: {e}")

    def _send_discord(self, data):
        """디스코드 메시지 발송 (Telegram 포맷과 통일)"""
        try:
            # Header
            description_lines = [
                f"{data['gate_info']}",
                f"{data['summary_title']}",
                f"{data['summary_desc']}",
                "-" * 25,
                "**📋 전체 신호:**"
            ]
            
            # Signals Loop
            for s in data['signals']:
                f_buy_str = self._format_money(s['f_buy'])
                i_buy_str = self._format_money(s['i_buy'])
                tv_str = f"{s['trading_value']/100000000:.1f}억"
                
                # Markdown Format (Telegram HTML 대응)
                item_text = (
                    f"\n{s['index']}. {s['market_icon']} **{s['name']} ({s['code']})** - {s['grade']}등급 {s['score']}점\n"
                    f"   📈 상승: {s['change_pct']:+.1f}% | 배수: {s['volume_ratio']:.1f}x | 대금: {tv_str}\n"
                    f"   🏦 외인(5일): {f_buy_str} | 기관(5일): {i_buy_str}\n"
                    f"   💰 진입: {s['entry']:,} | 목표: {s['target']:,} | 손절: {s['stop']:,}\n"
                    f"   🤖 *{s['ai_reason'][:60]}...*"
                )
                description_lines.append(item_text)

            # 신호가 없을 경우
            if not data['signals']:
                description_lines.append("\n🚫 **오늘 조건에 부합하는 추천 종목이 없습니다.**\n내일의 기회를 기다려보세요! 🍀")
                
            footer_text = "\n\n⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다."
            
            # Combine
            full_description = "\n".join(description_lines) + footer_text
            
            # Length Check (Discord Embed Description Limit: 4096)
            if len(full_description) > 4000:
                full_description = full_description[:3900] + "\n\n...(내용이 길어 일부 생략됨, 전체 내역은 웹 대시보드 참고)..." + footer_text

            # Embed Construction
            embed = {
                "title": data['title'],
                "description": full_description,
                "color": 0x00ff00, # Green
                "footer": {"text": "AI Jongga Bot"}
            }

            payload = {
                "username": "Closing Bet Bot",
                "embeds": [embed]
            }
            
            resp = requests.post(self.discord_url, json=payload)
            if not resp.ok:
                logger.error(f"Discord 발송 실패 결과: {resp.text}")
            else:
                logger.info("Discord 알림 발송 성공")
                
        except Exception as e:
            logger.error(f"Discord 발송 중 오류: {e}")

    def _send_email(self, data):
        """이메일 발송 (HTML)"""
        try:
            if not self.smtp_user or not self.smtp_password:
                logger.warning("SMTP 설정이 누락되어 이메일을 발송할 수 없습니다.")
                return

            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = ", ".join(self.email_recipients)
            msg['Subject'] = data['title']

            # HTML Body Construction
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .header {{ background-color: #f4f4f4; padding: 20px; border-bottom: 2px solid #ddd; }}
                    .gate-info {{ font-weight: bold; color: #d32f2f; }}
                    .summary {{ margin: 20px 0; }}
                    .signal-item {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }}
                    .signal-header {{ font-weight: bold; font-size: 1.1em; color: #1976d2; }}
                    .grade-badge {{ background-color: #e3f2fd; color: #1976d2; padding: 3px 8px; border-radius: 12px; font-size: 0.9em; }}
                    .details {{ margin-top: 10px; font-size: 0.95em; }}
                    .price-info {{ font-weight: bold; }}
                    .ai-reason {{ background-color: #fff3e0; padding: 10px; margin-top: 10px; border-left: 4px solid #ff9800; font-style: italic; }}
                    .footer {{ margin-top: 30px; font-size: 0.8em; color: #777; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>{data['title']}</h2>
                    <p class="gate-info">{data['gate_info']}</p>
                </div>

                <div class="summary">
                    <h3>{data['summary_title']}</h3>
                    <p>{data['summary_desc']}</p>
                </div>

                <div class="signals">
                    <h3>📋 전체 신호</h3>
            """

            for s in data['signals']:
                f_buy_str = self._format_money(s['f_buy'])
                i_buy_str = self._format_money(s['i_buy'])
                tv_str = f"{s['trading_value']/100000000:.1f}억"
                
                html_body += f"""
                    <div class="signal-item">
                        <div class="signal-header">
                            {s['index']}. {s['market_icon']} {s['name']} ({s['code']}) 
                            <span class="grade-badge">{s['grade']}등급 ({s['score']}점)</span>
                        </div>
                        <div class="details">
                            📈 <b>상승:</b> {s['change_pct']:+.1f}% | <b>배수:</b> {s['volume_ratio']:.1f}x | <b>대금:</b> {tv_str}<br>
                            🏦 <b>외인(5일):</b> {f_buy_str} | <b>기관(5일):</b> {i_buy_str}<br>
                            💰 <span class="price-info">진입: {s['entry']:,}원 | 목표: {s['target']:,}원 | 손절: {s['stop']:,}원</span>
                        </div>
                        <div class="ai-reason">
                            🤖 AI 분석: {s['ai_reason']}
                        </div>
                    </div>
                    </div>
                    <br>
                """

            if not data['signals']:
                html_body += """
                    <div style="text-align: center; padding: 30px; color: #666;">
                        <span style="font-size: 3em;">🚫</span>
                        <h3>오늘 조건에 부합하는 추천 종목이 없습니다.</h3>
                        <p>내일의 기회를 기다려보세요! 🍀</p>
                    </div>
                """

            html_body += """
                </div>
                <div class="footer">
                    <p>⚠️ 본 메일은 정보 제공을 목적으로 하며, 투자의 책임은 본인에게 있습니다.</p>
                    <p>Powered by AI Jongga V2 Bot</p>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(html_body, 'html'))

            # Send Email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"이메일 발송 성공: {', '.join(self.email_recipients)}")

        except Exception as e:
            logger.error(f"이메일 발송 중 오류: {e}")
