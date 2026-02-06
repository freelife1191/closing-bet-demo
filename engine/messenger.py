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

def _safe_int(val):
    try:
        return int(val)
    except:
        return 587

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
        self.smtp_host = os.getenv('SMTP_HOST')
        self.smtp_port = _safe_int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.email_recipients = [e.strip() for e in os.getenv('EMAIL_RECIPIENTS', '').split(',') if e.strip()]

        # [USER REQUEST] 공용 키 사용량 0으로 설정 -> 개인 설정값 없으면 동작 안 하게 강제
        # 만약 개인 설정이 없다면 disabled 처리 또는 로깅
        if not any([self.telegram_token, self.discord_url, self.smtp_user]):
            logger.warning("[Messenger] 개인 알림 설정이 감지되지 않았습니다. 알림 발송이 동작하지 않을 수 있습니다.")


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

    def _get_score_total(self, score_obj):
        """점수 객체 또는 딕셔너리에서 total 값 안전하게 추출"""
        if not score_obj:
            return 0
        if isinstance(score_obj, dict):
            return float(score_obj.get('total', 0))
        return float(getattr(score_obj, 'total', 0))

    def _generate_message_data(self, result):
        """메시지 데이터 구조 생성"""
        date_str = result.date.strftime('%Y-%m-%d')

        # [수정] 정렬 로직 추가: 등급순(S->A->B->C->D) -> 점수순(내림차순)
        if result.signals:
            grade_priority = {'S': 0, 'A': 1, 'B': 2, 'C': 3, 'D': 4}
            result.signals.sort(key=lambda s: (
                grade_priority.get(str(getattr(s.grade, 'value', s.grade)).upper(), 99),
                -self._get_score_total(s.score)
            ))
        
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
            # [FIX] 키 이름 불일치 수정 (foreign_buy_5d -> foreign_net_buy)
            f_buy = details.get('foreign_net_buy', details.get('foreign_buy_5d', 0))
            i_buy = details.get('inst_net_buy', details.get('inst_buy_5d', 0))
            
            # AI Reason
            ai_reason = "AI 분석 대기중"
            if s.score:
                if isinstance(s.score, dict):
                    ai_reason = s.score.get('llm_reason', ai_reason)
                else:
                    ai_reason = getattr(s.score, 'llm_reason', ai_reason)

            # [DEBUG] Log score extraction
            extracted_score = self._get_score_total(s.score)
            logger.debug(f"[Messenger] {s.stock_name} - score type: {type(s.score)}, extracted_score: {extracted_score}")
            
            signals.append({
                "index": i,
                "name": s.stock_name,
                "code": s.stock_code,
                "market": s.market,
                "market_icon": market_icon,
                "grade": grade,
                "score": extracted_score,
                "change_pct": s.change_pct,
                "volume_ratio": s.volume_ratio or 0.0,
                "trading_value": s.trading_value,
                "f_buy": f_buy,
                "i_buy": i_buy,
                "entry": int(s.entry_price),
                "target": int(s.target_price),
                "stop": int(s.stop_price),
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
        """금액 포맷팅 (조/억/만 단위)"""
        try:
            val_float = float(val)
            val_int = int(val)
            # 정수라면 정수형 우선 사용
            if val_float == val_int:
                val = val_int
            else:
                val = val_float
        except:
            return str(val)
            
        abs_val = abs(val)
        if abs_val >= 1000000000000: # 1조 이상
            return f"{val/1000000000000:+.1f}조"
        elif abs_val >= 100000000: # 1억 이상
            return f"{val/100000000:+.0f}억"
        elif abs_val >= 10000: # 1만 이상
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
                # 거래대금: + 기호 제거
                tv_str = self._format_money(s['trading_value']).replace('+', '')
                
                # 상세 정보
                # 상세 정보 (가독성을 위해 종목 간 개행 추가)
                item_text = (
                    f"\n\n{s['index']}. {s['market_icon']} [{s['market']}] <b>{s['name']} ({s['code']})</b> - {s['grade']}등급 {s['score']}점\n"
                    f"   📈 상승: {s['change_pct']:+.1f}% | 배수: {s['volume_ratio']:.0f}x | 대금: {tv_str}\n"
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
        """디스코드 메시지 발송 (Embed Fields 활용, 가독성 개선 + Label 추가 버전)"""
        try:
            # 1. 등급별로 신호 그룹화
            grouped_signals = {'S': [], 'A': [], 'B': [], 'C': [], 'D': []}
            for s in data['signals']:
                grade = str(s['grade']).upper()
                if grade in grouped_signals:
                    grouped_signals[grade].append(s)
                else:
                    if 'Other' not in grouped_signals: grouped_signals['Other'] = []
                    grouped_signals['Other'].append(s)

            # 2. Main Embed Description (Summary)
            main_desc = (
                f"{data['gate_info']}\n"
                f"{data['summary_desc']}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )

            fields = []

            # 3. Add Fields per Grade
            priority_order = ['S', 'A', 'B', 'C', 'D', 'Other']
            
            for grade in priority_order:
                signals = grouped_signals.get(grade, [])
                if not signals:
                    continue
                
                # Field Title
                icon_map = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉', 'D': '⚠️', 'Other': '❓'}
                field_name = f"{icon_map.get(grade, '')} {grade} Grade ({len(signals)})"
                
                # Field Value (Signal List)
                field_value = ""
                for s in signals:
                    # 데이터 포맷팅
                    f_buy_str = self._format_money(s['f_buy'])
                    i_buy_str = self._format_money(s['i_buy'])
                    tv_str = self._format_money(s['trading_value']).replace('+', '')
                    
                    # [변경] 가독성을 위해 코드블럭 제거, 이모지 활용, 텍스트 라벨 추가
                    # 1. 한화솔루션 (001230)
                    # 📈 상승: +15.4% | 🌊 배수: 11x | 💰 대금: 2.2조
                    # 💵 진입: 42,000 | 🎯 목표: 44,100 | 🛡️ 손절: 40,740
                    # 🤖 AI: 시장 전체가...
                    
                    # Line 1: Name
                    field_value += f"**{s['index']}. {s['name']}** [{s['market']}] ({s['code']}) - {s['grade']}등급 **{s['score']}점**\n"
                    
                    # Line 2: Metrics (With Labels)
                    field_value += f"📈 **상승**: `{s['change_pct']:+.1f}%` | 🌊 **배수**: `{s['volume_ratio']:.0f}x` | 💰 **대금**: `{tv_str}`\n"
                    
                    # Line 3: Price (With Labels)
                    field_value += f"💵 **진입**: {s['entry']:,} | 🎯 **목표**: {s['target']:,} | 🛡️ **손절**: {s['stop']:,}\n"
                    
                    # Line 4: Supply (Optional - only if meaningful)
                    if s['f_buy'] != 0 or s['i_buy'] != 0:
                        field_value += f"🏦 **외인**: {f_buy_str} | **기관**: {i_buy_str}\n"
                    
                    # Line 5: AI Comment (Italic)
                    # Limit AI reason length
                    ai_reason = s['ai_reason']
                    if len(ai_reason) > 60:
                        ai_reason = ai_reason[:57] + "..."
                    field_value += f"🤖 **AI**: *{ai_reason}*\n"
                    
                    field_value += "\n" # Spacer

                # Discord Field Value Limit Check
                if len(field_value) > 1000:
                    field_value = field_value[:950] + "\n...(생략)..."
                
                # [변경] 등급 간 간격 추가를 위한 Spacer Field
                if fields: # 첫 번째 등급이 아니라면 앞에 공백 추가
                     fields.append({"name": "\u200b", "value": "\u200b", "inline": False})
                
                fields.append({"name": field_name, "value": field_value, "inline": False})

            # 4. Embed Construction
            embed = {
                "title": data['title'],
                "description": main_desc,
                "color": 0x00ff00 if data['signals'] else 0x99aab5, 
                "fields": fields,
                "footer": {"text": "AI Jongga Bot • 투자 책임은 본인에게 있습니다."}
            }

            # 5. Payload Construction
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

            if not self.email_recipients:
                logger.warning("수신자 이메일(EMAIL_RECIPIENTS)이 설정되지 않았습니다.")
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
                tv_str = self._format_money(s['trading_value'])
                
                html_body += f"""
                    <div class="signal-item">
                        <div class="signal-header">
                            {s['index']}. {s['market_icon']} [{s['market']}] {s['name']} ({s['code']}) 
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
