#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Messenger message data builder.
"""

from __future__ import annotations

from datetime import datetime

from engine.constants import MESSENGER
from engine.messenger_formatters_models import MessageData, SignalData


class MessageDataBuilder:
    """ScreenerResult를 MessageData로 변환한다."""

    @staticmethod
    def build(result) -> MessageData:
        """ScreenerResult에서 MessageData 빌드."""
        date_str = result.date.strftime('%Y-%m-%d')

        # 등급순 정렬
        if result.signals:
            grade_priority = dict(MESSENGER.GRADE_PRIORITY)
            result.signals.sort(
                key=lambda s: (
                    grade_priority.get(str(getattr(s.grade, 'value', s.grade)).upper(), 99),
                    -MessageDataBuilder._get_score_total(s.score),
                )
            )

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
            timestamp=datetime.now().isoformat(),
        )

    @staticmethod
    def _get_score_total(score_obj) -> float:
        """점수 객체 또는 딕셔너리에서 total 값 안전하게 추출."""
        if not score_obj:
            return 0
        if isinstance(score_obj, dict):
            return float(score_obj.get('total', 0))
        return float(getattr(score_obj, 'total', 0))

    @staticmethod
    def _build_signal_data(index: int, signal) -> SignalData:
        """개별 시그널 데이터 빌드."""
        grade = getattr(signal.grade, 'value', signal.grade)
        market_icon = '🔵' if signal.market == 'KOSPI' else '🟡'

        # 수급 데이터
        details = signal.score_details or {}
        f_buy = details.get('foreign_net_buy', details.get('foreign_buy_5d', 0))
        i_buy = details.get('inst_net_buy', details.get('inst_buy_5d', 0))

        # AI Reason
        ai_reason = 'AI 분석 대기중'
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
            ai_reason=ai_reason,
        )
