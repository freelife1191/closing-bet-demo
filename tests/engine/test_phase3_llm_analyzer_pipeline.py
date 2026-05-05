#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase3LLMAnalyzer 통합 동작 회귀 테스트.

매일 종가베팅 생성 파이프라인의 Phase3 → 어댑터 → analyze_news_batch_jongga
호출 → 결과 매핑 흐름을 가짜 LLMAnalyzer로 모킹해서 검증한다.

검증 포인트:
- analyze_news_batch_jongga가 호출되는 입력 shape이 dict 형태로 어댑터 통과 후의 형태인지
- 빈 입력/LLM 클라이언트 None 케이스에서 안전 종료
- 청크 분할/병합이 종목명을 키로 정확히 합쳐지는지
- analyze_news_batch(VCP)가 절대 호출되지 않는지 (잘못된 분기 방지)
- chunk 처리 중 일부 예외가 발생해도 전체 실행은 계속되는지
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from engine.models import ScoreDetail, StockData, SupplyData
from engine.phases_news_llm import Phase3LLMAnalyzer


def _stock(code: str, name: str) -> StockData:
    return StockData(
        code=code,
        name=name,
        market="KOSPI",
        sector="전기전자",
        close=80_000,
        change_pct=8.07,
        trading_value=8_358_799_527_000,
        volume=10_000_000,
    )


def _phase2_item(code: str, name: str) -> Dict[str, Any]:
    return {
        "stock": _stock(code, name),
        "charts": None,
        "supply": SupplyData(foreign_buy_5d=10_000_000_000, inst_buy_5d=5_000_000_000),
        "pre_score": ScoreDetail(total=11, news=2, volume=3, chart=2, candle=1, timing=1, supply=2),
        "score_details": {
            "foreign_net_buy": 10_000_000_000,
            "inst_net_buy": 5_000_000_000,
            "bonus_breakdown": {"volume": 1, "candle": 0, "limit_up": 0},
        },
        "temp_grade": "B",
        "vcp": None,
        "news": [
            {"title": f"{name} 뉴스 A", "weight": 1.5},
            {"title": f"{name} 뉴스 B", "weight": 1.0},
        ],
    }


class _FakeLLMAnalyzer:
    """analyze_news_batch_jongga만 구현한 가짜 분석기.

    호출 시 입력을 그대로 기록해두고, 종목명별로 결정적 결과 dict을 반환한다.
    """

    def __init__(self, fail_on_chunk: int | None = None) -> None:
        self.client = SimpleNamespace(name="fake-client")
        self.calls_jongga: List[List[Dict[str, Any]]] = []
        self.calls_market_status: List[Any] = []
        self.calls_vcp: List[List[Dict[str, Any]]] = []  # 잘못된 분기 감지용
        self._fail_on_chunk = fail_on_chunk

    async def analyze_news_batch_jongga(self, items, market_status=None):
        self.calls_jongga.append(list(items))
        self.calls_market_status.append(market_status)
        if (
            self._fail_on_chunk is not None
            and len(self.calls_jongga) == self._fail_on_chunk
        ):
            raise RuntimeError("simulated LLM failure for chunk")
        out: Dict[str, Dict[str, Any]] = {}
        for it in items:
            stock = it.get("stock") or {}
            name = stock.get("stock_name") or "unknown"
            out[name] = {
                "action": "BUY",
                "confidence": 75,
                "reason": "테스트 응답: ① 호재 ② 거래대금 ③ 차트 ④ 수급 ⑤ 결론",
                "model": "fake-model",
            }
        return out

    async def analyze_news_batch(self, items, market_status=None):  # noqa: D401
        """호출되면 안 됨. VCP 경로로 잘못 가는지 감시."""
        self.calls_vcp.append(list(items))
        return {}

    async def close(self):
        return None


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------

class TestPhase3HappyPath:
    def test_returns_one_entry_per_input_stock(self):
        analyzer = _FakeLLMAnalyzer()
        # chunk_size=2, concurrency=2, no delay → 5개 종목 → 3 chunk
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=2, concurrency=2, request_delay=0)
        items = [_phase2_item(f"00000{i}", f"종목{i}") for i in range(5)]
        result = asyncio.run(phase3.execute(items, market_status={"is_bullish": True}))

        assert set(result.keys()) == {f"종목{i}" for i in range(5)}
        for v in result.values():
            assert v["action"] == "BUY"
            assert "①" in v["reason"]

    def test_does_not_call_vcp_path(self):
        analyzer = _FakeLLMAnalyzer()
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=5, concurrency=1, request_delay=0)
        items = [_phase2_item("000001", "테스트종목")]
        asyncio.run(phase3.execute(items, market_status=None))
        assert analyzer.calls_vcp == [], "VCP 분기로 잘못 호출되면 안 됨"
        assert len(analyzer.calls_jongga) == 1

    def test_passes_adapted_dict_shape_to_llm(self):
        """analyze_news_batch_jongga가 받는 입력은 어댑터 통과 후의 dict.

        - stock은 dict이며 stock_code/stock_name/score/score_details 키 보유
        - supply는 dict이며 foreign_buy_5d/inst_buy_5d 키 보유
        """
        analyzer = _FakeLLMAnalyzer()
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=5, concurrency=1, request_delay=0)
        items = [_phase2_item("005930", "삼성전자")]
        asyncio.run(phase3.execute(items, market_status=None))

        assert len(analyzer.calls_jongga) == 1
        sent = analyzer.calls_jongga[0]
        assert isinstance(sent, list) and len(sent) == 1

        sent_item = sent[0]
        # stock은 dict, 객체 아님
        assert isinstance(sent_item["stock"], dict)
        assert sent_item["stock"]["stock_code"] == "005930"
        assert sent_item["stock"]["stock_name"] == "삼성전자"
        assert "score" in sent_item["stock"]
        assert sent_item["stock"]["score"]["total"] == 11
        assert sent_item["stock"]["score"]["news"] == 2
        # supply는 dict
        assert sent_item["supply"]["foreign_buy_5d"] == 10_000_000_000
        assert sent_item["supply"]["inst_buy_5d"] == 5_000_000_000
        # news 그대로 통과
        assert len(sent_item["news"]) == 2

    def test_market_status_passes_through_each_chunk(self):
        analyzer = _FakeLLMAnalyzer()
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=2, concurrency=2, request_delay=0)
        items = [_phase2_item(f"00000{i}", f"종목{i}") for i in range(4)]
        market_status = {"is_bullish": True, "score": 70}
        asyncio.run(phase3.execute(items, market_status=market_status))

        # 모든 청크 호출에 동일한 market_status 전달
        assert all(ms == market_status for ms in analyzer.calls_market_status)
        assert len(analyzer.calls_market_status) == 2  # 4 items / chunk 2 = 2 chunks


# ---------------------------------------------------------------------------
# 빈 입력 / 클라이언트 없음
# ---------------------------------------------------------------------------

class TestPhase3DegradedInputs:
    def test_empty_items_returns_empty(self):
        analyzer = _FakeLLMAnalyzer()
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=5, concurrency=1, request_delay=0)
        result = asyncio.run(phase3.execute([], market_status=None))
        assert result == {}
        assert analyzer.calls_jongga == []

    def test_no_client_returns_empty(self):
        analyzer = _FakeLLMAnalyzer()
        analyzer.client = None
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=5, concurrency=1, request_delay=0)
        items = [_phase2_item("000001", "종목1")]
        result = asyncio.run(phase3.execute(items, market_status=None))
        assert result == {}
        assert analyzer.calls_jongga == []


# ---------------------------------------------------------------------------
# 일부 청크 실패 시에도 나머지는 진행
# ---------------------------------------------------------------------------

class TestPhase3ChunkResilience:
    def test_one_chunk_failure_does_not_break_others(self):
        # 두 번째 청크에서만 실패
        analyzer = _FakeLLMAnalyzer(fail_on_chunk=2)
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=2, concurrency=1, request_delay=0)
        items = [_phase2_item(f"00000{i}", f"종목{i}") for i in range(4)]
        result = asyncio.run(phase3.execute(items, market_status=None))

        # 4개 중 2개만 살아남음 (실패한 청크의 2개는 누락)
        assert len(result) == 2
        # stats에 failed 2 누적
        assert phase3.stats["failed"] == 2
        assert phase3.stats["passed"] == 2


# ---------------------------------------------------------------------------
# 청킹 로직
# ---------------------------------------------------------------------------

class TestPhase3Chunking:
    def test_chunk_split_respects_chunk_size(self):
        analyzer = _FakeLLMAnalyzer()
        phase3 = Phase3LLMAnalyzer(analyzer, chunk_size=3, concurrency=2, request_delay=0)
        items = [_phase2_item(f"00000{i}", f"종목{i}") for i in range(7)]
        asyncio.run(phase3.execute(items, market_status=None))

        # 7개 / chunk 3 = 3 chunks (3, 3, 1)
        assert len(analyzer.calls_jongga) == 3
        chunk_sizes = sorted(len(c) for c in analyzer.calls_jongga)
        assert chunk_sizes == [1, 3, 3]
