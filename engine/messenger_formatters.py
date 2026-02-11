#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messenger Formatters Module

메시지 포맷팅 로직을 분리한 모듈입니다.
Strategy Pattern을 사용하여 각 플랫폼별 포맷터를 구현합니다.

Created: 2025-02-11 (Phase 4 Refactoring)
"""
import logging
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass

from engine.constants import MESSENGER, NEWS_SOURCE_WEIGHTS

logger = logging.getLogger(__name__)


# =============================================================================
# Formatters
# =============================================================================
@dataclass
class SignalData:
    """
    시그널 데이터 DTO

    Attributes:
        index: 순번
        name: 종목명
        code: 종목 코드
        market: 시장 (KOSPI/KOSDAQ)
        market_icon: 시장 아이콘
        grade: 등급
        score: 점수
        change_pct: 등락률
        volume_ratio: 거래량 배수
        trading_value: 거래대금
        f_buy: 외인 순매수
        i_buy: 기관 순매수
        entry: 진입가
        target: 목표가
        stop: 손절가
        ai_reason: AI 분석 의견
    """
    index: int
    name: str
    code: str
    market: str
    market_icon: str
    grade: str
    score: float
    change_pct: float
    volume_ratio: float
    trading_value: int
    f_buy: int
    i_buy: int
    entry: int
    target: int
    stop: int
    ai_reason: str


@dataclass
class MessageData:
    """
    메시지 데이터 DTO

    Attributes:
        title: 제목
        summary_title: 요약 제목
        summary_desc: 요약 설명
        gate_info: 게이트 정보
        signals: 시그널 리스트
        timestamp: 타임스탬프
    """
    title: str
    summary_title: str
    summary_desc: str
    gate_info: str
    signals: List[SignalData]
    timestamp: str


class MoneyFormatter:
    """금액 포맷터 (조/억/만 단위)"""

    @staticmethod
    def format(val: int | float) -> str:
        """
        금액 포맷팅

        Args:
            val: 금액 값

        Returns:
            포맷된 문자열 (예: +1.5조, +500억, +1.2만)
        """
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
        if abs_val >= 100_000_000_000:  # 1조 이상
            return f"{val / 100_000_000_000:+.1f}조"
        elif abs_val >= 100_000_000:  # 1억 이상
            return f"{val / 100_000_000:+.0f}억"
        elif abs_val >= 10_000:  # 1만 이상
            return f"{val / 10_000:+.0f}만"
        return f"{val:+}"


class MessageFormatter:
    """
    메시지 포맷터 기본 클래스 (Abstract)

    모든 포맷터는 이 클래스를 상속받아 format() 메서드를 구현해야 합니다.
    """

    def format(self, data: MessageData) -> str:
        """
        메시지 포맷팅

        Args:
            data: 메시지 데이터

        Returns:
            포맷된 메시지 문자열
        """
        raise NotImplementedError


class TelegramFormatter(MessageFormatter):
    """
    텔레그램 메시지 포맷터

    HTML 파싱 모드를 사용하여 메시지를 포맷팅합니다.
    메시지 길이 제한 (4096자)을 준수합니다.
    """

    def __init__(self):
        self.max_length = MESSENGER.TELEGRAM_MAX_LENGTH
        self.ai_reason_max_length = MESSENGER.AI_REASON_MAX_LENGTH

    def format(self, data: MessageData) -> str:
        """텔레그램 HTML 메시지 생성"""
        header_text = self._build_header(data)
        footer = self._build_footer()

        # 헤더 + 푸터 길이 계산
        current_len = len(header_text) + len(footer) + 50

        body_lines = []
        truncated = False

        for signal in data.signals:
            item_text = self._format_signal(signal)

            # 길이 체크
            if current_len + len(item_text) > self.max_length:
                truncated = True
                break

            body_lines.append(item_text)
            current_len += len(item_text)

        if truncated:
            body_lines.append("\n\n✂️ <b>(메시지 길이 제한으로 하위 등급 종목은 생략되었습니다)</b>")

        if not body_lines:
            body_lines.append("\n\n🚫 <b>오늘 조건에 부합하는 추천 종목이 없습니다.</b>\n내일의 기회를 기다려보세요! 🍀")

        return header_text + "".join(body_lines) + footer

    def _build_header(self, data: MessageData) -> str:
        """헤더 생성"""
        lines = [
            f"<b>{data.title}</b>",
            f"{data.gate_info}",
            f"{data.summary_title}",
            f"{data.summary_desc}",
            "-" * 25,
            "📋 <b>전체 신호:</b>"
        ]
        return "\n".join(lines)

    def _build_footer(self) -> str:
        """푸터 생성"""
        return "\n\n⚠️ 투자 참고용이며 손실에 대한 책임은 본인에게 있습니다."

    def _format_signal(self, signal: SignalData) -> str:
        """개별 시그널 포맷팅"""
        f_buy_str = MoneyFormatter.format(signal.f_buy)
        i_buy_str = MoneyFormatter.format(signal.i_buy)
        tv_str = MoneyFormatter.format(signal.trading_value).replace('+', '')

        ai_reason = signal.ai_reason
        if len(ai_reason) > self.ai_reason_max_length:
            ai_reason = ai_reason[:self.ai_reason_max_length - 3] + "..."

        return (
            f"\n\n"
            f"{signal.index}. {signal.market_icon} [{signal.market}] <b>{signal.name} ({signal.code})</b> - {signal.grade}등급 {signal.score}점\n"
            f"   📈 상승: {signal.change_pct:+.1f}% | 배수: {signal.volume_ratio:.0f}x | 대금: {tv_str}\n"
            f"   🏦 외인(5일): {f_buy_str} | 기관(5일): {i_buy_str}\n"
            f"   💰 진입: ₩{signal.entry:,} | 목표: ₩{signal.target:,} | 손절: ₩{signal.stop:,}\n"
            f"   🤖 <i>{ai_reason}...</i>"
        )


class DiscordFormatter(MessageFormatter):
    """
    디스코드 메시지 포맷터

    Embed 구조를 사용하여 메시지를 포맷팅합니다.
    등급별로 그룹화하여 가독성을 높입니다.
    """

    def __init__(self):
        self.field_max_length = MESSENGER.DISCORD_FIELD_MAX_LENGTH
        self.truncate_length = MESSENGER.DISCORD_FIELD_TRUNCATE_LENGTH
        self.ai_reason_max_length = MESSENGER.AI_REASON_MAX_LENGTH

        # 등급 아이콘 맵
        self.grade_icons = {
            'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉', 'D': '⚠️', 'Other': '❓'
        }

    def format(self, data: MessageData) -> Dict:
        """
        디스코드 Embed 페이로드 생성

        Returns:
            Dict (payload for Discord webhook)
        """
        # 1. 등급별 시그널 그룹화
        grouped_signals = self._group_by_grade(data.signals)

        # 2. Embed Description (Summary)
        main_desc = (
            f"{data.gate_info}\n"
            f"{data.summary_desc}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        # 3. Fields 생성
        fields = []
        priority_order = ['S', 'A', 'B', 'C', 'D', 'Other']

        for i, grade in enumerate(priority_order):
            signals = grouped_signals.get(grade, [])
            if not signals:
                continue

            field_name = f"{self.grade_icons.get(grade, '')} {grade} Grade ({len(signals)})"
            field_value = self._format_signals_by_grade(signals)

            # Field Value 길이 체크
            if len(field_value) > self.field_max_length:
                field_value = field_value[:self.truncate_length] + "\n...(생략)..."

            # Spacer Field (등급 간 간격)
            if i > 0:
                fields.append({"name": "\u200b", "value": "\u200b", "inline": False})

            fields.append({"name": field_name, "value": field_value, "inline": False})

        # 4. Embed 구성
        embed = {
            "title": data.title,
            "description": main_desc,
            "color": 0x00ff00 if data.signals else 0x99aab5,
            "fields": fields,
            "footer": {"text": "AI Jongga Bot • 투자 책임은 본인에게 있습니다."}
        }

        return {
            "username": "Closing Bet Bot",
            "embeds": [embed]
        }

    def _group_by_grade(self, signals: List[SignalData]) -> Dict[str, List[SignalData]]:
        """등급별 시그널 그룹화"""
        grouped = {'S': [], 'A': [], 'B': [], 'C': [], 'D': [], 'Other': []}
        for signal in signals:
            grade = str(signal.grade).upper()
            if grade in grouped:
                grouped[grade].append(signal)
            else:
                grouped['Other'].append(signal)
        return grouped

    def _format_signals_by_grade(self, signals: List[SignalData]) -> str:
        """등급별 시그널 포맷팅"""
        result = ""
        for s in signals:
            f_buy_str = MoneyFormatter.format(s.f_buy)
            i_buy_str = MoneyFormatter.format(s.i_buy)
            tv_str = MoneyFormatter.format(s.trading_value).replace('+', '')

            # AI Reason 길이 제한
            ai_reason = s.ai_reason
            if len(ai_reason) > self.ai_reason_max_length:
                ai_reason = ai_reason[:self.ai_reason_max_length - 3] + "..."

            result += f"**{s.index}. {s.name}** [{s.market}] ({s.code}) - {s.grade}등급 **{s.score}점**\n"
            result += f"📈 **상승**: `{s.change_pct:+.1f}%` | 🌊 **배수**: `{s.volume_ratio:.0f}x` | 💰 **대금**: `{tv_str}`\n"
            result += f"💵 **진입**: {s.entry:,} | 🎯 **목표**: {s.target:,} | 🛡️ **손절**: {s.stop:,}\n"

            # 수급 정보 (있는 경우만)
            if s.f_buy != 0 or s.i_buy != 0:
                result += f"🏦 **외인**: {f_buy_str} | **기관**: {i_buy_str}\n"

            result += f"🤖 **AI**: *{ai_reason}*\n"
            result += "\n"  # Spacer

        return result


class EmailFormatter(MessageFormatter):
    """
    이메일 메시지 포맷터

    HTML 템플릿을 사용하여 메시지를 포맷팅합니다.
    """

    def __init__(self):
        self.ai_reason_max_length = MESSENGER.AI_REASON_MAX_LENGTH

    def format(self, data: MessageData) -> str:
        """HTML 이메일 본문 생성"""
        html_body = self._build_html_template(data)

        if not data.signals:
            html_body += self._build_empty_state()

        html_body += self._build_html_footer()

        return html_body

    def _build_html_template(self, data: MessageData) -> str:
        """HTML 템플릿 헤더와 시그널 리스트 생성"""
        html = f"""
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
        <h2>{data.title}</h2>
        <p class="gate-info">{data.gate_info}</p>
    </div>

    <div class="summary">
        <h3>{data.summary_title}</h3>
        <p>{data.summary_desc}</p>
    </div>

    <div class="signals">
        <h3>📋 전체 신호</h3>
"""
        # 시그널 아이템 추가
        for signal in data.signals:
            html += self._format_signal_html(signal)

        return html

    def _format_signal_html(self, signal: SignalData) -> str:
        """개별 시그널 HTML 포맷팅"""
        f_buy_str = MoneyFormatter.format(signal.f_buy)
        i_buy_str = MoneyFormatter.format(signal.i_buy)
        tv_str = MoneyFormatter.format(signal.trading_value)

        return f"""
    <div class="signal-item">
        <div class="signal-header">
            {signal.index}. {signal.market_icon} [{signal.market}] {signal.name} ({signal.code})
            <span class="grade-badge">{signal.grade}등급 ({signal.score}점)</span>
        </div>
        <div class="details">
            📈 <b>상승:</b> {signal.change_pct:+.1f}% | <b>배수:</b> {signal.volume_ratio:.1f}x | <b>대금:</b> {tv_str}<br>
            🏦 <b>외인(5일):</b> {f_buy_str} | <b>기관(5일):</b> {i_buy_str}<br>
            💰 <span class="price-info">진입: {signal.entry:,}원 | 목표: {signal.target:,}원 | 손절: {signal.stop:,}원</span>
        </div>
        <div class="ai-reason">
            🤖 AI 분석: {signal.ai_reason}
        </div>
    </div>
    <br>
"""

    def _build_empty_state(self) -> str:
        """시그널 없을 때 메시지"""
        return """
    <div style="text-align: center; padding: 30px; color: #666;">
        <span style="font-size: 3em;">🚫</span>
        <h3>오늘 조건에 부합하는 추천 종목이 없습니다.</h3>
        <p>내일의 기회를 기다려보세요! 🍀</p>
    </div>
"""

    def _build_html_footer(self) -> str:
        """HTML 푸터"""
        return """
    </div>
    <div class="footer">
        <p>⚠️ 본 메일은 정보 제공을 목적으로 하며, 투자의 책임은 본인에게 있습니다.</p>
        <p>Powered by AI Jongga V2 Bot</p>
    </div>
</body>
</html>
"""


# =============================================================================
# Message Data Builder
# =============================================================================
class MessageDataBuilder:
    """
    메시지 데이터 빌더

    ScreenerResult를 MessageData로 변환합니다.
    """

    @staticmethod
    def build(result) -> MessageData:
        """
        ScreenerResult에서 MessageData 빌드

        Args:
            result: ScreeningResult 객체

        Returns:
            MessageData 객체
        """
        date_str = result.date.strftime('%Y-%m-%d')

        # 등급순 정렬
        if result.signals:
            grade_priority = dict(MESSENGER.GRADE_PRIORITY)
            result.signals.sort(key=lambda s: (
                grade_priority.get(str(getattr(s.grade, 'value', s.grade)).upper(), 99),
                -MessageDataBuilder._get_score_total(s.score)
            ))

        # Market Status
        market_stats = result.market_status or {}
        gate_status = market_stats.get('status', 'Unknown')
        gate_score = market_stats.get('total_score', 0)

        # Signal Items
        signals = []
        for i, s in enumerate(result.signals, 1):
            signals.append(MessageDataBuilder._build_signal_data(i, s))

        return MessageData(
            title=f"📊 종가베팅 ({date_str})",
            summary_title=f"✅ 총 {len(signals)}개 신호 생성",
            summary_desc=f"📊 등급 분포: {result.by_grade}",
            gate_info=f"Market Gate: {gate_status} ({gate_score}점)",
            signals=signals,
            timestamp=datetime.now().isoformat()
        )

    @staticmethod
    def _get_score_total(score_obj) -> float:
        """점수 객체 또는 딕셔너리에서 total 값 안전하게 추출"""
        if not score_obj:
            return 0
        if isinstance(score_obj, dict):
            return float(score_obj.get('total', 0))
        return float(getattr(score_obj, 'total', 0))

    @staticmethod
    def _build_signal_data(index: int, signal) -> SignalData:
        """개별 시그널 데이터 빌드"""
        grade = getattr(signal.grade, 'value', signal.grade)
        market_icon = "🔵" if signal.market == "KOSPI" else "🟡"

        # 수급 데이터
        details = signal.score_details or {}
        f_buy = details.get('foreign_net_buy', details.get('foreign_buy_5d', 0))
        i_buy = details.get('inst_net_buy', details.get('inst_buy_5d', 0))

        # AI Reason
        ai_reason = "AI 분석 대기중"
        if signal.score:
            if isinstance(signal.score, dict):
                ai_reason = signal.score.get('llm_reason', ai_reason)
            else:
                ai_reason = getattr(signal.score, 'llm_reason', ai_reason)

        return SignalData(
            index=index,
            name=signal.stock_name,
            code=signal.stock_code,
            market=signal.market,
            market_icon=market_icon,
            grade=grade,
            score=MessageDataBuilder._get_score_total(signal.score),
            change_pct=signal.change_pct,
            volume_ratio=signal.volume_ratio or 0.0,
            trading_value=signal.trading_value,
            f_buy=f_buy,
            i_buy=i_buy,
            entry=int(signal.entry_price),
            target=int(signal.target_price),
            stop=int(signal.stop_price),
            ai_reason=ai_reason
        )
