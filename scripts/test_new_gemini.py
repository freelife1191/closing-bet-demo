#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vertex AI 기반 LLMAnalyzer 동작 점검."""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))


async def test_gemini() -> bool:
    try:
        from engine.config import app_config
        from engine.llm_analyzer import LLMAnalyzer

        print("Testing Gemini SDK migration (Vertex AI)...")
        print(f"Model: {app_config.GEMINI_MODEL}")

        analyzer = LLMAnalyzer()  # api_key 인자는 더 이상 사용하지 않음

        test_news = [
            {
                "title": "삼성전자, 4분기 영업이익 10조원 기록... 어닝 서프라이즈",
                "summary": "삼성전자가 메모리 반도체 수요 회복에 힘입어 4분기 어닝 서프라이즈를 기록했습니다.",
            },
            {
                "title": "반도체 수출 호조 지속... 올해 역대 최대 수출 기대",
                "summary": "반도체 산업의 수출 호조가 지속되면서 올해는 수출 기록을 경신할 것으로 보입니다.",
            },
        ]

        print("Analyzing news...")
        result = await analyzer.analyze_news_sentiment("삼성전자", test_news)

        if result:
            print("\nAnalysis Result:")
            print(f"Score : {result.get('score')}")
            print(f"Reason: {result.get('reason')}")
            return True
        print("\nAnalysis failed. Check logs.")
        return False
    except Exception as e:
        print(f"Error during testing: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_gemini())
    sys.exit(0 if success else 1)
