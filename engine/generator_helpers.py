#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalGenerator 보조 로직 헬퍼.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from engine.market_gate import MarketGate
from engine.models import Signal, SignalStatus, StockData
from engine.toss_collector import TossCollector


async def sync_toss_data(
    *,
    candidates: List[StockData],
    target_date: Optional[date],
    config,
    scorer,
    logger,
) -> None:
    """
    Toss 증권 데이터 동기화 (Hybrid 모드)

    Toss API를 통해 실시간 가격 데이터를 후보 종목에 동기화합니다.
    """
    if not config.USE_TOSS_DATA or not candidates:
        return

    if target_date and target_date != date.today():
        return

    try:
        print(f"  [Hybrid] Toss 증권 데이터 동기화 중... ({len(candidates)}개)")
        codes = [stock.code for stock in candidates]
        toss_data_map = (
            scorer.collector_toss.get_prices_batch(codes)
            if hasattr(scorer, "collector_toss")
            else {}
        )

        if not toss_data_map:
            toss_collector = TossCollector(config)
            toss_data_map = toss_collector.get_prices_batch(codes)

        updated_count = 0
        for stock in candidates:
            if stock.code not in toss_data_map:
                continue

            t_data = toss_data_map[stock.code]
            new_close = t_data.get("current")
            new_val = t_data.get("trading_value")
            new_vol = t_data.get("volume")
            new_rate = t_data.get("change_pct")

            if new_close and new_val:
                stock.close = int(new_close)
                stock.trading_value = float(new_val)
                stock.volume = int(new_vol)
                stock.change_pct = float(new_rate)
                stock.open = int(t_data.get("open", 0))
                stock.high = int(t_data.get("high", 0))
                stock.low = int(t_data.get("low", 0))
                updated_count += 1

                if stock.trading_value >= 300_000_000_000:
                    logger.info(
                        "  [Toss Update] %s(%s): %s억 (Rate: %s%%)",
                        stock.name,
                        stock.code,
                        int(stock.trading_value) // 100000000,
                        stock.change_pct,
                    )

        print(f"  [Hybrid] {updated_count}개 종목 데이터 업데이트 완료 (Toss 기준)")
    except Exception as error:
        logger.error(f"Toss 데이터 동기화 중 오류: {error}")
        print(f"  [Warning] Toss 동기화 실패. KRX 데이터 사용. ({error})")


async def get_market_status(
    *,
    target_date: date,
    data_dir: str,
    logger,
) -> Dict:
    """Market Gate 상태 조회."""
    try:
        market_gate = MarketGate(data_dir)
        return market_gate.analyze(target_date.strftime("%Y-%m-%d"))
    except Exception as error:
        logger.warning(f"Market Gate analysis failed: {error}")
        return {}


def update_pipeline_drop_stats(*, pipeline, current_drop_stats: Dict[str, int]) -> Dict[str, int]:
    """파이프라인 drop stats를 누적/갱신한다."""
    new_drop_stats = dict(current_drop_stats)
    if hasattr(pipeline, "phase1") and pipeline.phase1:
        phase1_drops = pipeline.phase1.get_drop_stats()
        for key, value in phase1_drops.items():
            if key in new_drop_stats:
                new_drop_stats[key] += value
    return new_drop_stats


async def analyze_base(
    *,
    stock: StockData,
    collector,
    scorer,
    config,
) -> Optional[Dict]:
    """1단계: 기본 분석 (차트, 수급, Pre-Score)."""
    try:
        detail = await collector.get_stock_detail(stock.code)
        if detail:
            stock.high_52w = detail.get("high_52w", stock.high_52w)
            stock.low_52w = detail.get("low_52w", stock.low_52w)

        charts = await collector.get_chart_data(stock.code, 60)

        if config.USE_TOSS_DATA and charts and getattr(stock, "trading_value", 0) > 0 and charts.closes:
            try:
                charts.closes[-1] = stock.close
                charts.volumes[-1] = stock.volume
                if hasattr(stock, "open") and stock.open:
                    charts.opens[-1] = stock.open
                if hasattr(stock, "high") and stock.high:
                    charts.highs[-1] = stock.high
                if hasattr(stock, "low") and stock.low:
                    charts.lows[-1] = stock.low
            except Exception:
                pass

        supply = await collector.get_supply_data(stock.code)
        pre_score, _, score_details = scorer.calculate(stock, charts, [], supply, None)

        return {
            "stock": stock,
            "charts": charts,
            "supply": supply,
            "pre_score": pre_score,
            "score_details": score_details,
        }
    except Exception as error:
        print(f"    ⚠️ 기본 분석 오류 {stock.name}: {error}")
        return None


def create_final_signal(
    *,
    stock,
    target_date,
    news_list,
    llm_result,
    charts,
    supply,
    scorer,
    position_sizer,
    themes: Optional[List[str]] = None,
) -> Optional[Signal]:
    """최종 시그널 생성 헬퍼."""
    try:
        score, checklist, score_details = scorer.calculate(stock, charts, news_list, supply, llm_result)

        if llm_result:
            score_details["ai_evaluation"] = llm_result
            score.ai_evaluation = llm_result

        grade = scorer.determine_grade(stock, score, score_details, supply, charts)
        if not grade:
            print(
                "    [DEBUG] 등급탈락 %s: Score=%s, Value=%s억, Rise=%s%%, VolRatio=%s"
                % (
                    stock.name,
                    score.total,
                    stock.trading_value // 100_000_000,
                    stock.change_pct,
                    score_details.get("volume_ratio", 0),
                )
            )
            return None

        position = position_sizer.calculate(stock.close, grade)

        return Signal(
            stock_code=stock.code,
            stock_name=stock.name,
            market=stock.market,
            sector=stock.sector,
            signal_date=target_date,
            signal_time=datetime.now(),
            grade=grade,
            score=score,
            checklist=checklist,
            news_items=[
                {
                    "title": n.title,
                    "source": n.source,
                    "published_at": n.published_at.isoformat() if n.published_at else "",
                    "url": n.url,
                    "weight": getattr(n, "weight", 1.0),
                }
                for n in news_list[:5]
            ],
            current_price=stock.close,
            change_pct=stock.change_pct,
            entry_price=position.entry_price,
            stop_price=position.stop_price,
            target_price=position.target_price,
            r_value=position.r_value,
            position_size=position.position_size,
            quantity=position.quantity,
            r_multiplier=position.r_multiplier,
            trading_value=stock.trading_value,
            volume_ratio=int(score_details.get("volume_ratio", 0.0)),
            status=SignalStatus.PENDING,
            created_at=datetime.now(),
            score_details=score_details,
            ai_evaluation=llm_result,
            themes=themes or [],
        )
    except Exception as error:
        print(f"    ⚠️ 시그널 생성 오류 {stock.name}: {error}")
        return None


async def analyze_stock(
    *,
    stock: StockData,
    target_date: date,
    collector,
    news_collector,
    llm_analyzer,
    scorer,
    position_sizer,
    config,
) -> Optional[Signal]:
    """단일 종목 분석 (기존 호환용 - Batch 미사용)."""
    base_data = await analyze_base(
        stock=stock,
        collector=collector,
        scorer=scorer,
        config=config,
    )
    if not base_data:
        return None

    news_list = await news_collector.get_stock_news(stock.code, 3, stock.name)

    llm_result = None
    if news_list and llm_analyzer.client:
        print(f"    [LLM] Analyzing {stock.name} news...")
        news_dicts = [{"title": n.title, "summary": n.summary} for n in news_list]
        llm_result = await llm_analyzer.analyze_news_sentiment(stock.name, news_dicts)

    return create_final_signal(
        stock=stock,
        target_date=target_date,
        news_list=news_list,
        llm_result=llm_result,
        charts=base_data["charts"],
        supply=base_data["supply"],
        scorer=scorer,
        position_sizer=position_sizer,
    )


def build_signal_summary(signals: List[Signal]) -> Dict:
    """시그널 요약 정보."""
    summary = {
        "total": len(signals),
        "by_grade": {grade: 0 for grade in ["S", "A", "B"]},
        "by_market": {},
        "total_position": 0,
        "total_risk": 0,
    }

    for signal in signals:
        if hasattr(signal, "grade"):
            grade_val = getattr(signal.grade, "value", signal.grade)
            if grade_val in summary["by_grade"]:
                summary["by_grade"][grade_val] += 1

        if hasattr(signal, "market"):
            summary["by_market"][signal.market] = summary["by_market"].get(signal.market, 0) + 1

        if hasattr(signal, "position_size"):
            summary["total_position"] += signal.position_size

        if hasattr(signal, "r_value") and hasattr(signal, "r_multiplier"):
            summary["total_risk"] += signal.r_value * signal.r_multiplier

    return summary

